import { useMemo, useState } from 'react'
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Label,
} from 'recharts'

// Explorador Diário — curvas de irradiância GHI/DNI/DHI (+ céu limpo) de cada
// dia do ano, com calendário em mapa de calor e KPIs (HSP, picos, E_Grid).
// Dados: daily_irr do /daily — medidos (SONDA) ou sintetizados (NASA).

const DIAS_MES   = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
const CUM        = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
const MESES      = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

const CURVAS = [
  { id: 'ghi',    rotulo: 'GHI',       cor: '#f5a623' },
  { id: 'dni',    rotulo: 'DNI',       cor: '#00C8FF' },
  { id: 'dhi',    rotulo: 'DHI',       cor: '#a78bfa' },
  { id: 'ghi_cs', rotulo: 'Céu limpo', cor: 'rgba(226,232,240,0.55)' },
]

const fmt = (v, dec = 0) => (+v).toLocaleString('pt-BR', {
  minimumFractionDigits: dec, maximumFractionDigits: dec,
})

export default function ExploradorDiario({ daily, medido, loading }) {
  const [diaSel, setDiaSel] = useState(() => {
    // Abre no dia de maior GHI quando os dados chegarem (ver useMemo abaixo)
    return null
  })
  const [curvas, setCurvas] = useState({ ghi: true, dni: true, dhi: true, ghi_cs: false })

  const irr = daily?.daily_irr

  // Totais diários de GHI (kWh/m²) — alimentam o heatmap do calendário
  const ghiDiario = useMemo(() => {
    if (!irr?.ghi) return null
    return irr.ghi.map(dia => dia.reduce((s, v) => s + v, 0) / 1000)
  }, [irr])

  if (loading) return (
    <div className="chart-card" style={{ minHeight: 140, display: 'flex',
      alignItems: 'center', justifyContent: 'center' }}>
      <p style={{ color: 'var(--text-sub)' }}>Carregando explorador diário…</p>
    </div>
  )
  if (!irr?.ghi || !ghiDiario) return null

  const idx = diaSel ?? ghiDiario.indexOf(Math.max(...ghiDiario))
  const mes = CUM.findIndex((c, i) => idx < c + DIAS_MES[i])
  const diaDoMes = idx - CUM[mes] + 1

  const ghiMax = Math.max(...ghiDiario)
  const perfil = Array.from({ length: 24 }, (_, h) => ({
    hora: h,
    ghi:    irr.ghi[idx][h],
    dni:    irr.dni[idx][h],
    dhi:    irr.dhi[idx][h],
    ghi_cs: irr.ghi_cs[idx][h],
  }))

  const totalGHI = ghiDiario[idx]
  const totalDNI = irr.dni[idx].reduce((s, v) => s + v, 0) / 1000
  const totalDHI = irr.dhi[idx].reduce((s, v) => s + v, 0) / 1000
  const picoGHI  = Math.max(...irr.ghi[idx])
  const hPico    = irr.ghi[idx].indexOf(picoGHI)
  const egridDia = daily.daily_egrid?.[idx]

  const setMes = (novoMes) => {
    const d = Math.min(diaDoMes, DIAS_MES[novoMes])
    setDiaSel(CUM[novoMes] + d - 1)
  }
  const navDia = (delta) => setDiaSel(((idx + delta) % 365 + 365) % 365)

  const rotuloDia = `${String(diaDoMes).padStart(2, '0')}/${String(mes + 1).padStart(2, '0')}`

  return (
    <div className="chart-card">
      <h3>
        Explorador Diário — Irradiância hora a hora
        {medido && (
          <span style={{
            marginLeft: 10, fontSize: '0.68rem', fontWeight: 600,
            background: 'rgba(16,185,129,0.14)', border: '1px solid rgba(16,185,129,0.4)',
            color: '#34d399', borderRadius: 5, padding: '2px 8px',
            verticalAlign: 2, whiteSpace: 'nowrap',
          }}>
            ● dias medidos — SONDA {medido}
          </span>
        )}
      </h3>
      <p className="chart-sub">
        {medido
          ? 'Curvas medidas minuto a minuto (agregadas por hora) na estação SONDA.'
          : 'Curvas sintetizadas da climatologia NASA POWER (Collares-Pereira + Erbs).'}
        {' '}Clique num dia do calendário ou navegue com as setas.
      </p>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        {/* ── Calendário (mapa de calor de GHI) ── */}
        <div style={{ minWidth: 218 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <button type="button" onClick={() => setMes((mes + 11) % 12)} style={botaoNav}>‹</button>
            <select value={mes} onChange={e => setMes(+e.target.value)} style={{
              flex: 1, background: 'rgba(0,95,255,0.10)', color: 'var(--text-main, #e2e8f0)',
              border: '1px solid rgba(0,95,255,0.30)', borderRadius: 6,
              padding: '4px 8px', fontSize: '0.8rem', cursor: 'pointer',
            }}>
              {MESES.map((m, i) => <option key={m} value={i}>{m}</option>)}
            </select>
            <button type="button" onClick={() => setMes((mes + 1) % 12)} style={botaoNav}>›</button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3 }}>
            {Array.from({ length: DIAS_MES[mes] }, (_, i) => {
              const iDia = CUM[mes] + i
              const frac = ghiMax > 0 ? ghiDiario[iDia] / ghiMax : 0
              const sel  = iDia === idx
              return (
                <button key={i} type="button" onClick={() => setDiaSel(iDia)}
                  title={`${String(i + 1).padStart(2, '0')}/${String(mes + 1).padStart(2, '0')} — GHI ${ghiDiario[iDia].toFixed(2)} kWh/m²`}
                  style={{
                    aspectRatio: '1', fontSize: '0.68rem', cursor: 'pointer',
                    borderRadius: 5, padding: 0,
                    background: `rgba(245,166,35,${(0.06 + 0.5 * frac).toFixed(2)})`,
                    border: sel ? '1.5px solid #00C8FF' : '1px solid rgba(255,255,255,0.07)',
                    color: sel ? '#00C8FF' : 'var(--text-sub, #94a3b8)',
                    fontWeight: sel ? 700 : 400,
                  }}>
                  {i + 1}
                </button>
              )
            })}
          </div>
          <p style={{ fontSize: '0.68rem', color: 'var(--text-sub)', margin: '6px 2px 0' }}>
            Cor da célula ∝ GHI do dia (máx. do ano: {ghiMax.toFixed(2)} kWh/m²)
          </p>

          {/* KPIs do dia */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 10 }}>
            <KpiDia rotulo="GHI / HSP" valor={`${totalGHI.toFixed(2)}`} unidade="kWh/m² · h" cor="#f5a623" />
            <KpiDia rotulo="DNI total" valor={totalDNI.toFixed(2)} unidade="kWh/m²" cor="#00C8FF" />
            <KpiDia rotulo="DHI total" valor={totalDHI.toFixed(2)} unidade="kWh/m²" cor="#a78bfa" />
            <KpiDia rotulo="Pico GHI" valor={fmt(picoGHI)} unidade={`W/m² · ${hPico}h`} cor="#f5a623" />
            {egridDia != null && (
              <KpiDia rotulo="E_Grid do dia" valor={fmt(egridDia, 1)} unidade="kWh" cor="#10b981" larga />
            )}
          </div>
        </div>

        {/* ── Curvas do dia ── */}
        <div style={{ flex: 1, minWidth: 300 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
            <button type="button" onClick={() => navDia(-1)} style={botaoNav}>‹ dia</button>
            <strong style={{ color: '#00C8FF', fontSize: '0.92rem', minWidth: 46, textAlign: 'center' }}>
              {rotuloDia}
            </strong>
            <button type="button" onClick={() => navDia(1)} style={botaoNav}>dia ›</button>
            <span style={{ flex: 1 }} />
            {CURVAS.map(c => (
              <button key={c.id} type="button"
                onClick={() => setCurvas(s => ({ ...s, [c.id]: !s[c.id] }))}
                style={{
                  display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer',
                  background: 'transparent', borderRadius: 6, padding: '3px 8px',
                  border: `1px solid ${curvas[c.id] ? 'rgba(0,95,255,0.35)' : 'rgba(255,255,255,0.08)'}`,
                  opacity: curvas[c.id] ? 1 : 0.4, fontSize: '0.72rem',
                  color: 'var(--text-main, #e2e8f0)',
                }}>
                <span style={{ width: 9, height: 9, borderRadius: '50%', background: c.cor }} />
                {c.rotulo}
              </button>
            ))}
          </div>

          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={perfil} margin={{ top: 8, right: 18, left: 0, bottom: 18 }}>
              <defs>
                <linearGradient id="expGhiFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f5a623" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#f5a623" stopOpacity={0.03} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="hora" tick={{ fontSize: 11 }} tickFormatter={h => `${h}h`}>
                <Label value={`Irradiância — ${rotuloDia}`} position="insideBottom"
                  offset={-10} fill="#94a3b8" fontSize={11} />
              </XAxis>
              <YAxis tick={{ fontSize: 11 }} unit=" W/m²" width={72} />
              <Tooltip
                formatter={(v, nome) => [`${fmt(v)} W/m²`, nome]}
                labelFormatter={h => `${h}:00 – ${h}:59`}
                contentStyle={{ background: '#0d1530', border: '1px solid rgba(0,95,255,0.3)',
                  borderRadius: 6, fontSize: 12 }} />
              {curvas.ghi_cs && (
                <Line type="monotone" dataKey="ghi_cs" name="Céu limpo"
                  stroke="rgba(226,232,240,0.55)" strokeDasharray="6 4"
                  strokeWidth={1.5} dot={false} />
              )}
              {curvas.ghi && (
                <Area type="monotone" dataKey="ghi" name="GHI"
                  stroke="#f5a623" strokeWidth={2} fill="url(#expGhiFill)" />
              )}
              {curvas.dni && (
                <Line type="monotone" dataKey="dni" name="DNI"
                  stroke="#00C8FF" strokeWidth={2} dot={false} />
              )}
              {curvas.dhi && (
                <Line type="monotone" dataKey="dhi" name="DHI"
                  stroke="#a78bfa" strokeWidth={2} dot={false} />
              )}
            </ComposedChart>
          </ResponsiveContainer>

          {/* Tabela horária (só horas com sol) */}
          <details style={{ marginTop: 6 }}>
            <summary style={{ fontSize: '0.78rem', color: 'var(--text-sub)', cursor: 'pointer' }}>
              Tabela horária — {rotuloDia}
            </summary>
            <div style={{ overflowX: 'auto', marginTop: 6 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.76rem' }}>
                <thead>
                  <tr style={{ color: 'var(--text-sub)', textAlign: 'right' }}>
                    <th style={{ textAlign: 'left', padding: '3px 8px' }}>Hora</th>
                    <th style={{ padding: '3px 8px' }}>GHI (W/m²)</th>
                    <th style={{ padding: '3px 8px' }}>DNI (W/m²)</th>
                    <th style={{ padding: '3px 8px' }}>DHI (W/m²)</th>
                    <th style={{ padding: '3px 8px' }}>E_Grid (kW)</th>
                  </tr>
                </thead>
                <tbody>
                  {perfil.filter(p => p.ghi >= 1 || p.dni >= 1).map(p => (
                    <tr key={p.hora} style={{ textAlign: 'right',
                      borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                      <td style={{ textAlign: 'left', padding: '3px 8px',
                        color: 'var(--text-sub)' }}>{String(p.hora).padStart(2, '0')}:00</td>
                      <td style={{ padding: '3px 8px', color: '#f5a623' }}>{fmt(p.ghi)}</td>
                      <td style={{ padding: '3px 8px', color: '#00C8FF' }}>{fmt(p.dni)}</td>
                      <td style={{ padding: '3px 8px', color: '#a78bfa' }}>{fmt(p.dhi)}</td>
                      <td style={{ padding: '3px 8px', color: '#10b981' }}>
                        {daily.daily_hourly?.[idx]?.[p.hora] != null
                          ? fmt(daily.daily_hourly[idx][p.hora], 1) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      </div>
    </div>
  )
}

const botaoNav = {
  background: 'rgba(0,95,255,0.10)', border: '1px solid rgba(0,95,255,0.30)',
  borderRadius: 6, padding: '3px 10px', color: '#7db3ff',
  fontSize: '0.78rem', cursor: 'pointer', whiteSpace: 'nowrap',
}

function KpiDia({ rotulo, valor, unidade, cor, larga }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)',
      borderLeft: `3px solid ${cor}`, borderRadius: 6, padding: '6px 9px',
      gridColumn: larga ? '1 / -1' : 'auto',
    }}>
      <div style={{ fontSize: '0.64rem', color: 'var(--text-sub)' }}>{rotulo}</div>
      <div style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-main, #e2e8f0)' }}>
        {valor} <span style={{ fontSize: '0.62rem', fontWeight: 400,
          color: 'var(--text-sub)' }}>{unidade}</span>
      </div>
    </div>
  )
}
