# -*- coding: utf-8 -*-
"""
Pipeline offline SONDA → TGY (Typical GHI Year) — estação BRB (Brasília-DF).

Metodologia (mesma família da ferramenta TMY do PVSyst 7):
  1. Baixa os anos disponíveis de dados solarimétricos da estação
     (ZIP por ano, resolução de 1 minuto, fuso UTC).
  2. Aplica controle de qualidade (código 3333 = ausente; faixas físicas)
     e agrega 1 minuto → horário em hora local (UTC-3).
  3. Para cada mês do calendário, escolhe o mês real mais representativo
     do histórico pela estatística de Finkelstein-Schafer (FS) sobre a
     distribuição dos totais diários de GHI (variante TGY — peso na global).
  4. Exporta JSON compacto com as 8.760 horas (GHI/DNI/DHI em Wh/m²)
     + médias mensais prontas para o motor (nasa_data).

Uso:  python sonda_tgy_pipeline.py
Saída: frontend/public/sonda/BRB_TGY.json

Licença dos dados: SONDA/INPE — CC BY 4.0 (sonda.ccst.inpe.br).
Este script roda localmente; nada disso vai para o Worker.
"""

import io
import json
import math
import os
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta

# ── Configuração ────────────────────────────────────────────────────────────
ESTACAO = {
    'sigla': 'BRB', 'nome': 'Brasília-DF',
    'lat': -15.601, 'lon': -47.713, 'alt': 1023.0, 'tz': -3,
}
# Anos com cobertura anual razoável (2004/2005/2010 têm só meses isolados)
ANOS = [2011, 2012, 2013, 2014, 2015, 2018]

URL_BASE  = 'https://sonda.ccst.inpe.br/dados/solarimetricos/BRB'
DIR_RAW   = os.path.join(os.path.dirname(__file__), 'sonda_dados', 'raw')
ARQ_SAIDA = os.path.join(os.path.dirname(__file__),
                         'frontend', 'public', 'sonda', 'BRB_TGY.json')

COD_AUSENTE   = 3333.0      # código SONDA de dado ausente
MIN_VALIDOS_H = 30          # mínimo de minutos válidos para fechar a hora
FRAC_DIAS_MES = 0.80        # mínimo de dias válidos para o mês ser candidato
DIAS_MES      = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# Faixas físicas (W/m²) — fora disso o minuto é descartado
FAIXAS = {'ghi': (-15.0, 1600.0), 'dni': (-50.0, 1500.0), 'dhi': (-15.0, 900.0)}


# ── 1. Download (com cache local) ───────────────────────────────────────────
def baixar_ano(ano: int) -> str:
    os.makedirs(DIR_RAW, exist_ok=True)
    destino = os.path.join(DIR_RAW, f'BRB_{ano}_SD.zip')
    if os.path.exists(destino) and os.path.getsize(destino) > 10_000:
        print(f'  {ano}: cache ({os.path.getsize(destino)//1024} kB)')
        return destino
    url = f'{URL_BASE}/{ano}/BRB_{ano}_SD.zip'
    print(f'  {ano}: baixando {url} ...')
    urllib.request.urlretrieve(url, destino)
    print(f'  {ano}: ok ({os.path.getsize(destino)//1024} kB)')
    return destino


