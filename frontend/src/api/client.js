import axios from 'axios'

const WORKER_URL = 'https://aurova-motor.alexandreclm.workers.dev'

const api = axios.create({
  baseURL: WORKER_URL,
  timeout: 30000,
})

// Cache do resultado e da Promise em voo — evita race condition quando
// getModulos() e getInversores() são chamados simultaneamente.
let _catalogoCache   = null
let _catalogoPromise = null

function getCatalogo() {
  if (_catalogoCache) return Promise.resolve(_catalogoCache)
  if (_catalogoPromise) return _catalogoPromise

  _catalogoPromise = api.get('/catalogo')
    .then(r => {
      _catalogoCache   = r.data
      _catalogoPromise = null
      return r.data
    })
    .catch(e => {
      _catalogoPromise = null   // permite nova tentativa
      throw e
    })

  return _catalogoPromise
}

export const getModulos    = () => getCatalogo().then(c => c.modulos)
export const getInversores = () => getCatalogo().then(c => c.inversores)

export const submitSimulacao = (payload) =>
  api.post('/simulate', payload).then(r => r.data)
