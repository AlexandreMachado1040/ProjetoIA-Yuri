# -*- coding: utf-8 -*-
"""
Pipeline offline SONDA → TGY (Typical GHI Year) — rede completa.

Metodologia (mesma família da ferramenta TMY do PVSyst 7):
  1. Descobre nas páginas das estações (est_*.html) o código e os anos com
     ZIP anual de dados solarimétricos (resolução 1 min, fuso UTC).
  2. Baixa os anos (cache local), aplica controle de qualidade
     (código 3333 = ausente; faixas físicas) e agrega 1 min → horário
     em hora local da estação.
  3. Para cada mês do calendário, escolhe o mês real mais representativo
     pela estatística de Finkelstein-Schafer (FS) sobre os totais diários
     de GHI (variante TGY — peso na global). QC com relaxamento progressivo
     (80% → 60% → 50% de dias válidos) para meses com poucos candidatos.
  4. Exporta um JSON por estação (8.760 h de GHI/DNI/DHI em Wh/m²) +
     registro frontend/src/data/sonda_estacoes.json para o ConfigForm.

Uso:   python sonda_tgy_pipeline.py            # rede completa
       python sonda_tgy_pipeline.py BRB PTR    # só estações citadas
Saída: frontend/public/sonda/{CODIGO}_TGY.json

Licença dos dados: SONDA/INPE — CC BY 4.0 (sonda.ccst.inpe.br).
Este script roda localmente; nada disso vai para o Worker.
"""

import json
import os
import re
import sys
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta

# ── Configuração ────────────────────────────────────────────────────────────
URL_SITE  = 'https://sonda.ccst.inpe.br'
DIR_RAW   = os.path.join(os.path.dirname(__file__), 'sonda_dados', 'raw')
DIR_SAIDA = os.path.join(os.path.dirname(__file__),
                         'frontend', 'public', 'sonda')
ARQ_REGISTRO = os.path.join(os.path.dirname(__file__),
                            'frontend', 'src', 'data', 'sonda_estacoes.json')

# Páginas das estações → (nome de exibição, fuso UTC local).
# O código (sigla) e as coordenadas vêm dos próprios dados.
PAGINAS = {
    'est_brasilia.html':      ('Brasília-DF', -3),
    'est_cachoeira.html':     ('Cachoeira Paulista-SP', -3),
    'est_caico.html':         ('Caicó-RN', -3),
    'est_campogrande.html':   ('Campo Grande-MS (Fazenda)', -4),
    'est_cguniderp.html':     ('Campo Grande-MS (UNIDERP)', -4),
    'est_cmourao.html':       ('Campo Mourão-PR', -3),
    'est_cuiaba.html':        ('Cuiabá-MT', -4),
    'est_curitiba.html':      ('Curitiba-PR (TECPAR)', -3),
    'est_utfpr.html':         ('Curitiba-PR (UTFPR)', -3),
    'est_florianopolis.html': ('Florianópolis-SC (BSRN)', -3),
    'est_sapiens.html':       ('Florianópolis-SC (Sapiens Park)', -3),
    'est_joinville.html':     ('Joinville-SC', -3),
    'est_medianeira.html':    ('Medianeira-PR', -3),
    'est_natal.html':         ('Natal-RN', -3),
    'est_ourinhos.html':      ('Ourinhos-SP', -3),
    'est_palmas.html':        ('Palmas-TO', -3),
    'est_petrolina.html':     ('Petrolina-PE', -3),
    'est_santarem.html':      ('Santarém-PA', -3),
    'est_saoluiz.html':       ('São Luís-MA', -3),
    'est_saomartinho.html':   ('São Martinho da Serra-RS', -3),
    'est_sombrio.html':       ('Sombrio-SC', -3),
}

MIN_ANOS  = 3     # mínimo de anos completos para montar um TGY decente
MAX_ANOS  = 8     # usa no máximo os N anos mais recentes (limita download)

