"""Google Gemini LLM wrapper with simple call_llm function."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

import config


# Shared model instance
_chat_model: ChatGoogleGenerativeAI | None = None


def _get_model() -> ChatGoogleGenerativeAI:
    """Get or create shared chat model."""
    global _chat_model
    if _chat_model is None:
        _chat_model = ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL,
            api_key=config.GOOGLE_API_KEY,
            temperature=0.7,
            max_retries=2,
        )
    return _chat_model


def call_llm(
    system: str,
    user: str,
    *,
    schema: type[BaseModel] | None = None,
    temperature: float | None = None,
) -> str | BaseModel:
    """Call LLM with system and user messages.

    Args:
        system: System prompt.
        user: User message.
        schema: If provided, return structured output as Pydantic model.
        temperature: Override default temperature.

    Returns:
        str if no schema, or Pydantic model instance if schema given.
    """
    model = _get_model()

    if temperature is not None:
        model = ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL,
            api_key=config.GOOGLE_API_KEY,
            temperature=temperature,
            max_retries=2,
        )

    messages = [SystemMessage(system), HumanMessage(user)]

    if schema:
        structured = model.with_structured_output(schema)
        return structured.invoke(messages)

    response = model.invoke(messages)
    return str(response.content)
