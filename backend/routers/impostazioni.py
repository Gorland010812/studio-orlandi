from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models import Impostazioni, Sede, TipoVisita, Disponibilita, Appuntamento, FotoSito
from routers.auth import get_current_user

# Router separati — inclusi singolarmente in main.py
router_impostazioni = APIRouter(prefix="/api/impostazioni", tags=["impostazioni"])
router_sedi = APIRouter(prefix="/api/sedi", tags=["sedi"])
router_tipi_visita = APIRouter(prefix="/api/tipi-visita", tags=["tipi-visita"])
router_disponibilita = APIRouter(prefix="/api/disponibilita", tags=["disponibilita"])
router_sito = APIRouter(prefix="/api/sito", tags=["sito"])


# ── Schemi ────────────────────────────────────────────────────────────────────

class ImpostazioniUpdate(BaseModel):
    nome_medico: Optional[str] = None
    specializzazioni: Optional[str] = None
    servizi: Optional[str] = None
    testo_home: Optional[str] = None
    username: Optional[str] = None
    bio_testo: Optional[str] = None
    piva: Optional[str] = None
    google_reviews_link: Optional[str] = None
    numero_telefono: Optional[str] = None

class FotoUpdate(BaseModel):
    immagine_base64: Optional[str] = None

class SedeCreate(BaseModel):
    nome: str
    indirizzo: Optional[str] = None
    citta: Optional[str] = None
    provincia: Optional[str] = None
    cap: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    ordine: int = 0
    attiva: bool = True

class SedeUpdate(SedeCreate):
    nome: Optional[str] = None

class TipoVisitaCreate(BaseModel):
    nome: str
    durata_minuti: int = 30
    colore: str = "#0F6E56"
    attivo: bool = True
    ordine: int = 0
    costo: Optional[float] = None
    note: Optional[str] = None

class TipoVisitaUpdate(TipoVisitaCreate):
    nome: Optional[str] = None

class DisponibilitaItem(BaseModel):
    giorno_settimana: int
    ora_inizio_mattina: str = "08:30"
    ora_fine_mattina: str = "13:00"
    ora_inizio_pomeriggio: str = "15:30"
    ora_fine_pomeriggio: str = "19:00"
    attivo: bool = True

class DisponibilitaUpdate(BaseModel):
    disponibilita: list[DisponibilitaItem]


# ── /api/impostazioni ─────────────────────────────────────────────────────────

