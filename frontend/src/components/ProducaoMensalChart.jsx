import {
  ComposedChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine, ResponsiveContainer, Cell,
} from 'recharts'
import { useI18n } from '../i18n.jsx'

// Paleta para empilhar sub-arranjos
const CORES_SA = ['#00C8FF', '#10b981', '#f59e0b', '#a855f7', '#ef4444', '#0077EE', '#14b8a6', '#eab308']

export default function ProducaoMensalChart({ monthlyGridKwh, monthlyArrKwh, subarrays }) {
  const { t, meses: MESES } = useI18n()
  // ── Modo planta: barras empilhadas por sub-arranjo ──────────────────────────
  if (subarrays?.length > 0) {
    const data = MESES.map((m, i) => {
      const row = { mes: m, total: 0 }
      subarrays.forEach(s => {
        const v = +(((s.monthly_E_grid?.[i]) ?? 0) / 1000).toFixed(2)
        row[`sa${s.idx}`] = v
        row.total += v
      })
      row.total = +row.total.toFixed(2)
      return row
    })
    const media = data.reduce((acc, d) => acc + d.total, 0) / 12

    return (
      <div className="chart-card">
        <h3>{t('prod.titulo_sa')}</h3>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="mes" />
            <YAxis unit=" MWh" />
            <Tooltip formatter={(v, n) => [`${v} MWh`, n]} />
            <Legend wrapperStyle={{ fontSize: '0.75rem' }} />
            <ReferenceLine y={+media.toFixed(2)} stroke="#f59e0b" strokeDasharray="5 3"
              label={{ value: t('prod.media', { v: media.toFixed(2) }), position: 'right', fontSize: 11, fill: '#f59e0b' }} />
            {subarrays.map((s, k) => (
              <Bar
                key={s.idx}
                dataKey={`sa${s.idx}`}
                name={`SA${s.idx} · ${s.inversor_nome}`}
                stackId="sa"
                fill={CORES_SA[k % CORES_SA.length]}
                radius={k === subarrays.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    )
  }

  // ── Modo sub-arranjo único (comportamento original) ─────────────────────────
  if (!monthlyGridKwh) return null

  const gridMwh = monthlyGridKwh.map(v => +(v / 1000).toFixed(2))
  const arrMwh  = monthlyArrKwh  ? monthlyArrKwh.map(v => +(v / 1000).toFixed(2)) : null
  const media   = gridMwh.reduce((s, v) => s + v, 0) / 12

  const data = MESES.map((m, i) => ({
    mes:  m,
    grid: gridMwh[i],
    arr:  arrMwh ? arrMwh[i] : null,
  }))

  return (
    <div className="chart-card">
      <h3>{t('prod.titulo')}</h3>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="mes" />
          <YAxis unit=" MWh" />
          <Tooltip formatter={v => [`${v} MWh`]} />
          <Legend />
          <ReferenceLine y={+media.toFixed(2)} stroke="#f59e0b" strokeDasharray="5 3"
                         label={{ value: t('prod.media', { v: media.toFixed(2) }), position: 'right',
                                  fontSize: 11, fill: '#f59e0b' }} />
          {arrMwh && (
            <Bar dataKey="arr" name={t('prod.earr')} fill="#0077EE" radius={[3,3,0,0]} />
          )}
          <Bar dataKey="grid" name={t('prod.egrid')} radius={[3,3,0,0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.grid >= media ? '#00C8FF' : '#005FFF'} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
