import { useI18n, traduzirRotuloMotor } from '../i18n.jsx'

export default function LossDiagram({ lossChain, resultado }) {
  const { t } = useI18n()
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

  // Notas inteligentes de dimensionamento
  const notas = []
  if (R_DC_AC > 1.3) notas.push(t('loss.nota_super', { v: R_DC_AC }))
  else if (R_DC_AC < 0.9) notas.push(t('loss.nota_sub', { v: R_DC_AC }))
  else notas.push(t('loss.nota_ok', { v: R_DC_AC }))

  const E_grid_clip = monthly_E_grid ? monthly_E_grid.reduce((s, v) => s + v, 0) : 0
  const E_arr_total = monthly_E_arr  ? monthly_E_arr.reduce((s, v) => s + v, 0)  : 0
  if (E_arr_total > 0) {
    const clipPct = ((E_arr_total - E_grid_clip) / E_arr_total * 100).toFixed(1)
    if (parseFloat(clipPct) < 1) notas.push(t('loss.nota_clip_ok', { v: clipPct }))
    else notas.push(t('loss.nota_clip', { v: clipPct }))
  }

  if (ganho_bif_pct !== undefined) {
    if (ganho_bif_pct < 1) notas.push(t('loss.nota_bif_baixo', { v: ganho_bif_pct }))
    else notas.push(t('loss.nota_bif', { v: ganho_bif_pct }))
  }

  if (PR_pct >= 85)       notas.push(t('loss.nota_pr_otimo', { v: PR_pct }))
  else if (PR_pct >= 78)  notas.push(t('loss.nota_pr_bom', { v: PR_pct }))
  else if (PR_pct > 0)    notas.push(t('loss.nota_pr_baixo', { v: PR_pct }))

  return (
    <div className="chart-card loss-diagram">
      <h3>{t('loss.titulo')}</h3>

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
                  <span className="loss-label">{traduzirRotuloMotor(item.label, t)}</span>
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
                <span className="loss-label loss-delta-label">→ {traduzirRotuloMotor(item.label, t)}</span>
              </div>
            )
          })}
        </div>

        {/* RIGHT — results + notes */}
        <div className="loss-right">
          <div className="loss-panel">
            <h4>{t('loss.anuais')}</h4>
            <table className="loss-table">
              <tbody>
                <tr><td>GHI</td><td>{GHI_anual} kWh/m²</td></tr>
                <tr><td>{t('loss.g_frontal')}</td><td>{G_frontal} kWh/m²</td></tr>
                <tr><td>{t('loss.ft_frontal')}</td><td>{FT_frontal}</td></tr>
                {G_rear > 0 && <tr><td>{t('loss.g_rear')}</td><td>{G_rear} kWh/m²</td></tr>}
                {FT_bifacial && FT_bifacial !== FT_frontal && (
                  <tr><td>{t('loss.ft_bif')}</td><td>{FT_bifacial}</td></tr>
                )}
                {ganho_bif_pct > 0 && (
                  <tr className="loss-row-pos"><td>{t('loss.ganho_bif')}</td><td>+{ganho_bif_pct}%</td></tr>
                )}
              </tbody>
            </table>

            <h4 style={{ marginTop: '1rem' }}>{t('loss.perf')}</h4>
            <table className="loss-table">
              <tbody>
                <tr className="loss-row-highlight"><td>{t('loss.egrid_anual')}</td><td>{E_grid_MWh} MWh</td></tr>
                <tr className="loss-row-highlight"><td>PR</td><td>{PR_pct}%</td></tr>
                <tr><td>{t('loss.yf')}</td><td>{Yf} kWh/kWp</td></tr>
                <tr><td>{t('loss.ya')}</td><td>{Ya} kWh/kWp</td></tr>
                <tr><td>{t('loss.yr')}</td><td>{Yr} kWh/m²</td></tr>
              </tbody>
            </table>
          </div>

          {notas.length > 0 && (
            <div className="loss-notes">
              <h4>{t('loss.notas')}</h4>
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
