"""Rotas de simulação: submissão e consulta de status."""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

import parsers_pvsyst as pp
from backend.schemas import SimulacaoInput, JobStatus
from backend import job_store
from backend.services import motor_service

router = APIRouter()

MODULOS_DIR    = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                               "Arquivos", "PVmodules")
INVERSORES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                               "Arquivos", "Inverters")
PDF_DIR        = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                               "relatorios")


@router.post("/simulate", response_model=JobStatus, status_code=202)
def submeter_simulacao(body: SimulacaoInput):
    """Inicia uma simulação em background e retorna job_id."""
    # Valida equipamentos
    pan_path = os.path.join(MODULOS_DIR, body.modulo_nome + ".PAN")
    ond_path = os.path.join(INVERSORES_DIR, body.inversor_nome + ".OND")
    if not os.path.exists(pan_path):
        raise HTTPException(404, f"Módulo '{body.modulo_nome}' não encontrado")
    if not os.path.exists(ond_path):
        raise HTTPException(404, f"Inversor '{body.inversor_nome}' não encontrado")

    # Monta dict de inputs no formato esperado pelo motor
    mod  = pp.parse_pan(pan_path)
    inv  = pp.parse_ond(ond_path)

    inp = {
        # Localização
        "lat":  body.lat,
        "lon":  body.lon,
        "tz":   body.tz,
        # Equipamentos (dicts completos do parser + nomes)
        "modulo":  mod,
        "modulo_nome": body.modulo_nome,
        "inversor": inv,
        "inversor_nome": body.inversor_nome,
        # Arranjo
        "Ns": body.Ns,
        "Np": body.Np,
        "n_inversores": body.n_inversores,
        # Geometria
        "tilt":    body.tilt,
        "azimuth": body.azimuth,
        "modo":    body.modo,
        # Bifacial
        "pitch":     body.pitch,
        "h_hub":     body.h_hub,
        "mod_width": body.mod_width,
        "albedo":    body.albedo,
        # Dados climáticos
        "modo_dados": body.modo_dados,
        "ano_dados":  body.ano_dados,
    }

    job_id = job_store.create_job()
    motor_service.iniciar_simulacao(job_id, inp)
    return job_store.get_job(job_id)


@router.get("/simulate/{job_id}", response_model=JobStatus)
def consultar_job(job_id: str):
    """Retorna status e resultado (quando pronto) de uma simulação."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")
    return job


@router.get("/relatorios/{filename}")
def baixar_relatorio(filename: str):
    """Faz download do PDF gerado."""
    # Segurança: apenas nome de arquivo, sem path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Nome de arquivo inválido")
    path = os.path.join(PDF_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Relatório não encontrado")
    return FileResponse(path, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/jobs")
def listar_jobs():
    """Lista todos os jobs da sessão atual."""
    return job_store.list_jobs()
