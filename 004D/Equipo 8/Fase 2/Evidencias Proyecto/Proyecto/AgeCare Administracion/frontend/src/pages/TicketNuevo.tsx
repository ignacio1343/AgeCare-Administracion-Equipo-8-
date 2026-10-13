import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError, type Ref, type Ticket } from '../api'
import { Card, PRIORIDADES } from '../components/ui'

// CU36 · Registrar ticket (atención telefónica, correo o consola)
export default function TicketNuevo() {
  const nav = useNavigate()
  const [cats, setCats] = useState<Ref[]>([])
  const [f, setF] = useState({ asunto: '', descripcion: '', email_usuario: '', codigo_categoria: '', prioridad: 'media', canal: 'telefono', nombre_solicitante: '' })
  const [sinCuenta, setSinCuenta] = useState(false)
  const [error, setError] = useState('')
  const [campos, setCampos] = useState<Record<string, string>>({})
  const [enviando, setEnviando] = useState(false)

  useEffect(() => { api<Ref[]>('/soporte/categorias').then(setCats) }, [])
  const upd = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setError(''); setCampos({}); setEnviando(true)
    try {
      const t = await api<Ticket>('/soporte/tickets', {
        method: 'POST', body: { ...f, confirmar_sin_enlace: sinCuenta, nombre_solicitante: f.nombre_solicitante || null },
      })
      nav(`/soporte/${t.id_ticket}`)
    } catch (err) {
      if (err instanceof ApiError && err.code === 'USER_NOT_FOUND') setSinCuenta(true)
      if (err instanceof ApiError && Array.isArray(err.details))
        setCampos(Object.fromEntries((err.details as { field: string; message: string }[]).map(d => [d.field, d.message])))
      setError(err instanceof Error ? err.message : 'Error')
    } finally { setEnviando(false) }
  }

  return (
    <Card title="Registrar ticket" sub="CU36 · Para solicitudes recibidas por teléfono, correo o directamente en la consola">
      <form className="form" onSubmit={enviar}>
        <label className="full">Asunto<input value={f.asunto} onChange={upd('asunto')} maxLength={160} required minLength={5} />
          {campos.asunto && <span className="field-err">{campos.asunto}</span>}</label>
        <label>Correo del usuario<input type="email" value={f.email_usuario} onChange={e => { upd('email_usuario')(e); setSinCuenta(false) }} required />
          <span className="hint">Si tiene cuenta en la app, el ticket se enlaza automáticamente.</span></label>
        <label>Categoría
          <select value={f.codigo_categoria} onChange={upd('codigo_categoria')} required>
            <option value="">Elegir…</option>{cats.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select></label>
        {sinCuenta && (
          <label className="full warn-box">El correo no tiene cuenta en la app. Para crear el ticket sin enlazar, indica el nombre del solicitante:
            <input value={f.nombre_solicitante} onChange={upd('nombre_solicitante')} placeholder="Nombre y apellido" required /></label>
        )}
        <label>Prioridad
          <select value={f.prioridad} onChange={upd('prioridad')}>{Object.entries(PRIORIDADES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
        <label>Canal
          <select value={f.canal} onChange={upd('canal')}><option value="telefono">Teléfono</option><option value="correo">Correo</option><option value="consola">Consola</option></select></label>
        <label className="full">Descripción<textarea rows={6} value={f.descripcion} onChange={upd('descripcion')} maxLength={8000} required /></label>
        {error && <div className="alert crit full">{error}</div>}
        <div className="full actions">
          <Link to="/soporte" className="btn ghost">Cancelar</Link>
          <button className="btn primary" disabled={enviando}>{sinCuenta ? 'Crear sin enlazar' : 'Registrar ticket'}</button>
        </div>
      </form>
    </Card>
  )
}
