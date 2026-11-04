// Cliente HTTP del portal web (representante, residente y cuidador).
// Misma estrategia que la consola pero con su propia sesión: access token de tipo «app» en memoria y refresh token
// en la cookie HttpOnly `aca_portal` (ruta /api/v1/portal/auth). Así se puede tener abierta la consola y el portal.
import { API, ApiError } from '../api'

const CRED: RequestCredentials = API.startsWith('http') ? 'include' : 'same-origin'
const HINT_KEY = 'agecare.portal'

let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null
let onLost: () => void = () => {}

export const portalSession = {
  set(access: string) {
    accessToken = access
    try { localStorage.setItem(HINT_KEY, '1') } catch { /* modo privado */ }
  },
  clear() {
    accessToken = null
    try { localStorage.removeItem(HINT_KEY) } catch { /* noop */ }
  },
  puedeRecuperar(): boolean {
    try { return localStorage.getItem(HINT_KEY) === '1' } catch { return true }
  },
  onLost(fn: () => void) { onLost = fn },
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

export async function portalRefresh(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch(`${API}/portal/auth/refresh`, { method: 'POST', credentials: CRED, headers: { 'X-ACA-Refresh': '1' } })
        if (!res.ok) { portalSession.clear(); return false }
        portalSession.set((await res.json()).access_token)
        return true
      } catch { return false } finally { setTimeout(() => { refreshing = null }, 0) }
    })()
  }
  return refreshing
}

type Opts = { method?: string; body?: unknown; query?: Record<string, string | number | undefined | null>; headers?: Record<string, string> }

export async function papi<T = any>(path: string, opts: Opts = {}, retry = true): Promise<T> {
  let url = `${API}/portal${path}`
  if (opts.query) {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(opts.query)) if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
    if (qs.toString()) url += `?${qs}`
  }
  const headers: Record<string, string> = { ...opts.headers }
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  const res = await fetch(url, { method: opts.method ?? 'GET', credentials: CRED, headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined })
  if (res.status === 401 && retry && !path.startsWith('/auth/login')) {
    if (await portalRefresh()) return papi<T>(path, opts, false)
    portalSession.clear()
    onLost()
  }
  return parse(res)
}

// Mensaje legible para el usuario a partir de un error de la API (incluye el primer campo con problemas)
export function textoError(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.details as { field?: string; message?: string }[] | undefined
    if (e.code === 'VALIDATION_ERROR' && Array.isArray(d) && d.length) {
      return d.map(x => (x.message ?? '').replace(/^Value error, /, '')).filter(Boolean).join(' · ') || e.message
    }
    return e.message
  }
  return 'No pudimos conectarnos. Revisa tu conexión e intenta de nuevo.'
}

export function errorDeCampo(e: unknown, campo: string): string | undefined {
  if (!(e instanceof ApiError) || !Array.isArray(e.details)) return undefined
  const x = (e.details as { field?: string; message?: string }[]).find(d => d.field === campo)
  return x?.message?.replace(/^Value error, /, '')
}

// ---------------------------------------------------------------- tipos
export type Vista = 'representante' | 'residente' | 'cuidador'
export interface Me {
  id_usuario: number; nombre: string; nombres: string | null; primer_apellido: string | null; segundo_apellido: string | null
  email: string; rut: string | null; telefono: string | null; vistas: Vista[]; debe_cambiar_password: boolean
  whatsapp_habilitado: boolean; notificaciones_sin_leer: number
}
export interface PlanPortal {
  codigo_plan: string; nombre: string; precio: number; funcionalidades: string[]
  incluye_estado_tiempo_real: boolean; incluye_avisos_riesgo: boolean
}
export interface RegistroVital { id_registro: number; estado: 'normal' | 'alerta' | 'riesgoso'; etiqueta: string; observacion: string; cuidador: string; fecha: string }
export interface Residente { id_paciente: number; nombre: string; rut: string | null; edad: number | null; email: string | null }
export interface ItemResidente {
  id_suscripcion: number | null; plan: PlanPortal | null; estado_suscripcion: string | null; fin_periodo: string | null
  puede_gestionar: boolean; residente: Residente | null; puede_ver_estado: boolean; recibe_avisos: boolean
  ultimo_estado: RegistroVital | null
}
export interface Notificacion { id_notificacion: number; tipo: string; titulo: string; cuerpo: string; id_paciente: number | null; fecha_creacion: string; leida: boolean }
export interface Orden {
  orden_compra: string; estado: string; tipo: string; plan: string; monto: number; proveedor: string
  fecha_creacion: string; fecha_confirmacion: string | null; codigo_autorizacion: string | null; tarjeta: string | null
  tipo_pago: string | null; detalle: string | null; id_suscripcion: number | null; requiere_residente: boolean
}
export interface ContenidoPortal { id_contenido: number; tipo: 'chiste' | 'noticia' | 'evento'; titulo: string; cuerpo: string; fecha_publicacion: string | null; fecha_evento: string | null; lugar: string | null }
