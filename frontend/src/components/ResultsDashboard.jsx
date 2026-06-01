import ProducaoMensalChart from './ProducaoMensalChart'
import IrradianciaChart    from './IrradianciaChart'

export default function ResultsDashboard({ resultado }) {
  if (!resultado) return null

  const {
    E_grid_anual_kWh,
    PR_pct,
    GHI_anual,
    FT_frontal,
    FT_bifacial,
    ganho_bif_pct,
    P_nom_stc_kWp,
    P_nom_AC_kW,
    monthly_GHI,
    monthly_E_grid,
    modulo_nome,
    inversor_nome,
  } = resultado

  const E_grid_MWh = +(E_grid_anual_kWh / 1000).toFixed(1)
  const Yf         = P_nom_stc_kWp > 0 ? +(E_grid_anual_kWh / P_nom_stc_kWp).toFixed(0) : 0
  const R_DC_AC    = P_nom_AC_kW   > 0 ? +(P_nom_stc_kWp    / P_nom_AC_kW).toFixed(2)   : 0

  return (
    <div className="results-dashboard">
      <div className="results-header">
        <h2>Resultados da Simulação</h2>
        {modulo_nome && (
          <span className="fonte-tag">{modulo_nome} · {inversor_nome}</span>
        )}
      </div>

      <div className="kpi-grid">
        <KPI label="E_Grid Anual"   value={E_grid_MWh}           unit="MWh/ano" color="blue" />
        <KPI label="PR"             value={`${PR_pct}%`}                        color={PR_pct >= 80 ? 'green' : 'orange'} />
        <KPI label="GHI Anual"      value={GHI_anual}            unit="kWh/m²" color="blue" />
        <KPI label="Ganho Bifacial" value={`+${ganho_bif_pct}%`}               color="green" />
        <KPI label="FT Frontal"     value={FT_frontal}                          color="gray" />
        <KPI label="FT Bifacial"    value={FT_bifacial}                         color="gray" />
        <KPI label="Potência STC"   value={P_nom_stc_kWp}        unit="kWp"    color="gray" />
        <KPI label="Potência AC"    value={P_nom_AC_kW}          unit="kW"     color="gray" />
        <KPI label="Yf"             value={Yf}                   unit="h/ano"  color="blue" />
        <KPI label="R DC/AC"        value={R_DC_AC}                             color="gray" />
      </div>

      <ProducaoMensalChart monthlyGridKwh={monthly_E_grid} />

      <IrradianciaChart monthlyGHI={monthly_GHI} />
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
