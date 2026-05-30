import ProducaoMensalChart from './ProducaoMensalChart'
import IrradianciaChart    from './IrradianciaChart'
import HistogramaChart     from './HistogramaChart'
import LossDiagram         from './LossDiagram'

export default function ResultsDashboard({ resultado, pdfUrl }) {
  if (!resultado) return null

  const {
    GHI_anual, G_rear_rt, ganho_bifacial, E_grid_anual_MWh,
    PR_pct, Yf, Ya, fonte_dados,
    monthly_grid_kWh, monthly_arr_kWh,
    monthly_GHI, monthly_Gf, monthly_Gb,
    hist_bins, hist_arr, hist_grid,
    loss_chain,
    P_nom_stc_kWp, R_DC_AC,
  } = resultado

  const bifacial = ganho_bifacial > 0

  return (
    <div className="results-dashboard">
      <div className="results-header">
        <h2>Resultados da Simulação</h2>
        {fonte_dados && <span className="fonte-tag">{fonte_dados}</span>}
        {pdfUrl && (
          <a className="btn-pdf" href={pdfUrl} target="_blank" rel="noreferrer">
            Baixar PDF
          </a>
        )}
      </div>

      {/* ── KPIs ── */}
      <div className="kpi-grid">
        <KPI label="GHI Anual"       value={GHI_anual}         unit="kWh/m²"  color="blue" />
        <KPI label="G Traseira (RT)" value={G_rear_rt}         unit="kWh/m²"  color="green" />
        <KPI label="Ganho Bifacial"  value={`+${ganho_bifacial}%`}             color="green" />
        <KPI label="E_Grid Anual"    value={E_grid_anual_MWh}  unit="MWh/ano" color="blue" />
        <KPI label="PR"              value={`${PR_pct}%`}                      color={PR_pct >= 80 ? 'green' : 'orange'} />
        <KPI label="Yf (h/ano)"     value={Yf}                unit="h"       color="blue" />
        <KPI label="Ya (referência)" value={Ya}                unit="h"       color="gray" />
        <KPI label="Potência STC"   value={P_nom_stc_kWp}      unit="kWp"     color="gray" />
        <KPI label="R DC/AC"        value={R_DC_AC}                            color="gray" />
      </div>

      {/* ── Gráfico 1: Produção Mensal ── */}
      <ProducaoMensalChart
        monthlyGridKwh={monthly_grid_kWh}
        monthlyArrKwh={monthly_arr_kWh}
      />

      {/* ── Gráfico 2: Irradiância ── */}
      <IrradianciaChart
        monthlyGHI={monthly_GHI}
        monthlyGf={monthly_Gf}
        monthlyGb={monthly_Gb}
        bifacial={bifacial}
      />

      {/* ── Gráfico 3: Histograma ── */}
      <HistogramaChart
        bins={hist_bins}
        histArr={hist_arr}
        histGrid={hist_grid}
      />

      {/* ── Gráfico 4: Loss Diagram ── */}
      <LossDiagram lossChain={loss_chain} />
    </div>
  )
}

function KPI({ label, value, unit, color = 'blue' }) {
  return (
    <div className={`kpi-card kpi-${color}`}>
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}{unit ? ` ${unit}` : ''}</span>
    </div>
  )
}