# ── 2. Parsing + agregação horária ──────────────────────────────────────────
def processar_ano(caminho_zip: str):
    """Devolve {data_local: {hora: {'ghi': v, 'dni': v, 'dhi': v}}} (médias W/m²)."""
    soma = defaultdict(lambda: defaultdict(lambda: {'ghi': [0.0, 0],
                                                    'dni': [0.0, 0],
                                                    'dhi': [0.0, 0]}))
    desloc = timedelta(hours=ESTACAO['tz'])
    with zipfile.ZipFile(caminho_zip) as z:
        for nome in z.namelist():
            if not nome.lower().endswith('.dat'):
                continue
            with z.open(nome) as fh:
                texto = io.TextIOWrapper(fh, encoding='utf-8', errors='replace')
                for linha in texto:
                    c = linha.split(',')
                    if len(c) < 8 or c[1] != 'BRB':
                        continue
                    try:
                        ts = datetime.strptime(c[0], '%Y-%m-%d %H:%M:%S')
                        vals = (float(c[5]), float(c[6]), float(c[7]))
                    except ValueError:
                        continue
                    ts_local = ts + desloc
                    chave    = (ts_local.date(), ts_local.hour)
                    for nome_v, v in zip(('ghi', 'dni', 'dhi'), vals):
                        lo, hi = FAIXAS[nome_v]
                        if v == COD_AUSENTE or not (lo <= v <= hi):
                            continue
                        acc = soma[chave[0]][chave[1]][nome_v]
                        acc[0] += max(v, 0.0)   # offsets noturnos negativos → 0
                        acc[1] += 1

    horario = {}
    for dia, horas in soma.items():
        reg = {}
        for h, comp in horas.items():
            ghi_s, ghi_n = comp['ghi']
            if ghi_n < MIN_VALIDOS_H:
                continue                        # hora inválida (GHI é o mínimo)
            reg[h] = {
                'ghi': ghi_s / ghi_n,
                'dni': comp['dni'][0] / comp['dni'][1] if comp['dni'][1] >= MIN_VALIDOS_H else None,
                'dhi': comp['dhi'][0] / comp['dhi'][1] if comp['dhi'][1] >= MIN_VALIDOS_H else None,
            }
        if reg:
            horario[dia] = reg
    return horario


def dia_valido(reg_horas: dict) -> bool:
    """Dia válido: todas as horas de 6h às 18h locais presentes e total plausível."""
    if any(h not in reg_horas for h in range(6, 19)):
        return False
    total_kwh = sum(v['ghi'] for v in reg_horas.values()) / 1000.0
    return 0.3 <= total_kwh <= 9.5


# ── 3. Estatística de Finkelstein-Schafer ───────────────────────────────────
def cdf_empirica(valores):
    v = sorted(valores)
    n = len(v)
    return lambda x: sum(1 for u in v if u <= x) / n


def fs_estatistica(diarios_candidato, diarios_longo_prazo) -> float:
    cdf_lp   = cdf_empirica(diarios_longo_prazo)
    cdf_cand = cdf_empirica(diarios_candidato)
    return sum(abs(cdf_lp(x) - cdf_cand(x)) for x in diarios_candidato) \
        / len(diarios_candidato)


