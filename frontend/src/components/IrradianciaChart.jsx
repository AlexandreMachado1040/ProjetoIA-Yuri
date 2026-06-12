import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts'
import { useI18n } from '../i18n.jsx'

export default function IrradianciaChart({ monthlyGHI, monthlyGf, monthlyGb, bifacial }) {
  const { t, meses: MESES } = useI18n()
  if (!monthlyGHI) return null

  const data = MESES.map((m, i) => ({
    mes: m,
    GHI: +(monthlyGHI[i]     ?? 0).toFixed(1),
    Gf:  +(monthlyGf?.[i]    ?? 0).toFixed(1),
    Gb:  +(monthlyGb?.[i]    ?? 0).toFixed(1),
  }))

  return (
    <div className="chart-card">
      <h3>{t('irr.titulo')}</h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="mes" />
          <YAxis unit=" kWh" />
          <Tooltip formatter={v => [`${v} kWh/m²`]} />
          <Legend />
          <Bar dataKey="GHI"  name={t('irr.ghi')} fill="#00AAFF" radius={[2,2,0,0]} />
          {monthlyGf && (
            <Bar dataKey="Gf" name={t('irr.gf')} fill="#005FFF" radius={[2,2,0,0]} />
          )}
          {bifacial && monthlyGb && (
            <Bar dataKey="Gb" name={t('irr.gb')} fill="#10b981" radius={[2,2,0,0]} />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
