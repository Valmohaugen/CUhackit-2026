"""Tests for the AI chatbot module and API endpoint.

Covers:
  - chat() with missing API key
  - chat() with mocked OpenAI client
  - /api/chatbot endpoint via test client

These tests mock the openai SDK so they work without it installed.
"""

from __future__ import annotations

import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: ensure 'openai' is importable even if not installed
# ---------------------------------------------------------------------------

def _ensure_openai_mock():
    """Insert a fake 'openai' module into sys.modules if the real one is absent."""
    if "openai" not in sys.modules:
        mod = types.ModuleType("openai")
        mod.AsyncOpenAI = MagicMock  # type: ignore[attr-defined]
        sys.modules["openai"] = mod


# ---------------------------------------------------------------------------
# Unit tests for the chat() function
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestChatFunction:
    """Tests for src.modules.chatbot.chat()."""

    async def test_missing_api_key_returns_friendly_error(self) -> None:
        """chat() returns a helpful message when OPENAI_API_KEY is unset."""
        _ensure_openai_mock()
        # Force reimport to pick up the mock
        if "src.modules.chatbot" in sys.modules:
            del sys.modules["src.modules.chatbot"]
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            from src.modules.chatbot import chat
            result = await chat("Hello")
        assert "OPENAI_API_KEY" in result

    async def test_chat_with_mocked_openai(self) -> None:
        """chat() returns the model's response when OpenAI call succeeds."""
        _ensure_openai_mock()

        mock_message = MagicMock()
        mock_message.content = "Lattice crypto uses hard math problems."
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        # Patch AsyncOpenAI in the openai module so the lazy import picks it up
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
            with patch.dict(sys.modules["openai"].__dict__, {"AsyncOpenAI": lambda **_: mock_client}):
                if "src.modules.chatbot" in sys.modules:
                    del sys.modules["src.modules.chatbot"]
                from src.modules.chatbot import chat
                result = await chat("What is lattice crypto?")

        assert result == "Lattice crypto uses hard math problems."

    async def test_chat_with_context_injects_pool_size(self) -> None:
        """chat() injects context into the user message."""
        _ensure_openai_mock()

        mock_message = MagicMock()
        mock_message.content = "Got it."
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
            with patch.dict(sys.modules["openai"].__dict__, {"AsyncOpenAI": lambda **_: mock_client}):
                if "src.modules.chatbot" in sys.modules:
                    del sys.modules["src.modules.chatbot"]
                from src.modules.chatbot import chat
                result = await chat("Hello", context={"pool_size": 42})

        assert result == "Got it."
        # Check that context was injected
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        user_msg = call_kwargs["messages"][-1]["content"]
        assert "42 seeds" in user_msg

    async def test_chat_openai_error_returns_friendly_message(self) -> None:
        """chat() returns a friendly error string when OpenAI raises."""
        _ensure_openai_mock()

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("rate limited")
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
            with patch.dict(sys.modules["openai"].__dict__, {"AsyncOpenAI": lambda **_: mock_client}):
                if "src.modules.chatbot" in sys.modules:
                    del sys.modules["src.modules.chatbot"]
                from src.modules.chatbot import chat
                result = await chat("Hi")

        assert "rate limited" in result


# ---------------------------------------------------------------------------
# Integration test for the /api/chatbot endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestChatbotEndpoint:
    """Tests for the POST /api/chatbot FastAPI endpoint."""

    async def test_endpoint_handles_crash_gracefully(self, fake_redis) -> None:
        """The endpoint returns 200 with error message (not 500) if chat() crashes."""
        try:
            from fastapi import FastAPI
            from httpx import ASGITransport, AsyncClient
        except ImportError:
            pytest.skip("fastapi/httpx not installed — run in Docker")

        from src.api.routes.chatbot import router

        app = FastAPI()
        app.state.redis = fake_redis
        app.include_router(router)

        with patch("src.api.routes.chatbot.chat", side_effect=RuntimeError("boom")):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/api/chatbot",
                    json={"message": "Hello"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "boom" in data["response"]
