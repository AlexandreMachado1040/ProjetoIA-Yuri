#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  MOTOR PVSYST UNIFICADO v2.3                                                ║
║  Integra: ft_anual.py (Hay+Erbs+Bifacial RT) + Memorial PVSyst Rev03       ║
║  Novidade v2.1: chaveamento BIFACIAL / MONOFACIAL pelo usuário              ║
║    • BIFACIAL  → Ray-Tracing 2D ativo; G_bif=G_front+φ×G_rear;             ║
║                  relatório mostra G_rear, ganho bifacial e φ                ║
║    • MONOFACIAL→ Ray-Tracing desativado (φ=0); G_eff=G_front apenas;        ║
║                  relatório indica "sem bifacialidade"                        ║
║  Novidade v2.3: leitura de arquivos .PAN/.OND reais da pasta Arquivos/      ║
║    • Seleção interativa de módulo e inversor a partir dos arquivos           ║
║    • Eficiência do inversor pela curva ProfilPIO real do .OND                ║
║    • Modelo 1-diodo derivado diretamente dos parâmetros do .PAN              ║
║  Interface: UI interativa ou --auto (modo teste)                            ║
║  Saída: Relatório PDF 4 páginas estilo PVSyst + JSON                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  USO:                                                                        ║
║    python motor_pvsyst_unificado.py            → modo interativo             ║
║    python motor_pvsyst_unificado.py --auto     → padrão BIFACIAL (teste)    ║
║    python motor_pvsyst_unificado.py --mono     → padrão MONOFACIAL (teste)  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys, math, json, time, os, warnings, datetime
import urllib.request, urllib.error
warnings.filterwarnings('ignore')

try:
    import parsers_pvsyst as _pvp
    _PARSERS_OK = True
except ImportError:
    _pvp = None
    _PARSERS_OK = False

_ARQUIVOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Arquivos')

import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

PI = math.pi

# ═══════════════════════════════════════════════════════════════════════════
# PARTE 1 ── MOTOR ft_anual.py (COMPLETO, integrado sem modificações)
# ═══════════════════════════════════════════════════════════════════════════

DAYS_PER_MONTH  = [31,28,31,30,31,30,31,31,30,31,30,31]
MONTH_START_DAY = [1,32,60,91,121,152,182,213,244,274,305,335]
MONTH_NAMES     = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

# NASA POWER calibrado São Paulo → 1811 kWh/m²/ano (fallback offline)
NASA_GHI_SP = {1:6.378,2:6.052,3:5.419,4:4.559,5:3.778,6:3.431,
               7:3.738,8:4.381,9:4.796,10:5.231,11:5.696,12:6.141}

_NASA_CACHE = {}  # {(lat_r, lon_r): {'ghi','dni','dhi','t2m'} mensais climatológicos}

_NASA_MONTH_KEYS  = ['JAN','FEB','MAR','APR','MAY','JUN',
                     'JUL','AUG','SEP','OCT','NOV','DEC']
_NASA_PARAMS_CLIM = 'ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIF,T2M'
_NASA_PARAMS_HORA = 'ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIF,T2M'
_CACHE_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nasa_cache')

def _load_disk_cache(chave):
    path = os.path.join(_CACHE_DIR, chave + '.json')
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return None

def _save_disk_cache(chave, dados):
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(os.path.join(_CACHE_DIR, chave + '.json'), 'w') as f:
            json.dump(dados, f, separators=(',', ':'))
    except Exception:
        pass

