import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine, ResponsiveContainer, Cell,
} from 'recharts'

const MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

export default function ProducaoMensalChart({ monthlyGridKwh, monthlyArrKwh }) {
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
      <h3>Produção Mensal (MWh)</h3>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="mes" />
          <YAxis unit=" MWh" />
          <Tooltip formatter={v => [`${v} MWh`]} />
          <Legend />
          <ReferenceLine y={+media.toFixed(2)} stroke="#f59e0b" strokeDasharray="5 3"
                         label={{ value: `Média ${media.toFixed(2)} MWh`, position: 'right',
                                  fontSize: 11, fill: '#f59e0b' }} />
          {arrMwh && (
            <Bar dataKey="arr" name="E_Array (DC)" fill="#0077EE" radius={[3,3,0,0]} />
          )}
          <Bar dataKey="grid" name="E_Grid (rede AC)" radius={[3,3,0,0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.grid >= media ? '#00C8FF' : '#005FFF'} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
