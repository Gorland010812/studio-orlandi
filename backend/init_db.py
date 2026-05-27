"""
Script di inizializzazione del database.
Crea le tabelle e inserisce i dati predefiniti.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import engine, SessionLocal
from models import Base, Impostazioni, TipoVisita, Disponibilita, Sede, FotoSito
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TIPI_VISITA_DEFAULT = [
    {"nome": "Visita Cardiologica",      "durata_minuti": 30, "colore": "#0F6E56", "ordine": 1},
    {"nome": "Elettrocardiogramma",      "durata_minuti": 20, "colore": "#1A6A8A", "ordine": 2},
    {"nome": "Eco Cuore",               "durata_minuti": 45, "colore": "#2980B9", "ordine": 3},
    {"nome": "Holter Cardiaco",         "durata_minuti": 15, "colore": "#8E44AD", "ordine": 4},
    {"nome": "Idoneità Sportiva Base",  "durata_minuti": 30, "colore": "#F5C842", "ordine": 5},
    {"nome": "Idoneità Agonistica",     "durata_minuti": 45, "colore": "#E67E22", "ordine": 6},
    {"nome": "Visita di Controllo",     "durata_minuti": 20, "colore": "#27AE60", "ordine": 7},
]

# Disponibilità lun-ven (0=Lunedì … 4=Venerdì)
DISPONIBILITA_DEFAULT = [
    {"giorno_settimana": 0, "ora_inizio_mattina": "08:30", "ora_fine_mattina": "13:00",
     "ora_inizio_pomeriggio": "15:30", "ora_fine_pomeriggio": "19:00", "attivo": True},
    {"giorno_settimana": 1, "ora_inizio_mattina": "08:30", "ora_fine_mattina": "13:00",
     "ora_inizio_pomeriggio": "15:30", "ora_fine_pomeriggio": "19:00", "attivo": True},
    {"giorno_settimana": 2, "ora_inizio_mattina": "08:30", "ora_fine_mattina": "13:00",
     "ora_inizio_pomeriggio": "15:30", "ora_fine_pomeriggio": "19:00", "attivo": True},
    {"giorno_settimana": 3, "ora_inizio_mattina": "08:30", "ora_fine_mattina": "13:00",
     "ora_inizio_pomeriggio": "15:30", "ora_fine_pomeriggio": "19:00", "attivo": True},
    {"giorno_settimana": 4, "ora_inizio_mattina": "08:30", "ora_fine_mattina": "13:00",
     "ora_inizio_pomeriggio": "15:30", "ora_fine_pomeriggio": "19:00", "attivo": True},
    {"giorno_settimana": 5, "ora_inizio_mattina": "08:30", "ora_fine_mattina": "13:00",
     "ora_inizio_pomeriggio": "15:30", "ora_fine_pomeriggio": "19:00", "attivo": False},
    {"giorno_settimana": 6, "ora_inizio_mattina": "08:30", "ora_fine_mattina": "13:00",
     "ora_inizio_pomeriggio": "15:30", "ora_fine_pomeriggio": "19:00", "attivo": False},
]

SEDE_DEFAULT = {
    "nome": "Studio Orlandi – Pistoia",
    "indirizzo": "",
    "citta": "Pistoia",
    "provincia": "Toscana",
    "cap": "51100",
    "telefono": "",
    "email": "",
    "ordine": 1,
    "attiva": True,
}


def migrate_db():
    """Aggiunge colonne mancanti a tabelle esistenti (idempotente)."""
    from sqlalchemy import text
    with engine.connect() as conn:
        tv_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(tipi_visita)"))}
        if "costo" not in tv_cols:
            conn.execute(text("ALTER TABLE tipi_visita ADD COLUMN costo REAL"))
            print("Migrazione: aggiunta colonna tipi_visita.costo")
        if "note" not in tv_cols:
            conn.execute(text("ALTER TABLE tipi_visita ADD COLUMN note TEXT"))
            print("Migrazione: aggiunta colonna tipi_visita.note")

        imp_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(impostazioni)"))}
        for col in ["bio_testo", "piva", "google_reviews_link", "numero_telefono"]:
            if col not in imp_cols:
                conn.execute(text(f"ALTER TABLE impostazioni ADD COLUMN {col} TEXT"))
                print(f"Migrazione: aggiunta colonna impostazioni.{col}")

        conn.commit()


def init_db():
    print("Creazione tabelle...")
    Base.metadata.create_all(bind=engine)
    print("Tabelle create.")

    db = SessionLocal()
    try:
        # Impostazioni: inserisci solo se non esiste
        if db.query(Impostazioni).count() == 0:
            password_default = "orlandi2024"
            impostazioni = Impostazioni(
                nome_medico="Dott. Goffredo Orlandi",
                specializzazioni="— Diagnostica — Idoneità",
                servizi="— Elettrocardiogramma\n— Eco Cuore\n— Holter Cardiaco",
                testo_home="Calendario Appuntamenti: Cardio e idoneità",
                username="orlandi",
                password_hash=pwd_context.hash(password_default),
            )
            db.add(impostazioni)
            print(f"Impostazioni inserite (password default: {password_default})")

        # Tipi visita
        if db.query(TipoVisita).count() == 0:
            for tv in TIPI_VISITA_DEFAULT:
                db.add(TipoVisita(**tv))
            print(f"Inseriti {len(TIPI_VISITA_DEFAULT)} tipi visita.")

        # Disponibilità
        if db.query(Disponibilita).count() == 0:
            for d in DISPONIBILITA_DEFAULT:
                db.add(Disponibilita(**d))
            print("Inserita disponibilità lun-ven.")

        # Sede predefinita
        if db.query(Sede).count() == 0:
            db.add(Sede(**SEDE_DEFAULT))
            print("Inserita sede predefinita.")

        db.commit()
        print("Inizializzazione completata.")

    except Exception as e:
        db.rollback()
        print(f"Errore: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_db()
    init_db()