def fetch_nasa_power_all(lat, lon, timeout=25):
    """
    Busca GHI, DNI, DHI e T2M mensais climatológicos da NASA POWER em uma chamada.
    Retorna dict {'ghi':{1..12},'dni':{1..12},'dhi':{1..12},'t2m':{1..12}} ou None.
    Cache: memória (_NASA_CACHE) + disco (nasa_cache/clim_*.json).
    """
    key = (round(lat, 2), round(lon, 2))
    if key in _NASA_CACHE:
        return _NASA_CACHE[key]
    disk_key = f"clim_{round(lat,2)}_{round(lon,2)}".replace('-', 'm').replace('.', 'p')
    cached = _load_disk_cache(disk_key)
    if cached:
        result = {p: {int(k): v for k, v in cached[p].items()} for p in cached}
        _NASA_CACHE[key] = result
        return result
    url = (
        "https://power.larc.nasa.gov/api/temporal/climatology/point"
        f"?parameters={_NASA_PARAMS_CLIM}"
        f"&community=RE&longitude={lon}&latitude={lat}&format=JSON"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MotorPVSyst/2.2"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        param = data["properties"]["parameter"]
        result = {}
        for nome, nasa_key in [('ghi', 'ALLSKY_SFC_SW_DWN'), ('dni', 'ALLSKY_SFC_SW_DNI'),
                                 ('dhi', 'ALLSKY_SFC_SW_DIF'), ('t2m', 'T2M')]:
            raw = param[nasa_key]
            result[nome] = {i+1: float(raw[k]) for i, k in enumerate(_NASA_MONTH_KEYS)}
        _NASA_CACHE[key] = result
        _save_disk_cache(disk_key, result)
        return result
    except Exception:
        return None

def fetch_nasa_power_ghi(lat, lon, timeout=15):
    """Compatibilidade: retorna apenas GHI mensal {1..12} kWh/m²/dia."""
    data = fetch_nasa_power_all(lat, lon, timeout)
    return data['ghi'] if data else None

def fetch_nasa_power_hourly(lat, lon, ano, tz=0, timeout=120):
    """
    Busca série horária de GHI, DNI, DHI e T2M da NASA POWER para um ano completo.
    Irradiâncias em W/m² (NASA entrega kWh/m²/h → ×1000 = W/m²). T2M em °C.
    Cache em disco: nasa_cache/hourly_<lat>_<lon>_<ano>.json.
    Retorna dict {(doy, hora_local): {'ghi','dni','dhi','t2m'}} ou None se falhar.
    """
    disk_key = (f"hourly_{round(lat,2)}_{round(lon,2)}_{ano}"
                .replace('-', 'm').replace('.', 'p'))
    cached = _load_disk_cache(disk_key)
    if cached:
        print(f"  [NASA] Cache em disco: {disk_key}.json ({len(cached)} registros)")
        return {(int(k.split('_')[0]), int(k.split('_')[1])): v for k, v in cached.items()}

    print(f"  [NASA] Buscando dados horários {ano} (lat={lat}, lon={lon})...")
    print("  [NASA] Aguarde — pode levar 30–120 s na primeira vez...")
    url = (
        "https://power.larc.nasa.gov/api/temporal/hourly/point"
        f"?parameters={_NASA_PARAMS_HORA}"
        f"&community=RE&longitude={lon}&latitude={lat}"
        f"&start={ano}0101&end={ano}1231&format=JSON&time-standard=UTC"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MotorPVSyst/2.2"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        param = data["properties"]["parameter"]
        ghi_r = param['ALLSKY_SFC_SW_DWN']
        dni_r = param['ALLSKY_SFC_SW_DNI']
        dhi_r = param['ALLSKY_SFC_SW_DIF']
        t2m_r = param['T2M']

        result = {}; disk_data = {}
        for ts in sorted(ghi_r.keys()):
            if len(ts) < 10: continue
            yr, mo, dy = int(ts[0:4]), int(ts[4:6]), int(ts[6:8])
            hr_utc = int(ts[8:10])
            hr_loc  = (hr_utc + tz) % 24
            doy_off = (hr_utc + tz) // 24
            doy = datetime.date(yr, mo, dy).timetuple().tm_yday + doy_off
            doy = max(1, min(doy, 366))
            entry = {
                'ghi': max(float(ghi_r[ts]) * 1000, 0.0),
                'dni': max(float(dni_r[ts]) * 1000, 0.0),
                'dhi': max(float(dhi_r[ts]) * 1000, 0.0),
                't2m': float(t2m_r[ts]),
            }
            result[(doy, hr_loc)] = entry
            disk_data[f"{doy}_{hr_loc}"] = entry

        print(f"  [NASA] ✓ {len(result)} registros horários carregados (ano {ano})")
        _save_disk_cache(disk_key, disk_data)
        return result
    except Exception as e:
        print(f"  [NASA] ✗ Falha ao buscar dados horários: {e}")
        return None

def month_of_day(doy):
    for m in range(11,-1,-1):
        if doy >= MONTH_START_DAY[m]: return m+1
    return 1

def build_nasa_data(lat, lon, ghi_anual_alvo=None):
    """
    Retorna dict {'ghi','dni','dhi','t2m'} com dados mensais climatológicos.
    Prioridade 1: NASA POWER ao vivo (GHI+DNI+DHI+T2M reais).
    Prioridade 2: fallback offline — GHI escalado de SP + Erbs estimado + T2M=22°C.
    """
    live = fetch_nasa_power_all(lat, lon)
    if live:
        nasa = live
    else:
        ref_lat = -23.55
        scale   = 1.0 + (abs(ref_lat) - abs(lat)) * 0.012
        ghi_m   = {m: v * scale for m, v in NASA_GHI_SP.items()}
        kd_typ  = 0.35
        nasa = {
            'ghi': ghi_m,
            'dni': {m: max(ghi_m[m] * (1 - kd_typ) / 0.7, 0) for m in range(1, 13)},
            'dhi': {m: ghi_m[m] * kd_typ for m in range(1, 13)},
            't2m': {m: 22.0 for m in range(1, 13)},
        }
    if ghi_anual_alvo:
        atual = sum(nasa['ghi'][m] * DAYS_PER_MONTH[m-1] for m in range(1, 13))
        fator = ghi_anual_alvo / atual
        nasa  = {**nasa, 'ghi': {m: v * fator for m, v in nasa['ghi'].items()}}
    return nasa

def build_nasa_ghi(lat, lon, ghi_anual_alvo=None):
    """Compatibilidade: retorna apenas GHI mensal {1..12} kWh/m²/dia."""
    return build_nasa_data(lat, lon, ghi_anual_alvo)['ghi']

def calc_solar_position(doy, hour_mid, lat, lon, tz):
    B     = (doy-1)*2*PI/365
    ET    = 229.18*(0.000075+0.001868*math.cos(B)-0.032077*math.sin(B)
                    -0.014615*math.cos(2*B)-0.040890*math.sin(2*B))
    decl  = math.degrees(0.006918-0.399912*math.cos(B)+0.070257*math.sin(B)
                          -0.006758*math.cos(2*B)+0.000907*math.sin(2*B)
                          -0.002697*math.cos(3*B)+0.001480*math.sin(3*B))
    hs    = hour_mid + (ET+4*(lon-tz*15))/60
    HA    = 15*(hs-12)
    lr    = math.radians(lat); dr=math.radians(decl); Hr=math.radians(HA)
    sin_h = math.sin(lr)*math.sin(dr)+math.cos(lr)*math.cos(dr)*math.cos(Hr)
    HSun  = math.degrees(math.asin(max(min(sin_h,1),-1)))
    AzSun = 0.0
    if HSun > 0.5:
        ca = max(min((math.sin(dr)*math.cos(lr)-math.cos(dr)*math.sin(lr)*math.cos(Hr))
                     /math.cos(math.radians(HSun)),1),-1)
        AzSun = math.degrees(math.acos(ca))*(-1 if HA>0 else 1)
    ENI = 1361*(1+0.033*math.cos(2*PI*doy/365))
    return HSun, AzSun, ENI, decl, HA

def calc_daily_kd(doy, daily_GHI, lat):
    B    = (doy-1)*2*PI/365
    decl = math.degrees(0.006918-0.399912*math.cos(B)+0.070257*math.sin(B)
                         -0.006758*math.cos(2*B)+0.000907*math.sin(2*B)
                         -0.002697*math.cos(3*B)+0.001480*math.sin(3*B))
    lr   = math.radians(lat); dr=math.radians(decl)
    chs  = max(min(-math.tan(lr)*math.tan(dr),1),-1)
    HS0  = math.acos(chs)
    E0   = 1+0.033*math.cos(2*PI*doy/365)
    H0   = (24*1361*E0/PI*(math.sin(lr)*math.sin(dr)*HS0
                            +math.cos(lr)*math.cos(dr)*math.sin(HS0)))/1000
    KT   = max(min(daily_GHI/H0,1),0) if H0>0 else 0.5
    if   KT<0.22:  return 1-0.09*KT
    elif KT<=0.80: return 0.9511-0.1604*KT+4.388*KT**2-16.638*KT**3+12.336*KT**4
    return 0.165

def calc_ghi_hourly(doy, hour, daily_GHI, Kd, lat, lon, tz):
    HSun,AzSun,ENI,decl,HA = calc_solar_position(doy, hour+0.5, lat, lon, tz)
    if HSun<=2: return 0,0,0,HSun,AzSun,ENI
    lr   = math.radians(lat); dr=math.radians(decl)
    chs  = max(min(-math.tan(lr)*math.tan(dr),1),-1)
    HS0d = math.degrees(math.acos(chs))
    if HS0d<0.5: return 0,0,0,HSun,AzSun,ENI
    w  = math.radians(HA); w0=math.radians(HS0d)
    a  = 0.4090+0.5016*math.sin(w0-PI/3)
    b  = 0.6609-0.4767*math.sin(w0-PI/3)
    den= math.sin(w0)-w0*math.cos(w0)
    rt = max((PI/24)*(a+b*math.cos(w))*(math.cos(w)-math.cos(w0))/den,0) if den>0 else 0
    GHI = rt*daily_GHI*1000
    DHI = Kd*GHI
    DNI = (GHI-DHI)/math.sin(math.radians(HSun)) if math.sin(math.radians(HSun))>0.05 else 0
    return GHI, DNI, DHI, HSun, AzSun, ENI

def calc_ft_frontal(HSun, AzSun, GHI, DNI, DHI, ENI, albedo, tilt_deg, az_panel_deg):
    if HSun<=0.5 or GHI<=0: return 0.0, 0.0
    h  = math.radians(HSun); t=math.radians(tilt_deg)
    ar = math.radians(AzSun-az_panel_deg)
    cos_ia = math.cos(ar)*math.cos(h)*math.sin(t)+math.sin(h)*math.cos(t)
    Rb     = max(cos_ia/math.sin(h),0)
    fAni   = min(DNI/ENI,1) if ENI>0 else 0
    Gt     = max(DNI*Rb+DHI*(fAni*Rb+(1-fAni)*(1+math.cos(t))/2)
                 +GHI*albedo*(1-math.cos(t))/2, 0)
    return Gt, Gt/GHI

def _ray_seg_intersect(ox,oy,dx,dy,x1,y1,x2,y2):
    d = dx*(y2-y1)-dy*(x2-x1)
    if abs(d)<1e-12: return None
    t = ((x1-ox)*(y2-y1)-(y1-oy)*(x2-x1))/d
    if t<=1e-9: return None
    s = ((x1-ox)*dy-(y1-oy)*dx)/d
    return t if -1e-9<=s<=1+1e-9 else None

def calc_rear_raytracing(HSun, AzSun, GHI, DNI, DHI, tilt_deg, L, pitch,
                          albedo_ground, N_seg=15, N_rays=180, max_bounces=3):
    if HSun<=2 or GHI<=0: return 0.0
    T_r=math.radians(tilt_deg); cT=math.cos(T_r); sT=math.sin(T_r)
    x1=L*cT; y1=L*sT
    rn_angle=math.atan2(-cT,sT)
    H_r=math.radians(HSun); sun_x=-math.cos(H_r); sun_y=math.sin(H_r)
    G_rear_acc=0.0
    for seg in range(N_seg):
        s=(seg+0.5)/N_seg; px=s*x1; py=s*y1
        seg_G=0.0; seg_w=0.0
        for ray_i in range(N_rays):
            theta=(ray_i+0.5)/N_rays*PI-PI/2
            ray_angle=rn_angle+theta
            rdx=math.cos(ray_angle); rdy=math.sin(ray_angle)
            lam_w=math.cos(theta)
            cx,cy=px,py; cdx,cdy=rdx,rdy; contribution=0.0; att=1.0
            for bounce in range(max_bounces+1):
                t_min=float('inf'); hit='sky'
                if cdy<-1e-12:
                    t_g=-cy/cdy
                    if t_g>1e-9 and t_g<t_min:
                        t_min=t_g
                        xh=(cx+t_g*cdx)%pitch
                        hit='ground_unshaded' if x1<=xh<=pitch else 'ground_shaded'
                for period in (-2,-1,1,2):
                    ox_mod=period*pitch
                    t_mod=_ray_seg_intersect(cx,cy,cdx,cdy,ox_mod,0,ox_mod+x1,y1)
                    if t_mod is not None and t_mod<t_min:
                        t_min=t_mod; hit='module'
                if hit=='sky' or t_min==float('inf'):
                    if cdy>0:
                        cos_sun=cdx*sun_x+cdy*sun_y
                        contribution+=att*(DNI if cos_sun>0.9999 and HSun>2 else DHI/PI)
                    break
                elif hit=='module': break
                elif 'ground' in hit:
                    g_irr=GHI if hit=='ground_unshaded' else DHI
                    contribution+=att*albedo_ground*g_irr*0.5
                    if bounce<max_bounces and att*albedo_ground>0.01:
                        cx+=t_min*cdx; cy=1e-6; cdy=abs(cdy); att*=albedo_ground*0.5
                    else: break
            seg_G+=contribution*lam_w; seg_w+=lam_w
        if seg_w>0: G_rear_acc+=seg_G/seg_w
    return max(G_rear_acc/N_seg,0.0) if N_seg>0 else 0.0

def integrar_anual(lat, lon, tz, tilt, az_panel, albedo, phi,
                   pitch, mod_height, N_seg=15, N_rays=180, verbose=True,
                   bifacial=True, modo_dados='climatologia', ano=None):
    """
    Integração anual com duas fontes de dados NASA POWER:
      modo_dados='climatologia' → média de longo prazo mensal + CPR/Erbs horário
      modo_dados='horario'      → série horária real do ano especificado (ano=YYYY)
    bifacial=True  → Ray-Tracing 2D ativo; G_bif = G_front + φ×G_rear
    bifacial=False → G_rear=0, G_bif=G_front
    Tupla horária: (doy, hour, GHI, DNI, DHI, HSun, AzSun, Gf, Gr, Gb, T2M)
    """
    nasa_data = build_nasa_data(lat, lon)
    NASA_GHI  = nasa_data['ghi']
    NASA_T2M  = nasa_data['t2m']
    GHI_ref   = sum(NASA_GHI[m]*DAYS_PER_MONTH[m-1] for m in range(1,13))

    # Modo horário: busca série real da NASA POWER
    hourly_nasa = None
    if modo_dados == 'horario':
        if ano is None:
            ano = datetime.date.today().year - 1
        hourly_nasa = fetch_nasa_power_hourly(lat, lon, ano, tz)
        if hourly_nasa is None:
            print("  ⚠ Dados horários indisponíveis — modo climatológico ativado")
            modo_dados = 'climatologia'

    fonte_str = (f"NASA POWER horário {ano}" if modo_dados == 'horario' and hourly_nasa
                 else "Climatologia NASA POWER (longo prazo)")
    modo_str  = "BIFACIAL (Ray-Tracing 2D)" if bifacial else "MONOFACIAL (sem Ray-Tracing)"

    if verbose:
        print(f"\n  {'═'*56}")
        print(f"  INTEGRAÇÃO ANUAL — {modo_str}")
        print(f"  Fonte dados: {fonte_str}")
        print(f"  LAT={lat}° | LON={lon}° | Tz=UTC{tz:+d}")
        print(f"  Tilt={tilt}° | Az={az_panel}° | Albedo={albedo}")
        if bifacial:
            print(f"  φ={phi} | pitch={pitch}m | H_mod={mod_height}m")
        else:
            print(f"  φ=0.00 (bifacialidade DESATIVADA)")
        print(f"  GHI ref. climatologia: {GHI_ref:.0f} kWh/m²/ano")
        print(f"  {'─'*56}")

    acc = dict(GHI=0.,DNI=0.,DHI=0.,Gf=0.,Gb=0.,Gr=0.,hrs=0)
    mon = {k:[0.]*12 for k in ('GHI','Gf','Gb','DNI','DHI')}
    hourly = []  # (doy, hour, GHI, DNI, DHI, HSun, AzSun, Gf, Gr, Gb, T2M)

    is_leap = (ano is not None and ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0))
    doy_max = 366 if (modo_dados == 'horario' and is_leap) else 365

    t0 = time.time()
    for doy in range(1, doy_max + 1):
        m = month_of_day(doy); mi = m - 1
        T2M_mes = NASA_T2M.get(m, 22.0)

        if modo_dados == 'horario' and hourly_nasa is not None:
            # ── Modo horário: dados reais por hora da NASA POWER ─────────────
            for hour in range(24):
                entry = hourly_nasa.get((doy, hour))
                if entry is None: continue
                GHI = entry['ghi']; DNI = entry['dni']
                DHI = entry['dhi']; T2M_h = entry['t2m']
                if GHI < 1: continue
                HSun, AzSun, ENI, _, _ = calc_solar_position(doy, hour+0.5, lat, lon, tz)
                if HSun <= 2: continue
                acc['GHI']+=GHI; acc['DNI']+=DNI; acc['DHI']+=DHI; acc['hrs']+=1
                mon['GHI'][mi]+=GHI; mon['DNI'][mi]+=DNI; mon['DHI'][mi]+=DHI
                Gf,_ = calc_ft_frontal(HSun,AzSun,GHI,DNI,DHI,ENI,albedo,tilt,az_panel)
                acc['Gf']+=Gf; mon['Gf'][mi]+=Gf
                if bifacial:
                    Gr = calc_rear_raytracing(HSun,AzSun,GHI,DNI,DHI,tilt,mod_height,pitch,
                                              albedo,N_seg,N_rays)
                else:
                    Gr = 0.0
                Gb = Gf + phi*Gr
                acc['Gb']+=Gb; acc['Gr']+=Gr; mon['Gb'][mi]+=Gb
                hourly.append((doy,hour,GHI,DNI,DHI,HSun,AzSun,Gf,Gr,Gb,T2M_h))
        else:
            # ── Modo climatológico: CPR + Erbs por dia (comportamento original) ─
            dly = NASA_GHI[m]; Kd = calc_daily_kd(doy, dly, lat)
            for hour in range(24):
                GHI,DNI,DHI,HSun,AzSun,ENI = calc_ghi_hourly(doy,hour,dly,Kd,lat,lon,tz)
                if GHI<1 or HSun<=2: continue
                acc['GHI']+=GHI; acc['DNI']+=DNI; acc['DHI']+=DHI; acc['hrs']+=1
                mon['GHI'][mi]+=GHI; mon['DNI'][mi]+=DNI; mon['DHI'][mi]+=DHI
                Gf,_ = calc_ft_frontal(HSun,AzSun,GHI,DNI,DHI,ENI,albedo,tilt,az_panel)
                acc['Gf']+=Gf; mon['Gf'][mi]+=Gf
                if bifacial:
                    Gr = calc_rear_raytracing(HSun,AzSun,GHI,DNI,DHI,tilt,mod_height,pitch,
                                              albedo,N_seg,N_rays)
                else:
                    Gr = 0.0
                Gb = Gf + phi*Gr
                acc['Gb']+=Gb; acc['Gr']+=Gr; mon['Gb'][mi]+=Gb
                hourly.append((doy,hour,GHI,DNI,DHI,HSun,AzSun,Gf,Gr,Gb,T2M_mes))

    elapsed=time.time()-t0
    def kwh(x): return x/1000
    GHI_a=kwh(acc['GHI']); Gf_a=kwh(acc['Gf']); Gb_a=kwh(acc['Gb']); Gr_a=kwh(acc['Gr'])
    FTf=Gf_a/GHI_a if GHI_a>0 else 0
    FTb=Gb_a/GHI_a if GHI_a>0 else 0

    result = dict(
        lat=lat, lon=lon, tilt=tilt, az_panel=az_panel, albedo=albedo,
        phi=phi, pitch=pitch, mod_height=mod_height,
        bifacial=bifacial,
        phi_efetivo=phi if bifacial else 0.0,
        modo_dados=modo_dados,                                    # v2.2
        ano_dados=ano if modo_dados == 'horario' else None,       # v2.2
        fonte_dados=fonte_str,                                    # v2.2
        GHI_anual=round(GHI_a,1), DNI_anual=round(kwh(acc['DNI']),1),
        DHI_anual=round(kwh(acc['DHI']),1),
        DHI_GHI=round(kwh(acc['DHI'])/GHI_a,3) if GHI_a>0 else 0,
        Gtilt_frontal=round(Gf_a,1), FT_frontal=round(FTf,4),
        G_rear_rt=round(Gr_a,1), Gtilt_bifacial=round(Gb_a,1),
        FT_bifacial=round(FTb,4), ganho_bif_pct=round((FTb/FTf-1)*100 if FTf>0 else 0,2),
        horas_sol=acc['hrs'], tempo_calc_s=round(elapsed,1),
        monthly={k:[round(kwh(v),1) for v in mon[k]] for k in mon},
        hourly=hourly,
    )
    if verbose:
        print(f"  GHI={GHI_a:.1f} kWh/m² | FTf={FTf:.4f} | Fonte: {fonte_str}")
        if bifacial:
            print(f"  G_rear={Gr_a:.1f} kWh/m² | FTb={FTb:.4f} | Ganho bifacial={result['ganho_bif_pct']:+.2f}%")
        else:
            print(f"  MONOFACIAL: G_rear=0 | FTb=FTf={FTf:.4f} | sem ganho bifacial")
        print(f"  Horas={acc['hrs']} | t={elapsed:.1f}s")
    return result

# ═══════════════════════════════════════════════════════════════════════════
# PARTE 2 ── MODELO 1-DIODO (Parâmetros CS7N-730TB-AG calibrados)
# ═══════════════════════════════════════════════════════════════════════════

def solve_IV(V, Iph, I0, Rs, Rsh, Vt):
    I=Iph
    for _ in range(500):
        a=min((V+I*Rs)/Vt,500); ea=math.exp(a)
        f=I-Iph+I0*(ea-1)+(V+I*Rs)/Rsh
        df=1+I0*Rs*ea/Vt+Rs/Rsh
        if abs(df)<1e-20: break
        I-=f/df
        if abs(f)<1e-10: break
    return float(max(I,0))

def IV_string(V_str, T, Ns, Np, mod):
    """Corrente total da string Np×Ns módulos."""
    q=1.602e-19; kB=1.381e-23; T_ref=298.15; E_gap=1.12
    TcK=T+273.15
    Vt=mod['N_cs']*mod['gamma']*kB*TcK/q
    I0=mod['I0_ref']*(TcK/T_ref)**3*math.exp((q*E_gap)/(mod['gamma']*kB)*(1/T_ref-1/TcK))
    Iph=mod['Iph_ref']*(1+mod['mu_Isc']/100*(T-25))
    return Np*max(solve_IV(V_str/Ns, Iph, I0, mod['Rs'], mod['Rsh'], Vt), 0)

# ═══════════════════════════════════════════════════════════════════════════
# PARTE 3 ── CÁLCULO HORÁRIO DO SISTEMA + CADEIA DE PERDAS + HISTOGRAMA
#            Baseado no Memorial_Dimensionamento_PVSyst_v2 Rev03
# ═══════════════════════════════════════════════════════════════════════════

# Fatores de perda do Memorial (CSV PVSyst, São Paulo)
PERDAS_PADRAO = dict(
    f_shad   = 0.0186,   # Sombreamento próximo
    f_IAM    = 0.0438,   # IAM (ASHRAE b0=0.05)
    f_soil   = 0.0196,   # Sujeira / Soiling
    f_GInc   = 0.0081,   # Irradiância baixa
    f_temp   = 0.0272,   # Temperatura (TempLss)
    f_qual   = 0.0033,   # Qualidade módulo (positivo = ganho)
    f_LID    = 0.0174,   # LID (ajustar 0.002 para TOPCon N)
    f_mis    = 0.0615,   # Mismatch strings
    f_ohm    = 0.0073,   # Perdas ôhmicas DC
    f_ILPmax = 0.0144,   # Sobrecarga inversor (IL_Pmax)
    f_ILOper = 0.0365,   # Eficiência inversor (IL_Oper)
)

def calc_T_cell(Gf_Wm2, T_amb=22.0, alpha=0.90, eta_m=0.235, Uc=29.0):
    """Modelo térmico PVSyst: T_cell = T_amb + G_POA × α×(1−η_m)/Uc"""
    return T_amb + Gf_Wm2*alpha*(1-eta_m)/Uc if Gf_Wm2>0 else T_amb

def calc_perdas_DC(E_nom, perdas):
    """Aplica cadeia de perdas DC sobre E_nom e retorna E_Array."""
    f = perdas
    # E_nom_corr = E_nom × (1 - GIncLss - TempLss + ModQual - LID - Mis - Ohm)
    fator = (1 - f['f_GInc'] - f['f_temp'] + f['f_qual']
               - f['f_LID']  - f['f_mis']  - f['f_ohm'])
    return E_nom * fator

def calc_eta_inv_generico(P_array_kW, inv):
    """
    Eficiência do inversor em função da potência DC real (kW).
    Usa curvas ProfilPIOV do .OND quando disponíveis; caso contrário,
    usa interpolação paramétrica normalizada pelo eta_max do datasheet.

    P_array_kW : potência DC entregue ao inversor [kW]
    inv        : dict do inversor (campos 'profil_curves', 'eta_max', 'P_nomAC')
    Retorna η ∈ [0, 1].
    """
    if P_array_kW <= 0.01:
        return 0.0

    curves = inv.get('profil_curves', {})
    if curves:
        P_in_W = P_array_kW * 1000.0
        # Prefere V2 (tensão nominal); cai para primeira disponível
        key = 'V2' if 'V2' in curves else next(iter(curves))
        pts = curves[key]   # [(Pin_W, Pout_W), ...]

        if P_in_W < pts[0][0]:
            return 0.0
        if P_in_W >= pts[-1][0]:
            pin, pout = pts[-1]
            return pout / pin if pin > 0 else 0.0
        for i in range(len(pts) - 1):
            if pts[i][0] <= P_in_W <= pts[i+1][0]:
                alpha  = (P_in_W - pts[i][0]) / (pts[i+1][0] - pts[i][0])
                p_out  = pts[i][1] + alpha * (pts[i+1][1] - pts[i][1])
                return p_out / P_in_W
        return inv.get('eta_max', 99.0) / 100.0

    # Fallback: curva normalizada (forma baseada no CSI-250K, escalada pelo eta_max)
    eta_max  = inv.get('eta_max', 99.0) / 100.0
    P_nom_DC = inv['P_nomAC'] / eta_max if eta_max > 0 else inv['P_nomAC']
    P_ratio  = min(P_array_kW / P_nom_DC, 1.0) if P_nom_DC > 0 else 1.0
    pts_P = [0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00]
    pts_e = [0.940, 0.970, 0.983, 0.988, 0.990, 0.9901, 0.9895, 0.988]
    scale = eta_max / 0.9901
    p = min(max(P_ratio, 0.02), 1.0)
    for i in range(len(pts_P) - 1):
        if pts_P[i] <= p <= pts_P[i+1]:
            a = (p - pts_P[i]) / (pts_P[i+1] - pts_P[i])
            return min((pts_e[i] + a * (pts_e[i+1] - pts_e[i])) * scale, 0.9999)
    return min(pts_e[-1] * scale, 0.9999)


def calc_eta_inv_csi250(P_ratio, V_dc_norm=1.0):
    """Mantido para compatibilidade; redireciona para calc_eta_inv_generico."""
    inv_csi = dict(eta_max=99.01, P_nomAC=250.0, profil_curves={})
    P_nom_DC = 250.0 / 0.9901
    return calc_eta_inv_generico(P_ratio * P_nom_DC, inv_csi)

def calc_system_hourly(ft_result, sys_params):
    """
    Calcula hora a hora:
      P_mpp_pot = potência POTENCIAL do array (antes da limitação DC)
      P_array   = potência real extraída = min(P_mpp_pot, P_nomDC)
      IL_Pmax   = P_mpp_pot - P_array  (clipping)
      E_grid    = P_array × eta_inv

    Aplica também fatores de perda ópticos (IAM, soiling, shading)
    diretamente sobre G_eff antes de calcular a potência.

    Retorna: dict com séries horárias + totais + histograma.
    """
    mod   = sys_params['modulo']
    inv   = sys_params['inversor']
    Ns    = sys_params['N_s']
    Np    = sys_params['N_strings']
    phi   = mod['phi']
    perdas= sys_params.get('perdas', PERDAS_PADRAO)
    # v2.1 — respeitar flag bifacial do ft_result
    bifacial = ft_result.get('bifacial', True)
    phi_ef   = ft_result.get('phi_efetivo', phi)  # 0.0 se monofacial

    P_nom_stc  = Ns*Np*mod['Pmpp']/1000  # kWp
    P_nom_AC   = inv['P_nomAC']           # kW
    P_nom_DC   = P_nom_AC/(inv['eta_max']/100)  # kW
    mu_Pmpp    = mod['mu_Pmpp']/100       # /°C

    # Fatores ópticos sobre G_eff
    f_opt = (1 - perdas['f_shad'] - perdas['f_IAM'] - perdas['f_soil'])

    hours_out = []
    for (doy,hour,GHI,DNI,DHI,HSun,AzSun,Gf,Gr,Gb,T2M) in ft_result['hourly']:
        # Irradiância efetiva com perdas ópticas aplicadas (sobre componente frontal)
        Gf_eff = Gf * f_opt
        # v2.1: Gb_eff usa phi_ef=0 se monofacial → Gb_eff = Gf_eff
        Gb_eff = Gf_eff + phi_ef*Gr

        # Temperatura da célula (modelo térmico PVSyst) — T2M real da NASA
        T_cell = calc_T_cell(Gf_eff, T_amb=T2M)

        # Potência MPP potencial (inclui bifacial + correção temperatura + perdas DC)
        # P_mpp_pot [kW] = (G_eff [W/m²] / 1000) × P_nom_stc [kW] × (1 + μ×ΔT) × fDC
        G_norm    = Gb_eff/1000.0          # normalizado por G_STC=1000 W/m²
        # Temperatura já embutida via mu_Pmpp; aplica demais perdas DC restantes
        f_DC_rest = (1 - perdas['f_GInc'] - perdas['f_LID']
                       - perdas['f_mis']  - perdas['f_ohm']
                       + perdas['f_qual'])
        P_mpp_pot = G_norm * P_nom_stc * (1 + mu_Pmpp*(T_cell-25)) * f_DC_rest
        P_mpp_pot = max(P_mpp_pot, 0.0)

        # Potência real extraída (limite P_nomDC)
        P_array  = min(P_mpp_pot, P_nom_DC)
        IL_Pmax  = max(P_mpp_pot - P_nom_DC, 0.0)

        # Eficiência do inversor — usa curvas ProfilPIO reais se disponíveis
        eta_inv = calc_eta_inv_generico(P_array, inv)

        # Energia na rede (AC)
        E_grid_h = P_array * eta_inv

        hours_out.append(dict(
            doy=doy, hour=hour,
            GHI=round(GHI,2), Gf=round(Gf,2), Gb=round(Gb,2),
            Gf_eff=round(Gf_eff,2), Gb_eff=round(Gb_eff,2),
            T_cell=round(T_cell,1),
            P_mpp_pot=round(P_mpp_pot,4),
            P_array=round(P_array,4),
            IL_Pmax=round(IL_Pmax,4),
            eta_inv=round(eta_inv,5),
            E_grid=round(E_grid_h,4),
        ))

    # ── Totais anuais ──────────────────────────────────────────────────────
    arr = lambda k: np.array([h[k] for h in hours_out])
    P_mpp_a  = arr('P_mpp_pot');  E_arr_a = arr('P_array')
    IL_a     = arr('IL_Pmax');    E_g_a   = arr('E_grid')
    Gf_eff_a = arr('Gf_eff');     Gb_eff_a= arr('Gb_eff')

    E_mpp_tot   = float(P_mpp_a.sum())   # kWh
    E_array_tot = float(E_arr_a.sum())   # kWh
    IL_tot      = float(IL_a.sum())      # kWh
    E_grid_tot  = float(E_g_a.sum())     # kWh
    InvLoss_tot = E_array_tot - E_grid_tot

    # Irradiância no plano efetiva (kWh/m²)
    G_tilt_eff = float(Gf_eff_a.sum())/1000  # Wh → kWh
    G_bif_eff  = float(Gb_eff_a.sum())/1000

    # PR (PVSyst): PR = Yf / Yr_ref
    # Yr_ref = G_tilt_frontal (kWh/m²) = horas de pico equivalentes (base STC)
    # Yf     = E_grid / P_nom_stc
    # Nota: PR usa G_tilt ANTES das perdas ópticas como referência (PVSyst padrão)
    Yf      = E_grid_tot / P_nom_stc if P_nom_stc>0 else 0
    # G_tilt frontal do ft_result para PR (sem f_opt)
    G_tilt_pr= float(sum(h['Gf'] for h in hours_out))/1000  # Wh→kWh sem f_opt
    Yr      = G_tilt_pr if G_tilt_pr>0 else G_tilt_eff
    PR      = (Yf/Yr*100) if Yr>0 else 0

    # ── Histograma PVSyst ──────────────────────────────────────────────────
    # X = P_mpp_pot (potência POTENCIAL do array)
    # Série VERDE  = Σ P_mpp_pot × 1h por bin  → energia potencial
    # Série ROXA   = Σ P_array   × 1h por bin  → energia real (limitada por P_nomDC)
    # Diferença    = IL_Pmax por bin

    P_max_axis = max(float(P_mpp_a.max()), P_nom_stc) * 1.05 + 2
    bins = np.arange(0, P_max_axis+2, 2)
    ctr  = (bins[:-1]+bins[1:])/2
    mask = P_mpp_a > 0.01

    hist_v,_ = np.histogram(P_mpp_a[mask], bins=bins, weights=P_mpp_a[mask])
    hist_r,_ = np.histogram(P_mpp_a[mask], bins=bins, weights=E_arr_a[mask])
    hist_il,_= np.histogram(P_mpp_a[mask], bins=bins, weights=IL_a[mask])

    # ── Totais mensais ─────────────────────────────────────────────────────
    monthly_grid = [0.0]*12
    monthly_arr  = [0.0]*12
    for h in hours_out:
        mi = month_of_day(h['doy']) - 1
        monthly_grid[mi] += h['E_grid']
        monthly_arr[mi]  += h['P_array']

    return dict(
        hours        = hours_out,
        bifacial     = bifacial,           # v2.1
        phi_efetivo  = phi_ef,             # v2.1
        P_nom_stc    = round(P_nom_stc,2),
        P_nom_AC     = P_nom_AC,
        P_nom_DC     = round(P_nom_DC,2),
        R_DC_AC      = round(P_nom_stc/P_nom_AC,3),
        E_mpp_tot    = round(E_mpp_tot,1),
        E_array_tot  = round(E_array_tot,1),
        IL_tot       = round(IL_tot,1),
        IL_pct       = round(IL_tot/E_mpp_tot*100,2) if E_mpp_tot>0 else 0,
        E_grid_tot   = round(E_grid_tot,1),
        InvLoss_tot  = round(InvLoss_tot,1),
        InvLoss_pct  = round(InvLoss_tot/E_array_tot*100,2) if E_array_tot>0 else 0,
        G_tilt_eff   = round(G_tilt_eff,1),
        G_bif_eff    = round(G_bif_eff,1),
        PR           = round(PR,1),
        Yf           = round(Yf,0),
        Ya           = round(E_array_tot/P_nom_stc,0) if P_nom_stc>0 else 0,
        N_horas_clip = int((IL_a>0.001).sum()),
        bins_ctr     = ctr.tolist(),
        hist_verde   = hist_v.tolist(),
        hist_roxa    = hist_r.tolist(),
        hist_IL      = hist_il.tolist(),
        monthly_grid = [round(v,1) for v in monthly_grid],
        monthly_arr  = [round(v,1) for v in monthly_arr],
    )

# ═══════════════════════════════════════════════════════════════════════════
# PARTE 4 ── INTERFACE DO USUÁRIO
# ═══════════════════════════════════════════════════════════════════════════

def ask(prompt, default, typ=float, low=None, high=None):
    while True:
        try:
            raw = input(f"  {prompt} [{default}]: ").strip()
            v   = typ(raw) if raw else typ(str(default))
            if low is not None and v < low: print(f"    ⚠  min={low}"); continue
            if high is not None and v > high: print(f"    ⚠  max={high}"); continue
            return v
        except (ValueError, EOFError): return typ(str(default))


# ── Parâmetros de fallback (usados quando Arquivos/ não está disponível) ──────
_MOD_FALLBACK = dict(
    modelo='CS7N-730TB-AG', fabricante='CSI Solar Co., Ltd.',
    tecnologia='Mono-Si bifacial (φ=0.80)',
    Pmpp=730.0, Vmpp=41.2, Voc=49.1, Impp=17.75, Isc=18.79,
    mu_Pmpp=-0.29, mu_Voc=-0.2428, mu_Isc=0.0496,
    NOCT=41.0, phi=0.80, N_cs=132, eta=23.5,
    A_mod=2.384*1.303,
    gamma=1.051, I0_ref=2.034e-5, Iph_ref=18.803, Rs=0.135, Rsh=210.0,
)
_INV_FALLBACK = dict(
    modelo='CSI-250K-T8001A-E', fabricante='CSI Solar Co., Ltd.',
    P_nomAC=250.0, P_maxAC=250.0, eta_max=99.0, eta_euro=98.8,
    V_dc_max=1500, V_mpp_min=500, V_mpp_max=1500, V_start=550,
    V_nom=1090, N_mppt=12, N_str_max=24,
    I_max_mppt=0, I_sc_mppt=0,
    night_loss_W=15.0, pstart_W=1250.0,
    derate_T={-30:100, 0:100, 25:100, 50:100, 60:70},
    profil_curves={},
)


def _selecionar_modulo(auto=False):
    """
    Retorna dict `mod`. Em modo interativo oferece seleção dos arquivos .PAN.
    Fallback automático se a pasta Arquivos/ não existir.
    """
    pasta = os.path.join(_ARQUIVOS_DIR, 'PVmodules')
    modulos = []
    if _PARSERS_OK and os.path.isdir(pasta):
        modulos = _pvp.listar_modulos(pasta)

    if not modulos:
        if not auto:
            print("  ⚠  Pasta Arquivos/PVmodules não encontrada — usando módulo padrão.")
        return _MOD_FALLBACK.copy()

    # Índice padrão: módulo de maior Pmpp (último da lista ordenada)
    default_idx = len(modulos)   # 1-based

    if auto:
        mod = _pvp.parse_pan(modulos[-1][0])
        print(f"  Módulo (auto): {mod['modelo']}  {mod['Pmpp']:.0f} Wp")
        return mod

    print("\n  📦 MÓDULO FOTOVOLTAICO")
    print(f"  Arquivos .PAN disponíveis em Arquivos/PVmodules:")
    for i, (fp, nome, pmpp, phi) in enumerate(modulos, 1):
        bif_txt = f"bifacial φ={phi:.2f}" if phi > 0 else "monofacial"
        print(f"    [{i:2d}] {nome:<35s}  {pmpp:>6.0f} Wp  ({bif_txt})")
    print(f"    [ 0] Parâmetros padrão (fallback interno)")

    while True:
        try:
            raw = input(f"  Escolha o módulo [{default_idx}]: ").strip() or str(default_idx)
            idx = int(raw)
        except (ValueError, EOFError):
            idx = default_idx
        if idx == 0:
            print("  → Usando parâmetros padrão (fallback).")
            return _MOD_FALLBACK.copy()
        if 1 <= idx <= len(modulos):
            fp, nome, pmpp, phi = modulos[idx - 1]
            mod = _pvp.parse_pan(fp)
            print(f"  → Módulo selecionado: {mod['modelo']}  {mod['Pmpp']:.0f} Wp  η={mod['eta']:.1f}%")
            return mod
        print(f"    ⚠  Digite um número entre 0 e {len(modulos)}")


def _selecionar_inversor(auto=False):
    """
    Retorna dict `inv`. Em modo interativo oferece seleção dos arquivos .OND.
    Fallback automático se a pasta Arquivos/ não existir.
    """
    pasta = os.path.join(_ARQUIVOS_DIR, 'Inverters')
    inversores = []
    if _PARSERS_OK and os.path.isdir(pasta):
        inversores = _pvp.listar_inversores(pasta)

    if not inversores:
        if not auto:
            print("  ⚠  Pasta Arquivos/Inverters não encontrada — usando inversor padrão.")
        return _INV_FALLBACK.copy()

    # Índice padrão: CSI-250K se disponível, senão maior potência
    default_idx = len(inversores)
    for i, (fp, nome, pnom, eta, nmppt) in enumerate(inversores, 1):
        if '250' in nome and 'T8001' in nome:
            default_idx = i
            break

    if auto:
        inv = _pvp.parse_ond(inversores[default_idx - 1][0])
        print(f"  Inversor (auto): {inv['modelo']}  {inv['P_nomAC']:.0f} kW"
              f"  η={inv['eta_max']:.2f}%")
        return inv

    print("\n  🔌 INVERSOR")
    print(f"  Arquivos .OND disponíveis em Arquivos/Inverters:")
    for i, (fp, nome, pnom, eta, nmppt) in enumerate(inversores, 1):
        print(f"    [{i:2d}] {nome:<40s}  {pnom:>7.1f} kW  η={eta:.2f}%  {nmppt} MPPT")
    print(f"    [ 0] Parâmetros padrão (fallback interno)")

    while True:
        try:
            raw = input(f"  Escolha o inversor [{default_idx}]: ").strip() or str(default_idx)
            idx = int(raw)
        except (ValueError, EOFError):
            idx = default_idx
        if idx == 0:
            print("  → Usando parâmetros padrão (fallback).")
            return _INV_FALLBACK.copy()
        if 1 <= idx <= len(inversores):
            fp, nome, pnom, eta, nmppt = inversores[idx - 1]
            inv = _pvp.parse_ond(fp)
            n_curvas = len(inv.get('profil_curves', {}))
            print(f"  → Inversor selecionado: {inv['modelo']}  {inv['P_nomAC']:.0f} kW"
                  f"  η={inv['eta_max']:.2f}%"
                  f"  ({n_curvas} curvas ProfilPIO)")
            return inv
        print(f"    ⚠  Digite um número entre 0 e {len(inversores)}")


def get_inputs(auto=False):
    print("\n" + "═"*60)
    print("  MOTOR PVSyst UNIFICADO v2.3 — Configuração")
    print("═"*60)
    if auto: print("  Modo --auto | Módulo/inversor carregados de Arquivos/ (.PAN/.OND)\n")

    print("\n  📍 LOCALIZAÇÃO")
    lat = -23.55 if auto else ask("Latitude (° neg=Sul)",   -23.55, float, -90,   90)
    lon = -46.63 if auto else ask("Longitude (° neg=Oeste)",-46.63, float, -180, 180)
    tz  = -3     if auto else ask("Fuso horário UTC",        -3,     int,   -12,   14)

    print("\n  ☀  PLANO FOTOVOLTAICO")
    tilt = 20.8 if auto else ask("Inclinação (°)",          20.8, float, 0, 90)
    az   = 180  if auto else ask("Azimute (° — 180=Norte)", 180,  float, 0, 360)

    print("\n  🔧 CONFIGURAÇÃO DA STRING")
    Ns   = 28 if auto else ask("Módulos em série (N_s)",              28, int, 1, 50)
    Nstr = 3  if auto else ask("N° de strings / entradas no inversor",  3, int, 1, 30)

    # ── v2.1: escolha bifacial / monofacial ──────────────────────────────
    print("\n  🔆 MODELO DE IRRADIÂNCIA")
    if auto:
        bifacial = True   # modo --auto usa bifacial por padrão
    elif '--mono' in sys.argv:
        bifacial = False  # modo --mono força monofacial
    else:
        print("  Escolha o modelo de irradiância:")
        print("    [1] BIFACIAL   — Ray-Tracing 2D ativo; G_bif = G_front + φ×G_rear")
        print("                     Recomendado para módulos bifaciais (ex: CS7N-730TB-AG)")
        print("    [2] MONOFACIAL — Apenas irradiância frontal; G_eff = G_front")
        print("                     Use para módulos monofaciais ou comparação de cenários")
        while True:
            try:
                escolha = input("  Opção [1=Bifacial / 2=Monofacial] [1]: ").strip() or '1'
                if escolha in ('1','2'): bifacial = (escolha == '1'); break
                print("    ⚠  Digite 1 ou 2")
            except EOFError:
                bifacial = True; break
        modo_nome = "BIFACIAL" if bifacial else "MONOFACIAL"
        print(f"  → Modo selecionado: {modo_nome}")

    print("\n  🌿 PARÂMETROS AMBIENTAIS / BIFACIAL")
    albedo = 0.30  if auto else ask("Albedo do solo",            0.30, float, 0, 1)
    pitch  = 2.826 if auto else ask("Distância entre fileiras (m)", 2.826, float, 0.5, 30)
    modH   = 2.0   if auto else ask("Altura do módulo (m)",        2.0, float, 0.5, 5)

    print("\n  🚀 PRECISÃO DO MOTOR RAY-TRACING")
    Nseg  = 15  if auto else ask("Segmentos ray-tracing (15=rápido, 30=preciso)", 15, int, 5, 60)
    Nrays = 180 if auto else ask("Raios por segmento (180=rápido, 360=preciso)",  180,int,36,720)

    # ── v2.2: fonte de dados de irradiância (NASA climatologia vs horário) ─
    print("\n  🛰  FONTE DE DADOS NASA POWER")
    if auto:
        modo_dados = 'climatologia'; ano_dados = None
    else:
        print("  Escolha a fonte de dados de irradiância:")
        print("    [1] CLIMATOLOGIA — média de longo prazo (GHI+DNI+DHI+T2M, sem download extra)")
        print("    [2] HORÁRIO      — série horária real de 1 ano (~30–120 s de download)")
        print("                      DNI/DHI/T2M reais hora a hora; cache em disco após 1ª vez")
        while True:
            try:
                esc = input("  Opção [1=Climatologia / 2=Horário] [1]: ").strip() or '1'
                if esc in ('1', '2'): break
                print("    ⚠  Digite 1 ou 2")
            except EOFError:
                esc = '1'; break
        if esc == '2':
            ano_max  = datetime.date.today().year - 1
            ano_dados = ask(f"Ano dos dados horários (1990–{ano_max})", ano_max, int, 1990, ano_max)
            modo_dados = 'horario'
        else:
            modo_dados = 'climatologia'; ano_dados = None
        src_label = f"Horário NASA {ano_dados}" if modo_dados == 'horario' else "Climatologia NASA"
        print(f"  → Fonte selecionada: {src_label}")

    # ── v2.3: Seleção de módulo e inversor a partir de arquivos .PAN/.OND ──
    mod = _selecionar_modulo(auto)
    inv = _selecionar_inversor(auto)

    # Perdas da cadeia (calibradas com CSV PVSyst Memorial Rev03)
    # LID reduzido para TOPCon / HIT / bifaciais N-type (0.20% vs 1.74% pSi)
    tec = mod.get('tecnologia', '').lower()
    f_LID = 0.0020 if any(x in tec for x in ('bifacial', 'topcon', 'hit', 'hju')) \
            else PERDAS_PADRAO['f_LID']
    perdas = {**PERDAS_PADRAO, 'f_LID': f_LID}

    return dict(lat=lat,lon=lon,tz=tz,tilt=tilt,az=az,
                N_s=Ns, N_strings=Nstr,
                bifacial=bifacial,
                modo_dados=modo_dados, ano_dados=ano_dados,  # v2.2
                albedo=albedo, pitch=pitch, mod_height=modH,
                N_seg=Nseg, N_rays=Nrays,
                modulo=mod, inversor=inv, perdas=perdas)

# ═══════════════════════════════════════════════════════════════════════════
# PARTE 5 ── GERAÇÃO DO RELATÓRIO PDF (4 páginas estilo PVSyst)
# ═══════════════════════════════════════════════════════════════════════════

# ── Paleta de cores ─────────────────────────────────────────────────────────
C = dict(
    navy='#0D3B6E', blue='#1565C0', lblue='#1E88E5', sky='#E3F2FD',
    green='#2E7D32', lgreen='#E8F5E9', dgreen='#1B5E20',
    purple='#6A1B9A', lpurple='#F3E5F5',
    orange='#E65100', lorange='#FFF3E0',
    red='#C62828', lred='#FFEBEE',
    gold='#F57F17', lgold='#FFFDE7',
    gray='#455A64', lgray='#ECEFF1', dgray='#263238',
    white='#FFFFFF', bg='#F8FAFB',
)

def make_IV_chart(ax, Ns, Np, mod, inv):
    """Gráfico curvas I-V × limites (Aba 6 — Array Voltage Sizing)."""
    ax.set_facecolor('#FAFAFA')
    q=1.602e-19; kB=1.381e-23; T_ref=298.15; E_gap=1.12

    Voc_n10 = Ns*mod['Voc']*(1+mod['mu_Voc']/100*(-10-25))
    V_range  = np.linspace(50, Voc_n10*1.02, 250)

    colors_t = [(20,'#2E7D32','T=20°C','-'),
                (60,'#1565C0','T=60°C','--'),
                (-10,'#7B1FA2','T=-10°C',':')]

    for T, col, lbl, ls in colors_t:
        TcK = T+273.15
        Vt  = mod['N_cs']*mod['gamma']*kB*TcK/q
        I0  = mod['I0_ref']*(TcK/T_ref)**3*math.exp((q*E_gap)/(mod['gamma']*kB)*(1/T_ref-1/TcK))
        Iph = mod['Iph_ref']*(1+mod['mu_Isc']/100*(T-25))
        I_v = [Np*solve_IV(V/Ns, Iph, I0, mod['Rs'], mod['Rsh'], Vt) for V in V_range]
        ax.plot(V_range, I_v, color=col, lw=2.2, ls=ls, label=lbl, zorder=4)
        # Marcar ponto MPP
        Vmpp_T = Ns*mod['Vmpp']*(1+mod['mu_Voc']/100*(T-25))
        Impp_T = IV_string(Vmpp_T, T, Ns, Np, mod)
        ax.plot(Vmpp_T, Impp_T, 'o', color=col, ms=7, zorder=5)

    # Limites do inversor — linhas verticais
    ymax = Np*mod['Isc']*1.15
    for V_lim, ls_v in [(inv['V_mpp_min'],'--'),(inv['V_mpp_max'],':')]:
        ax.axvline(V_lim, color='#9C27B0', lw=1.5, ls=ls_v, alpha=0.9, zorder=3)
    # Labels das linhas de limite no rodapé (sem sobreposição com curvas)
    ax.text(inv['V_mpp_min']+12, ymax*0.05, f"V_mpp mín.\n{inv['V_mpp_min']}V",
            fontsize=7, color='#9C27B0', va='bottom', ha='left', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='#F3E5F5', edgecolor='#9C27B0', alpha=0.85))
    ax.text(inv['V_mpp_max']-12, ymax*0.05, f"V_abs máx.\n{inv['V_mpp_max']}V",
            fontsize=7, color='#9C27B0', va='bottom', ha='right', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='#F3E5F5', edgecolor='#9C27B0', alpha=0.85))

    # Valores numéricos de referência — setas escalonadas (sem sobreposição)
    Vmpp20 = Ns*mod['Vmpp']*(1+mod['mu_Voc']/100*(20-25))
    Vmpp60 = Ns*mod['Vmpp']*(1+mod['mu_Voc']/100*(60-25))
    Vco0   = Ns*mod['Voc']*(1+mod['mu_Voc']/100*(0-25))
    Impp20 = IV_string(Vmpp20, 20, Ns, Np, mod)
    Impp60 = IV_string(Vmpp60, 60, Ns, Np, mod)
    x_rng  = Ns*mod['Voc']*(1+mod['mu_Voc']/100*(-10-25))*1.02
    offset = x_rng * 0.09
    ax.annotate(f'Vmpp(20°C)\n{Vmpp20:.0f}V',
                xy=(Vmpp20, Impp20), xytext=(Vmpp20-offset, Impp20+ymax*0.12),
                arrowprops=dict(arrowstyle='->', color='#2E7D32', lw=1.2),
                fontsize=7.5, color='#2E7D32', ha='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#2E7D32', alpha=0.9))
    ax.annotate(f'Vmpp(60°C)\n{Vmpp60:.0f}V',
                xy=(Vmpp60, Impp60), xytext=(Vmpp60+offset, Impp60-ymax*0.14),
                arrowprops=dict(arrowstyle='->', color='#1565C0', lw=1.2),
                fontsize=7.5, color='#1565C0', ha='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#1565C0', alpha=0.9))
    ax.text(Vco0*0.98, Np*mod['Isc']*0.09, f'Vco(0°C)={Vco0:.0f}V',
            fontsize=7.5, color='#7B1FA2', ha='right',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='#F3E5F5', edgecolor='#9C27B0', alpha=0.85))

    ax.set_xlim(0, Voc_n10*1.05); ax.set_ylim(0, ymax)
    ax.set_xlabel('Tensão [V]', fontsize=9.5, color=C['gray'])
    ax.set_ylabel('Corrente [A]', fontsize=9.5, color=C['gray'])
    ax.set_title('Dimens. da tensão do grupo', fontsize=11, fontweight='bold', color=C['navy'])
    ax.legend(fontsize=8.5, loc='lower left', framealpha=0.95)
    ax.grid(True, alpha=0.25, color=C['lgray'])
    ax.tick_params(labelsize=8.5)

