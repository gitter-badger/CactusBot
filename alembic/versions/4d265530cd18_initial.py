"""initial

Revision ID: 4d265530cd18
Revises:
Create Date: 2016-04-11 21:05:06.053139

"""

# revision identifiers, used by Alembic.
revision = '4d265530cd18'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "commands",
        sa.Column("id", sa.Integer, unique=True, primary_key=True),
        sa.Column("command", sa.String, unique=True),
        sa.Column("response", sa.String),
        sa.Column("calls", sa.Integer, default=0),
        sa.Column("creation", sa.DateTime),
        sa.Column("author", sa.Integer)
    )

    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer, unique=True, primary_key=True),
        sa.Column("quote", sa.String),
        sa.Column("creation", sa.DateTime),
        sa.Column("author", sa.Integer)
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, unique=True, primary_key=True),
        sa.Column("friend", sa.Boolean, default=False),
        sa.Column("joins", sa.Integer, default=0),
        sa.Column("messages", sa.Integer, default=0),
        sa.Column("offenses", sa.Integer, default=0),
        sa.Column("points", sa.Integer, default=0)
    )


def downgrade():
    op.drop_table("commands")
    op.drop_table("quotes")
    op.drop_table("users")
