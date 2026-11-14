"""bsr alert opt-in and alert dedupe state

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("notify_bsr_alerts", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_table(
        "alert_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("last_snapshot_id", sa.Integer(), nullable=False),
        sa.Column(
            "alerted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_alert_states_user_product"),
    )
    op.create_index("ix_alert_states_user_id", "alert_states", ["user_id"])
    op.create_index("ix_alert_states_product_id", "alert_states", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_alert_states_product_id", table_name="alert_states")
    op.drop_index("ix_alert_states_user_id", table_name="alert_states")
    op.drop_table("alert_states")
    op.drop_column("users", "notify_bsr_alerts")
