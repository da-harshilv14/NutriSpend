from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


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


# --- personal foods ---
def _clean_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("name must not be blank")
    return value


class FoodItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    calories_per_100g: float = Field(gt=0)
    protein_per_100g: float | None = Field(default=None, ge=0)
    carbs_per_100g: float | None = Field(default=None, ge=0)
    fats_per_100g: float | None = Field(default=None, ge=0)
    sugar_per_100g: float | None = Field(default=None, ge=0)
    serving_size: float | None = Field(default=None, gt=0)
    serving_unit: str | None = Field(default=None, max_length=50)

    _strip_name = field_validator("name")(_clean_name)


class FoodItemUpdate(BaseModel):
    # Only these fields exist on the model, so protected columns (id, user_id,
    # source, created_at) can never reach the service. Use exclude_unset when dumping.
    name: str | None = Field(default=None, min_length=1, max_length=255)
    calories_per_100g: float | None = Field(default=None, gt=0)
    protein_per_100g: float | None = Field(default=None, ge=0)
    carbs_per_100g: float | None = Field(default=None, ge=0)
    fats_per_100g: float | None = Field(default=None, ge=0)
    sugar_per_100g: float | None = Field(default=None, ge=0)
    serving_size: float | None = Field(default=None, gt=0)
    serving_unit: str | None = Field(default=None, max_length=50)

    _strip_name = field_validator("name")(_clean_name)

    @model_validator(mode="after")
    def _required_fields_not_null(self):
        for field in ("name", "calories_per_100g"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class FoodItemResponse(BaseModel):
    id: int
    name: str
    calories_per_100g: float | None
    protein_per_100g: float | None
    carbs_per_100g: float | None
    fats_per_100g: float | None
    sugar_per_100g: float | None
    serving_size: float | None
    serving_unit: str | None

    model_config = {"from_attributes": True}


class FoodListResponse(BaseModel):
    foods: list[FoodItemResponse]
