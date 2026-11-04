// Pasarela simulada (PAGOS_MODO=simulado) y comprobante del pago al volver de Webpay.
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { clp, fechaHora } from '../components/ui'
import { papi, textoError, type Orden } from './api'
import { usePortal } from './auth'
import { PaginaAcceso } from './Acceso'
import { Cargando } from './PortalApp'

export function PasarelaSimulada() {
  const [q] = useSearchParams()
  const nav = useNavigate()
  const orden = q.get('orden') ?? ''
  const [o, setO] = useState<Orden | null>(null)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  useEffect(() => { papi<Orden>(`/pagos/${orden}`).then(setO).catch(e => setError(textoError(e))) }, [orden])
  const responder = async (aprobar: boolean) => {
    setEnviando(true)
    try { await papi(`/pagos/${orden}/simulado`, { method: 'POST', body: { aprobar } }); nav(`/portal/pago/resultado?orden=${orden}`, { replace: true }) }
    catch (e) { setError(textoError(e)); setEnviando(false) }
  }
  if (error) return <div className="p-alerta crit">{error}</div>
  if (!o) return <Cargando />
  return (
    <div className="p-centrado">
      <section className="p-tarjeta angosta p-pasarela">
        <div className="p-pasarela-head"><b>Pasarela de pago</b><span className="p-chip warn">Modo demostración</span></div>
        <p className="p-sub">No se cobra dinero real. En producción esta pantalla es Webpay de Transbank.</p>
        <dl className="p-kv">
          <dt>Comercio</dt><dd>AgeCare · Wellq Co</dd>
          <dt>Orden</dt><dd className="mono">{o.orden_compra}</dd>
          <dt>Detalle</dt><dd>Plan {o.plan} · 30 días</dd>
          <dt>Total</dt><dd className="p-total">{clp(o.monto)}</dd>
        </dl>
        <div className="p-tarjeta-demo">💳 VISA •••• 4242</div>
        {o.estado !== 'iniciada' ? <div className="p-alerta neutral">Esta orden ya fue procesada ({o.estado}).</div> : (
          <div className="p-acciones-col">
            <button className="p-btn primario grande" disabled={enviando} onClick={() => responder(true)}>Pagar {clp(o.monto)}</button>
            <button className="p-btn ghost" disabled={enviando} onClick={() => responder(false)}>Simular pago rechazado</button>
          </div>
        )}
      </section>
    </div>
  )
}

const RESULTADO: Record<string, { ico: string; titulo: string; cls: string }> = {
  aprobada: { ico: '✅', titulo: 'Pago aprobado', cls: 'ok' },
  rechazada: { ico: '❌', titulo: 'Pago rechazado', cls: 'crit' },
  anulada: { ico: '↩️', titulo: 'Pago anulado', cls: 'neutral' },
  error: { ico: '⚠️', titulo: 'No pudimos confirmar el pago', cls: 'warn' },
  iniciada: { ico: '⏳', titulo: 'Pago en proceso', cls: 'neutral' },
}

export function ResultadoPago() {
  const [q] = useSearchParams()
  const { me } = usePortal()
  const orden = q.get('orden')
  const [o, setO] = useState<Orden | null>(null)
  const [error, setError] = useState(orden ? '' : 'No recibimos el resultado del pago. Revisa tus residentes o intenta de nuevo.')
  useEffect(() => { if (orden) papi<Orden>(`/pagos/${orden}`).then(setO).catch(e => setError(textoError(e))) }, [orden])
  if (error) return <PaginaAcceso titulo="Resultado del pago"><div className="p-alerta crit">{error}</div><Link to="/portal" className="p-btn primario grande">Ir al portal</Link></PaginaAcceso>
  if (!o) return <Cargando />
  const r = RESULTADO[o.estado] ?? RESULTADO.iniciada
  const siguiente = o.requiere_residente && o.id_suscripcion
    ? { to: `/portal/representante/plan/${o.id_suscripcion}/residente`, txt: 'Registrar a mi residente' }
    : o.estado === 'aprobada' ? { to: '/portal/representante', txt: 'Ir a mis residentes' }
      : { to: '/portal/representante/contratar', txt: 'Intentar de nuevo' }
  return (
    <PaginaAcceso titulo={`${r.ico} ${r.titulo}`}>
      <div className={`p-alerta ${r.cls}`}>{o.estado === 'aprobada' ? `Tu plan ${o.plan} quedó activo por 30 días.` : o.detalle ?? 'No se realizó ningún cargo.'}</div>
      <dl className="p-kv comprobante">
        <dt>Comercio</dt><dd>AgeCare · Wellq Co</dd>
        <dt>Orden de compra</dt><dd className="mono">{o.orden_compra}</dd>
        <dt>Monto</dt><dd>{clp(o.monto)}</dd>
        <dt>Detalle</dt><dd>Plan {o.plan} · {o.tipo === 'alta' ? 'contratación' : o.tipo === 'cambio' ? 'cambio de plan' : 'pago del mes'}</dd>
        {o.codigo_autorizacion && <><dt>Código de autorización</dt><dd className="mono">{o.codigo_autorizacion}</dd></>}
        {o.tarjeta && <><dt>Tarjeta</dt><dd>•••• {o.tarjeta}{o.tipo_pago ? ` · ${o.tipo_pago}` : ''}</dd></>}
        <dt>Fecha</dt><dd>{fechaHora(o.fecha_confirmacion ?? o.fecha_creacion)}</dd>
        <dt>Medio</dt><dd>{o.proveedor === 'webpay' ? 'Webpay Plus (Transbank)' : 'Pasarela de demostración'}</dd>
      </dl>
      {me ? <Link to={siguiente.to} className="p-btn primario grande">{siguiente.txt}</Link>
        : <Link to="/portal/ingresar" state={{ desde: siguiente.to }} className="p-btn primario grande">Ingresar para continuar</Link>}
    </PaginaAcceso>
  )
}
