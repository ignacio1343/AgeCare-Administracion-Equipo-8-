--
-- PostgreSQL database dump
--

\restrict oVkzSr08YtS8AzxpFeJOKOQWVEoIE1agkdmZh9tkkQS9FrfpJ7Q7ZlcpLvxDbmo

-- Dumped from database version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: actividad_perfil; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.actividad_perfil (
    ventana_dias integer NOT NULL,
    codigo_perfil character varying(40) NOT NULL,
    usuarios_activos integer NOT NULL,
    sesiones_semana numeric(7,2) NOT NULL,
    duracion_media_seg integer NOT NULL,
    retencion_30d numeric(7,5) NOT NULL
);


--
-- Name: adopcion_funcionalidad; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.adopcion_funcionalidad (
    ventana_dias integer NOT NULL,
    codigo_funcionalidad character varying(40) NOT NULL,
    codigo_perfil character varying(40) NOT NULL,
    usuarios integer NOT NULL,
    activos_del_perfil integer NOT NULL,
    adopcion numeric(7,5) NOT NULL
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: alerta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alerta (
    id_alerta integer NOT NULL,
    id_paciente integer NOT NULL,
    codigo_tipo character varying(40) NOT NULL,
    fecha_emision timestamp with time zone NOT NULL,
    severidad character varying(30) NOT NULL,
    estado character varying(30) NOT NULL,
    fecha_atencion timestamp with time zone,
    signo_vital character varying(40),
    valor numeric(10,2),
    nivel_semaforo character varying(20)
);


--
-- Name: alerta_id_alerta_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.alerta_id_alerta_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: alerta_id_alerta_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.alerta_id_alerta_seq OWNED BY public.alerta.id_alerta;


--
-- Name: categoria_ticket; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categoria_ticket (
    codigo_categoria character varying(40) NOT NULL,
    nombre character varying(120) NOT NULL
);


--
-- Name: componente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.componente (
    codigo_componente character varying(40) NOT NULL,
    nombre character varying(120) NOT NULL,
    tecnologia character varying(120),
    es_asincrono boolean NOT NULL,
    estado_actual character varying(30) NOT NULL,
    uptime_30d numeric(7,5) NOT NULL,
    latencia_p50_ms integer,
    latencia_p95_ms integer,
    umbral_p95_ms integer NOT NULL,
    fallos_consecutivos integer NOT NULL,
    estado_desde timestamp with time zone NOT NULL,
    orden integer NOT NULL,
    CONSTRAINT ck_componente_estado CHECK (((estado_actual)::text = ANY ((ARRAY['operativo'::character varying, 'degradado'::character varying, 'caido'::character varying])::text[])))
);


--
-- Name: componente_proceso; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.componente_proceso (
    codigo_componente character varying(40) NOT NULL,
    codigo_proceso character varying(40) NOT NULL,
    fecha_asignacion timestamp with time zone NOT NULL
);


--
-- Name: contenido; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contenido (
    id_contenido integer NOT NULL,
    tipo character varying(20) NOT NULL,
    titulo character varying(160) NOT NULL,
    cuerpo text NOT NULL,
    etiquetas character varying(400),
    estado character varying(30) NOT NULL,
    fecha_programada timestamp with time zone,
    fecha_publicacion timestamp with time zone,
    fecha_creacion timestamp with time zone NOT NULL,
    fecha_eliminacion timestamp with time zone,
    CONSTRAINT ck_contenido_estado CHECK (((estado)::text = ANY ((ARRAY['borrador'::character varying, 'programado'::character varying, 'publicado'::character varying, 'archivado'::character varying])::text[]))),
    CONSTRAINT ck_contenido_tipo CHECK (((tipo)::text = ANY ((ARRAY['chiste'::character varying, 'noticia'::character varying])::text[])))
);


--
-- Name: contenido_id_contenido_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contenido_id_contenido_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contenido_id_contenido_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contenido_id_contenido_seq OWNED BY public.contenido.id_contenido;


--
-- Name: cuenta_cliente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cuenta_cliente (
    id_cuenta integer NOT NULL,
    id_usuario integer NOT NULL,
    tipo_cuenta character varying(20) NOT NULL,
    nombre character varying(120) NOT NULL,
    email_facturacion character varying(150) NOT NULL,
    rut character varying(12),
    estado character varying(30) NOT NULL,
    fecha_creacion timestamp with time zone NOT NULL,
    CONSTRAINT ck_cuenta_tipo CHECK (((tipo_cuenta)::text = ANY ((ARRAY['familia'::character varying, 'proveedor'::character varying])::text[])))
);


--
-- Name: cuenta_cliente_id_cuenta_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cuenta_cliente_id_cuenta_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cuenta_cliente_id_cuenta_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cuenta_cliente_id_cuenta_seq OWNED BY public.cuenta_cliente.id_cuenta;


--
-- Name: elemento_moderacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.elemento_moderacion (
    id_elemento integer NOT NULL,
    id_usuario_autor integer NOT NULL,
    id_usuario_reportante integer,
    id_staff_decisor integer,
    tipo_elemento character varying(30) NOT NULL,
    contenido_reportado text NOT NULL,
    motivo_reporte character varying(300),
    es_reporte_seguridad boolean NOT NULL,
    estado character varying(30) NOT NULL,
    motivo_rechazo character varying(30),
    nota_decision character varying(1000),
    fecha_decision timestamp with time zone,
    fecha_creacion timestamp with time zone NOT NULL,
    CONSTRAINT ck_moderacion_estado CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'aprobado'::character varying, 'rechazado'::character varying])::text[]))),
    CONSTRAINT ck_moderacion_motivo CHECK ((((estado)::text <> 'rechazado'::text) OR (motivo_rechazo IS NOT NULL))),
    CONSTRAINT ck_moderacion_tipo CHECK (((tipo_elemento)::text = ANY ((ARRAY['resena'::character varying, 'foto'::character varying, 'mensaje'::character varying, 'perfil'::character varying])::text[])))
);


--
-- Name: elemento_moderacion_id_elemento_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.elemento_moderacion_id_elemento_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: elemento_moderacion_id_elemento_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.elemento_moderacion_id_elemento_seq OWNED BY public.elemento_moderacion.id_elemento;


--
-- Name: encuesta_satisfaccion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.encuesta_satisfaccion (
    id_encuesta integer NOT NULL,
    id_ticket integer NOT NULL,
    fecha_envio timestamp with time zone NOT NULL,
    fecha_respuesta timestamp with time zone,
    puntaje integer,
    comentario text,
    CONSTRAINT ck_encuesta_puntaje CHECK (((puntaje IS NULL) OR ((puntaje >= 1) AND (puntaje <= 5))))
);


--
-- Name: encuesta_satisfaccion_id_encuesta_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.encuesta_satisfaccion_id_encuesta_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: encuesta_satisfaccion_id_encuesta_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.encuesta_satisfaccion_id_encuesta_seq OWNED BY public.encuesta_satisfaccion.id_encuesta;


