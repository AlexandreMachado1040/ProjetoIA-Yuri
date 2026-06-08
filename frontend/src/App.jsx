import { useState, useEffect } from 'react'
import ConfigForm from './components/ConfigForm'
import ResultsDashboard from './components/ResultsDashboard'
import { submitSimulacao, prewarm } from './api/client'
import './App.css'

// Versão da aplicação (exibida no cabeçalho). Atualizar a cada release.
const APP_VERSION = 'v3.0'

export default function App() {
  const [resultado, setResultado] = useState(null)
  const [payloadAtual, setPayloadAtual] = useState(null)
  const [loading, setLoading]     = useState(false)
  const [erro, setErro]           = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  // Aquece o Worker assim que o app carrega, para evitar cold start na 1ª simulação.
  useEffect(() => { prewarm() }, [])

  const handleSubmit = async (payload) => {
    setErro(null)
    setLoading(true)
    setResultado(null)
    try {
      const data = await submitSimulacao(payload)
      if (data.error) throw new Error(data.error)
      setResultado(data)
      setPayloadAtual(payload)
      setSidebarOpen(false)
    } catch (e) {
      const semResposta = !e?.response
      const msg = e?.response?.data?.error
        ?? (semResposta
            ? 'Não foi possível contatar o servidor (o motor pode estar reiniciando). Aguarde alguns segundos e tente novamente.'
            : (e?.message ?? 'Erro ao executar simulação.'))
      setErro(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-logo">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="40" height="40" aria-label="Aurova">
            <defs>
              <linearGradient id="hg1" x1="0%" y1="100%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#005FFF"/>
                <stop offset="100%" stopColor="#00C8FF"/>
              </linearGradient>
            </defs>
            <path d="M 12 130 A 88 88 0 0 1 188 130" stroke="#00AAFF" strokeWidth="6" fill="none" strokeLinecap="round" opacity="0.48"/>
            <path d="M 30 130 A 70 70 0 0 1 170 130" stroke="#0077EE" strokeWidth="9" fill="none" strokeLinecap="round" opacity="0.70"/>
            <path d="M 50 130 A 50 50 0 0 1 150 130" stroke="#005FFF" strokeWidth="14" fill="none" strokeLinecap="round"/>
            <circle cx="100" cy="134" r="11" fill="url(#hg1)"/>
          </svg>
          <div className="header-text">
            <h1>Aurova <span>Motor Solar {APP_VERSION}</span></h1>
            <p>Simulação fotovoltaica bifacial com Ray-Tracing 2D</p>
          </div>
        </div>
        <button
          className="btn-sidebar-toggle"
          onClick={() => setSidebarOpen(o => !o)}
        >
          {sidebarOpen ? '✕ Fechar' : '⚙ Parâmetros'}
        </button>
      </header>

      <main className="app-main">
        <aside className={`sidebar${sidebarOpen ? '' : ' collapsed'}`}>
          <ConfigForm onSubmit={handleSubmit} loading={loading} />
        </aside>

        <section className="content">
          {erro && <div className="error-banner">{erro}</div>}
          {loading && (
            <div className="empty-state">
              <p>Simulando… aguarde.</p>
            </div>
          )}
          {resultado && <ResultsDashboard resultado={resultado} inputPayload={payloadAtual} />}
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
