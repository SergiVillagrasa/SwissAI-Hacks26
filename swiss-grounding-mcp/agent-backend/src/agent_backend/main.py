from __future__ import annotations

import io
import logging
from math import ceil
from typing import Literal
from uuid import uuid4

import openai
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from mcp.server.transport_security import RequestBodyLimitMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field
from swiss_grounding_mcp.http_security import (
    SlidingWindowRateLimiter,
    bearer_token_matches,
    client_ip,
)

from agent_backend.agent_loop import run_chat
from agent_backend.clients import (
    build_aviation_client,
    build_flight_fares_client,
    build_ojp_client,
)
from agent_backend.execution_events import ExecutionEventEmitter
from agent_backend.settings import LOCAL_DEV_ORIGIN_REGEX, AgentSettings
from agent_backend.sse import format_sse

logger = logging.getLogger(__name__)
settings = AgentSettings.from_env()
app = FastAPI(title="Swiss Grounding MCP Agent Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    # Allow arbitrary local development ports only when explicitly enabled.
    allow_origin_regex=LOCAL_DEV_ORIGIN_REGEX if settings.cors_allow_any_local_port else None,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)
app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_size=settings.max_audio_upload_bytes + 65_536,
)

def _build_openai_client(api_key: str) -> OpenAI | None:
    """Create the OpenAI client, or None when the key is missing/invalid.

    The app must import and serve /api/health even without a key so that
    misconfiguration surfaces as a clean status instead of a crash.
    """
    if not api_key:
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception:  # noqa: BLE001 - any SDK init failure degrades cleanly
        return None


_OPENAI_MISSING_MESSAGE = (
    "The assistant service is unavailable: OPENAI_API_KEY is missing or "
    "invalid. Configure it in server/.env or agent-backend/.env."
)

_openai_client = _build_openai_client(settings.openai_api_key)
_ojp_client = build_ojp_client(settings)
_aviation_client = build_aviation_client(settings)
_flight_fares_client = build_flight_fares_client(settings)
_rate_limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute, 60)
_daily_limiter = SlidingWindowRateLimiter(settings.daily_request_limit, 86_400)


def enforce_access(request: Request) -> None:
    if settings.agent_api_key and not bearer_token_matches(
        request.headers.get("authorization"), settings.agent_api_key
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )

    retry_after = _rate_limiter.check(
        client_ip(
            request.headers,
            request.client.host if request.client else None,
            settings.client_ip_header,
        )
    )
    if retry_after is None:
        retry_after = _daily_limiter.check("global")
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(ceil(retry_after))},
        )


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    channel: Literal["text", "voice"] | None = None


class SpeakRequest(BaseModel):
    text: str = Field(max_length=1500)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "openai_configured": _openai_client is not None}


@app.post("/api/chat", dependencies=[Depends(enforce_access)])
def chat(request: ChatRequest) -> StreamingResponse:
    def event_stream():
        run_id = str(uuid4())
        if _openai_client is None:
            emitter = ExecutionEventEmitter(run_id)
            yield format_sse(emitter.emit(
                "run_started",
                node_id="run",
                label="Workflow started",
                status="running",
                summary="Starting your request",
            ))
            yield format_sse({
                "type": "widget",
                "tool": None,
                "status": "source_error",
                "data": {"message": _OPENAI_MISSING_MESSAGE},
            })
            yield format_sse(emitter.emit(
                "run_completed",
                node_id="run",
                label="Workflow failed",
                status="failed",
                summary="The assistant service is unavailable",
                outcome="failed",
            ))
            yield format_sse({"type": "done"})
            return
        messages = [message.model_dump() for message in request.messages]
        for event in run_chat(
            messages,
            run_id=run_id,
            channel=request.channel,
            openai_client=_openai_client,
            ojp_client=_ojp_client,
            aviation_client=_aviation_client,
            flight_fares_client=_flight_fares_client,
            settings=settings.mcp_settings,
            model=settings.openai_model,
        ):
            yield format_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post(
    "/api/voice/transcribe", dependencies=[Depends(enforce_access)]
)
async def transcribe(audio: UploadFile = File(...)) -> dict:
    if _openai_client is None:
        raise HTTPException(status_code=503, detail=_OPENAI_MISSING_MESSAGE)
    data = await audio.read(settings.max_audio_upload_bytes + 1)
    if len(data) > settings.max_audio_upload_bytes:
        raise HTTPException(status_code=413, detail="Audio upload too large")
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    buffer = io.BytesIO(data)
    buffer.name = audio.filename or "utterance.webm"
    try:
        transcript = _openai_client.audio.transcriptions.create(
            model=settings.openai_transcribe_model,
            file=buffer,
        )
    except openai.OpenAIError as exc:
        logger.exception("OpenAI transcription request failed")
        raise HTTPException(
            status_code=502, detail="Voice provider request failed."
        ) from exc
    return {"text": (transcript.text or "").strip()}


@app.post("/api/voice/speak", dependencies=[Depends(enforce_access)])
def speak(request: SpeakRequest) -> Response:
    if _openai_client is None:
        raise HTTPException(status_code=503, detail=_OPENAI_MISSING_MESSAGE)
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    try:
        audio = _openai_client.audio.speech.create(
            model=settings.openai_tts_model,
            voice=settings.openai_tts_voice,
            input=text,
            response_format="mp3",
        )
        audio_bytes = audio.read()
    except openai.OpenAIError as exc:
        logger.exception("OpenAI speech request failed")
        raise HTTPException(
            status_code=502, detail="Voice provider request failed."
        ) from exc
    return Response(content=audio_bytes, media_type="audio/mpeg")