--
-- Name: evento_pago; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evento_pago (
    id_evento integer NOT NULL,
    id_transaccion integer,
    id_externo_evento character varying(100) NOT NULL,
    tipo_evento character varying(60) NOT NULL,
    payload text,
    fecha_recepcion timestamp with time zone NOT NULL,
    procesado boolean NOT NULL,
    error_procesamiento character varying(300)
);


--
-- Name: evento_pago_id_evento_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.evento_pago_id_evento_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: evento_pago_id_evento_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.evento_pago_id_evento_seq OWNED BY public.evento_pago.id_evento;


--
-- Name: funcionalidad; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.funcionalidad (
    codigo_funcionalidad character varying(40) NOT NULL,
    nombre character varying(120) NOT NULL,
    uso_bajo_esperado boolean NOT NULL,
    nota character varying(300),
    orden integer NOT NULL
);


--
-- Name: incidente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incidente (
    id_incidente integer NOT NULL,
    codigo_componente character varying(40),
    id_staff_responsable integer,
    titulo character varying(160) NOT NULL,
    severidad character varying(30) NOT NULL,
    estado character varying(30) NOT NULL,
    es_mantenimiento boolean NOT NULL,
    creado_automaticamente boolean NOT NULL,
    descripcion text NOT NULL,
    resolucion text,
    fecha_inicio timestamp with time zone NOT NULL,
    fecha_resolucion timestamp with time zone,
    fecha_actualizacion timestamp with time zone NOT NULL,
    CONSTRAINT ck_incidente_estado CHECK (((estado)::text = ANY ((ARRAY['investigando'::character varying, 'en_observacion'::character varying, 'resuelto'::character varying, 'completado'::character varying])::text[]))),
    CONSTRAINT ck_incidente_severidad CHECK (((severidad)::text = ANY ((ARRAY['degradado'::character varying, 'caido'::character varying])::text[])))
);


--
-- Name: incidente_id_incidente_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.incidente_id_incidente_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: incidente_id_incidente_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.incidente_id_incidente_seq OWNED BY public.incidente.id_incidente;


--
-- Name: membresia_circulo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.membresia_circulo (
    id_usuario integer NOT NULL,
    id_paciente integer NOT NULL,
    rol_en_circulo character varying(30) NOT NULL,
    estado character varying(30) NOT NULL,
    fecha_invitacion timestamp with time zone NOT NULL,
    fecha_aceptacion timestamp with time zone
);


--
-- Name: mensaje_whatsapp; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mensaje_whatsapp (
    id_mensaje integer NOT NULL,
    id_alerta integer,
    id_paciente integer NOT NULL,
    id_usuario integer NOT NULL,
    telefono character varying(20),
    direccion character varying(10) DEFAULT 'saliente'::character varying NOT NULL,
    tipo_mensaje character varying(30) NOT NULL,
    plantilla character varying(80),
    contenido character varying(600) NOT NULL,
    estado character varying(20) NOT NULL,
    motivo character varying(300),
    id_mensaje_proveedor character varying(150),
    intentos integer NOT NULL,
    proximo_intento timestamp with time zone,
    fecha_creacion timestamp with time zone NOT NULL,
    fecha_envio timestamp with time zone,
    fecha_entrega timestamp with time zone,
    fecha_lectura timestamp with time zone,
    CONSTRAINT ck_whatsapp_direccion CHECK (((direccion)::text = ANY ((ARRAY['saliente'::character varying, 'entrante'::character varying])::text[]))),
    CONSTRAINT ck_whatsapp_estado CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'enviado'::character varying, 'entregado'::character varying, 'leido'::character varying, 'fallido'::character varying, 'omitido'::character varying])::text[])))
);


--
-- Name: mensaje_whatsapp_id_mensaje_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mensaje_whatsapp_id_mensaje_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mensaje_whatsapp_id_mensaje_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mensaje_whatsapp_id_mensaje_seq OWNED BY public.mensaje_whatsapp.id_mensaje;


--
-- Name: metrica_diaria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metrica_diaria (
    fecha date NOT NULL,
    altas integer NOT NULL,
    bajas integer NOT NULL,
    descargas integer NOT NULL,
    usuarios_activos integer NOT NULL,
    usuarios_pago integer NOT NULL,
    mrr integer NOT NULL
);


--
-- Name: metrica_soporte_diaria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metrica_soporte_diaria (
    fecha date NOT NULL,
    tickets_creados integer NOT NULL,
    tickets_resueltos integer NOT NULL,
    t_primera_respuesta_prom numeric(9,2),
    t_resolucion_prom numeric(9,2),
    csat_promedio numeric(4,2)
);


--
-- Name: miembro_staff; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.miembro_staff (
    id_staff integer NOT NULL,
    codigo_rol character varying(40) NOT NULL,
    nombre_completo character varying(120) NOT NULL,
    email character varying(150) NOT NULL,
    estado character varying(30) NOT NULL,
    mfa_requerido boolean NOT NULL,
    mfa_habilitado boolean NOT NULL,
    fecha_activacion timestamp with time zone,
    ultimo_acceso timestamp with time zone,
    fecha_creacion timestamp with time zone NOT NULL,
    password_hash character varying(255),
    secreto_mfa character varying(64),
    intentos_fallidos integer NOT NULL,
    primer_intento_fallido timestamp with time zone,
    bloqueado_hasta timestamp with time zone,
    token_activacion_hash character varying(64),
    token_activacion_expira timestamp with time zone,
    CONSTRAINT ck_staff_estado CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'activo'::character varying, 'inactivo'::character varying])::text[])))
);


--
-- Name: miembro_staff_id_staff_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.miembro_staff_id_staff_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: miembro_staff_id_staff_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.miembro_staff_id_staff_seq OWNED BY public.miembro_staff.id_staff;


--
-- Name: paciente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.paciente (
    id_paciente integer NOT NULL,
    nombre character varying(120) NOT NULL,
    estado character varying(30) NOT NULL,
    fecha_alta timestamp with time zone NOT NULL
);


--
-- Name: paciente_id_paciente_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.paciente_id_paciente_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: paciente_id_paciente_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.paciente_id_paciente_seq OWNED BY public.paciente.id_paciente;


--
-- Name: parametro_sistema; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parametro_sistema (
    clave character varying(80) NOT NULL,
    descripcion character varying(300) NOT NULL,
    categoria character varying(40) NOT NULL,
    tipo_valor character varying(20) NOT NULL,
    valor text NOT NULL,
    version integer NOT NULL,
    nota_cambio character varying(500),
    fecha_actualizacion timestamp with time zone
);


--
-- Name: perfil_app; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.perfil_app (
    codigo_perfil character varying(40) NOT NULL,
    nombre character varying(120) NOT NULL
);


