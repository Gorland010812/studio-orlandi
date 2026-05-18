from datetime import datetime, date, timedelta, time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import BaseModel

from database import get_db
from models import Appuntamento, Disponibilita, TipoVisita, Paziente
from routers.auth import get_current_user

router = APIRouter(prefix="/api/appuntamenti", tags=["appuntamenti"])

# ── Schemi Pydantic ────────────────────────────────────────────────────────────

class AppuntamentoCreate(BaseModel):
    data_ora: datetime
    tipo_visita_id: Optional[int] = None
    sede_id: Optional[int] = None
    paziente_id: Optional[int] = None
    durata_minuti: int = 30
    stato: str = "confermato"
    note: Optional[str] = None
    nome_paziente: Optional[str] = None
    cognome_paziente: Optional[str] = None
    telefono_paziente: Optional[str] = None
    email_paziente: Optional[str] = None

class AppuntamentoUpdate(BaseModel):
    data_ora: Optional[datetime] = None
    tipo_visita_id: Optional[int] = None
    sede_id: Optional[int] = None
    paziente_id: Optional[int] = None
    durata_minuti: Optional[int] = None
    stato: Optional[str] = None
    note: Optional[str] = None
    nome_paziente: Optional[str] = None
    cognome_paziente: Optional[str] = None
    telefono_paziente: Optional[str] = None
    email_paziente: Optional[str] = None


