"""add user_food table for per-user personal foods

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_food",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_normalized", sa.String(255), nullable=False),
        sa.Column("calories_per_100g", sa.Float(), nullable=True),
        sa.Column("protein_per_100g", sa.Float(), nullable=True),
        sa.Column("carbs_per_100g", sa.Float(), nullable=True),
        sa.Column("fats_per_100g", sa.Float(), nullable=True),
        sa.Column("sugar_per_100g", sa.Float(), nullable=True),
        sa.Column("serving_size", sa.Float(), nullable=True),
        sa.Column("serving_unit", sa.String(50), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="user"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "name_normalized", name="uq_user_food_user_name"
        ),
    )
    op.create_index("ix_user_food_user", "user_food", ["user_id"])
    # Fuzzy-match index (trigram GIN), mirroring nutrition_reference.
    op.execute(
        "CREATE INDEX ix_user_food_name_trgm "
        "ON user_food USING gin (name_normalized gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_table("user_food")
