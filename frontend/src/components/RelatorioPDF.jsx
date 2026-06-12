import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { useI18n, traduzirRotuloMotor, traduzirFonte } from '../i18n.jsx'
import './RelatorioPDF.css'

const MONTAGENS = ['livre', 'semi', 'integrada', 'pvusa']

export default function RelatorioPDF({ resultado, inputPayload, onClose }) {
  const { t, locale, fmt, meses: MESES } = useI18n()
  const hoje = () => {
    const d = new Date()
    const p = (n) => String(n).padStart(2, '0')
    return locale === 'en-US'
      ? `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
      : locale === 'zh-CN'
        ? `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
        : `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`
  }
  // Marca o body para o @media print esconder o app e mostrar só o documento.
  useEffect(() => {
    document.body.classList.add('relatorio-aberto')
    return () => document.body.classList.remove('relatorio-aberto')
  }, [])

  // Fecha com Esc.
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!resultado) return null
  const r = resultado
  const p = inputPayload ?? {}

  // Configuração dos sub-arranjos (do payload enviado; achatado = 1 sub-arranjo).
  const subsCfg = p.subarrays?.length
    ? p.subarrays
    : [{
        modulo: p.modulo, inversor: p.inversor,
        N_s: p.N_s, N_strings: p.N_strings,
        tilt: p.tilt, az: p.az, bifacial: p.bifacial,
        pitch: p.pitch, mod_height: p.mod_height,
      }]

  const Yf      = r.P_nom_stc_kWp > 0 ? r.E_grid_anual_kWh / r.P_nom_stc_kWp : 0
  const R_DC_AC = r.P_nom_AC_kW > 0 ? r.P_nom_stc_kWp / r.P_nom_AC_kW : 0

  const dadosMensais = MESES.map((m, i) => ({
    mes: m,
    ghi:   r.monthly_GHI?.[i],
    gf:    r.monthly_Gf?.[i],
    earr:  r.monthly_E_arr?.[i],
    egrid: r.monthly_E_grid?.[i],
  }))
  const somaCol = (k) => dadosMensais.reduce((s, d) => s + (+d[k] || 0), 0)

  const doc = (
    <div className="relatorio-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="relatorio-toolbar">
        <button type="button" className="btn-imprimir" onClick={() => window.print()}>
          {t('rel.imprimir')}
        </button>
        <button type="button" className="btn-fechar" onClick={onClose}>
          {t('rel.fechar')}
        </button>
      </div>

      <div className="relatorio-doc">
        {/* ── Cabeçalho ── */}
        <header className="rel-cabecalho">
          <div className="rel-marca">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="44" height="44" aria-label="Aurova">
              <defs>
                <linearGradient id="relg1" x1="0%" y1="100%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#005FFF" />
                  <stop offset="100%" stopColor="#00C8FF" />
                </linearGradient>
              </defs>
              <path d="M 12 130 A 88 88 0 0 1 188 130" stroke="#00AAFF" strokeWidth="6" fill="none" strokeLinecap="round" opacity="0.48" />
              <path d="M 30 130 A 70 70 0 0 1 170 130" stroke="#0077EE" strokeWidth="9" fill="none" strokeLinecap="round" opacity="0.70" />
              <path d="M 50 130 A 50 50 0 0 1 150 130" stroke="#005FFF" strokeWidth="14" fill="none" strokeLinecap="round" />
              <circle cx="100" cy="134" r="11" fill="url(#relg1)" />
            </svg>
            <h1>
              Aurova Motor Solar
              <span>{t('rel.doc_titulo')}</span>
            </h1>
          </div>
          <div className="rel-meta">
            <strong>{hoje()}</strong>
            {t('rel.meta')}
            {r.is_plant ? <><br />{t('rel.inversores', { n: r.n_inversores ?? r.subarrays?.length })}</> : null}
          </div>
        </header>
        <p className="rel-subtitulo">
          {t('rel.sub_base')}
          {subsCfg.some(s => s.bifacial) ? t('rel.sub_bif') : t('rel.sub_mono')}
          {r.nasa_source ? t('rel.sub_fonte', { v: traduzirFonte(r.nasa_source, t) }) : ''}
        </p>

        {/* ── 1. Dados do projeto ── */}
        <section className="rel-secao">
          <h2><span className="rel-num">1.</span>{t('rel.s1')}</h2>
          <div className="rel-grid-2">
            <div>
              <h3>{t('rel.s1_loc')}</h3>
              <table className="rel-pares"><tbody>
                <tr><td>{t('rel.lat')}</td><td>{fmt(p.lat, 4)}°</td></tr>
                <tr><td>{t('rel.lon')}</td><td>{fmt(p.lon, 4)}°</td></tr>
                <tr><td>{t('rel.fuso')}</td><td>UTC{p.tz >= 0 ? '+' : ''}{p.tz}</td></tr>
                <tr><td>{t('rel.albedo')}</td><td>{fmt(p.albedo, 2)}</td></tr>
                <tr><td>{t('rel.ghi_local')}</td><td>{fmt(r.GHI_anual, 1)} kWh/m²</td></tr>
              </tbody></table>
            </div>
            <div>
              <h3>{t('rel.s1_perdas')}</h3>
              <table className="rel-pares"><tbody>
                <tr><td>{t('rel.montagem')}</td><td>{MONTAGENS.includes(p.tipo_montagem) ? t(`rel.montagem_${p.tipo_montagem}`) : (p.tipo_montagem ?? '—')}</td></tr>
                <tr><td>{t('rel.cabo')}</td><td>{fmt(p.perda_cabo_cc_pct, 1)}%</td></tr>
                <tr><td>{t('rel.sujidade')}</td><td>{fmt(p.perda_sujidade_pct, 1)}%</td></tr>
                {p.iam_b0 !== undefined && (
                  <tr><td>{t('rel.iam')}</td><td>{fmt(p.iam_b0, 2)}</td></tr>
                )}
                {p.perda_mismatch_pct !== undefined && (
                  <tr><td>{t('rel.mismatch')}</td><td>{fmt(p.perda_mismatch_pct, 1)}%</td></tr>
                )}
                {p.perda_lid_pct !== undefined && (
                  <tr><td>{t('rel.lid')}</td><td>{fmt(p.perda_lid_pct, 1)}%</td></tr>
                )}
                {p.indisponibilidade_pct > 0 && (
                  <tr><td>{t('rel.indisp')}</td><td>{fmt(p.indisponibilidade_pct, 1)}%</td></tr>
                )}
                <tr><td>{t('rel.degradacao')}</td><td>{fmt(p.degradacao_anual_pct, 2)}%</td></tr>
                <tr><td>{t('rel.ano_op')}</td><td>{t('rel.ano_op_v', { n: p.ano_operacao ?? 1 })}</td></tr>
              </tbody></table>
            </div>
          </div>
        </section>

        {/* ── 2. Configuração do sistema ── */}
        <section className="rel-secao">
          <h2><span className="rel-num">2.</span>{t('rel.s2')}</h2>
          <table className="rel-tabela">
            <thead>
              <tr>
                <th>#</th><th>{t('rel.col_modulo')}</th><th>{t('rel.col_inversor')}</th>
                <th className="num">{t('rel.col_arranjo')}</th>
                <th className="num">{t('rel.col_incl')}</th>
                <th className="num">{t('rel.col_az')}</th>
                <th>{t('rel.col_modo')}</th>
              </tr>
            </thead>
            <tbody>
              {subsCfg.map((s, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>{s.modulo}</td>
                  <td>{s.inversor}</td>
                  <td className="num">{s.N_s} × {s.N_strings} {t('rel.strings')}</td>
                  <td className="num">{fmt(s.tilt, 1)}°</td>
                  <td className="num">{fmt(s.az, 0)}°</td>
                  <td>{s.bifacial ? t('form.bifacial') : t('form.monofacial')}</td>
                </tr>
              ))}
              <tr className="rel-total">
                <td colSpan={3}>{t('rel.total_usina')}</td>
                <td className="num" colSpan={2}>{fmt(r.P_nom_stc_kWp, 2)} kWp (STC)</td>
                <td className="num" colSpan={2}>{fmt(r.P_nom_AC_kW, 1)} kW (AC) · R DC/AC {fmt(R_DC_AC, 2)}</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* ── 3. Resultados anuais ── */}
        <section className="rel-secao">
          <h2><span className="rel-num">3.</span>{t('rel.s3')}</h2>
          <div className="rel-kpis">
            <div className="rel-kpi">
              <span className="rel-kpi-rotulo">{t('rel.kpi_egrid')}</span>
              <span className="rel-kpi-valor">{fmt(r.E_grid_anual_kWh / 1000, 1)}<small>MWh</small></span>
            </div>
            <div className="rel-kpi">
              <span className="rel-kpi-rotulo">{t('rel.kpi_pr')}</span>
              <span className="rel-kpi-valor">{fmt(r.PR_pct, 1)}<small>%</small></span>
            </div>
            <div className="rel-kpi">
              <span className="rel-kpi-rotulo">{t('rel.kpi_yf')}</span>
              <span className="rel-kpi-valor">{fmt(Yf, 0)}<small>kWh/kWp</small></span>
            </div>
            <div className="rel-kpi">
              <span className="rel-kpi-rotulo">{t('rel.kpi_bif')}</span>
              <span className="rel-kpi-valor">+{fmt(r.ganho_bif_pct, 2)}<small>%</small></span>
            </div>
          </div>
          <table className="rel-pares"><tbody>
            <tr><td>{t('rel.ft_frontal')}</td><td>{fmt(r.FT_frontal, 3)}</td></tr>
            {r.FT_bifacial !== r.FT_frontal && (
              <tr><td>{t('rel.ft_bif')}</td><td>{fmt(r.FT_bifacial, 3)}</td></tr>
            )}
            <tr><td>{t('rel.media_diaria')}</td><td>{fmt(r.E_grid_anual_kWh / 365, 1)} kWh</td></tr>
          </tbody></table>
        </section>

        {/* ── 4. Produção mensal ── */}
        <section className="rel-secao">
          <h2><span className="rel-num">4.</span>{t('rel.s4')}</h2>
          <table className="rel-tabela">
            <thead>
              <tr>
                <th>{t('rel.col_mes')}</th>
                <th className="num">GHI (kWh/m²)</th>
                <th className="num">{t('loss.g_frontal')} (kWh/m²)</th>
                <th className="num">E_Array (kWh)</th>
                <th className="num">E_Grid (kWh)</th>
              </tr>
            </thead>
            <tbody>
              {dadosMensais.map((d) => (
                <tr key={d.mes}>
                  <td>{d.mes}</td>
                  <td className="num">{fmt(d.ghi, 1)}</td>
                  <td className="num">{fmt(d.gf, 1)}</td>
                  <td className="num">{fmt(d.earr, 0)}</td>
                  <td className="num">{fmt(d.egrid, 0)}</td>
                </tr>
              ))}
              <tr className="rel-total">
                <td>{t('rel.ano')}</td>
                <td className="num">{fmt(somaCol('ghi'), 1)}</td>
                <td className="num">{fmt(somaCol('gf'), 1)}</td>
                <td className="num">{fmt(somaCol('earr'), 0)}</td>
                <td className="num">{fmt(somaCol('egrid'), 0)}</td>
              </tr>
            </tbody>
          </table>

          <div className="rel-chart">
            <ResponsiveContainer width="100%" height={210}>
              <ComposedChart data={dadosMensais} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="e" tick={{ fontSize: 11 }} unit=" kWh" width={72} />
                <YAxis yAxisId="g" orientation="right" tick={{ fontSize: 11 }} unit="" width={46} />
                <Tooltip
                  formatter={(v, n) => [fmt(v, n === 'GHI (kWh/m²)' ? 1 : 0), n]}
                  contentStyle={{ background: '#fff', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar  yAxisId="e" dataKey="egrid" name="E_Grid (kWh)" fill="#005FFF" radius={[3, 3, 0, 0]} />
                <Line yAxisId="g" dataKey="ghi" name="GHI (kWh/m²)" stroke="#f59e0b" strokeWidth={2} dot={{ r: 2.5 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* ── 5. Diagrama de perdas ── */}
        {r.loss_chain?.length > 0 && (
          <section className="rel-secao">
            <h2><span className="rel-num">5.</span>{t('rel.s5')}{r.is_plant ? t('rel.s5_usina') : ''}</h2>
            <CascataPerdas lossChain={r.loss_chain} t={t} fmt={fmt} />
          </section>
        )}

        {/* ── 6. Detalhamento por sub-arranjo (modo planta) ── */}
        {r.is_plant && r.subarrays?.length > 0 && (
          <section className="rel-secao">
            <h2><span className="rel-num">6.</span>{t('rel.s6')}</h2>
            <table className="rel-tabela">
              <thead>
                <tr>
                  <th>#</th><th>{t('rel.col_inversor')}</th><th>{t('rel.col_modulo')}</th>
                  <th className="num">kWp</th>
                  <th className="num">R DC/AC</th>
                  <th className="num">E_Grid (kWh)</th>
                  <th className="num">PR</th>
                </tr>
              </thead>
              <tbody>
                {r.subarrays.map((s) => (
                  <tr key={s.idx}>
                    <td>{s.idx}</td>
                    <td>{s.inversor_nome}</td>
                    <td>{s.modulo_nome}</td>
                    <td className="num">{fmt(s.P_nom_stc_kWp, 2)}</td>
                    <td className="num">{fmt(s.R_DC_AC, 2)}</td>
                    <td className="num">{fmt(s.E_grid_anual_kWh, 0)}</td>
                    <td className="num">{fmt(s.PR_pct, 1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {r.subarrays.map((s) => s.loss_chain?.length > 0 && (
              <div key={`lc-${s.idx}`} style={{ marginTop: 16 }}>
                <h3>{t('rel.perdas_sub', { n: s.idx, inv: s.inversor_nome })}</h3>
                <CascataPerdas lossChain={s.loss_chain} t={t} fmt={fmt} />
              </div>
            ))}
          </section>
        )}

        {/* ── Rodapé ── */}
        <footer className="rel-rodape">
          <span>{t('rel.rodape')}</span>
          <span>{t('rel.gerado', { v: hoje() })}</span>
        </footer>
      </div>
    </div>
  )

  return createPortal(doc, document.body)
}

// Cascata de perdas no estilo PVSyst: totais em destaque, deltas indentados.
function CascataPerdas({ lossChain, t, fmt }) {
  return (
    <div className="rel-perdas">
      {lossChain.map((item, i) => {
        if (item.tipo === 'total') {
          const final = i === lossChain.length - 1
          return (
            <div key={i} className={`rel-perda-total${final ? ' final' : ''}`}>
              <span className="v">{fmt(item.value, 1)}<small>{item.unit}</small></span>
              <span className="l">{traduzirRotuloMotor(item.label, t)}</span>
            </div>
          )
        }
        const pos = item.value >= 0
        return (
          <div key={i} className="rel-perda-delta">
            <span className={`pct ${pos ? 'pos' : 'neg'}`}>
              {pos ? '+' : ''}{fmt(item.value, 2)}%
            </span>
            <span>{traduzirRotuloMotor(item.label, t)}</span>
          </div>
        )
      })}
    </div>
  )
}
