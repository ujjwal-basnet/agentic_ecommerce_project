"""Google Gemini LLM wrapper — sync + async calls."""

from __future__ import annotations

from pathlib import Path

from google.oauth2 import service_account
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from api import config

_MODEL = config.GEMINI_MODEL
_chat_model: ChatGoogleGenerativeAI | None = None


def _vertex_credentials() -> service_account.Credentials:
    credentials_path = Path(config.GOOGLE_APPLICATION_CREDENTIALS).expanduser()
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Google service account file not found: {credentials_path}"
        )
    return service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def _get_model() -> ChatGoogleGenerativeAI:
    global _chat_model
    if _chat_model is None:
        if config.GOOGLE_GENAI_USE_VERTEXAI:
            _chat_model = ChatGoogleGenerativeAI(
                model=_MODEL,
                credentials=_vertex_credentials(),
                project=config.GOOGLE_CLOUD_PROJECT,
                location=config.GOOGLE_CLOUD_LOCATION,
                vertexai=True,
                temperature=0.2,
            )
        else:
            _chat_model = ChatGoogleGenerativeAI(
                model=_MODEL,
                api_key=config.GOOGLE_API_KEY,
                vertexai=False,
                temperature=0.2,
            )
    return _chat_model


def _messages(system: str, user: str):
    return [SystemMessage(system), HumanMessage(user)]


def call_llm(system, user, *, schema: type[BaseModel] | None = None):
    model = _get_model()
    if schema:
        return model.with_structured_output(schema).invoke(_messages(system, user))
    return str(model.invoke(_messages(system, user)).content)


async def acall_llm(system, user, *, schema: type[BaseModel] | None = None):
    """Async variant — uses native ainvoke (no thread pool needed)."""
    model = _get_model()
    if schema:
        return await model.with_structured_output(schema).ainvoke(
            _messages(system, user)
        )
    resp = await model.ainvoke(_messages(system, user))
    return str(resp.content)
