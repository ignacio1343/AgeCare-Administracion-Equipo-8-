// Cliente HTTP de la consola: agrega el token, renueva la sesión con el refresh token
// cuando el access token expira (401) y normaliza los errores de la API.

// En local y con Docker la API está en el mismo origen (/api). En Render el frontend es un sitio estático
// separado: VITE_API_URL apunta a la API (p. ej. https://agecare-admin-api.onrender.com).
const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? '').replace(/\/$/, '')
export const API = `${BASE}/api/v1`
const REFRESH_KEY = 'agecare.refresh'

let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null
let onSessionLost: () => void = () => {}

export class ApiError extends Error {
  status: number
  code: string
  details: unknown
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

export const session = {
  set(access: string, refresh: string) {
    accessToken = access
    try { localStorage.setItem(REFRESH_KEY, refresh) } catch { /* modo privado */ }
  },
  clear() {
    accessToken = null
    try { localStorage.removeItem(REFRESH_KEY) } catch { /* noop */ }
  },
  refreshToken(): string | null {
    try { return localStorage.getItem(REFRESH_KEY) } catch { return null }
  },
  hasAccess: () => accessToken !== null,
  onLost(fn: () => void) { onSessionLost = fn },
}

async function parse(res: Response) {
  if (res.status === 204) return null
  const text = await res.text()
  const body = text ? JSON.parse(text) : null
  if (!res.ok) {
    const e = body?.error
    throw new ApiError(res.status, e?.code ?? 'HTTP_ERROR', e?.message ?? `Error ${res.status}`, e?.details)
  }
  return body
}

export async function tryRefresh(): Promise<boolean> {
  const rt = session.refreshToken()
  if (!rt) return false
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch(`${API}/auth/refresh`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: rt }),
        })
        if (!res.ok) { session.clear(); return false }
        const data = await res.json()
        session.set(data.access_token, data.refresh_token)
        return true
      } catch { return false } finally { setTimeout(() => { refreshing = null }, 0) }
    })()
  }
  return refreshing
}

type Opts = { method?: string; body?: unknown; query?: Record<string, string | number | boolean | null | undefined> }

export async function api<T = any>(path: string, opts: Opts = {}, retry = true): Promise<T> {
  let url = `${API}${path}`
  if (opts.query) {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(opts.query)) if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
    const s = qs.toString()
    if (s) url += `?${s}`
  }
  const headers: Record<string, string> = {}
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  const res = await fetch(url, { method: opts.method ?? 'GET', headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined })
  if (res.status === 401 && retry && !path.startsWith('/auth/login')) {
    if (await tryRefresh()) return api<T>(path, opts, false)
    session.clear()
    onSessionLost()
  }
  return parse(res)
}

// ---------------------------------------------------------------- tipos
export type Permisos = Record<string, 'lectura' | 'escritura'>
export interface Perfil {
  id_staff: number; nombre_completo: string; email: string; codigo_rol: string; rol_nombre: string; estado: string
  mfa_requerido: boolean; mfa_habilitado: boolean; ultimo_acceso: string | null; fecha_creacion: string
  permisos: Permisos; configurar_mfa: boolean
}
export interface Page<T> { items: T[]; page: number; page_size: number; total: number }
export interface Ref { id: number | string; nombre: string }
export interface Ticket {
  id_ticket: number; numero: number; asunto: string; categoria: Ref; prioridad: string; estado: string; canal: string
  solicitante: { id_usuario: number | null; nombre: string; email: string | null; perfiles: string[] }
  paciente: Ref | null; asignado: Ref | null
  fecha_creacion: string; fecha_actualizacion: string; fecha_primera_respuesta: string | null
  fecha_resolucion: string | null; fecha_cierre: string | null
}
export interface TicketDetalle extends Ticket {
  descripcion: string
  contexto: { estado_cuenta: string | null; fecha_registro: string | null; ultimo_acceso: string | null; pacientes: Ref[]; tickets_previos: number }
  respuestas_total: number
  encuesta: { fecha_envio: string; fecha_respuesta: string | null; puntaje: number | null; comentario: string | null } | null
  transiciones_permitidas: string[]
}
export interface Respuesta { id_respuesta: number; tipo_autor: string; autor_nombre: string; cuerpo: string; es_interna: boolean; fecha: string }
export interface Indicadores {
  abiertos: number; en_curso: number; esperando_usuario: number; resueltos_30d: number
  primera_respuesta_horas_prom: number | null; resolucion_horas_prom: number | null
  csat_promedio: number | null; csat_respuestas: number; sin_asignar: number
  por_categoria_30d: { codigo: string; nombre: string; total: number }[]
}
export interface Staff {
  id_staff: number; nombre_completo: string; email: string; codigo_rol: string; estado: string
  mfa_requerido: boolean; mfa_habilitado: boolean; ultimo_acceso: string | null; fecha_creacion: string
}
export interface Rol { codigo_rol: string; nombre: string; descripcion: string | null; permisos: { modulo: string; nivel_acceso: string }[] }
export interface Auditoria {
  id_registro: number; fecha_hora: string; accion: string; tipo_entidad: string; id_entidad: string | null
  valor_anterior: string | null; valor_nuevo: string | null; ip: string | null; id_staff_actor: number | null; actor_nombre: string | null
}