--
-- Name: perfil_cuidadora; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.perfil_cuidadora (
    id_perfil integer NOT NULL,
    id_usuario integer NOT NULL,
    id_staff_revisor integer,
    zona character varying(80) NOT NULL,
    especialidades character varying(400),
    idiomas character varying(200),
    certificaciones_verificadas integer NOT NULL,
    calificacion_promedio numeric(3,2),
    estado_publicacion character varying(30) NOT NULL,
    motivo_estado character varying(1000),
    fecha_envio timestamp with time zone NOT NULL,
    fecha_revision timestamp with time zone,
    CONSTRAINT ck_cuidadora_estado CHECK (((estado_publicacion)::text = ANY ((ARRAY['pendiente'::character varying, 'aprobado'::character varying, 'suspendido'::character varying])::text[])))
);


--
-- Name: perfil_cuidadora_id_perfil_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.perfil_cuidadora_id_perfil_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: perfil_cuidadora_id_perfil_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.perfil_cuidadora_id_perfil_seq OWNED BY public.perfil_cuidadora.id_perfil;


--
-- Name: permiso_rol; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.permiso_rol (
    modulo character varying(40) NOT NULL,
    codigo_rol character varying(40) NOT NULL,
    nivel_acceso character varying(30) NOT NULL,
    CONSTRAINT ck_permiso_nivel CHECK (((nivel_acceso)::text = ANY ((ARRAY['lectura'::character varying, 'escritura'::character varying])::text[])))
);


--
-- Name: plan; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plan (
    codigo_plan character varying(40) NOT NULL,
    nombre character varying(120) NOT NULL,
    precio integer NOT NULL,
    moneda character varying(3) NOT NULL,
    unidad_facturable character varying(20) NOT NULL,
    periodicidad character varying(20) NOT NULL,
    activo boolean NOT NULL,
    orden integer NOT NULL
);


--
-- Name: plan_funcionalidad; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plan_funcionalidad (
    codigo_plan character varying(40) NOT NULL,
    codigo_funcionalidad character varying(40) NOT NULL,
    fecha_asignacion timestamp with time zone NOT NULL
);


--
-- Name: proceso_critico; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proceso_critico (
    codigo_proceso character varying(40) NOT NULL,
    nombre character varying(120) NOT NULL,
    cadena character varying(300) NOT NULL,
    p95_segundos numeric(9,3) NOT NULL,
    exito_24h numeric(7,5) NOT NULL,
    estado character varying(30) NOT NULL,
    orden integer NOT NULL
);


--
-- Name: producto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.producto (
    id_producto integer NOT NULL,
    nombre character varying(160) NOT NULL,
    categoria character varying(60) NOT NULL,
    proveedor character varying(120) NOT NULL,
    precio_referencial integer,
    url_externa character varying(500) NOT NULL,
    url_imagen character varying(500),
    estado character varying(30) NOT NULL,
    fecha_creacion timestamp with time zone NOT NULL,
    CONSTRAINT ck_producto_estado CHECK (((estado)::text = ANY ((ARRAY['borrador'::character varying, 'publicado'::character varying, 'archivado'::character varying])::text[])))
);


--
-- Name: producto_id_producto_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.producto_id_producto_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: producto_id_producto_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.producto_id_producto_seq OWNED BY public.producto.id_producto;


--
-- Name: reembolso; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reembolso (
    id_reembolso integer NOT NULL,
    id_transaccion integer NOT NULL,
    id_staff_autorizador integer NOT NULL,
    monto integer NOT NULL,
    motivo character varying(300) NOT NULL,
    estado character varying(30) NOT NULL,
    fecha timestamp with time zone NOT NULL,
    id_externo_pasarela character varying(100),
    CONSTRAINT ck_reembolso_monto CHECK ((monto > 0))
);


--
-- Name: reembolso_id_reembolso_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reembolso_id_reembolso_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reembolso_id_reembolso_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reembolso_id_reembolso_seq OWNED BY public.reembolso.id_reembolso;


--
-- Name: registro_auditoria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.registro_auditoria (
    id_registro integer NOT NULL,
    id_staff_actor integer,
    fecha_hora timestamp with time zone NOT NULL,
    accion character varying(60) NOT NULL,
    tipo_entidad character varying(40) NOT NULL,
    id_entidad character varying(40),
    valor_anterior text,
    valor_nuevo text,
    ip character varying(45)
);


--
-- Name: registro_auditoria_id_registro_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.registro_auditoria_id_registro_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: registro_auditoria_id_registro_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.registro_auditoria_id_registro_seq OWNED BY public.registro_auditoria.id_registro;


--
-- Name: respuesta_ticket; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.respuesta_ticket (
    id_respuesta integer NOT NULL,
    id_ticket integer NOT NULL,
    id_staff_autor integer,
    cuerpo text NOT NULL,
    tipo_autor character varying(30) NOT NULL,
    es_interna boolean NOT NULL,
    fecha timestamp with time zone NOT NULL,
    CONSTRAINT ck_respuesta_autor CHECK (((tipo_autor)::text = ANY ((ARRAY['staff'::character varying, 'usuario'::character varying, 'sistema'::character varying])::text[])))
);


--
-- Name: respuesta_ticket_id_respuesta_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.respuesta_ticket_id_respuesta_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: respuesta_ticket_id_respuesta_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.respuesta_ticket_id_respuesta_seq OWNED BY public.respuesta_ticket.id_respuesta;


--
-- Name: rol_staff; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rol_staff (
    codigo_rol character varying(40) NOT NULL,
    nombre character varying(120) NOT NULL,
    descripcion character varying(400)
);


--
-- Name: sesion_staff; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sesion_staff (
    id_sesion integer NOT NULL,
    id_staff integer NOT NULL,
    refresh_token_hash character varying(64) NOT NULL,
    fecha_inicio timestamp with time zone NOT NULL,
    fecha_expiracion timestamp with time zone NOT NULL,
    fecha_revocacion timestamp with time zone,
    motivo_revocacion character varying(30),
    ip character varying(45)
);


--
-- Name: sesion_staff_id_sesion_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sesion_staff_id_sesion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sesion_staff_id_sesion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sesion_staff_id_sesion_seq OWNED BY public.sesion_staff.id_sesion;


--
-- Name: snapshot_embudo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snapshot_embudo (
    fecha date NOT NULL,
    descargas integer NOT NULL,
    cuentas_creadas integer NOT NULL,
    activos_30d integer NOT NULL,
    de_pago integer NOT NULL
);


--
-- Name: snapshot_plan; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snapshot_plan (
    fecha date NOT NULL,
    codigo_plan character varying(40) NOT NULL,
    usuarios integer NOT NULL,
    precio_congelado integer,
    mrr integer NOT NULL,
    churn_mensual numeric(7,5) NOT NULL
);


