import { useEffect, useState, type FormEvent } from 'react'
import { api, type Page } from '../api'
import { useAuth } from '../auth'
import { Card, Cargando, Chip, clp, ErrorBox, fecha, fechaHora, num, Paginacion, Tabs } from '../components/ui'

interface Contenido {
  id_contenido: number; tipo: string; titulo: string; cuerpo: string; etiquetas: string[]; estado: string
  fecha_programada: string | null; fecha_publicacion: string | null; fecha_creacion: string
}
interface Producto {
  id_producto: number; nombre: string; categoria: string; proveedor: string; precio_referencial: number | null
  url_externa: string; url_imagen: string | null; estado: string; fecha_creacion: string
}
interface Cuidadora {
  id_perfil: number; nombre: string; email: string; zona: string; especialidades: string[]; idiomas: string[]
  certificaciones_verificadas: number; calificacion_promedio: number | null; estado_publicacion: string; motivo_estado: string | null
  revisor: string | null; fecha_envio: string; fecha_revision: string | null
}

const vacio = { tipo: 'noticia', titulo: '', cuerpo: '', etiquetas: '' }

// CU17 Gestionar contenido curado · CU18 Publicar/programar
function TabContenido({ escribe }: { escribe: boolean }) {
  const [data, setData] = useState<Page<Contenido> | null>(null)
  const [f, setF] = useState({ tipo: '', estado: '', page: 1 })
  const [form, setForm] = useState<null | (typeof vacio & { id?: number })>(null)
  const [prog, setProg] = useState<{ id: number; fecha: string } | null>(null)
  const [error, setError] = useState<unknown>(null)
  const cargar = () => api<Page<Contenido>>('/contenidos', { query: { ...f, page_size: 12 } }).then(setData).catch(setError)
  useEffect(() => { cargar() }, [f]) // eslint-disable-line react-hooks/exhaustive-deps

  const guardar = async (e: FormEvent) => {
    e.preventDefault(); if (!form) return; setError(null)
    const etiquetas = form.etiquetas.split(',').map(s => s.trim()).filter(Boolean)
    try {
      if (form.id) await api(`/contenidos/${form.id}`, { method: 'PATCH', body: { titulo: form.titulo, cuerpo: form.cuerpo, etiquetas } })
      else await api('/contenidos', { method: 'POST', body: { tipo: form.tipo, titulo: form.titulo, cuerpo: form.cuerpo, etiquetas } })
      setForm(null); cargar()
    } catch (err) { setError(err) }
  }
  const accion = async (path: string, method = 'POST', body?: unknown) => {
    setError(null)
    try { await api(path, { method, body }); setProg(null); cargar() } catch (err) { setError(err) }
  }

  return (
    <Card title="Contenido curado" sub="Chistes y noticias del feed de la app · los borradores no se ven en la app"
      actions={escribe && <button className="btn primary sm" onClick={() => setForm(form ? null : { ...vacio })}>{form ? 'Cancelar' : '+ Nuevo contenido'}</button>}>
      <ErrorBox error={error} />
      {form && (
        <form className="form inline-form" style={{ gridTemplateColumns: '1fr 2fr' }} onSubmit={guardar}>
          <label>Tipo<select value={form.tipo} disabled={!!form.id} onChange={e => setForm({ ...form, tipo: e.target.value })}>
            <option value="noticia">Noticia</option><option value="chiste">Chiste</option></select></label>
          <label>Título<input value={form.titulo} onChange={e => setForm({ ...form, titulo: e.target.value })} required minLength={3} /></label>
          <label className="full">Texto<textarea value={form.cuerpo} onChange={e => setForm({ ...form, cuerpo: e.target.value })} required minLength={10} /></label>
          <label>Etiquetas <span className="hint">separadas por coma</span><input value={form.etiquetas} onChange={e => setForm({ ...form, etiquetas: e.target.value })} /></label>
          <div className="actions"><button className="btn primary">{form.id ? 'Guardar cambios' : 'Guardar borrador'}</button></div>
        </form>
      )}
      <div className="filters">
        <select value={f.tipo} onChange={e => setF({ ...f, tipo: e.target.value, page: 1 })} aria-label="Tipo"><option value="">Tipo</option><option value="noticia">Noticias</option><option value="chiste">Chistes</option></select>
        <select value={f.estado} onChange={e => setF({ ...f, estado: e.target.value, page: 1 })} aria-label="Estado">
          <option value="">Estado</option>{['borrador', 'programado', 'publicado', 'archivado'].map(s => <option key={s} value={s}>{s}</option>)}</select>
      </div>
      {!data ? <Cargando /> : (
        <>
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Contenido</th><th>Tipo</th><th>Estado</th><th>Fecha</th><th></th></tr></thead>
            <tbody>{data.items.map(c => (
              <tr key={c.id_contenido}>
                <td><div className="strong">{c.titulo}</div><div className="sub">{c.cuerpo.slice(0, 90)}{c.cuerpo.length > 90 && '…'}</div>
                  {c.etiquetas.length > 0 && <div style={{ marginTop: 4 }}>{c.etiquetas.map(t => <span key={t} className="chip sm neutral">#{t}</span>)}</div>}</td>
                <td>{c.tipo === 'chiste' ? 'Chiste' : 'Noticia'}</td>
                <td><Chip estado={c.estado} /></td>
                <td className="nowrap">{c.estado === 'programado' ? fechaHora(c.fecha_programada) : c.estado === 'publicado' ? fechaHora(c.fecha_publicacion) : fecha(c.fecha_creacion)}</td>
                <td className="right">{escribe && (
                  <div className="state-actions" style={{ justifyContent: 'flex-end' }}>
                    {c.estado !== 'archivado' && <button className="btn ghost sm" onClick={() => setForm({ id: c.id_contenido, tipo: c.tipo, titulo: c.titulo, cuerpo: c.cuerpo, etiquetas: c.etiquetas.join(', ') })}>Editar</button>}
                    {['borrador', 'programado', 'archivado'].includes(c.estado) && <button className="btn primary sm" onClick={() => accion(`/contenidos/${c.id_contenido}/publicar`, 'POST', {})}>Publicar ahora</button>}
                    {c.estado === 'borrador' && <button className="btn ghost sm" onClick={() => setProg(prog?.id === c.id_contenido ? null : { id: c.id_contenido, fecha: '' })}>Programar</button>}
                    {c.estado === 'publicado' && <button className="btn ghost sm" onClick={() => accion(`/contenidos/${c.id_contenido}/archivar`)}>Retirar</button>}
                    {c.estado !== 'publicado' && <button className="btn ghost sm danger" onClick={() => confirm('¿Eliminar este contenido?') && accion(`/contenidos/${c.id_contenido}`, 'DELETE')}>Eliminar</button>}
                  </div>)}
                  {prog?.id === c.id_contenido && (
                    <form className="mod-form" style={{ justifyContent: 'flex-end' }} onSubmit={e => { e.preventDefault(); accion(`/contenidos/${c.id_contenido}/publicar`, 'POST', { fecha_programada: new Date(prog.fecha).toISOString() }) }}>
                      <input type="datetime-local" required value={prog.fecha} onChange={e => setProg({ ...prog, fecha: e.target.value })} aria-label="Fecha de publicación" style={{ flex: 'none' }} />
                      <button className="btn primary sm">Confirmar</button>
                    </form>)}
                </td>
              </tr>
            ))}</tbody>
          </table>{!data.items.length && <p className="empty">Sin contenido con esos filtros.</p>}</div>
          <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={p => setF({ ...f, page: p })} />
        </>
      )}
    </Card>
  )
}

const prodVacio = { nombre: '', categoria: '', proveedor: '', precio_referencial: '', url_externa: 'https://' }

// CU19 Gestionar catálogo de productos de apoyo
function TabProductos({ escribe }: { escribe: boolean }) {
  const [data, setData] = useState<Page<Producto> | null>(null)
  const [page, setPage] = useState(1)
  const [form, setForm] = useState<null | (typeof prodVacio & { id?: number })>(null)
  const [error, setError] = useState<unknown>(null)
  const cargar = () => api<Page<Producto>>('/productos', { query: { page, page_size: 12 } }).then(setData).catch(setError)
  useEffect(() => { cargar() }, [page]) // eslint-disable-line react-hooks/exhaustive-deps

  const guardar = async (e: FormEvent) => {
    e.preventDefault(); if (!form) return; setError(null)
    const { id, ...rest } = form
    const body = { ...rest, precio_referencial: rest.precio_referencial === '' ? null : Number(rest.precio_referencial) }
    try {
      await api(id ? `/productos/${id}` : '/productos', { method: id ? 'PATCH' : 'POST', body })
      setForm(null); cargar()
    } catch (err) { setError(err) }
  }
  const estado = async (p: Producto, e: string) => {
    setError(null)
    try { await api(`/productos/${p.id_producto}`, { method: 'PATCH', body: { estado: e } }); cargar() } catch (err) { setError(err) }
  }

  return (
    <Card title="Productos de apoyo" sub="Vitrina del marketplace · el enlace lleva a la tienda del proveedor (solo https)"
      actions={escribe && <button className="btn primary sm" onClick={() => setForm(form ? null : { ...prodVacio })}>{form ? 'Cancelar' : '+ Agregar producto'}</button>}>
      <ErrorBox error={error} />
      {form && (
        <form className="form inline-form" style={{ gridTemplateColumns: '1fr 1fr' }} onSubmit={guardar}>
          <label>Nombre<input value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })} required minLength={3} /></label>
          <label>Categoría<input value={form.categoria} onChange={e => setForm({ ...form, categoria: e.target.value })} required minLength={3} placeholder="movilidad, baño, monitoreo…" /></label>
          <label>Proveedor<input value={form.proveedor} onChange={e => setForm({ ...form, proveedor: e.target.value })} required minLength={2} /></label>
          <label>Precio referencial (CLP)<input type="number" min={0} value={form.precio_referencial} onChange={e => setForm({ ...form, precio_referencial: e.target.value })} /></label>
          <label className="full">Enlace a la tienda<input type="url" value={form.url_externa} onChange={e => setForm({ ...form, url_externa: e.target.value })} required pattern="https://.*" /></label>
          <div className="actions full"><button className="btn primary">{form.id ? 'Guardar cambios' : 'Agregar como borrador'}</button></div>
        </form>
      )}
      {!data ? <Cargando /> : (
        <>
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Producto</th><th>Categoría</th><th className="right">Precio ref.</th><th>Estado</th><th></th></tr></thead>
            <tbody>{data.items.map(p => (
              <tr key={p.id_producto}>
                <td><div className="strong">{p.nombre}</div><div className="sub">{p.proveedor} · <a href={p.url_externa} target="_blank" rel="noreferrer">ver en tienda ↗</a></div></td>
                <td>{p.categoria}</td><td className="right">{clp(p.precio_referencial)}</td><td><Chip estado={p.estado} /></td>
                <td className="right">{escribe && <div className="state-actions" style={{ justifyContent: 'flex-end' }}>
                  <button className="btn ghost sm" onClick={() => setForm({ id: p.id_producto, nombre: p.nombre, categoria: p.categoria, proveedor: p.proveedor, precio_referencial: p.precio_referencial?.toString() ?? '', url_externa: p.url_externa })}>Editar</button>
                  {p.estado !== 'publicado' && <button className="btn primary sm" onClick={() => estado(p, 'publicado')}>Publicar</button>}
                  {p.estado === 'publicado' && <button className="btn ghost sm" onClick={() => estado(p, 'archivado')}>Archivar</button>}
                </div>}</td>
              </tr>
            ))}</tbody>
          </table></div>
          <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
        </>
      )}
    </Card>
  )
}

