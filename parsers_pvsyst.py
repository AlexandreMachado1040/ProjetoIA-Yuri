"""
Parsers para arquivos .PAN (módulos FV) e .OND (inversores) no formato PVSyst.
Extrai parâmetros e mapeia para o formato interno do motor_pvsyst_unificado.
"""

import os
import re
import math
import glob

# Constantes físicas
kB   = 8.617333e-5    # eV/K (kB/q em V/K)
T_REF = 298.15        # K (25 °C)
E_GAP = 1.121         # eV (gap do Si a 300 K)


# ─────────────────────────────────────────────────────────────────
#  Utilitários internos
# ─────────────────────────────────────────────────────────────────

def _parse_key_value(filepath):
    """Lê arquivo PVSyst e retorna dict {chave: valor_str}."""
    kv = {}
    with open(filepath, 'r', encoding='latin-1') as f:
        for line in f:
            line = line.strip()
            if '=' not in line:
                continue
            if line.startswith(('PVObject_', 'End ', 'Str_', 'Point_',
                                 'OperPoints', 'ProfilP', 'IAMProfile')):
                continue
            key, _, val = line.partition('=')
            key = key.strip()
            val = val.strip()
            if key and val:
                kv[key] = val
    return kv


def _flt(kv, key, default=0.0):
    try:
        return float(kv.get(key, default))
    except (ValueError, TypeError):
        return default


def _int(kv, key, default=0):
    try:
        return int(float(kv.get(key, default)))
    except (ValueError, TypeError):
        return default


def _parse_profil_curves(filepath):
    """
    Extrai curvas ProfilPIOV1/V2/V3 do arquivo .OND.
    Retorna dict {'V1': [(Pin_W, Pout_W), ...], 'V2': [...], 'V3': [...]}.
    """
    curves = {}
    with open(filepath, 'r', encoding='latin-1') as f:
        content = f.read()

    for idx in ('1', '2', '3'):
        pattern = rf'ProfilPIOV{idx}=TCubicProfile(.*?)End of TCubicProfile'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            continue
        block = match.group(1)
        points = []
        for m in re.finditer(r'Point_\d+=(-?\d+\.?\d*),(-?\d+\.?\d*)', block):
            pin, pout = float(m.group(1)), float(m.group(2))
            if pin > 0 and pout > 0:
                points.append((pin, pout))
        if points:
            curves[f'V{idx}'] = sorted(points, key=lambda x: x[0])

    # Fallback: curva sem índice (ProfilPIO)
    if not curves:
        match = re.search(r'ProfilPIO=TCubicProfile(.*?)End of TCubicProfile', content, re.DOTALL)
        if match:
            block = match.group(1)
            points = []
            for m in re.finditer(r'Point_\d+=(-?\d+\.?\d*),(-?\d+\.?\d*)', block):
                pin, pout = float(m.group(1)), float(m.group(2))
                if pin > 0 and pout > 0:
                    points.append((pin, pout))
            if points:
                curves['V2'] = sorted(points, key=lambda x: x[0])

    return curves


_TECNOL_MAP = {
    'mtSiMono':    'Mono-Si',
    'mtSiPoly':    'Poli-Si',
    'mtCIGS':      'CIGS',
    'mtCdTe':      'CdTe',
    'mtAmorphous': 'a-Si',
    'mtHIT':       'HIT',
}


# ─────────────────────────────────────────────────────────────────
#  Parser de módulo (.PAN)
# ─────────────────────────────────────────────────────────────────

