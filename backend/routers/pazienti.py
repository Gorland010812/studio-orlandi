from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import BaseModel

from database import get_db
from models import Paziente, ComuneItaliano
from routers.auth import get_current_user

router = APIRouter(prefix="/api/pazienti", tags=["pazienti"])

# ── Codice Fiscale ─────────────────────────────────────────────────────────────

_MESI_CF = "ABCDEHLMPRST"

_DISPARI = {
    "0": 1,  "1": 0,  "2": 5,  "3": 7,  "4": 9,  "5": 13, "6": 15, "7": 17,
    "8": 19, "9": 21, "A": 1,  "B": 0,  "C": 5,  "D": 7,  "E": 9,  "F": 13,
    "G": 15, "H": 17, "I": 19, "J": 21, "K": 2,  "L": 4,  "M": 18, "N": 20,
    "O": 11, "P": 3,  "Q": 6,  "R": 8,  "S": 12, "T": 14, "U": 16, "V": 10,
    "W": 22, "X": 25, "Y": 24, "Z": 23,
}
_PARI = {
    "0": 0,  "1": 1,  "2": 2,  "3": 3,  "4": 4,  "5": 5,  "6": 6,  "7": 7,
    "8": 8,  "9": 9,  "A": 0,  "B": 1,  "C": 2,  "D": 3,  "E": 4,  "F": 5,
    "G": 6,  "H": 7,  "I": 8,  "J": 9,  "K": 10, "L": 11, "M": 12, "N": 13,
    "O": 14, "P": 15, "Q": 16, "R": 17, "S": 18, "T": 19, "U": 20, "V": 21,
    "W": 22, "X": 23, "Y": 24, "Z": 25,
}


def _pulisci(s: str) -> str:
    return s.upper().replace(" ", "").replace("'", "")


def _codifica_cognome(cognome: str) -> str:
    s = _pulisci(cognome)
    consonanti = [c for c in s if c.isalpha() and c not in "AEIOU"]
    vocali     = [c for c in s if c.isalpha() and c in "AEIOU"]
    result = (consonanti + vocali + ["X", "X", "X"])[:3]
    return "".join(result)


def _codifica_nome(nome: str) -> str:
    s = _pulisci(nome)
    consonanti = [c for c in s if c.isalpha() and c not in "AEIOU"]
    vocali     = [c for c in s if c.isalpha() and c in "AEIOU"]
    if len(consonanti) >= 4:
        result = [consonanti[0], consonanti[2], consonanti[3]]
    else:
        result = (consonanti + vocali + ["X", "X", "X"])[:3]
    return "".join(result)


def _carattere_controllo(cf15: str) -> str:
    totale = sum(
        _DISPARI[c] if i % 2 == 0 else _PARI[c]
        for i, c in enumerate(cf15)
    )
    return chr(ord("A") + totale % 26)


def calcola_codice_fiscale(
    cognome: str,
    nome: str,
    data_nascita: date,
    sesso: str,
    codice_belfiore: str,
) -> str:
    cf = (
        _codifica_cognome(cognome)
        + _codifica_nome(nome)
        + str(data_nascita.year)[-2:]
        + _MESI_CF[data_nascita.month - 1]
        + str(data_nascita.day + (40 if sesso == "F" else 0)).zfill(2)
        + codice_belfiore.upper()
    )
    return cf + _carattere_controllo(cf)


# ── Schemi Pydantic ────────────────────────────────────────────────────────────

class PazienteBase(BaseModel):
    cognome: str
    nome: str
    data_nascita: Optional[date] = None
    luogo_nascita: Optional[str] = None
    provincia_nascita: Optional[str] = None
    codice_comune_nascita: Optional[str] = None
    codice_fiscale: Optional[str] = None
    sesso: Optional[str] = None
    indirizzo: Optional[str] = None
    cap: Optional[str] = None
    citta_residenza: Optional[str] = None
    provincia_residenza: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    professione: Optional[str] = None
    medico_base: Optional[str] = None
    titolo_studio: Optional[str] = None
    stato_civile: Optional[str] = None
    inviato_da: Optional[str] = None
    note: Optional[str] = None

class PazienteCreate(PazienteBase):
    pass

class PazienteUpdate(PazienteBase):
    cognome: Optional[str] = None
    nome: Optional[str] = None