def make_histogram(ax, sys_r, P_nom_stc, P_nom_DC):
    """Histograma PVSyst — Aba 7 Power Distribution."""
    ax.set_facecolor('#FAFAFA')
    ctr    = np.array(sys_r['bins_ctr'])
    h_v    = np.array(sys_r['hist_verde'])/1000   # → MWh
    h_r    = np.array(sys_r['hist_roxa'])/1000
    bw     = (ctr[1]-ctr[0])*0.90 if len(ctr)>1 else 1.8

    ax.bar(ctr, h_v, width=bw, color=C['green'],  alpha=0.85, zorder=3,
           label='Energia do grupo no MPP')
    ax.bar(ctr, h_r, width=bw, color=C['purple'], alpha=0.85, zorder=4,
           label='Energia AC com limitação de potência')

    # Linhas de referência verticais
    ax.axvline(P_nom_DC,  color=C['purple'], lw=2, ls='--', zorder=5)
    ax.axvline(P_nom_stc, color=C['blue'],   lw=1.5, ls=':',  zorder=5)

    ymax = max(h_v.max(), 0.01)*1.20
    ax.annotate(f'Inversor\nPnom DC\n{P_nom_DC:.0f} kW',
                xy=(P_nom_DC, ymax*0.35), xytext=(P_nom_DC*0.82, ymax*0.68),
                arrowprops=dict(arrowstyle='->', color=C['purple'], lw=1.3),
                fontsize=8.5, color=C['purple'], ha='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3',facecolor=C['lpurple'],edgecolor=C['purple'],alpha=0.9))
    ax.annotate(f'Grupo\nPnom STC\n{P_nom_stc:.1f} kWp',
                xy=(P_nom_stc, ymax*0.15), xytext=(P_nom_stc*1.06, ymax*0.45),
                arrowprops=dict(arrowstyle='->', color=C['blue'], lw=1.3),
                fontsize=8.5, color=C['blue'], ha='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3',facecolor=C['sky'],edgecolor=C['blue'],alpha=0.9))

    ax.set_xlabel('Potência do grupo [kW]', fontsize=9.5, color=C['gray'])
    bw_label = f"{(ctr[1]-ctr[0]) if len(ctr)>1 else 2:.2g}"
    ax.set_ylabel(f'Energia [MWh / classe {bw_label} kW]', fontsize=9.5, color=C['gray'])
    ax.set_title('Dimensionamento da potência: Distribuição de saída do inversor',
                 fontsize=11, fontweight='bold', color=C['navy'], pad=7)
    ax.legend(fontsize=8.5, loc='upper left', framealpha=0.95)
    ax.grid(True, axis='y', alpha=0.25, color=C['lgray'])
    ax.set_xlim(-0.5, max(P_nom_stc*1.12, ctr[-1]+2))
    ax.set_ylim(0, ymax)
    ax.tick_params(labelsize=8.5)

    # Stats box inferior
    il_pct = sys_r['IL_pct']
    stats  = (f"IL_Pmax={sys_r['IL_tot']:.0f} kWh ({il_pct:.2f}%)  "
              f"  R_DC_AC={sys_r['R_DC_AC']:.3f}  "
              f"  {sys_r['N_horas_clip']} h/ano clipping")
    ax.text(0.01, 0.97, stats, transform=ax.transAxes, fontsize=7.5, va='top',
            bbox=dict(boxstyle='round', facecolor=C['lgold'], alpha=0.92, edgecolor=C['gold']))

