import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine, ReferenceArea, Label,
} from 'recharts'
import { useI18n } from '../i18n.jsx'

// ── Constantes físicas ────────────────────────────────────────────────────────
const kB  = 1.38064852e-23    // J/K
const q_e = 1.602176634e-19   // C
const Eg  = 1.121             // eV — silício cristalino

// ── Newton-Raphson: resolve I(V) na equação completa do diodo (com Rsh) ──────
// f(I) = Iph − I₀·(exp((V+I·Rs)/Vt) − 1) − (V+I·Rs)/Rsh − I = 0
function solveI(V, Iph, I0, Rs, Rsh, Vt, I_init) {
  if (!isFinite(V) || !isFinite(Vt) || Vt <= 0) return 0
  let I = I_init
  for (let k = 0; k < 50; k++) {
    const u      = V + I * Rs
    const expArg = Math.min(u / Vt, 700)
    const expT   = Math.exp(expArg)
    const f  = Iph - I0 * (expT - 1) - u / Rsh - I
    const fp = -I0 * Rs / Vt * expT - Rs / Rsh - 1
    if (!isFinite(f) || !isFinite(fp) || Math.abs(fp) < 1e-20) break
    const dI = -f / fp
    if (!isFinite(dI)) break
    I = Math.max(0, I + dI)
    if (Math.abs(dI) < 1e-9) break
  }
  return isFinite(I) ? Math.max(0, I) : 0
}

// ── buildCurve — modelo de diodo completo com Rsh e γ(T) variável ─────────
function buildCurve(mod, Ns, Nstr, T_C) {
  const T    = T_C + 273.15
  const Tref = 298.15

  // ── Calibração de muGamma ─────────────────────────────────────────────────
  // Derivada analítica de Voc pelo modelo de diodo a T_ref (γ fixo):
  //   dVoc/dT|model = Voc/T_ref − N_cs·(kB/q)·(3γ + Eg/(kB/q·T_ref))
  // muGamma é o ajuste para que o modelo reproduza μ_Voc do datasheet.
  const kBq         = kB / q_e                                     // 8.617e-5 V/K
  const muVoc_abs   = mod.Voc * mod.mu_Voc / 100                   // V/°C/módulo (absoluto)
  const muVoc_model = mod.Voc / Tref
    - mod.N_cs * kBq * (3 * mod.gamma + Eg / (kBq * Tref))        // V/°C/módulo (modelo)
  const muGamma = (muVoc_abs - muVoc_model) / mod.Voc              // /°C

  // ── Parâmetros dependentes de temperatura ─────────────────────────────────
  const gamma = mod.gamma + muGamma * (T - Tref)                   // γ(T)
  const Vt    = gamma * mod.N_cs * kB * T / q_e                    // tensão térmica [V]
  const Iph   = mod.Iph_ref * (1 + mod.mu_Isc / 100 * (T_C - 25)) // foto-corrente [A]
  const I0    = mod.I0_ref
    * Math.pow(T / Tref, 3)
    * Math.exp(Eg * q_e / (gamma * kB) * (1 / Tref - 1 / T))      // corrente de saturação [A]
  const Rs    = mod.Rs    // resistência série [Ω/módulo]
  const Rsh   = mod.Rsh   // resistência paralela [Ω/módulo]

  // ── Guarda: parâmetros válidos ────────────────────────────────────────────
  if (!isFinite(gamma) || gamma <= 0 || !isFinite(Vt) || !isFinite(Iph) || !isFinite(I0) || I0 <= 0) {
    return { pts: [], Vmpp: 0, Impp: 0, Voc: 0, Isc: 0, Pmpp: 0 }
  }

  // ── Isc: I(V=0) ──────────────────────────────────────────────────────────
  const Isc_mod = solveI(0, Iph, I0, Rs, Rsh, Vt, Iph)

  // ── Estimativa conservadora de Voc (sem Rsh) ──────────────────────────
  const Voc_raw = Vt * Math.log(Iph / I0 + 1)
  const Voc_est = isFinite(Voc_raw) ? Voc_raw * 1.02 : 0
  if (Voc_est <= 0) return { pts: [], Vmpp: 0, Impp: 0, Voc: 0, Isc: +(Nstr * Isc_mod).toFixed(2), Pmpp: 0 }

  // ── Varredura V: 0 → Voc_est, resolve I por Newton-Raphson ──────────────
  const N = 500
  const pts = [{ V: 0, I: +(Nstr * Isc_mod).toFixed(2) }]
  let maxP = 0, Vmpp = 0, Impp = 0
  let I_prev = Isc_mod

  for (let i = 1; i <= N; i++) {
    const V_mod = Voc_est * i / N
    const I_mod = solveI(V_mod, Iph, I0, Rs, Rsh, Vt, I_prev)
    if (!isFinite(I_mod) || I_mod < 1e-6) break

    I_prev = I_mod
    const Vstr = +(Ns * V_mod).toFixed(1)
    const Istr = +(Nstr * I_mod).toFixed(2)
    const P    = Vstr * Istr

    pts.push({ V: Vstr, I: Istr })
    if (P > maxP) { maxP = P; Vmpp = Vstr; Impp = Istr }
  }

  return {
    pts,
    Vmpp,
    Impp,
    Voc:  pts.length > 1 ? pts[pts.length - 1].V : 0,
    Isc:  +(Nstr * Isc_mod).toFixed(2),
    Pmpp: +(maxP / 1000).toFixed(1),
  }
}

