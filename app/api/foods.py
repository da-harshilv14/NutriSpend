from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import Services, get_current_user, get_services
from app.api.schemas import (
    FoodItemCreate,
    FoodItemResponse,
    FoodItemUpdate,
    FoodListResponse,
)
from app.db.models import User
from app.services.user_food_service import DuplicateFoodError

router = APIRouter(prefix="/foods", tags=["foods"])

_NOT_FOUND = "food not found"


def _duplicate() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "you already have a food with that name")


@router.get("", response_model=FoodListResponse)
def list_foods(
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> FoodListResponse:
    foods = services.user_food.list(user.id)
    return FoodListResponse(foods=[FoodItemResponse.model_validate(f) for f in foods])


@router.post("", response_model=FoodItemResponse, status_code=status.HTTP_201_CREATED)
def create_food(
    body: FoodItemCreate,
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> FoodItemResponse:
    try:
        food = services.user_food.create(user_id=user.id, **body.model_dump())
    except DuplicateFoodError:
        raise _duplicate()
    except IntegrityError:  # backstop for a race past the service's duplicate check
        raise _duplicate()
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return FoodItemResponse.model_validate(food)


@router.get("/{food_id}", response_model=FoodItemResponse)
def get_food(
    food_id: int,
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> FoodItemResponse:
    food = services.user_food.get(user.id, food_id)
    if food is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return FoodItemResponse.model_validate(food)


@router.patch("/{food_id}", response_model=FoodItemResponse)
def update_food(
    food_id: int,
    body: FoodItemUpdate,
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> FoodItemResponse:
    # Only validated schema fields ever reach the service (no id/user_id/source).
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no food fields to update")
    try:
        food = services.user_food.update(user.id, food_id, changes)
    except DuplicateFoodError:
        raise _duplicate()
    except IntegrityError:
        raise _duplicate()
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if food is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return FoodItemResponse.model_validate(food)


@router.delete("/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food(
    food_id: int,
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> Response:
    if not services.user_food.delete(user.id, food_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
