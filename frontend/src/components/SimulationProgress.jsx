export default function SimulationProgress({ job }) {
  if (!job) return null

  const isError = job.status === 'error'
  const isDone  = job.status === 'done'

  return (
    <div className={`progress-box ${isError ? 'error' : isDone ? 'done' : 'running'}`}>
      <div className="progress-header">
        <span className="status-badge">{statusLabel(job.status)}</span>
        <span className="progress-pct">{job.progress}%</span>
      </div>
      <div className="progress-bar-track">
        <div
          className="progress-bar-fill"
          style={{ width: `${job.progress}%` }}
        />
      </div>
      <p className="progress-msg">{job.message}</p>
    </div>
  )
}

function statusLabel(s) {
  return { pending: 'Aguardando', running: 'Simulando', done: 'Concluído', error: 'Erro' }[s] ?? s
}
