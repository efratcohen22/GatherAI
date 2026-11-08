"""Deny direct client access on PostgreSQL. The API uses a privileged server-side role.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
from sqlalchemy import inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _tables() -> list[str]:
    return [t for t in inspect(op.get_bind()).get_table_names() if t != "alembic_version"]


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in _tables():
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in _tables():
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
