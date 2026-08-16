from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import Services, get_services
from app.api.schemas import LoginRequest, SignupRequest, TokenResponse
from app.core.security import create_access_token
from app.services.auth_service import EmailTakenError, UsernameTakenError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, services: Services = Depends(get_services)) -> TokenResponse:
    try:
        user = services.auth.signup(username=body.username, email=body.email, password=body.password)
    except UsernameTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "username already taken")
    except EmailTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, services: Services = Depends(get_services)) -> TokenResponse:
    user = services.auth.authenticate(identifier=body.identifier, password=body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    return TokenResponse(access_token=create_access_token(str(user.id)))
