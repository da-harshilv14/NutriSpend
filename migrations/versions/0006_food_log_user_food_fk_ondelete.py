"""food_log.user_food_id ON DELETE SET NULL + index

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("food_log_user_food_id_fkey", "food_log", type_="foreignkey")
    op.create_foreign_key(
        "food_log_user_food_id_fkey",
        "food_log",
        "user_food",
        ["user_food_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_food_log_user_food_id", "food_log", ["user_food_id"])


def downgrade() -> None:
    op.drop_index("ix_food_log_user_food_id", table_name="food_log")
    op.drop_constraint("food_log_user_food_id_fkey", "food_log", type_="foreignkey")
    op.create_foreign_key(
        "food_log_user_food_id_fkey",
        "food_log",
        "user_food",
        ["user_food_id"],
        ["id"],
    )
