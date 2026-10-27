import { useEffect, useState, type FormEvent } from 'react'
import { api, type Page } from '../api'
import { useAuth } from '../auth'
import { Card, Cargando, Chip, ErrorBox, fechaHora, hace, num, Paginacion } from '../components/ui'

interface Mensaje {
  id_mensaje: number; id_alerta: number | null; paciente: string; destinatario: string; telefono: string | null
  tipo_mensaje: string; contenido: string; estado: string; motivo: string | null; intentos: number
  proximo_intento: string | null; fecha_creacion: string; fecha_envio: string | null; fecha_entrega: string | null; fecha_lectura: string | null
}
type Conteo = Record<'pendiente' | 'enviado' | 'entregado' | 'leido' | 'fallido' | 'omitido', number>
interface Resumen {
  modo: 'simulado' | 'meta'; activo: boolean; plantilla: string; minutos_entre_avisos: number; planes_con_whatsapp: string[]
  familiares_habilitados: number; familiares_total: number; ultimas_24h: Conteo; ultimos_7d: Conteo; entrega_seg_prom: number | null
}
interface PacienteOp { id_paciente: number; nombre: string; plan: string | null; con_whatsapp: boolean; familiares_habilitados: number }
interface SignoOp { signo_vital: string; nombre: string; unidad: string; verde_min: number; verde_max: number; amarillo_min: number; amarillo_max: number }
interface Resultado { nivel: string | null; id_alerta: number | null; severidad: string | null; avisos: Mensaje[]; mensaje: string }

const FILTROS: [string, string][] = [['', 'Todos'], ['entregado', 'Entregados'], ['leido', 'Leídos'], ['fallido', 'Fallidos'], ['omitido', 'Omitidos']]
const NIVEL: Record<string, string> = { verde: 'ok', amarillo: 'warn', rojo: 'crit' }
const enviados = (c: Conteo) => c.enviado + c.entregado + c.leido

