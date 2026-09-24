from __future__ import annotations

import io

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from agent_backend.agent_loop import run_chat
from agent_backend.clients import build_aviation_client, build_flight_fares_client, build_ojp_client
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

_openai_client = OpenAI(api_key=settings.openai_api_key)
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
            flight_fares_client=_flight_fares_client,
            settings=settings.mcp_settings,
            model=settings.openai_model,
        ):
            yield format_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/voice/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
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
