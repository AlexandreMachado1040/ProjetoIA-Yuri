import { useState } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Label,
} from 'recharts'

const MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
               'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

export default function HourlyEgridChart({ hourlyEgridMonth }) {
  // Mês padrão: o de maior produção diária
  const totaisDia = (hourlyEgridMonth ?? []).map(h => h.reduce((s, v) => s + v, 0))
  const mesPadrao = totaisDia.length
    ? totaisDia.indexOf(Math.max(...totaisDia)) : 0
  const [mes, setMes] = useState(mesPadrao)

  if (!hourlyEgridMonth || hourlyEgridMonth.length !== 12) return null

  const perfil = hourlyEgridMonth[mes] ?? []
  const data = perfil.map((v, h) => ({ hora: h, egrid: +(+v).toFixed(2) }))
  const totalDia = perfil.reduce((s, v) => s + v, 0)
  const pico = perfil.length ? Math.max(...perfil) : 0

  return (
    <div className="chart-card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ margin: 0 }}>E_Grid Horário — Dia Representativo</h3>
        <select
          value={mes}
          onChange={e => setMes(Number(e.target.value))}
          style={{
            background: '#0d1530', color: 'var(--text-sub)',
            border: '1px solid rgba(0,95,255,0.3)', borderRadius: 6,
            padding: '4px 8px', fontSize: '0.8rem',
          }}
        >
          {MESES.map((m, i) => <option key={i} value={i}>{m}</option>)}
        </select>
      </div>

      <p className="chart-sub">
        {MESES[mes]} · Total no dia: <strong>{totalDia.toFixed(1)} kWh</strong>
        &nbsp;·&nbsp; Pico: <strong>{pico.toFixed(1)} kW</strong>
      </p>

      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data} margin={{ top: 10, right: 24, left: 0, bottom: 20 }}>
          <defs>
            <linearGradient id="egridFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00C8FF" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#005FFF" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis dataKey="hora" tick={{ fontSize: 11 }} tickFormatter={h => `${h}h`}>
            <Label value="Hora do dia" position="insideBottom" offset={-12} fill="#94a3b8" fontSize={11} />
          </XAxis>
          <YAxis tick={{ fontSize: 11 }} unit=" kW" />
          <Tooltip
            formatter={v => [`${v} kWh`, 'E_Grid']}
            labelFormatter={h => `${h}:00 – ${h}:59`}
            contentStyle={{ background: '#0d1530', border: '1px solid rgba(0,95,255,0.3)', borderRadius: 6, fontSize: 12 }}
          />
          <Area type="monotone" dataKey="egrid" name="E_Grid" stroke="#00C8FF"
            strokeWidth={2} fill="url(#egridFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
