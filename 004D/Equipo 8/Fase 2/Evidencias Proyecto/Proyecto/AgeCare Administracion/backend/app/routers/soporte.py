"""Módulo de soporte: CU25 indicadores · CU35 cola · CU36 registrar · CU37 atender · CU38 contexto
· CU39 responder · CU40 encuesta de satisfacción."""
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from ..audit import diff, registrar
from ..db import get_db, utcnow
from ..deps import permisos_de, requiere
from ..errors import ApiError
from ..models import (TRANSICIONES_TICKET, CategoriaTicket, EncuestaSatisfaccion, MembresiaCirculo, MiembroStaff,
                      Paciente, RespuestaTicket, Ticket, UsuarioApp)
from ..schemas import (CategoriaConteo, ContextoOut, EncuestaOut, IndicadoresOut, Page, Ref, RespuestaIn, RespuestaOut,
                       SolicitanteOut, TicketCreateIn, TicketDetailOut, TicketOut, TicketUpdateIn)

router = APIRouter(prefix="/soporte", tags=["Soporte"])
LECTURA = requiere("soporte", "lectura")
ESCRITURA = requiere("soporte", "escritura")

ORDEN_PRIORIDAD = case({"critica": 4, "alta": 3, "media": 2, "baja": 1}, value=Ticket.prioridad)
ORDENES = {
    "-fecha_creacion": Ticket.fecha_creacion.desc(), "fecha_creacion": Ticket.fecha_creacion.asc(),
    "-fecha_actualizacion": Ticket.fecha_actualizacion.desc(), "-prioridad": ORDEN_PRIORIDAD.desc(),
}


# ---------------------------------------------------------------- serialización
def ticket_out(t: Ticket) -> TicketOut:
    u = t.usuario
    return TicketOut(
        id_ticket=t.id_ticket, numero=t.numero, asunto=t.asunto,
        categoria=Ref(id=t.categoria.codigo_categoria, nombre=t.categoria.nombre),
        prioridad=t.prioridad, estado=t.estado, canal=t.canal,
        solicitante=SolicitanteOut(id_usuario=u.id_usuario if u else None,
                                   nombre=u.nombre if u else (t.nombre_solicitante or t.email_solicitante or "—"),
                                   email=u.email if u else t.email_solicitante,
                                   perfiles=[p.codigo_perfil for p in u.perfiles] if u else []),
        paciente=Ref(id=t.paciente.id_paciente, nombre=t.paciente.nombre) if t.paciente else None,
        asignado=Ref(id=t.asignado.id_staff, nombre=t.asignado.nombre_completo) if t.asignado else None,
        fecha_creacion=t.fecha_creacion, fecha_actualizacion=t.fecha_actualizacion,
        fecha_primera_respuesta=t.fecha_primera_respuesta, fecha_resolucion=t.fecha_resolucion, fecha_cierre=t.fecha_cierre,
    )


def respuesta_out(r: RespuestaTicket) -> RespuestaOut:
    if r.tipo_autor == "staff":
        nombre = r.autor.nombre_completo if r.autor else "Staff"
    elif r.tipo_autor == "usuario":
        nombre = (r.ticket.usuario.nombre if r.ticket.usuario else r.ticket.nombre_solicitante) or "Usuario"
    else:
        nombre = "Sistema"
    return RespuestaOut(id_respuesta=r.id_respuesta, tipo_autor=r.tipo_autor, autor_nombre=nombre, cuerpo=r.cuerpo,
                        es_interna=r.es_interna, fecha=r.fecha)


def _snap(t: Ticket) -> dict:
    return {"estado": t.estado, "prioridad": t.prioridad, "codigo_categoria": t.codigo_categoria,
            "id_staff_asignado": t.id_staff_asignado}


def _get(db: Session, ref: str) -> Ticket:
    """Acepta el id interno o el número visible con prefijo # (p. ej. %231482)."""
    t = None
    if ref.startswith("#") and ref[1:].isdigit():
        t = db.scalar(select(Ticket).where(Ticket.numero == int(ref[1:])))
    elif ref.isdigit():
        t = db.get(Ticket, int(ref))
    if t is None:
        raise ApiError(404, "NOT_FOUND", "El ticket no existe.")
    return t


