"""add_channel_id_to_food_order

Revision ID: 8b2c2a2f361f
Revises: 7dcb49b666a6
Create Date: 2019-12-20 19:13:20.462490

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b2c2a2f361f'
down_revision = '7dcb49b666a6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('food_order', sa.Column('channel_name', sa.String(length=24), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('food_order', 'channel_name')
    # ### end Alembic commands ###