def parse_pan(filepath):
    """
    Lê arquivo .PAN (PVSyst módulo FV) e retorna dict `mod`
    compatível com motor_pvsyst_unificado.
    """
    kv = _parse_key_value(filepath)

    # Parâmetros STC
    PNom  = _flt(kv, 'PNom',  700.0)
    Isc   = _flt(kv, 'Isc',   18.5)
    Voc   = _flt(kv, 'Voc',   48.0)
    Imp   = _flt(kv, 'Imp',   17.5)
    Vmp   = _flt(kv, 'Vmp',   40.0)

    # Coeficientes de temperatura (unidades PVSyst)
    muISC     = _flt(kv, 'muISC',     9.0)     # mA/°C absoluto
    muVocSpec = _flt(kv, 'muVocSpec', -120.0)  # mV/°C absoluto
    muPmpReq  = _flt(kv, 'muPmpReq', -0.29)   # %/°C (já relativo)

    # Modelo 1-diodo
    RSerie  = _flt(kv, 'RSerie',  0.135)
    RShunt  = _flt(kv, 'RShunt',  200.0)
    Gamma   = _flt(kv, 'Gamma',   1.05)

    # Bifacialidade
    BifFac = _flt(kv, 'BifacialityFactor', 0.0)

    # Células
    NCelS = _int(kv, 'NCelS', 66)
    NCelP = _int(kv, 'NCelP', 2)
    N_cs  = NCelS * NCelP

    # Dimensões
    Width  = _flt(kv, 'Width',  1.303)
    Height = _flt(kv, 'Height', 2.384)
    A_mod  = Width * Height

    # Info comercial
    modelo     = kv.get('Model',        os.path.splitext(os.path.basename(filepath))[0])
    fabricante = kv.get('Manufacturer', 'N/A')
    tec_raw    = kv.get('Technol',      'mtSiMono')
    base_tec   = _TECNOL_MAP.get(tec_raw, tec_raw)
    tecnologia = f'{base_tec} bifacial (φ={BifFac:.2f})' if BifFac > 0 else base_tec

    # Conversão de coeficientes para %/°C (formato interno do motor)
    mu_Isc  = muISC     / 1000.0 / Isc * 100.0   if Isc  > 0 else 0.05
    mu_Voc  = muVocSpec / 1000.0 / Voc * 100.0   if Voc  > 0 else -0.25
    mu_Pmpp = muPmpReq                             # já em %/°C

    # Eficiência STC
    eta = PNom / (A_mod * 1000.0) * 100.0 if A_mod > 0 else 0.0

    # Modelo 1-diodo — derivação dos parâmetros de referência (STC)
    #   Vt_ref = N_cs × Gamma × kB × T_REF  [V]
    Vt_ref  = N_cs * Gamma * kB * T_REF
    #   Iph_ref ≈ Isc (corrente de fótons na STC)
    Iph_ref = Isc + RSerie * Isc / RShunt  # correção de 2ª ordem
    #   I0_ref da condição de circuito aberto: 0 = Iph - I0*exp(Voc/Vt) - Voc/Rsh
    denom   = math.exp(min(Voc / Vt_ref, 500))
    I0_ref  = max((Iph_ref - Voc / RShunt) / denom, 1e-15)

    return dict(
        modelo=modelo,
        fabricante=fabricante,
        tecnologia=tecnologia,
        Pmpp=PNom,
        Vmpp=Vmp,
        Voc=Voc,
        Impp=Imp,
        Isc=Isc,
        mu_Pmpp=round(mu_Pmpp, 4),
        mu_Voc=round(mu_Voc,  4),
        mu_Isc=round(mu_Isc,  4),
        NOCT=41.0,          # não consta no .PAN; valor típico bifacial vidro-vidro
        phi=BifFac,
        N_cs=N_cs,
        eta=round(eta, 2),
        A_mod=round(A_mod, 6),
        gamma=Gamma,
        I0_ref=I0_ref,
        Iph_ref=round(Iph_ref, 4),
        Rs=RSerie,
        Rsh=RShunt,
    )


# ─────────────────────────────────────────────────────────────────
#  Parser de inversor (.OND)
# ─────────────────────────────────────────────────────────────────

