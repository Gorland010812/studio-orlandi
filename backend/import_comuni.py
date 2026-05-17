"""
Script di importazione comuni italiani nel database.
Sorgente: matteocontrini/comuni-json (GitHub) — ~7900 comuni con codice belfiore.
Eseguire dopo init_db.py.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import urllib.request
from database import engine, SessionLocal
from models import Base, ComuneItaliano
from sqlalchemy import text

SOURCE_URL = "https://raw.githubusercontent.com/matteocontrini/comuni-json/master/comuni.json"
BATCH_SIZE = 500


def scarica_comuni() -> list:
    print(f"Download comuni da {SOURCE_URL} ...")
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        print(f"Scaricati {len(data)} comuni.")
        return data
    except Exception as e:
        print(f"Errore download: {e}")
        sys.exit(1)


def converti(record: dict) -> dict:
    cap_raw = record.get("cap", [])
    cap = cap_raw[0] if cap_raw else None

    return {
        "nome": record["nome"],
        "provincia": record.get("provincia", {}).get("nome", ""),
        "sigla_provincia": record.get("sigla", ""),
        "codice_istat": record.get("codiceCatastale", ""),
        "cap": cap,
        "regione": record.get("regione", {}).get("nome", ""),
    }


def import_comuni(force: bool = False):
    db = SessionLocal()
    try:
        count = db.query(ComuneItaliano).count()
        if count > 0 and not force:
            print(f"Comuni già presenti nel database ({count} record). Usa --force per reimportare.")
            return

        if force and count > 0:
            print("Cancellazione comuni esistenti...")
            db.execute(text("DELETE FROM comuni_italiani"))
            db.execute(text("DELETE FROM sqlite_sequence WHERE name='comuni_italiani'"))
            db.commit()

        raw = scarica_comuni()

        print("Creazione indici...")
        Base.metadata.create_all(bind=engine)

        print(f"Importazione {len(raw)} comuni in batch da {BATCH_SIZE}...")
        totale = 0
        batch = []

        for record in raw:
            try:
                batch.append(ComuneItaliano(**converti(record)))
            except Exception:
                continue  # salta record malformati

            if len(batch) >= BATCH_SIZE:
                db.bulk_save_objects(batch)
                db.commit()
                totale += len(batch)
                batch = []
                print(f"  Importati {totale}/{len(raw)}...", end="\r")

        if batch:
            db.bulk_save_objects(batch)
            db.commit()
            totale += len(batch)

        # Indici per ricerca veloce
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_comuni_nome ON comuni_italiani(nome COLLATE NOCASE)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_comuni_sigla ON comuni_italiani(sigla_provincia)"))
        db.commit()

        print(f"\nImportazione completata: {totale} comuni nel database.")

    except Exception as e:
        db.rollback()
        print(f"\nErrore durante l'importazione: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    import_comuni(force=force)
