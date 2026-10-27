export default function Proximamente({ modulo }: { modulo: { label: string; ico: string; sprint?: string } }) {
  return (
    <div className="placeholder-box">
      <div className="ph-ico">{modulo.ico}</div>
      <b>{modulo.label}</b>
      <p>Módulo planificado para el <b>{modulo.sprint}</b> según la carta Gantt. La ruta, el permiso y el menú ya están
        conectados al control de acceso por rol.</p>
    </div>
  )
}
