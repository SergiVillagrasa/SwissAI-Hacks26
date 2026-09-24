from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from agent_backend.agent_loop import run_chat
from agent_backend.clients import build_aviation_client, build_ojp_client
from agent_backend.settings import AgentSettings
from agent_backend.sse import format_sse

settings = AgentSettings.from_env()
app = FastAPI(title="Swiss Grounding MCP Agent Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

_openai_client = OpenAI(api_key=settings.openai_api_key)
_ojp_client = build_ojp_client(settings)
_aviation_client = build_aviation_client(settings)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    def event_stream():
        messages = [message.model_dump() for message in request.messages]
        for event in run_chat(
            messages,
            openai_client=_openai_client,
            ojp_client=_ojp_client,
            aviation_client=_aviation_client,
            settings=settings.mcp_settings,
            model=settings.openai_model,
        ):
            yield format_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
