export default function LossDiagram({ lossChain, resultado }) {
  if (!lossChain || lossChain.length === 0) return null

  const {
    GHI_anual, FT_frontal, FT_bifacial, ganho_bif_pct,
    E_grid_anual_kWh, PR_pct, P_nom_stc_kWp, P_nom_AC_kW,
    monthly_E_arr, monthly_E_grid,
  } = resultado ?? {}

  const E_grid_MWh = E_grid_anual_kWh ? +(E_grid_anual_kWh / 1000).toFixed(1) : 0
  const G_frontal  = FT_frontal && GHI_anual ? +(FT_frontal * GHI_anual).toFixed(1) : 0
  const G_bifacial = FT_bifacial && GHI_anual ? +(FT_bifacial * GHI_anual).toFixed(1) : 0
  const G_rear     = +(G_bifacial - G_frontal).toFixed(1)
  const Yr         = G_frontal
  const Yf         = P_nom_stc_kWp > 0 ? +(E_grid_anual_kWh / P_nom_stc_kWp).toFixed(0) : 0
  const E_arr_sum  = monthly_E_arr ? monthly_E_arr.reduce((s, v) => s + v, 0) : 0
  const Ya         = P_nom_stc_kWp > 0 ? +(E_arr_sum / P_nom_stc_kWp).toFixed(0) : 0
  const R_DC_AC    = P_nom_AC_kW > 0 ? +(P_nom_stc_kWp / P_nom_AC_kW).toFixed(3) : 0

  // Generate smart notes
  const notas = []
  if (R_DC_AC > 1.3) notas.push(`R_DC/AC = ${R_DC_AC} → inversor superdimensionado`)
  else if (R_DC_AC < 0.9) notas.push(`R_DC/AC = ${R_DC_AC} → arranjo subdimensionado`)
  else notas.push(`R_DC/AC = ${R_DC_AC} → dimensionamento adequado`)

  const E_grid_clip = monthly_E_grid ? monthly_E_grid.reduce((s, v) => s + v, 0) : 0
  const E_arr_total = monthly_E_arr  ? monthly_E_arr.reduce((s, v) => s + v, 0)  : 0
  if (E_arr_total > 0) {
    const clipPct = ((E_arr_total - E_grid_clip) / E_arr_total * 100).toFixed(1)
    if (parseFloat(clipPct) < 1) notas.push(`IL_Pmax ≈ ${clipPct}% (sem clipping significativo)`)
    else notas.push(`Perdas clipping ≈ ${clipPct}% — considere inversor maior`)
  }

  if (ganho_bif_pct !== undefined) {
    if (ganho_bif_pct < 1) notas.push(`Ganho bifacial ${ganho_bif_pct}% — verificar N_seg/albedo`)
    else notas.push(`Ganho bifacial ${ganho_bif_pct}% (φ=0.80)`)
  }

  if (PR_pct >= 85)       notas.push(`PR = ${PR_pct}% — excelente`)
  else if (PR_pct >= 78)  notas.push(`PR = ${PR_pct}% — bom`)
  else if (PR_pct > 0)    notas.push(`PR = ${PR_pct}% — abaixo do esperado, verificar perdas`)

  return (
    <div className="chart-card loss-diagram">
      <h3>Loss Diagram — Cadeia de Perdas</h3>

      <div className="loss-layout">
        {/* LEFT — cascade */}
        <div className="loss-cascade">
          {lossChain.map((item, i) => {
            if (item.tipo === 'total') {
              const isFinal = i === lossChain.length - 1
              return (
                <div key={i} className={`loss-row loss-total${isFinal ? ' loss-final' : ''}`}>
                  <span className="loss-val">
                    {item.value} <span className="loss-unit">{item.unit}</span>
                  </span>
                  <span className="loss-label">{item.label}</span>
                </div>
              )
            }
            const isPos = item.value >= 0
            const pctColor = item.tipo === 'bifacial' ? '#10b981'
                           : isPos ? '#10b981' : '#ef4444'
            return (
              <div key={i} className="loss-row loss-delta">
                <span className="loss-pct" style={{ color: pctColor }}>
                  {isPos ? '+' : ''}{item.value}%
                </span>
                <span className="loss-label loss-delta-label">→ {item.label}</span>
              </div>
            )
          })}
        </div>

        {/* RIGHT — results + notes */}
        <div className="loss-right">
          <div className="loss-panel">
            <h4>Resultados Anuais</h4>
            <table className="loss-table">
              <tbody>
                <tr><td>GHI</td><td>{GHI_anual} kWh/m²</td></tr>
                <tr><td>G frontal</td><td>{G_frontal} kWh/m²</td></tr>
                <tr><td>FT frontal</td><td>{FT_frontal}</td></tr>
                {G_rear > 0 && <tr><td>G traseiro (bifacial)</td><td>{G_rear} kWh/m²</td></tr>}
                {FT_bifacial && FT_bifacial !== FT_frontal && (
                  <tr><td>FT bifacial efetivo</td><td>{FT_bifacial}</td></tr>
                )}
                {ganho_bif_pct > 0 && (
                  <tr className="loss-row-pos"><td>Ganho bifacial</td><td>+{ganho_bif_pct}%</td></tr>
                )}
              </tbody>
            </table>

            <h4 style={{ marginTop: '1rem' }}>Performance do Sistema</h4>
            <table className="loss-table">
              <tbody>
                <tr className="loss-row-highlight"><td>E_Grid anual</td><td>{E_grid_MWh} MWh</td></tr>
                <tr className="loss-row-highlight"><td>PR</td><td>{PR_pct}%</td></tr>
                <tr><td>Yf (yield final)</td><td>{Yf} kWh/kWp</td></tr>
                <tr><td>Ya (yield array)</td><td>{Ya} kWh/kWp</td></tr>
                <tr><td>Yr (yield ref.)</td><td>{Yr} kWh/m²</td></tr>
              </tbody>
            </table>
          </div>

          {notas.length > 0 && (
            <div className="loss-notes">
              <h4>Notas de dimensionamento</h4>
              <ul>
                {notas.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
