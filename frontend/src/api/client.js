import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 15000,
})

export const getModulos = () => api.get('/modulos').then(r => r.data)
export const getInversores = () => api.get('/inversores').then(r => r.data)

export const submitSimulacao = (payload) =>
  api.post('/simulate', payload).then(r => r.data)

export const getJobStatus = (jobId) =>
  api.get(`/simulate/${jobId}`).then(r => r.data)

export const getPdfUrl = (filename) =>
  `http://localhost:8000/api/relatorios/${filename}`
