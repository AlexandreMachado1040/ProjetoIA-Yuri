#!/usr/bin/env python3
"""Interface Streamlit — Motor PVSyst Unificado v2.1"""

import sys, os, time, tempfile
import streamlit as st
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor_pvsyst_unificado import (
    integrar_anual, calc_system_hourly, gerar_relatorio_pdf,
    build_nasa_ghi, fetch_nasa_power_ghi, make_IV_chart, make_histogram,
    MONTH_NAMES, DAYS_PER_MONTH, PERDAS_PADRAO,
)

# ── Equipamentos fixos ───────────────────────────────────────────────────────
MOD = dict(
    modelo='CS7N-730TB-AG', fabricante='Canadian Solar',
    tecnologia='TOPCon tipo N bifacial',
    Pmpp=730.0, Vmpp=41.2, Voc=49.1, Impp=17.75, Isc=18.79,
    mu_Pmpp=-0.29, mu_Voc=-0.25, mu_Isc=0.05,
    NOCT=41.0, phi=0.80, N_cs=132, eta=23.5,
    A_mod=2.384*1.303,
    gamma=1.081, I0_ref=2.8813e-5, Iph_ref=18.888, Rs=0.001, Rsh=500.0,
)
INV = dict(
    modelo='CSI-250K-T8001A-E', fabricante='Canadian Solar',
    P_nomAC=250, P_maxAC=250, eta_max=99.01, eta_euro=98.8,
    V_dc_max=1500, V_mpp_min=500, V_mpp_max=1500, V_start=550,
    V_nom=1200, N_mppt=12, N_str_max=24,
    I_max_mppt=20, I_sc_mppt=60,
    derate_T={-30:100,0:100,25:100,30:100,35:100,40:100,45:100,50:100,60:70},
)
PERDAS = {**PERDAS_PADRAO, 'f_LID': 0.0020}

