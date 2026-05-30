"""Backend FastAPI — Motor PVSyst Unificado v2.3"""
import os, sys

# Garante que o diretório pai (raiz do projeto) esteja no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routers import equipamentos, simulacao

app = FastAPI(
    title="Motor PVSyst API",
    version="2.3.0",
    description="API REST para simulação fotovoltaica bifacial",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(equipamentos.router, prefix="/api", tags=["Equipamentos"])
app.include_router(simulacao.router, prefix="/api", tags=["Simulação"])


@app.get("/api/health", tags=["Sistema"])
def health():
    return {"status": "ok", "motor": "v2.3"}
