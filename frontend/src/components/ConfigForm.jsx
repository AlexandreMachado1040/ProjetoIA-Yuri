import { useState, useEffect, useCallback } from 'react'
import { getModulos, getInversores } from '../api/client'
import ESTACOES_SONDA from '../data/sonda_estacoes.json'
import { carregarTGY } from '../utils/sondaTgy'
import { useI18n } from '../i18n.jsx'

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

// Estações SONDA/INPE com TGY pré-processado: o registro em
// src/data/sonda_estacoes.json é gerado por sonda_tgy_pipeline.py.
// O TGY entra como fonte de irradiância medida quando o projeto está próximo.
const RAIO_SONDA_KM = 100

function distanciaKm(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180
  const a = Math.sin((lat2 - lat1) * r / 2) ** 2 +
            Math.cos(lat1 * r) * Math.cos(lat2 * r) *
            Math.sin((lon2 - lon1) * r / 2) ** 2
  return 12742 * Math.asin(Math.sqrt(a))
}

// Tipos de montagem térmica (U-value PVSyst) — espelha MONTAGEM_PRESETS do motor.
const MONTAGENS = ['livre', 'semi', 'integrada', 'pvusa']

export default function ConfigForm({ onSubmit, loading }) {
  const { t } = useI18n()
  const [modulos,    setModulos]    = useState([])
  const [inversores, setInversores] = useState([])
  const [form,       setForm]       = useState(GLOBAL_DEFAULTS)
  const [subarrays,  setSubarrays]  = useState([{ ...SUBARRAY_DEFAULT }])
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [catalogError,   setCatalogError]   = useState(false)

  // Fonte de irradiância: 'nasa' (padrão) ou 'sonda' (TGY medido em solo).
  // O seletor é sempre visível; a opção SONDA só habilita quando o local
  // está a até RAIO_SONDA_KM da estação mais próxima.
  const [fonteIrr, setFonteIrr] = useState('nasa')
  const estacaoMaisProxima = ESTACOES_SONDA
    .map(e => ({ ...e, dist: distanciaKm(form.lat, form.lon, e.lat, e.lon) }))
    .sort((a, b) => a.dist - b.dist)[0]
  const sondaDisponivel = estacaoMaisProxima.dist <= RAIO_SONDA_KM
  const estacaoProxima  = sondaDisponivel ? estacaoMaisProxima : null

  useEffect(() => {
    if (!sondaDisponivel && fonteIrr !== 'nasa') setFonteIrr('nasa')
  }, [sondaDisponivel, fonteIrr])

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
  const handleSubmit = async (e) => {
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

    // Fonte SONDA: anexa os agregados mensais do TGY da estação próxima.
    // Em caso de falha no carregamento, segue com a NASA (sem bloquear).
    if (fonteIrr === 'sonda' && estacaoProxima) {
      try {
        const tgy = await carregarTGY(estacaoProxima.arquivo)
        base.sonda_tgy = {
          estacao: tgy.estacao,
          arquivo: estacaoProxima.arquivo,   // p/ análise diária buscar as 8.760 h
          ghi: tgy.ghi_mensal_kwh_dia,
          dni: tgy.dni_mensal_kwh_dia,
          dhi: tgy.dhi_mensal_kwh_dia,
        }
      } catch (err) {
        console.warn('TGY SONDA indisponível, usando NASA POWER:', err)
      }
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
      <h2>{t('form.titulo')}</h2>

      <section>
        <h3>{t('form.localizacao')}</h3>
        {field(t('form.lat'), 'lat')}
        {field(t('form.lon'), 'lon')}
        {field(t('form.fuso'), 'tz', 'number', 1)}

        <label className="field">
          <span>{t('form.fonte')}</span>
          <select value={fonteIrr} onChange={e => setFonteIrr(e.target.value)}>
            <option value="nasa">{t('form.fonte_nasa')}</option>
            <option value="sonda" disabled={!sondaDisponivel}>
              {sondaDisponivel
                ? t('form.fonte_sonda', { sigla: estacaoMaisProxima.sigla })
                : t('form.fonte_sonda_off', { raio: RAIO_SONDA_KM })}
            </option>
          </select>
        </label>
        <p style={{
          fontSize: '0.72rem', color: 'var(--text-sub, #8b95c0)',
          margin: '2px 2px 8px', lineHeight: 1.5,
        }}>
          {fonteIrr === 'sonda' && estacaoProxima
            ? t('form.hint_sonda', {
                nome: estacaoProxima.nome,
                dist: estacaoProxima.dist.toFixed(0),
              })
            : t('form.hint_proxima', {
                nome: estacaoMaisProxima.nome,
                sigla: estacaoMaisProxima.sigla,
                dist: estacaoMaisProxima.dist.toFixed(0),
              }) + (sondaDisponivel
                ? t('form.hint_selecione')
                : t('form.hint_ajuste', {
                    raio: RAIO_SONDA_KM,
                    n: ESTACOES_SONDA.length,
                    lat: estacaoMaisProxima.lat.toFixed(2),
                    lon: estacaoMaisProxima.lon.toFixed(2),
                  }))}
        </p>
      </section>

      {catalogError && (
        <div style={{
          background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.30)',
          borderRadius: 7, padding: '8px 10px', fontSize: '0.78rem', color: '#fca5a5',
          marginBottom: 10, display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', gap: 8,
        }}>
          <span>{t('form.catalogo_erro')}</span>
          <button type="button" onClick={loadCatalog} style={{
            background: 'rgba(239,68,68,0.20)', border: '1px solid rgba(239,68,68,0.40)',
            borderRadius: 5, padding: '3px 10px', color: '#fca5a5',
            fontSize: '0.76rem', cursor: 'pointer', whiteSpace: 'nowrap',
          }}>{t('form.tentar')}</button>
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
              {subarrays.length > 1 ? t('form.subarranjo', { n: idx + 1 }) : t('form.equipamento')}
            </h3>
            {subarrays.length > 1 && (
              <button type="button" onClick={() => removeSubarray(idx)} style={{
                background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.35)',
                borderRadius: 5, padding: '2px 9px', color: '#fca5a5',
                fontSize: '0.74rem', cursor: 'pointer',
              }}>{t('form.remover')}</button>
            )}
          </div>

          <label className="field">
            <span>{t('form.modulo')}{catalogLoading ? t('form.carregando') : ''}</span>
            <select value={s.modulo} onChange={setSub(idx, 'modulo')}
              disabled={catalogLoading || catalogError}>
              {catalogLoading && <option>{t('form.opt_carregando')}</option>}
              {catalogError   && <option>{t('form.opt_erro')}</option>}
              {modulos.map(m => (
                <option key={m.nome} value={m.nome}>{m.nome} ({m.Pmpp_Wp} Wp)</option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>{t('form.inversor')}{catalogLoading ? t('form.carregando') : ''}</span>
            <select value={s.inversor} onChange={setSub(idx, 'inversor')}
              disabled={catalogLoading || catalogError}>
              {catalogLoading && <option>{t('form.opt_carregando')}</option>}
              {catalogError   && <option>{t('form.opt_erro')}</option>}
              {inversores.map(i => (
                <option key={i.nome} value={i.nome}>{i.nome} ({i.P_nomAC_kW} kW)</option>
              ))}
            </select>
          </label>

          {subField(idx, t('form.ns'), 'N_s', 'number', 1)}
          {subField(idx, t('form.nstrings'), 'N_strings', 'number', 1)}
          {subField(idx, t('form.tilt'), 'tilt')}
          {subField(idx, t('form.az'), 'az')}

          <label className="field">
            <span>{t('form.modo')}</span>
            <select
              value={s.bifacial ? 'BIFACIAL' : 'MONOFACIAL'}
              onChange={e => setSubVal(idx, 'bifacial', e.target.value === 'BIFACIAL')}
            >
              <option value="BIFACIAL">{t('form.bifacial')}</option>
              <option value="MONOFACIAL">{t('form.monofacial')}</option>
            </select>
          </label>

          {s.bifacial && (
            <>
              {subField(idx, t('form.pitch'), 'pitch')}
              {subField(idx, t('form.mod_height'), 'mod_height')}
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
        {t('form.add_sub')}
      </button>

      <section>
        <h3>{t('form.perdas')}</h3>
        <label className="field">
          <span>{t('form.montagem')}</span>
          <select value={form.tipo_montagem} onChange={set('tipo_montagem')}>
            {MONTAGENS.map(m => (
              <option key={m} value={m}>{t(`form.montagem_${m}`)}</option>
            ))}
          </select>
        </label>
        {field(t('form.cabo'), 'perda_cabo_cc_pct', 'number', 0.1)}
        {field(t('form.sujidade'), 'perda_sujidade_pct', 'number', 0.1)}
        {field(t('form.degradacao'), 'degradacao_anual_pct', 'number', 0.1)}
        {field(t('form.ano_op'), 'ano_operacao', 'number', 1)}
        {field(t('form.albedo'), 'albedo')}
      </section>

      <button
        type="submit"
        disabled={loading || catalogLoading || catalogError || algumSemModulo}
        className="btn-simular"
      >
        {loading ? t('form.simulando') : t('form.simular')}
      </button>
    </form>
  )
}
