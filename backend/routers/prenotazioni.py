"""
Endpoints pubblici per il portale prenotazioni pazienti.
Nessuna autenticazione richiesta — rate limiting su POST /richiesta.
"""
from collections import defaultdict
from time import time as now
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from pydantic import BaseModel

from database import get_db
from models import Impostazioni, Sede, TipoVisita, Appuntamento, Paziente, ComuneItaliano
from routers.appuntamenti import calcola_slot_liberi

router = APIRouter(prefix="/api/prenota", tags=["portale"])

# ── Rate limiting in-memory (max 10 POST /richiesta per IP per ora) ───────────

_rate_store: dict[str, list[float]] = defaultdict(list)
_RATE_MAX = 10
_RATE_WINDOW = 3600  # secondi


def _check_rate(ip: str):
    soglia = now() - _RATE_WINDOW
    _rate_store[ip] = [t for t in _rate_store[ip] if t > soglia]
    if len(_rate_store[ip]) >= _RATE_MAX:
        raise HTTPException(
            status_code=429,
            detail="Troppi tentativi. Riprova tra un'ora.",
        )
    _rate_store[ip].append(now())


def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Schemi ────────────────────────────────────────────────────────────────────

class RichiestaPrenotazione(BaseModel):
    tipo_visita_id: int
    data_ora: str           # ISO format: "2024-03-15T10:30:00"
    sede_id: Optional[int] = None
    # Dati paziente
    nome: str
    cognome: str
    data_nascita: Optional[str] = None
    sesso: Optional[str] = None
    codice_comune_nascita: Optional[str] = None
    luogo_nascita: Optional[str] = None
    provincia_nascita: Optional[str] = None
    codice_fiscale: Optional[str] = None
    citta_residenza: Optional[str] = None
    provincia_residenza: Optional[str] = None
    indirizzo: Optional[str] = None
    cap: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None
    # GDPR
    privacy_accettata: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/info-studio")
def info_studio(db: Session = Depends(get_db)):
    imp = db.query(Impostazioni).first()
    sedi = db.query(Sede).filter(Sede.attiva == True).order_by(Sede.ordine).all()
    return {
        "nome_medico": imp.nome_medico if imp else "Studio Medico",
        "specializzazioni": imp.specializzazioni if imp else "",
        "servizi": imp.servizi if imp else "",
        "testo_home": imp.testo_home if imp else "",
        "sedi": [
            {
                "id": s.id, "nome": s.nome, "indirizzo": s.indirizzo,
                "citta": s.citta, "cap": s.cap, "telefono": s.telefono, "email": s.email,
            }
            for s in sedi
        ],
    }


@router.get("/tipi-visita")
def tipi_visita_pubblici(db: Session = Depends(get_db)):
    tipi = (
        db.query(TipoVisita)
        .filter(TipoVisita.attivo == True)
        .order_by(TipoVisita.ordine, TipoVisita.id)
        .all()
    )
    return [
        {"id": t.id, "nome": t.nome, "durata_minuti": t.durata_minuti, "colore": t.colore}
        for t in tipi
    ]


@router.get("/slot-liberi")
def slot_liberi_pubblici(
    tipo_visita_id: int = Query(...),
    db: Session = Depends(get_db),
):
    tv = db.query(TipoVisita).filter(TipoVisita.id == tipo_visita_id, TipoVisita.attivo == True).first()
    if not tv:
        raise HTTPException(status_code=404, detail="Tipo visita non trovato")
    return calcola_slot_liberi(db, tv.durata_minuti)


