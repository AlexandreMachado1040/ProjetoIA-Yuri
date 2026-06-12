import { useState, useEffect } from 'react'
import { exportarCSV, exportarPNGs } from '../utils/exportRelatorio'
import { getDailyAnalysis } from '../api/client'
import { carregarTGY, achatarHorasTGY } from '../utils/sondaTgy'
import { useI18n, traduzirFonte } from '../i18n.jsx'
import RelatorioPDF          from './RelatorioPDF'
import ProducaoMensalChart   from './ProducaoMensalChart'
import IrradianciaChart      from './IrradianciaChart'
import DailyEgridChart       from './DailyEgridChart'
import ExploradorDiario      from './ExploradorDiario'
import LossDiagram           from './LossDiagram'
import IVCurveChart          from './IVCurveChart'
import PowerHistogramChart   from './PowerHistogramChart'
import FTCurveChart          from './FTCurveChart'

export default function ResultsDashboard({ resultado, inputPayload }) {
  const { t, locale, lang } = useI18n()
  // Sub-arranjos recolhidos (por idx). Padrão: todos expandidos.
  const [recolhidos, setRecolhidos] = useState({})
  const toggleSub = (idx) =>
    setRecolhidos(r => ({ ...r, [idx]: !r[idx] }))

  // Análise diária (/daily): buscada UMA vez e compartilhada entre o
  // ExploradorDiario e o DailyEgridChart. Com fonte SONDA, anexa as
  // 8.760 h medidas do TGY para o motor usar dias reais.
  const [dailyData, setDailyData]       = useState(null)
  const [dailyMedido, setDailyMedido]   = useState(null)
  const [dailyLoading, setDailyLoading] = useState(false)
  const dailyKey = inputPayload ? JSON.stringify(inputPayload) : null

  useEffect(() => {
    if (!inputPayload) return
    setDailyLoading(true); setDailyData(null); setDailyMedido(null)

    const montarPayload = async () => {
      const st = inputPayload.sonda_tgy
      if (!st?.arquivo) return { payload: inputPayload, medida: null }
      try {
        const horas = achatarHorasTGY(await carregarTGY(st.arquivo))
        return {
          payload: { ...inputPayload, sonda_tgy: { ...st, horas } },
          medida: st.estacao,
        }
      } catch (err) {
        console.warn('TGY horário indisponível, usando síntese:', err)
        return { payload: inputPayload, medida: null }
      }
    }

    montarPayload()
      .then(({ payload, medida }) => getDailyAnalysis(payload).then(d => {
        setDailyData(d)
        setDailyMedido(medida)
        setDailyLoading(false)
      }))
      .catch(() => setDailyLoading(false))
  }, [dailyKey])

  // Exportação de PNGs é assíncrona (um download por gráfico).
  const [exportandoPng, setExportandoPng] = useState(false)
  const handlePng = async () => {
    setExportandoPng(true)
    try { await exportarPNGs() } finally { setExportandoPng(false) }
  }

  // Pré-visualização do relatório em documento (PDF via impressão).
  const [mostrarRelatorio, setMostrarRelatorio] = useState(false)

  if (!resultado) return null

  const {
    E_grid_anual_kWh, PR_pct, GHI_anual,
    FT_frontal, FT_bifacial, ganho_bif_pct,
    P_nom_stc_kWp, P_nom_AC_kW,
    monthly_GHI, monthly_Gf, monthly_E_arr, monthly_E_grid,
    loss_chain, modulo_nome, inversor_nome, nasa_source,
    input_params, is_plant, subarrays,
  } = resultado

  const E_grid_MWh = +(E_grid_anual_kWh / 1000).toFixed(1)
  const Yf         = P_nom_stc_kWp > 0 ? +(E_grid_anual_kWh / P_nom_stc_kWp).toFixed(0) : 0
  const R_DC_AC    = P_nom_AC_kW   > 0 ? +(P_nom_stc_kWp    / P_nom_AC_kW).toFixed(2)   : 0
  const bifacial   = ganho_bif_pct > 0

  return (
    <div className="results-dashboard">
      <div className="results-header">
        <h2>{t('dash.titulo')}</h2>
        <div className="header-tags">
          {modulo_nome && <span className="fonte-tag">{modulo_nome} · {inversor_nome}</span>}
          {nasa_source  && <span className="fonte-tag nasa">{traduzirFonte(nasa_source, t)}</span>}
        </div>
        <div className="export-toolbar">
          <button type="button" onClick={() => exportarCSV(resultado, inputPayload, { t, lang })} title={t('dash.csv_title')}>
            ⬇ CSV
          </button>
          <button type="button" onClick={handlePng} disabled={exportandoPng} title={t('dash.png_title')}>
            {exportandoPng ? '…' : t('dash.png')}
          </button>
          <button type="button" onClick={() => setMostrarRelatorio(true)} title={t('dash.relatorio_title')}>
            {t('dash.relatorio')}
          </button>
        </div>
      </div>

      {mostrarRelatorio && (
        <RelatorioPDF
          resultado={resultado}
          inputPayload={inputPayload}
          onClose={() => setMostrarRelatorio(false)}
        />
      )}

      <div className="kpi-grid">
        <KPI label={t('dash.kpi_egrid')} value={E_grid_MWh}           unit="MWh" color="blue" />
        <KPI label={t('dash.kpi_pr')}    value={`${PR_pct}%`}                    color={PR_pct >= 80 ? 'green' : 'orange'} />
        <KPI label={t('dash.kpi_ghi')}   value={GHI_anual}            unit="kWh/m²" color="blue" />
        <KPI label={t('dash.kpi_bif')}   value={`+${ganho_bif_pct}%`}            color="green" />
        <KPI label={t('dash.kpi_ftf')}   value={FT_frontal}                      color="gray" />
        <KPI label={t('dash.kpi_ftb')}   value={FT_bifacial}                     color="gray" />
        <KPI label={t('dash.kpi_pstc')}  value={P_nom_stc_kWp}        unit="kWp" color="gray" />
        <KPI label={t('dash.kpi_pac')}   value={P_nom_AC_kW}          unit="kW"  color="gray" />
        <KPI label={t('dash.kpi_yf')}    value={Yf}                   unit="kWh/kWp" color="blue" />
        <KPI label={t('dash.kpi_rdcac')} value={R_DC_AC}                         color="gray" />
      </div>

      <LossDiagram lossChain={loss_chain} resultado={resultado} />

      {is_plant && subarrays?.length > 0 && (
        <div className="chart-card">
          <h3>{t('dash.subs_titulo', { n: subarrays.length })}</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ color: 'var(--text-sub)', textAlign: 'right' }}>
                  <th style={{ textAlign: 'left', padding: '4px 8px' }}>#</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px' }}>{t('dash.col_inversor')}</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px' }}>{t('dash.col_modulo')}</th>
                  <th style={{ padding: '4px 8px' }}>{t('dash.col_arranjo')}</th>
                  <th style={{ padding: '4px 8px' }}>kWp</th>
                  <th style={{ padding: '4px 8px' }}>{t('dash.kpi_rdcac')}</th>
                  <th style={{ padding: '4px 8px' }}>{t('dash.col_egrid')}</th>
                  <th style={{ padding: '4px 8px' }}>PR</th>
                </tr>
              </thead>
              <tbody>
                {subarrays.map(s => (
                  <tr key={s.idx} style={{ textAlign: 'right', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                    <td style={{ textAlign: 'left', padding: '4px 8px' }}>{s.idx}</td>
                    <td style={{ textAlign: 'left', padding: '4px 8px' }}>{s.inversor_nome}</td>
                    <td style={{ textAlign: 'left', padding: '4px 8px' }}>{s.modulo_nome}</td>
                    <td style={{ padding: '4px 8px' }}>{s.N_s}s×{s.N_strings}str</td>
                    <td style={{ padding: '4px 8px' }}>{s.P_nom_stc_kWp}</td>
                    <td style={{ padding: '4px 8px' }}>{s.R_DC_AC}</td>
                    <td style={{ padding: '4px 8px' }}>{s.E_grid_anual_kWh?.toLocaleString(locale)}</td>
                    <td style={{ padding: '4px 8px' }}>{s.PR_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {is_plant && (
        <>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-sub)', margin: '8px 2px 4px' }}>
            {t('dash.usina_dist')}
          </p>
          <PowerHistogramChart resultado={resultado} />
        </>
      )}

      {is_plant && subarrays?.map(s => {
        const colapsado = !!recolhidos[s.idx]
        return (
          <div key={s.idx} style={{ marginBottom: 8 }}>
            <button
              type="button"
              onClick={() => toggleSub(s.idx)}
              aria-expanded={!colapsado}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 8,
                background: 'rgba(0,95,255,0.10)', border: '1px solid rgba(0,95,255,0.25)',
                borderRadius: 7, padding: '8px 12px', margin: '8px 0 6px',
                color: 'var(--text-sub)', fontSize: '0.82rem', cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <span style={{
                display: 'inline-block', transition: 'transform 0.15s',
                transform: colapsado ? 'rotate(-90deg)' : 'rotate(0deg)',
              }}>▾</span>
              <strong style={{ color: 'var(--text-main, #e2e8f0)' }}>{t('dash.sub', { n: s.idx })}</strong>
              <span>— {s.inversor_nome} · {s.modulo_nome}
                {s.input_params && ` · ${t('dash.incl_az', { tilt: s.input_params.tilt, az: s.input_params.az })}`}</span>
              <span style={{ marginLeft: 'auto', fontSize: '0.74rem', opacity: 0.7 }}>
                {colapsado ? t('dash.expandir') : t('dash.recolher')}
              </span>
            </button>
            {!colapsado && (
              <>
                <LossDiagram lossChain={s.loss_chain} resultado={s} />
                <IVCurveChart resultado={s} />
                <PowerHistogramChart resultado={s} />
                <FTCurveChart inputParams={s.input_params} resultado={s} />
              </>
            )}
          </div>
        )
      })}

      {/* No modo planta, a curva I-V do topo não renderiza (N_s é por sub-arranjo) */}
      {!is_plant && <IVCurveChart resultado={resultado} />}

      <ProducaoMensalChart
        monthlyGridKwh={monthly_E_grid}
        monthlyArrKwh={monthly_E_arr}
        subarrays={is_plant ? subarrays : null}
      />

      <IrradianciaChart
        monthlyGHI={monthly_GHI}
        monthlyGf={monthly_Gf}
        bifacial={bifacial}
      />

      <ExploradorDiario daily={dailyData} medido={dailyMedido} loading={dailyLoading} />

      <DailyEgridChart daily={dailyData} medido={dailyMedido} loading={dailyLoading} />

      {!is_plant && <PowerHistogramChart resultado={resultado} />}

      {!is_plant && <FTCurveChart inputParams={input_params} resultado={resultado} />}
    </div>
  )
}

function KPI({ label, value, unit, color = 'blue' }) {
  return (
    <div className={`kpi-card kpi-${color}`}>
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}{unit ? ` ${unit}` : ''}</span>
    </div>
  )
}

