// Exportação de resultados — CSV (Excel PT-BR), PNG dos gráficos e PDF (impressão).

const MES_ABREV = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                   'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

// Número no padrão brasileiro (vírgula decimal), sem separador de milhar
// para não conflitar com o ";" do CSV.
const num = (v, dec = 2) =>
  (v === null || v === undefined || Number.isNaN(+v)) ? '' : (+v).toFixed(dec).replace('.', ',')

// Protege campos de texto que possam conter ";" ou aspas.
const txt = (v) => {
  const s = String(v ?? '')
  return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function baixarBlob(blob, nome) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = nome
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 5000)
}

function dataHoje() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return {
    rotulo: `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`,
    arquivo: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`,
  }
}

// ── CSV ─────────────────────────────────────────────────────────────────────
export function exportarCSV(resultado, inputPayload) {
  if (!resultado) return
  const r = resultado
  const L = []
  const hoje = dataHoje()

  L.push('Aurova Motor Solar — Relatório de Simulação')
  L.push(`Gerado em;${hoje.rotulo}`)
  if (r.modulo_nome)   L.push(`Módulo;${txt(r.modulo_nome)}`)
  if (r.inversor_nome) L.push(`Inversor;${txt(r.inversor_nome)}`)
  if (r.nasa_source)   L.push(`Fonte de dados;${txt(r.nasa_source)}`)
  if (inputPayload?.lat !== undefined) {
    L.push(`Latitude;${num(inputPayload.lat, 4)}`)
    L.push(`Longitude;${num(inputPayload.lon, 4)}`)
  }
  L.push('')

  L.push('[Indicadores anuais]')
  L.push(`E_Grid anual (kWh);${num(r.E_grid_anual_kWh, 0)}`)
  L.push(`PR (%);${num(r.PR_pct, 1)}`)
  L.push(`GHI anual (kWh/m²);${num(r.GHI_anual, 1)}`)
  L.push(`Ganho bifacial (%);${num(r.ganho_bif_pct, 2)}`)
  L.push(`FT frontal;${num(r.FT_frontal, 3)}`)
  L.push(`FT bifacial;${num(r.FT_bifacial, 3)}`)
  L.push(`Potência STC (kWp);${num(r.P_nom_stc_kWp, 2)}`)
  L.push(`Potência AC (kW);${num(r.P_nom_AC_kW, 2)}`)
  if (r.P_nom_stc_kWp > 0) {
    L.push(`Yf (kWh/kWp);${num(r.E_grid_anual_kWh / r.P_nom_stc_kWp, 0)}`)
  }
  if (r.P_nom_AC_kW > 0) {
    L.push(`R DC/AC;${num(r.P_nom_stc_kWp / r.P_nom_AC_kW, 2)}`)
  }
  L.push('')

  if (r.monthly_E_grid?.length === 12) {
    L.push('[Produção mensal]')
    L.push('Mês;GHI (kWh/m²);G frontal (kWh/m²);E_Array (kWh);E_Grid (kWh)')
    for (let m = 0; m < 12; m++) {
      L.push([
        MES_ABREV[m],
        num(r.monthly_GHI?.[m], 1),
        num(r.monthly_Gf?.[m], 1),
        num(r.monthly_E_arr?.[m], 1),
        num(r.monthly_E_grid?.[m], 1),
      ].join(';'))
    }
    L.push('')
  }

  if (r.loss_chain?.length) {
    L.push('[Cadeia de perdas]')
    L.push('Etapa;Valor;Unidade')
    for (const item of r.loss_chain) {
      L.push(item.tipo === 'total'
        ? `${txt(item.label)};${num(item.value, 1)};${txt(item.unit ?? '')}`
        : `${txt(item.label)};${num(item.value, 2)};%`)
    }
    L.push('')
  }

  if (r.is_plant && r.subarrays?.length) {
    L.push('[Sub-arranjos]')
    L.push('#;Inversor;Módulo;Séries;Strings;kWp;R DC/AC;E_Grid (kWh);PR (%)')
    for (const s of r.subarrays) {
      L.push([
        s.idx, txt(s.inversor_nome), txt(s.modulo_nome),
        s.N_s, s.N_strings,
        num(s.P_nom_stc_kWp, 2), num(s.R_DC_AC, 2),
        num(s.E_grid_anual_kWh, 0), num(s.PR_pct, 1),
      ].join(';'))
    }
    L.push('')

    L.push('[Produção mensal por sub-arranjo (E_Grid kWh)]')
    L.push(['Mês', ...r.subarrays.map(s => txt(`SA${s.idx} — ${s.inversor_nome}`))].join(';'))
    for (let m = 0; m < 12; m++) {
      L.push([MES_ABREV[m], ...r.subarrays.map(s => num(s.monthly_E_grid?.[m], 1))].join(';'))
    }
    L.push('')

    for (const s of r.subarrays) {
      if (!s.loss_chain?.length) continue
      L.push(`[Cadeia de perdas — Sub-arranjo ${s.idx} (${s.inversor_nome})]`)
      L.push('Etapa;Valor;Unidade')
      for (const item of s.loss_chain) {
        L.push(item.tipo === 'total'
          ? `${txt(item.label)};${num(item.value, 1)};${txt(item.unit ?? '')}`
          : `${txt(item.label)};${num(item.value, 2)};%`)
      }
      L.push('')
    }
  }

  // BOM para o Excel reconhecer UTF-8; ";" como separador (padrão PT-BR).
  const blob = new Blob(['﻿' + L.join('\r\n')], { type: 'text/csv;charset=utf-8' })
  baixarBlob(blob, `aurova_simulacao_${hoje.arquivo}.csv`)
}

// ── PNG dos gráficos ────────────────────────────────────────────────────────
// Copia para o clone os estilos calculados (o CSS do app não acompanha o SVG
// serializado — sem isso, textos e grades sairiam com as cores padrão).
const PROPS_SVG = [
  'fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'stroke-linecap',
  'opacity', 'font-size', 'font-family', 'font-weight', 'text-anchor',
]
function inlinarEstilos(origem, clone) {
  const o = [origem, ...origem.querySelectorAll('*')]
  const c = [clone, ...clone.querySelectorAll('*')]
  for (let i = 0; i < o.length; i++) {
    const cs = window.getComputedStyle(o[i])
    for (const p of PROPS_SVG) {
      const v = cs.getPropertyValue(p)
      if (v) c[i].style.setProperty(p, v)
    }
  }
}

function svgParaPng(svg, nome, escala = 2) {
  return new Promise((resolve) => {
    const rect = svg.getBoundingClientRect()
    const w = Math.ceil(rect.width)
    const h = Math.ceil(rect.height)
    if (!w || !h) return resolve(false)

    const clone = svg.cloneNode(true)
    inlinarEstilos(svg, clone)
    clone.setAttribute('width', w)
    clone.setAttribute('height', h)

    const xml = new XMLSerializer().serializeToString(clone)
    const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml)

    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width  = w * escala
      canvas.height = h * escala
      const ctx = canvas.getContext('2d')
      ctx.scale(escala, escala)
      ctx.fillStyle = '#0b1226'   // fundo do cartão (o SVG é transparente)
      ctx.fillRect(0, 0, w, h)
      ctx.drawImage(img, 0, 0, w, h)
      canvas.toBlob((blob) => {
        if (blob) baixarBlob(blob, nome)
        resolve(!!blob)
      }, 'image/png')
    }
    img.onerror = () => resolve(false)
    img.src = url
  })
}

const slug = (s) => s.toLowerCase()
  .normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
  .slice(0, 48)

// Baixa um PNG por gráfico visível (um arquivo por .chart-card com SVG).
// O navegador pode pedir permissão para múltiplos downloads.
export async function exportarPNGs() {
  const cards = document.querySelectorAll('.results-dashboard .chart-card')
  const hoje = dataHoje()
  let n = 0
  for (const card of cards) {
    const svg = card.querySelector('svg.recharts-surface') ?? card.querySelector('svg')
    if (!svg) continue
    const titulo = card.querySelector('h3')?.textContent ?? `grafico_${n + 1}`
    n++
    await svgParaPng(svg, `aurova_${String(n).padStart(2, '0')}_${slug(titulo)}_${hoje.arquivo}.png`)
    // Pausa curta entre downloads para o navegador não descartar nenhum.
    await new Promise(r => setTimeout(r, 350))
  }
  return n
}

