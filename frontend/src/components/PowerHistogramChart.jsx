import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, ReferenceLine, Label,
} from 'recharts'

export default function PowerHistogramChart({ resultado }) {
  const { hist_power_bins, hist_power_arr, hist_power_grid, P_nom_stc_kWp, P_nom_AC_kW } = resultado ?? {}
  if (!hist_power_bins || hist_power_bins.length === 0) return null

  const data = hist_power_bins
    .slice(0, hist_power_bins.length - 1)
    .map((b, i) => ({
      kW:   +b.toFixed(1),
      arr:  +(hist_power_arr?.[i]  ?? 0),
      grid: +(hist_power_grid?.[i] ?? 0),
    }))
    .filter(d => d.arr > 0)

  const totalMWh   = hist_power_arr?.reduce((s, v) => s + v, 0) ?? 1
  const clippedMWh = hist_power_arr?.[hist_power_arr.length - 1] ?? 0
  const clipPct    = totalMWh > 0 ? ((clippedMWh / totalMWh) * 100).toFixed(1) : '0.0'

  return (
    <div className="chart-card">
      <h3>Distribuição de Saída do Inversor</h3>
      <p className="chart-sub">
        Energia por faixa de potência DC &nbsp;|&nbsp;
        Pnom STC: {P_nom_stc_kWp} kWp &nbsp;|&nbsp;
        Pnom AC: {P_nom_AC_kW} kW &nbsp;|&nbsp;
        Perdas clipping: {clipPct}%
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 30 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis dataKey="kW" tick={{ fontSize: 11 }}>
            <Label value="Potência DC do array [kW]" position="insideBottom" offset={-18} fill="#94a3b8" fontSize={12} />
          </XAxis>
          <YAxis unit=" MWh" tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v, n) => [`${v.toFixed(2)} MWh`, n === 'arr' ? 'E_Array (MPP)' : 'E_Grid (AC)']} />
          <Legend verticalAlign="top" />
          {P_nom_AC_kW && (
            <ReferenceLine x={P_nom_AC_kW} stroke="#f59e0b" strokeDasharray="5 3"
              label={{ value: 'Pnom AC', position: 'top', fontSize: 10, fill: '#f59e0b' }} />
          )}
          {P_nom_stc_kWp && (
            <ReferenceLine x={P_nom_stc_kWp} stroke="#10b981" strokeDasharray="5 3"
              label={{ value: 'Pnom STC', position: 'top', fontSize: 10, fill: '#10b981' }} />
          )}
          <Bar dataKey="arr"  name="E_Array (MPP)" fill="#0077EE" radius={[2,2,0,0]} />
          <Bar dataKey="grid" name="E_Grid (AC)"   fill="#00C8FF" radius={[2,2,0,0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
