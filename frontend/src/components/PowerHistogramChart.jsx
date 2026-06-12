import {
  ComposedChart, Bar, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
  ReferenceArea, Label,
} from 'recharts'
import { useI18n } from '../i18n.jsx'

// Critério PVSyst: 0–0.2% ótimo, 0.2–3% aceitável, >3% subdimensionado
function clipColor(pct) {
  const v = parseFloat(pct)
  if (v <= 0.2) return '#10b981'
  if (v <= 3.0) return '#f59e0b'
  return '#ef4444'
}

function clipLabelKey(pct) {
  const v = parseFloat(pct)
  if (v <= 0.2) return 'hist.otimo'
  if (v <= 3.0) return 'hist.aceitavel'
  return 'hist.subdim'
}

function CustomTooltip({ active, payload, label, P_nom_DC, t }) {
  if (!active || !payload?.length) return null
  const grid    = payload.find(p => p.dataKey === 'grid')?.value ?? 0
  const loss    = payload.find(p => p.dataKey === 'loss')?.value ?? 0
  const arr     = grid + loss
  const pct     = arr > 0 ? ((loss / arr) * 100).toFixed(1) : '0.0'
  const clipped = label > P_nom_DC
  return (
    <div style={{
      background: '#0d1530', border: '1px solid rgba(0,95,255,0.3)',
      borderRadius: 6, padding: '8px 12px', fontSize: 12,
    }}>
      <p style={{ color: '#94a3b8', marginBottom: 4 }}>
        P_DC: {label} kW {clipped ? <span style={{ color: '#ef4444' }}>{t('hist.clipping')}</span> : ''}
      </p>
      <p style={{ color: '#00C8FF' }}>E_Grid: {grid.toFixed(0)} kWh</p>
      <p style={{ color: clipped ? '#ef4444' : '#f97316' }}>
        {clipped ? t('hist.perda_tt_clip') : t('hist.perda_tt_inv')}: {loss.toFixed(0)} kWh ({pct}%)
      </p>
      <p style={{ color: '#e2e8f0', borderTop: '1px solid rgba(255,255,255,0.1)', marginTop: 4, paddingTop: 4 }}>
        E_Array: {arr.toFixed(0)} kWh
      </p>
    </div>
  )
}

