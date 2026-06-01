import { useState } from 'react'
import ConfigForm from './components/ConfigForm'
import ResultsDashboard from './components/ResultsDashboard'
import { submitSimulacao } from './api/client'
import './App.css'

export default function App() {
  const [resultado, setResultado] = useState(null)
  const [loading, setLoading]     = useState(false)
  const [erro, setErro]           = useState(null)

  const handleSubmit = async (payload) => {
    setErro(null)
    setLoading(true)
    setResultado(null)
    try {
      const data = await submitSimulacao(payload)
      if (data.error) throw new Error(data.error)
      setResultado(data)
    } catch (e) {
      setErro(e?.response?.data?.error ?? e?.message ?? 'Erro ao executar simulação.')
    } finally {
      setLoading(false)
    }
  }

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
          {loading && (
            <div className="empty-state">
              <p>Simulando… aguarde.</p>
            </div>
          )}
          {resultado && <ResultsDashboard resultado={resultado} />}
          {!resultado && !loading && !erro && (
            <div className="empty-state">
              <p>Preencha os parâmetros e clique em <strong>Simular</strong> para iniciar.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