--
-- Name: suscripcion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.suscripcion (
    id_suscripcion integer NOT NULL,
    id_cuenta integer NOT NULL,
    codigo_plan character varying(40) NOT NULL,
    estado character varying(30) NOT NULL,
    fecha_inicio timestamp with time zone NOT NULL,
    inicio_periodo timestamp with time zone NOT NULL,
    fin_periodo timestamp with time zone NOT NULL,
    fecha_cancelacion timestamp with time zone,
    motivo_cancelacion character varying(300),
    id_externo_pasarela character varying(100),
    CONSTRAINT ck_suscripcion_estado CHECK (((estado)::text = ANY ((ARRAY['activa'::character varying, 'en_mora'::character varying, 'cancelada'::character varying, 'vencida'::character varying])::text[])))
);


--
-- Name: suscripcion_id_suscripcion_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.suscripcion_id_suscripcion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: suscripcion_id_suscripcion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.suscripcion_id_suscripcion_seq OWNED BY public.suscripcion.id_suscripcion;


--
-- Name: ticket; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ticket (
    id_ticket integer NOT NULL,
    numero integer,
    codigo_categoria character varying(40) NOT NULL,
    id_usuario integer,
    id_paciente integer,
    id_staff_asignado integer,
    asunto character varying(160) NOT NULL,
    descripcion text NOT NULL,
    prioridad character varying(30) NOT NULL,
    estado character varying(30) NOT NULL,
    canal character varying(30) NOT NULL,
    fecha_creacion timestamp with time zone NOT NULL,
    fecha_actualizacion timestamp with time zone NOT NULL,
    fecha_primera_respuesta timestamp with time zone,
    fecha_resolucion timestamp with time zone,
    fecha_cierre timestamp with time zone,
    nombre_solicitante character varying(120),
    email_solicitante character varying(150),
    CONSTRAINT ck_ticket_canal CHECK (((canal)::text = ANY ((ARRAY['app'::character varying, 'correo'::character varying, 'telefono'::character varying, 'consola'::character varying])::text[]))),
    CONSTRAINT ck_ticket_estado CHECK (((estado)::text = ANY ((ARRAY['abierto'::character varying, 'en_curso'::character varying, 'esperando_usuario'::character varying, 'resuelto'::character varying, 'cerrado'::character varying])::text[]))),
    CONSTRAINT ck_ticket_prioridad CHECK (((prioridad)::text = ANY ((ARRAY['baja'::character varying, 'media'::character varying, 'alta'::character varying, 'critica'::character varying])::text[])))
);


--
-- Name: ticket_id_ticket_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ticket_id_ticket_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ticket_id_ticket_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ticket_id_ticket_seq OWNED BY public.ticket.id_ticket;


--
-- Name: tipo_alerta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tipo_alerta (
    codigo_tipo character varying(40) NOT NULL,
    nombre character varying(120) NOT NULL,
    severidad_por_defecto character varying(30) NOT NULL
);


--
-- Name: transaccion_pago; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transaccion_pago (
    id_transaccion integer NOT NULL,
    id_suscripcion integer NOT NULL,
    monto integer NOT NULL,
    moneda character varying(3) NOT NULL,
    estado character varying(30) NOT NULL,
    fecha timestamp with time zone NOT NULL,
    medio_pago character varying(60),
    codigo_error character varying(60),
    id_externo_pasarela character varying(100),
    CONSTRAINT ck_transaccion_estado CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'aprobada'::character varying, 'rechazada'::character varying])::text[])))
);


--
-- Name: transaccion_pago_id_transaccion_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transaccion_pago_id_transaccion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transaccion_pago_id_transaccion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transaccion_pago_id_transaccion_seq OWNED BY public.transaccion_pago.id_transaccion;


--
-- Name: umbral_alerta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.umbral_alerta (
    signo_vital character varying(40) NOT NULL,
    nivel_semaforo character varying(20) NOT NULL,
    codigo_tipo character varying(40) NOT NULL,
    valor_minimo numeric(10,2) NOT NULL,
    valor_maximo numeric(10,2) NOT NULL,
    unidad character varying(20) NOT NULL,
    fecha_actualizacion timestamp with time zone,
    CONSTRAINT ck_umbral_nivel CHECK (((nivel_semaforo)::text = ANY ((ARRAY['verde'::character varying, 'amarillo'::character varying, 'rojo'::character varying])::text[]))),
    CONSTRAINT ck_umbral_rango CHECK ((valor_minimo <= valor_maximo))
);


--
-- Name: usuario_app; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario_app (
    id_usuario integer NOT NULL,
    nombre character varying(120) NOT NULL,
    email character varying(150) NOT NULL,
    estado_cuenta character varying(30) NOT NULL,
    fecha_registro timestamp with time zone NOT NULL,
    ultimo_acceso timestamp with time zone,
    telefono character varying(20),
    whatsapp_habilitado boolean DEFAULT false NOT NULL,
    whatsapp_verificado timestamp with time zone
);


--
-- Name: usuario_app_id_usuario_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuario_app_id_usuario_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_app_id_usuario_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuario_app_id_usuario_seq OWNED BY public.usuario_app.id_usuario;


--
-- Name: usuario_perfil; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario_perfil (
    id_usuario integer NOT NULL,
    codigo_perfil character varying(40) NOT NULL,
    fecha_asignacion timestamp with time zone NOT NULL
);


--
-- Name: verificacion_salud; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.verificacion_salud (
    codigo_componente character varying(40) NOT NULL,
    fecha_hora timestamp with time zone NOT NULL,
    exitosa boolean NOT NULL,
    latencia_ms integer,
    detalle character varying(300)
);


--
-- Name: version_legal; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.version_legal (
    id_version integer NOT NULL,
    id_staff_autor integer NOT NULL,
    tipo_documento character varying(20) NOT NULL,
    version_mayor integer NOT NULL,
    version_menor integer NOT NULL,
    contenido text NOT NULL,
    registro_cambios character varying(2000) NOT NULL,
    fecha_vigencia date NOT NULL,
    requiere_reaceptacion boolean NOT NULL,
    estado character varying(30) NOT NULL,
    fecha_publicacion timestamp with time zone,
    CONSTRAINT ck_legal_estado CHECK (((estado)::text = ANY ((ARRAY['borrador'::character varying, 'publicada'::character varying, 'reemplazada'::character varying])::text[]))),
    CONSTRAINT ck_legal_tipo CHECK (((tipo_documento)::text = ANY ((ARRAY['terminos'::character varying, 'privacidad'::character varying])::text[])))
);


--
-- Name: version_legal_id_version_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.version_legal_id_version_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: version_legal_id_version_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.version_legal_id_version_seq OWNED BY public.version_legal.id_version;


--
-- Name: alerta id_alerta; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerta ALTER COLUMN id_alerta SET DEFAULT nextval('public.alerta_id_alerta_seq'::regclass);


--
-- Name: contenido id_contenido; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contenido ALTER COLUMN id_contenido SET DEFAULT nextval('public.contenido_id_contenido_seq'::regclass);


--
-- Name: cuenta_cliente id_cuenta; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cuenta_cliente ALTER COLUMN id_cuenta SET DEFAULT nextval('public.cuenta_cliente_id_cuenta_seq'::regclass);


