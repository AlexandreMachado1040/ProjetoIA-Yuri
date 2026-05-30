"""Executa o motor de simulação em thread de background."""
import os, sys, threading, traceback, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import parsers_pvsyst as pp
import motor_pvsyst_unificado as motor
from motor_pvsyst_unificado import PERDAS_PADRAO
from backend import job_store

MODULOS_DIR    = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                               "Arquivos", "PVmodules")
INVERSORES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                               "Arquivos", "Inverters")
PDF_DIR        = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                               "relatorios")
os.makedirs(PDF_DIR, exist_ok=True)


def _build_inp(api_inp: dict) -> dict:
    """Converte o dict da API para o formato interno do motor."""
    mod = api_inp['modulo']
    inv = api_inp['inversor']

    # Ajuste de LID para tecnologia TOPCon / HIT / bifacial
    tec = mod.get('tecnologia', '').lower()
    f_LID = 0.0020 if any(x in tec for x in ('bifacial', 'topcon', 'hit', 'hju')) \
            else PERDAS_PADRAO['f_LID']
    perdas = {**PERDAS_PADRAO, 'f_LID': f_LID}

    bifacial = api_inp.get('modo', 'BIFACIAL') == 'BIFACIAL'

    return dict(
        lat=api_inp['lat'],
        lon=api_inp['lon'],
        tz=api_inp['tz'],
        tilt=api_inp['tilt'],
        az=api_inp.get('azimuth', 180.0),   # motor usa az; 180=Norte (padrão Brasil)
        N_s=api_inp['Ns'],
        N_strings=api_inp['Np'],
        n_inversores=api_inp.get('n_inversores', 1),
        bifacial=bifacial,
        modo_dados=api_inp.get('modo_dados', 'climatologia'),
        ano_dados=api_inp.get('ano_dados'),
        albedo=api_inp.get('albedo', 0.25),
        pitch=api_inp.get('pitch', 10.0),
        mod_height=api_inp.get('mod_width', 2.0),  # largura física do módulo = altura no rack
        N_seg=15,
        N_rays=180,
        modulo=mod,
        inversor=inv,
        perdas=perdas,
    )


