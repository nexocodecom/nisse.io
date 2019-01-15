"""add_event_id

Revision ID: 3bb17e0138f8
Revises: 5c77f4799359
Create Date: 2019-01-14 15:23:58.696983

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '3bb17e0138f8'
down_revision = '5c77f4799359'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('vacations', sa.Column('event_id', sa.String(length=255), nullable=True))
    op.drop_column('vacations', 'reason')


def downgrade():
    op.add_column('vacations', sa.Column('reason', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
    op.drop_column('vacations', 'event_id')
