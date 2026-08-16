from fastapi import APIRouter, Depends

from app.agent.agent import Agent
from app.agent.tools import ToolContext
from app.api.deps import Services, get_agent, get_current_user, get_services
from app.api.schemas import ChatRequest, ChatResponse
from app.db.models import User

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
    agent: Agent = Depends(get_agent),
) -> ChatResponse:
    # The server is stateless: the client sends prior `history` back each turn.
    context = ToolContext(
        user_id=user.id,
        food_service=services.food,
        expense_service=services.expense,
        nutrition_service=services.nutrition,
    )
    result = agent.run(user_message=body.message, context=context, history=body.history)
    return ChatResponse(reply=result.reply, history=result.history,
                        pending=result.pending, receipts=result.receipts)