// ── Voc linear com μ_Voc — check de segurança conservador ───────────────────
function vocLinear(mod, Ns, T_C) {
  return +(Ns * mod.Voc * (1 + mod.mu_Voc / 100 * (T_C - 25))).toFixed(0)
}

// ── Componentes visuais ───────────────────────────────────────────────────────
function MppDot({ cx, cy, fill }) {
  if (cx == null || cy == null) return null
  return (
    <g>
      <circle cx={cx} cy={cy} r={6} fill={fill} stroke="#0a0f20" strokeWidth={1.5} />
      <circle cx={cx} cy={cy} r={3} fill="#fff" opacity={0.8} />
    </g>
  )
}

function Check({ ok, label }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '6px',
      background: ok ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
      border: `1px solid ${ok ? 'rgba(16,185,129,0.30)' : 'rgba(239,68,68,0.30)'}`,
      borderRadius: '6px', padding: '5px 10px', fontSize: '0.78rem',
    }}>
      <span style={{ fontWeight: 800, color: ok ? '#10b981' : '#ef4444', fontSize: '1rem', lineHeight: 1 }}>
        {ok ? '✓' : '✗'}
      </span>
      <span style={{ color: ok ? '#10b981' : '#fca5a5' }}>{label}</span>
    </div>
  )
}

// ── Componente principal ──────────────────────────────────────────────────────
export default function IVCurveChart({ resultado }) {
  try {
    return <IVCurveChartInner resultado={resultado} />
  } catch (e) {
    console.error('IVCurveChart error:', e)
    return null
  }
}

