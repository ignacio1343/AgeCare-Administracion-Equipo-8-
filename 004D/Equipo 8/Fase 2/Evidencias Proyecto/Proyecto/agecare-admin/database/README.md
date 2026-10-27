# Base de datos · AgeCare Administración

PostgreSQL 16 · 43 tablas (más `alembic_version`) · versión del esquema `0003_whatsapp` (v0.5.0).
Los datos son ficticios (datos de demostración); no contienen información real de pacientes.

## Contenido

| Archivo | Qué es |
| --- | --- |
| `01_esquema_agecare_admin_postgresql.sql` | Esquema completo: tablas, claves primarias y foráneas, restricciones CHECK y UNIQUE, índices y secuencias. |
| `02_datos_demo_agecare_admin.sql` | Datos de demostración como sentencias INSERT (staff, usuarios, tickets, métricas, planes, etc.). |
| `agecare_admin_completo.dump` | Respaldo completo (esquema + datos) en formato `pg_dump -Fc`. |
| `03_Diccionario_de_datos_AgeCare_Admin.xlsx` | Diccionario: 43 tablas con su módulo y descripción, 333 columnas con tipo, nulos y claves, y 27 restricciones CHECK. |

## Cómo restaurarla

Opción 1, con los scripts SQL:

```bash
createdb -U postgres agecare_admin
psql -U postgres -d agecare_admin -f 01_esquema_agecare_admin_postgresql.sql
psql -U postgres -d agecare_admin -f 02_datos_demo_agecare_admin.sql
```

Opción 2, con el respaldo completo:

```bash
createdb -U postgres agecare_admin
pg_restore -U postgres -d agecare_admin --no-owner agecare_admin_completo.dump
```

En Neon se usa la connection string en lugar de `-d agecare_admin`, por ejemplo
`pg_restore -d "postgresql://usuario:clave@ep-….neon.tech/neondb?sslmode=require" --no-owner agecare_admin_completo.dump`.

Ambas opciones se probaron sobre bases vacías y dejan 46 tickets, 6.480 verificaciones de salud, 51 avisos por WhatsApp y el esquema en la versión `0003_whatsapp`.
La aplicación también puede crear la base sola: `alembic upgrade head` y `python -m scripts.seed`.
