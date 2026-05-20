from sqlalchemy import Column, Integer, Text, Boolean, Date, DateTime as Timestamp, ForeignKey, CheckConstraint, Numeric
from sqlalchemy.sql import func
from database import Base


class Impostazioni(Base):
    __tablename__ = "impostazioni"

    id = Column(Integer, primary_key=True)
    nome_medico = Column(Text, nullable=False, default="Dott. Goffredo Orlandi")
    specializzazioni = Column(Text, default="— Diagnostica — Idoneità")
    servizi = Column(Text, default="— Elettrocardiogramma\n— Eco Cuore\n— Holter Cardiaco")
    testo_home = Column(Text, default="Calendario Appuntamenti: Cardio e idoneità")
    username = Column(Text, nullable=False, default="orlandi")
    password_hash = Column(Text, nullable=False)
    created_at = Column(Timestamp, server_default=func.now())
    updated_at = Column(Timestamp, server_default=func.now(), onupdate=func.now())


class Sede(Base):
    __tablename__ = "sedi"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(Text, nullable=False)
    indirizzo = Column(Text)
    citta = Column(Text)
    provincia = Column(Text)
    cap = Column(Text)
    telefono = Column(Text)
    email = Column(Text)
    ordine = Column(Integer, default=0)
    attiva = Column(Boolean, default=True)


class Paziente(Base):
    __tablename__ = "pazienti"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cognome = Column(Text, nullable=False)
    nome = Column(Text, nullable=False)
    data_nascita = Column(Date)
    luogo_nascita = Column(Text)
    provincia_nascita = Column(Text)
    codice_comune_nascita = Column(Text)
    codice_fiscale = Column(Text)
    sesso = Column(Text)
    indirizzo = Column(Text)
    cap = Column(Text)
    citta_residenza = Column(Text)
    provincia_residenza = Column(Text)
    telefono = Column(Text)
    email = Column(Text)
    professione = Column(Text)
    medico_base = Column(Text)
    titolo_studio = Column(Text)
    stato_civile = Column(Text)
    inviato_da = Column(Text)
    note = Column(Text)
    created_at = Column(Timestamp, server_default=func.now())
    updated_at = Column(Timestamp, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("sesso IN ('M', 'F')", name="ck_pazienti_sesso"),
    )


class TipoVisita(Base):
    __tablename__ = "tipi_visita"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(Text, nullable=False)
    durata_minuti = Column(Integer, default=30)
    colore = Column(Text, default="#0F6E56")
    attivo = Column(Boolean, default=True)
    ordine = Column(Integer, default=0)
    costo = Column(Numeric(10, 2), nullable=True)
    note = Column(Text, nullable=True)


class Disponibilita(Base):
    __tablename__ = "disponibilita"

    id = Column(Integer, primary_key=True, autoincrement=True)
    giorno_settimana = Column(Integer, nullable=False)  # 0=Lunedì, 6=Domenica
    ora_inizio_mattina = Column(Text, default="08:30")
    ora_fine_mattina = Column(Text, default="13:00")
    ora_inizio_pomeriggio = Column(Text, default="15:30")
    ora_fine_pomeriggio = Column(Text, default="19:00")
    attivo = Column(Boolean, default=True)


class Appuntamento(Base):
    __tablename__ = "appuntamenti"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paziente_id = Column(Integer, ForeignKey("pazienti.id"))
    tipo_visita_id = Column(Integer, ForeignKey("tipi_visita.id"))
    sede_id = Column(Integer, ForeignKey("sedi.id"))
    data_ora = Column(Timestamp, nullable=False)
    durata_minuti = Column(Integer, default=30)
    stato = Column(Text, default="confermato")
    note = Column(Text)
    nome_paziente = Column(Text)
    cognome_paziente = Column(Text)
    telefono_paziente = Column(Text)
    email_paziente = Column(Text)
    created_at = Column(Timestamp, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "stato IN ('confermato', 'annullato', 'completato', 'in_attesa')",
            name="ck_appuntamenti_stato"
        ),
    )


class ComuneItaliano(Base):
    __tablename__ = "comuni_italiani"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(Text, nullable=False)
    provincia = Column(Text, nullable=False)
    sigla_provincia = Column(Text, nullable=False)
    codice_istat = Column(Text, nullable=False)
    cap = Column(Text)
    regione = Column(Text)