--
-- Name: elemento_moderacion id_elemento; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.elemento_moderacion ALTER COLUMN id_elemento SET DEFAULT nextval('public.elemento_moderacion_id_elemento_seq'::regclass);


--
-- Name: encuesta_satisfaccion id_encuesta; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encuesta_satisfaccion ALTER COLUMN id_encuesta SET DEFAULT nextval('public.encuesta_satisfaccion_id_encuesta_seq'::regclass);


--
-- Name: evento_pago id_evento; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento_pago ALTER COLUMN id_evento SET DEFAULT nextval('public.evento_pago_id_evento_seq'::regclass);


--
-- Name: incidente id_incidente; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidente ALTER COLUMN id_incidente SET DEFAULT nextval('public.incidente_id_incidente_seq'::regclass);


--
-- Name: mensaje_whatsapp id_mensaje; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensaje_whatsapp ALTER COLUMN id_mensaje SET DEFAULT nextval('public.mensaje_whatsapp_id_mensaje_seq'::regclass);


--
-- Name: miembro_staff id_staff; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.miembro_staff ALTER COLUMN id_staff SET DEFAULT nextval('public.miembro_staff_id_staff_seq'::regclass);


--
-- Name: paciente id_paciente; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paciente ALTER COLUMN id_paciente SET DEFAULT nextval('public.paciente_id_paciente_seq'::regclass);


--
-- Name: perfil_cuidadora id_perfil; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_cuidadora ALTER COLUMN id_perfil SET DEFAULT nextval('public.perfil_cuidadora_id_perfil_seq'::regclass);


--
-- Name: producto id_producto; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto ALTER COLUMN id_producto SET DEFAULT nextval('public.producto_id_producto_seq'::regclass);


--
-- Name: reembolso id_reembolso; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reembolso ALTER COLUMN id_reembolso SET DEFAULT nextval('public.reembolso_id_reembolso_seq'::regclass);


--
-- Name: registro_auditoria id_registro; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro_auditoria ALTER COLUMN id_registro SET DEFAULT nextval('public.registro_auditoria_id_registro_seq'::regclass);


--
-- Name: respuesta_ticket id_respuesta; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respuesta_ticket ALTER COLUMN id_respuesta SET DEFAULT nextval('public.respuesta_ticket_id_respuesta_seq'::regclass);


--
-- Name: sesion_staff id_sesion; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion_staff ALTER COLUMN id_sesion SET DEFAULT nextval('public.sesion_staff_id_sesion_seq'::regclass);


--
-- Name: suscripcion id_suscripcion; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suscripcion ALTER COLUMN id_suscripcion SET DEFAULT nextval('public.suscripcion_id_suscripcion_seq'::regclass);


--
-- Name: ticket id_ticket; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket ALTER COLUMN id_ticket SET DEFAULT nextval('public.ticket_id_ticket_seq'::regclass);


--
-- Name: transaccion_pago id_transaccion; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaccion_pago ALTER COLUMN id_transaccion SET DEFAULT nextval('public.transaccion_pago_id_transaccion_seq'::regclass);


--
-- Name: usuario_app id_usuario; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_app ALTER COLUMN id_usuario SET DEFAULT nextval('public.usuario_app_id_usuario_seq'::regclass);


--
-- Name: version_legal id_version; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version_legal ALTER COLUMN id_version SET DEFAULT nextval('public.version_legal_id_version_seq'::regclass);


--
-- Name: actividad_perfil actividad_perfil_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_perfil
    ADD CONSTRAINT actividad_perfil_pkey PRIMARY KEY (ventana_dias, codigo_perfil);


--
-- Name: adopcion_funcionalidad adopcion_funcionalidad_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adopcion_funcionalidad
    ADD CONSTRAINT adopcion_funcionalidad_pkey PRIMARY KEY (ventana_dias, codigo_funcionalidad, codigo_perfil);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: alerta alerta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerta
    ADD CONSTRAINT alerta_pkey PRIMARY KEY (id_alerta);


--
-- Name: categoria_ticket categoria_ticket_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria_ticket
    ADD CONSTRAINT categoria_ticket_pkey PRIMARY KEY (codigo_categoria);


--
-- Name: componente componente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.componente
    ADD CONSTRAINT componente_pkey PRIMARY KEY (codigo_componente);


--
-- Name: componente_proceso componente_proceso_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.componente_proceso
    ADD CONSTRAINT componente_proceso_pkey PRIMARY KEY (codigo_componente, codigo_proceso);


--
-- Name: contenido contenido_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contenido
    ADD CONSTRAINT contenido_pkey PRIMARY KEY (id_contenido);


--
-- Name: cuenta_cliente cuenta_cliente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cuenta_cliente
    ADD CONSTRAINT cuenta_cliente_pkey PRIMARY KEY (id_cuenta);


--
-- Name: elemento_moderacion elemento_moderacion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.elemento_moderacion
    ADD CONSTRAINT elemento_moderacion_pkey PRIMARY KEY (id_elemento);


--
-- Name: encuesta_satisfaccion encuesta_satisfaccion_id_ticket_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encuesta_satisfaccion
    ADD CONSTRAINT encuesta_satisfaccion_id_ticket_key UNIQUE (id_ticket);


--
-- Name: encuesta_satisfaccion encuesta_satisfaccion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encuesta_satisfaccion
    ADD CONSTRAINT encuesta_satisfaccion_pkey PRIMARY KEY (id_encuesta);


--
-- Name: evento_pago evento_pago_id_externo_evento_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento_pago
    ADD CONSTRAINT evento_pago_id_externo_evento_key UNIQUE (id_externo_evento);


--
-- Name: evento_pago evento_pago_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento_pago
    ADD CONSTRAINT evento_pago_pkey PRIMARY KEY (id_evento);


--
-- Name: funcionalidad funcionalidad_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcionalidad
    ADD CONSTRAINT funcionalidad_pkey PRIMARY KEY (codigo_funcionalidad);


--
-- Name: incidente incidente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidente
    ADD CONSTRAINT incidente_pkey PRIMARY KEY (id_incidente);


--
-- Name: membresia_circulo membresia_circulo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.membresia_circulo
    ADD CONSTRAINT membresia_circulo_pkey PRIMARY KEY (id_usuario, id_paciente);


--
-- Name: mensaje_whatsapp mensaje_whatsapp_id_mensaje_proveedor_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensaje_whatsapp
    ADD CONSTRAINT mensaje_whatsapp_id_mensaje_proveedor_key UNIQUE (id_mensaje_proveedor);


--
-- Name: mensaje_whatsapp mensaje_whatsapp_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensaje_whatsapp
    ADD CONSTRAINT mensaje_whatsapp_pkey PRIMARY KEY (id_mensaje);


--
-- Name: metrica_diaria metrica_diaria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metrica_diaria
    ADD CONSTRAINT metrica_diaria_pkey PRIMARY KEY (fecha);