COD_AUSENTE   = 3333.0
MIN_VALIDOS_H = 30                    # minutos válidos para fechar a hora
NIVEIS_QC     = (0.80, 0.60, 0.50)    # fração de dias válidos (relaxamento)
DIAS_MES      = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

FAIXAS = {'ghi': (-15.0, 1700.0), 'dni': (-50.0, 1500.0), 'dhi': (-15.0, 1000.0)}


# ── 1. Descoberta das estações e anos disponíveis ───────────────────────────
RE_ZIP_ANO = re.compile(
    r'dados/solarimetricos/([A-Z0-9]+)/(\d{4})/\1_\2_SD\.zip')


def descobrir_estacoes():
    """Varre as páginas das estações e devolve
    [{sigla, nome, tz, anos:[...]}, ...] com anos completos disponíveis."""
    estacoes = []
    for pagina, (nome, tz) in PAGINAS.items():
        url = f'{URL_SITE}/{pagina}'
        try:
            html = urllib.request.urlopen(url, timeout=30).read().decode(
                'utf-8', errors='replace')
        except Exception as e:
            print(f'  {nome}: falha ao ler página ({e}) — pulada', flush=True)
            continue
        achados = RE_ZIP_ANO.findall(html)
        if not achados:
            print(f'  {nome}: sem ZIPs anuais — pulada', flush=True)
            continue
        sigla = achados[0][0]
        anos  = sorted({int(a) for _, a in achados})[-MAX_ANOS:]
        if len(anos) < MIN_ANOS:
            print(f'  {nome} ({sigla}): só {len(anos)} ano(s) — pulada',
                  flush=True)
            continue
        estacoes.append({'sigla': sigla, 'nome': nome, 'tz': tz, 'anos': anos})
        print(f'  {nome} ({sigla}): anos {anos}', flush=True)
    return estacoes


# ── 2. Download (com cache local) ───────────────────────────────────────────
def baixar_ano(sigla: str, ano: int) -> str | None:
    os.makedirs(DIR_RAW, exist_ok=True)
    destino = os.path.join(DIR_RAW, f'{sigla}_{ano}_SD.zip')
    if os.path.exists(destino) and os.path.getsize(destino) > 10_000:
        return destino
    url = f'{URL_SITE}/dados/solarimetricos/{sigla}/{ano}/{sigla}_{ano}_SD.zip'
    try:
        urllib.request.urlretrieve(url, destino)
    except Exception as e:
        print(f'    {sigla} {ano}: falha no download ({e})', flush=True)
        if os.path.exists(destino):
            os.remove(destino)
        return None
    return destino


# ── 3. Parsing + agregação horária ──────────────────────────────────────────
RE_COORD = re.compile(r'lat:\s*(-?\d+\.?\d*).*?lon:\s*(-?\d+\.?\d*)'
                      r'.*?alt:\s*(-?\d+\.?\d*)', re.S)


