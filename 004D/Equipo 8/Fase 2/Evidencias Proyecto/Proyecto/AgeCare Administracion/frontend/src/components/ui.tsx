import type { ReactNode } from 'react'

export const ESTADOS: Record<string, { label: string; cls: string; ico: string }> = {
  abierto: { label: 'Abierto', cls: 'neutral', ico: '●' },
  en_curso: { label: 'En curso', cls: 'warn', ico: '▲' },
  esperando_usuario: { label: 'Esperando usuario', cls: 'info', ico: '◷' },
  resuelto: { label: 'Resuelto', cls: 'ok', ico: '✔' },
  cerrado: { label: 'Cerrado', cls: 'muted', ico: '■' },
}
export const PRIORIDADES: Record<string, { label: string; cls: string }> = {
  baja: { label: 'Baja', cls: 'neutral' }, media: { label: 'Media', cls: 'neutral' },
  alta: { label: 'Alta', cls: 'serious' }, critica: { label: 'Crítica', cls: 'crit' },
}
export const CANALES: Record<string, string> = { app: 'App', correo: 'Correo', telefono: 'Teléfono', consola: 'Consola' }
export const PERFILES: Record<string, string> = { familiar: 'Familiar', cuidadora: 'Cuidadora', adulto_mayor: 'Adulto mayor', medico: 'Médico' }
export const ROLES: Record<string, string> = { admin: 'Administrador', analista: 'Analista', soporte: 'Agente de soporte', editor: 'Editor de contenido', moderador: 'Moderador' }

export function EstadoChip({ estado }: { estado: string }) {
  const e = ESTADOS[estado] ?? { label: estado, cls: 'neutral', ico: '●' }
  return <span className={`chip ${e.cls}`}>{e.ico} {e.label}</span>
}
export function PrioridadChip({ prioridad }: { prioridad: string }) {
  const p = PRIORIDADES[prioridad] ?? { label: prioridad, cls: 'neutral' }
  return <span className={`chip ${p.cls}`}>◆ {p.label}</span>
}

