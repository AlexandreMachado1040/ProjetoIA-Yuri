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
    Ib_H    = max(GHI - DHI, 0.0)   # irradiância direta na horizontal (Hay 1979)
    Gt      = max(
        Ib_H * Rb
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
    acc_E_arr      = 0.0
    acc_E_stc      = 0.0   # energia teórica STC (Gb, sem perdas T nem DC)
    acc_E_arr_noT  = 0.0   # energia DC sem perda de temperatura (só f_DC)

    # Histograma: bins de 100 W/m² em Gf (0-100, 100-200, ..., 900-1000, >1000)
    N_BINS = 11
    hist_arr_acc   = [0.0] * N_BINS
    hist_grid_acc  = [0.0] * N_BINS

    N_PWR_BINS        = 20
    pwr_bin_kw        = P_nom_stc / N_PWR_BINS if P_nom_stc > 0 else 1.0
    hist_pwr_arr_acc  = [0.0] * (N_PWR_BINS + 1)
    hist_pwr_grid_acc = [0.0] * (N_PWR_BINS + 1)

    for m in range(1, 13):
        mi  = m - 1
        # Dia representativo: ~meio do mês
        doy = MONTH_START_DAY[mi] + 14
        doy = min(doy, 365)

        dly_GHI = NASA_GHI.get(m, 5.0)    # kWh/m²/dia
        T_amb   = NASA_T2M.get(m, 22.0)    # °C
        Kd      = calc_daily_kd(doy, dly_GHI, lat)
        n_days  = DAYS_PER_MONTH[mi]

        day_GHI       = 0.0
        day_E_grid    = 0.0
        day_E_arr     = 0.0
        day_E_stc     = 0.0
        day_E_arr_noT = 0.0
        day_Gf        = 0.0
        day_Gb        = 0.0
        day_hist_arr  = [0.0] * N_BINS
        day_hist_grid = [0.0] * N_BINS
        day_hist_pwr_arr  = [0.0] * (N_PWR_BINS + 1)
        day_hist_pwr_grid = [0.0] * (N_PWR_BINS + 1)

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
            day_E_arr  += P_mpp
            day_E_grid += E_grid_h

            # Acumuladores para diagrama de perdas
            day_E_stc     += max(G_norm * P_nom_stc, 0.0)
            day_E_arr_noT += max(G_norm * P_nom_stc * f_DC, 0.0)

            # Histograma por bin de Gf (100 W/m² por bin)
            b = min(int(Gf // 100), N_BINS - 1) if Gf > 0 else 0
            day_hist_arr[b]  += P_mpp
            day_hist_grid[b] += E_grid_h

            pb = min(int(P_mpp / pwr_bin_kw), N_PWR_BINS) if P_mpp > 0 and pwr_bin_kw > 0 else 0
            day_hist_pwr_arr[pb]  += P_mpp
            day_hist_pwr_grid[pb] += E_grid_h

        monthly_GHI[mi]    = (day_GHI / 1000.0) * n_days
        monthly_Gf[mi]     = (day_Gf  / 1000.0) * n_days
        monthly_E_arr[mi]  = day_E_arr  * n_days
        monthly_E_grid[mi] = day_E_grid * n_days

        acc_GHI        += monthly_GHI[mi]
        acc_E_grid     += monthly_E_grid[mi]
        acc_E_arr      += monthly_E_arr[mi]
        acc_Gf         += monthly_Gf[mi]
        acc_Gb         += (day_Gb / 1000.0) * n_days
        acc_E_stc      += day_E_stc      * n_days
        acc_E_arr_noT  += day_E_arr_noT  * n_days
        for b in range(N_BINS):
            hist_arr_acc[b]  += day_hist_arr[b]  * n_days
            hist_grid_acc[b] += day_hist_grid[b] * n_days
        for pb in range(N_PWR_BINS + 1):
            hist_pwr_arr_acc[pb]  += day_hist_pwr_arr[pb]  * n_days
            hist_pwr_grid_acc[pb] += day_hist_pwr_grid[pb] * n_days

    # ── Fatores de transposição ───────────────────────────────────────────────
    FT_frontal  = acc_Gf  / acc_GHI if acc_GHI > 0 else 0.0
    FT_bifacial = acc_Gb  / acc_GHI if acc_GHI > 0 else 0.0
    ganho_bif   = ((FT_bifacial / FT_frontal - 1) * 100.0
                   if FT_frontal > 0 else 0.0)

    # ── Performance Ratio ─────────────────────────────────────────────────────
    Yf       = acc_E_grid / P_nom_stc if P_nom_stc > 0 else 0.0
    Yr       = acc_Gb if acc_Gb > 0 else 1.0
    PR_pct   = (Yf / Yr * 100.0) if Yr > 0 else 0.0

    # ── Histograma ────────────────────────────────────────────────────────────
    hist_bins = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110]

    # ── Diagrama de perdas ────────────────────────────────────────────────────
    loss_temp_pct = ((acc_E_arr_noT - acc_E_arr) / acc_E_arr_noT * 100.0
                     if acc_E_arr_noT > 0 else 0.0)
    loss_dc_pct   = (1.0 - f_DC) * 100.0
    loss_inv_pct  = ((acc_E_arr - acc_E_grid) / acc_E_arr * 100.0
                     if acc_E_arr > 0 else 0.0)

    ft_gain_pct = round((FT_frontal - 1) * 100, 2)
    loss_chain = [
        {'label': 'GHI horizontal',                       'value': round(acc_GHI, 1),           'unit': 'kWh/m²', 'tipo': 'total'},
        {'label': 'Transposição (plano inclinado)',        'value': ft_gain_pct,                 'unit': '%',       'tipo': 'ganho' if ft_gain_pct >= 0 else 'perda'},
        {'label': 'G frontal inclinado',                   'value': round(acc_Gf, 1),            'unit': 'kWh/m²', 'tipo': 'total'},
        {'label': 'Ganho bifacial',                        'value': round(ganho_bif, 2),         'unit': '%',       'tipo': 'bifacial'},
        {'label': 'G efetivo bifacial',                    'value': round(acc_Gb, 1),            'unit': 'kWh/m²', 'tipo': 'total'},
        {'label': 'E_Array STC (teórico)',                 'value': round(acc_E_stc / 1000, 1),  'unit': 'MWh',    'tipo': 'total'},
        {'label': 'Perdas temperatura',                    'value': -round(loss_temp_pct, 1),    'unit': '%',       'tipo': 'perda'},
        {'label': 'Perdas DC (mismatch+LID+ohm+soiling)', 'value': -round(loss_dc_pct, 1),      'unit': '%',       'tipo': 'perda'},
        {'label': 'E_Array DC',                            'value': round(acc_E_arr / 1000, 1),  'unit': 'MWh',    'tipo': 'total'},
        {'label': 'Perdas inversor',                       'value': -round(loss_inv_pct, 1),     'unit': '%',       'tipo': 'perda'},
        {'label': 'E_Grid (rede)',                         'value': round(acc_E_grid / 1000, 1), 'unit': 'MWh',    'tipo': 'total'},
    ]

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
        'hist_bins':        hist_bins,
        'hist_arr':         [round(v, 1) for v in hist_arr_acc],
        'hist_grid':        [round(v, 1) for v in hist_grid_acc],
        'loss_chain':       loss_chain,
        'modulo_nome':      mod.get('modelo', ''),
        'inversor_nome':    inv.get('modelo', ''),
        'nasa_source':      nasa_source,
        'N_s':              N_s,
        'N_strings':        N_strings,
        'hist_power_bins':  [round(i * pwr_bin_kw, 2) for i in range(N_PWR_BINS + 2)],
        'hist_power_arr':   [round(v / 1000, 3) for v in hist_pwr_arr_acc],
        'hist_power_grid':  [round(v / 1000, 3) for v in hist_pwr_grid_acc],
        'P_nom_DC_kW':      round(P_nom_DC, 2),
        'R_DC_AC':          round(P_nom_stc / P_nom_AC, 3) if P_nom_AC > 0 else 0,
        'eta_inv_max_pct':  round(eta_max, 2),
        'modulo_elec': {
            'Voc':     mod.get('Voc',     0.0),
            'Isc':     mod.get('Isc',     0.0),
            'Vmpp':    mod.get('Vmpp',    0.0),
            'Impp':    mod.get('Impp',    0.0),
            'mu_Voc':  mod.get('mu_Voc',  -0.25),
            'mu_Isc':  mod.get('mu_Isc',  0.05),
            'mu_Pmpp': mod.get('mu_Pmpp', -0.29),
            'N_cs':    mod.get('N_cs',    66),
            'gamma':   mod.get('gamma',   1.04),
            'I0_ref':  mod.get('I0_ref',  2e-11),
            'Iph_ref': mod.get('Iph_ref', 0.0),
            'Rs':      mod.get('Rs',      0.135),
            'Rsh':     mod.get('Rsh',     200.0),
            'A_mod':   mod.get('A_mod',   3.106352),
        },
        'inversor_elec': {
            'V_mpp_min': inv.get('V_mpp_min', 0),
            'V_mpp_max': inv.get('V_mpp_max', 1500),
            'V_dc_max':  inv.get('V_dc_max',  1500),
        },
        'input_params': {
            'lat': lat, 'lon': lon, 'tz': tz,
            'tilt': tilt, 'az': az_panel,
        },
    }

def calc_ft_curve(lat: float, lon: float, tz: float,
                  tilt: float, az: float, nasa_data: dict) -> dict:
    """
    Calcula o fator de transposição anual em função da inclinação e do azimute.
    Usa o mesmo método de 12 dias representativos de simulate_fast (sem ray-tracing).
    Retorna tilt_curve [[tilt, FT], ...] e az_curve [[az, FT], ...].
    """
    NASA_GHI = nasa_data['ghi']

    def _ft_annual(t, a):
        acc_Gf = acc_GHI = 0.0
        for m in range(1, 13):
            mi      = m - 1
            doy     = MONTH_START_DAY[mi] + 14
            dly_GHI = NASA_GHI.get(m, 5.0)
            Kd      = calc_daily_kd(doy, dly_GHI, lat)
            n_days  = DAYS_PER_MONTH[mi]
            day_Gf = day_GHI = 0.0
            for hour in range(24):
                GHI, DNI, DHI, HSun, AzSun, ENI = calc_ghi_hourly(
                    doy, hour, dly_GHI, Kd, lat, lon, tz)
                if GHI < 1.0:
                    continue
                Gf, _ = calc_ft_frontal(HSun, AzSun, GHI, DNI, DHI, ENI, 0.25, t, a)
                day_Gf  += Gf
                day_GHI += GHI
            acc_Gf  += day_Gf  * n_days
            acc_GHI += day_GHI * n_days
        return acc_Gf / acc_GHI if acc_GHI > 0 else 0.0

    tilts      = list(range(0, 91, 5))
    tilt_curve = [[t, round(_ft_annual(t, az), 4)]   for t in tilts]
    opt_t      = max(tilt_curve, key=lambda x: x[1])

    azs        = list(range(-90, 91, 5))
    az_curve   = [[a, round(_ft_annual(tilt, a), 4)] for a in azs]
    opt_a      = max(az_curve, key=lambda x: x[1])

    return {
        'tilt_curve':       tilt_curve,
        'az_curve':         az_curve,
        'optimal_tilt':     opt_t[0],
        'FT_optimal_tilt':  opt_t[1],
        'optimal_az':       opt_a[0],
        'FT_optimal_az':    opt_a[1],
        'FT_current':       round(_ft_annual(tilt, az), 4),
        'current_tilt':     tilt,
        'current_az':       az,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 11. Catálogo de módulos (parâmetros derivados dos arquivos .PAN)
# ─────────────────────────────────────────────────────────────────────────────

CATALOGO_MODULOS = {
    'CS7N-700TB-AG': dict(
        modelo='CS7N-700TB-AG', fabricante='CSI Solar Co., Ltd.', tecnologia='Mono-Si bifacial',
        Pmpp=700.0, Vmpp=40.00, Voc=47.90, Impp=17.510, Isc=18.490,
        mu_Pmpp=-0.290, mu_Voc=-0.2499, mu_Isc=0.0500,
        NOCT=45.0, phi=0.800, N_cs=66, eta=22.53, A_mod=3.106352,
        gamma=1.066, I0_ref=2.51e-11, Iph_ref=18.490, Rs=0.136, Rsh=200.0,
    ),
    'CS7N-705TB-AG': dict(
        modelo='CS7N-705TB-AG', fabricante='CSI Solar Co., Ltd.', tecnologia='Mono-Si bifacial',
        Pmpp=705.0, Vmpp=40.20, Voc=48.10, Impp=17.550, Isc=18.540,
        mu_Pmpp=-0.290, mu_Voc=-0.2489, mu_Isc=0.0498,
        NOCT=45.0, phi=0.800, N_cs=66, eta=22.70, A_mod=3.106352,
        gamma=1.038, I0_ref=2.51e-11, Iph_ref=18.540, Rs=0.135, Rsh=200.0,
    ),
    'CS7N-710TB-AG': dict(
        modelo='CS7N-710TB-AG', fabricante='CSI Solar Co., Ltd.', tecnologia='Mono-Si bifacial',
        Pmpp=710.0, Vmpp=40.40, Voc=48.30, Impp=17.590, Isc=18.590,
        mu_Pmpp=-0.290, mu_Voc=-0.2478, mu_Isc=0.0497,
        NOCT=45.0, phi=0.800, N_cs=66, eta=22.86, A_mod=3.106352,
        gamma=1.040, I0_ref=2.37e-11, Iph_ref=18.590, Rs=0.135, Rsh=200.0,
    ),
    'CS7N-715TB-AG': dict(
        modelo='CS7N-715TB-AG', fabricante='CSI Solar Co., Ltd.', tecnologia='Mono-Si bifacial',
        Pmpp=715.0, Vmpp=40.60, Voc=48.50, Impp=17.630, Isc=18.640,
        mu_Pmpp=-0.290, mu_Voc=-0.2458, mu_Isc=0.0500,
        NOCT=45.0, phi=0.800, N_cs=66, eta=23.02, A_mod=3.106352,
        gamma=1.042, I0_ref=2.24e-11, Iph_ref=18.640, Rs=0.135, Rsh=200.0,
    ),
    'CS7N-720TB-AG': dict(
        modelo='CS7N-720TB-AG', fabricante='CSI Solar Co., Ltd.', tecnologia='Mono-Si bifacial',
        Pmpp=720.0, Vmpp=40.80, Voc=48.70, Impp=17.670, Isc=18.690,
        mu_Pmpp=-0.290, mu_Voc=-0.2448, mu_Isc=0.0499,
        NOCT=45.0, phi=0.800, N_cs=66, eta=23.18, A_mod=3.106352,
        gamma=1.043, I0_ref=2.06e-11, Iph_ref=18.690, Rs=0.135, Rsh=200.0,
    ),
    'CS7N-725TB-AG': dict(
        modelo='CS7N-725TB-AG', fabricante='CSI Solar Co., Ltd.', tecnologia='Mono-Si bifacial',
        Pmpp=725.0, Vmpp=41.00, Voc=48.90, Impp=17.710, Isc=18.740,
        mu_Pmpp=-0.290, mu_Voc=-0.2438, mu_Isc=0.0497,
        NOCT=45.0, phi=0.800, N_cs=66, eta=23.34, A_mod=3.106352,
        gamma=1.045, I0_ref=1.94e-11, Iph_ref=18.740, Rs=0.136, Rsh=210.0,
    ),
    'CS7N-730TB-AG': dict(
        modelo='CS7N-730TB-AG', fabricante='CSI Solar Co., Ltd.', tecnologia='Mono-Si bifacial',
        Pmpp=730.0, Vmpp=41.20, Voc=49.10, Impp=17.750, Isc=18.790,
        mu_Pmpp=-0.290, mu_Voc=-0.2428, mu_Isc=0.0496,
        NOCT=45.0, phi=0.800, N_cs=66, eta=23.50, A_mod=3.106352,
        gamma=1.051, I0_ref=2.04e-11, Iph_ref=18.790, Rs=0.135, Rsh=210.0,
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# 12. Catálogo de inversores (parâmetros derivados dos arquivos .OND)
# ─────────────────────────────────────────────────────────────────────────────

CATALOGO_INVERSORES = {
    # ── Série S — monofásico residencial ─────────────────────────────────────
    'CSI-5K-S22003-E': dict(
        modelo='CSI-5K-S22003-E', fabricante='CSI Solar Co., Ltd.',
        P_nomAC=5.0, P_maxAC=5.0, eta_max=97.50, eta_euro=96.80,
        V_dc_max=600, V_mpp_min=100, V_mpp_max=500, V_nom=360, N_mppt=2, N_str_max=2,
        profil_curves={'V2': [
            (24.8,0.0),(250.0,234.4),(500.0,481.5),(1000.0,973.1),
            (1250.0,1217.6),(1500.0,1462.0),(2500.0,2436.7),(3750.0,3640.9),(5000.0,4848.5),
        ]},
    ),
    'CSI-7K-S22003-E': dict(
        modelo='CSI-7K-S22003-E', fabricante='CSI Solar Co., Ltd.',
        P_nomAC=7.0, P_maxAC=7.0, eta_max=97.50, eta_euro=96.80,
        V_dc_max=600, V_mpp_min=100, V_mpp_max=500, V_nom=360, N_mppt=2, N_str_max=2,
        profil_curves={'V2': [
            (34.7,0.0),(350.0,339.1),(700.0,684.0),(1400.0,1373.0),
            (1750.0,1716.7),(2100.0,2059.5),(3500.0,3424.1),(5250.0,5117.2),(7000.0,6799.1),
        ]},
    ),
    'CSI-9K-S22003-E': dict(
        modelo='CSI-9K-S22003-E', fabricante='CSI Solar Co., Ltd.',
        P_nomAC=9.0, P_maxAC=9.0, eta_max=97.50, eta_euro=96.80,
        V_dc_max=600, V_mpp_min=100, V_mpp_max=500, V_nom=360, N_mppt=2, N_str_max=2,
        profil_curves={'V2': [
            (34.7,0.0),(450.0,436.0),(900.0,879.5),(1800.0,1765.3),
            (2250.0,2207.2),(2700.0,2647.9),(4500.0,4402.4),(6750.0,6579.2),(9000.0,8741.7),
        ]},
    ),
    # ── Série T2201A — trifásico string 220 V ────────────────────────────────
    'CSI-50K-T2201A-E': dict(
        modelo='CSI-50K-T2201A-E', fabricante='CSI Solar Co., Ltd.',
        P_nomAC=50.0, P_maxAC=50.0, eta_max=99.0, eta_euro=98.60,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=560, N_mppt=6, N_str_max=2,
        profil_curves={'V2': [
            (250.0,0.0),(2500.0,2293.0),(5000.0,4602.0),(10000.0,9643.0),
            (12500.0,12083.7),(15000.0,14523.0),(25000.0,24220.0),(37500.0,36285.0),(50000.0,48280.0),
        ]},
    ),
    'CSI-60K-T2201A-E': dict(
        modelo='CSI-60K-T2201A-E', fabricante='CSI Solar Co., Ltd.',
        P_nomAC=60.0, P_maxAC=60.0, eta_max=99.0, eta_euro=98.60,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=560, N_mppt=6, N_str_max=2,
        profil_curves={'V2': [
            (250.0,0.0),(3000.0,2813.7),(6000.0,5716.2),(12000.0,11598.0),
            (15000.0,14524.5),(18000.0,17442.0),(30000.0,29064.0),(45000.0,43488.0),(60000.0,57828.0),
        ]},
    ),
    'CSI-75K-T2201A-E': dict(
        modelo='CSI-75K-T2201A-E', fabricante='CSI Solar Co., Ltd.',
        P_nomAC=75.0, P_maxAC=75.0, eta_max=99.0, eta_euro=98.60,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=560, N_mppt=6, N_str_max=2,
        profil_curves={'V2': [
            (250.0,0.0),(3750.0,3479.2),(7500.0,7197.0),(15000.0,14526.0),
            (18750.0,18170.6),(22500.0,21818.3),(37500.0,36285.0),(56250.0,54253.1),(75000.0,72090.0),
        ]},
    ),
    # ── Série T4001A — trifásico string 400 V ────────────────────────────────
    'CSI-15K-T4001A-E': dict(
        modelo='CSI-15K-T4001A-E', fabricante='CSI Solar Inc',
        P_nomAC=15.0, P_maxAC=15.0, eta_max=98.43, eta_euro=98.14,
        V_dc_max=1100, V_mpp_min=160, V_mpp_max=1000, V_nom=635, N_mppt=2, N_str_max=2,
        profil_curves={'V2': [
            (123.8,0.0),(750.0,693.4),(1500.0,1434.3),(3000.0,2913.3),
            (3750.0,3651.7),(4500.0,4389.3),(7500.0,7329.8),(11250.0,10985.6),(15000.0,14613.0),
        ]},
    ),
    'CSI-17K-T4001A-E': dict(
        modelo='CSI-17K-T4001A-E', fabricante='CSI Solar Inc',
        P_nomAC=17.0, P_maxAC=17.0, eta_max=98.43, eta_euro=98.14,
        V_dc_max=1100, V_mpp_min=160, V_mpp_max=1000, V_nom=635, N_mppt=2, N_str_max=2,
        profil_curves={'V2': [
            (123.8,0.0),(850.0,791.9),(1700.0,1631.0),(3400.0,3306.8),
            (4250.0,4145.0),(5100.0,4980.7),(8500.0,8309.6),(12750.0,12436.4),(17000.0,16551.2),
        ]},
    ),
    'CSI-20K-T4001A-E': dict(
        modelo='CSI-20K-T4001A-E', fabricante='CSI Solar Inc',
        P_nomAC=20.0, P_maxAC=20.0, eta_max=98.43, eta_euro=98.14,
        V_dc_max=1100, V_mpp_min=160, V_mpp_max=1000, V_nom=635, N_mppt=2, N_str_max=2,
        profil_curves={'V2': [
            (123.8,0.0),(1000.0,935.4),(2000.0,1925.2),(4000.0,3900.4),
            (5000.0,4886.5),(6000.0,5871.0),(10000.0,9795.0),(15000.0,14668.5),(20000.0,19506.0),
        ]},
    ),
    'CSI-23K-T4001A-E': dict(
        modelo='CSI-23K-T4001A-E', fabricante='CSI Solar Inc',
        P_nomAC=23.0, P_maxAC=23.0, eta_max=98.43, eta_euro=98.14,
        V_dc_max=1100, V_mpp_min=160, V_mpp_max=1000, V_nom=635, N_mppt=2, N_str_max=2,
        profil_curves={'V2': [
            (123.8,0.0),(1150.0,1085.1),(2300.0,2222.7),(4600.0,4493.3),
            (5750.0,5626.4),(6900.0,6755.8),(11500.0,11264.2),(17250.0,16856.7),(23000.0,22395.1),
        ]},
    ),
    'CSI-25K-T4001A-E': dict(
        modelo='CSI-25K-T4001A-E', fabricante='CSI Solar Inc',
        P_nomAC=25.0, P_maxAC=25.0, eta_max=98.43, eta_euro=98.14,
        V_dc_max=1100, V_mpp_min=160, V_mpp_max=1000, V_nom=635, N_mppt=2, N_str_max=2,
        profil_curves={'V2': [
            (123.8,0.0),(1250.0,1184.9),(2500.0,2421.0),(5000.0,4888.5),
            (6250.0,6119.4),(7500.0,7347.0),(12500.0,12238.8),(18750.0,18303.8),(25000.0,24305.0),
        ]},
    ),
    'CSI-40K-T4001A-E': dict(
        modelo='CSI-40K-T4001A-E', fabricante='CSI Solar Inc',
        P_nomAC=40.0, P_maxAC=44.0, eta_max=98.43, eta_euro=98.14,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=600, N_mppt=3, N_str_max=2,
        profil_curves={'V2': [
            (198.0,0.0),(2000.0,1833.6),(4000.0,3824.0),(8000.0,7761.6),
            (10000.0,9736.0),(12000.0,11694.0),(20000.0,19552.0),(30000.0,29367.0),(40000.0,39052.0),
        ]},
    ),
    'CSI-50K-T4001A-E': dict(
        modelo='CSI-50K-T4001A-E', fabricante='CSI Solar Inc',
        P_nomAC=50.0, P_maxAC=55.0, eta_max=98.43, eta_euro=98.14,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=600, N_mppt=4, N_str_max=2,
        profil_curves={'V2': [
            (198.0,0.0),(2500.0,2335.3),(5000.0,4806.0),(10000.0,9735.0),
            (12500.0,12190.0),(15000.0,14649.0),(25000.0,24457.5),(37500.0,36641.2),(50000.0,48745.0),
        ]},
    ),
    'CSI-60K-T4001A-E': dict(
        modelo='CSI-60K-T4001A-E', fabricante='CSI Solar Inc',
        P_nomAC=60.0, P_maxAC=60.0, eta_max=98.43, eta_euro=98.14,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=600, N_mppt=5, N_str_max=2,
        profil_curves={'V2': [
            (198.0,0.0),(3000.0,2825.4),(6000.0,5790.0),(12000.0,11698.8),
            (15000.0,14644.5),(18000.0,17598.6),(30000.0,29319.0),(45000.0,43884.0),(60000.0,58368.0),
        ]},
    ),
    'CSI-75K-T40001-E': dict(
        modelo='CSI-75K-T40001-E', fabricante='CSI Solar Inc',
        P_nomAC=75.0, P_maxAC=75.0, eta_max=97.50, eta_euro=96.80,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=600, N_mppt=6, N_str_max=2,
        profil_curves={'V2': [
            (618.8,0.0),(3750.0,3570.4),(7500.0,7284.0),(15000.0,14695.5),
            (18750.0,18401.2),(22500.0,22104.0),(37500.0,36937.5),(56250.0,55282.5),(75000.0,73582.5),
        ]},
    ),
    'CSI-100K-T4001A-E': dict(
        modelo='CSI-100K-T4001A-E', fabricante='CSI Solar Inc',
        P_nomAC=100.0, P_maxAC=100.0, eta_max=97.50, eta_euro=96.80,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=600, N_mppt=6, N_str_max=2,
        profil_curves={'V2': [
            (618.8,0.0),(5000.0,4836.5),(10000.0,9792.0),(20000.0,19686.0),
            (25000.0,24622.5),(30000.0,29508.0),(50000.0,49105.0),(75000.0,73582.5),(100000.0,97990.0),
        ]},
    ),
    'CSI-100K-T4001B-E': dict(
        modelo='CSI-100K-T4001B-E', fabricante='CSI Solar Inc',
        P_nomAC=100.0, P_maxAC=100.0, eta_max=97.50, eta_euro=96.80,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=600, N_mppt=9, N_str_max=2,
        profil_curves={'V2': [
            (618.8,0.0),(5000.0,4836.0),(10000.0,9793.0),(20000.0,19684.0),
            (25000.0,24622.5),(30000.0,29502.0),(50000.0,49090.0),(75000.0,73575.0),(100000.0,97870.0),
        ]},
    ),
    'CSI-110K-T4001A-E': dict(
        modelo='CSI-110K-T4001A-E', fabricante='CSI Solar Inc',
        P_nomAC=110.0, P_maxAC=110.0, eta_max=97.50, eta_euro=96.80,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=600, N_mppt=6, N_str_max=2,
        profil_curves={'V2': [
            (618.8,0.0),(5500.0,5294.8),(11000.0,10737.1),(22000.0,21595.2),
            (27500.0,27013.3),(33000.0,32422.5),(55000.0,54180.5),(82500.0,80833.5),(110000.0,107382.0),
        ]},
    ),
    'CSI-110K-T4001B-E': dict(
        modelo='CSI-110K-T4001B-E', fabricante='CSI Solar Inc',
        P_nomAC=110.0, P_maxAC=110.0, eta_max=97.50, eta_euro=96.80,
        V_dc_max=1100, V_mpp_min=200, V_mpp_max=1000, V_nom=600, N_mppt=9, N_str_max=2,
        profil_curves={'V2': [
            (618.8,0.0),(5500.0,5330.6),(11000.0,10771.2),(22000.0,21643.6),
            (27500.0,27076.5),(33000.0,32498.4),(55000.0,54131.0),(82500.0,81089.3),(110000.0,107074.0),
        ]},
    ),
    # ── Série T8001 — central 800 V AC ───────────────────────────────────────
    'CSI-250K-T8001A-E': dict(
        modelo='CSI-250K-T8001A-E', fabricante='CSI Solar Co., Ltd.',
        P_nomAC=250.0, P_maxAC=250.0, eta_max=99.00, eta_euro=98.80,
        V_dc_max=1500, V_mpp_min=500, V_mpp_max=1500, V_nom=1200, N_mppt=12, N_str_max=2,
        profil_curves={'V2': [
            (1250.0,0.0),(12500.0,12126.3),(25000.0,24592.5),(50000.0,49420.0),
            (62500.0,61825.0),(75000.0,74227.5),(125000.0,123762.5),(187500.0,185531.2),(250000.0,247150.0),
        ]},
    ),
    'CSI-333K-T8001A-E': dict(
        modelo='CSI-333K-T8001A-E', fabricante='CSI Solar Inc',
        P_nomAC=333.0, P_maxAC=333.0, eta_max=97.50, eta_euro=96.80,
        V_dc_max=1500, V_mpp_min=500, V_mpp_max=1500, V_nom=1200, N_mppt=12, N_str_max=2,
        profil_curves={'V2': [
            (1732.5,0.0),(16650.0,16247.1),(33300.0,32840.5),(66600.0,65907.4),
            (83250.0,82417.5),(99900.0,98851.0),(166500.0,164818.3),(249750.0,246952.8),(333000.0,328737.6),
        ]},
    ),
    'CSI-333K-T8001B-E': dict(
        modelo='CSI-333K-T8001B-E', fabricante='CSI Solar Inc',
        P_nomAC=333.0, P_maxAC=333.0, eta_max=97.50, eta_euro=96.80,
        V_dc_max=1500, V_mpp_min=500, V_mpp_max=1500, V_nom=1200, N_mppt=16, N_str_max=2,
        profil_curves={'V2': [
            (1732.5,0.0),(16650.0,16178.8),(33300.0,32810.5),(66600.0,65880.7),
            (83250.0,82400.9),(99900.0,98891.0),(166500.0,164851.7),(249750.0,246927.8),(333000.0,328870.8),
        ]},
    ),
    'CSI-350K-T8001A-E': dict(
        modelo='CSI-350K-T8001A-E', fabricante='CSI Solar Inc',
        P_nomAC=350.0, P_maxAC=350.0, eta_max=99.01, eta_euro=98.80,
        V_dc_max=1500, V_mpp_min=500, V_mpp_max=1500, V_nom=1200, N_mppt=12, N_str_max=2,
        profil_curves={'V2': [
            (1732.5,0.0),(17500.0,17078.2),(35000.0,34478.5),(70000.0,69216.0),
            (87500.0,86555.0),(105000.0,103960.5),(175000.0,173232.5),(262500.0,259455.0),(350000.0,345380.0),
        ]},
    ),
    'CSI-350K-T8001B-E': dict(
        modelo='CSI-350K-T8001B-E', fabricante='CSI Solar Inc',
        P_nomAC=350.0, P_maxAC=350.0, eta_max=99.01, eta_euro=98.81,
        V_dc_max=1500, V_mpp_min=500, V_mpp_max=1500, V_nom=1200, N_mppt=16, N_str_max=2,
        profil_curves={'V2': [
            (1732.5,0.0),(17500.0,17125.5),(35000.0,34520.5),(70000.0,69272.0),
            (87500.0,86616.2),(105000.0,103960.5),(175000.0,173232.5),(262500.0,259455.0),(350000.0,345555.0),
        ]},
    ),
}
