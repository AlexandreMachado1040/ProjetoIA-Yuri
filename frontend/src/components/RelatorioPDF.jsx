import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import './RelatorioPDF.css'

const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
               'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

const MONTAGEM_LABELS = {
  livre:     'Estrutura livre (ventilada) — Uc 29 W/m²K',
  semi:      'Semi-integrada no telhado — Uc 20 W/m²K',
  integrada: 'Integrada / verso isolado — Uc 15 W/m²K',
  pvusa:     'Com vento (PVUSA) — Uc 25, Uv 1,2',
}

// Número no padrão brasileiro.
const fmt = (v, dec = 1) =>
  (v === null || v === undefined || Number.isNaN(+v))
    ? '—'
    : (+v).toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec })

const hoje = () => {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`
}

export default function RelatorioPDF({ resultado, inputPayload, onClose }) {
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
          🖨 Imprimir / Salvar PDF
        </button>
        <button type="button" className="btn-fechar" onClick={onClose}>
          ✕ Fechar
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
              <span>Relatório de Simulação Fotovoltaica</span>
            </h1>
          </div>
          <div className="rel-meta">
            <strong>{hoje()}</strong>
            Simulação anual · clima NASA POWER
            {r.is_plant ? <><br />{r.n_inversores ?? r.subarrays?.length} inversores</> : null}
          </div>
        </header>
        <p className="rel-subtitulo">
          Simulação horária com transposição Hay, modelo térmico U-value e
          {subsCfg.some(s => s.bifacial) ? ' ganho bifacial por ray-tracing 2D.' : ' módulos monofaciais.'}
          {r.nasa_source ? ` Fonte meteorológica: ${r.nasa_source}.` : ''}
        </p>

        {/* ── 1. Dados do projeto ── */}
        <section className="rel-secao">
          <h2><span className="rel-num">1.</span>Dados do projeto</h2>
          <div className="rel-grid-2">
            <div>
              <h3>Localização</h3>
              <table className="rel-pares"><tbody>
                <tr><td>Latitude</td><td>{fmt(p.lat, 4)}°</td></tr>
                <tr><td>Longitude</td><td>{fmt(p.lon, 4)}°</td></tr>
                <tr><td>Fuso horário</td><td>UTC{p.tz >= 0 ? '+' : ''}{p.tz}</td></tr>
                <tr><td>Albedo do solo</td><td>{fmt(p.albedo, 2)}</td></tr>
                <tr><td>GHI anual no local</td><td>{fmt(r.GHI_anual, 1)} kWh/m²</td></tr>
              </tbody></table>
            </div>
            <div>
              <h3>Perdas configuradas</h3>
              <table className="rel-pares"><tbody>
                <tr><td>Montagem (térmica)</td><td>{MONTAGEM_LABELS[p.tipo_montagem] ?? p.tipo_montagem ?? '—'}</td></tr>
                <tr><td>Cabo CC (em STC)</td><td>{fmt(p.perda_cabo_cc_pct, 1)}%</td></tr>
                <tr><td>Sujidade (anual)</td><td>{fmt(p.perda_sujidade_pct, 1)}%</td></tr>
                <tr><td>Degradação dos módulos</td><td>{fmt(p.degradacao_anual_pct, 2)}%/ano</td></tr>
                <tr><td>Ano de operação</td><td>{p.ano_operacao ?? 1}º ano</td></tr>
              </tbody></table>
            </div>
          </div>
        </section>

        {/* ── 2. Configuração do sistema ── */}
        <section className="rel-secao">
          <h2><span className="rel-num">2.</span>Configuração do sistema</h2>
          <table className="rel-tabela">
            <thead>
              <tr>
                <th>#</th><th>Módulo</th><th>Inversor</th>
                <th className="num">Arranjo</th>
                <th className="num">Inclinação</th>
                <th className="num">Azimute</th>
                <th>Modo</th>
              </tr>
            </thead>
            <tbody>
              {subsCfg.map((s, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>{s.modulo}</td>
                  <td>{s.inversor}</td>
                  <td className="num">{s.N_s} × {s.N_strings} strings</td>
                  <td className="num">{fmt(s.tilt, 1)}°</td>
                  <td className="num">{fmt(s.az, 0)}°</td>
                  <td>{s.bifacial ? 'Bifacial' : 'Monofacial'}</td>
                </tr>
              ))}
              <tr className="rel-total">
                <td colSpan={3}>Total da usina</td>
                <td className="num" colSpan={2}>{fmt(r.P_nom_stc_kWp, 2)} kWp (STC)</td>
                <td className="num" colSpan={2}>{fmt(r.P_nom_AC_kW, 1)} kW (AC) · R DC/AC {fmt(R_DC_AC, 2)}</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* ── 3. Resultados anuais ── */}
        <section className="rel-secao">
          <h2><span className="rel-num">3.</span>Resultados anuais</h2>
          <div className="rel-kpis">
            <div className="rel-kpi">
              <span className="rel-kpi-rotulo">Energia injetada (E_Grid)</span>
              <span className="rel-kpi-valor">{fmt(r.E_grid_anual_kWh / 1000, 1)}<small>MWh/ano</small></span>
            </div>
            <div className="rel-kpi">
              <span className="rel-kpi-rotulo">Performance Ratio</span>
              <span className="rel-kpi-valor">{fmt(r.PR_pct, 1)}<small>%</small></span>
            </div>
            <div className="rel-kpi">
              <span className="rel-kpi-rotulo">Produtividade (Yf)</span>
              <span className="rel-kpi-valor">{fmt(Yf, 0)}<small>kWh/kWp</small></span>
            </div>
            <div className="rel-kpi">
              <span className="rel-kpi-rotulo">Ganho bifacial</span>
              <span className="rel-kpi-valor">+{fmt(r.ganho_bif_pct, 2)}<small>%</small></span>
            </div>
          </div>
          <table className="rel-pares"><tbody>
            <tr><td>Fator de transposição frontal (FT)</td><td>{fmt(r.FT_frontal, 3)}</td></tr>
            {r.FT_bifacial !== r.FT_frontal && (
              <tr><td>Fator de transposição bifacial efetivo</td><td>{fmt(r.FT_bifacial, 3)}</td></tr>
            )}
            <tr><td>Energia média diária injetada</td><td>{fmt(r.E_grid_anual_kWh / 365, 1)} kWh/dia</td></tr>
          </tbody></table>
        </section>

        {/* ── 4. Produção mensal ── */}
        <section className="rel-secao">
          <h2><span className="rel-num">4.</span>Produção mensal</h2>
          <table className="rel-tabela">
            <thead>
              <tr>
                <th>Mês</th>
                <th className="num">GHI (kWh/m²)</th>
                <th className="num">G frontal (kWh/m²)</th>
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
                <td>Ano</td>
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
            <h2><span className="rel-num">5.</span>Diagrama de perdas {r.is_plant ? '— usina completa' : ''}</h2>
            <CascataPerdas lossChain={r.loss_chain} />
          </section>
        )}

        {/* ── 6. Detalhamento por sub-arranjo (modo planta) ── */}
        {r.is_plant && r.subarrays?.length > 0 && (
          <section className="rel-secao">
            <h2><span className="rel-num">6.</span>Detalhamento por sub-arranjo</h2>
            <table className="rel-tabela">
              <thead>
                <tr>
                  <th>#</th><th>Inversor</th><th>Módulo</th>
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
                <h3>Perdas — Sub-arranjo {s.idx} ({s.inversor_nome})</h3>
                <CascataPerdas lossChain={s.loss_chain} />
              </div>
            ))}
          </section>
        )}

        {/* ── Rodapé ── */}
        <footer className="rel-rodape">
          <span>Aurova Motor Solar — simulação fotovoltaica bifacial</span>
          <span>Relatório gerado em {hoje()}</span>
        </footer>
      </div>
    </div>
  )

  return createPortal(doc, document.body)
}

// Cascata de perdas no estilo PVSyst: totais em destaque, deltas indentados.
function CascataPerdas({ lossChain }) {
  return (
    <div className="rel-perdas">
      {lossChain.map((item, i) => {
        if (item.tipo === 'total') {
          const final = i === lossChain.length - 1
          return (
            <div key={i} className={`rel-perda-total${final ? ' final' : ''}`}>
              <span className="v">{fmt(item.value, 1)}<small>{item.unit}</small></span>
              <span className="l">{item.label}</span>
            </div>
          )
        }
        const pos = item.value >= 0
        return (
          <div key={i} className="rel-perda-delta">
            <span className={`pct ${pos ? 'pos' : 'neg'}`}>
              {pos ? '+' : ''}{fmt(item.value, 2)}%
            </span>
            <span>{item.label}</span>
          </div>
        )
      })}
    </div>
  )
}
