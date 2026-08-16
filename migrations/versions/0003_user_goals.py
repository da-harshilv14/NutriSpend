"""add per-user daily goals

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GOALS = {
    "daily_budget": "1500",
    "daily_calories": "2100",
    "daily_protein": "90",
    "daily_carbs": "260",
    "daily_fats": "70",
    "daily_sugar": "40",
}


def upgrade() -> None:
    for name, default in _GOALS.items():
        op.add_column(
            "users",
            sa.Column(name, sa.Float(), nullable=False, server_default=default),
        )


def downgrade() -> None:
    for name in _GOALS:
        op.drop_column("users", name)
