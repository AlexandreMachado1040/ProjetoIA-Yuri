import { useState, useEffect } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Label,
} from 'recharts'

const WORKER_URL = 'https://aurova-motor.alexandreclm.workers.dev'

export default function FTCurveChart({ inputParams }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

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
      <p style={{ color: 'var(--text-sub)' }}>Calculando otimização de orientação…</p>
    </div>
  )
  if (error || !data) return null

  const tiltData = data.tilt_curve.map(([t, ft]) => ({ tilt: t, FT: ft }))
  const azData   = data.az_curve.map(([a, ft])   => ({ az: a,   FT: ft }))

  const diffTilt = ((data.FT_optimal_tilt - data.FT_current) / data.FT_current * 100).toFixed(1)
  const diffAz   = ((data.FT_optimal_az   - data.FT_current) / data.FT_current * 100).toFixed(1)

  return (
    <div className="chart-card">
      <h3>Otimização de Orientação — Fator de Transposição</h3>
      <p className="chart-sub">
        FT atual: <strong>{data.FT_current}</strong> &nbsp;|&nbsp;
        Ótimo por inclinação: <strong>{data.FT_optimal_tilt}</strong> @ {data.optimal_tilt}° (+{diffTilt}%) &nbsp;|&nbsp;
        Ótimo por azimute: <strong>{data.FT_optimal_az}</strong> @ {data.optimal_az}° (+{diffAz}%)
      </p>
      <div className="ft-grid">
        <div>
          <p style={{ textAlign:'center', fontSize:'0.8rem', color:'var(--text-sub)', marginBottom:'0.25rem' }}>
            FT × Inclinação &nbsp;(azimute fixo: {data.current_az}°)
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={tiltData} margin={{ top: 8, right: 20, left: 0, bottom: 28 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="tilt" tick={{ fontSize: 10 }}>
                <Label value="Inclinação [°]" position="insideBottom" offset={-16} fill="#94a3b8" fontSize={11} />
              </XAxis>
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10 }} />
              <Tooltip formatter={v => [v.toFixed(4), 'FT']} labelFormatter={v => `Tilt: ${v}°`} />
              <Line type="monotone" dataKey="FT" stroke="#00C8FF" strokeWidth={2} dot={false} />
              <ReferenceLine x={data.current_tilt} stroke="#f59e0b" strokeDasharray="5 3"
                label={{ value: `atual ${data.current_tilt}°`, position: 'top', fontSize: 9, fill: '#f59e0b' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div>
          <p style={{ textAlign:'center', fontSize:'0.8rem', color:'var(--text-sub)', marginBottom:'0.25rem' }}>
            FT × Azimute &nbsp;(inclinação fixa: {data.current_tilt}°)
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={azData} margin={{ top: 8, right: 20, left: 0, bottom: 28 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="az" tick={{ fontSize: 10 }}>
                <Label value="Azimute [°]" position="insideBottom" offset={-16} fill="#94a3b8" fontSize={11} />
              </XAxis>
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10 }} />
              <Tooltip formatter={v => [v.toFixed(4), 'FT']} labelFormatter={v => `Az: ${v}°`} />
              <Line type="monotone" dataKey="FT" stroke="#005FFF" strokeWidth={2} dot={false} />
              <ReferenceLine x={data.current_az} stroke="#f59e0b" strokeDasharray="5 3"
                label={{ value: `atual ${data.current_az}°`, position: 'top', fontSize: 9, fill: '#f59e0b' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