--
-- Name: metrica_soporte_diaria metrica_soporte_diaria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metrica_soporte_diaria
    ADD CONSTRAINT metrica_soporte_diaria_pkey PRIMARY KEY (fecha);


--
-- Name: miembro_staff miembro_staff_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.miembro_staff
    ADD CONSTRAINT miembro_staff_pkey PRIMARY KEY (id_staff);


--
-- Name: paciente paciente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paciente
    ADD CONSTRAINT paciente_pkey PRIMARY KEY (id_paciente);


--
-- Name: parametro_sistema parametro_sistema_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parametro_sistema
    ADD CONSTRAINT parametro_sistema_pkey PRIMARY KEY (clave);


--
-- Name: perfil_app perfil_app_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_app
    ADD CONSTRAINT perfil_app_pkey PRIMARY KEY (codigo_perfil);


--
-- Name: perfil_cuidadora perfil_cuidadora_id_usuario_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_cuidadora
    ADD CONSTRAINT perfil_cuidadora_id_usuario_key UNIQUE (id_usuario);


--
-- Name: perfil_cuidadora perfil_cuidadora_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_cuidadora
    ADD CONSTRAINT perfil_cuidadora_pkey PRIMARY KEY (id_perfil);


--
-- Name: permiso_rol permiso_rol_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permiso_rol
    ADD CONSTRAINT permiso_rol_pkey PRIMARY KEY (modulo, codigo_rol);


--
-- Name: plan_funcionalidad plan_funcionalidad_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_funcionalidad
    ADD CONSTRAINT plan_funcionalidad_pkey PRIMARY KEY (codigo_plan, codigo_funcionalidad);


--
-- Name: plan plan_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan
    ADD CONSTRAINT plan_pkey PRIMARY KEY (codigo_plan);


--
-- Name: proceso_critico proceso_critico_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proceso_critico
    ADD CONSTRAINT proceso_critico_pkey PRIMARY KEY (codigo_proceso);


--
-- Name: producto producto_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto
    ADD CONSTRAINT producto_pkey PRIMARY KEY (id_producto);


--
-- Name: reembolso reembolso_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reembolso
    ADD CONSTRAINT reembolso_pkey PRIMARY KEY (id_reembolso);


--
-- Name: registro_auditoria registro_auditoria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro_auditoria
    ADD CONSTRAINT registro_auditoria_pkey PRIMARY KEY (id_registro);


--
-- Name: respuesta_ticket respuesta_ticket_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respuesta_ticket
    ADD CONSTRAINT respuesta_ticket_pkey PRIMARY KEY (id_respuesta);


--
-- Name: rol_staff rol_staff_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rol_staff
    ADD CONSTRAINT rol_staff_pkey PRIMARY KEY (codigo_rol);


--
-- Name: sesion_staff sesion_staff_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion_staff
    ADD CONSTRAINT sesion_staff_pkey PRIMARY KEY (id_sesion);


--
-- Name: sesion_staff sesion_staff_refresh_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion_staff
    ADD CONSTRAINT sesion_staff_refresh_token_hash_key UNIQUE (refresh_token_hash);


--
-- Name: snapshot_embudo snapshot_embudo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.snapshot_embudo
    ADD CONSTRAINT snapshot_embudo_pkey PRIMARY KEY (fecha);


--
-- Name: snapshot_plan snapshot_plan_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.snapshot_plan
    ADD CONSTRAINT snapshot_plan_pkey PRIMARY KEY (fecha, codigo_plan);


--
-- Name: suscripcion suscripcion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suscripcion
    ADD CONSTRAINT suscripcion_pkey PRIMARY KEY (id_suscripcion);


--
-- Name: ticket ticket_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_pkey PRIMARY KEY (id_ticket);


--
-- Name: tipo_alerta tipo_alerta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipo_alerta
    ADD CONSTRAINT tipo_alerta_pkey PRIMARY KEY (codigo_tipo);


--
-- Name: transaccion_pago transaccion_pago_id_externo_pasarela_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaccion_pago
    ADD CONSTRAINT transaccion_pago_id_externo_pasarela_key UNIQUE (id_externo_pasarela);


--
-- Name: transaccion_pago transaccion_pago_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaccion_pago
    ADD CONSTRAINT transaccion_pago_pkey PRIMARY KEY (id_transaccion);


--
-- Name: umbral_alerta umbral_alerta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.umbral_alerta
    ADD CONSTRAINT umbral_alerta_pkey PRIMARY KEY (signo_vital, nivel_semaforo);


--
-- Name: version_legal uq_version_legal; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version_legal
    ADD CONSTRAINT uq_version_legal UNIQUE (tipo_documento, version_mayor, version_menor);


--
-- Name: usuario_app usuario_app_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_app
    ADD CONSTRAINT usuario_app_pkey PRIMARY KEY (id_usuario);


--
-- Name: usuario_perfil usuario_perfil_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_perfil
    ADD CONSTRAINT usuario_perfil_pkey PRIMARY KEY (id_usuario, codigo_perfil);


--
-- Name: verificacion_salud verificacion_salud_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verificacion_salud
    ADD CONSTRAINT verificacion_salud_pkey PRIMARY KEY (codigo_componente, fecha_hora);


--
-- Name: version_legal version_legal_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version_legal
    ADD CONSTRAINT version_legal_pkey PRIMARY KEY (id_version);


--
-- Name: ix_alerta_fecha_emision; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_alerta_fecha_emision ON public.alerta USING btree (fecha_emision);


--
-- Name: ix_alerta_id_paciente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_alerta_id_paciente ON public.alerta USING btree (id_paciente);


--
-- Name: ix_cuenta_cliente_id_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cuenta_cliente_id_usuario ON public.cuenta_cliente USING btree (id_usuario);


--
-- Name: ix_elemento_moderacion_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_elemento_moderacion_estado ON public.elemento_moderacion USING btree (estado);


--
-- Name: ix_elemento_moderacion_id_usuario_autor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_elemento_moderacion_id_usuario_autor ON public.elemento_moderacion USING btree (id_usuario_autor);


--
-- Name: ix_incidente_fecha_inicio; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incidente_fecha_inicio ON public.incidente USING btree (fecha_inicio);


--
-- Name: ix_mensaje_whatsapp_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mensaje_whatsapp_estado ON public.mensaje_whatsapp USING btree (estado);


--
-- Name: ix_mensaje_whatsapp_fecha_creacion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mensaje_whatsapp_fecha_creacion ON public.mensaje_whatsapp USING btree (fecha_creacion);


--
-- Name: ix_mensaje_whatsapp_id_alerta; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mensaje_whatsapp_id_alerta ON public.mensaje_whatsapp USING btree (id_alerta);


--
-- Name: ix_mensaje_whatsapp_id_paciente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mensaje_whatsapp_id_paciente ON public.mensaje_whatsapp USING btree (id_paciente);