def processar_ano(caminho_zip: str, sigla: str, tz: int, meta: dict):
    """Devolve {date_local: {hora: {'ghi','dni','dhi'}}} (médias W/m²).
    Preenche meta['lat'/'lon'/'alt'] a partir do cabeçalho do .dat."""
    # acumulador: chave (ordinal_do_dia, hora) → [s_ghi,n_ghi,s_dni,n_dni,s_dhi,n_dhi]
    acc = defaultdict(lambda: [0.0, 0, 0.0, 0, 0.0, 0])
    lo_g, hi_g = FAIXAS['ghi']
    lo_n, hi_n = FAIXAS['dni']
    lo_d, hi_d = FAIXAS['dhi']
    cache_ord = {}

    with zipfile.ZipFile(caminho_zip) as z:
        for nome in z.namelist():
            if not nome.lower().endswith('.dat'):
                continue
            with z.open(nome) as fh:
                cab = fh.readline().decode('utf-8', errors='replace')
                if 'lat' not in meta:
                    m = RE_COORD.search(cab)
                    if m:
                        meta['lat'] = float(m.group(1))
                        meta['lon'] = float(m.group(2))
                        meta['alt'] = float(m.group(3))
                for bruta in fh:
                    linha = bruta.decode('ascii', errors='replace')
                    p = linha.split(',', 8)
                    if len(p) < 8 or p[1] != sigla:
                        continue
                    ts = p[0]
                    dia_str = ts[:10]
                    ordinal = cache_ord.get(dia_str)
                    if ordinal is None:
                        try:
                            ordinal = date(int(ts[0:4]), int(ts[5:7]),
                                           int(ts[8:10])).toordinal()
                        except ValueError:
                            continue
                        cache_ord[dia_str] = ordinal
                    try:
                        hora = int(ts[11:13])
                        ghi  = float(p[5])
                        dni  = float(p[6])
                        dhi  = float(p[7])
                    except ValueError:
                        continue
                    # UTC → hora local da estação
                    h_loc = hora + tz
                    o_loc = ordinal
                    if h_loc < 0:
                        h_loc += 24
                        o_loc -= 1
                    elif h_loc > 23:
                        h_loc -= 24
                        o_loc += 1
                    a = acc[(o_loc, h_loc)]
                    if ghi != COD_AUSENTE and lo_g <= ghi <= hi_g:
                        a[0] += ghi if ghi > 0.0 else 0.0
                        a[1] += 1
                    if dni != COD_AUSENTE and lo_n <= dni <= hi_n:
                        a[2] += dni if dni > 0.0 else 0.0
                        a[3] += 1
                    if dhi != COD_AUSENTE and lo_d <= dhi <= hi_d:
                        a[4] += dhi if dhi > 0.0 else 0.0
                        a[5] += 1

    horario = defaultdict(dict)
    for (o, h), a in acc.items():
        if a[1] < MIN_VALIDOS_H:
            continue
        horario[date.fromordinal(o)][h] = {
            'ghi': a[0] / a[1],
            'dni': a[2] / a[3] if a[3] >= MIN_VALIDOS_H else None,
            'dhi': a[4] / a[5] if a[5] >= MIN_VALIDOS_H else None,
        }
    return dict(horario)


def dia_valido(reg_horas: dict) -> bool:
    """Dia válido: todas as horas de 6h às 18h locais presentes e total plausível."""
    if any(h not in reg_horas for h in range(6, 19)):
        return False
    total_kwh = sum(v['ghi'] for v in reg_horas.values()) / 1000.0
    return 0.3 <= total_kwh <= 9.5


# ── 4. Estatística de Finkelstein-Schafer ───────────────────────────────────
def cdf_empirica(valores):
    v = sorted(valores)
    n = len(v)
    return lambda x: sum(1 for u in v if u <= x) / n


def fs_estatistica(diarios_candidato, diarios_longo_prazo) -> float:
    cdf_lp   = cdf_empirica(diarios_longo_prazo)
    cdf_cand = cdf_empirica(diarios_candidato)
    return sum(abs(cdf_lp(x) - cdf_cand(x)) for x in diarios_candidato) \
        / len(diarios_candidato)


