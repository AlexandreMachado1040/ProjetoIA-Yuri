import axios from 'axios'

const WORKER_URL = 'https://motor-pvsyst.alexandreclm.workers.dev'

const api = axios.create({
  baseURL: WORKER_URL,
  timeout: 30000,
})

let _catalogoCache = null

async function getCatalogo() {
  if (!_catalogoCache) {
    const r = await api.get('/catalogo')
    _catalogoCache = r.data
  }
  return _catalogoCache
}

export const getModulos    = () => getCatalogo().then(c => c.modulos)
export const getInversores = () => getCatalogo().then(c => c.inversores)

export const submitSimulacao = (payload) =>
  api.post('/simulate', payload).then(r => r.data)