# ---------------------------------------------------------------- catálogos
@router.get("/categorias", response_model=list[Ref], summary="Categorías de ticket")
def categorias(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    return [Ref(id=c.codigo_categoria, nombre=c.nombre)
            for c in db.scalars(select(CategoriaTicket).order_by(CategoriaTicket.nombre))]


@router.get("/agentes", response_model=list[Ref], summary="Staff activo que puede atender tickets")
def agentes(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    activos = db.scalars(select(MiembroStaff).where(MiembroStaff.estado == "activo").order_by(MiembroStaff.nombre_completo))
    return [Ref(id=s.id_staff, nombre=s.nombre_completo) for s in activos
            if permisos_de(db, s.codigo_rol).get("soporte") == "escritura"]


# ---------------------------------------------------------------- CU25
@router.get("/indicadores", response_model=IndicadoresOut, summary="CU25 · Indicadores de soporte")
def indicadores(_: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    desde = utcnow() - timedelta(days=30)
    conteo = dict(db.execute(select(Ticket.estado, func.count()).group_by(Ticket.estado)).all())
    sin_asignar = db.scalar(select(func.count()).where(Ticket.id_staff_asignado.is_(None),
                                                       Ticket.estado.in_(("abierto", "en_curso", "esperando_usuario"))))
    resueltos = db.scalar(select(func.count()).where(Ticket.fecha_resolucion >= desde))
    # Promedios calculados en Python para funcionar igual en PostgreSQL y SQLite
    filas = db.execute(select(Ticket.fecha_creacion, Ticket.fecha_primera_respuesta, Ticket.fecha_resolucion)
                       .where(Ticket.fecha_creacion >= desde)).all()
    primeras = [(p - c).total_seconds() / 3600 for c, p, _ in filas if p]
    resol = [(r - c).total_seconds() / 3600 for c, _, r in filas if r]
    csat = db.execute(select(func.avg(EncuestaSatisfaccion.puntaje), func.count(EncuestaSatisfaccion.puntaje))
                      .where(EncuestaSatisfaccion.fecha_respuesta >= desde)).one()
    cats = db.execute(select(CategoriaTicket.codigo_categoria, CategoriaTicket.nombre, func.count(Ticket.id_ticket))
                      .join(Ticket, Ticket.codigo_categoria == CategoriaTicket.codigo_categoria)
                      .where(Ticket.fecha_creacion >= desde)
                      .group_by(CategoriaTicket.codigo_categoria, CategoriaTicket.nombre)
                      .order_by(func.count(Ticket.id_ticket).desc())).all()
    return IndicadoresOut(
        abiertos=conteo.get("abierto", 0), en_curso=conteo.get("en_curso", 0),
        esperando_usuario=conteo.get("esperando_usuario", 0), resueltos_30d=resueltos or 0,
        primera_respuesta_horas_prom=round(sum(primeras) / len(primeras), 1) if primeras else None,
        resolucion_horas_prom=round(sum(resol) / len(resol), 1) if resol else None,
        csat_promedio=round(float(csat[0]), 2) if csat[0] is not None else None, csat_respuestas=csat[1] or 0,
        sin_asignar=sin_asignar or 0,
        por_categoria_30d=[CategoriaConteo(codigo=c, nombre=n, total=t) for c, n, t in cats],
    )


# ---------------------------------------------------------------- CU35
@router.get("/tickets", response_model=Page[TicketOut], summary="CU35 · Consultar cola de tickets")
def listar(estado: str | None = None, prioridad: str | None = None, categoria: str | None = None,
           asignado: str | None = Query(None, description="id del staff, 'yo' o 'sin_asignar'"),
           activos: bool = Query(False, description="Solo abierto, en curso o esperando usuario"),
           q: str | None = Query(None, max_length=120), orden: str = "-fecha_creacion",
           page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
           staff: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    stmt = select(Ticket).outerjoin(UsuarioApp, Ticket.id_usuario == UsuarioApp.id_usuario)
    if estado:
        stmt = stmt.where(Ticket.estado.in_(estado.split(",")))
    if activos:
        stmt = stmt.where(Ticket.estado.in_(("abierto", "en_curso", "esperando_usuario")))
    if prioridad:
        stmt = stmt.where(Ticket.prioridad == prioridad)
    if categoria:
        stmt = stmt.where(Ticket.codigo_categoria == categoria)
    if asignado == "yo":
        stmt = stmt.where(Ticket.id_staff_asignado == staff.id_staff)
    elif asignado == "sin_asignar":
        stmt = stmt.where(Ticket.id_staff_asignado.is_(None))
    elif asignado and asignado.isdigit():
        stmt = stmt.where(Ticket.id_staff_asignado == int(asignado))
    if q:
        qq = q.strip().lstrip("#")
        like = f"%{qq.lower()}%"
        conds = [func.lower(Ticket.asunto).like(like), func.lower(Ticket.email_solicitante).like(like),
                 func.lower(UsuarioApp.email).like(like), func.lower(UsuarioApp.nombre).like(like)]
        if qq.isdigit():
            conds.append(Ticket.numero == int(qq))
        stmt = stmt.where(or_(*conds))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(ORDENES.get(orden, Ticket.fecha_creacion.desc()), Ticket.id_ticket.desc())
                      .offset((page - 1) * page_size).limit(page_size)).unique().all()
    return Page(items=[ticket_out(t) for t in rows], page=page, page_size=page_size, total=total)


# ---------------------------------------------------------------- CU36
@router.post("/tickets", response_model=TicketOut, status_code=201, summary="CU36 · Registrar ticket")
def crear(data: TicketCreateIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA), db: Session = Depends(get_db)):
    if db.get(CategoriaTicket, data.codigo_categoria) is None:
        raise ApiError(422, "VALIDATION_ERROR", "La categoría no existe.",
                       [{"field": "codigo_categoria", "message": "Categoría desconocida"}])
    email = data.email_usuario.lower()
    usuario = db.scalar(select(UsuarioApp).where(UsuarioApp.email == email))
    if usuario is None and not data.confirmar_sin_enlace:
        raise ApiError(404, "USER_NOT_FOUND", "No existe ningún usuario con ese correo. Verifícalo o crea el ticket "
                                             "sin enlazar (confirmar_sin_enlace = true).")
    if data.id_paciente is not None and db.get(Paciente, data.id_paciente) is None:
        raise ApiError(422, "VALIDATION_ERROR", "El paciente no existe.", [{"field": "id_paciente", "message": "No existe"}])
    t = Ticket(asunto=data.asunto.strip(), descripcion=data.descripcion.strip(), codigo_categoria=data.codigo_categoria,
               prioridad=data.prioridad, canal=data.canal, estado="abierto", id_paciente=data.id_paciente,
               id_usuario=usuario.id_usuario if usuario else None,
               nombre_solicitante=usuario.nombre if usuario else (data.nombre_solicitante or None),
               email_solicitante=email)
    db.add(t)
    db.flush()
    t.numero = 1000 + t.id_ticket  # correlativo visible (#1001, #1002…)
    registrar(db, actor=staff, accion="ticket.crear", tipo_entidad="ticket", id_entidad=t.id_ticket,
              despues=_snap(t) | {"numero": t.numero, "asunto": t.asunto}, request=request)
    db.commit()
    db.refresh(t)
    return ticket_out(t)


# ---------------------------------------------------------------- detalle + CU38
@router.get("/tickets/{ref}", response_model=TicketDetailOut, summary="Detalle del ticket con contexto (CU38)")
def detalle(ref: str, _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    t = _get(db, ref)
    u = t.usuario
    pacientes: list[Ref] = []
    previos = 0
    if u:
        pacientes = [Ref(id=m.paciente.id_paciente, nombre=f"{m.paciente.nombre} ({m.rol_en_circulo})")
                     for m in db.scalars(select(MembresiaCirculo).where(MembresiaCirculo.id_usuario == u.id_usuario))]
        previos = db.scalar(select(func.count()).where(Ticket.id_usuario == u.id_usuario, Ticket.id_ticket != t.id_ticket))
    total_resp = db.scalar(select(func.count()).where(RespuestaTicket.id_ticket == t.id_ticket))
    base = ticket_out(t).model_dump()
    return TicketDetailOut(
        **base, descripcion=t.descripcion,
        contexto=ContextoOut(estado_cuenta=u.estado_cuenta if u else None, fecha_registro=u.fecha_registro if u else None,
                             ultimo_acceso=u.ultimo_acceso if u else None, pacientes=pacientes, tickets_previos=previos),
        respuestas_total=total_resp,
        encuesta=EncuestaOut.model_validate(t.encuesta) if t.encuesta else None,
        transiciones_permitidas=sorted(TRANSICIONES_TICKET[t.estado]),
    )


# ---------------------------------------------------------------- CU37 (+ CU40)
@router.patch("/tickets/{ref}", response_model=TicketOut, summary="CU37 · Atender ticket (estado, prioridad, asignación)")
def actualizar(ref: str, data: TicketUpdateIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
               db: Session = Depends(get_db)):
    t = _get(db, ref)
    antes = _snap(t)
    enviados = data.model_fields_set
    now = utcnow()

    if "codigo_categoria" in enviados and data.codigo_categoria:
        if db.get(CategoriaTicket, data.codigo_categoria) is None:
            raise ApiError(422, "VALIDATION_ERROR", "La categoría no existe.")
        t.codigo_categoria = data.codigo_categoria
    if "prioridad" in enviados and data.prioridad:
        t.prioridad = data.prioridad
    if "id_staff_asignado" in enviados:
        if data.id_staff_asignado is not None:
            ag = db.get(MiembroStaff, data.id_staff_asignado)
            if ag is None or ag.estado != "activo" or permisos_de(db, ag.codigo_rol).get("soporte") != "escritura":
                raise ApiError(404, "ASSIGNEE_NOT_FOUND", "El agente indicado no existe o está desactivado.")
        t.id_staff_asignado = data.id_staff_asignado

    if "estado" in enviados and data.estado and data.estado != t.estado:
        if data.estado not in TRANSICIONES_TICKET[t.estado]:
            raise ApiError(409, "INVALID_TRANSITION",
                           f"Transición no permitida: {t.estado} → {data.estado}. Un ticket cerrado no se reabre; crea uno nuevo.",
                           {"permitidas": sorted(TRANSICIONES_TICKET[t.estado])})
        anterior, t.estado = t.estado, data.estado
        if data.estado == "en_curso" and t.id_staff_asignado is None:
            t.id_staff_asignado = staff.id_staff  # quien lo toma queda asignado
        if data.estado == "resuelto":
            t.fecha_resolucion = now
            if t.encuesta is None:  # CU40: se envía la encuesta CSAT (envío simulado)
                db.add(EncuestaSatisfaccion(id_ticket=t.id_ticket, fecha_envio=now))
                db.add(RespuestaTicket(id_ticket=t.id_ticket, tipo_autor="sistema", es_interna=True,
                                       cuerpo="Se envió la encuesta de satisfacción al usuario."))
        if anterior == "resuelto" and data.estado == "en_curso":
            t.fecha_resolucion = None
        if data.estado == "cerrado":
            t.fecha_cierre = now
    t.fecha_actualizacion = now
    a, d = diff(antes, _snap(t))
    if d:
        registrar(db, actor=staff, accion="ticket.actualizar", tipo_entidad="ticket", id_entidad=t.id_ticket,
                  antes=a, despues=d, request=request)
    db.commit()
    db.refresh(t)
    return ticket_out(t)


# ---------------------------------------------------------------- CU39
@router.get("/tickets/{ref}/respuestas", response_model=list[RespuestaOut], summary="Conversación del ticket")
def conversacion(ref: str, _: MiembroStaff = Depends(LECTURA), db: Session = Depends(get_db)):
    t = _get(db, ref)
    return [respuesta_out(r) for r in t.respuestas]


@router.post("/tickets/{ref}/respuestas", response_model=RespuestaOut, status_code=201,
             summary="CU39 · Responder ticket o agregar nota interna")
def responder(ref: str, data: RespuestaIn, request: Request, staff: MiembroStaff = Depends(ESCRITURA),
              db: Session = Depends(get_db)):
    t = _get(db, ref)
    if t.estado == "cerrado":
        raise ApiError(409, "TICKET_CLOSED", "El ticket está cerrado y no admite nuevas respuestas.")
    now = utcnow()
    r = RespuestaTicket(id_ticket=t.id_ticket, id_staff_autor=staff.id_staff, tipo_autor="staff", cuerpo=data.cuerpo.strip(),
                        es_interna=data.es_interna, fecha=now)
    db.add(r)
    if not data.es_interna and t.fecha_primera_respuesta is None:
        t.fecha_primera_respuesta = now  # base del indicador de primera respuesta (OE1)
    if t.id_staff_asignado is None:
        t.id_staff_asignado = staff.id_staff
    t.fecha_actualizacion = now
    db.flush()
    registrar(db, actor=staff, accion="ticket.nota_interna" if data.es_interna else "ticket.responder",
              tipo_entidad="ticket", id_entidad=t.id_ticket, despues={"id_respuesta": r.id_respuesta}, request=request)
    db.commit()
    db.refresh(r)
    return respuesta_out(r)
