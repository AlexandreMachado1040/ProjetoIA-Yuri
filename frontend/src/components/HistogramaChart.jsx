import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts'

export default function HistogramaChart({ bins, histArr, histGrid }) {
  if (!bins || bins.length === 0) return null

  // Agrupa bins < 0.5% do total para exibição limpa
  const totalArr = histArr.reduce((s, v) => s + v, 0)
  const data = bins
    .map((b, i) => ({
      bin:  `${b}%`,
      arr:  +(histArr[i]  ?? 0).toFixed(1),
      grid: +(histGrid[i] ?? 0).toFixed(1),
      pct:  totalArr > 0 ? (histArr[i] / totalArr) * 100 : 0,
    }))
    .filter(d => d.pct >= 0.5)   // mesma filtragem do PDF

  return (
    <div className="chart-card">
      <h3>Histograma de Potência (kWh por bin de irradiância)</h3>
      <p className="chart-sub">Distribuição de energia por nível de irradiância no plano inclinado</p>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 30 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="bin" angle={-45} textAnchor="end" interval={1}
                 tick={{ fontSize: 11 }} />
          <YAxis unit=" kWh" />
          <Tooltip formatter={v => [`${v.toFixed(0)} kWh`]} />
          <Legend verticalAlign="top" />
          <Bar dataKey="arr"  name="E_Array (P_arr)"  fill="#0077EE" radius={[2,2,0,0]} />
          <Bar dataKey="grid" name="E_Grid (rede)"    fill="#00C8FF" radius={[2,2,0,0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