// CU41 Registrar evento de salud · CU42 Avisar al familiar por WhatsApp · CU43 Consultar avisos enviados
export default function Whatsapp() {
  const { puede } = useAuth()
  const escribe = puede('operacion', 'escritura')
  const [res, setRes] = useState<Resumen | null>(null)
  const [data, setData] = useState<Page<Mensaje> | null>(null)
  const [f, setF] = useState({ estado: '', q: '', dias: 7, page: 1 })
  const [busca, setBusca] = useState('')
  const [abierto, setAbierto] = useState<number | null>(null)
  const [error, setError] = useState<unknown>(null)

  const cargar = () => {
    api<Resumen>('/whatsapp/resumen').then(setRes).catch(setError)
    api<Page<Mensaje>>('/whatsapp/mensajes', { query: { ...f, page_size: 15 } }).then(setData).catch(setError)
  }
  useEffect(() => { cargar() }, [f]) // eslint-disable-line react-hooks/exhaustive-deps

  const reintentar = async (m: Mensaje) => {
    setError(null)
    try { await api(`/whatsapp/mensajes/${m.id_mensaje}/reintentar`, { method: 'POST' }); setTimeout(cargar, 800) } catch (e) { setError(e) }
  }

  const r = res?.ultimas_24h
  return (
    <>
      {res && r && (
        <div className="kpis k6">
          <div className="kpi"><div className="kpi-label">Enviados · 24 h</div><div className="kpi-value">{num(enviados(r))}</div>
            <div className="kpi-delta">{num(enviados(res.ultimos_7d))} en 7 días</div></div>
          <div className="kpi"><div className="kpi-label">Entregados</div><div className="kpi-value">{num(r.entregado + r.leido)}</div>
            <div className="kpi-delta">{enviados(r) ? `${Math.round((r.entregado + r.leido) * 100 / enviados(r))} % de los enviados` : '—'}</div></div>
          <div className="kpi"><div className="kpi-label">Leídos</div><div className="kpi-value">{num(r.leido)}</div></div>
          <div className="kpi"><div className="kpi-label">Fallidos</div><div className="kpi-value">{num(r.fallido)}</div>
            <div className={`kpi-delta ${r.fallido ? 'down' : 'up'}`}>{r.fallido ? '▲ revisar teléfono' : 'sin fallas'}</div></div>
          <div className="kpi"><div className="kpi-label">Omitidos</div><div className="kpi-value">{num(r.omitido)}</div>
            <div className="kpi-delta">sin plan, sin consentimiento o agrupados</div></div>
          <div className="kpi"><div className="kpi-label">Alerta → entregado</div>
            <div className="kpi-value">{res.entrega_seg_prom == null ? '—' : `${num(res.entrega_seg_prom, 0)} s`}</div>
            <div className="kpi-delta">promedio 7 días</div></div>
        </div>
      )}

      <div className="grid g2">
        <Card title="Cómo funciona" sub="Aviso al familiar cuando el paciente tiene un evento de salud de riesgo">
          {!res ? <Cargando /> : (
            <>
              <dl className="kv">
                <dt>Estado</dt><dd>{res.activo ? <span className="chip ok">✔ Activo</span> : <span className="chip muted">■ Apagado</span>}
                  <span className="sub"> · parámetro «whatsapp_activo» en Configuración</span></dd>
                <dt>Proveedor</dt><dd>{res.modo === 'meta'
                  ? <span className="chip info">WhatsApp Business Cloud API (Meta)</span>
                  : <span className="chip neutral">Simulado · no se envían mensajes reales</span>}</dd>
                <dt>Plantilla</dt><dd className="mono">{res.plantilla}</dd>
                <dt>Planes</dt><dd>{res.planes_con_whatsapp.join(', ') || 'ninguno'}</dd>
                <dt>Familiares</dt><dd>{res.familiares_habilitados} de {res.familiares_total} autorizaron avisos</dd>
                <dt>Agrupación</dt><dd>máximo un aviso cada {res.minutos_entre_avisos} min por paciente y familiar</dd>
              </dl>
              <ul className="small muted" style={{ margin: '12px 0 0', paddingLeft: 18 }}>
                <li>Se avisa ante <b>signos vitales en rojo</b> (fuera del rango amarillo), <b>caídas</b> y <b>SOS</b>.</li>
                <li>Solo a familiares del círculo de cuidado que dieron su consentimiento (ficha en «Usuarios de la app»).</li>
                <li>Si un envío falla se reintenta a 1, 5 y 15 minutos; luego queda «fallido» y se puede reintentar aquí.</li>
              </ul>
              {escribe && <Diagnostico />}
            </>
          )}
        </Card>
        {escribe ? <SimularEvento onListo={() => setTimeout(cargar, 900)} /> : (
          <Card title="Simular evento de salud"><p className="muted">Tu rol puede consultar los avisos, pero no registrar eventos.</p></Card>
        )}
      </div>

      <Card title="Bitácora de avisos" sub="Cada evento crítico deja un registro por familiar, también cuando no se envía (con el motivo)">
        <div className="filters">
          <div className="seg">{FILTROS.map(([k, l]) =>
            <button key={k} className={f.estado === k ? 'on' : ''} onClick={() => setF({ ...f, estado: k, page: 1 })}>{l}</button>)}</div>
          <form className="search" onSubmit={e => { e.preventDefault(); setF({ ...f, q: busca.trim(), page: 1 }) }}>
            <input placeholder="Buscar paciente o familiar" value={busca} onChange={e => setBusca(e.target.value)} aria-label="Buscar" />
          </form>
          <select value={f.dias} onChange={e => setF({ ...f, dias: Number(e.target.value), page: 1 })} aria-label="Periodo">
            <option value={1}>Últimas 24 h</option><option value={7}>Últimos 7 días</option><option value={30}>Últimos 30 días</option></select>
        </div>
        <ErrorBox error={error} />
        {!data ? <Cargando /> : (
          <>
            <div className="table-wrap"><table className="data clickable">
              <thead><tr><th>Fecha</th><th>Paciente</th><th>Familiar</th><th>Mensaje</th><th>Estado</th><th className="right">Intentos</th><th></th></tr></thead>
              <tbody>{data.items.map(m => (
                <tr key={m.id_mensaje} onClick={() => setAbierto(abierto === m.id_mensaje ? null : m.id_mensaje)} tabIndex={0}
                  onKeyDown={e => e.key === 'Enter' && setAbierto(abierto === m.id_mensaje ? null : m.id_mensaje)}>
                  <td className="nowrap">{fechaHora(m.fecha_creacion)}<div className="sub">{hace(m.fecha_creacion)}</div></td>
                  <td className="strong">{m.paciente}</td>
                  <td>{m.destinatario}<div className="sub mono">{m.telefono ?? 'sin teléfono'}</div></td>
                  <td style={{ maxWidth: 380 }}>{abierto === m.id_mensaje ? m.contenido : <span className="clip">{m.contenido}</span>}</td>
                  <td><Chip estado={m.estado} />
                    {m.motivo && <div className="sub">{m.motivo}</div>}
                    {m.estado === 'leido' && <div className="sub">leído {fechaHora(m.fecha_lectura)}</div>}
                    {m.estado === 'pendiente' && m.proximo_intento && <div className="sub">próximo intento {hace(m.proximo_intento)}</div>}</td>
                  <td className="right">{m.intentos}</td>
                  <td className="right">{escribe && m.estado === 'fallido' &&
                    <button className="btn ghost sm" onClick={e => { e.stopPropagation(); reintentar(m) }}>Reintentar</button>}</td>
                </tr>
              ))}</tbody>
            </table>{!data.items.length && <p className="empty">No hay avisos en este periodo.</p>}</div>
            <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={p => setF({ ...f, page: p })} />
          </>
        )}
      </Card>
    </>
  )
}

