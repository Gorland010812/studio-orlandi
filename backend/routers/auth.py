from datetime import datetime, timedelta
from typing import Optional
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from database import get_db
from models import Impostazioni

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "cambia-questa-chiave-segreta-in-produzione")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

DEFAULT_PASSWORD = "orlandi2024"


# ── Schemi Pydantic ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    password_corrente: str
    nuova_password: str
    conferma_password: str

class SetupRequest(BaseModel):
    username: str
    password: str


# ── Utilità JWT ───────────────────────────────────────────────────────────────

def crea_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verifica_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# ── Dependency: utente corrente ───────────────────────────────────────────────

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Impostazioni:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token mancante")

    username = verifica_token(credentials.credentials)
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token non valido o scaduto")

    impostazioni = db.query(Impostazioni).first()
    if impostazioni is None or impostazioni.username != username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente non trovato")

    return impostazioni


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/needs-setup")
def needs_setup(db: Session = Depends(get_db)):
    """Controlla se il sistema è ancora configurato con le credenziali default."""
    impostazioni = db.query(Impostazioni).first()
    if impostazioni is None:
        return {"needs_setup": True}
    is_default = pwd_context.verify(DEFAULT_PASSWORD, impostazioni.password_hash)
    return {"needs_setup": is_default}


@router.post("/setup")
def setup_iniziale(body: SetupRequest, db: Session = Depends(get_db)):
    """Setup credenziali al primo accesso (solo se password è ancora quella default)."""
    impostazioni = db.query(Impostazioni).first()
    if impostazioni is None:
        raise HTTPException(status_code=404, detail="Impostazioni non trovate — eseguire init_db.py")

    if not pwd_context.verify(DEFAULT_PASSWORD, impostazioni.password_hash):
        raise HTTPException(status_code=403, detail="Setup già completato")

    if len(body.username.strip()) < 3:
        raise HTTPException(status_code=422, detail="Username deve avere almeno 3 caratteri")
    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="Password deve avere almeno 6 caratteri")

    impostazioni.username = body.username.strip().lower()
    impostazioni.password_hash = pwd_context.hash(body.password)
    db.commit()

    token = crea_token({"sub": impostazioni.username})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    impostazioni = db.query(Impostazioni).first()
    if impostazioni is None:
        raise HTTPException(status_code=500, detail="Sistema non inizializzato")

    if body.username.strip().lower() != impostazioni.username.lower():
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    if not pwd_context.verify(body.password, impostazioni.password_hash):
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    token = crea_token({"sub": impostazioni.username})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    current_user: Impostazioni = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not pwd_context.verify(body.password_corrente, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Password corrente non valida")

    if body.nuova_password != body.conferma_password:
        raise HTTPException(status_code=422, detail="Le password non coincidono")

    if len(body.nuova_password) < 6:
        raise HTTPException(status_code=422, detail="La nuova password deve avere almeno 6 caratteri")

    current_user.password_hash = pwd_context.hash(body.nuova_password)
    db.commit()
    return {"message": "Password aggiornata con successo"}


@router.get("/me")
def me(current_user: Impostazioni = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "nome_medico": current_user.nome_medico,
    }
