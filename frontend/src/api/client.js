import axios from 'axios'

// ─────────────────────────────────────────────────────────────────────────────
// Cliente da API — Cloudflare Worker "motor-pvsyst"
//
// O frontend foi originalmente escrito para o backend FastAPI (fluxo assíncrono
// com job + polling, /modulos e /inversores separados, geração de PDF). O worker
// do Cloudflare expõe uma API mais enxuta e SÍNCRONA (/catalogo + POST /simulate).
// Esta camada faz a tradução entre os dois contratos, mantendo o restante do
// frontend (App, ConfigForm, dashboard, hooks) sem alterações.
//
// Configure a URL via .env (VITE_WORKER_URL) — veja frontend/.env.example.
// ─────────────────────────────────────────────────────────────────────────────

const WORKER_URL = (
  import.meta.env.VITE_WORKER_URL || 'https://motor-pvsyst.SEU-SUBDOMINIO.workers.dev'
).replace(/\/+$/, '')

const api = axios.create({
  baseURL: WORKER_URL,
  timeout: 30000, // simulação pode levar alguns segundos no worker
})

// ── Catálogo ─────────────────────────────────────────────────────────────────
// O worker entrega módulos e inversores juntos em GET /catalogo. Cacheamos a
// promessa para não baixar duas vezes (ConfigForm chama getModulos + getInversores).
let _catalogoPromise = null
const _catalogo = () => {
  if (!_catalogoPromise) {
    _catalogoPromise = api.get('/catalogo').then(r => r.data).catch(e => {
      _catalogoPromise = null // permite nova tentativa em caso de falha
      throw e
    })
  }
  return _catalogoPromise
}

export const getModulos = () =>
  _catalogo().then(c => (c.modulos ?? []).map(m => ({
    nome:          m.nome,
    modelo:        m.nome,
    pmpp:          m.Pmpp_Wp,
    bifacialidade: m.phi,
  })))

export const getInversores = () =>
  _catalogo().then(c => (c.inversores ?? []).map(i => ({
    nome:    i.nome,
    modelo:  i.nome,
    p_nom:   i.P_nomAC_kW,
    eta_max: i.eta_max_pct,
    nb_mppt: i.N_mppt,
  })))

// ── Simulação ────────────────────────────────────────────────────────────────
// Adaptação do fluxo de job: o worker responde de forma síncrona, então
// guardamos o resultado em memória e devolvemos um job_id sintético que o
// useJobPoller consulta uma vez (status já vem "done").
const _jobs = new Map()

// Traduz o payload do ConfigForm (nomes do backend) para o esperado pelo worker.
const _toWorkerPayload = (p) => ({
  lat:        p.lat,
  lon:        p.lon,
  tz:         p.tz,
  tilt:       p.tilt,
  az:         p.azimuth,
  N_s:        p.Ns,
  N_strings:  p.Np,
  bifacial:   p.modo !== 'MONOFACIAL',
  albedo:     p.albedo,
  pitch:      p.pitch,
  mod_height: p.h_hub,
  modulo:     p.modulo_nome,
  inversor:   p.inversor_nome,
})

// Traduz o resultado do worker para o formato consumido pelo ResultsDashboard.
// Campos que o worker (versão rápida) não retorna ficam indefinidos — os
// componentes correspondentes (histograma, diagrama de perdas, E_array mensal)
// se auto-ocultam via `return null`.
const _toResultado = (r) => {
  const ft_f = r.FT_frontal  ?? 0
  const ft_b = r.FT_bifacial ?? 0
  const ghi  = r.monthly_GHI ?? []
  const eKwh = r.E_grid_anual_kWh

  return {
    GHI_anual:        r.GHI_anual,
    ganho_bifacial:   r.ganho_bif_pct,
    E_grid_anual_MWh: eKwh != null ? +(eKwh / 1000).toFixed(1) : undefined,
    PR_pct:           r.PR_pct,
    // Yield final: energia na rede por kWp instalado.
    Yf: (eKwh != null && r.P_nom_stc_kWp) ? Math.round(eKwh / r.P_nom_stc_kWp) : undefined,
    P_nom_stc_kWp:    r.P_nom_stc_kWp,
    // Razão DC/AC: potência do array sobre potência nominal do inversor.
    R_DC_AC: (r.P_nom_stc_kWp && r.P_nom_AC_kW)
      ? +(r.P_nom_stc_kWp / r.P_nom_AC_kW).toFixed(2)
      : undefined,
    fonte_dados: 'NASA POWER (Cloudflare Worker)',
    monthly_grid_kWh: r.monthly_E_grid,
    monthly_GHI:      ghi,
    // Irradiância frontal/bifacial mensal derivada do fator de transposição anual.
    monthly_Gf: ghi.map(g => +(g * ft_f).toFixed(1)),
    monthly_Gb: ghi.map(g => +(g * ft_b).toFixed(1)),
  }
}

export const submitSimulacao = (payload) =>
  api.post('/simulate', _toWorkerPayload(payload)).then(r => {
    if (r.data?.error) {
      const err = new Error(r.data.error)
      err.response = { data: { detail: r.data.error } }
      throw err
    }
    const job_id = `w_${Date.now()}`
    _jobs.set(job_id, {
      job_id,
      status:    'done',
      progress:  100,
      message:   'Simulação concluída.',
      pdf_url:   null, // worker não gera PDF
      resultado: _toResultado(r.data),
    })
    return { job_id }
  })

export const getJobStatus = (jobId) =>
  Promise.resolve(
    _jobs.get(jobId) ?? {
      job_id:   jobId,
      status:   'error',
      progress: 0,
      message:  'Job não encontrado.',
    }
  )

// O worker não disponibiliza PDF; mantido por compatibilidade de assinatura.
export const getPdfUrl = () => null
