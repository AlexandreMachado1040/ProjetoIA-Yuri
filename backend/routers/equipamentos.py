"""Rotas para listagem de módulos e inversores disponíveis."""
import os
from fastapi import APIRouter, HTTPException
import parsers_pvsyst as pp

router = APIRouter()

MODULOS_DIR   = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                              "Arquivos", "PVmodules")
INVERSORES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                               "Arquivos", "Inverters")


def _pan_nome(nome: str) -> str:
    """Retorna o nome do arquivo sem extensão."""
    return os.path.splitext(os.path.basename(nome))[0]


def _pan_path(nome: str) -> str:
    base = nome if nome.endswith(".PAN") else nome + ".PAN"
    return os.path.join(MODULOS_DIR, base)


def _ond_path(nome: str) -> str:
    base = nome if nome.endswith(".OND") else nome + ".OND"
    return os.path.join(INVERSORES_DIR, base)


@router.get("/modulos")
def listar_modulos():
    """Retorna lista de módulos .PAN disponíveis.
    listar_modulos() retorna [(filepath, modelo, Pmpp, phi), ...]
    """
    tuplas = pp.listar_modulos(MODULOS_DIR)
    resultado = []
    for fp, modelo, pmpp, phi in tuplas:
        nome = os.path.splitext(os.path.basename(fp))[0]
        resultado.append({
            "nome": nome,
            "modelo": modelo,
            "pmpp": pmpp,
            "bifacialidade": phi,
        })
    return resultado


@router.get("/modulos/{nome}")
def detalhar_modulo(nome: str):
    """Retorna parâmetros completos de um módulo .PAN."""
    path = _pan_path(nome)
    if not os.path.exists(path):
        raise HTTPException(404, f"Módulo '{nome}' não encontrado")
    return pp.parse_pan(path)


@router.get("/inversores")
def listar_inversores():
    """Retorna lista de inversores .OND disponíveis.
    listar_inversores() retorna [(filepath, modelo, PNom_kW, eta_max, NbMPPT), ...]
    """
    tuplas = pp.listar_inversores(INVERSORES_DIR)
    resultado = []
    for fp, modelo, pnom, eta_max, nb_mppt in tuplas:
        nome = os.path.splitext(os.path.basename(fp))[0]
        resultado.append({
            "nome": nome,
            "modelo": modelo,
            "p_nom": pnom,
            "eta_max": eta_max,
            "nb_mppt": nb_mppt,
        })
    return resultado


@router.get("/inversores/{nome}")
def detalhar_inversor(nome: str):
    """Retorna parâmetros completos de um inversor .OND."""
    path = _ond_path(nome)
    if not os.path.exists(path):
        raise HTTPException(404, f"Inversor '{nome}' não encontrado")
    return pp.parse_ond(path)
