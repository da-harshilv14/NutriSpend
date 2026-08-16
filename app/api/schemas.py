from pydantic import BaseModel, EmailStr, Field


# --- auth ---
class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    identifier: str  # username or email
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- profile ---
class Goals(BaseModel):
    daily_budget: float
    daily_calories: float
    daily_protein: float
    daily_carbs: float
    daily_fats: float
    daily_sugar: float


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    has_api_key: bool
    goals: Goals


class ApiKeyUpdate(BaseModel):
    api_key: str = Field(min_length=1)


class GoalsUpdate(BaseModel):
    # All optional so the client can PATCH just the fields it changed.
    daily_budget: float | None = Field(default=None, gt=0)
    daily_calories: float | None = Field(default=None, gt=0)
    daily_protein: float | None = Field(default=None, ge=0)
    daily_carbs: float | None = Field(default=None, ge=0)
    daily_fats: float | None = Field(default=None, ge=0)
    daily_sugar: float | None = Field(default=None, ge=0)


# --- chat ---
class ChatRequest(BaseModel):
    message: str
    history: list[dict] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    history: list[dict]
    pending: dict | None = None  # structured HITL: candidates to pick, or a web estimate to confirm
    receipts: list[dict] = []  # what got logged this turn: [{title, amount, calories}]


# --- tracking ---
class ExpenseCreate(BaseModel):
    amount: float
    category: str | None = None
    description: str | None = None


class FoodCreate(BaseModel):
    food_name: str | None = None
    portion_text: str = "1 serving"
    nutrition_id: int | None = None