# ── 4. Montagem do TGY ──────────────────────────────────────────────────────
def montar_tgy(dados_por_ano: dict) -> dict:
    """dados_por_ano: {ano: {data: {hora: {...}}}} → estrutura final do TGY."""
    # Totais diários de GHI (kWh/m²) por (ano, mês), só dias válidos
    diarios = defaultdict(dict)          # (ano, mes) -> {dia: total_kwh}
    for ano, dias in dados_por_ano.items():
        for d, horas in dias.items():
            if dia_valido(horas):
                diarios[(ano, d.month)][d.day] = \
                    sum(v['ghi'] for v in horas.values()) / 1000.0

    meses_saida, anos_usados, fs_valores = [], {}, {}
    ghi_mensal, dni_mensal, dhi_mensal   = {}, {}, {}
    for mes in range(1, 13):
        n_dias = DIAS_MES[mes - 1]
        # Candidatos: anos com fração mínima de dias válidos no mês
        candidatos = [a for a in ANOS
                      if len(diarios.get((a, mes), {})) >= FRAC_DIAS_MES * n_dias]
        if not candidatos:
            raise RuntimeError(f'Mês {mes:02d}: nenhum ano com dados suficientes')

        longo_prazo = [t for a in candidatos
                       for t in diarios[(a, mes)].values()]
        melhor = min(candidatos,
                     key=lambda a: fs_estatistica(
                         list(diarios[(a, mes)].values()), longo_prazo))
        fs_melhor = fs_estatistica(list(diarios[(melhor, mes)].values()),
                                   longo_prazo)
        anos_usados[mes] = melhor
        fs_valores[mes]  = round(fs_melhor, 4)

        # Perfil médio horário do mês escolhido (para preencher lacunas)
        perfil = [[] for _ in range(24)]
        dias_mes = {d: h for d, h in dados_por_ano[melhor].items()
                    if d.month == mes}
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

        # Série final do mês: dia a dia, hora a hora (lacuna → perfil médio)
        dias_json, preenchidos = [], 0
        for nd in range(1, n_dias + 1):
            try:
                d = date(melhor, mes, nd)
            except ValueError:          # 29/02 nunca entra (DIAS_MES fixa 28)
                continue
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

        media_diaria = sum(sum(d['ghi']) for d in dias_json) / n_dias / 1000.0
        ghi_mensal[mes] = round(media_diaria, 3)
        dni_mensal[mes] = round(sum(sum(d['dni']) for d in dias_json)
                                / n_dias / 1000.0, 3)
        dhi_mensal[mes] = round(sum(sum(d['dhi']) for d in dias_json)
                                / n_dias / 1000.0, 3)
        meses_saida.append({'mes': mes, 'ano': melhor,
                            'horas_preenchidas': preenchidos,
                            'dias': dias_json})
        print(f'  mês {mes:02d}: ano escolhido {melhor} '
              f'(FS={fs_melhor:.4f}, candidatos={candidatos}, '
              f'GHI médio {media_diaria:.2f} kWh/m²/dia, '
              f'{preenchidos} h preenchidas)')

    return {
        'estacao':    ESTACAO['sigla'],
        'nome':       ESTACAO['nome'],
        'lat':        ESTACAO['lat'],
        'lon':        ESTACAO['lon'],
        'alt_m':      ESTACAO['alt'],
        'tz':         ESTACAO['tz'],
        'fonte':      'SONDA/INPE — sonda.ccst.inpe.br',
        'licenca':    'CC BY 4.0',
        'metodologia': 'TGY — Finkelstein-Schafer sobre totais diários de GHI '
                       '(variante TGY da ferramenta TMY do PVSyst 7)',
        'anos_disponiveis': ANOS,
        'anos_usados': anos_usados,
        'fs':          fs_valores,
        'gerado_em':   datetime.now().strftime('%d/%m/%Y'),
        'unidade':     'Wh/m² por hora (média horária em hora local UTC-3)',
        # Médias mensais (kWh/m²/dia) prontas para o nasa_data do motor;
        # t2m fica com a NASA POWER (a estação BRB não mede temperatura).
        'ghi_mensal_kwh_dia': ghi_mensal,
        'dni_mensal_kwh_dia': dni_mensal,
        'dhi_mensal_kwh_dia': dhi_mensal,
        'meses':       meses_saida,
    }


# ── Execução ────────────────────────────────────────────────────────────────
def main():
    print('1/3 — Download dos anos disponíveis (cache em sonda_dados/raw):')
    zips = {ano: baixar_ano(ano) for ano in ANOS}

    print('2/3 — Parsing + QC + agregação horária:')
    dados = {}
    for ano, caminho in zips.items():
        dados[ano] = processar_ano(caminho)
        n_validos = sum(1 for d, h in dados[ano].items() if dia_valido(h))
        print(f'  {ano}: {len(dados[ano])} dias com registro, '
              f'{n_validos} dias válidos')

    print('3/3 — Seleção FS e montagem do TGY:')
    tgy = montar_tgy(dados)

    os.makedirs(os.path.dirname(ARQ_SAIDA), exist_ok=True)
    with open(ARQ_SAIDA, 'w', encoding='utf-8') as f:
        json.dump(tgy, f, ensure_ascii=False, separators=(',', ':'))
    tamanho = os.path.getsize(ARQ_SAIDA) // 1024
    print(f'\nTGY gravado em {ARQ_SAIDA} ({tamanho} kB)')
    print('GHI mensal (kWh/m²/dia):',
          {m: tgy["ghi_mensal_kwh_dia"][m] for m in range(1, 13)})


if __name__ == '__main__':
    main()
