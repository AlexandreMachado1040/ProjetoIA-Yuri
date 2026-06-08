import axios from 'axios'
import { CATALOGO_FALLBACK } from '../data/catalogoFallback'

const WORKER_URL = 'https://aurova-motor.alexandreclm.workers.dev'

const api = axios.create({
  baseURL: WORKER_URL,
  timeout: 30000,
})

// Cache do resultado e da Promise em voo — evita race condition quando
// getModulos() e getInversores() são chamados simultaneamente.
let _catalogoCache   = null
let _catalogoPromise = null

const sleep = (ms) => new Promise(r => setTimeout(r, ms))

// Busca /catalogo com retry e backoff — o Python Worker tem cold start lento,
// e a primeira requisição após ociosidade pode falhar enquanto o runtime sobe.
async function fetchCatalogoComRetry(tentativas = 3) {
  let ultimoErro
  for (let i = 0; i < tentativas; i++) {
    try {
      const r = await api.get('/catalogo')
      if (r.data?.modulos?.length && r.data?.inversores?.length) return r.data
      throw new Error('Catálogo vazio ou malformado')
    } catch (e) {
      ultimoErro = e
      if (i < tentativas - 1) await sleep(800 * (i + 1)) // 0,8s → 1,6s
    }
  }
  throw ultimoErro
}

function getCatalogo() {
  if (_catalogoCache) return Promise.resolve(_catalogoCache)
  if (_catalogoPromise) return _catalogoPromise

  _catalogoPromise = fetchCatalogoComRetry()
    .then(data => {
      _catalogoCache   = data
      _catalogoPromise = null
      return data
    })
    .catch(e => {
      // Fallback definitivo: catálogo estático embutido. Os seletores de
      // equipamento nunca ficam vazios, mesmo se o Worker estiver indisponível.
      console.warn('Falha ao carregar /catalogo, usando fallback estático:', e?.message ?? e)
      _catalogoCache   = CATALOGO_FALLBACK
      _catalogoPromise = null
      return CATALOGO_FALLBACK
    })

  return _catalogoPromise
}

export const getModulos    = () => getCatalogo().then(c => c.modulos)
export const getInversores = () => getCatalogo().then(c => c.inversores)

// Decide se vale repetir: cold start do Python Worker devolve 5xx (ou nenhum
// response → "Network Error" sem CORS). Erros 4xx são de validação — não repetir.
function devoRepetir(e) {
  const status = e?.response?.status
  if (status === undefined) return true        // sem response = falha de rede/CORS/cold start
  return status >= 500                          // erro de servidor
}

// Backoff generoso: o cold start do Python Worker pode levar vários segundos,
// e a 1ª requisição do navegador (preflight OPTIONS) falha se pegar o runtime
// ainda subindo. Espera acumulada ~2+4+6+8 = 20s antes de desistir.
const _BACKOFF_MS = [2000, 4000, 6000, 8000]

export async function submitSimulacao(payload, tentativas = 5) {
  let ultimoErro
  for (let i = 0; i < tentativas; i++) {
    try {
      const r = await api.post('/simulate', payload)
      return r.data
    } catch (e) {
      ultimoErro = e
      if (i < tentativas - 1 && devoRepetir(e)) {
        await sleep(_BACKOFF_MS[Math.min(i, _BACKOFF_MS.length - 1)])
        continue
      }
      throw e
    }
  }
  throw ultimoErro
}

// Análise diária (365 dias) — endpoint mais pesado, timeout maior + retry.
export async function getDailyAnalysis(payload, tentativas = 3) {
  let ultimoErro
  for (let i = 0; i < tentativas; i++) {
    try {
      const r = await api.post('/daily', payload, { timeout: 60000 })
      return r.data
    } catch (e) {
      ultimoErro = e
      if (i < tentativas - 1 && devoRepetir(e)) {
        await sleep(_BACKOFF_MS[Math.min(i, _BACKOFF_MS.length - 1)])
        continue
      }
      throw e
    }
  }
  throw ultimoErro
}

// Aquece o Worker em segundo plano (dispara cold start cedo). Chamado quando o
// app carrega, para que o motor já esteja quente quando o usuário clicar Simular.
export function prewarm() {
  api.get('/').catch(() => {})
}
