"""
Motor PVSyst API — Cloudflare Worker (Python)
POST /simulate → JSON com resultados da simulação FV bifacial
GET  /         → documentação da API
GET  /catalogo → lista de módulos e inversores disponíveis
"""

from js import Response, Headers, URL, fetch as js_fetch
import json
from motor_core import simulate_fast, calc_ft_curve, build_nasa_data, CATALOGO_MODULOS, CATALOGO_INVERSORES

_CORS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

_DEFAULTS = dict(
    lat=-23.55, lon=-46.63, tz=-3,
    tilt=20.8, az=0.0,
    N_s=28, N_strings=3,
    bifacial=True,
    albedo=0.30, pitch=2.826, mod_height=2.0,
    N_seg=5, N_rays=12, perda_cabo_cc_pct=1.5, perda_sujidade_pct=2.0,
    tipo_montagem="livre",
    modulo="CS7N-730TB-AG",
    inversor="CSI-250K-T8001A-E",
)

_NASA_MONTH_KEYS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                    'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

_DOCS = {
    "name": "Motor PVSyst API",
    "version": "1.1",
    "description": "Simulação FV bifacial — Hay+Erbs+Ray-Tracing 2D. Dados climáticos: NASA POWER.",
    "endpoints": {
        "POST /simulate": {"body": _DEFAULTS},
        "GET /catalogo":  "Lista módulos e inversores disponíveis",
        "GET /":          "Esta documentação",
    },
}


def _json_response(data, status=200):
    hdrs = Headers.new({**_CORS, "Content-Type": "application/json"}.items())
    return Response.new(json.dumps(data, ensure_ascii=False), status=status, headers=hdrs)


def _error(msg, status=400):
    return _json_response({"error": msg}, status=status)


async def _fetch_nasa(lat: float, lon: float):
    """Busca dados climatológicos da NASA POWER via js.fetch (Workers-compatible)."""
    url = (
        "https://power.larc.nasa.gov/api/temporal/climatology/point"
        f"?parameters=ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIFF,T2M"
        f"&community=RE&longitude={lon}&latitude={lat}&format=JSON"
    )
    resp = await js_fetch(url)
    if not resp.ok:
        raise Exception(f"NASA HTTP {resp.status}")
    text = await resp.text()
    data = json.loads(text)
    param = data["properties"]["parameter"]
    result = {}
    for nome, nasa_key in [
        ('ghi', 'ALLSKY_SFC_SW_DWN'),
        ('dni', 'ALLSKY_SFC_SW_DNI'),
        ('dhi', 'ALLSKY_SFC_SW_DIFF'),
        ('t2m', 'T2M'),
    ]:
        raw = param[nasa_key]
        result[nome] = {i + 1: float(raw[k]) for i, k in enumerate(_NASA_MONTH_KEYS)}
    return result


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

    # GET /nasa-test — diagnóstico do fetch NASA
    if method == "GET" and path == "/nasa-test":
        try:
            data = await _fetch_nasa(-23.55, -46.63)
            return _json_response({"ok": True, "meses": list(data.get("ghi", {}).values())[:3]})
        except Exception as e:
            return _json_response({"ok": False, "error": str(e), "tipo": type(e).__name__})

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
            raw_text = await request.text()
            body = json.loads(raw_text)
        except Exception:
            return _error("Body JSON inválido")

        try:
            p = {**_DEFAULTS, **{k: v for k, v in body.items() if v is not None}}

            # Resolve módulo
            mod_key = p.get("modulo", "CS7N-730TB-AG")
            if isinstance(mod_key, str):
                mod = CATALOGO_MODULOS.get(mod_key)
                if mod is None:
                    return _error(f"Módulo '{mod_key}' não encontrado. Disponíveis: {list(CATALOGO_MODULOS)}")
            else:
                mod = mod_key

            # Resolve inversor
            inv_key = p.get("inversor", "CSI-250K-T8001A-E")
            if isinstance(inv_key, str):
                inv = CATALOGO_INVERSORES.get(inv_key)
                if inv is None:
                    return _error(f"Inversor '{inv_key}' não encontrado. Disponíveis: {list(CATALOGO_INVERSORES)}")
            else:
                inv = inv_key

            lat = float(p["lat"])
            lon = float(p["lon"])

            # Busca NASA POWER via js.fetch (async, nativo do Workers)
            _nasa_err = None
            try:
                nasa_data = await _fetch_nasa(lat, lon)
            except Exception as e:
                nasa_data = None
                _nasa_err = f"{type(e).__name__}: {e}"

            params = {
                "lat":        lat,
                "lon":        lon,
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
                "N_rays":     min(int(p.get("N_rays", 12)), 90),
                "perda_cabo_cc_pct": max(0.0, min(float(p.get("perda_cabo_cc_pct", 1.5)), 10.0)),
                "perda_sujidade_pct": max(0.0, min(float(p.get("perda_sujidade_pct", 2.0)), 25.0)),
                "perda_sujidade_mensal": p.get("perda_sujidade_mensal"),
                "tipo_montagem": str(p.get("tipo_montagem", "livre")),
                "vento_ms":   float(p.get("vento_ms", 1.0)),
                "modulo":     mod,
                "inversor":   inv,
                "nasa_data":  nasa_data,   # None → simulate_fast usa fallback SP
            }

            result = simulate_fast(params)
            if _nasa_err:
                result['nasa_debug'] = _nasa_err
        except Exception as exc:
            return _error(f"Erro na simulação: {type(exc).__name__}: {exc}", status=500)

        return _json_response(result)

    # GET /ft-curve
    if method == "GET" and path == "/ft-curve":
        try:
            from urllib.parse import parse_qs, urlparse as _urlparse
            qs  = parse_qs(_urlparse(request.url).query)
            def _qp(k, d): return float(qs.get(k, [str(d)])[0])
            lat  = _qp('lat',  -23.55)
            lon  = _qp('lon',  -46.63)
            tz   = _qp('tz',   -3)
            tilt = _qp('tilt', 20.8)
            az   = _qp('az',   0.0)
            try:
                nasa_data = await _fetch_nasa(lat, lon)
            except Exception:
                nasa_data = build_nasa_data(lat, lon)
            result = calc_ft_curve(lat, lon, tz, tilt, az, nasa_data)
            return _json_response(result)
        except Exception as exc:
            return _error(f"Erro ft-curve: {type(exc).__name__}: {exc}", status=500)

    return _error("Endpoint não encontrado", status=404)


async def on_scheduled(event, env, ctx=None):
    """Cron keep-warm: toca o catálogo em memória para manter o isolate aquecido
    e reduzir o cold start do Python Worker entre simulações."""
    _ = len(CATALOGO_MODULOS) + len(CATALOGO_INVERSORES)
    return None
