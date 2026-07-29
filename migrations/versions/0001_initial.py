"""initial schema: users, nutrition_reference, food_log, expense_log

Revision ID: 0001
Revises:
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fuzzy food-name matching (Phase 2) needs trigram similarity.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("api_key", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "nutrition_reference",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_normalized", sa.String(255), nullable=False),
        sa.Column("calories_per_100g", sa.Float(), nullable=True),
        sa.Column("protein_per_100g", sa.Float(), nullable=True),
        sa.Column("carbs_per_100g", sa.Float(), nullable=True),
        sa.Column("fats_per_100g", sa.Float(), nullable=True),
        sa.Column("sugar_per_100g", sa.Float(), nullable=True),
        sa.Column("serving_size", sa.Float(), nullable=True),
        sa.Column("serving_unit", sa.String(50), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="dataset"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    # Exact-match lookup key (also enforces one canonical row per food).
    op.create_index(
        "ix_nutrition_reference_name_normalized", "nutrition_reference", ["name_normalized"], unique=True
    )
    # Fuzzy-match index (trigram GIN) for the lookup chain's fuzzy link.
    op.execute(
        "CREATE INDEX ix_nutrition_reference_name_trgm "
        "ON nutrition_reference USING gin (name_normalized gin_trgm_ops)"
    )

    op.create_table(
        "food_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("nutrition_id", sa.Integer(), sa.ForeignKey("nutrition_reference.id"), nullable=True),
        sa.Column("quantity_grams", sa.Float(), nullable=False),
        sa.Column("portion_text", sa.String(255), nullable=True),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("protein", sa.Float(), nullable=True),
        sa.Column("carbs", sa.Float(), nullable=True),
        sa.Column("fats", sa.Float(), nullable=True),
        sa.Column("sugar", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_food_log_user_date", "food_log", ["user_id", "log_date"])

    op.create_table(
        "expense_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("food_log_id", sa.Integer(), sa.ForeignKey("food_log.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_expense_log_user_date", "expense_log", ["user_id", "log_date"])


def downgrade() -> None:
    op.drop_table("expense_log")
    op.drop_table("food_log")
    op.drop_table("nutrition_reference")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