# ── 5. Montagem do TGY de uma estação ───────────────────────────────────────
def montar_tgy(est: dict, dados_por_ano: dict, meta: dict):
    """Devolve o dict do TGY ou None (estação sem dados suficientes)."""
    anos = sorted(dados_por_ano.keys())
    diarios = defaultdict(dict)          # (ano, mes) -> {dia: total_kwh}
    for ano, dias in dados_por_ano.items():
        for d, horas in dias.items():
            if d.year == ano and dia_valido(horas):
                diarios[(ano, d.month)][d.day] = \
                    sum(v['ghi'] for v in horas.values()) / 1000.0

    meses_saida, anos_usados, fs_valores = [], {}, {}
    ghi_mensal, dni_mensal, dhi_mensal   = {}, {}, {}
    qc_relaxado = {}

    for mes in range(1, 13):
        n_dias = DIAS_MES[mes - 1]
        candidatos, nivel_usado = [], None
        for nivel in NIVEIS_QC:
            candidatos = [a for a in anos
                          if len(diarios.get((a, mes), {})) >= nivel * n_dias]
            if candidatos:
                nivel_usado = nivel
                break
        if not candidatos:
            print(f'    mês {mes:02d}: sem candidatos — estação descartada',
                  flush=True)
            return None
        if nivel_usado < NIVEIS_QC[0]:
            qc_relaxado[mes] = nivel_usado

        longo_prazo = [t for a in candidatos
                       for t in diarios[(a, mes)].values()]
        melhor = min(candidatos,
                     key=lambda a: fs_estatistica(
                         list(diarios[(a, mes)].values()), longo_prazo))
        anos_usados[mes] = melhor
        fs_valores[mes]  = round(fs_estatistica(
            list(diarios[(melhor, mes)].values()), longo_prazo), 4)

        # Perfil médio horário do mês escolhido (preenche lacunas)
        perfil = [[] for _ in range(24)]
        dias_mes = {d: h for d, h in dados_por_ano[melhor].items()
                    if d.month == mes and d.year == melhor}
        for d, horas in dias_mes.items():
            for h, v in horas.items():
                perfil[h].append(v)
        perfil_medio = []
        for h in range(24):
            if perfil[h]:
                perfil_medio.append({
                    k: (sum(x[k] for x in perfil[h] if x[k] is not None)
                        / max(1, sum(1 for x in perfil[h] if x[k] is not None)))
                    for k in ('ghi', 'dni', 'dhi')})
            else:
                perfil_medio.append({'ghi': 0.0, 'dni': 0.0, 'dhi': 0.0})

        dias_json, preenchidos = [], 0
        for nd in range(1, n_dias + 1):
            d = date(melhor, mes, nd)
            horas = dados_por_ano[melhor].get(d, {})
            ghi_l, dni_l, dhi_l = [], [], []
            for h in range(24):
                v = horas.get(h)
                if v is None:
                    v = perfil_medio[h]
                    preenchidos += 1
                ghi_l.append(int(round(v['ghi'])))
                dni_l.append(int(round(v['dni'] if v['dni'] is not None
                                       else perfil_medio[h]['dni'] or 0)))
                dhi_l.append(int(round(v['dhi'] if v['dhi'] is not None
                                       else perfil_medio[h]['dhi'] or 0)))
            dias_json.append({'ghi': ghi_l, 'dni': dni_l, 'dhi': dhi_l})

        ghi_mensal[mes] = round(sum(sum(d['ghi']) for d in dias_json)
                                / n_dias / 1000.0, 3)
        dni_mensal[mes] = round(sum(sum(d['dni']) for d in dias_json)
                                / n_dias / 1000.0, 3)
        dhi_mensal[mes] = round(sum(sum(d['dhi']) for d in dias_json)
                                / n_dias / 1000.0, 3)
        meses_saida.append({'mes': mes, 'ano': melhor,
                            'horas_preenchidas': preenchidos,
                            'dias': dias_json})

    ghi_anual = round(sum(ghi_mensal[m] * DIAS_MES[m - 1]
                          for m in range(1, 13)), 1)
    print(f'    TGY ok — GHI anual {ghi_anual} kWh/m² | anos usados '
          f'{sorted(set(anos_usados.values()))}'
          + (f' | QC relaxado nos meses {sorted(qc_relaxado)}'
             if qc_relaxado else ''), flush=True)

    return {
        'estacao':    est['sigla'],
        'nome':       est['nome'],
        'lat':        meta.get('lat'),
        'lon':        meta.get('lon'),
        'alt_m':      meta.get('alt'),
        'tz':         est['tz'],
        'fonte':      'SONDA/INPE — sonda.ccst.inpe.br',
        'licenca':    'CC BY 4.0',
        'metodologia': 'TGY — Finkelstein-Schafer sobre totais diários de GHI '
                       '(variante TGY da ferramenta TMY do PVSyst 7)',
        'anos_disponiveis': est['anos'],
        'anos_usados': anos_usados,
        'fs':          fs_valores,
        'qc_relaxado': qc_relaxado,
        'gerado_em':   datetime.now().strftime('%d/%m/%Y'),
        'unidade':     f'Wh/m² por hora (média horária em hora local '
                       f'UTC{est["tz"]:+d})',
        'ghi_anual_kwh': ghi_anual,
        # Médias mensais (kWh/m²/dia) prontas para o nasa_data do motor;
        # t2m fica com a NASA POWER (as estações não medem ou não exportamos).
        'ghi_mensal_kwh_dia': ghi_mensal,
        'dni_mensal_kwh_dia': dni_mensal,
        'dhi_mensal_kwh_dia': dhi_mensal,
        'meses':       meses_saida,
    }


