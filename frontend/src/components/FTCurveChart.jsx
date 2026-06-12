import { useState, useEffect } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Label, Legend,
} from 'recharts'
import { useI18n } from '../i18n.jsx'

const WORKER_URL = 'https://aurova-motor.alexandreclm.workers.dev'

// Ponto ótimo destacado numa curva específica
function makeDot(optimalX, keyX, keyY, fill) {
  return function OptimalDot(props) {
    const { cx, cy, payload } = props
    if (payload[keyX] !== optimalX) return null
    return (
      <g key={`opt-${cx}-${cy}`}>
        <circle cx={cx} cy={cy} r={8} fill={fill} stroke="#0a0f20" strokeWidth={1.5} />
        <circle cx={cx} cy={cy} r={3.5} fill="#fff" />
      </g>
    )
  }
}

function yDomain(data, keys) {
  const vals = data.flatMap(d => keys.map(k => d[k]).filter(v => v != null))
  const min  = Math.min(...vals)
  const max  = Math.max(...vals)
  const pad  = (max - min) * 0.1 || 0.005
  return [+(min - pad).toFixed(4), +(max + pad).toFixed(4)]
}

export default function FTCurveChart({ inputParams, resultado }) {
  const { t } = useI18n()
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  const { FT_frontal, FT_bifacial, ganho_bif_pct } = resultado ?? {}
  const isBifacial   = ganho_bif_pct > 0 && FT_bifacial && FT_bifacial !== FT_frontal
  const ganhoFactor  = isBifacial ? (1 + ganho_bif_pct / 100) : 1

  const key = inputParams
    ? `${inputParams.lat}_${inputParams.lon}_${inputParams.tz}_${inputParams.tilt}_${inputParams.az}`
    : null

  useEffect(() => {
    if (!inputParams) return
    setLoading(true)
    setError(null)
    const { lat, lon, tz, tilt, az } = inputParams
    fetch(`${WORKER_URL}/ft-curve?lat=${lat}&lon=${lon}&tz=${tz}&tilt=${tilt}&az=${az}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(String(e)); setLoading(false) })
  }, [key])

  if (!inputParams) return null
  if (loading) return (
    <div className="chart-card" style={{ minHeight: 180, display:'flex', alignItems:'center', justifyContent:'center' }}>
      <p style={{ color: 'var(--text-sub)' }}>{t('ft.calculando')}</p>
    </div>
  )
  if (error || !data) return null

  // Monta dados com curva frontal + curva bifacial estimada
  const tiltData = data.tilt_curve.map(([t, ft]) => ({
    tilt:    t,
    frontal: ft,
    bifacial: isBifacial ? +(ft * ganhoFactor).toFixed(4) : undefined,
  }))

  const azData = data.az_curve.map(([a, ft]) => ({
    az:      a,
    frontal: ft,
    bifacial: isBifacial ? +(ft * ganhoFactor).toFixed(4) : undefined,
  }))

  const FT_bif_opt_tilt = isBifacial
    ? +(data.FT_optimal_tilt * ganhoFactor).toFixed(4) : null
  const FT_bif_opt_az = isBifacial
    ? +(data.FT_optimal_az   * ganhoFactor).toFixed(4) : null

  const tiltOptDiff = data.optimal_tilt !== data.current_tilt
  const azOptDiff   = data.optimal_az   !== data.current_az

  const domainTilt = yDomain(tiltData, isBifacial ? ['frontal','bifacial'] : ['frontal'])
  const domainAz   = yDomain(azData,   isBifacial ? ['frontal','bifacial'] : ['frontal'])

  const dotFrontTilt = makeDot(data.optimal_tilt, 'tilt', 'frontal', '#00C8FF')
  const dotBifTilt   = makeDot(data.optimal_tilt, 'tilt', 'bifacial', '#10b981')
  const dotFrontAz   = makeDot(data.optimal_az,   'az',   'frontal', '#005FFF')
  const dotBifAz     = makeDot(data.optimal_az,   'az',   'bifacial', '#10b981')

  const tooltipStyle = {
    background: '#0d1530',
    border: '1px solid rgba(0,95,255,0.3)',
    fontSize: 12, borderRadius: 6,
  }

  const formatTooltip = (v, name) => [v?.toFixed(4) ?? '—', name]

  return (
    <div className="chart-card">
      <h3>{t('ft.titulo')}</h3>
      <p className="chart-sub">
        {t('ft.atual_f')} <strong>{data.FT_current}</strong>
        {isBifacial && (
          <> &nbsp;·&nbsp;
            {t('ft.atual_b')} <strong style={{ color: '#10b981' }}>{FT_bifacial}</strong>
            &nbsp;(+{ganho_bif_pct}%)
          </>
        )}
        &nbsp;|&nbsp;
        {t('ft.otimo_tilt', { v: data.optimal_tilt })}&nbsp;
        {t('ft.frontal')} <strong style={{ color: '#00C8FF' }}>{data.FT_optimal_tilt}</strong>
        {isBifacial && <> · {t('ft.bifacial')} <strong style={{ color: '#10b981' }}>{FT_bif_opt_tilt}</strong></>}
        &nbsp;|&nbsp;
        {t('ft.otimo_az', { v: data.optimal_az })}&nbsp;
        {t('ft.frontal')} <strong style={{ color: '#005FFF' }}>{data.FT_optimal_az}</strong>
        {isBifacial && <> · {t('ft.bifacial')} <strong style={{ color: '#10b981' }}>{FT_bif_opt_az}</strong></>}
      </p>

      {isBifacial && (
        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
          {t('ft.estimada', { v: ganho_bif_pct })}
        </p>
      )}

      <div className="ft-grid">

        {/* ── FT × Inclinação ── */}
        <div>
          <p style={{ textAlign:'center', fontSize:'0.8rem', color:'var(--text-sub)', marginBottom:'0.25rem' }}>
            {t('ft.x_tilt', { v: data.current_az })}
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={tiltData} margin={{ top: 16, right: 20, left: 0, bottom: 28 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="tilt" tick={{ fontSize: 10 }}>
                <Label value={t('ft.incl')} position="insideBottom" offset={-16} fill="#94a3b8" fontSize={11} />
              </XAxis>
              <YAxis domain={domainTilt} tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(3)} />
              <Tooltip formatter={formatTooltip} labelFormatter={v => `Tilt: ${v}°`} contentStyle={tooltipStyle} />
              <Legend verticalAlign="top" wrapperStyle={{ fontSize: '0.75rem' }} />

              {/* Linha atual */}
              <ReferenceLine x={data.current_tilt} stroke="#f59e0b" strokeDasharray="5 3"
                label={{ value: t('ft.atual', { v: data.current_tilt }), position: 'insideTopLeft', fontSize: 9, fill: '#f59e0b' }} />

              {/* Linha ótima */}
              {tiltOptDiff && (
                <ReferenceLine x={data.optimal_tilt} stroke="#10b981" strokeDasharray="4 2"
                  label={{ value: t('ft.otimo', { v: data.optimal_tilt }), position: 'insideTopRight', fontSize: 9, fill: '#10b981' }} />
              )}

              {/* Curva frontal */}
              <Line
                type="monotone" dataKey="frontal" name={t('ft.serie_f')}
                stroke="#00C8FF" strokeWidth={2}
                dot={dotFrontTilt} activeDot={{ r: 4 }}
              />

              {/* Curva bifacial */}
              {isBifacial && (
                <Line
                  type="monotone" dataKey="bifacial" name={t('ft.serie_b')}
                  stroke="#10b981" strokeWidth={2} strokeDasharray="6 3"
                  dot={dotBifTilt} activeDot={{ r: 4 }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* ── FT × Azimute ── */}
        <div>
          <p style={{ textAlign:'center', fontSize:'0.8rem', color:'var(--text-sub)', marginBottom:'0.25rem' }}>
            {t('ft.x_az', { v: data.current_tilt })}
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={azData} margin={{ top: 16, right: 20, left: 0, bottom: 28 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="az" tick={{ fontSize: 10 }}>
                <Label value={t('ft.azimute')} position="insideBottom" offset={-16} fill="#94a3b8" fontSize={11} />
              </XAxis>
              <YAxis domain={domainAz} tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(3)} />
              <Tooltip formatter={formatTooltip} labelFormatter={v => `Az: ${v}°`} contentStyle={tooltipStyle} />
              <Legend verticalAlign="top" wrapperStyle={{ fontSize: '0.75rem' }} />

              {/* Linha atual */}
              <ReferenceLine x={data.current_az} stroke="#f59e0b" strokeDasharray="5 3"
                label={{ value: t('ft.atual', { v: data.current_az }), position: 'insideTopLeft', fontSize: 9, fill: '#f59e0b' }} />

              {/* Linha ótima */}
              {azOptDiff && (
                <ReferenceLine x={data.optimal_az} stroke="#10b981" strokeDasharray="4 2"
                  label={{ value: t('ft.otimo', { v: data.optimal_az }), position: 'insideTopRight', fontSize: 9, fill: '#10b981' }} />
              )}

              {/* Curva frontal */}
              <Line
                type="monotone" dataKey="frontal" name={t('ft.serie_f')}
                stroke="#005FFF" strokeWidth={2}
                dot={dotFrontAz} activeDot={{ r: 4 }}
              />

              {/* Curva bifacial */}
              {isBifacial && (
                <Line
                  type="monotone" dataKey="bifacial" name={t('ft.serie_b')}
                  stroke="#10b981" strokeWidth={2} strokeDasharray="6 3"
                  dot={dotBifAz} activeDot={{ r: 4 }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>

      </div>
    </div>
  )
}
