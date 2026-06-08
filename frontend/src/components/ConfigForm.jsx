import { useState, useEffect, useCallback } from 'react'
import { getModulos, getInversores } from '../api/client'

// Parâmetros globais (site + perdas), comuns a todos os sub-arranjos.
const GLOBAL_DEFAULTS = {
  lat:        -23.55,
  lon:        -46.63,
  tz:         -3,
  albedo:     0.30,
  perda_cabo_cc_pct: 1.5,
  perda_sujidade_pct: 2.0,
  tipo_montagem: 'livre',
  degradacao_anual_pct: 0.5,
  ano_operacao: 1,
}

// Um sub-arranjo: equipamento + arranjo + geometria.
const SUBARRAY_DEFAULT = {
  modulo:     '',
  inversor:   '',
  N_s:        28,
  N_strings:  3,
  tilt:       20.8,
  az:         0.0,
  bifacial:   true,
  pitch:      2.826,
  mod_height: 2.0,
}

// Tipos de montagem térmica (U-value PVSyst) — espelha MONTAGEM_PRESETS do motor.
const MONTAGENS = [
  { id: 'livre',     label: 'Estrutura livre (ventilada) — Uc 29' },
  { id: 'semi',      label: 'Semi-integrada no telhado — Uc 20' },
  { id: 'integrada', label: 'Integrada / verso isolado — Uc 15' },
  { id: 'pvusa',     label: 'Com vento (PVUSA) — Uc 25, Uv 1,2' },
]

