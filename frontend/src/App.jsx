import { useState } from 'react'
import ConfigForm from './components/ConfigForm'
import SimulationProgress from './components/SimulationProgress'
import ResultsDashboard from './components/ResultsDashboard'
import { submitSimulacao } from './api/client'
import { useJobPoller } from './hooks/useJobPoller'
import './App.css'

export default function App() {
  const [jobId, setJobId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState(null)

  const job = useJobPoller(jobId)

  const handleSubmit = async (payload) => {
    setErro(null)
    setLoading(true)
    try {
      const data = await submitSimulacao(payload)
      setJobId(data.job_id)
    } catch (e) {
      setErro(e?.response?.data?.detail ?? 'Erro ao iniciar simulação.')
    } finally {
      setLoading(false)
    }
  }

  const pdfUrl = job?.pdf_url
    ? `http://localhost:8000${job.pdf_url}`
    : null

  return (
    <div className="app">
      <header className="app-header">
        <h1>Motor PVSyst <span>v2.3</span></h1>
        <p>Simulação fotovoltaica bifacial com Ray-Tracing 2D</p>
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <ConfigForm onSubmit={handleSubmit} loading={loading} />
        </aside>

        <section className="content">
          {erro && <div className="error-banner">{erro}</div>}
          {job && <SimulationProgress job={job} />}
          {job?.status === 'done' && (
            <ResultsDashboard resultado={job.resultado} pdfUrl={pdfUrl} />
          )}
          {!job && !loading && (
            <div className="empty-state">
              <p>Preencha os parâmetros e clique em <strong>Simular</strong> para iniciar.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
