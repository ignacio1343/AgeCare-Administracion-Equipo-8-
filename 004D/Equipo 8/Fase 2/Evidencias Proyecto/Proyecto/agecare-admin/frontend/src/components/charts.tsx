import { useEffect, useRef, useState } from 'react'

// Gráficos SVG livianos (sin librerías). Paleta categórica validada (CVD y contraste):
// serie 1 azul #2a78d6, serie 2 naranja #eb6834. Rampa secuencial azul para magnitudes.
export const SERIE = ['#2a78d6', '#eb6834']
const RAMPA = ['#cde2fb', '#b7d3f6', '#9ec5f4', '#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6', '#256abf', '#1c5cab', '#184f95', '#104281', '#0d366b']

/** Color de celda para un valor 0..1 y si el texto encima debe ser blanco */
export function rampa(v: number): { bg: string; claro: boolean } {
  const i = Math.max(0, Math.min(RAMPA.length - 1, Math.round(v * (RAMPA.length - 1))))
  return { bg: RAMPA[i], claro: i >= 6 }
}

function useAncho<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [w, setW] = useState(640)
  useEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, e.contentRect.width)))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return [ref, w] as const
}

function ticks(max: number, n = 4) {
  if (max <= 0) return [0, 1]
  const raw = max / n
  const p = 10 ** Math.floor(Math.log10(raw))
  const paso = [1, 2, 2.5, 5, 10].map(m => m * p).find(s => s >= raw) ?? raw
  const out = []
  for (let v = 0; v <= max + paso * 0.001; v += paso) out.push(v)
  if (out[out.length - 1] < max) out.push(out[out.length - 1] + paso)
  return out
}

export interface Serie { nombre: string; valores: (number | null)[] }

/** Gráfico de líneas con una sola escala Y, cruz de lectura (crosshair) y tooltip */
export function LineChart({ etiquetas, series, alto = 220, unidad = '', decimales = 0 }:
  { etiquetas: string[]; series: Serie[]; alto?: number; unidad?: string; decimales?: number }) {
  const [ref, w] = useAncho<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const m = { t: 12, r: 64, b: 26, l: 44 }
  const iw = w - m.l - m.r, ih = alto - m.t - m.b
  const max = Math.max(1, ...series.flatMap(s => s.valores.filter((v): v is number => v != null)))
  const ts = ticks(max)
  const top = ts[ts.length - 1]
  const n = etiquetas.length
  const x = (i: number) => m.l + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw)
  const y = (v: number) => m.t + ih - (v / top) * ih
  const fmt = (v: number | null) => (v == null ? '—' : `${v.toLocaleString('es-CL', { maximumFractionDigits: decimales })}${unidad}`)
  const cadaX = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(iw / 70))))

  const path = (vals: (number | null)[]) => {
    let d = '', abierto = false
    vals.forEach((v, i) => {
      if (v == null) { abierto = false; return }
      d += `${abierto ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`
      abierto = true
    })
    return d
  }
  const mover = (e: React.PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const px = e.clientX - r.left
    setHover(Math.max(0, Math.min(n - 1, Math.round((px / r.width) * (n - 1)))))
  }

  return (
    <div className="chart-wrap" ref={ref}>
      {series.length > 1 && (
        <div className="legend">{series.map((s, i) => <span key={s.nombre}><i style={{ background: SERIE[i] }} />{s.nombre}</span>)}</div>
      )}
      <svg width={w} height={alto} role="img" aria-label={`Gráfico de líneas: ${series.map(s => s.nombre).join(' y ')}`}>
        {ts.map(t => (
          <g key={t}>
            <line x1={m.l} x2={m.l + iw} y1={y(t)} y2={y(t)} stroke="#e4e8ee" strokeWidth={1} />
            <text x={m.l - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize={11} fill="#8b95a3">{t.toLocaleString('es-CL')}</text>
          </g>
        ))}
        {etiquetas.map((e, i) => (i % cadaX === 0 || i === n - 1) && (
          <text key={i} x={x(i)} y={alto - 6} textAnchor="middle" fontSize={11} fill="#8b95a3">{e}</text>
        ))}
        {series.map((s, si) => <path key={s.nombre} d={path(s.valores)} fill="none" stroke={SERIE[si]} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />)}
        {/* etiqueta directa al final de cada serie */}
        {series.map((s, si) => {
          let i = s.valores.length - 1
          while (i >= 0 && s.valores[i] == null) i--
          if (i < 0) return null
          const v = s.valores[i] as number
          const otro = series.length > 1 ? series[1 - si]?.valores[i] : null
          const dy = otro != null && Math.abs(y(otro) - y(v)) < 14 ? (v >= otro ? -7 : 7) : 0
          return (
            <g key={s.nombre}>
              <circle cx={x(i)} cy={y(v)} r={4} fill={SERIE[si]} stroke="#fff" strokeWidth={2} />
              <text x={x(i) + 8} y={y(v) + dy} dy="0.32em" fontSize={11.5} fontWeight={600} fill="#1f2733">{fmt(v)}</text>
            </g>
          )
        })}
        {hover != null && (
          <g pointerEvents="none">
            <line x1={x(hover)} x2={x(hover)} y1={m.t} y2={m.t + ih} stroke="#8b95a3" strokeWidth={1} />
            {series.map((s, si) => s.valores[hover] != null &&
              <circle key={s.nombre} cx={x(hover)} cy={y(s.valores[hover] as number)} r={4} fill={SERIE[si]} stroke="#fff" strokeWidth={2} />)}
          </g>
        )}
        <rect x={m.l} y={m.t} width={iw} height={ih} fill="transparent" onPointerMove={mover} onPointerLeave={() => setHover(null)} />
      </svg>
      {hover != null && (
        <div className="tip" style={{ left: Math.min(Math.max(x(hover), 70), w - 70), top: m.t + 24 }}>
          <div style={{ opacity: .75, marginBottom: 2 }}>{etiquetas[hover]}</div>
          {series.map((s, si) => (
            <div key={s.nombre}><i style={{ display: 'inline-block', width: 10, height: 2, background: SERIE[si], verticalAlign: 'middle', marginRight: 6 }} />
              <b>{fmt(s.valores[hover])}</b> {s.nombre}</div>
          ))}
        </div>
      )}
    </div>
  )
}
