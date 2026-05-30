"""Modelos Pydantic para validação de entrada/saída da API."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class SimulacaoInput(BaseModel):
    # Localização
    lat: float = Field(..., ge=-90, le=90, description="Latitude (graus decimais)")
    lon: float = Field(..., ge=-180, le=180, description="Longitude (graus decimais)")
    tz: int = Field(-3, ge=-12, le=14, description="Fuso horário UTC offset")

    # Equipamentos
    modulo_nome: str = Field(..., description="Nome do arquivo .PAN (sem extensão)")
    inversor_nome: str = Field(..., description="Nome do arquivo .OND (sem extensão)")

    # Arranjo
    Ns: int = Field(..., ge=1, description="Módulos em série por string")
    Np: int = Field(..., ge=1, description="Strings em paralelo")
    n_inversores: int = Field(1, ge=1, description="Número de inversores")

    # Geometria
    tilt: float = Field(..., ge=0, le=90, description="Inclinação dos módulos (°)")
    azimuth: float = Field(0.0, ge=-180, le=180, description="Azimute (0=Sul, -90=Leste)")
    modo: Literal["BIFACIAL", "MONOFACIAL"] = "BIFACIAL"

    # Bifacial (apenas se modo=BIFACIAL)
    pitch: float = Field(10.0, gt=0, description="Espaçamento entre fileiras (m)")
    h_hub: float = Field(1.5, gt=0, description="Altura do centro do módulo (m)")
    mod_width: float = Field(2.382, gt=0, description="Largura do módulo (m)")
    albedo: float = Field(0.25, ge=0, le=1, description="Albedo do solo")

    # Fonte de dados climáticos
    modo_dados: Literal["climatologia", "horario"] = "climatologia"
    ano_dados: Optional[int] = Field(None, ge=2001, le=2023,
                                      description="Ano para modo horário")


class JobStatus(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    progress: int = Field(0, ge=0, le=100, description="Progresso estimado (%)")
    message: str = ""
    resultado: Optional[dict] = None
    pdf_url: Optional[str] = None


class ModuloInfo(BaseModel):
    nome: str
    fabricante: str
    modelo: str
    pmpp: float
    tecnologia: str


class InversorInfo(BaseModel):
    nome: str
    fabricante: str
    modelo: str
    p_nom: float
    eta_max: float