def parse_ond(filepath):
    """
    Lê arquivo .OND (PVSyst inversor) e retorna dict `inv`
    compatível com motor_pvsyst_unificado.
    """
    kv = _parse_key_value(filepath)

    PNomConv = _flt(kv, 'PNomConv', 50.0)
    PMaxOUT  = _flt(kv, 'PMaxOUT',  PNomConv * 1.1)
    VMppMin  = _flt(kv, 'VMppMin',  200.0)
    VMPPMax  = _flt(kv, 'VMPPMax',  1000.0)
    VmppNom  = _flt(kv, 'VmppNom',  600.0)
    VAbsMax  = _flt(kv, 'VAbsMax',  VMPPMax)

    # Eficiências — preferência para EfficMaxV (por tensão); fallback EfficMax
    EfficMax  = _flt(kv, 'EfficMax',  0.0)
    EfficEuro = _flt(kv, 'EfficEuro', 0.0)

    for raw_key, dest in [('EfficMaxV', None), ('EfficEuroV', None)]:
        raw = kv.get(raw_key, '')
        if raw:
            vals = [float(x) for x in raw.rstrip(',').split(',') if x.strip()]
            if vals:
                if raw_key == 'EfficMaxV':
                    EfficMax = max(vals)
                else:
                    EfficEuro = max(vals)

    # Correntes
    IMaxDC  = _flt(kv, 'IMaxDC',  0.0)
    INomAC  = _flt(kv, 'INomAC',  0.0)
    IMaxAC  = _flt(kv, 'IMaxAC',  INomAC)

    # Configuração MPPT
    NbMPPT   = _int(kv, 'NbMPPT',  1)
    NbInputs = _int(kv, 'NbInputs', NbMPPT)

    # Derating por temperatura
    TPNom  = _flt(kv, 'TPNom',  50.0)
    TPLim1 = _flt(kv, 'TPLim1', 60.0)
    PLim1  = _flt(kv, 'PLim1',  PNomConv)

    Night_Loss = _flt(kv, 'Night_Loss', 5.0)
    PSeuil     = _flt(kv, 'PSeuil',     0.0)

    # Info comercial
    modelo     = kv.get('Model',        os.path.splitext(os.path.basename(filepath))[0])
    fabricante = kv.get('Manufacturer', 'N/A')

    # Curvas de eficiência reais (ProfilPIOV1/V2/V3)
    profil_curves = _parse_profil_curves(filepath)

    derate_T = {
        -30: 100, 0: 100, 25: 100,
        int(TPNom): 100,
        int(TPLim1): round(PLim1 / PNomConv * 100, 1) if PNomConv > 0 else 100,
    }

    I_max_mppt = round(IMaxDC / NbMPPT, 1) if (NbMPPT > 0 and IMaxDC > 0) else 0.0

    return dict(
        modelo=modelo,
        fabricante=fabricante,
        P_nomAC=PNomConv,
        P_maxAC=PMaxOUT,
        eta_max=EfficMax,
        eta_euro=EfficEuro,
        V_dc_max=VAbsMax,
        V_mpp_min=VMppMin,
        V_mpp_max=VMPPMax,
        V_start=VMppMin + 50,
        V_nom=VmppNom,
        N_mppt=NbMPPT,
        N_str_max=NbInputs,
        I_max_mppt=I_max_mppt,
        I_sc_mppt=0,
        night_loss_W=Night_Loss,
        pstart_W=PSeuil,
        derate_T=derate_T,
        profil_curves=profil_curves,
    )


# ─────────────────────────────────────────────────────────────────
#  Listagens para a UI
# ─────────────────────────────────────────────────────────────────

def listar_modulos(pasta):
    """
    Retorna lista de (filepath, modelo, Pmpp_Wp, BifFac)
    ordenada por Pmpp crescente. Sem duplicatas.
    """
    resultado = []
    vistos = set()
    padroes = [os.path.join(pasta, '*.PAN'), os.path.join(pasta, '*.pan')]
    arquivos = []
    for padrao in padroes:
        arquivos += glob.glob(padrao)
    for fp in arquivos:
        chave = os.path.normcase(os.path.abspath(fp))
        if chave in vistos:
            continue
        vistos.add(chave)
        try:
            kv = _parse_key_value(fp)
            modelo = kv.get('Model', os.path.splitext(os.path.basename(fp))[0])
            Pmpp   = _flt(kv, 'PNom',  0.0)
            phi    = _flt(kv, 'BifacialityFactor', 0.0)
            resultado.append((fp, modelo, Pmpp, phi))
        except Exception:
            pass
    return sorted(resultado, key=lambda x: x[2])


def listar_inversores(pasta):
    """
    Retorna lista de (filepath, modelo, PNom_kW, eta_max_pct, NbMPPT)
    ordenada por PNom crescente. Sem duplicatas.
    """
    resultado = []
    vistos = set()
    padroes = [os.path.join(pasta, '*.OND'), os.path.join(pasta, '*.ond')]
    arquivos = []
    for padrao in padroes:
        arquivos += glob.glob(padrao)
    # Exclui .Fav e deduplica
    for fp in arquivos:
        if fp.lower().endswith('.fav'):
            continue
        chave = os.path.normcase(os.path.abspath(fp))
        if chave in vistos:
            continue
        vistos.add(chave)
        try:
            kv = _parse_key_value(fp)
            modelo  = kv.get('Model', os.path.splitext(os.path.basename(fp))[0])
            PNom    = _flt(kv, 'PNomConv', 0.0)
            NbMPPT  = _int(kv, 'NbMPPT',  1)
            eta_max = _flt(kv, 'EfficMax', 0.0)
            raw = kv.get('EfficMaxV', '')
            if raw:
                vals = [float(x) for x in raw.rstrip(',').split(',') if x.strip()]
                if vals:
                    eta_max = max(vals)
            resultado.append((fp, modelo, PNom, eta_max, NbMPPT))
        except Exception:
            pass
    return sorted(resultado, key=lambda x: x[2])
