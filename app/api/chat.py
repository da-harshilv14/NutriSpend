from fastapi import APIRouter, Depends, Query

from app.agent.agent import Agent
from app.agent.tools import ToolContext
from app.api.deps import Services, get_agent, get_current_user, get_services
from app.api.schemas import ChatHistoryMessage, ChatHistoryResponse, ChatRequest, ChatResponse
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
    services.chat_message.record_turn(
        user_id=user.id,
        user_message=body.message,
        assistant_reply=result.reply,
        receipts=result.receipts,
    )
    return ChatResponse(reply=result.reply, history=result.history,
                        pending=result.pending, receipts=result.receipts)


@router.get("/chat/history", response_model=ChatHistoryResponse)
def chat_history(
    days: int = Query(7, ge=1, le=7),
    user: User = Depends(get_current_user),
    services: Services = Depends(get_services),
) -> ChatHistoryResponse:
    entries = services.chat_message.recent(user_id=user.id, days=days)
    return ChatHistoryResponse(messages=[
        ChatHistoryMessage(id=e.id, kind=e.kind, content=e.content, created_at=e.created_at.isoformat())
        for e in entries
    ])
