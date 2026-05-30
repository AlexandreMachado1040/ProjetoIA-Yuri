import { useState, useEffect } from 'react'
import { getModulos, getInversores } from '../api/client'

const DEFAULTS = {
  lat: -23.55,
  lon: -46.63,
  tz: -3,
  Ns: 28,
  Np: 3,
  n_inversores: 1,
  tilt: 15,
  azimuth: 0,
  modo: 'BIFACIAL',
  pitch: 10.0,
  h_hub: 1.5,
  mod_width: 2.382,
  albedo: 0.25,
  modo_dados: 'climatologia',
  ano_dados: '',
}

export default function ConfigForm({ onSubmit, loading }) {
  const [modulos, setModulos] = useState([])
  const [inversores, setInversores] = useState([])
  const [form, setForm] = useState({
    ...DEFAULTS,
    modulo_nome: '',
    inversor_nome: '',
  })

  useEffect(() => {
    getModulos().then(data => {
      setModulos(data)
      if (data.length) setForm(f => ({ ...f, modulo_nome: data[0].nome }))
    })
    getInversores().then(data => {
      setInversores(data)
      if (data.length) setForm(f => ({ ...f, inversor_nome: data[0].nome }))
    })
  }, [])

  const set = (k) => (e) => {
    const v = e.target.type === 'number' ? Number(e.target.value) : e.target.value
    setForm(f => ({ ...f, [k]: v }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const payload = { ...form }
    if (payload.ano_dados === '' || form.modo_dados === 'climatologia') {
      delete payload.ano_dados
    } else {
      payload.ano_dados = Number(payload.ano_dados)
    }
    onSubmit(payload)
  }

  const field = (label, key, type = 'number', step = 'any') => (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={form[key]} onChange={set(key)} step={step} />
    </label>
  )

  return (
    <form onSubmit={handleSubmit} className="config-form">
      <h2>Parâmetros de Simulação</h2>

      <section>
        <h3>Localização</h3>
        {field('Latitude (°)', 'lat')}
        {field('Longitude (°)', 'lon')}
        {field('Fuso horário (UTC)', 'tz', 'number', 1)}
      </section>

      <section>
        <h3>Equipamentos</h3>
        <label className="field">
          <span>Módulo</span>
          <select value={form.modulo_nome} onChange={set('modulo_nome')}>
            {modulos.map(m => (
              <option key={m.nome} value={m.nome}>
                {m.modelo} ({m.pmpp} Wp)
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Inversor</span>
          <select value={form.inversor_nome} onChange={set('inversor_nome')}>
            {inversores.map(i => (
              <option key={i.nome} value={i.nome}>
                {i.modelo} ({i.p_nom} kW)
              </option>
            ))}
          </select>
        </label>
      </section>

      <section>
        <h3>Arranjo</h3>
        {field('Módulos em série (Ns)', 'Ns', 'number', 1)}
        {field('Strings em paralelo (Np)', 'Np', 'number', 1)}
        {field('Número de inversores', 'n_inversores', 'number', 1)}
      </section>

      <section>
        <h3>Geometria</h3>
        {field('Inclinação (°)', 'tilt')}
        {field('Azimute (° | 0=Sul)', 'azimuth')}
        <label className="field">
          <span>Modo</span>
          <select value={form.modo} onChange={set('modo')}>
            <option value="BIFACIAL">Bifacial</option>
            <option value="MONOFACIAL">Monofacial</option>
          </select>
        </label>
      </section>

      {form.modo === 'BIFACIAL' && (
        <section>
          <h3>Bifacial</h3>
          {field('Pitch — espaçamento entre fileiras (m)', 'pitch')}
          {field('Altura do hub (m)', 'h_hub')}
          {field('Largura do módulo (m)', 'mod_width')}
          {field('Albedo', 'albedo')}
        </section>
      )}

      <section>
        <h3>Dados Climáticos</h3>
        <label className="field">
          <span>Fonte</span>
          <select value={form.modo_dados} onChange={set('modo_dados')}>
            <option value="climatologia">Climatologia (longo prazo)</option>
            <option value="horario">Horário real (NASA)</option>
          </select>
        </label>
        {form.modo_dados === 'horario' && (
          <label className="field">
            <span>Ano (2001–2023)</span>
            <input type="number" min={2001} max={2023} value={form.ano_dados}
                   onChange={set('ano_dados')} />
          </label>
        )}
      </section>

      <button type="submit" disabled={loading} className="btn-simular">
        {loading ? 'Simulando…' : 'Simular'}
      </button>
    </form>
  )
}
