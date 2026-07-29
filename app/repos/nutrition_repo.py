from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import NutritionReference
from app.repos.interfaces import NutritionRepository


class SqlAlchemyNutritionRepository(NutritionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, reference_id: int) -> NutritionReference | None:
        return self._session.get(NutritionReference, reference_id)

    def get_by_normalized_name(self, name_normalized: str) -> NutritionReference | None:
        return self._session.scalar(
            select(NutritionReference).where(
                NutritionReference.name_normalized == name_normalized
            )
        )

    def search_fuzzy(
        self, name_normalized: str, *, limit: int = 5, threshold: float = 0.3
    ) -> list[tuple[NutritionReference, float]]:
        # Set the trigram cutoff for this transaction, then use the `%` operator
        # so Postgres can serve the match from the GIN trigram index; order the
        # survivors by actual similarity so the closest name comes first. The
        # score rides along so the caller can gauge confidence for HITL.
        self._session.execute(
            text("SELECT set_config('pg_trgm.similarity_threshold', :t, true)"),
            {"t": str(threshold)},
        )
        similarity = func.similarity(NutritionReference.name_normalized, name_normalized)
        statement = (
            select(NutritionReference, similarity.label("score"))
            .where(NutritionReference.name_normalized.op("%")(name_normalized))
            .order_by(similarity.desc())
            .limit(limit)
        )
        return [(row[0], float(row[1])) for row in self._session.execute(statement).all()]

    def add(self, reference: NutritionReference) -> NutritionReference:
        self._session.add(reference)
        self._session.flush()
        return reference