def gerar_relatorio_pdf(inp, ft, sys_r, out_path):
    """Gera relatório PDF 4 páginas estilo PVSyst."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as RC
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle, HRFlowable,
                                     PageBreak, Image, KeepTogether)
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    import io as _io

    mod = inp['modulo']; inv = inp['inversor']
    Ns  = inp['N_s'];    Np  = inp['N_strings']
    P_STC  = sys_r['P_nom_stc']
    P_nomDC= sys_r['P_nom_DC']
    R_DC   = sys_r['R_DC_AC']

    # Cores ReportLab
    PN  = RC.HexColor('#0D3B6E')
    PB  = RC.HexColor('#1565C0')
    PLB = RC.HexColor('#E3F2FD')
    PG  = RC.HexColor('#2E7D32')
    PLG = RC.HexColor('#E8F5E9')
    PO  = RC.HexColor('#E65100')
    PLO = RC.HexColor('#FFF3E0')
    PR  = RC.HexColor('#C62828')
    PLR = RC.HexColor('#FFEBEE')
    PGD = RC.HexColor('#F57F17')
    PLG2= RC.HexColor('#FFFDE7')
    PGY = RC.HexColor('#455A64')
    PLG3= RC.HexColor('#F5F7FA')
    W   = RC.white; W_page = A4[0]-3.2*cm

    # Estilos
    H1 = ParagraphStyle('H1',fontName='Helvetica-Bold',fontSize=15,textColor=W,
                          alignment=1,backColor=PN,borderPad=10,spaceAfter=4)
    H2 = ParagraphStyle('H2',fontName='Helvetica-Bold',fontSize=12,textColor=W,
                          backColor=PB,borderPad=7,spaceBefore=8,spaceAfter=3)
    H3 = ParagraphStyle('H3',fontName='Helvetica-Bold',fontSize=10,textColor=W,
                          backColor=PN,borderPad=5,spaceBefore=5,spaceAfter=2)
    BD = ParagraphStyle('BD',fontName='Helvetica',fontSize=9,textColor=PGY,
                          spaceAfter=4,leading=13,alignment=TA_JUSTIFY)
    BB = ParagraphStyle('BB',fontName='Helvetica-Bold',fontSize=9,textColor=PGY,spaceAfter=3)
    NT = ParagraphStyle('NT',fontName='Helvetica-Oblique',fontSize=8,textColor=PGY,
                          spaceAfter=3,leading=11)

    def tbl(data, widths, extras=None):
        base = [('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),8.5),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),4),
                ('BOTTOMPADDING',(0,0),(-1,-1),4),('LEFTPADDING',(0,0),(-1,-1),5),
                ('RIGHTPADDING',(0,0),(-1,-1),5),
                ('GRID',(0,0),(-1,-1),0.4,RC.HexColor('#C5CAE9')),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[W,PLG3]),
                ('BACKGROUND',(0,0),(-1,0),PB),('TEXTCOLOR',(0,0),(-1,0),W),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')]
        if extras: base.extend(extras)
        t = Table(data, colWidths=widths); t.setStyle(TableStyle(base)); return t

    P_ = lambda t,s=BD: Paragraph(t,s)
    SP = lambda h=0.3: Spacer(1,h*cm)
    HR = lambda: HRFlowable(width='100%',thickness=1,color=PB,spaceAfter=6)

    # ── Gerar imagens intermediárias ─────────────────────────────────────
    import tempfile
    TMP = tempfile.gettempdir()
    matplotlib.rcParams.update({'figure.facecolor':'#F8FAFB','font.family':'DejaVu Sans'})

    # Fig 1: Curvas I-V × Limites (Aba 6)
    fig1, ax1 = plt.subplots(figsize=(8.5,5))
    make_IV_chart(ax1, Ns, Np, mod, inv)
    fig1.tight_layout(pad=1.5)
    p1 = os.path.join(TMP,'fig_iv.png')
    fig1.savefig(p1, dpi=130, bbox_inches='tight', facecolor=C['bg']); plt.close(fig1)

    # Fig 2: Histograma (Aba 7)
    fig2, ax2 = plt.subplots(figsize=(8.5,5))
    make_histogram(ax2, sys_r, P_STC, P_nomDC)
    fig2.tight_layout(pad=1.5)
    p2 = os.path.join(TMP,'fig_hist.png')
    fig2.savefig(p2, dpi=130, bbox_inches='tight', facecolor=C['bg']); plt.close(fig2)

    # Fig 3: GHI mensal + FT
    bifacial = inp.get('bifacial', True)
    fig3, (ax3a,ax3b) = plt.subplots(1,2,figsize=(12,5))
    fig3.patch.set_facecolor(C['bg'])
    x=np.arange(12); w=0.38
    nasa_m = [build_nasa_ghi(inp['lat'],inp['lon'])[i+1]*DAYS_PER_MONTH[i] for i in range(12)]
    motor_m = ft['monthly']['GHI']
    ax3a.set_facecolor('#FAFAFA')
    bars_nasa  = ax3a.bar(x-w/2, nasa_m,  w, label='NASA POWER', color='#1976D2', alpha=0.85)
    bars_motor = ax3a.bar(x+w/2, motor_m, w, label=f'Motor ({ft["GHI_anual"]:.0f} kWh/m²)', color='#42A5F5', alpha=0.85)
    for bar, val in zip(bars_motor, motor_m):
        ax3a.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1.5,
                  f'{val:.0f}', ha='center', va='bottom', fontsize=6.5, color=C['navy'])
    ax3a.set_xticks(x); ax3a.set_xticklabels(MONTH_NAMES, fontsize=8.5)
    ax3a.set_ylabel('kWh/m²/mês', fontsize=10); ax3a.grid(True, axis='y', alpha=0.3)
    ax3a.set_title('GHI Mensal', fontsize=11, fontweight='bold', color=C['navy'])
    ax3a.legend(fontsize=9); ax3a.tick_params(labelsize=8.5)
    ax3a.set_ylim(0, max(max(nasa_m), max(motor_m))*1.18)
    ax3b.set_facecolor('#FAFAFA')
    ghi_m=ft['monthly']['GHI']; gf_m=ft['monthly']['Gf']; gb_m=ft['monthly']['Gb']
    ftf_m=[f/g if g>0 else 0 for f,g in zip(gf_m,ghi_m)]
    ftb_m=[b/g if g>0 else 0 for b,g in zip(gb_m,ghi_m)]
    ax3b.plot(MONTH_NAMES, ftf_m, 'o-', color='#1565C0', lw=2.2, ms=7,
              label=f"FT frontal={ft['FT_frontal']:.4f}")
    if bifacial:
        ax3b.plot(MONTH_NAMES, ftb_m, 's-', color='#2E7D32', lw=2.2, ms=7,
                  label=f"FT bifacial={ft['FT_bifacial']:.4f}")
        ganho_txt   = f"Ganho bifacial = {ft['ganho_bif_pct']:+.2f}%"
        ganho_color = C['gold']
    else:
        ganho_txt   = "Modo MONOFACIAL — sem ganho bifacial"
        ganho_color = '#C62828'
    ax3b.set_ylabel('FT = G_tilt / GHI', fontsize=10); ax3b.grid(True, alpha=0.3)
    ax3b.set_title('Fator de Transposição Mensal', fontsize=11, fontweight='bold', color=C['navy'])
    ax3b.legend(fontsize=9, loc='lower center')
    ax3b.tick_params(labelsize=8.5, axis='x', rotation=30)
    ax3b.text(0.5, 0.97, ganho_txt, transform=ax3b.transAxes, ha='center',
              fontsize=9, color=ganho_color, fontweight='bold',
              bbox=dict(boxstyle='round', facecolor=C['lgold'], alpha=0.9))
    fig3.tight_layout(pad=1.8)
    p3 = os.path.join(TMP,'fig_ghi.png')
    fig3.savefig(p3, dpi=140, bbox_inches='tight', facecolor=C['bg']); plt.close(fig3)

    # Fig 5: Produção mensal E_Grid
    monthly_kwh = sys_r.get('monthly_grid', [0.0]*12)
    monthly_mwh = [v/1000 for v in monthly_kwh]
    colors_prod = ['#1565C0' if v >= sum(monthly_mwh)/12 else '#42A5F5' for v in monthly_mwh]
    fig5, ax5 = plt.subplots(figsize=(11,3.8))
    fig5.patch.set_facecolor(C['bg']); ax5.set_facecolor('#FAFAFA')
    bars5 = ax5.bar(MONTH_NAMES, monthly_mwh, color=colors_prod, alpha=0.88, edgecolor='white', lw=0.8, zorder=3)
    for bar, val in zip(bars5, monthly_mwh):
        ax5.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.02,
                 f'{val:.1f}', ha='center', va='bottom', fontsize=8.5, color=C['navy'], fontweight='bold')
    media = sum(monthly_mwh)/12
    ax5.axhline(media, color=C['orange'], lw=1.5, ls='--', alpha=0.8, zorder=4,
                label=f'Média mensal: {media:.1f} MWh')
    ax5.set_ylabel('Energia gerada [MWh/mês]', fontsize=10)
    ax5.set_title(f'Produção Mensal Estimada — E_Grid = {sys_r["E_grid_tot"]/1000:.1f} MWh/ano  |  PR={sys_r["PR"]:.1f}%  |  Yf={sys_r["Yf"]:.0f} kWh/kWp',
                  fontsize=10, fontweight='bold', color=C['navy'])
    ax5.legend(fontsize=9); ax5.grid(True, axis='y', alpha=0.3, zorder=0)
    ax5.set_ylim(0, max(monthly_mwh)*1.22); ax5.tick_params(labelsize=9)
    fig5.tight_layout(pad=1.5)
    p5 = os.path.join(TMP, 'fig_prod.png')
    fig5.savefig(p5, dpi=140, bbox_inches='tight', facecolor=C['bg']); plt.close(fig5)

    # Fig 4: Loss Diagram simplificado
    fig4, ax4 = plt.subplots(figsize=(10,7))
    fig4.patch.set_facecolor(C['bg']); ax4.set_facecolor('#FAFAFA'); ax4.axis('off')
    ax4.set_xlim(0,10); ax4.set_ylim(0,12)
    ax4.set_title('Loss Diagram — Cadeia de Perdas PVSyst', fontsize=12,
                   fontweight='bold', color=C['navy'], pad=10)

    # Cascata de perdas — v2.1: adapta ao modo bifacial/monofacial
    E_nom   = sys_r['E_mpp_tot']
    E_arr   = sys_r['E_array_tot']
    E_grid  = sys_r['E_grid_tot']
    G_tilt  = ft['Gtilt_frontal']
    G_bif   = ft['Gtilt_bifacial']
    bifacial = inp.get('bifacial', True)
    phi_ef   = ft.get('phi_efetivo', mod['phi'] if bifacial else 0.0)

    perds = inp['perdas']
    if bifacial:
        bif_label = f"Global efetivo bifacial (+φ×G_rear)  φ={phi_ef:.2f}"
        bif_color = '#2E7D32'
        bif_delta = f"+{ft['ganho_bif_pct']:.2f}%  G_rear RT"
    else:
        bif_label = "MONOFACIAL — G_rear=0, G_bif=G_front (sem ganho traseiro)"
        bif_color = '#C62828'
        bif_delta = "+0.00%  (monofacial)"

    blocks = [
        (f"{ft['GHI_anual']:.0f} kWh/m²",    "Global horizontal (GHI)",                '#1565C0'),
        (f"{G_tilt:.0f} kWh/m²",              f"+{(ft['FT_frontal']-1)*100:.1f}%  Global incid. plano coletores", '#1976D2'),
        (f"-{perds['f_shad']*100:.1f}%",       "Near Shadings: perda irradiância",       '#E57373'),
        (f"-{perds['f_soil']*100:.1f}%",        "Soiling loss factor",                   '#EF9A9A'),
        (f"-{perds['f_IAM']*100:.1f}%",         "IAM factor on global",                  '#EF9A9A'),
        (f"{G_bif:.0f} kWh/m²",               bif_label,                               bif_color),
        (f"{E_nom/1000:.2f} MWh",             f"Array nominal energy (η_STC={mod['eta']:.1f}%)", '#2E7D32'),
        (f"-{perds['f_temp']*100:.1f}%",       "PV loss due to temperature",             '#FF7043'),
        (f"-{perds['f_LID']*100:.2f}%",        "LID — degradação induzida",              '#FF8A65'),
        (f"-{perds['f_mis']*100:.1f}%",        "Mismatch loss, modules/strings",         '#FF5722'),
        (f"-{perds['f_ohm']*100:.2f}%",        "Ohmic wiring loss",                      '#FF7043'),
        (f"{E_arr/1000:.2f} MWh",             "Array virtual energy at MPP",             '#1B5E20'),
        (f"-{sys_r['IL_pct']:.2f}%",           "Inverter Loss over nominal power (IL_Pmax)", '#7B1FA2'),
        (f"-{sys_r['InvLoss_pct']:.1f}%",      "Inverter Loss during operation",         '#9C27B0'),
        (f"{E_grid/1000:.2f} MWh",            "Energy injected into grid",               '#0D3B6E'),
    ]

    for i,(val,lbl,col) in enumerate(blocks):
        y = 11.0 - i*0.76
        is_total = 'MWh' in val or 'kWh/m²' in val
        bg_col = col if is_total else '#FFEBEE'
        txt_col = 'white' if is_total else col
        fw = 'bold' if is_total else 'normal'
        width_bar = 2.2 if is_total else 1.4
        ax4.add_patch(FancyBboxPatch((0.1,y-0.28),width_bar,0.52,
                      boxstyle='round,pad=0.03',facecolor=bg_col,edgecolor=col,lw=1,alpha=0.9))
        ax4.text(0.1+width_bar/2, y, val, ha='center', va='center',
                 fontsize=8.5, color=txt_col, fontweight=fw)
        ax4.text(width_bar+0.25, y, lbl, ha='left', va='center',
                 fontsize=8.5, color=C['gray'])

    fig4.tight_layout(pad=1.5)
    p4 = os.path.join(TMP,'fig_loss.png')
    fig4.savefig(p4, dpi=130, bbox_inches='tight', facecolor=C['bg']); plt.close(fig4)

    # ── Construir PDF ─────────────────────────────────────────────────────
    doc = SimpleDocTemplate(out_path, pagesize=A4,
                             leftMargin=1.6*cm, rightMargin=1.6*cm,
                             topMargin=1.8*cm, bottomMargin=1.8*cm,
                             title='Relatório PVSyst — Motor Unificado v2.0')
    story = []

    # ═══ PÁGINA 1 — CAPA + RESUMO ═══════════════════════════════════════
    story += [SP(0.6), P_('RELATÓRIO DE DIMENSIONAMENTO SOLAR FOTOVOLTAICO', H1), SP(0.2)]
    story += [P_('Array / Inverter Sizing Conditions  |  Loss Diagram  |  Performance Analysis',
                  ParagraphStyle('sub',fontName='Helvetica',fontSize=11,textColor=PB,
                                  alignment=1,spaceAfter=6)), SP(0.4)]

    # v2.1 — modo bifacial/monofacial
    bifacial = inp.get('bifacial', True)
    phi_ef   = ft.get('phi_efetivo', mod['phi'] if bifacial else 0.0)
    modo_bif_str = (f"BIFACIAL  |  φ={phi_ef:.2f}  |  G_rear={ft['G_rear_rt']:.1f} kWh/m²/ano"
                    if bifacial else
                    "MONOFACIAL  |  φ=0  |  G_rear=0 (Ray-Tracing desativado)")

    capa = [
        ['Campo','Especificação'],
        ['Módulo FV', f"{mod['fabricante']} {mod['modelo']}  ({mod['tecnologia']})"],
        ['Inversor',  f"{inv['fabricante']} {inv['modelo']}  —  {inv['P_nomAC']:.0f} kW AC"],
        ['Localização', f"LAT={inp['lat']}° | LON={inp['lon']}° | UTC{inp['tz']:+d}"],
        ['Orientação', f"Inclinação={inp['tilt']}° | Azimute={inp['az']}°"],
        ['Configuração string', f"N_s={Ns} módulos em série  ×  N_str={Np} strings"],
        ['Nr. de módulos', f"{Ns*Np}  |  Superfície={Ns*Np*mod['A_mod']:.1f} m²"],
        ['Potência Grupo STC', f"{P_STC:.2f} kWp"],
        ['Potência AC nominal', f"{inv['P_nomAC']:.0f} kWAC"],
        ['PnomDC = PnomAC/eta', f"{P_nomDC:.2f} kWDC"],
        ['Rácio Pnom (DC/AC)', f"{R_DC:.3f}  ({'OK < 1.25' if R_DC<=1.25 else 'Verificar'})"],
        ['▶ Modo de irradiância', modo_bif_str],
        ['GHI anual (motor)', f"{ft['GHI_anual']:.1f} kWh/m²/ano  (NASA POWER)"],
        ['FT frontal (motor)', f"{ft['FT_frontal']:.4f}"],
    ]
    if bifacial:
        capa += [
            ['G_rear ray-tracing', f"{ft['G_rear_rt']:.1f} kWh/m²/ano  (φ={phi_ef:.2f})"],
            ['FT bifacial', f"{ft['FT_bifacial']:.4f}  |  Ganho={ft['ganho_bif_pct']:+.2f}%"],
        ]
    else:
        capa += [
            ['G_rear ray-tracing', "0 kWh/m²/ano  (MONOFACIAL — desativado)"],
            ['FT efetivo (= FT frontal)', f"{ft['FT_frontal']:.4f}  |  sem ganho bifacial"],
        ]
    capa += [
        ['E_Grid estimada', f"{sys_r['E_grid_tot']:.0f} kWh/ano"],
        ['PR (Performance Ratio)', f"{sys_r['PR']:.1f}%"],
        ['IL_Pmax (sobrecarga)', f"{sys_r['IL_tot']:.0f} kWh  ({sys_r['IL_pct']:.2f}%)"],
        ['Data do relatório', time.strftime('%d/%m/%Y %H:%M')],
    ]
    capa_table = tbl(capa, [5*cm, W_page-5*cm],
                     [('BACKGROUND',(0,12),(-1,12), PG if bifacial else PR),
                      ('TEXTCOLOR',(0,12),(-1,12), W),
                      ('FONTNAME',(0,12),(-1,12),'Helvetica-Bold')])
    story += [capa_table, SP(0.4)]
    story += [P_('Produção Mensal Estimada', H3), SP(0.1)]
    story += [Image(p5, width=W_page, height=6*cm), SP(0.3)]
    story += [P_('⚠  Esta perda por sobrecarga é uma estimativa baseada no histograma de '
                  'distribuição de potência. Os valores definitivos serão os resultados '
                  'da simulação horária completa.', NT)]

    # ═══ PÁGINA 2 — ABA 6: VOLTAGE SIZING + HISTOGRAMA (ABA 7) ══════════
    story += [PageBreak()]
    story += [P_('1. CONDIÇÕES DE DIMENSIONAMENTO GRUPO / INVERSOR', H2), SP(0.15), HR()]
    story += [P_('1.1 Dimensionamento da Tensão do Grupo', H3), SP(0.1)]
    story += [P_('Curvas I-V do array (Modelo 1-Diodo, Shockley/Beckman) em 3 temperaturas críticas. '
                  'Pontos marcados = V_mpp na temperatura correspondente. '
                  'As linhas verticais definem a janela MPPT do inversor.', BD)]
    story += [Image(p1, width=14.5*cm, height=8.8*cm), SP(0.2)]

    # Tabela Dimensionamento da Potência
    Vmpp60 = round(Ns*mod['Vmpp']*(1+mod['mu_Voc']/100*(60-25)),0)
    Vmpp20 = round(Ns*mod['Vmpp']*(1+mod['mu_Voc']/100*(20-25)),0)
    Vco0   = round(Ns*mod['Voc']*(1+mod['mu_Voc']/100*(0-25)),0)
    Pmax_DC= round(Ns*Np*mod['Pmpp']/1000*(1110/1000)*(1+mod['mu_Pmpp']/100*(60-25)),1)

    pwr = [['Grandeza','Valor','Limite / Fórmula','Status'],
           ['Vmpp (60°C)', f'{Vmpp60:.0f} V', f'>= {inv["V_mpp_min"]} V',
            'OK' if Vmpp60>=inv['V_mpp_min'] else 'ERRO'],
           ['Vmpp (20°C)', f'{Vmpp20:.0f} V', f'[{inv["V_mpp_min"]}; {inv["V_mpp_max"]}] V',
            'OK' if inv['V_mpp_min']<=Vmpp20<=inv['V_mpp_max'] else 'ERRO'],
           ['Vco (0°C)',   f'{Vco0:.0f} V',   f'< {inv["V_dc_max"]} V',
            'OK' if Vco0<inv['V_dc_max'] else 'ERRO'],
           ['Impp / MPPT', f'{round(Np*mod["Impp"],1)} A',
            f'< {inv["I_max_mppt"]} A' if inv['I_max_mppt']>0 else 'N/D (IDCMax=0 no .OND)',
            'OK' if (inv['I_max_mppt']>0 and Np*mod['Impp']<inv['I_max_mppt']) else ('' if inv['I_max_mppt']==0 else 'ERRO')],
           ['Isc / MPPT',  f'{round(Np*mod["Isc"],1)} A',
            f'< {inv["I_sc_mppt"]} A' if inv['I_sc_mppt']>0 else 'N/D (não no .OND)',
            'OK' if (inv['I_sc_mppt']>0 and Np*mod['Isc']<inv['I_sc_mppt']) else ('' if inv['I_sc_mppt']==0 else 'ERRO')],
           ['Grupo FV, Pnom STC',    f'{P_STC:.2f} kWp',    'N_s×N_str×Pmpp/1000',''],
           ['Grupo FV, Pmax (G,T)',  f'{Pmax_DC:.2f} kWDC', 'G=1110W/m², T_c=60°C',''],
           ['Inversores, Pnom AC',   f'{inv["P_nomAC"]:.0f} kW','Datasheet',''],
           ['PnomDC = PnomAC/eta',   f'{P_nomDC:.2f} kW',   f'={inv["P_nomAC"]}/{inv["eta_max"]/100:.4f}',''],
           ['Perdas sobrecarga',      f'{sys_r["IL_tot"]:.0f} kWh = {sys_r["IL_pct"]:.2f}%',
            'Σ max(P_MPP-P_nomDC,0)×1h',''],
           ['Rácio Pnom Grupo/Inv.',  f'{R_DC:.3f}',         'P_STC/P_nomAC',
            'IDEAL' if R_DC<=1.25 else ('ACEITAR' if R_DC<=1.30 else 'ATENÇÃO')]]

    extras_pwr=[('BACKGROUND',(3,i),(3,i),PLG if row[3]=='OK' or row[3]=='IDEAL'
                  else (PLO if row[3] in ['ACEITAR',''] else PLR))
                 for i,row in enumerate(pwr[1:],1)]
    story += [tbl(pwr,[5.5*cm,3.5*cm,4*cm,W_page-13*cm],extras_pwr), SP(0.3)]

    # ═══ PÁGINA 3 — HISTOGRAMA (ABA 7) ════════════════════════════════
    story += [PageBreak()]
    story += [P_('2. DIMENSIONAMENTO DA POTÊNCIA: DISTRIBUIÇÃO DE SAÍDA DO INVERSOR', H2),
              SP(0.15), HR()]
    story += [P_('O histograma abaixo reproduz a Aba 7 do Memorial PVSyst. '
                  'Eixo X = P_arr MPP potencial (0 → P_STC). '
                  '<b>Verde</b> = EArrPmpp (energia potencial do array). '
                  '<b>Roxo</b> = energia real com limitação de P_nomDC. '
                  'A área entre as curvas = IL_Pmax (perda por sobrecarga).', BD)]
    story += [Image(p2, width=14.5*cm, height=8*cm), SP(0.2)]

    # Tabela do histograma compacta — filtra bins < 0.5% para caber na página
    ctr_a  = np.array(sys_r['bins_ctr'])
    hv_a   = np.array(sys_r['hist_verde'])/1000
    hr_a   = np.array(sys_r['hist_roxa'])/1000
    hil_a  = np.array(sys_r['hist_IL'])/1000
    total_v= hv_a.sum()
    thresh  = total_v * 0.005  # 0.5% do total

    hist_rows = [['P_bin (kW)','E_MPP (MWh)','E_CA (MWh)','IL_Pmax (MWh)','% E_MPP']]
    outros_v = outros_r = outros_il = 0.0
    for i in range(len(ctr_a)):
        if hv_a[i] >= thresh:
            hist_rows.append([f'{ctr_a[i]:.0f}', f'{hv_a[i]:.3f}', f'{hr_a[i]:.3f}',
                               f'{hil_a[i]:.3f}', f'{hv_a[i]/total_v*100:.1f}%'])
        elif hv_a[i] > 0.0001:
            outros_v += hv_a[i]; outros_r += hr_a[i]; outros_il += hil_a[i]
    if outros_v > 0:
        hist_rows.append([f'< {thresh/total_v*100:.1f}%', f'{outros_v:.3f}', f'{outros_r:.3f}',
                          f'{outros_il:.3f}', f'{outros_v/total_v*100:.1f}%'])
    hist_rows.append(['TOTAL', f'{hv_a.sum():.2f}', f'{hr_a.sum():.2f}',
                      f'{hil_a.sum():.2f}', '100.0%'])

    base_h = [('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),8),
              ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),2),
              ('BOTTOMPADDING',(0,0),(-1,-1),2),('LEFTPADDING',(0,0),(-1,-1),4),
              ('RIGHTPADDING',(0,0),(-1,-1),4),
              ('GRID',(0,0),(-1,-1),0.3,RC.HexColor('#C5CAE9')),
              ('ROWBACKGROUNDS',(0,1),(-1,-1),[W,PLG3]),
              ('BACKGROUND',(0,0),(-1,0),PB),('TEXTCOLOR',(0,0),(-1,0),W),
              ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')]
    ext_h = [('BACKGROUND',(0,i),(-1,i),PLR)
              for i,row in enumerate(hist_rows[1:-1],1) if float(row[3])>0.0001]
    ext_h += [('BACKGROUND',(0,-1),(-1,-1),PN),
              ('TEXTCOLOR',(0,-1),(-1,-1),W),
              ('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold')]
    t_hist = Table(hist_rows, colWidths=[2.5*cm,3*cm,3*cm,3.5*cm,W_page-12*cm])
    t_hist.setStyle(TableStyle(base_h + ext_h))
    story += [t_hist]

    # ═══ PÁGINA 4 — MOTOR FT + PERFORMANCE + LOSS DIAGRAM ══════════════
    story += [PageBreak()]
    fonte_pdf = ft.get('fonte_dados', 'NASA POWER').upper()
    story += [P_(f'3. RESULTADOS DO MOTOR FT ({fonte_pdf})', H2),
              SP(0.15), HR()]
    story += [Image(p3, width=W_page, height=6.5*cm), SP(0.2)]

    ft_rows = [['Grandeza','Valor','Unidade','Descrição'],
               ['GHI anual',        f'{ft["GHI_anual"]:.1f}', 'kWh/m²','NASA POWER calibrado'],
               ['G_tilt frontal',   f'{ft["Gtilt_frontal"]:.1f}','kWh/m²','Modelo Hay + Erbs + CPR'],
               ['FT frontal',       f'{ft["FT_frontal"]:.4f}','—','G_front/GHI'],
               ['G_rear (RT)',
                f'{ft["G_rear_rt"]:.1f}' if bifacial else '0.0',
                'kWh/m²',
                'Ray-Tracing 2D multi-bounce' if bifacial else 'MONOFACIAL — desativado'],
               ['φ (bifacialidade)',
                f'{phi_ef:.2f}' if bifacial else '0.00  (desativado)',
                '—',
                f'φ={phi_ef:.2f}: datasheet módulo' if bifacial else 'Modo monofacial selecionado'],
               ['G_tilt bifacial / efetivo',
                f'{ft["Gtilt_bifacial"]:.1f}' if bifacial else f'{ft["Gtilt_frontal"]:.1f}',
                'kWh/m²',
                'G_front + φ×G_rear' if bifacial else 'G_front (= G_tilt frontal)'],
               ['FT efetivo',
                f'{ft["FT_bifacial"]:.4f}' if bifacial else f'{ft["FT_frontal"]:.4f}',
                '—', 'G_bif/GHI' if bifacial else 'G_front/GHI (monofacial)'],
               ['Ganho bifacial',
                f'{ft["ganho_bif_pct"]:+.2f}' if bifacial else '0.00',
                '%', 'FTb/FTf − 1' if bifacial else '— Não aplicável (monofacial)'],
               ['Horas com sol',    f'{ft["horas_sol"]}','h/ano','G > 1 W/m², HSun > 2°'],
               ['Tempo de cálculo', f'{ft["tempo_calc_s"]:.1f}','s',
                f'N_seg={inp["N_seg"]}, N_rays={inp["N_rays"]}' if bifacial else 'Ray-Tracing desativado (rápido)']]
    # Destacar a linha do ganho bifacial
    color_bif = PLG if bifacial else PLR
    extra_ft  = [('BACKGROUND',(0,8),(-1,8), color_bif)]
    story += [tbl(ft_rows,[4.5*cm,3*cm,2.5*cm,W_page-10*cm], extra_ft), SP(0.3)]

    story += [P_('4. PERFORMANCE DO SISTEMA', H2), SP(0.15), HR()]
    perf = [['Indicador','Valor','Referência','Status'],
            ['E_MPP potencial',   f'{sys_r["E_mpp_tot"]:.0f} kWh/ano','—','—'],
            ['E_Array real (DC)', f'{sys_r["E_array_tot"]:.0f} kWh/ano','—','—'],
            ['E_Grid (AC rede)',  f'{sys_r["E_grid_tot"]:.0f} kWh/ano','—','—'],
            ['PR (Perf. Ratio)',  f'{sys_r["PR"]:.1f}%','75-82% SP',
             'OK' if sys_r['PR']>=65 else 'BAIXO'],
            ['Yf (Yield final)',  f'{sys_r["Yf"]:.0f} kWh/kWp/ano','1300-1700','—'],
            ['Ya (Yield array)',  f'{sys_r["Ya"]:.0f} kWh/kWp/ano','—','—'],
            ['IL_Pmax',          f'{sys_r["IL_tot"]:.0f} kWh = {sys_r["IL_pct"]:.2f}%','< 3%',
             'OK' if sys_r['IL_pct']<3 else 'REVISAR'],
            ['InvLoss total',    f'{sys_r["InvLoss_tot"]:.0f} kWh = {sys_r["InvLoss_pct"]:.1f}%','—','—'],
            ['Horas clipping',   f'{sys_r["N_horas_clip"]} h/ano','—','—'],
            ['R_DC_AC',          f'{R_DC:.3f}','1.0–1.30',
             'IDEAL' if R_DC<=1.25 else ('OK' if R_DC<=1.30 else 'ATENÇÃO')]]

    ext_p = [('BACKGROUND',(3,i),(3,i),PLG if 'OK' in str(row[3]) or 'IDEAL' in str(row[3])
               else (PLR if 'BAIXO' in str(row[3]) or 'ATENÇÃO' in str(row[3]) else PLG3))
              for i,row in enumerate(perf[1:],1)]
    story += [tbl(perf,[5.5*cm,4*cm,3*cm,W_page-12.5*cm],ext_p), SP(0.3)]

    story += [P_('5. LOSS DIAGRAM — Cadeia de Perdas', H2), SP(0.15), HR()]
    story += [Image(p4, width=14.5*cm, height=10*cm), SP(0.2)]

    # Tabela de perdas resumida — v2.1: diferencia bifacial/monofacial
    bif_row_lbl = f"G_bif bifacial (φ={phi_ef:.2f})" if bifacial else "G_eff monofacial (φ=0)"
    bif_row_val = f'+{ft["ganho_bif_pct"]:.2f}%' if bifacial else '0.00%'
    bif_row_g   = f'{ft["Gtilt_bifacial"]:.1f} kWh/m²' if bifacial else f'{ft["Gtilt_frontal"]:.1f} kWh/m²'
    bif_row_note= f'G_front+φ×G_rear  Ganho: {ft["ganho_bif_pct"]:+.2f}%' if bifacial else 'Sem irradiância traseira'

    loss_rows = [['Etapa','Fator','Valor','% / Nota'],
                 ['G_tilt frontal (FT)',  f'+{(ft["FT_frontal"]-1)*100:.1f}%',
                  f'{ft["Gtilt_frontal"]:.1f} kWh/m²','Sobre GHI'],
                 [bif_row_lbl, bif_row_val, bif_row_g, bif_row_note],
                 ['Perdas ópticas (IAM+Soil+Shad)',
                  f'-{(inp["perdas"]["f_IAM"]+inp["perdas"]["f_soil"]+inp["perdas"]["f_shad"])*100:.1f}%',
                  '—','Sobre G_tilt'],
                 ['Temperatura (TempLss)',f'-{inp["perdas"]["f_temp"]*100:.2f}%','—','Modelo 1-Diodo'],
                 ['LID',                  f'-{inp["perdas"]["f_LID"]*100:.2f}%','—','TOPCon N-type'],
                 ['Mismatch',             f'-{inp["perdas"]["f_mis"]*100:.1f}%','—','Strings desbal.'],
                 ['Ôhmicas DC',           f'-{inp["perdas"]["f_ohm"]*100:.2f}%','—','Cabos DC'],
                 ['E_Array real',         '—',f'{sys_r["E_array_tot"]:.0f} kWh','—'],
                 ['IL_Pmax (clipping)',   f'-{sys_r["IL_pct"]:.2f}%',
                  f'{sys_r["IL_tot"]:.0f} kWh','Sobre E_Array'],
                 ['IL_Oper (eficiência)', f'-{sys_r["InvLoss_pct"]:.1f}%',
                  f'{sys_r["InvLoss_tot"]:.0f} kWh','Sobre E_Array'],
                 ['E_Grid (AC rede)',     '—',f'{sys_r["E_grid_tot"]:.0f} kWh','PR='+str(sys_r["PR"])+'%']]
    # Destacar linha bifacial/monofacial com verde (ganho) ou vermelho (zero/mono)
    loss_bif_color = PLG if bifacial else PLR
    extra_loss = [('BACKGROUND',(0,2),(-1,2), loss_bif_color),
                  ('FONTNAME',(0,2),(-1,2),'Helvetica-Bold')]
    story += [tbl(loss_rows,[5*cm,3*cm,4*cm,W_page-12*cm], extra_loss), SP(0.3)]

    # Rodapé
    modo_pdf = "BIFACIAL (Ray-Tracing 2D ativo)" if bifacial else "MONOFACIAL (Ray-Tracing desativado)"
    story += [HR()]
    story += [P_(f'Motor PVSyst Unificado v2.3  |  Modo: {modo_pdf}  |  '
                  f'ft_anual.py (Hay+Erbs+RT 2D) × Memorial_Dimensionamento_PVSyst_v2 Rev03  |  '
                  f'Gerado em {time.strftime("%d/%m/%Y %H:%M")}', NT)]
    story += [P_('Ref.: NASA POWER/SSE | Hay 1980 | Erbs 1982 | Marion et al. 2017 (NREL) | '
                  'Berrian et al. 2019 | Beckman & Duffie 1991 | PVSyst 8.0 | '
                  'CS7N-730TB-AG Datasheet v1.91 | CSI-250K-T8001A-E Datasheet v1.5', NT)]

    doc.build(story)
    print(f"\n  ✅ Relatório: {out_path}")

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    auto = '--auto' in sys.argv or '-a' in sys.argv
    mono = '--mono' in sys.argv
    print("\n"+"═"*60)
    print("  MOTOR PVSYST UNIFICADO v2.3")
    print("  ft_anual.py + Memorial_PVSyst_Rev03 → PDF")
    print("  Leitura .PAN/.OND | NASA POWER horário | Ray-Tracing 2D | PDF profissional")
    print("="*60)

    inp = get_inputs(auto=auto)
    mod = inp['modulo']; inv = inp['inversor']
    bifacial = inp.get('bifacial', True)
    modo_str = "BIFACIAL (φ=%.2f, Ray-Tracing 2D)" % mod['phi'] if bifacial else "MONOFACIAL (φ=0, Ray-Tracing OFF)"

    print("\n─"*60)
    pts = inp['N_seg']*inp['N_rays'] if bifacial else 0
    print(f"  PASSO 1/3 — Integração anual | Modo: {modo_str}")
    if bifacial:
        print(f"  Precisão: {pts} pts/hora (N_seg={inp['N_seg']}, N_rays={inp['N_rays']})")
    else:
        print("  Ray-Tracing desativado — cálculo mais rápido")
    print("─"*60)
    ft = integrar_anual(
        lat=inp['lat'], lon=inp['lon'], tz=inp['tz'],
        tilt=inp['tilt'], az_panel=inp['az'],
        albedo=inp['albedo'], phi=mod['phi'],
        pitch=inp['pitch'], mod_height=inp['mod_height'],
        N_seg=inp['N_seg'], N_rays=inp['N_rays'],
        verbose=True, bifacial=bifacial,
        modo_dados=inp.get('modo_dados', 'climatologia'),
        ano=inp.get('ano_dados'))                  # ← v2.2

    print("\n─"*60)
    print("  PASSO 2/3 — Cálculo do sistema + histograma")
    print("─"*60)
    sys_r = calc_system_hourly(ft, dict(
        modulo=mod, inversor=inv,
        N_s=inp['N_s'], N_strings=inp['N_strings'],
        perdas=inp['perdas'],
    ))
    print(f"  Modo         = {modo_str}")
    print(f"  P_nom STC    = {sys_r['P_nom_stc']:.2f} kWp")
    print(f"  E_Grid       = {sys_r['E_grid_tot']:.0f} kWh/ano")
    print(f"  PR           = {sys_r['PR']:.1f}%")
    print(f"  Yf           = {sys_r['Yf']:.0f} kWh/kWp")
    print(f"  IL_Pmax      = {sys_r['IL_tot']:.0f} kWh = {sys_r['IL_pct']:.2f}%")
    print(f"  R_DC_AC      = {sys_r['R_DC_AC']:.3f}")
    if bifacial:
        print(f"  G_rear RT    = {ft['G_rear_rt']:.1f} kWh/m²/ano")
        print(f"  Ganho bif.   = {ft['ganho_bif_pct']:+.2f}%")

    print("\n─"*60)
    print("  PASSO 3/3 — Gerando relatório PDF estilo PVSyst")
    print("─"*60)
    sufixo = "BIFACIAL" if bifacial else "MONOFACIAL"
    nome   = f"Relatorio_PVSyst_{sufixo}_{time.strftime('%Y%m%d_%H%M')}.pdf"
    out_pdf= os.path.join(os.path.dirname(os.path.abspath(__file__)), nome)
    gerar_relatorio_pdf(inp, ft, sys_r, out_pdf)

    # Salvar JSON
    out_json = out_pdf.replace('.pdf','.json')
    with open(out_json,'w') as f:
        json.dump(dict(
            inputs  ={k:v for k,v in inp.items() if k not in ('modulo','inversor','perdas')},
            modulo  ={k:v for k,v in mod.items() if not isinstance(v,float) or abs(v)<1e4},
            inversor=inv,
            ft_result  ={k:v for k,v in ft.items()    if k!='hourly'},
            sys_result ={k:v for k,v in sys_r.items() if k!='hours'},
        ), f, indent=2)
    print(f"  ✅ JSON: {out_json}")

    return out_pdf

if __name__ == '__main__':
    out = main()
    print(f"\n{'═'*60}")
    print(f"  Relatório final: {out}")
    print(f"{'═'*60}\n")