export default function PowerHistogramChart({ resultado }) {
  const { t } = useI18n()
  const {
    hist_power_bins, hist_power_arr, hist_power_grid,
    P_nom_stc_kWp, P_nom_AC_kW, P_nom_DC_kW, R_DC_AC, eta_inv_max_pct,
  } = resultado ?? {}
  if (!hist_power_bins || hist_power_bins.length === 0) return null

  // Dados em kWh (converter de MWh)
  const data = hist_power_bins
    .slice(0, hist_power_bins.length - 1)
    .map((b, i) => {
      const arr  = +((hist_power_arr?.[i]  ?? 0) * 1000)
      const grid = +((hist_power_grid?.[i] ?? 0) * 1000)
      const loss = +(arr - grid).toFixed(1)
      return { kW: +b.toFixed(1), grid: +grid.toFixed(1), loss }
    })
    .filter(d => (d.grid + d.loss) > 0)

  // Perdas totais
  const totalArr  = hist_power_arr?.reduce((s, v) => s + v, 0) ?? 1
  const totalLoss = hist_power_arr && hist_power_grid
    ? hist_power_arr.reduce((s, v, i) => s + v - (hist_power_grid[i] ?? 0), 0)
    : 0
  const clipPct = totalArr > 0 ? ((totalLoss / totalArr) * 100).toFixed(1) : '0.0'

  // Pnom DC: limiar real de clipping (= Pnom AC / η_max)
  const P_dc = P_nom_DC_kW ?? (P_nom_AC_kW ? +(P_nom_AC_kW / ((eta_inv_max_pct ?? 99) / 100)).toFixed(1) : null)
  const rDC  = R_DC_AC ?? (P_nom_AC_kW && P_nom_stc_kWp ? +(P_nom_stc_kWp / P_nom_AC_kW).toFixed(2) : null)

  const maxKW = data.length ? data[data.length - 1].kW : (P_nom_stc_kWp ?? 100)
  const xMax  = Math.ceil(maxKW * 1.08 / 10) * 10

  const color = clipColor(clipPct)
  const label = t(clipLabelKey(clipPct))

  return (
    <div className="chart-card">
      <h3>{t('hist.titulo')}</h3>

      {/* Subtitle estilo PVSyst */}
      <p className="chart-sub">
        Pnom STC: <strong>{P_nom_stc_kWp} kWp</strong>
        &nbsp;·&nbsp;
        Pnom AC: <strong>{P_nom_AC_kW} kW</strong>
        {P_dc && <> &nbsp;·&nbsp; Pnom DC: <strong>{P_dc} kW</strong></>}
        {rDC  && <> &nbsp;·&nbsp; R DC/AC: <strong>{rDC}</strong></>}
        &nbsp;·&nbsp;
        {t('hist.overload')}&nbsp;
        <strong style={{ color }}>{clipPct}%</strong>
        &nbsp;
        <span style={{
          background: `${color}18`, border: `1px solid ${color}50`,
          borderRadius: 4, padding: '1px 6px', fontSize: '0.7rem', color,
        }}>
          {label}
        </span>
      </p>

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} barCategoryGap="28%"
          margin={{ top: 20, right: 24, left: 10, bottom: 32 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />

          <XAxis
            dataKey="kW" type="number"
            domain={[0, xMax]} tickCount={10}
            tick={{ fontSize: 11 }}
            tickFormatter={v => v === 0 ? '0' : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : Math.round(v).toString()}
          >
            <Label value={t('hist.pdc')} position="insideBottom" offset={-20} fill="#94a3b8" fontSize={12} />
          </XAxis>

          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={v => v === 0 ? '0' : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : Math.round(v).toString()}
            label={{ value: 'kWh', angle: -90, position: 'insideLeft', offset: 10, fill: '#94a3b8', fontSize: 11 }}
          />

          <Tooltip content={<CustomTooltip P_nom_DC={P_dc} t={t} />} />
          <Legend verticalAlign="top" />

          {/* Zona de clipping — acima do Pnom DC */}
          {P_dc && (
            <ReferenceArea
              x1={P_dc} x2={xMax}
              fill="rgba(239,68,68,0.07)"
              stroke="none"
            />
          )}

          {/* Pnom DC — limiar real de clipping */}
          {P_dc && (
            <ReferenceLine x={P_dc} stroke="#ef4444" strokeWidth={1.5} strokeDasharray="4 2"
              label={{ value: `Pnom DC ${P_dc} kW`, position: 'insideTopLeft', fontSize: 9, fill: '#ef4444' }} />
          )}

          {/* Pnom AC */}
          {P_nom_AC_kW && (
            <ReferenceLine x={P_nom_AC_kW} stroke="#f59e0b" strokeWidth={2} strokeDasharray="6 3"
              label={{ value: `Pnom AC ${P_nom_AC_kW} kW`, position: 'top', fontSize: 10, fill: '#f59e0b' }} />
          )}

          {/* Pnom STC — potência projetada total do arranjo */}
          {P_nom_stc_kWp && (
            <ReferenceLine x={P_nom_stc_kWp} stroke="#10b981" strokeWidth={2}
              label={{ value: `Pnom STC ${P_nom_stc_kWp} kWp`, position: 'top', fontSize: 10, fill: '#10b981' }} />
          )}

          {/* E_Grid — base da barra (fill na série também alimenta a legenda).
              maxBarSize garante o afinamento também no eixo numérico. */}
          <Bar dataKey="grid" name={t('hist.egrid_ac')} stackId="a" radius={[0,0,2,2]}
            fill="#00C8FF" maxBarSize={26} />

          {/* Perda — topo da barra: laranja (eficiência) ou vermelho (clipping).
              O fill da série dá a cor da legenda; as Cells pintam barra a barra. */}
          <Bar dataKey="loss" name={t('hist.perda_inv')} stackId="a" radius={[3,3,0,0]}
            opacity={0.85} fill="#f97316" maxBarSize={26}>
            {data.map((d, i) => (
              <Cell key={i} fill={P_dc && d.kW > P_dc ? '#ef4444' : '#f97316'} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>

      {/* Legenda de cores da perda */}
      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: '0.72rem', color: 'var(--text-sub)', flexWrap: 'wrap' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 12, height: 12, borderRadius: 2, background: '#f97316', display: 'inline-block' }} />
          {t('hist.perda_ef')}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 12, height: 12, borderRadius: 2, background: '#ef4444', display: 'inline-block' }} />
          {t('hist.perda_clip')}
        </span>
      </div>
    </div>
  )
}
