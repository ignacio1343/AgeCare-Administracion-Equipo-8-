# AgeCare-Administracion-Equipo-8-
Desarrollo de proyecto Capstone del equipo 8 (AgeCare Administracion), Duoc uc Sede San andrés

___________________________________________________________________________________________________________________________________

Integrantes del equipo: Alvaro Faundez - Paolo Salamanca - Ignacio Bustos
Nombre del proyecto: AgeCare Administracion
Descripción: Es una Single Page Application (SPA) y API REST que funciona como el núcleo operativo
de la plataforma de salud AgeCare. El sistema centraliza la gestión de cuentas, la curación de contenidos
de entretenimiento, la moderación del marketplace y la monitorización de alertas de signos vitales.
Además, incluye un panel analítico para la gestión comercial y control de adopción del modelo freemium.

El uso de esta plataforma es exclusivo para el equipo interno de la empresa.
Está diseñada para operar bajo un estricto modelo de control de acceso por roles,
dirigido a: Administradores y Gerencia, Ejecutivos de Soporte, Editores de Contenido, Operadores de salud.

Resuelve la falta de visibilidad y control centralizado en la operación de la startup.
Sin este panel, el equipo humano no tendría las herramientas para dar soporte a los usuarios ni tomar decisiones.

Tecnologías utilizadas: 

  Frontend: React, Vite, TypeScript.
  Backend: Python, FastAPI.
  Base de Datos: PostgreSQL.
  Infraestructura y Nube (Cloud): Microsoft Azure Static Web Apps (con despliegue continuo automático).
  Seguridad: Autenticación JWT y Azure Key Vault para la gestión de secretos.
  Observabilidad: Application Insights para visualización de métricas de rendimiento y errores.

Metodología de trabajo del equipo: Metodologia Agil Scrum, la planificación inicial exige el cierre definitivo de
la Carta Gantt de manera estricta antes de la definición de la Matriz RACI y el Cuadro de Costos, para garantizar
la integridad temporal y financiera del proyecto.

Arquitectura de la solución: Arquitectura cliente-servidor donde el frontend (React) consume endpoints administrativos
dedicados (FastAPI) expuestos bajo la ruta /admin/v1. La persistencia se maneja en PostgreSQL con un modelo multi-rol (RBAC).
Todo el sistema está containerizado con Docker para asegurar portabilidad entre el entorno local y la nube.


_______________________________________________ Proximo a desarrollar ____________________________________________________________

Instrucciones para ejecutar el proyecto localmente

