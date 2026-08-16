from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.adapters.nutrition_source import StubApiSource
from app.adapters.web_nutrition_source import WebSearchNutritionSource
from app.adapters.web_search import DuckDuckGoSearch
from app.agent.agent import Agent
from app.agent.tools import build_default_registry
from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import SessionLocal
from app.llm.openai_adapter import OpenAICompatibleAdapter
from app.nutrition.lookup import build_nutrition_lookup
from app.repos.expense_log_repo import SqlAlchemyExpenseLogRepository
from app.repos.food_log_repo import SqlAlchemyFoodLogRepository
from app.repos.nutrition_repo import SqlAlchemyNutritionRepository
from app.repos.user_repo import SqlAlchemyUserRepository
from app.services.auth_service import AuthService
from app.services.expense_service import ExpenseService
from app.services.food_service import FoodService
from app.services.nutrition_service import NutritionService

# Stateless singletons — reused across requests (no per-request state).
_settings = get_settings()
_web_search = DuckDuckGoSearch()
_llm = OpenAICompatibleAdapter(
    api_key=_settings.llm_api_key, base_url=_settings.llm_base_url, model=_settings.llm_model
)
_bearer = HTTPBearer(auto_error=False)


def get_session():
    """One session per request; commit on success, roll back on error.
    This is the transaction boundary the services rely on."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@dataclass
class Services:
    auth: AuthService
    food: FoodService
    expense: ExpenseService
    nutrition: NutritionService


def get_services(session: Session = Depends(get_session)) -> Services:
    nutrition_repo = SqlAlchemyNutritionRepository(session)
    lookup = build_nutrition_lookup(
        nutrition_repo, StubApiSource(), WebSearchNutritionSource(_web_search, _llm)
    )
    return Services(
        auth=AuthService(SqlAlchemyUserRepository(session)),
        food=FoodService(SqlAlchemyFoodLogRepository(session), nutrition_repo, lookup),
        expense=ExpenseService(SqlAlchemyExpenseLogRepository(session)),
        nutrition=NutritionService(lookup),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    user = SqlAlchemyUserRepository(session).get_by_id(int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


def get_agent() -> Agent:
    return Agent(_llm, build_default_registry(_web_search))