function SimularEvento({ onListo }: { onListo: () => void }) {
  const [op, setOp] = useState<{ pacientes: PacienteOp[]; signos: SignoOp[] } | null>(null)
  const [form, setForm] = useState({ id_paciente: '', tipo: 'vital', signo_vital: 'saturacion_o2', valor: '86' })
  const [res, setRes] = useState<Resultado | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    api<{ pacientes: PacienteOp[]; signos: SignoOp[] }>('/whatsapp/opciones').then(o => {
      setOp(o)
      const p = o.pacientes.find(x => x.con_whatsapp && x.familiares_habilitados) ?? o.pacientes[0]
      if (p) setForm(f => ({ ...f, id_paciente: String(p.id_paciente) }))
    }).catch(setError)
  }, [])

  const signo = op?.signos.find(s => s.signo_vital === form.signo_vital)
  const paciente = op?.pacientes.find(p => String(p.id_paciente) === form.id_paciente)

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setError(null); setRes(null); setEnviando(true)
    try {
      const body = form.tipo === 'vital'
        ? { id_paciente: Number(form.id_paciente), tipo: 'vital', signo_vital: form.signo_vital, valor: Number(form.valor.replace(',', '.')) }
        : { id_paciente: Number(form.id_paciente), tipo: form.tipo }
      setRes(await api<Resultado>('/operacion/eventos-salud', { method: 'POST', body }))
      onListo()
    } catch (err) { setError(err) } finally { setEnviando(false) }
  }

  return (
    <Card title="Simular evento de salud" sub="En producción lo informa la Plataforma AgeCare (wearable, app o botón SOS)">
      <ErrorBox error={error} />
      {!op ? <Cargando /> : (
        <form className="form" onSubmit={enviar}>
          <label className="full">Paciente
            <select value={form.id_paciente} onChange={e => setForm({ ...form, id_paciente: e.target.value })} required>
              {op.pacientes.map(p => <option key={p.id_paciente} value={p.id_paciente}>
                {p.nombre} · {p.plan ?? 'sin plan'}{p.con_whatsapp ? ` · WhatsApp (${p.familiares_habilitados} familiar/es)` : ' · sin WhatsApp'}</option>)}
            </select>
            {paciente && !paciente.con_whatsapp && <span className="hint">Su plan no incluye avisos: el aviso quedará «omitido».</span>}
          </label>
          <div className="seg full">{[['vital', 'Signo vital'], ['caida', 'Caída'], ['sos', 'Botón SOS']].map(([k, l]) =>
            <button type="button" key={k} className={form.tipo === k ? 'on' : ''} onClick={() => setForm({ ...form, tipo: k })}>{l}</button>)}</div>
          {form.tipo === 'vital' && (
            <>
              <label>Signo vital
                <select value={form.signo_vital} onChange={e => setForm({ ...form, signo_vital: e.target.value })}>
                  {op.signos.map(s => <option key={s.signo_vital} value={s.signo_vital}>{s.nombre}</option>)}</select></label>
              <label>Valor medido {signo && <span className="hint">({signo.unidad})</span>}
                <input inputMode="decimal" value={form.valor} onChange={e => setForm({ ...form, valor: e.target.value })} required /></label>
              {signo && <p className="hint full">Verde {num(signo.verde_min, 1)}–{num(signo.verde_max, 1)} · amarillo {num(signo.amarillo_min, 1)}–{num(signo.amarillo_max, 1)} {signo.unidad}. Fuera del amarillo es rojo y se avisa por WhatsApp.</p>}
            </>
          )}
          <div className="actions full"><button className="btn primary" disabled={enviando || !form.id_paciente}>{enviando ? 'Registrando…' : 'Registrar evento'}</button></div>
        </form>
      )}
      {res && (
        <div className={`alert ${res.avisos.some(a => a.estado === 'pendiente') ? 'ok' : 'info'}`} role="status" style={{ marginTop: 12 }}>
          {res.nivel && <span className={`chip ${NIVEL[res.nivel]}`} style={{ marginRight: 8 }}>Nivel {res.nivel}</span>}{res.mensaje}
          {res.avisos.length > 0 && <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>{res.avisos.map(a =>
            <li key={a.id_mensaje}>{a.destinatario} ({a.telefono ?? 'sin teléfono'}): {a.estado === 'pendiente' ? 'enviando…' : <>omitido — {a.motivo}</>}</li>)}</ul>}
        </div>
      )}
    </Card>
  )
}

