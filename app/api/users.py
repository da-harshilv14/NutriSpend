from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import Services, get_current_user, get_services
from app.api.schemas import ApiKeyUpdate, Goals, GoalsUpdate, UserResponse
from app.db.models import User

router = APIRouter(tags=["profile"])


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        has_api_key=user.api_key is not None,
        goals=Goals(
            daily_budget=user.daily_budget,
            daily_calories=user.daily_calories,
            daily_protein=user.daily_protein,
            daily_carbs=user.daily_carbs,
            daily_fats=user.daily_fats,
            daily_sugar=user.daily_sugar,
        ),
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    return _to_response(user)


@router.patch("/me", response_model=UserResponse)
def set_api_key(
    body: ApiKeyUpdate,
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> UserResponse:
    updated = services.auth.set_api_key(user_id=user.id, api_key=body.api_key)
    return _to_response(updated)


@router.patch("/me/goals", response_model=UserResponse)
def set_goals(
    body: GoalsUpdate,
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> UserResponse:
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no goal fields to update")
    updated = services.auth.set_goals(user_id=user.id, goals=changes)
    return _to_response(updated)
