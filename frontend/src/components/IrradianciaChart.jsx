import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts'

const MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

export default function IrradianciaChart({ monthlyGHI, monthlyGf, monthlyGb, bifacial }) {
  if (!monthlyGHI) return null

  const data = MESES.map((m, i) => ({
    mes: m,
    GHI: +(monthlyGHI[i]     ?? 0).toFixed(1),
    Gf:  +(monthlyGf?.[i]    ?? 0).toFixed(1),
    Gb:  +(monthlyGb?.[i]    ?? 0).toFixed(1),
  }))

  return (
    <div className="chart-card">
      <h3>Irradiância Mensal (kWh/m²)</h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="mes" />
          <YAxis unit=" kWh" />
          <Tooltip formatter={v => [`${v} kWh/m²`]} />
          <Legend />
          <Bar dataKey="GHI"  name="GHI (horizontal)"     fill="#90CAF9" radius={[2,2,0,0]} />
          {monthlyGf && (
            <Bar dataKey="Gf" name="G frontal (inclinado)" fill="#1976D2" radius={[2,2,0,0]} />
          )}
          {bifacial && monthlyGb && (
            <Bar dataKey="Gb" name="G bifacial"            fill="#2E7D32" radius={[2,2,0,0]} />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