interface Diag {
  modo: string; api_version: string; plantilla: string; idioma: string; token: boolean; phone_number_id: boolean
  app_secret: boolean; verify_token: boolean; waba_id: boolean
  numero: { telefono: string | null; nombre: string | null; calidad: string | null } | null
  plantilla_estado: string | null; errores: string[]
}

// Comprueba con Meta el número emisor, el token y la plantilla, sin enviar mensajes
function Diagnostico() {
  const [d, setD] = useState<Diag | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [cargando, setCargando] = useState(false)
  const probar = async () => {
    setError(null); setCargando(true)
    try { setD(await api<Diag>('/whatsapp/diagnostico')) } catch (e) { setError(e) } finally { setCargando(false) }
  }
  const si = (b: boolean) => b ? <span className="chip ok">✔</span> : <span className="chip crit">✖ falta</span>
  return (
    <div className="wa-box">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <b>Conexión con Meta</b>
        <button className="btn ghost sm" onClick={probar} disabled={cargando}>{cargando ? 'Probando…' : 'Probar conexión'}</button>
      </div>
      <ErrorBox error={error} />
      {d && (
        <>
          <dl className="kv" style={{ marginTop: 8 }}>
            <dt>Modo</dt><dd className="mono">{d.modo}</dd>
            {d.modo === 'meta' && <>
              <dt>Número emisor</dt><dd>{d.numero ? <>{d.numero.telefono} · {d.numero.nombre}{d.numero.calidad && <span className="sub"> · calidad {d.numero.calidad}</span>}</> : '—'}</dd>
              <dt>Plantilla</dt><dd><span className="mono">{d.plantilla}</span> ({d.idioma}) · {d.plantilla_estado ?? 'sin revisar (falta WHATSAPP_WABA_ID)'}</dd>
              <dt>Variables</dt><dd>token {si(d.token)} · número {si(d.phone_number_id)} · app secret {si(d.app_secret)} · verify token {si(d.verify_token)}</dd>
            </>}
          </dl>
          {d.errores.length > 0
            ? <div className="alert crit" style={{ marginTop: 8 }}>{d.errores.map(e => <div key={e}>{e}</div>)}</div>
            : <div className="alert ok" style={{ marginTop: 8 }}>Conexión correcta. Envía un mensaje de prueba desde la ficha de un familiar.</div>}
        </>
      )}
    </div>
  )
}