--
-- Name: ix_mensaje_whatsapp_id_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mensaje_whatsapp_id_usuario ON public.mensaje_whatsapp USING btree (id_usuario);


--
-- Name: ix_miembro_staff_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_miembro_staff_email ON public.miembro_staff USING btree (email);


--
-- Name: ix_miembro_staff_token_activacion_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_miembro_staff_token_activacion_hash ON public.miembro_staff USING btree (token_activacion_hash);


--
-- Name: ix_reembolso_id_transaccion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reembolso_id_transaccion ON public.reembolso USING btree (id_transaccion);


--
-- Name: ix_registro_auditoria_accion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_registro_auditoria_accion ON public.registro_auditoria USING btree (accion);


--
-- Name: ix_registro_auditoria_fecha_hora; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_registro_auditoria_fecha_hora ON public.registro_auditoria USING btree (fecha_hora);


--
-- Name: ix_registro_auditoria_id_staff_actor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_registro_auditoria_id_staff_actor ON public.registro_auditoria USING btree (id_staff_actor);


--
-- Name: ix_respuesta_ticket_id_ticket; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_respuesta_ticket_id_ticket ON public.respuesta_ticket USING btree (id_ticket);


--
-- Name: ix_sesion_staff_id_staff; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sesion_staff_id_staff ON public.sesion_staff USING btree (id_staff);


--
-- Name: ix_suscripcion_id_cuenta; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_suscripcion_id_cuenta ON public.suscripcion USING btree (id_cuenta);


--
-- Name: ix_ticket_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ticket_estado ON public.ticket USING btree (estado);


--
-- Name: ix_ticket_fecha_creacion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ticket_fecha_creacion ON public.ticket USING btree (fecha_creacion);


--
-- Name: ix_ticket_id_staff_asignado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ticket_id_staff_asignado ON public.ticket USING btree (id_staff_asignado);


--
-- Name: ix_ticket_id_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ticket_id_usuario ON public.ticket USING btree (id_usuario);


--
-- Name: ix_ticket_numero; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_ticket_numero ON public.ticket USING btree (numero);


--
-- Name: ix_transaccion_pago_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transaccion_pago_fecha ON public.transaccion_pago USING btree (fecha);


--
-- Name: ix_transaccion_pago_id_suscripcion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transaccion_pago_id_suscripcion ON public.transaccion_pago USING btree (id_suscripcion);


--
-- Name: ix_usuario_app_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_usuario_app_email ON public.usuario_app USING btree (email);


--
-- Name: actividad_perfil actividad_perfil_codigo_perfil_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_perfil
    ADD CONSTRAINT actividad_perfil_codigo_perfil_fkey FOREIGN KEY (codigo_perfil) REFERENCES public.perfil_app(codigo_perfil);


--
-- Name: adopcion_funcionalidad adopcion_funcionalidad_codigo_funcionalidad_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adopcion_funcionalidad
    ADD CONSTRAINT adopcion_funcionalidad_codigo_funcionalidad_fkey FOREIGN KEY (codigo_funcionalidad) REFERENCES public.funcionalidad(codigo_funcionalidad);


--
-- Name: adopcion_funcionalidad adopcion_funcionalidad_codigo_perfil_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adopcion_funcionalidad
    ADD CONSTRAINT adopcion_funcionalidad_codigo_perfil_fkey FOREIGN KEY (codigo_perfil) REFERENCES public.perfil_app(codigo_perfil);


--
-- Name: alerta alerta_codigo_tipo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerta
    ADD CONSTRAINT alerta_codigo_tipo_fkey FOREIGN KEY (codigo_tipo) REFERENCES public.tipo_alerta(codigo_tipo);


--
-- Name: alerta alerta_id_paciente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerta
    ADD CONSTRAINT alerta_id_paciente_fkey FOREIGN KEY (id_paciente) REFERENCES public.paciente(id_paciente);


--
-- Name: componente_proceso componente_proceso_codigo_componente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.componente_proceso
    ADD CONSTRAINT componente_proceso_codigo_componente_fkey FOREIGN KEY (codigo_componente) REFERENCES public.componente(codigo_componente);


--
-- Name: componente_proceso componente_proceso_codigo_proceso_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.componente_proceso
    ADD CONSTRAINT componente_proceso_codigo_proceso_fkey FOREIGN KEY (codigo_proceso) REFERENCES public.proceso_critico(codigo_proceso);


--
-- Name: cuenta_cliente cuenta_cliente_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cuenta_cliente
    ADD CONSTRAINT cuenta_cliente_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario_app(id_usuario);


--
-- Name: elemento_moderacion elemento_moderacion_id_staff_decisor_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.elemento_moderacion
    ADD CONSTRAINT elemento_moderacion_id_staff_decisor_fkey FOREIGN KEY (id_staff_decisor) REFERENCES public.miembro_staff(id_staff);


--
-- Name: elemento_moderacion elemento_moderacion_id_usuario_autor_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.elemento_moderacion
    ADD CONSTRAINT elemento_moderacion_id_usuario_autor_fkey FOREIGN KEY (id_usuario_autor) REFERENCES public.usuario_app(id_usuario);


--
-- Name: elemento_moderacion elemento_moderacion_id_usuario_reportante_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.elemento_moderacion
    ADD CONSTRAINT elemento_moderacion_id_usuario_reportante_fkey FOREIGN KEY (id_usuario_reportante) REFERENCES public.usuario_app(id_usuario);


--
-- Name: encuesta_satisfaccion encuesta_satisfaccion_id_ticket_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encuesta_satisfaccion
    ADD CONSTRAINT encuesta_satisfaccion_id_ticket_fkey FOREIGN KEY (id_ticket) REFERENCES public.ticket(id_ticket);


--
-- Name: evento_pago evento_pago_id_transaccion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento_pago
    ADD CONSTRAINT evento_pago_id_transaccion_fkey FOREIGN KEY (id_transaccion) REFERENCES public.transaccion_pago(id_transaccion);


--
-- Name: incidente incidente_codigo_componente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidente
    ADD CONSTRAINT incidente_codigo_componente_fkey FOREIGN KEY (codigo_componente) REFERENCES public.componente(codigo_componente);


--
-- Name: incidente incidente_id_staff_responsable_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidente
    ADD CONSTRAINT incidente_id_staff_responsable_fkey FOREIGN KEY (id_staff_responsable) REFERENCES public.miembro_staff(id_staff);


--
-- Name: membresia_circulo membresia_circulo_id_paciente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.membresia_circulo
    ADD CONSTRAINT membresia_circulo_id_paciente_fkey FOREIGN KEY (id_paciente) REFERENCES public.paciente(id_paciente);


--
-- Name: membresia_circulo membresia_circulo_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.membresia_circulo
    ADD CONSTRAINT membresia_circulo_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario_app(id_usuario);