def _paziente_to_dict(p: Paziente) -> dict:
    return {
        "id": p.id,
        "cognome": p.cognome,
        "nome": p.nome,
        "data_nascita": p.data_nascita.isoformat() if p.data_nascita else None,
        "luogo_nascita": p.luogo_nascita,
        "provincia_nascita": p.provincia_nascita,
        "codice_comune_nascita": p.codice_comune_nascita,
        "codice_fiscale": p.codice_fiscale,
        "sesso": p.sesso,
        "indirizzo": p.indirizzo,
        "cap": p.cap,
        "citta_residenza": p.citta_residenza,
        "provincia_residenza": p.provincia_residenza,
        "telefono": p.telefono,
        "email": p.email,
        "professione": p.professione,
        "medico_base": p.medico_base,
        "titolo_studio": p.titolo_studio,
        "stato_civile": p.stato_civile,
        "inviato_da": p.inviato_da,
        "note": p.note,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/cerca")
def cerca_pazienti(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Ricerca per nome/cognome — usata per controllo duplicati."""
    termine = f"%{q}%"
    risultati = (
        db.query(Paziente)
        .filter(
            or_(
                func.lower(Paziente.cognome).like(func.lower(termine)),
                func.lower(Paziente.nome).like(func.lower(termine)),
                (func.lower(Paziente.cognome) + " " + func.lower(Paziente.nome)).like(func.lower(termine)),
                (func.lower(Paziente.nome) + " " + func.lower(Paziente.cognome)).like(func.lower(termine)),
            )
        )
        .order_by(Paziente.cognome, Paziente.nome)
        .limit(20)
        .all()
    )
    return [{"id": p.id, "cognome": p.cognome, "nome": p.nome,
             "data_nascita": p.data_nascita.isoformat() if p.data_nascita else None,
             "codice_fiscale": p.codice_fiscale, "telefono": p.telefono,
             "email": p.email, "provincia_nascita": p.provincia_nascita} for p in risultati]


@router.get("")
def lista_pazienti(
    q: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(Paziente)
    if q:
        termine = f"%{q}%"
        query = query.filter(
            or_(
                func.lower(Paziente.cognome).like(func.lower(termine)),
                func.lower(Paziente.nome).like(func.lower(termine)),
                func.lower(Paziente.codice_fiscale).like(func.lower(termine)),
            )
        )
    totale = query.count()
    pazienti = query.order_by(Paziente.cognome, Paziente.nome).offset(skip).limit(limit).all()
    return {
        "totale": totale,
        "skip": skip,
        "limit": limit,
        "pazienti": [_paziente_to_dict(p) for p in pazienti],
    }


@router.get("/{paziente_id}")
def dettaglio_paziente(
    paziente_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    p = db.query(Paziente).filter(Paziente.id == paziente_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Paziente non trovato")
    return _paziente_to_dict(p)


@router.post("", status_code=201)
def crea_paziente(
    body: PazienteCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    # Calcolo CF automatico se non fornito
    cf = body.codice_fiscale
    if not cf and body.data_nascita and body.sesso and body.codice_comune_nascita:
        comune = db.query(ComuneItaliano).filter(
            ComuneItaliano.codice_istat == body.codice_comune_nascita
        ).first()
        if comune:
            cf = calcola_codice_fiscale(
                body.cognome, body.nome, body.data_nascita,
                body.sesso, comune.codice_istat
            )

    p = Paziente(**body.model_dump(exclude={"codice_fiscale"}), codice_fiscale=cf)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _paziente_to_dict(p)


@router.put("/{paziente_id}")
def modifica_paziente(
    paziente_id: int,
    body: PazienteUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    p = db.query(Paziente).filter(Paziente.id == paziente_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Paziente non trovato")

    dati = body.model_dump(exclude_unset=True)

    # Ricalcola CF se cambiano i dati anagrafici
    ricalcola = any(k in dati for k in ("cognome", "nome", "data_nascita", "sesso", "codice_comune_nascita"))
    if ricalcola and "codice_fiscale" not in dati:
        cognome  = dati.get("cognome", p.cognome)
        nome     = dati.get("nome", p.nome)
        dn       = dati.get("data_nascita", p.data_nascita)
        sesso    = dati.get("sesso", p.sesso)
        cod_com  = dati.get("codice_comune_nascita", p.codice_comune_nascita)
        if dn and sesso and cod_com:
            comune = db.query(ComuneItaliano).filter(
                ComuneItaliano.codice_istat == cod_com
            ).first()
            if comune:
                dati["codice_fiscale"] = calcola_codice_fiscale(
                    cognome, nome, dn, sesso, comune.codice_istat
                )

    for k, v in dati.items():
        setattr(p, k, v)

    db.commit()
    db.refresh(p)
    return _paziente_to_dict(p)


@router.delete("/{paziente_id}", status_code=204)
def elimina_paziente(
    paziente_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    p = db.query(Paziente).filter(Paziente.id == paziente_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Paziente non trovato")
    db.delete(p)
    db.commit()


@router.get("/{paziente_id}/duplicati")
def controlla_duplicati(
    paziente_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Cerca pazienti con stesso nome/cognome escludendo l'ID corrente."""
    p = db.query(Paziente).filter(Paziente.id == paziente_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Paziente non trovato")

    simili = (
        db.query(Paziente)
        .filter(
            Paziente.id != paziente_id,
            func.lower(Paziente.cognome) == func.lower(p.cognome),
            func.lower(Paziente.nome) == func.lower(p.nome),
        )
        .all()
    )
    return [{"id": s.id, "cognome": s.cognome, "nome": s.nome,
             "data_nascita": s.data_nascita.isoformat() if s.data_nascita else None,
             "codice_fiscale": s.codice_fiscale} for s in simili]