@router.get("/cerca-paziente")
def cerca_paziente_pubblico(
    nome: str = Query(..., min_length=2),
    cognome: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    """
    Cerca paziente per autocompletamento nel portale.
    Restituisce solo i dati necessari per pre-popolare il form.
    """
    risultati = (
        db.query(Paziente)
        .filter(
            func.lower(Paziente.nome) == func.lower(nome.strip()),
            func.lower(Paziente.cognome) == func.lower(cognome.strip()),
        )
        .limit(5)
        .all()
    )
    return [
        {
            "id": p.id,
            "nome": p.nome,
            "cognome": p.cognome,
            "data_nascita": p.data_nascita.isoformat() if p.data_nascita else None,
            "sesso": p.sesso,
            "codice_fiscale": p.codice_fiscale,
            "luogo_nascita": p.luogo_nascita,
            "provincia_nascita": p.provincia_nascita,
            "codice_comune_nascita": p.codice_comune_nascita,
            "citta_residenza": p.citta_residenza,
            "provincia_residenza": p.provincia_residenza,
            "indirizzo": p.indirizzo,
            "cap": p.cap,
            "telefono": p.telefono,
            "email": p.email,
        }
        for p in risultati
    ]


@router.post("/richiesta", status_code=201)
def invia_richiesta(
    body: RichiestaPrenotazione,
    request: Request,
    db: Session = Depends(get_db),
):
    _check_rate(_get_ip(request))

    if not body.privacy_accettata:
        raise HTTPException(status_code=422, detail="Accettazione privacy obbligatoria")

    if not body.nome.strip() or not body.cognome.strip():
        raise HTTPException(status_code=422, detail="Nome e cognome obbligatori")

    if not body.telefono and not body.email:
        raise HTTPException(status_code=422, detail="Inserire almeno telefono o email")

    tv = db.query(TipoVisita).filter(TipoVisita.id == body.tipo_visita_id, TipoVisita.attivo == True).first()
    if not tv:
        raise HTTPException(status_code=404, detail="Tipo visita non trovato")

    from datetime import datetime
    try:
        data_ora = datetime.fromisoformat(body.data_ora)
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato data/ora non valido")

    if data_ora <= datetime.now():
        raise HTTPException(status_code=422, detail="La data deve essere nel futuro")

    # Crea appuntamento in stato "in_attesa" (il medico confermerà)
    appuntamento = Appuntamento(
        tipo_visita_id=body.tipo_visita_id,
        sede_id=body.sede_id,
        data_ora=data_ora,
        durata_minuti=tv.durata_minuti,
        stato="in_attesa",
        note=body.note,
        nome_paziente=body.nome.strip(),
        cognome_paziente=body.cognome.strip(),
        telefono_paziente=body.telefono,
        email_paziente=body.email,
    )
    db.add(appuntamento)
    db.commit()
    db.refresh(appuntamento)

    return {
        "id": appuntamento.id,
        "message": "Richiesta inviata con successo. Lo studio la contatterà per conferma.",
        "tipo_visita": tv.nome,
        "data_ora": data_ora.isoformat(),
    }


# ── Comuni (endpoint pubblico per calcolo CF nel portale) ─────────────────────

router_comuni = APIRouter(prefix="/api/comuni", tags=["comuni"])


@router_comuni.get("/province")
def lista_province(db: Session = Depends(get_db)):
    province = (
        db.query(ComuneItaliano.sigla_provincia, ComuneItaliano.provincia)
        .distinct()
        .order_by(ComuneItaliano.sigla_provincia)
        .all()
    )
    return [{"sigla": row[0], "nome": row[1]} for row in province]


@router_comuni.get("/cerca/{nome}")
def cerca_comune(nome: str, db: Session = Depends(get_db)):
    risultati = (
        db.query(ComuneItaliano)
        .filter(func.lower(ComuneItaliano.nome).like(func.lower(f"{nome}%")))
        .order_by(ComuneItaliano.nome)
        .limit(20)
        .all()
    )
    return [
        {
            "id": c.id, "nome": c.nome, "provincia": c.provincia,
            "sigla_provincia": c.sigla_provincia, "codice_istat": c.codice_istat,
            "cap": c.cap, "regione": c.regione,
        }
        for c in risultati
    ]


@router_comuni.get("/{sigla}")
def comuni_per_provincia(sigla: str, db: Session = Depends(get_db)):
    comuni = (
        db.query(ComuneItaliano)
        .filter(func.upper(ComuneItaliano.sigla_provincia) == sigla.upper())
        .order_by(ComuneItaliano.nome)
        .all()
    )
    return [
        {
            "id": c.id, "nome": c.nome, "codice_istat": c.codice_istat,
            "cap": c.cap,
        }
        for c in comuni
    ]
