"""add food_log.user_food_id for personal-food logging

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "food_log",
        sa.Column(
            "user_food_id",
            sa.Integer(),
            sa.ForeignKey("user_food.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("food_log", "user_food_id")
