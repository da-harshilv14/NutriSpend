from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Where a nutrition_reference row's values came from. Stored as a plain string
# (not a DB enum) so new sources are additions, not schema migrations.
NUTRITION_SOURCES = ("dataset", "api", "websearch", "user")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    api_key: Mapped[str | None] = mapped_column(String(255), default=None)

    # Daily targets shown on the Today screen. Defaults are the app's starting
    # values; the user can change them from Profile.
    daily_budget: Mapped[float] = mapped_column(default=1500.0)
    daily_calories: Mapped[float] = mapped_column(default=2100.0)
    daily_protein: Mapped[float] = mapped_column(default=90.0)
    daily_carbs: Mapped[float] = mapped_column(default=260.0)
    daily_fats: Mapped[float] = mapped_column(default=70.0)
    daily_sugar: Mapped[float] = mapped_column(default=40.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NutritionReference(Base):
    __tablename__ = "nutrition_reference"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # Lowercased/trimmed lookup key. Unique so cache-back has one canonical row
    # per food; a trigram GIN index (added in the migration) powers fuzzy match.
    name_normalized: Mapped[str] = mapped_column(String(255), unique=True)

    calories_per_100g: Mapped[float | None] = mapped_column(default=None)
    protein_per_100g: Mapped[float | None] = mapped_column(default=None)
    carbs_per_100g: Mapped[float | None] = mapped_column(default=None)
    fats_per_100g: Mapped[float | None] = mapped_column(default=None)
    sugar_per_100g: Mapped[float | None] = mapped_column(default=None)

    serving_size: Mapped[float | None] = mapped_column(default=None)
    serving_unit: Mapped[str | None] = mapped_column(String(50), default=None)
    source: Mapped[str] = mapped_column(String(20), default="dataset")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FoodLog(Base):
    __tablename__ = "food_log"
    __table_args__ = (Index("ix_food_log_user_date", "user_id", "log_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    log_date: Mapped[date] = mapped_column(Date)
    nutrition_id: Mapped[int | None] = mapped_column(
        ForeignKey("nutrition_reference.id"), default=None
    )

    quantity_grams: Mapped[float]
    portion_text: Mapped[str | None] = mapped_column(String(255), default=None)

    # Snapshot of the computed nutrients for this entry, so later corrections to
    # nutrition_reference never silently change historical logs.
    calories: Mapped[float | None] = mapped_column(default=None)
    protein: Mapped[float | None] = mapped_column(default=None)
    carbs: Mapped[float | None] = mapped_column(default=None)
    fats: Mapped[float | None] = mapped_column(default=None)
    sugar: Mapped[float | None] = mapped_column(default=None)

    # True if the nutrition came from a web estimate at log time (kept forever,
    # even after the cached reference row is promoted to a verified source).
    is_estimate: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExpenseLog(Base):
    __tablename__ = "expense_log"
    __table_args__ = (Index("ix_expense_log_user_date", "user_id", "log_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    log_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    category: Mapped[str | None] = mapped_column(String(100), default=None)
    description: Mapped[str | None] = mapped_column(String(500), default=None)
    food_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("food_log.id"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
