import { useState, useEffect } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Label, ReferenceLine,
} from 'recharts'
import { useI18n } from '../i18n.jsx'

// Dia do ano (1-365) → "dd/mm" (ano não bissexto)
const CUM = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
function doyToLabel(doy) {
  let m = 11
  while (m > 0 && doy <= CUM[m]) m--
  const dia = doy - CUM[m]
  return `${String(dia).padStart(2, '0')}/${String(m + 1).padStart(2, '0')}`
}

// Apresentação pura: a busca do /daily (incluindo as horas medidas do TGY
// SONDA) é feita uma única vez no ResultsDashboard e compartilhada com o
// ExploradorDiario via props.
export default function DailyEgridChart({ daily: data, medido, loading }) {
  const { t, meses: MES_ABREV } = useI18n()
  const [diaSel, setDiaSel] = useState(0)   // índice 0-364

  useEffect(() => {
    const de = data?.daily_egrid ?? []
    if (de.length) setDiaSel(de.indexOf(Math.max(...de)))
  }, [data])

  if (loading) return (
    <div className="chart-card" style={{ minHeight: 160, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <p style={{ color: 'var(--text-sub)' }}>{t('daily.calculando')}</p>
    </div>
  )
  if (!data?.daily_egrid) return null

  const daily = data.daily_egrid
  const dailyData = daily.map((v, i) => ({ doy: i + 1, egrid: v, label: doyToLabel(i + 1) }))
  const totalAno = daily.reduce((s, v) => s + v, 0)
  const media    = totalAno / daily.length
  const idxPico  = daily.indexOf(Math.max(...daily))
  const idxMin   = daily.indexOf(Math.min(...daily))

  const perfil = data.daily_hourly?.[diaSel] ?? []
  const horaData = perfil.map((v, h) => ({ hora: h, egrid: +(+v).toFixed(2) }))
  const totalDia = perfil.reduce((s, v) => s + v, 0)
  const pico     = perfil.length ? Math.max(...perfil) : 0

  // Marcas de mês no eixo X (início de cada mês)
  const ticks = CUM.map(c => c + 1)

  return (
    <div className="chart-card">
      <h3>
        {t('daily.titulo')}
        {medido && (
          <span style={{
            marginLeft: 10, fontSize: '0.68rem', fontWeight: 600,
            background: 'rgba(16,185,129,0.14)', border: '1px solid rgba(16,185,129,0.4)',
            color: '#34d399', borderRadius: 5, padding: '2px 8px',
            verticalAlign: 2, whiteSpace: 'nowrap',
          }}>
            {t('daily.medido', { sigla: medido })}
          </span>
        )}
      </h3>
      <p className="chart-sub">
        {medido ? t('daily.medido_sub', { sigla: medido }) : ''}
        {t('daily.total')} <strong>{(totalAno / 1000).toFixed(1)} MWh</strong>
        &nbsp;·&nbsp; {t('daily.media_dia')} <strong>{media.toFixed(1)} kWh</strong>
        &nbsp;·&nbsp; {t('daily.pico')} <strong>{daily[idxPico].toFixed(1)} kWh</strong> ({doyToLabel(idxPico + 1)})
        &nbsp;·&nbsp; {t('daily.minimo')} <strong>{daily[idxMin].toFixed(1)} kWh</strong> ({doyToLabel(idxMin + 1)})
      </p>

      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={dailyData} margin={{ top: 10, right: 24, left: 0, bottom: 20 }}
          onClick={e => { if (e?.activeTooltipIndex != null) setDiaSel(e.activeTooltipIndex) }}>
          <defs>
            <linearGradient id="dailyFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity={0.45} />
              <stop offset="100%" stopColor="#10b981" stopOpacity={0.04} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis dataKey="doy" ticks={ticks} tick={{ fontSize: 10 }}
            tickFormatter={d => MES_ABREV[CUM.findIndex(c => c + 1 === d)] ?? ''}>
            <Label value={t('daily.dia_ano')} position="insideBottom" offset={-12} fill="#94a3b8" fontSize={11} />
          </XAxis>
          <YAxis tick={{ fontSize: 11 }} unit=" kWh" />
          <Tooltip
            formatter={v => [`${(+v).toFixed(1)} kWh`, t('daily.egrid_dia')]}
            labelFormatter={d => doyToLabel(d)}
            contentStyle={{ background: '#0d1530', border: '1px solid rgba(0,95,255,0.3)', borderRadius: 6, fontSize: 12 }} />
          <ReferenceLine y={+media.toFixed(1)} stroke="#f59e0b" strokeDasharray="5 3"
            label={{ value: t('daily.media_ref', { v: media.toFixed(0) }), position: 'right', fontSize: 10, fill: '#f59e0b' }} />
          <ReferenceLine x={diaSel + 1} stroke="#00C8FF" strokeWidth={1.5}
            label={{ value: doyToLabel(diaSel + 1), position: 'top', fontSize: 10, fill: '#00C8FF' }} />
          <Area type="monotone" dataKey="egrid" stroke="#10b981" strokeWidth={1.5} fill="url(#dailyFill)" />
        </AreaChart>
      </ResponsiveContainer>

      {/* Seletor de dia + perfil horário */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '12px 2px 6px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.82rem', color: 'var(--text-sub)' }}>
          {t('daily.dia')} <strong style={{ color: '#00C8FF' }}>{doyToLabel(diaSel + 1)}</strong>
        </span>
        <input
          type="range" min={1} max={365} value={diaSel + 1}
          onChange={e => setDiaSel(Number(e.target.value) - 1)}
          style={{ flex: 1, minWidth: 160, accentColor: '#00C8FF' }}
        />
        <span style={{ fontSize: '0.8rem', color: 'var(--text-sub)' }}>
          {t('daily.total_dia')} <strong>{totalDia.toFixed(1)} kWh</strong> · {t('daily.pico_dia')} <strong>{pico.toFixed(1)} kW</strong>
        </span>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={horaData} margin={{ top: 6, right: 24, left: 0, bottom: 20 }}>
          <defs>
            <linearGradient id="dayHourFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00C8FF" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#005FFF" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis dataKey="hora" tick={{ fontSize: 11 }} tickFormatter={h => `${h}h`}>
            <Label value={t('daily.perfil', { v: doyToLabel(diaSel + 1) })} position="insideBottom" offset={-12} fill="#94a3b8" fontSize={11} />
          </XAxis>
          <YAxis tick={{ fontSize: 11 }} unit=" kW" />
          <Tooltip formatter={v => [`${v} kWh`, 'E_Grid']} labelFormatter={h => `${h}:00 – ${h}:59`}
            contentStyle={{ background: '#0d1530', border: '1px solid rgba(0,95,255,0.3)', borderRadius: 6, fontSize: 12 }} />
          <Area type="monotone" dataKey="egrid" stroke="#00C8FF" strokeWidth={2} fill="url(#dayHourFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
