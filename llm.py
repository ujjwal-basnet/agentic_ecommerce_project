"""Google Gemini LLM wrapper — sync + async calls.

Client creation lives in google_client.py so llm.py never re-initializes
credentials or the chat model per call.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from google_client import get_chat_model


def _messages(system: str, user: str):
    return [SystemMessage(system), HumanMessage(user)]


def call_llm(system, user, *, schema: type[BaseModel] | None = None):
    model = get_chat_model()
    if schema:
        return model.with_structured_output(schema).invoke(_messages(system, user))
    return str(model.invoke(_messages(system, user)).content)


async def acall_llm(system, user, *, schema: type[BaseModel] | None = None):
    """Async variant — uses native ainvoke (no thread pool needed)."""
    model = get_chat_model()
    if schema:
        return await model.with_structured_output(schema).ainvoke(_messages(system, user))
    resp = await model.ainvoke(_messages(system, user))
    return str(resp.content)
