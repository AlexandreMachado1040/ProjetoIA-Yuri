"""
Motor PVSyst API — Cloudflare Worker (Python)
POST /simulate → JSON com resultados da simulação FV bifacial
GET  /         → documentação da API
GET  /catalogo → lista de módulos e inversores disponíveis
"""

from js import Response, Headers, URL
import json
from motor_core import simulate_fast, CATALOGO_MODULOS, CATALOGO_INVERSORES

_CORS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

_DEFAULTS = dict(
    lat=-23.55, lon=-46.63, tz=-3,
    tilt=20.8, az=180.0,
    N_s=28, N_strings=3,
    bifacial=True,
    albedo=0.30, pitch=2.826, mod_height=2.0,
    N_seg=5, N_rays=36,
    modulo="CS7N-730TB-AG",
    inversor="CSI-250K-T8001A-E",
)

_DOCS = {
    "name": "Motor PVSyst API",
    "version": "1.0",
    "description": "Simulação FV bifacial — Hay+Erbs+Ray-Tracing 2D. Dados climáticos: NASA POWER.",
    "endpoints": {
        "POST /simulate": {
            "body": _DEFAULTS,
            "response": {
                "E_grid_anual_kWh": "Energia anual injetada na rede [kWh]",
                "PR_pct": "Performance Ratio [%]",
                "GHI_anual": "Irradiância horizontal global anual [kWh/m²]",
                "FT_frontal": "Fator de transposição frontal",
                "FT_bifacial": "Fator de transposição bifacial (inclui G_rear)",
                "ganho_bif_pct": "Ganho bifacial [%]",
                "P_nom_stc_kWp": "Potência nominal do array [kWp]",
                "P_nom_AC_kW": "Potência nominal do inversor [kW]",
                "monthly_GHI": "GHI mensal [kWh/m²] (lista 12 meses)",
                "monthly_E_grid": "Energia mensal na rede [kWh] (lista 12 meses)",
                "modulo_nome": "Modelo do módulo usado",
                "inversor_nome": "Modelo do inversor usado",
            },
        },
        "GET /catalogo": "Lista módulos e inversores disponíveis",
        "GET /": "Esta documentação",
    },
}


def _json_response(data, status=200):
    hdrs = Headers.new({**_CORS, "Content-Type": "application/json; charset=utf-8"}.items())
    return Response.new(json.dumps(data, ensure_ascii=False), status=status, headers=hdrs)


def _error(msg, status=400):
    return _json_response({"error": msg}, status=status)


async def on_fetch(request, env):
    url = URL.new(request.url)
    path = url.pathname.rstrip("/") or "/"
    method = request.method.upper()

    # CORS preflight
    if method == "OPTIONS":
        hdrs = Headers.new(_CORS.items())
        return Response.new("", status=204, headers=hdrs)

    # GET /
    if method == "GET" and path == "/":
        return _json_response(_DOCS)

    # GET /catalogo
    if method == "GET" and path == "/catalogo":
        catalogo = {
            "modulos": [
                {"nome": k, "Pmpp_Wp": v["Pmpp"], "fabricante": v["fabricante"],
                 "phi": v["phi"], "eta_pct": v["eta"]}
                for k, v in CATALOGO_MODULOS.items()
            ],
            "inversores": [
                {"nome": k, "P_nomAC_kW": v["P_nomAC"], "fabricante": v["fabricante"],
                 "eta_max_pct": v["eta_max"], "N_mppt": v["N_mppt"]}
                for k, v in CATALOGO_INVERSORES.items()
            ],
        }
        return _json_response(catalogo)

    # POST /simulate
    if method == "POST" and path in ("/simulate", "/"):
        try:
            body = await request.json()
        except Exception:
            return _error("Body JSON inválido")

        # Mescla defaults com os parâmetros recebidos
        p = {**_DEFAULTS, **{k: v for k, v in body.items() if v is not None}}

        # Resolve módulo
        mod_key = p.get("modulo", "CS7N-730TB-AG")
        if isinstance(mod_key, str):
            mod = CATALOGO_MODULOS.get(mod_key)
            if mod is None:
                return _error(f"Módulo '{mod_key}' não encontrado. Disponíveis: {list(CATALOGO_MODULOS)}")
        else:
            mod = mod_key  # aceita dict completo

        # Resolve inversor
        inv_key = p.get("inversor", "CSI-250K-T8001A-E")
        if isinstance(inv_key, str):
            inv = CATALOGO_INVERSORES.get(inv_key)
            if inv is None:
                return _error(f"Inversor '{inv_key}' não encontrado. Disponíveis: {list(CATALOGO_INVERSORES)}")
        else:
            inv = inv_key

        params = {
            "lat":        float(p["lat"]),
            "lon":        float(p["lon"]),
            "tz":         int(p["tz"]),
            "tilt":       float(p["tilt"]),
            "az":         float(p["az"]),
            "N_s":        int(p["N_s"]),
            "N_strings":  int(p["N_strings"]),
            "bifacial":   bool(p["bifacial"]),
            "albedo":     float(p["albedo"]),
            "pitch":      float(p["pitch"]),
            "mod_height": float(p["mod_height"]),
            "N_seg":      min(int(p.get("N_seg", 5)),  15),
            "N_rays":     min(int(p.get("N_rays", 36)), 90),
            "modulo":     mod,
            "inversor":   inv,
        }

        try:
            result = simulate_fast(params)
        except Exception as exc:
            return _error(f"Erro na simulação: {exc}", status=500)

        return _json_response(result)

    return _error("Endpoint não encontrado", status=404)
