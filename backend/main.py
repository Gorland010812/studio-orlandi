import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith('/assets/'):
            response.headers['Cache-Control'] = 'public, max-age=86400'
        elif not path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-cache'
        return response


from routers.auth import router as auth_router
from routers.pazienti import router as pazienti_router
from routers.appuntamenti import router as appuntamenti_router
from routers.impostazioni import (
    router_impostazioni,
    router_sedi,
    router_tipi_visita,
    router_disponibilita,
)
from routers.prenotazioni import router as prenotazioni_router, router_comuni

# ── Percorsi ──────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# In Docker: frontend/ è copiato dentro /app/frontend/
# In sviluppo locale: frontend/ è ../frontend/ rispetto a backend/
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
if not os.path.isdir(FRONTEND_DIR):
    FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
FRONTEND_DIR = os.path.abspath(FRONTEND_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.isdir(DATA_DIR):
    DATA_DIR = os.path.join(BASE_DIR, "..", "data")
DATA_DIR = os.path.abspath(DATA_DIR)
os.makedirs(DATA_DIR, exist_ok=True)


# ── Lifespan (startup) ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from init_db import migrate_db, init_db
    migrate_db()
    init_db()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Studio Orlandi",
    description="Gestione studio medico – Dott. Goffredo Orlandi",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
# La sicurezza dell'area medico è garantita dal JWT token.
# Il portale pazienti deve essere raggiungibile dall'esterno.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CacheControlMiddleware)


# ── Error handlers ────────────────────────────────────────────────────────────

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = exc.errors()
    messages = [f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in errors]
    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(messages)},
    )


# ── API Routers ───────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(pazienti_router)
app.include_router(appuntamenti_router)
app.include_router(router_impostazioni)
app.include_router(router_sedi)
app.include_router(router_tipi_visita)
app.include_router(router_disponibilita)
app.include_router(prenotazioni_router)
app.include_router(router_comuni)


# ── Static Files ──────────────────────────────────────────────────────────────

if os.path.isdir(FRONTEND_DIR):
    assets_dir = os.path.join(FRONTEND_DIR, "assets")
    medico_dir = os.path.join(FRONTEND_DIR, "medico")
    paziente_dir = os.path.join(FRONTEND_DIR, "paziente")

    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    if os.path.isdir(medico_dir):
        app.mount("/medico", StaticFiles(directory=medico_dir, html=True), name="medico")

    if os.path.isdir(paziente_dir):
        app.mount("/paziente", StaticFiles(directory=paziente_dir, html=True), name="paziente")

    @app.get("/", include_in_schema=False)
    def root():
        index = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return JSONResponse({"status": "Studio Orlandi API attiva", "docs": "/api/docs"})

else:
    @app.get("/", include_in_schema=False)
    def root_no_frontend():
        return JSONResponse({
            "status": "Studio Orlandi API attiva",
            "nota": "Frontend non trovato — avviare dal progetto root",
            "docs": "/api/docs",
        })


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/api/health", include_in_schema=False)
def health():
    return {"status": "ok", "service": "Studio Orlandi"}
