# Studio Orlandi — Gestione Studio Medico

Applicazione web per la gestione dello studio del Dott. Goffredo Orlandi.  
Stack: FastAPI · SQLite · HTML/CSS/JS vanilla · Docker.

---

## Struttura del progetto

```
studio-orlandi/
├── backend/
│   ├── main.py            # Entry point FastAPI
│   ├── database.py        # Connessione SQLite
│   ├── models.py          # Modelli ORM
│   ├── init_db.py         # Inizializzazione DB e dati default
│   ├── import_comuni.py   # Import comuni italiani ISTAT
│   ├── requirements.txt
│   └── routers/
│       ├── auth.py        # Login / JWT
│       ├── pazienti.py    # CRUD pazienti + calcolo CF
│       ├── appuntamenti.py# CRUD appuntamenti + slot liberi
│       ├── impostazioni.py# Impostazioni, sedi, tipi visita, disponibilità
│       └── prenotazioni.py# Portale pubblico + comuni italiani
├── frontend/
│   ├── index.html         # Pagina iniziale (scelta medico/paziente)
│   ├── assets/            # style.css, app.js
│   ├── medico/            # login, home, anagrafica, calendario, impostazioni
│   └── paziente/          # prenota.html (wizard 4 step)
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── data/                  # Database SQLite (escluso da git)
```

---

## Accesso

| Area | URL | Protezione |
|------|-----|------------|
| Pagina iniziale | `/` | Pubblica |
| Area medico | `/medico/login.html` | JWT — accesso via Tailscale |
| Portale pazienti | `/paziente/prenota.html` | Pubblica |
| Swagger UI | `/api/docs` | — |

**Credenziali default (da cambiare al primo accesso):**
- Username: `orlandi`
- Password: `orlandi2024`

Al primo accesso il sistema mostra automaticamente il wizard di configurazione per impostare username e password definitivi.

---

## Sviluppo locale

```bash
# 1. Crea virtualenv e installa dipendenze
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# 2. Importa comuni italiani (una volta sola — richiede internet)
cd backend
python import_comuni.py

# 3. Avvia il server
uvicorn main:app --reload --port 8080
```

Apri: http://localhost:8080

> Il database viene creato e inizializzato automaticamente al primo avvio in `data/studio_orlandi.db`.

---

## Deploy su NAS Ugreen 2800

### 1. Trasferire i file sul NAS

Da questa Mac, con il NAS raggiungibile in rete locale:

```bash
rsync -av \
  --exclude='.venv' \
  --exclude='data/*.db' \
  --exclude='__pycache__' \
  /Users/francorlandi/studio-orlandi/ \
  nas-user@NAS-IP:/volume1/docker/studio-orlandi/
```

In alternativa: copiare la cartella via condivisione SMB del NAS.

### 2. Verificare la SECRET_KEY

La chiave JWT è già configurata in `docker/docker-compose.yml`.  
Per rigenerarla in qualsiasi momento:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Sostituire il valore in `docker/docker-compose.yml`:

```yaml
environment:
  - SECRET_KEY=<nuova-chiave-generata>
```

### 3. Build e avvio del container

Accedere al NAS via SSH, poi:

```bash
cd /volume1/docker/studio-orlandi/docker
docker compose up -d --build
```

### 4. Import comuni italiani (solo al primo avvio)

```bash
docker compose exec studio-orlandi python import_comuni.py
```

Scarica e importa ~7900 comuni con codici belfiore ISTAT.  
Necessario per il calcolo automatico del Codice Fiscale.

### 5. Verifica

```bash
# Stato container
docker compose ps

# Log di avvio
docker compose logs --tail=40

# Health check
curl http://localhost:8080/api/health
```

Risposta attesa: `{"status":"ok","service":"Studio Orlandi"}`

---

## Persistenza dati

Il database SQLite è salvato fuori dal container e sopravvive ai riavvii:

```
NAS filesystem:  /volume1/docker/studio-orlandi/data/studio_orlandi.db
                 ↕ volume mount
Container:       /app/data/studio_orlandi.db
```

**Backup:** è sufficiente copiare il file `data/studio_orlandi.db`.

---

## Aggiornamento applicazione

```bash
cd /volume1/docker/studio-orlandi/docker

# Ferma il container
docker compose down

# (Trasferisci i nuovi file via rsync)

# Rebuild e riavvio
docker compose up -d --build
```

> I dati nel volume `../data` non vengono toccati dal rebuild.

---

## Configurazione rete NAS

| Accesso | Metodo | Porta |
|---------|--------|-------|
| Medico (esterno) | Tailscale VPN | 8080 (privata) |
| Portale pazienti (esterno) | Port forwarding router | 8080 → pubblica |
| Rete locale | IP NAS diretto | 8080 |

> Il portale prenotazioni è pubblico per design. L'area medico è protetta da JWT e accessibile dall'esterno solo via Tailscale.
