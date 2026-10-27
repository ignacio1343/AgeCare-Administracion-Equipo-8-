import { Fragment, useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'
import { Card, Cargando, Chip, ErrorBox, fecha, fechaHora, Tabs } from '../components/ui'

interface Parametro { clave: string; descripcion: string; categoria: string; tipo_valor: string; valor: string; version: number; nota_cambio: string | null; fecha_actualizacion: string | null }
interface Umbral { signo_vital: string; nivel_semaforo: string; codigo_tipo: string; tipo_alerta: string; valor_minimo: number; valor_maximo: number; unidad: string; fecha_actualizacion: string | null }
interface Version { id_version: number; tipo_documento: string; version: string; contenido: string; registro_cambios: string; fecha_vigencia: string
  requiere_reaceptacion: boolean; estado: string; autor: string; fecha_publicacion: string | null }

const SIGNOS: Record<string, string> = { frecuencia_cardiaca: 'Frecuencia cardíaca', saturacion_oxigeno: 'Saturación de oxígeno', presion_sistolica: 'Presión sistólica', presion_diastolica: 'Presión diastólica', temperatura: 'Temperatura', glucosa: 'Glucosa' }
const SEMAFORO: Record<string, { cls: string; ico: string; label: string }> = { verde: { cls: 'ok', ico: '●', label: 'Verde' }, amarillo: { cls: 'warn', ico: '▲', label: 'Amarillo' }, rojo: { cls: 'crit', ico: '✖', label: 'Rojo' } }
const DOCS: Record<string, string> = { terminos: 'Términos y condiciones', privacidad: 'Política de privacidad' }

// CU06 Configurar parámetros del sistema
function TabParametros() {
  const [ps, setPs] = useState<Parametro[] | null>(null)
  const [ed, setEd] = useState<{ clave: string; valor: string; version: number; nota: string } | null>(null)
  const [error, setError] = useState<unknown>(null)
  const cargar = () => api<Parametro[]>('/configuracion/parametros').then(setPs).catch(setError)
  useEffect(() => { cargar() }, [])
  const guardar = async (e: FormEvent) => {
    e.preventDefault(); if (!ed) return; setError(null)
    try { await api(`/configuracion/parametros/${ed.clave}`, { method: 'PUT', body: { valor: ed.valor, version: ed.version, nota_cambio: ed.nota } }); setEd(null); cargar() }
    catch (err) { setError(err); cargar() }
  }
  const cats = [...new Set(ps?.map(p => p.categoria) ?? [])]
  return (
    <Card title="Parámetros del sistema" sub="CU06 · cada cambio exige una nota y queda versionado; si otra persona lo cambió antes, se avisa el conflicto">
      <ErrorBox error={error} />
      {!ps ? <Cargando /> : cats.map(c => (
        <div key={c} style={{ marginBottom: 14 }}>
          <div className="nav-group" style={{ padding: '6px 0', color: 'var(--ink-faint)' }}>{c}</div>
          <div className="table-wrap"><table className="data">
            <tbody>{ps.filter(p => p.categoria === c).map(p => (
              <tr key={p.clave}>
                <td style={{ width: '55%' }}><div className="strong mono">{p.clave}</div><div className="sub">{p.descripcion}</div></td>
                <td>{ed?.clave === p.clave ? (
                  <form className="mod-form" style={{ marginTop: 0 }} onSubmit={guardar}>
                    {p.tipo_valor === 'booleano'
                      ? <select value={ed.valor} onChange={e => setEd({ ...ed, valor: e.target.value })} aria-label="Valor"><option value="true">Sí</option><option value="false">No</option></select>
                      : <input className="inline" type={p.tipo_valor === 'numero' ? 'number' : 'text'} step="any" value={ed.valor} onChange={e => setEd({ ...ed, valor: e.target.value })} aria-label="Valor" style={{ flex: 'none' }} />}
                    <input placeholder="Nota del cambio" value={ed.nota} onChange={e => setEd({ ...ed, nota: e.target.value })} required minLength={3} aria-label="Nota" />
                    <button className="btn primary sm">Guardar</button><button type="button" className="btn ghost sm" onClick={() => setEd(null)}>×</button>
                  </form>
                ) : (
                  <><b>{p.tipo_valor === 'booleano' ? (p.valor === 'true' ? 'Sí' : 'No') : p.valor}</b>
                    <div className="sub">v{p.version}{p.fecha_actualizacion && ` · ${fechaHora(p.fecha_actualizacion)}`}{p.nota_cambio && ` · «${p.nota_cambio}»`}</div></>
                )}</td>
                <td className="right">{ed?.clave !== p.clave && <button className="btn ghost sm" onClick={() => setEd({ clave: p.clave, valor: p.valor, version: p.version, nota: '' })}>Cambiar</button>}</td>
              </tr>
            ))}</tbody>
          </table></div>
        </div>
      ))}
    </Card>
  )
}

// CU05 Configurar umbrales de alertas (semáforo de signos vitales)
function TabUmbrales() {
  const [us, setUs] = useState<Umbral[] | null>(null)
  const [ed, setEd] = useState<Record<string, { min: string; max: string }>>({})
  const [error, setError] = useState<unknown>(null)
  const [ok, setOk] = useState('')
  const cargar = () => api<Umbral[]>('/configuracion/umbrales').then(setUs).catch(setError)
  useEffect(() => { cargar() }, [])
  const key = (u: Umbral) => `${u.signo_vital}/${u.nivel_semaforo}`
  const guardar = async (u: Umbral) => {
    const v = ed[key(u)]; setError(null); setOk('')
    try {
      await api(`/configuracion/umbrales/${u.signo_vital}/${u.nivel_semaforo}`, { method: 'PUT', body: { valor_minimo: Number(v.min), valor_maximo: Number(v.max) } })
      const n = { ...ed }; delete n[key(u)]; setEd(n); setOk(`${SIGNOS[u.signo_vital] ?? u.signo_vital} (${u.nivel_semaforo}) actualizado.`); cargar()
    } catch (e) { setError(e) }
  }
  const signos = [...new Set(us?.map(u => u.signo_vital) ?? [])]
  return (
    <Card title="Umbrales del semáforo de signos vitales" sub="CU05 · fuera del rango verde se emite alerta; el rango amarillo debe contener al verde">
      <ErrorBox error={error} />{ok && <div className="alert ok">{ok}</div>}
      {!us ? <Cargando /> : (
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Signo vital</th><th>Nivel</th><th>Mínimo</th><th>Máximo</th><th>Actualizado</th><th></th></tr></thead>
          <tbody>{signos.flatMap(s => us.filter(u => u.signo_vital === s).map((u, i) => {
            const e = ed[key(u)]; const sm = SEMAFORO[u.nivel_semaforo]
            return (
              <tr key={key(u)}>
                <td>{i === 0 && <><div className="strong">{SIGNOS[s] ?? s}</div><div className="sub">{u.unidad}</div></>}</td>
                <td><span className={`chip ${sm?.cls ?? 'neutral'}`}>{sm?.ico} {sm?.label ?? u.nivel_semaforo}</span></td>
                <td><input className="inline" type="number" step="any" value={e?.min ?? u.valor_minimo} aria-label={`Mínimo ${s} ${u.nivel_semaforo}`}
                  onChange={ev => setEd({ ...ed, [key(u)]: { min: ev.target.value, max: e?.max ?? String(u.valor_maximo) } })} /></td>
                <td><input className="inline" type="number" step="any" value={e?.max ?? u.valor_maximo} aria-label={`Máximo ${s} ${u.nivel_semaforo}`}
                  onChange={ev => setEd({ ...ed, [key(u)]: { min: e?.min ?? String(u.valor_minimo), max: ev.target.value } })} /></td>
                <td className="nowrap">{fechaHora(u.fecha_actualizacion)}</td>
                <td className="right">{e && <button className="btn primary sm" onClick={() => guardar(u)}>Guardar</button>}</td>
              </tr>
            )
          }))}</tbody>
        </table></div>
      )}
    </Card>
  )
}

// CU07 Redactar versión legal · CU08 Publicar versión legal
function TabLegales() {
  const [vs, setVs] = useState<Version[] | null>(null)
  const [form, setForm] = useState<{ id?: number; tipo_documento: string; contenido: string; registro_cambios: string; fecha_vigencia: string; cambio_mayor: boolean } | null>(null)
  const [ver, setVer] = useState<number | null>(null)
  const [error, setError] = useState<unknown>(null)
  const cargar = () => api<Version[]>('/legales/versiones').then(setVs).catch(setError)
  useEffect(() => { cargar() }, [])

  const nuevo = (tipo: string) => {
    const vigente = vs?.find(v => v.tipo_documento === tipo && v.estado === 'publicada')
    const manana = new Date(Date.now() + 86400000).toISOString().slice(0, 10)
    setForm({ tipo_documento: tipo, contenido: vigente?.contenido ?? '', registro_cambios: '', fecha_vigencia: manana, cambio_mayor: false })
  }
  const guardar = async (e: FormEvent) => {
    e.preventDefault(); if (!form) return; setError(null)
    try {
      if (form.id) await api(`/legales/versiones/${form.id}`, { method: 'PATCH', body: { contenido: form.contenido, registro_cambios: form.registro_cambios, fecha_vigencia: form.fecha_vigencia } })
      else await api('/legales/versiones', { method: 'POST', body: form })
      setForm(null); cargar()
    } catch (err) { setError(err) }
  }
  const publicar = async (v: Version) => {
    if (!confirm(`¿Publicar ${DOCS[v.tipo_documento]} v${v.version}? Reemplaza a la versión vigente${v.requiere_reaceptacion ? ' y los usuarios deberán aceptarla de nuevo' : ''}.`)) return
    setError(null)
    try { await api(`/legales/versiones/${v.id_version}/publicar`, { method: 'POST' }); cargar() } catch (e) { setError(e) }
  }

  return (
    <Card title="Términos y política de privacidad" sub="CU07 redactar · CU08 publicar · una versión publicada no se edita: se crea una nueva"
      actions={!form && <div className="state-actions">
        <button className="btn primary sm" onClick={() => nuevo('terminos')}>+ Nueva versión de términos</button>
        <button className="btn ghost sm" onClick={() => nuevo('privacidad')}>+ Nueva versión de privacidad</button></div>}>
      <ErrorBox error={error} />
      {form && (
        <form className="form inline-form" style={{ gridTemplateColumns: '1fr 1fr' }} onSubmit={guardar}>
          <div className="full strong">{form.id ? 'Editar borrador' : 'Nuevo borrador'} · {DOCS[form.tipo_documento]}</div>
          <label className="full">Texto completo <span className="hint">mínimo 100 caracteres · {form.contenido.length}</span>
            <textarea rows={10} value={form.contenido} onChange={e => setForm({ ...form, contenido: e.target.value })} required minLength={100} /></label>
          <label className="full">Registro de cambios <span className="hint">qué cambió y por qué (lo verán los usuarios)</span>
            <input value={form.registro_cambios} onChange={e => setForm({ ...form, registro_cambios: e.target.value })} required minLength={5} /></label>
          <label>Fecha de vigencia<input type="date" value={form.fecha_vigencia} onChange={e => setForm({ ...form, fecha_vigencia: e.target.value })} required /></label>
          {!form.id && <label className="toggle" style={{ flexDirection: 'row', alignSelf: 'end' }}><input type="checkbox" checked={form.cambio_mayor} onChange={e => setForm({ ...form, cambio_mayor: e.target.checked })} />
            Cambio mayor (sube versión X.0 y exige re-aceptación)</label>}
          <div className="actions full"><button type="button" className="btn ghost" onClick={() => setForm(null)}>Cancelar</button><button className="btn primary">Guardar borrador</button></div>
        </form>
      )}
      {!vs ? <Cargando /> : (
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Documento</th><th>Versión</th><th>Estado</th><th>Vigencia</th><th>Cambios</th><th></th></tr></thead>
          <tbody>{vs.map(v => (
            <Fragment key={v.id_version}>
              <tr>
                <td className="strong">{DOCS[v.tipo_documento]}</td>
                <td className="mono">v{v.version}{v.requiere_reaceptacion && <div className="sub">re-aceptación</div>}</td>
                <td><Chip estado={v.estado} /></td>
                <td className="nowrap">{fecha(v.fecha_vigencia + 'T12:00:00')}<div className="sub">{v.autor}</div></td>
                <td className="small">{v.registro_cambios}</td>
                <td className="right"><div className="state-actions" style={{ justifyContent: 'flex-end' }}>
                  <button className="btn ghost sm" onClick={() => setVer(ver === v.id_version ? null : v.id_version)}>{ver === v.id_version ? 'Ocultar' : 'Ver texto'}</button>
                  {v.estado === 'borrador' && <>
                    <button className="btn ghost sm" onClick={() => setForm({ id: v.id_version, tipo_documento: v.tipo_documento, contenido: v.contenido, registro_cambios: v.registro_cambios, fecha_vigencia: v.fecha_vigencia, cambio_mayor: v.requiere_reaceptacion })}>Editar</button>
                    <button className="btn primary sm" onClick={() => publicar(v)}>Publicar</button></>}
                </div></td>
              </tr>
              {ver === v.id_version && <tr><td colSpan={6}><div className="legal-body">{v.contenido}</div></td></tr>}
            </Fragment>
          ))}</tbody>
        </table></div>
      )}
    </Card>
  )
}

type Tab = 'parametros' | 'umbrales' | 'legales'
export default function Configuracion() {
  const [tab, setTab] = useState<Tab>('parametros')
  return (
    <>
      <Tabs value={tab} onChange={setTab} items={[['parametros', 'Parámetros'], ['umbrales', 'Umbrales de alertas'], ['legales', 'Documentos legales']]} />
      {tab === 'parametros' && <TabParametros />}
      {tab === 'umbrales' && <TabUmbrales />}
      {tab === 'legales' && <TabLegales />}
    </>
  )
}
