"""removed_not_used_tables

Revision ID: cbb870be3cbc
Revises: d11926bbd2ec
Create Date: 2018-12-19 10:30:04.776074

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'cbb870be3cbc'
down_revision = 'd11926bbd2ec'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###    
    op.add_column('tokens', sa.Column('client_secret', sa.String(length=255), nullable=True))
    op.create_unique_constraint('tokens_client_id_key', 'tokens', ['client_id'])
    #op.drop_constraint('tokens_user_id_fkey', 'tokens', type_='foreignkey')
    #op.drop_constraint('tokens_client_id_fkey', 'tokens', type_='foreignkey')
    op.drop_table('clients')
    op.drop_column('tokens', 'expires')
    op.drop_column('tokens', 'user_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tokens', sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('tokens', sa.Column('expires', postgresql.TIMESTAMP(), autoincrement=False, nullable=True))
    #op.create_foreign_key('tokens_client_id_fkey', 'tokens', 'clients', ['client_id'], ['client_id'])
    #op.create_foreign_key('tokens_user_id_fkey', 'tokens', 'users', ['user_id'], ['user_id'])
    op.drop_constraint('tokens_client_id_key', 'tokens', type_='unique')
    op.drop_column('tokens', 'client_secret')
    op.create_table('clients',
    sa.Column('client_id', sa.VARCHAR(length=40), autoincrement=False, nullable=False),
    sa.Column('client_type', sa.VARCHAR(length=40), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('client_id', name='clients_pkey')
    )
    # ### end Alembic commands ###
