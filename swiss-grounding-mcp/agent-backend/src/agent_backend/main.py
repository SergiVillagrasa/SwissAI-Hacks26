from __future__ import annotations

import io
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from agent_backend.agent_loop import run_chat
from agent_backend.clients import build_aviation_client, build_flight_fares_client, build_ojp_client
from agent_backend.execution_events import ExecutionEventEmitter
from agent_backend.settings import LOCAL_DEV_ORIGIN_REGEX, AgentSettings
from agent_backend.sse import format_sse

settings = AgentSettings.from_env()
app = FastAPI(title="Swiss Grounding MCP Agent Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    # Beyond the explicit allowlist, accept any localhost/127.0.0.1 port so a
    # dev tool that serves the frontend through a proxy on an unpredictable
    # port (or Vite falling back off a busy 3000) isn't a fresh CORS
    # rejection every time. Toggle off with CORS_ALLOW_ANY_LOCAL_PORT=false.
    allow_origin_regex=LOCAL_DEV_ORIGIN_REGEX if settings.cors_allow_any_local_port else None,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
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


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class SpeakRequest(BaseModel):
    text: str


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "openai_configured": _openai_client is not None}


@app.post("/api/chat")
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
            openai_client=_openai_client,
            ojp_client=_ojp_client,
            aviation_client=_aviation_client,
            flight_fares_client=_flight_fares_client,
            settings=settings.mcp_settings,
            model=settings.openai_model,
        ):
            yield format_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/voice/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    if _openai_client is None:
        raise HTTPException(status_code=503, detail=_OPENAI_MISSING_MESSAGE)
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    buffer = io.BytesIO(data)
    buffer.name = audio.filename or "utterance.webm"
    transcript = _openai_client.audio.transcriptions.create(
        model=settings.openai_transcribe_model,
        file=buffer,
    )
    return {"text": (transcript.text or "").strip()}


@app.post("/api/voice/speak")
def speak(request: SpeakRequest) -> Response:
    if _openai_client is None:
        raise HTTPException(status_code=503, detail=_OPENAI_MISSING_MESSAGE)
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    audio = _openai_client.audio.speech.create(
        model=settings.openai_tts_model,
        voice=settings.openai_tts_voice,
        input=text,
        response_format="mp3",
    )
    return Response(content=audio.read(), media_type="audio/mpeg")
