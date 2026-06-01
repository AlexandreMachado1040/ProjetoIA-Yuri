"""
motor_core.py — Motor de simulação FV bifacial, versão pura Python (stdlib only).
Compatível com Cloudflare Workers Python (sem numpy, sem matplotlib, sem I/O de disco).

Algoritmos: Hay 1979 (transposição), Erbs 1982 (difusa), Ray-Tracing 2D bifacial.
Simulação rápida: 12 dias representativos × 24 h → equivalente a simulação mensal.
"""

import math
import json

try:
    import urllib.request
    import urllib.error
    _HAS_URLLIB = True
except ImportError:
    _HAS_URLLIB = False

# ─────────────────────────────────────────────────────────────────────────────
# Constantes físicas e de calendário
# ─────────────────────────────────────────────────────────────────────────────

PI = math.pi
kB = 8.617333e-5          # eV/K
q  = 1.602176634e-19      # C
E_GAP = 1.121             # eV (silício)
T_REF = 298.15            # K (25 °C)

DAYS_PER_MONTH  = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTH_START_DAY = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
MONTH_NAMES     = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                   'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

# Fallback GHI climatológico São Paulo (kWh/m²/dia), calibrado NASA POWER
NASA_GHI_SP = {
    1: 6.378, 2: 6.052, 3: 5.419,  4: 4.559,  5: 3.778,  6: 3.431,
    7: 3.738, 8: 4.381, 9: 4.796, 10: 5.231, 11: 5.696, 12: 6.141,
}

# Cache em memória: {(lat_r, lon_r): {'ghi','dni','dhi','t2m'}}
_NASA_CACHE: dict = {}

_NASA_MONTH_KEYS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                    'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

# ─────────────────────────────────────────────────────────────────────────────
# 1. NASA POWER — busca e fallback
# ─────────────────────────────────────────────────────────────────────────────