export default function ConfigForm({ onSubmit, loading }) {
  const [modulos,    setModulos]    = useState([])
  const [inversores, setInversores] = useState([])
  const [form,       setForm]       = useState(GLOBAL_DEFAULTS)
  const [subarrays,  setSubarrays]  = useState([{ ...SUBARRAY_DEFAULT }])
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [catalogError,   setCatalogError]   = useState(false)

  const loadCatalog = useCallback(() => {
    setCatalogLoading(true)
    setCatalogError(false)

    Promise.all([getModulos(), getInversores()])
      .then(([mods, invs]) => {
        setModulos(mods)
        setInversores(invs)
        // Preenche módulo/inversor padrão em sub-arranjos ainda vazios
        setSubarrays(subs => subs.map(s => ({
          ...s,
          modulo:   s.modulo   || (mods[0]?.nome ?? ''),
          inversor: s.inversor || (invs[0]?.nome ?? ''),
        })))
        setCatalogLoading(false)
      })
      .catch(() => {
        setCatalogLoading(false)
        setCatalogError(true)
      })
  }, [])

  // Carrega catálogo. O client.js já faz retry com backoff e cai para um
  // catálogo estático embutido se o Worker falhar.
  useEffect(() => {
    loadCatalog()
  }, [loadCatalog])

  // ── Helpers de estado ───────────────────────────────────────────────────
  const set = (k) => (e) => {
    const v = e.target.type === 'number' ? Number(e.target.value) : e.target.value
    setForm(f => ({ ...f, [k]: v }))
  }

  const setSub = (idx, k) => (e) => {
    const v = e.target.type === 'number' ? Number(e.target.value) : e.target.value
    setSubarrays(subs => subs.map((s, i) => i === idx ? { ...s, [k]: v } : s))
  }

  const addSubarray = () => {
    setSubarrays(subs => [...subs, {
      ...SUBARRAY_DEFAULT,
      modulo:   modulos[0]?.nome ?? '',
      inversor: inversores[0]?.nome ?? '',
    }])
  }

  const removeSubarray = (idx) => {
    setSubarrays(subs => subs.length > 1 ? subs.filter((_, i) => i !== idx) : subs)
  }

  const setSubVal = (idx, k, v) => {
    setSubarrays(subs => subs.map((s, i) => i === idx ? { ...s, [k]: v } : s))
  }

  // ── Submit ──────────────────────────────────────────────────────────────
  const handleSubmit = (e) => {
    e.preventDefault()
    const anyBifacial = subarrays.some(s => s.bifacial)
    const base = {
      lat: form.lat, lon: form.lon, tz: form.tz, albedo: form.albedo,
      N_seg: anyBifacial ? 5 : 0,
      N_rays: anyBifacial ? 12 : 0,
      perda_cabo_cc_pct: form.perda_cabo_cc_pct,
      perda_sujidade_pct: form.perda_sujidade_pct,
      tipo_montagem: form.tipo_montagem,
      degradacao_anual_pct: form.degradacao_anual_pct,
      ano_operacao: form.ano_operacao,
    }

    if (subarrays.length === 1) {
      // Sub-arranjo único → payload achatado (rota simulate_fast clássica)
      const s = subarrays[0]
      onSubmit({
        ...base,
        modulo: s.modulo, inversor: s.inversor,
        N_s: s.N_s, N_strings: s.N_strings,
        tilt: s.tilt, az: s.az, bifacial: s.bifacial,
        pitch: s.pitch, mod_height: s.mod_height,
      })
    } else {
      // Vários sub-arranjos → simulate_plant
      onSubmit({
        ...base,
        modulo: subarrays[0].modulo, inversor: subarrays[0].inversor,
        subarrays: subarrays.map(s => ({
          modulo: s.modulo, inversor: s.inversor,
          N_s: s.N_s, N_strings: s.N_strings,
          tilt: s.tilt, az: s.az, bifacial: s.bifacial,
          pitch: s.pitch, mod_height: s.mod_height,
        })),
      })
    }
  }

  const field = (label, key, type = 'number', step = 'any') => (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={form[key]} onChange={set(key)} step={step} />
    </label>
  )

  const subField = (idx, label, key, type = 'number', step = 'any') => (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={subarrays[idx][key]} onChange={setSub(idx, key)} step={step} />
    </label>
  )

  const algumSemModulo = subarrays.some(s => !s.modulo)

  return (
    <form onSubmit={handleSubmit} className="config-form">
      <h2>Parâmetros de Simulação</h2>

      <section>
        <h3>Localização</h3>
        {field('Latitude (°)', 'lat')}
        {field('Longitude (°)', 'lon')}
        {field('Fuso horário (UTC)', 'tz', 'number', 1)}
      </section>

      {catalogError && (
        <div style={{
          background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.30)',
          borderRadius: 7, padding: '8px 10px', fontSize: '0.78rem', color: '#fca5a5',
          marginBottom: 10, display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', gap: 8,
        }}>
          <span>Falha ao carregar catálogo.</span>
          <button type="button" onClick={loadCatalog} style={{
            background: 'rgba(239,68,68,0.20)', border: '1px solid rgba(239,68,68,0.40)',
            borderRadius: 5, padding: '3px 10px', color: '#fca5a5',
            fontSize: '0.76rem', cursor: 'pointer', whiteSpace: 'nowrap',
          }}>Tentar novamente</button>
        </div>
      )}

      {/* ── Sub-arranjos (equipamento + arranjo + geometria) ── */}
      {subarrays.map((s, idx) => (
        <section key={idx} style={{
          border: '1px solid rgba(0,95,255,0.20)', borderRadius: 8,
          padding: '10px 12px', marginBottom: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h3 style={{ margin: 0 }}>
              {subarrays.length > 1 ? `Sub-arranjo ${idx + 1}` : 'Equipamento e Arranjo'}
            </h3>
            {subarrays.length > 1 && (
              <button type="button" onClick={() => removeSubarray(idx)} style={{
                background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.35)',
                borderRadius: 5, padding: '2px 9px', color: '#fca5a5',
                fontSize: '0.74rem', cursor: 'pointer',
              }}>Remover</button>
            )}
          </div>

          <label className="field">
            <span>Módulo{catalogLoading ? ' (carregando…)' : ''}</span>
            <select value={s.modulo} onChange={setSub(idx, 'modulo')}
              disabled={catalogLoading || catalogError}>
              {catalogLoading && <option>Carregando…</option>}
              {catalogError   && <option>Erro ao carregar</option>}
              {modulos.map(m => (
                <option key={m.nome} value={m.nome}>{m.nome} ({m.Pmpp_Wp} Wp)</option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Inversor{catalogLoading ? ' (carregando…)' : ''}</span>
            <select value={s.inversor} onChange={setSub(idx, 'inversor')}
              disabled={catalogLoading || catalogError}>
              {catalogLoading && <option>Carregando…</option>}
              {catalogError   && <option>Erro ao carregar</option>}
              {inversores.map(i => (
                <option key={i.nome} value={i.nome}>{i.nome} ({i.P_nomAC_kW} kW)</option>
              ))}
            </select>
          </label>

          {subField(idx, 'Módulos em série (N_s)', 'N_s', 'number', 1)}
          {subField(idx, 'Strings em paralelo (N_strings)', 'N_strings', 'number', 1)}
          {subField(idx, 'Inclinação (°)', 'tilt')}
          {subField(idx, 'Azimute (° | 0=Norte no HS)', 'az')}

          <label className="field">
            <span>Modo</span>
            <select
              value={s.bifacial ? 'BIFACIAL' : 'MONOFACIAL'}
              onChange={e => setSubVal(idx, 'bifacial', e.target.value === 'BIFACIAL')}
            >
              <option value="BIFACIAL">Bifacial</option>
              <option value="MONOFACIAL">Monofacial</option>
            </select>
          </label>

          {s.bifacial && (
            <>
              {subField(idx, 'Pitch — entre fileiras (m)', 'pitch')}
              {subField(idx, 'Altura do módulo (m)', 'mod_height')}
            </>
          )}
        </section>
      ))}

      <button type="button" onClick={addSubarray}
        disabled={catalogLoading || catalogError}
        style={{
          width: '100%', background: 'rgba(0,95,255,0.12)',
          border: '1px dashed rgba(0,95,255,0.45)', borderRadius: 7,
          padding: '8px', color: '#7db3ff', fontSize: '0.82rem',
          cursor: 'pointer', marginBottom: 14,
        }}>
        + Adicionar inversor / sub-arranjo
      </button>

      <section>
        <h3>Perdas</h3>
        <label className="field">
          <span>Tipo de montagem (térmica)</span>
          <select value={form.tipo_montagem} onChange={set('tipo_montagem')}>
            {MONTAGENS.map(m => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>
        </label>
        {field('Perda de cabo CC (% em STC)', 'perda_cabo_cc_pct', 'number', 0.1)}
        {field('Perda por sujidade (% anual)', 'perda_sujidade_pct', 'number', 0.1)}
        {field('Degradação dos módulos (%/ano)', 'degradacao_anual_pct', 'number', 0.1)}
        {field('Ano de operação', 'ano_operacao', 'number', 1)}
        {field('Albedo', 'albedo')}
      </section>

      <button
        type="submit"
        disabled={loading || catalogLoading || catalogError || algumSemModulo}
        className="btn-simular"
      >
        {loading ? 'Simulando…' : 'Simular'}
      </button>
    </form>
  )
}