--
-- Name: mensaje_whatsapp mensaje_whatsapp_id_alerta_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensaje_whatsapp
    ADD CONSTRAINT mensaje_whatsapp_id_alerta_fkey FOREIGN KEY (id_alerta) REFERENCES public.alerta(id_alerta);


--
-- Name: mensaje_whatsapp mensaje_whatsapp_id_paciente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensaje_whatsapp
    ADD CONSTRAINT mensaje_whatsapp_id_paciente_fkey FOREIGN KEY (id_paciente) REFERENCES public.paciente(id_paciente);


--
-- Name: mensaje_whatsapp mensaje_whatsapp_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensaje_whatsapp
    ADD CONSTRAINT mensaje_whatsapp_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario_app(id_usuario);


--
-- Name: miembro_staff miembro_staff_codigo_rol_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.miembro_staff
    ADD CONSTRAINT miembro_staff_codigo_rol_fkey FOREIGN KEY (codigo_rol) REFERENCES public.rol_staff(codigo_rol);


--
-- Name: perfil_cuidadora perfil_cuidadora_id_staff_revisor_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_cuidadora
    ADD CONSTRAINT perfil_cuidadora_id_staff_revisor_fkey FOREIGN KEY (id_staff_revisor) REFERENCES public.miembro_staff(id_staff);


--
-- Name: perfil_cuidadora perfil_cuidadora_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfil_cuidadora
    ADD CONSTRAINT perfil_cuidadora_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario_app(id_usuario);


--
-- Name: permiso_rol permiso_rol_codigo_rol_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permiso_rol
    ADD CONSTRAINT permiso_rol_codigo_rol_fkey FOREIGN KEY (codigo_rol) REFERENCES public.rol_staff(codigo_rol);


--
-- Name: plan_funcionalidad plan_funcionalidad_codigo_funcionalidad_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_funcionalidad
    ADD CONSTRAINT plan_funcionalidad_codigo_funcionalidad_fkey FOREIGN KEY (codigo_funcionalidad) REFERENCES public.funcionalidad(codigo_funcionalidad);


--
-- Name: plan_funcionalidad plan_funcionalidad_codigo_plan_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_funcionalidad
    ADD CONSTRAINT plan_funcionalidad_codigo_plan_fkey FOREIGN KEY (codigo_plan) REFERENCES public.plan(codigo_plan);


--
-- Name: reembolso reembolso_id_staff_autorizador_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reembolso
    ADD CONSTRAINT reembolso_id_staff_autorizador_fkey FOREIGN KEY (id_staff_autorizador) REFERENCES public.miembro_staff(id_staff);


--
-- Name: reembolso reembolso_id_transaccion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reembolso
    ADD CONSTRAINT reembolso_id_transaccion_fkey FOREIGN KEY (id_transaccion) REFERENCES public.transaccion_pago(id_transaccion);


--
-- Name: registro_auditoria registro_auditoria_id_staff_actor_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro_auditoria
    ADD CONSTRAINT registro_auditoria_id_staff_actor_fkey FOREIGN KEY (id_staff_actor) REFERENCES public.miembro_staff(id_staff);


--
-- Name: respuesta_ticket respuesta_ticket_id_staff_autor_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respuesta_ticket
    ADD CONSTRAINT respuesta_ticket_id_staff_autor_fkey FOREIGN KEY (id_staff_autor) REFERENCES public.miembro_staff(id_staff);


--
-- Name: respuesta_ticket respuesta_ticket_id_ticket_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respuesta_ticket
    ADD CONSTRAINT respuesta_ticket_id_ticket_fkey FOREIGN KEY (id_ticket) REFERENCES public.ticket(id_ticket);


--
-- Name: sesion_staff sesion_staff_id_staff_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion_staff
    ADD CONSTRAINT sesion_staff_id_staff_fkey FOREIGN KEY (id_staff) REFERENCES public.miembro_staff(id_staff);


--
-- Name: snapshot_plan snapshot_plan_codigo_plan_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.snapshot_plan
    ADD CONSTRAINT snapshot_plan_codigo_plan_fkey FOREIGN KEY (codigo_plan) REFERENCES public.plan(codigo_plan);


--
-- Name: suscripcion suscripcion_codigo_plan_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suscripcion
    ADD CONSTRAINT suscripcion_codigo_plan_fkey FOREIGN KEY (codigo_plan) REFERENCES public.plan(codigo_plan);


--
-- Name: suscripcion suscripcion_id_cuenta_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suscripcion
    ADD CONSTRAINT suscripcion_id_cuenta_fkey FOREIGN KEY (id_cuenta) REFERENCES public.cuenta_cliente(id_cuenta);


--
-- Name: ticket ticket_codigo_categoria_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_codigo_categoria_fkey FOREIGN KEY (codigo_categoria) REFERENCES public.categoria_ticket(codigo_categoria);


--
-- Name: ticket ticket_id_paciente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_id_paciente_fkey FOREIGN KEY (id_paciente) REFERENCES public.paciente(id_paciente);


--
-- Name: ticket ticket_id_staff_asignado_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_id_staff_asignado_fkey FOREIGN KEY (id_staff_asignado) REFERENCES public.miembro_staff(id_staff);


--
-- Name: ticket ticket_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket
    ADD CONSTRAINT ticket_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario_app(id_usuario);


--
-- Name: transaccion_pago transaccion_pago_id_suscripcion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaccion_pago
    ADD CONSTRAINT transaccion_pago_id_suscripcion_fkey FOREIGN KEY (id_suscripcion) REFERENCES public.suscripcion(id_suscripcion);


--
-- Name: umbral_alerta umbral_alerta_codigo_tipo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.umbral_alerta
    ADD CONSTRAINT umbral_alerta_codigo_tipo_fkey FOREIGN KEY (codigo_tipo) REFERENCES public.tipo_alerta(codigo_tipo);


--
-- Name: usuario_perfil usuario_perfil_codigo_perfil_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_perfil
    ADD CONSTRAINT usuario_perfil_codigo_perfil_fkey FOREIGN KEY (codigo_perfil) REFERENCES public.perfil_app(codigo_perfil);


--
-- Name: usuario_perfil usuario_perfil_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_perfil
    ADD CONSTRAINT usuario_perfil_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario_app(id_usuario);


--
-- Name: verificacion_salud verificacion_salud_codigo_componente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verificacion_salud
    ADD CONSTRAINT verificacion_salud_codigo_componente_fkey FOREIGN KEY (codigo_componente) REFERENCES public.componente(codigo_componente);


--
-- Name: version_legal version_legal_id_staff_autor_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version_legal
    ADD CONSTRAINT version_legal_id_staff_autor_fkey FOREIGN KEY (id_staff_autor) REFERENCES public.miembro_staff(id_staff);


--
-- PostgreSQL database dump complete
--

\unrestrict oVkzSr08YtS8AzxpFeJOKOQWVEoIE1agkdmZh9tkkQS9FrfpJ7Q7ZlcpLvxDbmo