@router_impostazioni.get("")
def get_impostazioni(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    imp = db.query(Impostazioni).first()
    if not imp:
        raise HTTPException(status_code=404, detail="Impostazioni non trovate")
    return {
        "id": imp.id,
        "nome_medico": imp.nome_medico,
        "specializzazioni": imp.specializzazioni,
        "servizi": imp.servizi,
        "testo_home": imp.testo_home,
        "username": imp.username,
        "bio_testo": imp.bio_testo,
        "piva": imp.piva,
        "google_reviews_link": imp.google_reviews_link,
        "numero_telefono": imp.numero_telefono,
    }


@router_impostazioni.put("")
def update_impostazioni(
    body: ImpostazioniUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    imp = db.query(Impostazioni).first()
    if not imp:
        raise HTTPException(status_code=404, detail="Impostazioni non trovate")

    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "username" and v and len(v.strip()) < 3:
            raise HTTPException(status_code=422, detail="Username deve avere almeno 3 caratteri")
        setattr(imp, k, v)

    db.commit()
    db.refresh(imp)
    return {"message": "Impostazioni aggiornate"}


# ── /api/sedi ─────────────────────────────────────────────────────────────────

def _sede_to_dict(s: Sede) -> dict:
    return {
        "id": s.id, "nome": s.nome, "indirizzo": s.indirizzo,
        "citta": s.citta, "provincia": s.provincia, "cap": s.cap,
        "telefono": s.telefono, "email": s.email,
        "ordine": s.ordine, "attiva": s.attiva,
    }

@router_sedi.get("")
def lista_sedi(db: Session = Depends(get_db), _=Depends(get_current_user)):
    sedi = db.query(Sede).order_by(Sede.ordine, Sede.id).all()
    return [_sede_to_dict(s) for s in sedi]


@router_sedi.post("", status_code=201)
def crea_sede(body: SedeCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    s = Sede(**body.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return _sede_to_dict(s)


@router_sedi.put("/{sede_id}")
def modifica_sede(sede_id: int, body: SedeUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    s = db.query(Sede).filter(Sede.id == sede_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sede non trovata")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return _sede_to_dict(s)


@router_sedi.delete("/{sede_id}", status_code=204)
def elimina_sede(sede_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    s = db.query(Sede).filter(Sede.id == sede_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sede non trovata")
    db.delete(s)
    db.commit()


# ── /api/tipi-visita ──────────────────────────────────────────────────────────

def _tv_to_dict(tv: TipoVisita) -> dict:
    return {
        "id": tv.id, "nome": tv.nome, "durata_minuti": tv.durata_minuti,
        "colore": tv.colore, "attivo": tv.attivo, "ordine": tv.ordine,
        "costo": float(tv.costo) if tv.costo is not None else None,
        "note": tv.note,
    }

@router_tipi_visita.get("")
def lista_tipi_visita(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [_tv_to_dict(tv) for tv in db.query(TipoVisita).order_by(TipoVisita.ordine, TipoVisita.id).all()]


@router_tipi_visita.post("", status_code=201)
def crea_tipo_visita(body: TipoVisitaCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    tv = TipoVisita(**body.model_dump())
    db.add(tv)
    db.commit()
    db.refresh(tv)
    return _tv_to_dict(tv)


@router_tipi_visita.put("/{tv_id}")
def modifica_tipo_visita(tv_id: int, body: TipoVisitaUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    tv = db.query(TipoVisita).filter(TipoVisita.id == tv_id).first()
    if not tv:
        raise HTTPException(status_code=404, detail="Tipo visita non trovato")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(tv, k, v)
    db.commit()
    db.refresh(tv)
    return _tv_to_dict(tv)


@router_tipi_visita.delete("/{tv_id}", status_code=204)
def elimina_tipo_visita(tv_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    tv = db.query(TipoVisita).filter(TipoVisita.id == tv_id).first()
    if not tv:
        raise HTTPException(status_code=404, detail="Tipo visita non trovato")
    db.query(Appuntamento).filter(Appuntamento.tipo_visita_id == tv_id).update({"tipo_visita_id": None})
    db.delete(tv)
    db.commit()


# ── /api/disponibilita ────────────────────────────────────────────────────────

def _disp_to_dict(d: Disponibilita) -> dict:
    giorni = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    return {
        "id": d.id,
        "giorno_settimana": d.giorno_settimana,
        "giorno_nome": giorni[d.giorno_settimana] if 0 <= d.giorno_settimana <= 6 else "",
        "ora_inizio_mattina": d.ora_inizio_mattina,
        "ora_fine_mattina": d.ora_fine_mattina,
        "ora_inizio_pomeriggio": d.ora_inizio_pomeriggio,
        "ora_fine_pomeriggio": d.ora_fine_pomeriggio,
        "attivo": d.attivo,
    }

@router_disponibilita.get("")
def get_disponibilita(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [_disp_to_dict(d) for d in db.query(Disponibilita).order_by(Disponibilita.giorno_settimana).all()]


@router_disponibilita.put("")
def update_disponibilita(body: DisponibilitaUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    for item in body.disponibilita:
        d = db.query(Disponibilita).filter(Disponibilita.giorno_settimana == item.giorno_settimana).first()
        if d:
            d.ora_inizio_mattina    = item.ora_inizio_mattina
            d.ora_fine_mattina      = item.ora_fine_mattina
            d.ora_inizio_pomeriggio = item.ora_inizio_pomeriggio
            d.ora_fine_pomeriggio   = item.ora_fine_pomeriggio
            d.attivo                = item.attivo
        else:
            db.add(Disponibilita(**item.model_dump()))
    db.commit()
    return {"message": "Disponibilità aggiornata"}


# ── /api/sito ─────────────────────────────────────────────────────────────────

@router_sito.get("/contenuti")
def get_contenuti_sito(db: Session = Depends(get_db)):
    imp = db.query(Impostazioni).first()
    sedi = db.query(Sede).filter(Sede.attiva == True).order_by(Sede.ordine, Sede.id).all()
    tv = db.query(TipoVisita).filter(TipoVisita.attivo == True).order_by(TipoVisita.ordine, TipoVisita.id).all()
    foto_rows = db.query(FotoSito).all()
    foto = {f.tipo: f.immagine_base64 for f in foto_rows if f.immagine_base64}
    return {
        "impostazioni": {
            "nome_medico": imp.nome_medico if imp else None,
            "specializzazioni": imp.specializzazioni if imp else None,
            "servizi": imp.servizi if imp else None,
            "bio_testo": imp.bio_testo if imp else None,
            "piva": imp.piva if imp else None,
            "google_reviews_link": imp.google_reviews_link if imp else None,
            "numero_telefono": imp.numero_telefono if imp else None,
        } if imp else {},
        "sedi": [_sede_to_dict(s) for s in sedi],
        "tipi_visita": [
            {
                "nome": t.nome,
                "durata_minuti": t.durata_minuti,
                "colore": t.colore,
                "costo": float(t.costo) if t.costo is not None else None,
                "note": t.note,
            }
            for t in tv
        ],
        "foto": foto,
    }


@router_sito.get("/foto/{tipo}")
def get_foto(tipo: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    if tipo not in ("hero", "chisono", "logo"):
        raise HTTPException(status_code=400, detail="Tipo foto non valido")
    foto = db.query(FotoSito).filter(FotoSito.tipo == tipo).first()
    if not foto:
        return {"tipo": tipo, "immagine_base64": None}
    return {"tipo": foto.tipo, "immagine_base64": foto.immagine_base64}


@router_sito.put("/foto/{tipo}")
def update_foto(tipo: str, body: FotoUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    if tipo not in ("hero", "chisono", "logo"):
        raise HTTPException(status_code=400, detail="Tipo foto non valido")
    foto = db.query(FotoSito).filter(FotoSito.tipo == tipo).first()
    if foto:
        foto.immagine_base64 = body.immagine_base64
    else:
        db.add(FotoSito(tipo=tipo, immagine_base64=body.immagine_base64))
    db.commit()
    return {"message": "Foto aggiornata"}


@router_sito.delete("/foto/{tipo}", status_code=204)
def delete_foto(tipo: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    if tipo not in ("hero", "chisono", "logo"):
        raise HTTPException(status_code=400, detail="Tipo foto non valido")
    foto = db.query(FotoSito).filter(FotoSito.tipo == tipo).first()
    if foto:
        db.delete(foto)
        db.commit()
