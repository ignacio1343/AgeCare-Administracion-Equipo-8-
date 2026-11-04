"""código de registro por correo (Brevo) en vez de SMS: verificacion_sms → verificacion_correo

Revision ID: 0005_correo
Revises: 0004_portal
Create Date: 2026-11-04 03:10:00

"""
from typing import Sequence, Union

from alembic import op

revision: str = '0005_correo'
down_revision: Union[str, None] = '0004_portal'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table('verificacion_sms', 'verificacion_correo')
    op.execute("ALTER INDEX ix_verificacion_sms_rut RENAME TO ix_verificacion_correo_rut")
    op.execute("ALTER TABLE verificacion_correo RENAME CONSTRAINT verificacion_sms_pkey TO verificacion_correo_pkey")
    op.execute("ALTER TABLE verificacion_correo RENAME CONSTRAINT verificacion_sms_token_hash_key "
               "TO verificacion_correo_token_hash_key")
    op.execute("ALTER TABLE verificacion_correo RENAME CONSTRAINT ck_sms_estado TO ck_verificacion_estado")
    op.execute("ALTER SEQUENCE verificacion_sms_id_verificacion_seq RENAME TO verificacion_correo_id_verificacion_seq")
    # Los registros a medio confirmar con el código por SMS ya no se pueden completar
    op.execute("UPDATE verificacion_correo SET estado = 'expirada' WHERE estado = 'pendiente'")


def downgrade() -> None:
    op.execute("ALTER SEQUENCE verificacion_correo_id_verificacion_seq RENAME TO verificacion_sms_id_verificacion_seq")
    op.execute("ALTER TABLE verificacion_correo RENAME CONSTRAINT ck_verificacion_estado TO ck_sms_estado")
    op.execute("ALTER TABLE verificacion_correo RENAME CONSTRAINT verificacion_correo_token_hash_key "
               "TO verificacion_sms_token_hash_key")
    op.execute("ALTER TABLE verificacion_correo RENAME CONSTRAINT verificacion_correo_pkey TO verificacion_sms_pkey")
    op.execute("ALTER INDEX ix_verificacion_correo_rut RENAME TO ix_verificacion_sms_rut")
    op.rename_table('verificacion_correo', 'verificacion_sms')
