"""«Mis solicitudes» en el portal: respuestas del usuario, avisos de soporte con enlace

Revision ID: 0006_solicitudes
Revises: 0005_correo
Create Date: 2026-11-10 23:45:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0006_solicitudes'
down_revision: Union[str, None] = '0005_correo'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('notificacion_app', sa.Column('enlace', sa.String(length=200), nullable=True))
    op.add_column('respuesta_ticket', sa.Column('id_usuario_autor', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_respuesta_usuario_autor', 'respuesta_ticket', 'usuario_app',
                          ['id_usuario_autor'], ['id_usuario'])
    op.drop_constraint('ck_notificacion_tipo', 'notificacion_app', type_='check')
    op.create_check_constraint('ck_notificacion_tipo', 'notificacion_app',
                               "tipo IN ('estado_riesgoso', 'alerta_salud', 'pago', 'plan', 'sistema', 'soporte')")


def downgrade() -> None:
    op.execute("DELETE FROM notificacion_app WHERE tipo = 'soporte'")
    op.drop_constraint('ck_notificacion_tipo', 'notificacion_app', type_='check')
    op.create_check_constraint('ck_notificacion_tipo', 'notificacion_app',
                               "tipo IN ('estado_riesgoso', 'alerta_salud', 'pago', 'plan', 'sistema')")
    op.drop_constraint('fk_respuesta_usuario_autor', 'respuesta_ticket', type_='foreignkey')
    op.drop_column('respuesta_ticket', 'id_usuario_autor')
    op.drop_column('notificacion_app', 'enlace')
