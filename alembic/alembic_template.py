"""This is the initial template for setting up the DB via alembic.
    Run `alembic revision -m "revisionNameHere"`` and then add this code,
    along with any new tables/columns to the new file under alembic/versions/
    Once you're done adding the new changes, run `alembic upgrade head` to
    upgrade the DB to the new version
"""

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