const dtf = new Intl.DateTimeFormat('es-CL', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
const df = new Intl.DateTimeFormat('es-CL', { day: '2-digit', month: 'short', year: 'numeric' })
export const fechaHora = (s?: string | null) => (s ? dtf.format(new Date(s)) : '—')
export const fecha = (s?: string | null) => (s ? df.format(new Date(s)) : '—')
export function hace(s?: string | null) {
  if (!s) return '—'
  const min = Math.round((Date.now() - new Date(s).getTime()) / 60000)
  if (min < 1) return 'recién'
  if (min < 60) return `hace ${min} min`
  const h = Math.round(min / 60)
  if (h < 24) return `hace ${h} h`
  return `hace ${Math.round(h / 24)} d`
}

export function Card({ title, sub, actions, children }: { title?: ReactNode; sub?: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {(title || actions) && (
        <div className="card-head">
          <div>{title && <div className="card-title">{title}</div>}{sub && <div className="card-sub">{sub}</div>}</div>
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null
  const msg = error instanceof Error ? error.message : String(error)
  return <div className="alert crit" role="alert">{msg}</div>
}

export function Paginacion({ page, pageSize, total, onChange }: { page: number; pageSize: number; total: number; onChange: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="pager">
      <span>{total === 0 ? 'Sin resultados' : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} de ${total}`}</span>
      <button className="btn ghost sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>‹ Anterior</button>
      <button className="btn ghost sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>Siguiente ›</button>
    </div>
  )
}

export function Cargando() { return <div className="loading">Cargando…</div> }

// ---------------------------------------------------------------- formato y piezas compartidas (Sprints 3–5)
const nf = new Intl.NumberFormat('es-CL')
export const num = (n?: number | null, d = 0) => (n == null ? '—' : n.toLocaleString('es-CL', { maximumFractionDigits: d, minimumFractionDigits: 0 }))
export const clp = (n?: number | null) => (n == null ? '—' : `$${nf.format(Math.round(n))}`)
export const pct = (n?: number | null, d = 1) => (n == null ? '—' : `${(n * 100).toLocaleString('es-CL', { maximumFractionDigits: d })}%`)
export function Delta({ v, invertir = false }: { v: number | null | undefined; invertir?: boolean }) {
  if (v == null) return <div className="kpi-delta">sin periodo anterior</div>
  const bueno = invertir ? v <= 0 : v >= 0
  return <div className={`kpi-delta ${bueno ? 'up' : 'down'}`}>{v >= 0 ? '▲' : '▼'} {pct(Math.abs(v))} vs. periodo anterior</div>
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: [T, string][] }) {
  return (
    <div className="tabs" role="tablist">
      {items.map(([k, l]) => <button key={k} role="tab" aria-selected={value === k} className={value === k ? 'on' : ''} onClick={() => onChange(k)}>{l}</button>)}
    </div>
  )
}

// Semáforo de estados técnicos y de negocio: siempre ícono + texto, nunca solo color
export const ESTADO_GEN: Record<string, { label: string; cls: string; ico: string }> = {
  operativo: { label: 'Operativo', cls: 'ok', ico: '✔' }, degradado: { label: 'Degradado', cls: 'warn', ico: '▲' },
  caido: { label: 'Caído', cls: 'crit', ico: '✖' }, mantenimiento: { label: 'Mantenimiento', cls: 'info', ico: '⚙' },
  investigando: { label: 'Investigando', cls: 'crit', ico: '●' }, en_observacion: { label: 'En observación', cls: 'warn', ico: '◷' },
  resuelto: { label: 'Resuelto', cls: 'ok', ico: '✔' }, programado: { label: 'Programado', cls: 'info', ico: '◷' },
  en_curso: { label: 'En curso', cls: 'warn', ico: '▲' }, completado: { label: 'Completado', cls: 'ok', ico: '✔' },
  activa: { label: 'Activa', cls: 'ok', ico: '✔' }, desactivada: { label: 'Desactivada', cls: 'muted', ico: '■' },
  pendiente_verificacion: { label: 'Sin verificar', cls: 'warn', ico: '◷' }, en_mora: { label: 'En mora', cls: 'serious', ico: '▲' },
  cancelada: { label: 'Cancelada', cls: 'muted', ico: '■' }, vencida: { label: 'Vencida', cls: 'muted', ico: '■' },
  suspendida: { label: 'Suspendida', cls: 'serious', ico: '■' }, aprobada: { label: 'Aprobada', cls: 'ok', ico: '✔' },
  rechazada: { label: 'Rechazada', cls: 'crit', ico: '✖' }, reembolsada: { label: 'Reembolsada', cls: 'info', ico: '↺' },
  reembolsada_parcial: { label: 'Reemb. parcial', cls: 'info', ico: '↺' },
  borrador: { label: 'Borrador', cls: 'neutral', ico: '✎' }, publicado: { label: 'Publicado', cls: 'ok', ico: '✔' },
  publicada: { label: 'Publicada', cls: 'ok', ico: '✔' }, reemplazada: { label: 'Reemplazada', cls: 'muted', ico: '■' },
  archivado: { label: 'Archivado', cls: 'muted', ico: '■' }, pendiente: { label: 'Pendiente', cls: 'warn', ico: '◷' },
  aprobado: { label: 'Aprobado', cls: 'ok', ico: '✔' }, rechazado: { label: 'Rechazado', cls: 'crit', ico: '✖' },
  suspendido: { label: 'Suspendido', cls: 'serious', ico: '■' }, invitado: { label: 'Invitado', cls: 'warn', ico: '◷' },
  activo: { label: 'Activo', cls: 'ok', ico: '✔' }, atendida: { label: 'Atendida', cls: 'ok', ico: '✔' },
  descartada: { label: 'Descartada', cls: 'muted', ico: '■' },
}
export function Chip({ estado }: { estado: string }) {
  const e = ESTADO_GEN[estado] ?? { label: estado.replace(/_/g, ' '), cls: 'neutral', ico: '●' }
  return <span className={`chip ${e.cls}`}>{e.ico} {e.label}</span>
}
