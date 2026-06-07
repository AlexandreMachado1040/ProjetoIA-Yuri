import {
  ComposedChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine, ReferenceArea,
} from 'recharts'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const grid = payload.find(p => p.dataKey === 'grid')?.value ?? 0
  const loss = payload.find(p => p.dataKey === 'loss')?.value ?? 0
  const arr  = grid + loss
  const pct  = arr > 0 ? ((loss / arr) * 100).toFixed(1) : '0.0'
  return (
    <div style={{
      background: '#0d1530', border: '1px solid rgba(0,95,255,0.3)',
      borderRadius: 6, padding: '8px 12px', fontSize: 12,
    }}>
      <p style={{ color: '#94a3b8', marginBottom: 4 }}>Irradiância: {label} de G_STC</p>
      <p style={{ color: '#00C8FF' }}>E_Grid:  {grid.toFixed(0)} kWh</p>
      <p style={{ color: '#ef4444' }}>Perda inv.: {loss.toFixed(0)} kWh ({pct}%)</p>
      <p style={{ color: '#e2e8f0', borderTop: '1px solid rgba(255,255,255,0.1)', marginTop: 4, paddingTop: 4 }}>
        E_Array total: {arr.toFixed(0)} kWh
      </p>
    </div>
  )
}

export default function HistogramaChart({ bins, histArr, histGrid }) {
  if (!bins || bins.length === 0) return null

  const totalArr  = histArr.reduce((s, v) => s + v, 0)
  const totalLoss = histArr.reduce((s, v, i) => s + v - (histGrid[i] ?? 0), 0)
  const clipPct   = totalArr > 0 ? ((totalLoss / totalArr) * 100).toFixed(1) : '0.0'

  const data = bins
    .map((b, i) => {
      const arr  = +(histArr[i]  ?? 0)
      const grid = +(histGrid[i] ?? 0)
      const loss = +(arr - grid).toFixed(1)
      const pct  = totalArr > 0 ? (arr / totalArr) * 100 : 0
      return { bin: `${b}%`, grid: +grid.toFixed(1), loss, pct }
    })
    .filter(d => d.pct >= 0.5)

  // Bin de 100% = G_STC (irradiância nominal)
  const stcBin  = '100%'
  const overBin = '110%'

  return (
    <div className="chart-card">
      <h3>Histograma de Potência (kWh por bin de irradiância)</h3>
      <p className="chart-sub">
        Distribuição de energia por nível de irradiância no plano inclinado &nbsp;|&nbsp;
        Perdas inversor: <strong style={{ color: parseFloat(clipPct) > 3 ? '#ef4444' : parseFloat(clipPct) > 0.2 ? '#f59e0b' : '#10b981' }}>{clipPct}%</strong>
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 16, right: 24, left: 10, bottom: 36 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />

          <XAxis dataKey="bin" angle={-45} textAnchor="end" interval={0} tick={{ fontSize: 11 }} />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={v => v === 0 ? '0' : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : Math.round(v).toString()}
            label={{ value: 'kWh', angle: -90, position: 'insideLeft', offset: 10, fill: '#94a3b8', fontSize: 11 }}
          />

          <Tooltip content={<CustomTooltip />} />
          <Legend verticalAlign="top" />

          {/* Zona acima de G_STC (overirradiance + clipping) */}
          {data.some(d => d.bin === overBin) && (
            <ReferenceArea
              x1={stcBin} x2={overBin}
              fill="rgba(239,68,68,0.08)"
              stroke="rgba(239,68,68,0.2)"
              label={{ value: 'Sobreirradiância', position: 'insideTopLeft', fontSize: 9, fill: '#ef4444' }}
            />
          )}

          {/* Linha de referência G_STC — potência projetada nominal */}
          {data.some(d => d.bin === stcBin) && (
            <ReferenceLine x={stcBin} stroke="#10b981" strokeWidth={2}
              label={{ value: 'G_STC (1000 W/m²)', position: 'top', fontSize: 10, fill: '#10b981' }} />
          )}

          {/* Barra base — E_Grid */}
          <Bar dataKey="grid" name="E_Grid (rede)"
            stackId="a" fill="#00C8FF" radius={[0,0,2,2]} />

          {/* Barra topo — Perda inversor */}
          <Bar dataKey="loss" name="Perda inversor"
            stackId="a" fill="#ef4444" opacity={0.80} radius={[3,3,0,0]} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