def _app_to_dict(a: Appuntamento, db: Session) -> dict:
    paziente = db.query(Paziente).filter(Paziente.id == a.paziente_id).first() if a.paziente_id else None
    tipo = db.query(TipoVisita).filter(TipoVisita.id == a.tipo_visita_id).first() if a.tipo_visita_id else None

    nome_display = (
        f"{paziente.cognome} {paziente.nome}" if paziente
        else f"{a.cognome_paziente or ''} {a.nome_paziente or ''}".strip() or "—"
    )

    return {
        "id": a.id,
        "data_ora": a.data_ora.isoformat(),
        "durata_minuti": a.durata_minuti,
        "stato": a.stato,
        "note": a.note,
        "paziente_id": a.paziente_id,
        "nome_display": nome_display,
        "tipo_visita_id": a.tipo_visita_id,
        "tipo_visita_nome": tipo.nome if tipo else None,
        "tipo_visita_colore": tipo.colore if tipo else "#0F6E56",
        "sede_id": a.sede_id,
        "nome_paziente": a.nome_paziente,
        "cognome_paziente": a.cognome_paziente,
        "telefono_paziente": a.telefono_paziente,
        "email_paziente": a.email_paziente,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ── Calcolo slot liberi ────────────────────────────────────────────────────────

def _parse_time(t: str) -> time:
    h, m = map(int, t.split(":"))
    return time(h, m)


def _genera_slot(data: date, disp: Disponibilita, durata: int) -> list[datetime]:
    """Genera tutti gli slot teorici per un giorno di disponibilità."""
    slot = []
    for inizio_str, fine_str in [
        (disp.ora_inizio_mattina, disp.ora_fine_mattina),
        (disp.ora_inizio_pomeriggio, disp.ora_fine_pomeriggio),
    ]:
        if not inizio_str or not fine_str:
            continue
        inizio = datetime.combine(data, _parse_time(inizio_str))
        fine   = datetime.combine(data, _parse_time(fine_str))
        t = inizio
        while t + timedelta(minutes=durata) <= fine:
            slot.append(t)
            t += timedelta(minutes=durata)
    return slot


def _slot_occupato(slot_inizio: datetime, durata: int, appuntamenti: list) -> bool:
    slot_fine = slot_inizio + timedelta(minutes=durata)
    for a in appuntamenti:
        a_inizio = a.data_ora
        a_fine   = a_inizio + timedelta(minutes=a.durata_minuti)
        # Sovrapposizione se gli intervalli si intersecano
        if a_inizio < slot_fine and slot_inizio < a_fine:
            return True
    return False


def calcola_slot_giorno(db: Session, data: date, durata_minuti: int) -> dict:
    """Slot liberi per un giorno specifico (endpoint medico, senza limiti di data)."""
    dow = data.weekday()
    disp = db.query(Disponibilita).filter(
        Disponibilita.giorno_settimana == dow,
        Disponibilita.attivo == True,
    ).first()
    if not disp:
        return {"slot": [], "ha_disponibilita": False}
    slot_teorici = _genera_slot(data, disp, durata_minuti)
    app_giorno = (
        db.query(Appuntamento)
        .filter(
            Appuntamento.stato.notin_(["annullato"]),
            Appuntamento.data_ora >= datetime.combine(data, time(0, 0)),
            Appuntamento.data_ora < datetime.combine(data, time(23, 59)),
        )
        .all()
    )
    slot_liberi = [
        s.strftime("%H:%M")
        for s in slot_teorici
        if not _slot_occupato(s, durata_minuti, app_giorno)
    ]
    return {"slot": slot_liberi, "ha_disponibilita": True}


def calcola_slot_liberi(
    db: Session,
    durata_minuti: int,
    giorni_da_cercare: int = 30,
    max_giorni_con_slot: int = 10,
) -> list[dict]:
    disponibilita = db.query(Disponibilita).filter(Disponibilita.attivo == True).all()
    if not disponibilita:
        return []

    disp_map = {d.giorno_settimana: d for d in disponibilita}

    oggi = date.today()
    domani = oggi + timedelta(days=1)

    # Precarica appuntamenti del periodo
    fine_periodo = domani + timedelta(days=giorni_da_cercare)
    appuntamenti = (
        db.query(Appuntamento)
        .filter(
            Appuntamento.stato.notin_(["annullato"]),
            Appuntamento.data_ora >= datetime.combine(domani, time(0, 0)),
            Appuntamento.data_ora < datetime.combine(fine_periodo, time(23, 59)),
        )
        .all()
    )

    risultati = []
    giorno_corrente = domani

    while giorno_corrente < fine_periodo and len(risultati) < max_giorni_con_slot:
        # 0=Lunedì in Python isoweekday → 0=Lunedì in nostro schema
        dow = giorno_corrente.weekday()
        if dow in disp_map:
            disp = disp_map[dow]
            slot_teorici = _genera_slot(giorno_corrente, disp, durata_minuti)

            # Appuntamenti del giorno
            app_giorno = [
                a for a in appuntamenti
                if a.data_ora.date() == giorno_corrente
            ]

            slot_liberi = [
                s.strftime("%H:%M")
                for s in slot_teorici
                if not _slot_occupato(s, durata_minuti, app_giorno)
            ]

            if slot_liberi:
                risultati.append({
                    "data": giorno_corrente.isoformat(),
                    "giorno_settimana": dow,
                    "slot": slot_liberi,
                })

        giorno_corrente += timedelta(days=1)

    return risultati


# ── Endpoints ──────────────────────────────────────────────────────────────────

# ATTENZIONE: /mese/{anno}/{mese} deve stare PRIMA di /{id}

@router.get("/mese/{anno}/{mese}")
def appuntamenti_mese(
    anno: int,
    mese: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    if not (1 <= mese <= 12):
        raise HTTPException(status_code=422, detail="Mese non valido")

    inizio = datetime(anno, mese, 1)
    if mese == 12:
        fine = datetime(anno + 1, 1, 1)
    else:
        fine = datetime(anno, mese + 1, 1)

    appuntamenti = (
        db.query(Appuntamento)
        .filter(
            Appuntamento.data_ora >= inizio,
            Appuntamento.data_ora < fine,
        )
        .order_by(Appuntamento.data_ora)
        .all()
    )
    return [_app_to_dict(a, db) for a in appuntamenti]


@router.get("/slot-liberi")
def slot_liberi(
    tipo_visita_id: Optional[int] = Query(None),
    durata_minuti: Optional[int] = Query(None),
    data: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    durata = durata_minuti
    if not durata and tipo_visita_id:
        tv = db.query(TipoVisita).filter(TipoVisita.id == tipo_visita_id).first()
        durata = tv.durata_minuti if tv else 30
    if not durata:
        durata = 30
    if data:
        return calcola_slot_giorno(db, data, durata)
    return calcola_slot_liberi(db, durata)


@router.get("")
def lista_appuntamenti(
    data_inizio: Optional[date] = Query(None),
    data_fine: Optional[date] = Query(None),
    stato: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(Appuntamento)
    if data_inizio:
        query = query.filter(Appuntamento.data_ora >= datetime.combine(data_inizio, time(0, 0)))
    if data_fine:
        query = query.filter(Appuntamento.data_ora <= datetime.combine(data_fine, time(23, 59)))
    if stato:
        query = query.filter(Appuntamento.stato == stato)
    appuntamenti = query.order_by(Appuntamento.data_ora).all()
    return [_app_to_dict(a, db) for a in appuntamenti]


@router.get("/{appuntamento_id}")
def dettaglio_appuntamento(
    appuntamento_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    a = db.query(Appuntamento).filter(Appuntamento.id == appuntamento_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")
    return _app_to_dict(a, db)


@router.post("", status_code=201)
def crea_appuntamento(
    body: AppuntamentoCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    # Prendi durata dal tipo visita se non specificata
    durata = body.durata_minuti
    if body.tipo_visita_id:
        tv = db.query(TipoVisita).filter(TipoVisita.id == body.tipo_visita_id).first()
        if tv:
            durata = tv.durata_minuti

    a = Appuntamento(
        data_ora=body.data_ora,
        tipo_visita_id=body.tipo_visita_id,
        sede_id=body.sede_id,
        paziente_id=body.paziente_id,
        durata_minuti=durata,
        stato=body.stato,
        note=body.note,
        nome_paziente=body.nome_paziente,
        cognome_paziente=body.cognome_paziente,
        telefono_paziente=body.telefono_paziente,
        email_paziente=body.email_paziente,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _app_to_dict(a, db)


@router.put("/{appuntamento_id}")
def modifica_appuntamento(
    appuntamento_id: int,
    body: AppuntamentoUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    a = db.query(Appuntamento).filter(Appuntamento.id == appuntamento_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")

    dati = body.model_dump(exclude_unset=True)
    for k, v in dati.items():
        setattr(a, k, v)

    db.commit()
    db.refresh(a)
    return _app_to_dict(a, db)


@router.delete("/{appuntamento_id}", status_code=204)
def elimina_appuntamento(
    appuntamento_id: int,
    annulla: bool = Query(False),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    a = db.query(Appuntamento).filter(Appuntamento.id == appuntamento_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")

    if annulla:
        a.stato = "annullato"
        db.commit()
    else:
        db.delete(a)
        db.commit()