# ── Execução ────────────────────────────────────────────────────────────────
def main():
    filtro = {s.upper() for s in sys.argv[1:]}

    print('1/3 — Descobrindo estações e anos disponíveis:', flush=True)
    estacoes = descobrir_estacoes()
    if filtro:
        estacoes = [e for e in estacoes if e['sigla'] in filtro]

    print(f'\n2/3 — Processando {len(estacoes)} estações:', flush=True)
    for est in estacoes:
        sigla = est['sigla']
        print(f'  == {est["nome"]} ({sigla}) ==', flush=True)
        dados, meta = {}, {}
        for ano in est['anos']:
            caminho = baixar_ano(sigla, ano)
            if caminho is None:
                continue
            try:
                dados[ano] = processar_ano(caminho, sigla, est['tz'], meta)
            except zipfile.BadZipFile:
                print(f'    {ano}: ZIP corrompido — ignorado', flush=True)
                continue
            n_validos = sum(1 for h in dados[ano].values() if dia_valido(h))
            print(f'    {ano}: {len(dados[ano])} dias, {n_validos} válidos',
                  flush=True)
        if len(dados) < MIN_ANOS or 'lat' not in meta:
            print(f'    {sigla}: dados insuficientes — descartada', flush=True)
            continue

        tgy = montar_tgy(est, dados, meta)
        if tgy is None:
            continue

        os.makedirs(DIR_SAIDA, exist_ok=True)
        arq = os.path.join(DIR_SAIDA, f'{sigla}_TGY.json')
        with open(arq, 'w', encoding='utf-8') as f:
            json.dump(tgy, f, ensure_ascii=False, separators=(',', ':'))

    # Registro reconstruído de TODOS os TGYs presentes no diretório de saída
    # (execuções parciais/interrompidas não perdem estações já processadas).
    registro = []
    for arq in sorted(os.listdir(DIR_SAIDA)):
        if not arq.endswith('_TGY.json'):
            continue
        with open(os.path.join(DIR_SAIDA, arq), encoding='utf-8') as f:
            t = json.load(f)
        registro.append({
            'sigla': t['estacao'], 'nome': t['nome'],
            'lat': t['lat'], 'lon': t['lon'],
            'arquivo': f'/sonda/{t["estacao"]}_TGY.json',
            'ghi_anual_kwh': t.get('ghi_anual_kwh'),
        })

    print(f'\n3/3 — Registro com {len(registro)} estações:', flush=True)
    registro.sort(key=lambda e: e['nome'])
    os.makedirs(os.path.dirname(ARQ_REGISTRO), exist_ok=True)
    with open(ARQ_REGISTRO, 'w', encoding='utf-8') as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)
    for e in registro:
        print(f'  {e["sigla"]:4s} {e["nome"]:35s} '
              f'GHI {e["ghi_anual_kwh"]:7.1f} kWh/m²/ano', flush=True)
    print(f'\nRegistro gravado em {ARQ_REGISTRO}', flush=True)


if __name__ == '__main__':
    main()
