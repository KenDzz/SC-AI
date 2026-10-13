"""Cameras that move between views, such as PTZ presets."""

import sqlalchemy as sa
from alembic import op

revision = "003_camera_multi_view"
down_revision = "002_zone_reference_frame"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 001 builds the schema from the current models, so a fresh database already has the column.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("cameras")}
    if "multi_view" not in columns:
        op.add_column("cameras", sa.Column("multi_view", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("cameras", "multi_view")