// CU20 Revisar perfiles de cuidadoras
function TabCuidadoras({ escribe }: { escribe: boolean }) {
  const [data, setData] = useState<Page<Cuidadora> | null>(null)
  const [f, setF] = useState({ estado: 'pendiente', page: 1 })
  const [motivo, setMotivo] = useState<Record<number, string>>({})
  const [error, setError] = useState<unknown>(null)
  const cargar = () => api<Page<Cuidadora>>('/cuidadoras', { query: { ...f, page_size: 12 } }).then(setData).catch(setError)
  useEffect(() => { cargar() }, [f]) // eslint-disable-line react-hooks/exhaustive-deps

  const decidir = async (c: Cuidadora, decision: string) => {
    setError(null)
    try { await api(`/cuidadoras/${c.id_perfil}/revision`, { method: 'POST', body: { decision, motivo: motivo[c.id_perfil] || null } }); cargar() } catch (err) { setError(err) }
  }

  return (
    <Card title="Perfiles de cuidadoras" sub="Solo se aprueban perfiles con al menos una certificación verificada · suspender exige motivo">
      <div className="filters"><div className="seg">
        {[['pendiente', 'Pendientes'], ['aprobado', 'Aprobados'], ['suspendido', 'Suspendidos'], ['', 'Todos']].map(([k, l]) =>
          <button key={k} className={f.estado === k ? 'on' : ''} onClick={() => setF({ estado: k, page: 1 })}>{l}</button>)}
      </div></div>
      <ErrorBox error={error} />
      {!data ? <Cargando /> : (
        <>
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Cuidadora</th><th>Especialidades</th><th className="right">Cert.</th><th className="right">Calif.</th><th>Estado</th><th></th></tr></thead>
            <tbody>{data.items.map(c => (
              <tr key={c.id_perfil}>
                <td><div className="strong">{c.nombre}</div><div className="sub">{c.zona} · {c.idiomas.join(', ')} · enviado {fecha(c.fecha_envio)}</div></td>
                <td>{c.especialidades.map(s => <span key={s} className="chip sm neutral">{s}</span>)}</td>
                <td className="right">{c.certificaciones_verificadas ? c.certificaciones_verificadas : <span className="chip warn">0</span>}</td>
                <td className="right">{c.calificacion_promedio != null ? `★ ${num(c.calificacion_promedio, 1)}` : '—'}</td>
                <td><Chip estado={c.estado_publicacion} />{c.motivo_estado && <div className="sub">{c.motivo_estado}</div>}{c.revisor && <div className="sub">por {c.revisor}</div>}</td>
                <td className="right">{escribe && (
                  <div className="mod-form" style={{ justifyContent: 'flex-end', marginTop: 0 }}>
                    {c.estado_publicacion !== 'suspendido' && <input placeholder="Motivo (para suspender)" value={motivo[c.id_perfil] ?? ''} onChange={e => setMotivo({ ...motivo, [c.id_perfil]: e.target.value })} aria-label="Motivo" />}
                    {c.estado_publicacion !== 'aprobado' && <button className="btn primary sm" disabled={!c.certificaciones_verificadas} title={!c.certificaciones_verificadas ? 'Requiere una certificación verificada' : ''} onClick={() => decidir(c, 'aprobado')}>Aprobar</button>}
                    {c.estado_publicacion !== 'suspendido' && <button className="btn ghost sm danger" disabled={(motivo[c.id_perfil] ?? '').trim().length < 10} onClick={() => decidir(c, 'suspendido')}>Suspender</button>}
                  </div>)}</td>
              </tr>
            ))}</tbody>
          </table>{!data.items.length && <p className="empty">No hay perfiles en este estado.</p>}</div>
          <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={p => setF({ ...f, page: p })} />
        </>
      )}
    </Card>
  )
}

export default function Contenidos() {
  const { puede } = useAuth()
  const tabs: ['contenido' | 'productos' | 'cuidadoras', string][] = []
  if (puede('contenido')) tabs.push(['contenido', 'Contenido curado'])
  if (puede('marketplace')) tabs.push(['productos', 'Productos de apoyo'], ['cuidadoras', 'Perfiles de cuidadoras'])
  const [tab, setTab] = useState(tabs[0]?.[0] ?? 'contenido')
  return (
    <>
      <Tabs value={tab} onChange={setTab} items={tabs} />
      {tab === 'contenido' && <TabContenido escribe={puede('contenido', 'escritura')} />}
      {tab === 'productos' && <TabProductos escribe={puede('marketplace', 'escritura')} />}
      {tab === 'cuidadoras' && <TabCuidadoras escribe={puede('marketplace', 'escritura')} />}
    </>
  )
}