def fetch_nasa_power_all(lat: float, lon: float, timeout: int = 4):
    """
    Busca GHI, DNI, DHI e T2M mensais climatológicos da NASA POWER em uma chamada.
    Usa cache em memória (_NASA_CACHE) sem I/O de disco.

    Retorna dict {'ghi':{1..12}, 'dni':{1..12}, 'dhi':{1..12}, 't2m':{1..12}}
    com valores em kWh/m²/dia (irradiância) e °C (temperatura), ou None se falhar.
    """
    if not _HAS_URLLIB:
        return None

    key = (round(lat, 2), round(lon, 2))
    if key in _NASA_CACHE:
        return _NASA_CACHE[key]

    url = (
        "https://power.larc.nasa.gov/api/temporal/climatology/point"
        f"?parameters=ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIFF,T2M"
        f"&community=RE&longitude={lon}&latitude={lat}&format=JSON"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MotorCore/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
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
        _NASA_CACHE[key] = result
        return result
    except Exception:
        return None


def build_nasa_data(lat: float, lon: float) -> dict:
    """
    Retorna dict {'ghi', 'dni', 'dhi', 't2m'} com dados mensais climatológicos.

    Prioridade 1: NASA POWER ao vivo.
    Prioridade 2: fallback offline — GHI escalado de São Paulo + Erbs estimado.
    """
    live = fetch_nasa_power_all(lat, lon)
    if live:
        return live

    # Fallback: escala GHI de SP pela diferença de latitude
    ref_lat = -23.55
    scale   = 1.0 + (abs(ref_lat) - abs(lat)) * 0.012
    ghi_m   = {m: v * scale for m, v in NASA_GHI_SP.items()}
    kd_typ  = 0.35
    return {
        'ghi': ghi_m,
        'dni': {m: max(ghi_m[m] * (1 - kd_typ) / 0.7, 0.0) for m in range(1, 13)},
        'dhi': {m: ghi_m[m] * kd_typ for m in range(1, 13)},
        't2m': {m: 22.0 for m in range(1, 13)},
    }

# ─────────────────────────────────────────────────────────────────────────────
# 2. Calendário
# ─────────────────────────────────────────────────────────────────────────────

def month_of_day(doy: int) -> int:
    """Retorna o mês (1..12) correspondente ao dia do ano (1..365)."""
    for m in range(11, -1, -1):
        if doy >= MONTH_START_DAY[m]:
            return m + 1
    return 1

# ─────────────────────────────────────────────────────────────────────────────
# 3. Posição solar
# ─────────────────────────────────────────────────────────────────────────────

def calc_solar_position(doy: int, hour_mid: float, lat: float, lon: float, tz: float):
    """
    Calcula posição solar pelo método de série de Fourier (Spencer 1971).

    Parâmetros:
        doy      : dia do ano (1..365)
        hour_mid : hora solar local (ex: 10.5 = 10h30)
        lat      : latitude em graus (negativo = Sul)
        lon      : longitude em graus (positivo = Leste)
        tz       : fuso horário em horas (ex: -3 para BRT)

    Retorna (HSun, AzSun, ENI, decl, HA):
        HSun  : elevação solar [°]
        AzSun : azimute solar [°] (0=Sul, +Leste, -Oeste)
        ENI   : irradiância extraterrestre normal [W/m²]
        decl  : declinação solar [°]
        HA    : ângulo horário [°]
    """
    B     = (doy - 1) * 2 * PI / 365
    # Equação do tempo [min]
    ET    = 229.18 * (
        0.000075
        + 0.001868 * math.cos(B)   - 0.032077 * math.sin(B)
        - 0.014615 * math.cos(2*B) - 0.040890 * math.sin(2*B)
    )
    # Declinação solar [°]
    decl  = math.degrees(
        0.006918
        - 0.399912 * math.cos(B)   + 0.070257 * math.sin(B)
        - 0.006758 * math.cos(2*B) + 0.000907 * math.sin(2*B)
        - 0.002697 * math.cos(3*B) + 0.001480 * math.sin(3*B)
    )
    # Hora solar verdadeira
    hs    = hour_mid + (ET + 4 * (lon - tz * 15)) / 60
    HA    = 15 * (hs - 12)   # ângulo horário [°]

    lr = math.radians(lat)
    dr = math.radians(decl)
    Hr = math.radians(HA)

    sin_h = (math.sin(lr) * math.sin(dr)
             + math.cos(lr) * math.cos(dr) * math.cos(Hr))
    HSun  = math.degrees(math.asin(max(min(sin_h, 1.0), -1.0)))

    AzSun = 0.0
    if HSun > 0.5:
        ca = max(min(
            (math.sin(dr) * math.cos(lr) - math.cos(dr) * math.sin(lr) * math.cos(Hr))
            / math.cos(math.radians(HSun)),
            1.0), -1.0)
        AzSun = math.degrees(math.acos(ca)) * (-1 if HA > 0 else 1)

    ENI = 1361 * (1 + 0.033 * math.cos(2 * PI * doy / 365))
    return HSun, AzSun, ENI, decl, HA

# ─────────────────────────────────────────────────────────────────────────────
# 4. Decomposição Erbs (1982)
# ─────────────────────────────────────────────────────────────────────────────

def calc_daily_kd(doy: int, daily_GHI: float, lat: float) -> float:
    """
    Calcula a fração difusa diária (Kd = DHI/GHI) pelo modelo Erbs (1982).

    Parâmetros:
        doy       : dia do ano (1..365)
        daily_GHI : GHI diário médio [kWh/m²/dia]
        lat       : latitude [°]

    Retorna Kd ∈ [0.165, 1].
    """
    B    = (doy - 1) * 2 * PI / 365
    decl = math.degrees(
        0.006918
        - 0.399912 * math.cos(B)   + 0.070257 * math.sin(B)
        - 0.006758 * math.cos(2*B) + 0.000907 * math.sin(2*B)
        - 0.002697 * math.cos(3*B) + 0.001480 * math.sin(3*B)
    )
    lr  = math.radians(lat)
    dr  = math.radians(decl)
    chs = max(min(-math.tan(lr) * math.tan(dr), 1.0), -1.0)
    HS0 = math.acos(chs)
    E0  = 1 + 0.033 * math.cos(2 * PI * doy / 365)
    # Irradiância extraterrestre diária [kWh/m²/dia]
    H0  = (24 * 1361 * E0 / PI
           * (math.sin(lr) * math.sin(dr) * HS0
              + math.cos(lr) * math.cos(dr) * math.sin(HS0))) / 1000.0
    KT  = max(min(daily_GHI / H0, 1.0), 0.0) if H0 > 0 else 0.5

    if KT < 0.22:
        return 1 - 0.09 * KT
    if KT <= 0.80:
        return (0.9511 - 0.1604*KT + 4.388*KT**2
                - 16.638*KT**3 + 12.336*KT**4)
    return 0.165

# ─────────────────────────────────────────────────────────────────────────────
# 5. Distribuição horária (CPR) + decomposição Erbs
# ─────────────────────────────────────────────────────────────────────────────

def calc_ghi_hourly(doy: int, hour: int, daily_GHI: float,
                    Kd: float, lat: float, lon: float, tz: float):
    """
    Distribui o GHI diário em valores horários usando o modelo CPR
    e decompõe em DNI/DHI pelo modelo Erbs.

    Parâmetros:
        doy       : dia do ano
        hour      : hora inteira local (0..23)
        daily_GHI : GHI diário [kWh/m²/dia]
        Kd        : fração difusa diária (de calc_daily_kd)
        lat, lon  : coordenadas [°]
        tz        : fuso horário [h]

    Retorna (GHI, DNI, DHI, HSun, AzSun, ENI) com irradiâncias em W/m².
    """
    HSun, AzSun, ENI, decl, HA = calc_solar_position(doy, hour + 0.5, lat, lon, tz)
    if HSun <= 2:
        return 0.0, 0.0, 0.0, HSun, AzSun, ENI

    lr   = math.radians(lat)
    dr   = math.radians(decl)
    chs  = max(min(-math.tan(lr) * math.tan(dr), 1.0), -1.0)
    HS0d = math.degrees(math.acos(chs))
    if HS0d < 0.5:
        return 0.0, 0.0, 0.0, HSun, AzSun, ENI

    w    = math.radians(HA)
    w0   = math.radians(HS0d)
    a    = 0.4090 + 0.5016 * math.sin(w0 - PI / 3)
    b    = 0.6609 - 0.4767 * math.sin(w0 - PI / 3)
    den  = math.sin(w0) - w0 * math.cos(w0)
    rt   = (max((PI / 24) * (a + b * math.cos(w))
                * (math.cos(w) - math.cos(w0)) / den, 0.0)
            if den > 0 else 0.0)

    GHI  = rt * daily_GHI * 1000.0          # W/m²
    DHI  = Kd * GHI
    sin_h = math.sin(math.radians(HSun))
    DNI  = (GHI - DHI) / sin_h if sin_h > 0.05 else 0.0
    return GHI, DNI, DHI, HSun, AzSun, ENI

# ─────────────────────────────────────────────────────────────────────────────
# 6. Transposição frontal — modelo Hay (1979)
# ─────────────────────────────────────────────────────────────────────────────

def calc_ft_frontal(HSun: float, AzSun: float,
                    GHI: float, DNI: float, DHI: float, ENI: float,
                    albedo: float, tilt_deg: float, az_panel_deg: float):
    """
    Calcula a irradiância no plano inclinado frontal pelo modelo Hay (1979).

    Retorna (Gt, FT):
        Gt : irradiância total no plano [W/m²]
        FT : fator de transposição Gt/GHI (adimensional)
    """
    if HSun <= 0.5 or GHI <= 0:
        return 0.0, 0.0
    h   = math.radians(HSun)
    t   = math.radians(tilt_deg)
    ar  = math.radians(AzSun - az_panel_deg)
    cos_ia = (math.cos(ar) * math.cos(h) * math.sin(t)
              + math.sin(h) * math.cos(t))
    Rb      = max(cos_ia / math.sin(h), 0.0)
    fAni    = min(DNI / ENI, 1.0) if ENI > 0 else 0.0
    Gt      = max(
        DNI * Rb
        + DHI * (fAni * Rb + (1 - fAni) * (1 + math.cos(t)) / 2)
        + GHI * albedo * (1 - math.cos(t)) / 2,
        0.0,
    )
    return Gt, Gt / GHI

# ─────────────────────────────────────────────────────────────────────────────
# 7. Interseção raio-segmento (auxiliar do ray-tracing)
# ─────────────────────────────────────────────────────────────────────────────

def _ray_seg_intersect(ox: float, oy: float, dx: float, dy: float,
                       x1: float, y1: float, x2: float, y2: float):
    """
    Calcula o parâmetro t de interseção do raio (ox,oy)+t*(dx,dy) com o
    segmento (x1,y1)-(x2,y2).

    Retorna t > 0 se houver interseção, ou None caso contrário.
    """
    d = dx * (y2 - y1) - dy * (x2 - x1)
    if abs(d) < 1e-12:
        return None
    t = ((x1 - ox) * (y2 - y1) - (y1 - oy) * (x2 - x1)) / d
    if t <= 1e-9:
        return None
    s = ((x1 - ox) * dy - (y1 - oy) * dx) / d
    return t if -1e-9 <= s <= 1 + 1e-9 else None

# ─────────────────────────────────────────────────────────────────────────────
# 8. Ray-Tracing 2D bifacial
# ─────────────────────────────────────────────────────────────────────────────

def calc_rear_raytracing(HSun: float, AzSun: float,
                         GHI: float, DNI: float, DHI: float,
                         tilt_deg: float, L: float, pitch: float,
                         albedo_ground: float,
                         N_seg: int = 5, N_rays: int = 36,
                         max_bounces: int = 2) -> float:
    """
    Calcula a irradiância na face traseira do módulo por Ray-Tracing 2D.

    O modelo opera no plano 2D perpendicular ao eixo longitudinal do módulo
    (projeção no plano vertical). Cada segmento da face traseira lança N_rays
    raios em semi-espaço coseno-ponderado; cada raio sofre até max_bounces
    reflexões no solo antes de atingir o céu ou outro módulo.

    Parâmetros:
        HSun          : elevação solar [°]
        AzSun         : azimute solar [°]
        GHI, DNI, DHI : irradiâncias [W/m²]
        tilt_deg      : inclinação do módulo [°]
        L             : comprimento do módulo (altura no plano inclinado) [m]
        pitch         : distância entre fileiras [m]
        albedo_ground : albedo do solo (0..1)
        N_seg         : número de segmentos na face traseira (resolução)
        N_rays        : número de raios por segmento
        max_bounces   : reflexões máximas permitidas

    Retorna G_rear [W/m²].
    """
    if HSun <= 2 or GHI <= 0:
        return 0.0

    T_r      = math.radians(tilt_deg)
    cT       = math.cos(T_r)
    sT       = math.sin(T_r)
    x1       = L * cT          # projeção horizontal do módulo
    y1       = L * sT          # altura do topo do módulo
    rn_angle = math.atan2(-cT, sT)   # normal da face traseira

    H_r   = math.radians(HSun)
    sun_x = -math.cos(H_r)
    sun_y =  math.sin(H_r)

    G_rear_acc = 0.0

    for seg in range(N_seg):
        s  = (seg + 0.5) / N_seg
        px = s * x1
        py = s * y1

        seg_G = 0.0
        seg_w = 0.0

        for ray_i in range(N_rays):
            theta     = (ray_i + 0.5) / N_rays * PI - PI / 2
            ray_angle = rn_angle + theta
            rdx = math.cos(ray_angle)
            rdy = math.sin(ray_angle)
            lam_w = math.cos(theta)   # peso lambertiano

            cx, cy    = px, py
            cdx, cdy  = rdx, rdy
            contribution = 0.0
            att          = 1.0

            for bounce in range(max_bounces + 1):
                t_min = float('inf')
                hit   = 'sky'

                # Interseção com o solo (y = 0)
                if cdy < -1e-12:
                    t_g = -cy / cdy
                    if t_g > 1e-9 and t_g < t_min:
                        t_min = t_g
                        xh    = (cx + t_g * cdx) % pitch
                        hit   = ('ground_unshaded'
                                 if x1 <= xh <= pitch
                                 else 'ground_shaded')

                # Interseção com módulos vizinhos (períodos -2, -1, +1, +2)
                for period in (-2, -1, 1, 2):
                    ox_mod = period * pitch
                    t_mod  = _ray_seg_intersect(
                        cx, cy, cdx, cdy,
                        ox_mod, 0.0, ox_mod + x1, y1,
                    )
                    if t_mod is not None and t_mod < t_min:
                        t_min = t_mod
                        hit   = 'module'

                # Resolução do hit
                if hit == 'sky' or t_min == float('inf'):
                    if cdy > 0:
                        cos_sun = cdx * sun_x + cdy * sun_y
                        if cos_sun > 0.9999 and HSun > 2:
                            contribution += att * DNI
                        else:
                            contribution += att * DHI / PI
                    break
                elif hit == 'module':
                    break   # módulo opaco — absorve
                else:       # ground_unshaded ou ground_shaded
                    g_irr = GHI if hit == 'ground_unshaded' else DHI
                    contribution += att * albedo_ground * g_irr * 0.5
                    if bounce < max_bounces and att * albedo_ground > 0.01:
                        cx  += t_min * cdx
                        cy   = 1e-6
                        cdy  = abs(cdy)
                        att *= albedo_ground * 0.5
                    else:
                        break

            seg_G += contribution * lam_w
            seg_w += lam_w

        if seg_w > 0:
            G_rear_acc += seg_G / seg_w

    return max(G_rear_acc / N_seg, 0.0) if N_seg > 0 else 0.0

# ─────────────────────────────────────────────────────────────────────────────
# 9. Eficiência do inversor (interpolação por curva ou paramétrica)
# ─────────────────────────────────────────────────────────────────────────────

def calc_eta_inv_generico(P_array_kW: float, inv: dict) -> float:
    """
    Calcula a eficiência do inversor em função da potência DC entregue.

    Se inv['profil_curves'] não for vazio, interpola na curva V2 (Pin_W → Pout_W).
    Caso contrário, usa interpolação paramétrica normalizada pelo eta_max.

    Parâmetros:
        P_array_kW : potência DC [kW]
        inv        : dict do inversor (campos 'profil_curves', 'eta_max', 'P_nomAC')

    Retorna η ∈ [0, 1].
    """
    if P_array_kW <= 0.01:
        return 0.0

    curves = inv.get('profil_curves', {})
    if curves:
        P_in_W = P_array_kW * 1000.0
        key    = 'V2' if 'V2' in curves else next(iter(curves))
        pts    = curves[key]   # [(Pin_W, Pout_W), ...]

        if P_in_W < pts[0][0]:
            return 0.0
        if P_in_W >= pts[-1][0]:
            pin, pout = pts[-1]
            return pout / pin if pin > 0 else 0.0
        for i in range(len(pts) - 1):
            if pts[i][0] <= P_in_W <= pts[i + 1][0]:
                alpha = (P_in_W - pts[i][0]) / (pts[i + 1][0] - pts[i][0])
                p_out = pts[i][1] + alpha * (pts[i + 1][1] - pts[i][1])
                return p_out / P_in_W
        return inv.get('eta_max', 99.0) / 100.0

    # Fallback: curva normalizada (forma CSI-250K, escalada pelo eta_max)
    eta_max  = inv.get('eta_max', 99.0) / 100.0
    P_nom_DC = (inv['P_nomAC'] / eta_max) if eta_max > 0 else inv['P_nomAC']
    P_ratio  = min(P_array_kW / P_nom_DC, 1.0) if P_nom_DC > 0 else 1.0
    pts_P    = [0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00]
    pts_e    = [0.940, 0.970, 0.983, 0.988, 0.990, 0.9901, 0.9895, 0.988]
    scale    = eta_max / 0.9901
    p        = min(max(P_ratio, 0.02), 1.0)
    for i in range(len(pts_P) - 1):
        if pts_P[i] <= p <= pts_P[i + 1]:
            a = (p - pts_P[i]) / (pts_P[i + 1] - pts_P[i])
            return min((pts_e[i] + a * (pts_e[i + 1] - pts_e[i])) * scale, 0.9999)
    return min(pts_e[-1] * scale, 0.9999)

# ─────────────────────────────────────────────────────────────────────────────
# 10. Simulação rápida mensal (12 dias representativos × 24 h)
# ─────────────────────────────────────────────────────────────────────────────

def simulate_fast(params: dict) -> dict:
    """
    Simulação mensal rápida usando um dia representativo por mês (±14 dias do
    início do mês) e integrando 24 horas para cada dia.

    Em vez de 365 dias completos, executa apenas 12 iterações de dia × 24 h,
    escalonando o resultado pelo número de dias do mês — cerca de 30× mais
    rápido que a integração anual completa, mantendo boa precisão climatológica.

    Parâmetros de entrada (dict `params`):
    ─────────────────────────────────────
    lat          float   Latitude [°] (negativo = Sul)
    lon          float   Longitude [°] (positivo = Leste)
    tz           float   Fuso horário UTC (ex: -3 para BRT)
    tilt         float   Inclinação do módulo [°]
    az           float   Azimute do painel [°] (0 = Norte/Sul, 180 = Norte no HS)
    N_s          int     Número de módulos em série por string
    N_strings    int     Número de strings em paralelo
    bifacial     bool    Ativa ray-tracing traseiro
    albedo       float   Albedo do solo (0..1)
    pitch        float   Distância entre fileiras [m]
    mod_height   float   Comprimento do módulo (dimensão no plano inclinado) [m]
    N_seg        int     Segmentos de ray-tracing (padrão 5)
    N_rays       int     Raios por segmento (padrão 36)
    modulo       dict    Parâmetros do módulo (veja CATALOGO_MODULOS)
    inversor     dict    Parâmetros do inversor (veja CATALOGO_INVERSORES)

    Retorna dict com:
    ─────────────────
    E_grid_anual_kWh  float   Energia anual entregue à rede [kWh]
    PR_pct            float   Performance Ratio [%]
    GHI_anual         float   GHI total no plano horizontal [kWh/m²/ano]
    FT_frontal        float   Fator de transposição frontal médio
    FT_bifacial       float   Fator de transposição bifacial médio
    ganho_bif_pct     float   Ganho bifacial em relação ao frontal [%]
    P_nom_stc_kWp     float   Potência nominal STC do array [kWp]
    P_nom_AC_kW       float   Potência nominal AC do inversor [kW]
    monthly_GHI       list    GHI mensal [kWh/m²/mês] (12 valores)
    monthly_E_grid    list    Energia mensal na rede [kWh/mês] (12 valores)
    modulo_nome       str     Nome/modelo do módulo
    inversor_nome     str     Nome/modelo do inversor
    """
    # ── Extração de parâmetros ────────────────────────────────────────────────
    lat       = float(params['lat'])
    lon       = float(params['lon'])
    tz        = float(params.get('tz', -3))
    tilt      = float(params.get('tilt', 20))
    az_panel  = float(params.get('az', 0))
    N_s       = int(params.get('N_s', 28))
    N_strings = int(params.get('N_strings', 1))
    bifacial  = bool(params.get('bifacial', True))
    albedo    = float(params.get('albedo', 0.25))
    pitch     = float(params.get('pitch', 10.0))
    mod_h     = float(params.get('mod_height', 2.384))
    N_seg     = int(params.get('N_seg', 5))
    N_rays    = int(params.get('N_rays', 36))

    mod = params['modulo']
    inv = params['inversor']

    Pmpp      = float(mod['Pmpp'])             # W por módulo
    mu_Pmpp   = float(mod['mu_Pmpp'])          # %/°C
    phi       = float(mod.get('phi', 0.0))     # bifacialidade

    P_nom_stc = N_s * N_strings * Pmpp / 1000.0   # kWp
    P_nom_AC  = float(inv['P_nomAC'])              # kW
    eta_max   = float(inv.get('eta_max', 99.0))
    P_nom_DC  = P_nom_AC / (eta_max / 100.0)       # kW (limite DC)

    # Fator de perdas DC simplificado (mismatch + ôhmica + LID + soiling frontal)
    f_DC = 0.9320   # ≈ 1 − 0.0615 − 0.0073 − 0.0174 + 0.0033 − 0.0081 − 0.0196

    # ── Dados climatológicos NASA POWER ───────────────────────────────────────
    nasa_override = params.get('nasa_data')
    if nasa_override:
        nasa = nasa_override
        nasa_source = 'NASA POWER (ao vivo)'
    else:
        live = fetch_nasa_power_all(lat, lon)
        if live:
            nasa = live
            nasa_source = 'NASA POWER'
        else:
            nasa = build_nasa_data(lat, lon)
            nasa_source = 'Fallback climatológico'
    NASA_GHI = nasa['ghi']
    NASA_T2M = nasa['t2m']

    # ── Acumuladores ──────────────────────────────────────────────────────────
    monthly_GHI    = [0.0] * 12
    monthly_Gf     = [0.0] * 12
    monthly_E_grid = [0.0] * 12
    monthly_E_arr  = [0.0] * 12
    acc_Gf         = 0.0
    acc_Gb         = 0.0
    acc_GHI        = 0.0
    acc_E_grid     = 0.0

    for m in range(1, 13):
        mi  = m - 1
        # Dia representativo: ~meio do mês
        doy = MONTH_START_DAY[mi] + 14
        doy = min(doy, 365)

        dly_GHI = NASA_GHI.get(m, 5.0)    # kWh/m²/dia
        T_amb   = NASA_T2M.get(m, 22.0)    # °C
        Kd      = calc_daily_kd(doy, dly_GHI, lat)
        n_days  = DAYS_PER_MONTH[mi]

        day_GHI    = 0.0
        day_E_grid = 0.0
        day_E_arr  = 0.0
        day_Gf     = 0.0
        day_Gb     = 0.0

        for hour in range(24):
            GHI, DNI, DHI, HSun, AzSun, ENI = calc_ghi_hourly(
                doy, hour, dly_GHI, Kd, lat, lon, tz
            )
            if GHI < 1.0 or HSun <= 2:
                continue

            # Transposição frontal (Hay 1979)
            Gf, _ = calc_ft_frontal(
                HSun, AzSun, GHI, DNI, DHI, ENI,
                albedo, tilt, az_panel,
            )

            # Face traseira (Ray-Tracing 2D) — apenas se bifacial ativo
            if bifacial and phi > 0:
                Gr = calc_rear_raytracing(
                    HSun, AzSun, GHI, DNI, DHI,
                    tilt, mod_h, pitch, albedo,
                    N_seg, N_rays,
                )
                Gb = Gf + phi * Gr
            else:
                Gr = 0.0
                Gb = Gf

            # Modelo térmico PVSyst simplificado:
            # T_cell = T_amb + G_front × α×(1−η_m)/Uc
            T_cell = T_amb + Gf * 0.9 * (1 - 0.235) / 29.0

            # Potência MPP do array [kW]
            G_norm    = Gb / 1000.0
            P_mpp     = (G_norm * P_nom_stc
                         * (1 + mu_Pmpp / 100.0 * (T_cell - 25.0))
                         * f_DC)
            P_mpp     = max(P_mpp, 0.0)

            # Limitação DC → AC
            P_array   = min(P_mpp, P_nom_DC)
            eta_inv   = calc_eta_inv_generico(P_array, inv)
            E_grid_h  = P_array * eta_inv   # kWh (hora completa)

            day_GHI    += GHI
            day_Gf     += Gf
            day_Gb     += Gb
            day_E_arr  += P_mpp      # kW × 1h = kWh (DC antes do inversor)
            day_E_grid += E_grid_h

        monthly_GHI[mi]    = (day_GHI / 1000.0) * n_days
        monthly_Gf[mi]     = (day_Gf  / 1000.0) * n_days
        monthly_E_arr[mi]  = day_E_arr  * n_days
        monthly_E_grid[mi] = day_E_grid * n_days

        acc_GHI    += monthly_GHI[mi]
        acc_E_grid += monthly_E_grid[mi]
        acc_Gf     += monthly_Gf[mi]
        acc_Gb     += (day_Gb / 1000.0) * n_days

    # ── Performance Ratio ─────────────────────────────────────────────────────
    # PR = Yf / Yr_ref  onde Yr_ref = G_tilt_frontal / 1  (horas de pico)
    Yf       = acc_E_grid / P_nom_stc if P_nom_stc > 0 else 0.0
    Yr       = acc_Gf if acc_Gf > 0 else 1.0
    PR_pct   = (Yf / Yr * 100.0) if Yr > 0 else 0.0

    # ── Fatores de transposição ───────────────────────────────────────────────
    FT_frontal  = acc_Gf  / acc_GHI if acc_GHI > 0 else 0.0
    FT_bifacial = acc_Gb  / acc_GHI if acc_GHI > 0 else 0.0
    ganho_bif   = ((FT_bifacial / FT_frontal - 1) * 100.0
                   if FT_frontal > 0 else 0.0)

    return {
        'E_grid_anual_kWh': round(acc_E_grid, 1),
        'PR_pct':           round(PR_pct, 1),
        'GHI_anual':        round(acc_GHI, 1),
        'FT_frontal':       round(FT_frontal, 4),
        'FT_bifacial':      round(FT_bifacial, 4),
        'ganho_bif_pct':    round(ganho_bif, 2),
        'P_nom_stc_kWp':    round(P_nom_stc, 3),
        'P_nom_AC_kW':      round(P_nom_AC, 1),
        'monthly_GHI':      [round(v, 2) for v in monthly_GHI],
        'monthly_Gf':       [round(v, 2) for v in monthly_Gf],
        'monthly_E_arr':    [round(v, 1) for v in monthly_E_arr],
        'monthly_E_grid':   [round(v, 1) for v in monthly_E_grid],
        'modulo_nome':      mod.get('modelo', ''),
        'inversor_nome':    inv.get('modelo', ''),
        'nasa_source':      nasa_source,
    }

# ─────────────────────────────────────────────────────────────────────────────
# 11. Catálogo de módulos (parâmetros derivados dos arquivos .PAN)
# ─────────────────────────────────────────────────────────────────────────────

CATALOGO_MODULOS = {
    'CS7N-720TB-AG': dict(
        modelo='CS7N-720TB-AG',
        fabricante='CSI Solar Co., Ltd.',
        tecnologia='Mono-Si bifacial',
        Pmpp=720.0, Vmpp=40.80, Voc=48.70,
        Impp=17.670, Isc=18.690,
        mu_Pmpp=-0.290, mu_Voc=-0.2448, mu_Isc=0.0499,
        NOCT=41.0, phi=0.80, N_cs=132,
        eta=23.2, A_mod=3.106732,
        gamma=1.043, I0_ref=1.937e-5, Iph_ref=18.703,
        Rs=0.135, Rsh=200.0,
    ),
    'CS7N-730TB-AG': dict(
        modelo='CS7N-730TB-AG',
        fabricante='CSI Solar Co., Ltd.',
        tecnologia='Mono-Si bifacial',
        Pmpp=730.0, Vmpp=41.20, Voc=49.10,
        Impp=17.750, Isc=18.790,
        mu_Pmpp=-0.290, mu_Voc=-0.2428, mu_Isc=0.0496,
        NOCT=41.0, phi=0.80, N_cs=132,
        eta=23.5, A_mod=3.106732,
        gamma=1.051, I0_ref=1.985e-5, Iph_ref=18.803,
        Rs=0.135, Rsh=210.0,
    ),
    'CS7N-700TB-AG': dict(
        modelo='CS7N-700TB-AG',
        fabricante='CSI Solar Co., Ltd.',
        tecnologia='Mono-Si bifacial',
        Pmpp=700.0, Vmpp=40.00, Voc=47.90,
        Impp=17.510, Isc=18.490,
        mu_Pmpp=-0.290, mu_Voc=-0.2498, mu_Isc=0.0499,
        NOCT=41.0, phi=0.80, N_cs=132,
        eta=22.5, A_mod=3.106732,
        gamma=1.066, I0_ref=1.80e-5, Iph_ref=18.503,
        Rs=0.136, Rsh=200.0,
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# 12. Catálogo de inversores (parâmetros derivados dos arquivos .OND)
# ─────────────────────────────────────────────────────────────────────────────

CATALOGO_INVERSORES = {
    'CSI-250K-T8001A-E': dict(
        modelo='CSI-250K-T8001A-E',
        fabricante='CSI Solar Co., Ltd.',
        P_nomAC=250.0, P_maxAC=250.0,
        eta_max=99.0, eta_euro=98.8,
        V_dc_max=1500, V_mpp_min=500, V_mpp_max=1500, V_nom=1090,
        N_mppt=12, N_str_max=24,
        profil_curves={
            'V2': [
                (1250,      0),
                (12500,  12126.3),
                (25000,  24592.5),
                (50000,  49420.0),
                (62500,  61825.0),
                (75000,  74227.5),
                (125000, 123762.5),
                (187500, 185531.2),
                (250000, 247150.0),
            ],
        },
    ),
    'SUN2000-215KTL-H3': dict(
        modelo='SUN2000-215KTL-H3',
        fabricante='Huawei Technologies',
        P_nomAC=200.0, P_maxAC=215.0,
        eta_max=99.03, eta_euro=98.78,
        V_dc_max=1500, V_mpp_min=500, V_mpp_max=1500, V_nom=1080,
        N_mppt=3, N_str_max=14,
        profil_curves={
            'V2': [
                (180,        0),
                (20431.1,  20000.0),
                (50556.1,  50000.0),
                (111077.5, 110000.0),
                (151837.2, 150000.0),
                (202695.9, 200000.0),
            ],
        },
    ),
    'CSI-50K-T4001A-E': dict(
        modelo='CSI-50K-T4001A-E',
        fabricante='CSI Solar Co., Ltd.',
        P_nomAC=50.0, P_maxAC=55.0,
        eta_max=98.43, eta_euro=98.14,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=600,
        N_mppt=4, N_str_max=8,
        profil_curves={
            'V2': [
                (198,      0),
                (2500,   2335.3),
                (5000,   4806.0),
                (10000,  9735.0),
                (12500, 12190.0),
                (15000, 14649.0),
                (25000, 24457.5),
                (37500, 36641.2),
                (50000, 48745.0),
            ],
        },
    ),
}
