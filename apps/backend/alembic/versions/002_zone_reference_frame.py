"""Store the frame each zone was drawn on."""

import sqlalchemy as sa
from alembic import op

revision = "002_zone_reference_frame"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 001 builds the schema from the current models, so a fresh database already has the column.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("zones")}
    if "reference_key" not in columns:
        op.add_column("zones", sa.Column("reference_key", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("zones", "reference_key")