def _run(job_id: str, api_inp: dict) -> None:
    try:
        inp = _build_inp(api_inp)
        mod = inp['modulo']

        job_store.update_job(job_id, status="running", progress=5,
                             message="Iniciando simulação…")

        # ── 1. Integração anual (Ray-Tracing + FT) ──
        job_store.update_job(job_id, progress=10,
                             message="Calculando fator de transposição e Ray-Tracing…")
        ft = motor.integrar_anual(
            lat=inp['lat'], lon=inp['lon'], tz=inp['tz'],
            tilt=inp['tilt'], az_panel=inp['az'],
            albedo=inp['albedo'], phi=mod['phi'],
            pitch=inp['pitch'], mod_height=inp['mod_height'],
            N_seg=inp['N_seg'], N_rays=inp['N_rays'],
            verbose=False, bifacial=inp['bifacial'],
            modo_dados=inp['modo_dados'],
            ano=inp.get('ano_dados'),
        )

        # ── 2. Simulação horária do sistema ──
        job_store.update_job(job_id, progress=75,
                             message="Simulando sistema hora a hora…")
        sys_r = motor.calc_system_hourly(ft, dict(
            modulo=inp['modulo'],
            inversor=inp['inversor'],
            N_s=inp['N_s'],
            N_strings=inp['N_strings'],
            perdas=inp['perdas'],
        ))

        # ── 3. Geração do PDF ──
        job_store.update_job(job_id, progress=90, message="Gerando relatório PDF…")
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        modo_label = "BIFACIAL" if inp['bifacial'] else "MONOFACIAL"
        pdf_filename = f"Relatorio_{modo_label}_{ts}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)
        motor.gerar_relatorio_pdf(inp, ft, sys_r, pdf_path)

        # ── 4. Monta resumo de resultado ──
        perdas  = inp['perdas']
        bifacial = inp['bifacial']
        phi_ef   = ft.get('phi_efetivo', mod['phi'] if bifacial else 0.0)
        E_nom    = sys_r.get('E_mpp_tot', 0)
        E_arr    = sys_r.get('E_array_tot', 0)
        E_grid   = sys_r.get('E_grid_tot', 0)
        G_tilt   = ft.get('Gtilt_frontal', 0)
        G_bif    = ft.get('Gtilt_bifacial', 0)

        # Cascata de perdas — mesma lógica do PDF
        loss_chain = [
            {"label": "Global horizontal (GHI)",              "value": round(ft.get('GHI_anual', 0), 1),        "unit": "kWh/m²", "tipo": "total"},
            {"label": f"FT frontal (+{(ft.get('FT_frontal',1)-1)*100:.1f}% inclinação)",
                                                               "value": round(G_tilt, 1),                         "unit": "kWh/m²", "tipo": "total"},
            {"label": "Sombreamento próximo",                 "value": -round(perdas['f_shad']*100, 2),          "unit": "%",       "tipo": "perda"},
            {"label": "Sujeira / Soiling",                    "value": -round(perdas['f_soil']*100, 2),          "unit": "%",       "tipo": "perda"},
            {"label": "IAM (ângulo de incidência)",           "value": -round(perdas['f_IAM']*100, 2),           "unit": "%",       "tipo": "perda"},
            {"label": f"Bifacial φ={phi_ef:.2f} (+{ft.get('ganho_bif_pct',0):.2f}% G_rear)"
                       if bifacial else "Monofacial (sem G_rear)",
                                                               "value": round(G_bif, 1),                          "unit": "kWh/m²", "tipo": "bifacial"},
            {"label": f"Array nominal (η_STC={mod.get('eta',0):.1f}%)",
                                                               "value": round(E_nom / 1000, 3),                   "unit": "MWh",    "tipo": "total"},
            {"label": "Perda por temperatura",                "value": -round(perdas['f_temp']*100, 2),          "unit": "%",       "tipo": "perda"},
            {"label": "LID — degradação induzida",            "value": -round(perdas['f_LID']*100, 2),           "unit": "%",       "tipo": "perda"},
            {"label": "Mismatch módulos/strings",             "value": -round(perdas['f_mis']*100, 2),           "unit": "%",       "tipo": "perda"},
            {"label": "Perdas ôhmicas DC",                    "value": -round(perdas['f_ohm']*100, 2),           "unit": "%",       "tipo": "perda"},
            {"label": "Array virtual energy (MPP)",           "value": round(E_arr / 1000, 3),                   "unit": "MWh",    "tipo": "total"},
            {"label": "Sobrecarga inversor (IL_Pmax)",        "value": -round(sys_r.get('IL_pct', 0), 2),        "unit": "%",       "tipo": "perda"},
            {"label": "Eficiência do inversor",               "value": -round(sys_r.get('InvLoss_pct', 0), 2),   "unit": "%",       "tipo": "perda"},
            {"label": "Energia injetada na rede",             "value": round(E_grid / 1000, 3),                  "unit": "MWh",    "tipo": "total"},
        ]

        monthly_ft = ft.get('monthly', {})

        resultado = {
            # KPIs principais
            "GHI_anual":        round(ft.get("GHI_anual", 0), 1),
            "G_rear_rt":        round(ft.get("G_rear_rt", 0), 1),
            "ganho_bifacial":   round(ft.get("ganho_bif_pct", 0), 2),
            "E_grid_anual_MWh": round(E_grid / 1000, 3),
            "PR_pct":           round(sys_r.get("PR", 0), 1),
            "Yf":               round(sys_r.get("Yf", 0), 1),
            "Ya":               round(sys_r.get("Ya", 0), 1),
            "fonte_dados":      ft.get("fonte_dados", ""),
            # Gráfico de produção mensal (Array vs Grid)
            "monthly_grid_kWh": sys_r.get("monthly_grid", [0] * 12),
            "monthly_arr_kWh":  sys_r.get("monthly_arr",  [0] * 12),
            # Gráfico de irradiância mensal (GHI, Gf, Gb)
            "monthly_GHI":  monthly_ft.get("GHI", [0] * 12),
            "monthly_Gf":   monthly_ft.get("Gf",  [0] * 12),
            "monthly_Gb":   monthly_ft.get("Gb",  [0] * 12),
            # Histograma de potência
            "hist_bins":    [round(b, 1) for b in sys_r.get("bins_ctr", [])],
            "hist_arr":     [round(v, 1) for v in sys_r.get("hist_verde", [])],
            "hist_grid":    [round(v, 1) for v in sys_r.get("hist_roxa", [])],
            # Diagrama de perdas
            "loss_chain":   loss_chain,
            # Extras para info
            "P_nom_stc_kWp": round(sys_r.get("P_nom_stc", 0), 2),
            "R_DC_AC":       round(sys_r.get("R_DC_AC", 0), 3),
        }

        job_store.update_job(job_id, status="done", progress=100,
                             message="Concluído.",
                             resultado=resultado,
                             pdf_url=f"/api/relatorios/{pdf_filename}")

    except Exception as exc:
        job_store.update_job(job_id, status="error", progress=0,
                             message=f"Erro: {exc}\n{traceback.format_exc()}")


def iniciar_simulacao(job_id: str, api_inp: dict) -> None:
    """Lança thread de simulação sem bloquear o servidor."""
    t = threading.Thread(target=_run, args=(job_id, api_inp), daemon=True)
    t.start()
