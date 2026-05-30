export default function LossDiagram({ lossChain }) {
  if (!lossChain || lossChain.length === 0) return null

  // Escala separada por unidade
  const mwhValues    = lossChain.filter(b => b.unit === 'MWh').map(b => b.value)
  const irradValues  = lossChain.filter(b => b.unit === 'kWh/m²').map(b => b.value)
  const maxMWh       = mwhValues.length    ? Math.max(...mwhValues)   : 1
  const maxIrrad     = irradValues.length  ? Math.max(...irradValues) : 1

  return (
    <div className="chart-card loss-diagram">
      <h3>Diagrama de Perdas — Cadeia PVSyst</h3>
      <div className="loss-list">
        {lossChain.map((blk, i) => {
          const isPerda = blk.tipo === 'perda'

          let barWidth
          if (blk.unit === 'MWh') {
            barWidth = (blk.value / maxMWh) * 100
          } else if (blk.unit === 'kWh/m²') {
            barWidth = (blk.value / maxIrrad) * 100
          } else {
            // percentual de perda — escala 0–10%
            barWidth = Math.min(Math.abs(blk.value) / 10 * 100, 100)
          }
          barWidth = Math.min(Math.max(barWidth, 2), 100)

          const barColor = blk.tipo === 'total'    ? '#1565C0'
                         : blk.tipo === 'bifacial'  ? '#2E7D32'
                         : '#ef9a9a'

          const valueFmt = isPerda
            ? `${blk.value}%`
            : `${blk.value} ${blk.unit}`

          return (
            <div key={i} className={`loss-row loss-${blk.tipo}`}>
              <div className="loss-bar-wrap">
                <div className="loss-bar" style={{ width: `${barWidth}%`, background: barColor }} />
              </div>
              <div className="loss-value">{valueFmt}</div>
              <div className="loss-label">{blk.label}</div>
            </div>
          )
        })}
      </div>
      <p className="chart-sub" style={{ marginTop: 10 }}>
        Azul = totais energéticos | Verde = bifacial | Vermelho = perdas
      </p>
    </div>
  )
}
