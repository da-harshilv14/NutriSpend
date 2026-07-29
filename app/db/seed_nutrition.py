"""Seed nutrition_reference from the Kaggle Indian-food dataset.

Run once (idempotent — safe to re-run):
    python -m app.db.seed_nutrition
"""
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import NutritionReference
from app.db.session import SessionLocal
from app.nutrition.text import normalize_name

CSV_PATH = Path("data/indian_food_nutrition.csv")

# CSV column -> our per-100g field. Only the five tracked nutrients are loaded.
COLUMN_MAP = {
    "Calories (kcal)": "calories_per_100g",
    "Protein (g)": "protein_per_100g",
    "Carbohydrates (g)": "carbs_per_100g",
    "Fats (g)": "fats_per_100g",
    "Free Sugar (g)": "sugar_per_100g",
}


def build_records(frame: pd.DataFrame) -> list[dict]:
    records = []
    for _, row in frame.iterrows():
        record = {
            "name": str(row["Dish Name"]).strip(),
            "name_normalized": normalize_name(row["Dish Name"]),
            "source": "dataset",
        }
        for csv_column, field in COLUMN_MAP.items():
            record[field] = float(row[csv_column])
        records.append(record)
    return records


def main() -> None:
    frame = pd.read_csv(CSV_PATH)
    records = build_records(frame)

    count_query = select(func.count()).select_from(NutritionReference)
    with SessionLocal() as session:
        before = session.scalar(count_query)
        # ON CONFLICT DO NOTHING makes re-runs harmless: rows whose name already
        # exists (dataset seed or a cached lookup) are skipped, not duplicated.
        statement = insert(NutritionReference).on_conflict_do_nothing(
            index_elements=["name_normalized"]
        )
        session.execute(statement, records)
        session.commit()
        after = session.scalar(count_query)

    print(f"Read {len(records)} rows from CSV; inserted {after - before} new; "
          f"table now holds {after} nutrition rows.")


if __name__ == "__main__":
    main()
