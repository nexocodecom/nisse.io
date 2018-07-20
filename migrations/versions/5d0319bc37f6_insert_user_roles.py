"""insert_user_roles

Revision ID: 5d0319bc37f6
Revises: eac021f634d2
Create Date: 2018-06-27 12:19:32.326261

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5d0319bc37f6'
down_revision = 'eac021f634d2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute("INSERT INTO user_roles(`role`) VALUES('admin');")
    op.execute("INSERT INTO user_roles(`role`) VALUES('user');")

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute("DELETE FROM user_roles where role= 'admin';")
    op.execute("INSERT INTO user_roles where role= 'user';")

    # ### end Alembic commands ###
