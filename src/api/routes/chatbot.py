"""AI chatbot API endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.modules.chatbot import chat

router = APIRouter()


class ChatRequest(BaseModel):
    """Request body for POST /api/chatbot."""

    message: str
    context: dict | None = None
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    """Response for POST /api/chatbot."""

    response: str


@router.post("/api/chatbot", response_model=ChatResponse)
async def chatbot_endpoint(body: ChatRequest, request: Request) -> ChatResponse:
    """Send a message to the AI assistant."""
    try:
        response = await chat(
            user_message=body.message,
            context=body.context,
            history=body.history,
        )
    except Exception as e:
        response = f"Chatbot error: {e}"
    return ChatResponse(response=response)