# ── Configuração da página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Motor PVSyst Unificado v2.1",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.4rem; font-weight: 700; }
[data-testid="stSidebar"] { background-color: #F0F4F8; }
.block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# ── Cabeçalho ────────────────────────────────────────────────────────────────
st.markdown("# ☀️ Motor PVSyst Unificado v2.1")
st.caption(
    "ft_anual.py (Hay + Erbs + Ray-Tracing 2D Bifacial) × "
    "Memorial_Dimensionamento_PVSyst_v2 Rev03  |  "
    f"Módulo: **{MOD['fabricante']} {MOD['modelo']}** | "
    f"Inversor: **{INV['fabricante']} {INV['modelo']}**"
)
st.divider()

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Parâmetros de entrada")

    st.markdown("### 📍 Localização")
    lat = st.number_input("Latitude (° neg=Sul)",    value=-23.55, min_value=-90.0,  max_value=90.0,  step=0.01, format="%.2f")
    lon = st.number_input("Longitude (° neg=Oeste)", value=-46.63, min_value=-180.0, max_value=180.0, step=0.01, format="%.2f")
    tz  = int(st.number_input("Fuso horário UTC",    value=-3,     min_value=-12,    max_value=14,    step=1))

    st.markdown("### ☀️ Plano Fotovoltaico")
    tilt = st.number_input("Inclinação (°)",           value=20.8, min_value=0.0, max_value=90.0,  step=0.1, format="%.1f")
    az   = st.number_input("Azimute (°, 180=Norte)",   value=180.0, min_value=0.0, max_value=360.0, step=1.0, format="%.1f")

    st.markdown("### 🔧 Configuração da String")
    Ns   = int(st.number_input("Módulos em série (N_s)", value=28, min_value=1, max_value=50, step=1))
    Nstr = int(st.number_input("N° de strings",          value=3,  min_value=1, max_value=30, step=1))

    st.markdown("### 🔆 Modelo de Irradiância")
    modo_radio = st.radio("Modo", ["BIFACIAL", "MONOFACIAL"], index=0, horizontal=True)
    bifacial = (modo_radio == "BIFACIAL")

    st.markdown("### 🌿 Ambiente / Bifacial")
    albedo     = st.slider("Albedo do solo", 0.0, 1.0, 0.30, 0.01)
    pitch      = st.number_input("Dist. entre fileiras (m)", value=2.826, min_value=0.5,  max_value=30.0, step=0.001, format="%.3f")
    mod_height = st.number_input("Altura do módulo (m)",     value=2.0,   min_value=0.5,  max_value=5.0,  step=0.1,   format="%.1f")

    st.markdown("### 🚀 Precisão Ray-Tracing")
    N_seg  = st.select_slider("Segmentos",      options=[5, 10, 15, 20, 30, 60],       value=15)
    N_rays = st.select_slider("Raios/segmento", options=[36, 60, 90, 120, 180, 360, 720], value=180)
    if bifacial:
        st.caption(f"⏱ ~{int(N_seg*N_rays*4259/2700/10)*10} s estimado")
    else:
        st.caption("⚡ Modo monofacial — cálculo rápido")

    st.divider()

    # Verificar fonte dos dados NASA em tempo real
    with st.spinner("Consultando NASA POWER..."):
        nasa_live = fetch_nasa_power_ghi(lat, lon)
    if nasa_live:
        ghi_anual = sum(nasa_live[m]*DAYS_PER_MONTH[m-1] for m in range(1,13))
        st.success(f"NASA POWER ao vivo — GHI anual: **{ghi_anual:.0f} kWh/m²**")
    else:
        st.warning("NASA POWER inacessível — usando fallback São Paulo")

    calcular = st.button("▶  Calcular", type="primary", use_container_width=True)

# ── Tela inicial ─────────────────────────────────────────────────────────────
if "ft_result" not in st.session_state and not calcular:
    c1, c2 = st.columns(2)
    with c1:
        st.info(
            "**Configure os parâmetros** na barra lateral e clique em "
            "**▶ Calcular** para iniciar a simulação."
        )
        st.markdown(f"""
| Campo | Valor |
|---|---|
| Módulo | {MOD['fabricante']} {MOD['modelo']} |
| Tecnologia | {MOD['tecnologia']} |
| Potência STC | {MOD['Pmpp']:.0f} Wp |
| Eficiência | {MOD['eta']:.1f}% |
| Bifacialidade φ | {MOD['phi']:.2f} |
""")
    with c2:
        st.markdown(f"""
| Campo | Valor |
|---|---|
| Inversor | {INV['fabricante']} {INV['modelo']} |
| Potência AC | {INV['P_nomAC']} kW |
| η máx. | {INV['eta_max']:.2f}% |
| V_dc máx. | {INV['V_dc_max']} V |
| MPPTs | {INV['N_mppt']} |
""")

# ── Cálculo ──────────────────────────────────────────────────────────────────
if calcular:
    modo_str = "BIFACIAL (Ray-Tracing 2D)" if bifacial else "MONOFACIAL"
    prog = st.progress(0, text=f"Passo 1/2 — Integração anual ({modo_str})...")

    ft = integrar_anual(
        lat=lat, lon=lon, tz=tz,
        tilt=tilt, az_panel=az,
        albedo=albedo, phi=MOD['phi'],
        pitch=pitch, mod_height=mod_height,
        N_seg=N_seg, N_rays=N_rays,
        verbose=False, bifacial=bifacial,
    )
    prog.progress(70, text="Passo 2/2 — Calculando sistema e histograma...")

    sys_r = calc_system_hourly(ft, dict(
        modulo=MOD, inversor=INV,
        N_s=Ns, N_strings=Nstr,
        perdas=PERDAS,
    ))
    prog.progress(100, text="✅ Simulação concluída!")
    time.sleep(0.5)
    prog.empty()

    st.session_state["ft_result"]  = ft
    st.session_state["sys_result"] = sys_r
    st.session_state["inp_params"] = dict(
        lat=lat, lon=lon, tz=tz, tilt=tilt, az=az,
        N_s=Ns, N_strings=Nstr, bifacial=bifacial,
        albedo=albedo, pitch=pitch, mod_height=mod_height,
        N_seg=N_seg, N_rays=N_rays,
        modulo=MOD, inversor=INV, perdas=PERDAS,
    )
    st.success(f"✅ Simulação concluída em {ft['tempo_calc_s']:.1f} s")

# ── Resultados ────────────────────────────────────────────────────────────────
if "ft_result" in st.session_state:
    ft    = st.session_state["ft_result"]
    sys_r = st.session_state["sys_result"]
    inp   = st.session_state["inp_params"]
    is_bif = ft.get("bifacial", True)

    # ── Fonte dos dados ───────────────────────────────────────────────────────
    nasa_live = fetch_nasa_power_ghi(inp['lat'], inp['lon'])  # cache hit
    if nasa_live:
        st.info(
            f"🛰️ **Dados NASA POWER ao vivo** — LAT={inp['lat']}°, LON={inp['lon']}°  |  "
            f"GHI anual real: **{sum(nasa_live[m]*DAYS_PER_MONTH[m-1] for m in range(1,13)):.0f} kWh/m²**  |  "
            f"[power.larc.nasa.gov](https://power.larc.nasa.gov)"
        )
    else:
        st.warning("⚠️ NASA POWER inacessível — resultados usando fallback São Paulo")

    # ── KPIs ─────────────────────────────────────────────────────────────────
    st.markdown("## 📊 Resultados")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("E_Grid",       f"{sys_r['E_grid_tot']:,.0f} kWh/ano")
    k2.metric("PR",           f"{sys_r['PR']:.1f}%")
    k3.metric("Yf",           f"{sys_r['Yf']:.0f} kWh/kWp")
    k4.metric("GHI anual",    f"{ft['GHI_anual']:.0f} kWh/m²")
    k5.metric("Ganho bifacial", f"{ft['ganho_bif_pct']:+.2f}%" if is_bif else "0,00%")
    k6.metric("IL_Pmax",      f"{sys_r['IL_pct']:.2f}%")

    st.divider()

    # ── Gráficos — linha 1 ────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        fig, ax = plt.subplots(figsize=(6, 3.8))
        fig.patch.set_facecolor("#F8FAFB"); ax.set_facecolor("#FAFAFA")
        x = np.arange(12); w = 0.38
        nasa_m = [build_nasa_ghi(inp['lat'], inp['lon'])[i+1]*DAYS_PER_MONTH[i] for i in range(12)]
        ax.bar(x-w/2, nasa_m,                    w, label="NASA POWER",                      color="#1976D2", alpha=0.82)
        ax.bar(x+w/2, ft["monthly"]["GHI"], w, label=f"Motor ({ft['GHI_anual']:.0f} kWh/m²)", color="#42A5F5", alpha=0.82)
        ax.set_xticks(x); ax.set_xticklabels(MONTH_NAMES, fontsize=8)
        ax.set_ylabel("kWh/m²/mês"); ax.grid(axis="y", alpha=0.3)
        ax.set_title("GHI Mensal", fontweight="bold", color="#0D3B6E")
        ax.legend(fontsize=8); ax.tick_params(labelsize=8)
        fig.tight_layout()
        st.pyplot(fig); plt.close(fig)

    with col_b:
        fig, ax = plt.subplots(figsize=(6, 3.8))
        fig.patch.set_facecolor("#F8FAFB"); ax.set_facecolor("#FAFAFA")
        ghi_m = ft["monthly"]["GHI"]; gf_m = ft["monthly"]["Gf"]; gb_m = ft["monthly"]["Gb"]
        ftf_m = [f/g if g > 0 else 0 for f, g in zip(gf_m, ghi_m)]
        ftb_m = [b/g if g > 0 else 0 for b, g in zip(gb_m, ghi_m)]
        ax.plot(MONTH_NAMES, ftf_m, "o-", color="#1565C0", lw=2, ms=6, label=f"FT frontal = {ft['FT_frontal']:.4f}")
        if is_bif:
            ax.plot(MONTH_NAMES, ftb_m, "s-", color="#2E7D32", lw=2, ms=6, label=f"FT bifacial = {ft['FT_bifacial']:.4f}")
            ganho_lbl = f"Ganho bifacial = {ft['ganho_bif_pct']:+.2f}%"
            ganho_col = "#F57F17"
        else:
            ganho_lbl = "Modo MONOFACIAL — sem ganho bifacial"
            ganho_col = "#C62828"
        ax.text(0.5, 0.97, ganho_lbl, transform=ax.transAxes, ha="center", fontsize=8.5,
                color=ganho_col, fontweight="bold",
                bbox=dict(boxstyle="round", facecolor="#FFFDE7", alpha=0.9))
        ax.set_ylabel("FT = G_tilt / GHI"); ax.grid(alpha=0.3)
        ax.set_title("Fator de Transposição Mensal", fontweight="bold", color="#0D3B6E")
        ax.legend(fontsize=8, loc="lower center"); ax.tick_params(labelsize=8, rotation=45)
        fig.tight_layout()
        st.pyplot(fig); plt.close(fig)

    # ── Gráficos — linha 2 ────────────────────────────────────────────────────
    col_c, col_d = st.columns(2)

    with col_c:
        fig, ax = plt.subplots(figsize=(6, 3.8))
        fig.patch.set_facecolor("#F8FAFB")
        make_histogram(ax, sys_r, sys_r["P_nom_stc"], sys_r["P_nom_DC"])
        fig.tight_layout()
        st.pyplot(fig); plt.close(fig)

    with col_d:
        fig, ax = plt.subplots(figsize=(6, 3.8))
        fig.patch.set_facecolor("#F8FAFB")
        make_IV_chart(ax, Ns, Nstr, MOD, INV)
        fig.tight_layout()
        st.pyplot(fig); plt.close(fig)

    # ── Tabela de perdas ─────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📉 Cadeia de perdas")
    col_e, col_f = st.columns([1, 1])

    with col_e:
        perds = inp["perdas"]
        dados_ft = {
            "GHI anual":          f"{ft['GHI_anual']:.1f} kWh/m²",
            "G_tilt frontal":     f"{ft['Gtilt_frontal']:.1f} kWh/m²",
            "FT frontal":         f"{ft['FT_frontal']:.4f}",
            "G_rear (RT)":        f"{ft['G_rear_rt']:.1f} kWh/m²" if is_bif else "0,0 kWh/m²",
            "φ (bifacialidade)":  f"{ft['phi_efetivo']:.2f}" if is_bif else "0,00 (desativado)",
            "G_tilt bifacial":    f"{ft['Gtilt_bifacial']:.1f} kWh/m²",
            "FT efetivo":         f"{ft['FT_bifacial']:.4f}",
            "Horas com sol":      f"{ft['horas_sol']} h/ano",
        }
        st.dataframe(
            {"Grandeza": list(dados_ft.keys()), "Valor": list(dados_ft.values())},
            use_container_width=True, hide_index=True,
        )

    with col_f:
        dados_sys = {
            "P_nom STC":         f"{sys_r['P_nom_stc']:.2f} kWp",
            "P_nom AC":          f"{sys_r['P_nom_AC']:.0f} kW",
            "P_nom DC":          f"{sys_r['P_nom_DC']:.2f} kW",
            "R_DC_AC":           f"{sys_r['R_DC_AC']:.3f}",
            "E_MPP potencial":   f"{sys_r['E_mpp_tot']:,.0f} kWh/ano",
            "E_Array real (DC)": f"{sys_r['E_array_tot']:,.0f} kWh/ano",
            "E_Grid (AC rede)":  f"{sys_r['E_grid_tot']:,.0f} kWh/ano",
            "IL_Pmax":           f"{sys_r['IL_tot']:,.0f} kWh ({sys_r['IL_pct']:.2f}%)",
            "Inv. Loss":         f"{sys_r['InvLoss_tot']:,.0f} kWh ({sys_r['InvLoss_pct']:.1f}%)",
            "Horas clipping":    f"{sys_r['N_horas_clip']} h/ano",
        }
        st.dataframe(
            {"Indicador": list(dados_sys.keys()), "Valor": list(dados_sys.values())},
            use_container_width=True, hide_index=True,
        )

    # ── Download PDF ─────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📄 Relatório PDF")

    if st.button("⬇️  Gerar e baixar PDF", type="primary"):
        with st.spinner("Gerando relatório PDF..."):
            tmp_pdf = os.path.join(
                tempfile.gettempdir(),
                f"relatorio_pvsyst_{int(time.time())}.pdf",
            )
            gerar_relatorio_pdf(inp, ft, sys_r, tmp_pdf)
            with open(tmp_pdf, "rb") as f:
                pdf_bytes = f.read()

        sufixo = "BIFACIAL" if is_bif else "MONOFACIAL"
        st.download_button(
            label="📥  Clique aqui para baixar o PDF",
            data=pdf_bytes,
            file_name=f"Relatorio_PVSyst_{sufixo}_{time.strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
        )