function IVCurveChartInner({ resultado }) {
  const { t } = useI18n()
  const { modulo_elec: mod, inversor_elec: inv, N_s, N_strings } = resultado ?? {}
  if (!mod || !inv || !N_s || !mod.Iph_ref || !mod.Rsh) return null

  // Temperaturas de dimensionamento
  const rCold = buildCurve(mod, N_s, N_strings, -10)  // −10°C → Voc máximo
  const rRef  = buildCurve(mod, N_s, N_strings,  20)  // +20°C → Vmpp máximo
  const rHot  = buildCurve(mod, N_s, N_strings,  60)  // +60°C → Vmpp mínimo
  const rSTC  = buildCurve(mod, N_s, N_strings,  25)  // +25°C → STC

  // Voc de segurança: fórmula LINEAR com μ_Voc — mais conservadora
  const Voc_safety = vocLinear(mod, N_s, -10)

  // Critérios de validação de tensão
  const okVoc   = Voc_safety    <= inv.V_dc_max
  const okVmppL = rHot.Vmpp    >= inv.V_mpp_min
  const okVmppH = rRef.Vmpp    <= inv.V_mpp_max
  const allOk   = okVoc && okVmppL && okVmppH

  const maxV = Math.ceil((Math.max(Voc_safety, inv.V_dc_max) * 1.08) / 100) * 100
  const maxI = Math.ceil((rSTC.Isc * 1.15) / 5) * 5
  const mppMaxDistinct = inv.V_mpp_max && inv.V_mpp_max < inv.V_dc_max

  return (
    <div className="chart-card">
      <h3>{t('iv.titulo')}</h3>

      {/* Badges de validação */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px', alignItems: 'center' }}>
        <span style={{
          fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase',
          letterSpacing: '0.06em', color: allOk ? '#10b981' : '#ef4444', marginRight: 4,
        }}>
          {allOk ? t('iv.ok') : t('iv.verificar')}
        </span>
        <Check ok={okVoc}
          label={`Voc(−10°C) = ${Voc_safety} V ≤ V_dc_max ${inv.V_dc_max} V`} />
        <Check ok={okVmppL}
          label={`Vmpp(60°C) = ${rHot.Vmpp} V ≥ V_MPPT_min ${inv.V_mpp_min} V`} />
        <Check ok={okVmppH}
          label={`Vmpp(20°C) = ${rRef.Vmpp} V ≤ V_MPPT_max ${inv.V_mpp_max} V`} />
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ top: 20, right: 32, left: 10, bottom: 32 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />

          <XAxis type="number" dataKey="V" name="Tensão" unit=" V"
                 domain={[0, maxV]} tickCount={9} tick={{ fontSize: 11 }}>
            <Label value={t('iv.tensao')} position="insideBottom" offset={-20} fill="#94a3b8" fontSize={12} />
          </XAxis>

          <YAxis type="number" dataKey="I" name="Corrente" unit=" A"
                 domain={[0, maxI]} tick={{ fontSize: 11 }}>
            <Label value={t('iv.corrente')} angle={-90} position="insideLeft" offset={10} fill="#94a3b8" fontSize={12} />
          </YAxis>

          <Tooltip cursor={{ strokeDasharray: '3 3' }}
            formatter={(v, name) => [`${v}`, name]}
            contentStyle={{ background: '#0d1530', border: '1px solid rgba(0,95,255,0.3)', fontSize: 12, borderRadius: 6 }} />
          <Legend verticalAlign="top" wrapperStyle={{ fontSize: '0.8rem' }} />

          {/* Janela MPPT — área verde */}
          <ReferenceArea
            x1={inv.V_mpp_min}
            x2={mppMaxDistinct ? inv.V_mpp_max : inv.V_dc_max}
            fill="rgba(16,185,129,0.07)" stroke="none"
          />
          {/* Zona proibida — área vermelha */}
          <ReferenceArea x1={inv.V_dc_max} x2={maxV}
            fill="rgba(239,68,68,0.07)" stroke="none" />

          {/* Limites do inversor */}
          <ReferenceLine x={inv.V_mpp_min} stroke="#10b981" strokeWidth={1.5} strokeDasharray="6 3"
            label={{ value: `V_MPPT_min ${inv.V_mpp_min}V`, position: 'insideTopLeft', fontSize: 9, fill: '#10b981' }} />
          {mppMaxDistinct && (
            <ReferenceLine x={inv.V_mpp_max} stroke="#10b981" strokeWidth={1.5} strokeDasharray="6 3"
              label={{ value: `V_MPPT_max ${inv.V_mpp_max}V`, position: 'insideTopRight', fontSize: 9, fill: '#10b981' }} />
          )}
          <ReferenceLine x={inv.V_dc_max} stroke="#ef4444" strokeWidth={2}
            label={{ value: `V_dc_max ${inv.V_dc_max}V`, position: 'insideTopRight', fontSize: 9, fill: '#ef4444' }} />

          {/* Voc(−10°C) calculado pela fórmula linear μ_Voc — safety reference */}
          <ReferenceLine x={Voc_safety} stroke="#818cf8" strokeDasharray="4 2" strokeOpacity={0.8}
            label={{ value: `Voc(−10°C) ${Voc_safety}V`, position: 'insideBottomRight', fontSize: 9, fill: '#818cf8' }} />
          {/* Vmpp(60°C) — limite inferior da janela operacional */}
          <ReferenceLine x={rHot.Vmpp} stroke="#f97316" strokeDasharray="4 2" strokeOpacity={0.7}
            label={{ value: `Vmpp(60°C) ${rHot.Vmpp}V`, position: 'insideBottomLeft', fontSize: 9, fill: '#f97316' }} />

          {/* Curvas I-V */}
          <Scatter name="−10 °C" data={rCold.pts}
            line={{ stroke: '#818cf8', strokeWidth: 2 }} shape={() => null} fill="#818cf8" />
          <Scatter name="25 °C (STC)" data={rSTC.pts}
            line={{ stroke: '#00C8FF', strokeWidth: 2 }} shape={() => null} fill="#00C8FF" />
          <Scatter name="60 °C" data={rHot.pts}
            line={{ stroke: '#f97316', strokeWidth: 2 }} shape={() => null} fill="#f97316" />

          {/* Pontos MPP */}
          <Scatter legendType="none" data={[{ V: rCold.Vmpp, I: rCold.Impp }]} shape={<MppDot fill="#818cf8" />} />
          <Scatter legendType="none" data={[{ V: rSTC.Vmpp,  I: rSTC.Impp  }]} shape={<MppDot fill="#00C8FF" />} />
          <Scatter legendType="none" data={[{ V: rHot.Vmpp,  I: rHot.Impp  }]} shape={<MppDot fill="#f97316" />} />
        </ScatterChart>
      </ResponsiveContainer>

      {/* Tabela de parâmetros por temperatura */}
      <table style={{
        width: '100%', borderCollapse: 'collapse',
        marginTop: '14px', fontSize: '0.78rem',
      }}>
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
            {[t('iv.temperatura'), 'Voc', 'Vmpp', 'Pmpp', 'Isc'].map((h, i) => (
              <th key={h} style={{
                padding: '4px 10px', color: 'var(--text-muted)',
                fontWeight: 600, textAlign: i === 0 ? 'left' : 'right',
                fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em',
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {/* −10°C */}
          <tr>
            <td style={{ padding: '5px 10px', color: '#818cf8', fontWeight: 700 }}>−10°C</td>
            <td style={{ padding: '5px 10px', textAlign: 'right' }}>
              <strong style={{ color: okVoc ? '#818cf8' : '#ef4444' }}>{Voc_safety} V</strong>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem', marginLeft: 5 }}>μ_Voc</span>
            </td>
            <td style={{ padding: '5px 10px', textAlign: 'right' }}>
              <strong style={{ color: '#818cf8' }}>{rCold.Vmpp} V</strong>
            </td>
            <td style={{ padding: '5px 10px', textAlign: 'right' }}>
              <strong style={{ color: 'var(--text)' }}>{rCold.Pmpp} kW</strong>
            </td>
            <td style={{ padding: '5px 10px', textAlign: 'right', color: 'var(--text-muted)' }}>—</td>
          </tr>
          {/* 25°C STC */}
          <tr style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
            <td style={{ padding: '5px 10px', color: '#00C8FF', fontWeight: 700 }}>25°C (STC)</td>
            <td style={{ padding: '5px 10px', textAlign: 'right' }}>
              <strong style={{ color: '#00C8FF' }}>{rSTC.Voc} V</strong>
            </td>
            <td style={{ padding: '5px 10px', textAlign: 'right' }}>
              <strong style={{ color: '#00C8FF' }}>{rSTC.Vmpp} V</strong>
            </td>
            <td style={{ padding: '5px 10px', textAlign: 'right' }}>
              <strong style={{ color: 'var(--text)' }}>{rSTC.Pmpp} kW</strong>
            </td>
            <td style={{ padding: '5px 10px', textAlign: 'right' }}>
              <strong style={{ color: 'var(--text)' }}>{rSTC.Isc} A</strong>
            </td>
          </tr>
          {/* 60°C */}
          <tr style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
            <td style={{ padding: '5px 10px', color: '#f97316', fontWeight: 700 }}>60°C</td>
            <td style={{ padding: '5px 10px', textAlign: 'right' }}>
              <strong style={{ color: '#f97316' }}>{rHot.Voc} V</strong>
            </td>
            <td style={{ padding: '5px 10px', textAlign: 'right' }}>
              <strong style={{ color: okVmppL ? '#f97316' : '#ef4444' }}>{rHot.Vmpp} V</strong>
            </td>
            <td style={{ padding: '5px 10px', textAlign: 'right' }}>
              <strong style={{ color: 'var(--text)' }}>{rHot.Pmpp} kW</strong>
            </td>
            <td style={{ padding: '5px 10px', textAlign: 'right', color: 'var(--text-muted)' }}>—</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

