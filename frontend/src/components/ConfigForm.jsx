import { useState, useEffect } from 'react'
import { getModulos, getInversores } from '../api/client'

const DEFAULTS = {
  lat:        -23.55,
  lon:        -46.63,
  tz:         -3,
  N_s:        28,
  N_strings:  3,
  tilt:       20.8,
  az:         180.0,
  bifacial:   true,
  pitch:      2.826,
  mod_height: 2.0,
  albedo:     0.30,
  modulo:     '',
  inversor:   '',
}

export default function ConfigForm({ onSubmit, loading }) {
  const [modulos, setModulos]     = useState([])
  const [inversores, setInversores] = useState([])
  const [form, setForm]           = useState(DEFAULTS)

  useEffect(() => {
    getModulos().then(data => {
      setModulos(data)
      if (data.length) setForm(f => ({ ...f, modulo: data[0].nome }))
    })
    getInversores().then(data => {
      setInversores(data)
      if (data.length) setForm(f => ({ ...f, inversor: data[0].nome }))
    })
  }, [])

  const set = (k) => (e) => {
    const v = e.target.type === 'number' ? Number(e.target.value) : e.target.value
    setForm(f => ({ ...f, [k]: v }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit({
      lat:        form.lat,
      lon:        form.lon,
      tz:         form.tz,
      tilt:       form.tilt,
      az:         form.az,
      N_s:        form.N_s,
      N_strings:  form.N_strings,
      bifacial:   form.bifacial,
      albedo:     form.albedo,
      pitch:      form.pitch,
      mod_height: form.mod_height,
      N_seg:      0,
      N_rays:     0,
      modulo:     form.modulo,
      inversor:   form.inversor,
    })
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
          <select value={form.modulo} onChange={set('modulo')}>
            {modulos.map(m => (
              <option key={m.nome} value={m.nome}>
                {m.nome} ({m.Pmpp_Wp} Wp)
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Inversor</span>
          <select value={form.inversor} onChange={set('inversor')}>
            {inversores.map(i => (
              <option key={i.nome} value={i.nome}>
                {i.nome} ({i.P_nomAC_kW} kW)
              </option>
            ))}
          </select>
        </label>
      </section>

      <section>
        <h3>Arranjo</h3>
        {field('Módulos em série (N_s)', 'N_s', 'number', 1)}
        {field('Strings em paralelo (N_strings)', 'N_strings', 'number', 1)}
      </section>

      <section>
        <h3>Geometria</h3>
        {field('Inclinação (°)', 'tilt')}
        {field('Azimute (° | 180=Norte HS)', 'az')}
        <label className="field">
          <span>Modo</span>
          <select
            value={form.bifacial ? 'BIFACIAL' : 'MONOFACIAL'}
            onChange={e => setForm(f => ({ ...f, bifacial: e.target.value === 'BIFACIAL' }))}
          >
            <option value="BIFACIAL">Bifacial</option>
            <option value="MONOFACIAL">Monofacial</option>
          </select>
        </label>
      </section>

      {form.bifacial && (
        <section>
          <h3>Bifacial</h3>
          {field('Pitch — espaçamento entre fileiras (m)', 'pitch')}
          {field('Altura do módulo no plano inclinado (m)', 'mod_height')}
          {field('Albedo', 'albedo')}
        </section>
      )}

      <button type="submit" disabled={loading} className="btn-simular">
        {loading ? 'Simulando…' : 'Simular'}
      </button>
    </form>
  )
}
