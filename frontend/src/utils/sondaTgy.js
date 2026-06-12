// Utilidades compartilhadas para os TGYs SONDA (ConfigForm, análise diária
// e Explorador Diário). Cache por sessão — cada arquivo (~84 kB) baixa 1 vez.

const _cache = {}

export async function carregarTGY(arquivo) {
  if (!_cache[arquivo]) {
    const resp = await fetch(arquivo)
    if (!resp.ok) throw new Error(`TGY HTTP ${resp.status}`)
    _cache[arquivo] = await resp.json()
  }
  return _cache[arquivo]
}

// Achata meses → 365 dias × 24 h (W/m² médios da hora), na ordem do ano.
export function achatarHorasTGY(tgy) {
  const ghi = [], dni = [], dhi = []
  for (const m of tgy.meses) {
    for (const d of m.dias) {
      ghi.push(d.ghi); dni.push(d.dni); dhi.push(d.dhi)
    }
  }
  return { ghi, dni, dhi }
}
