"""Hands-free conversational voice assistant for the Swiss Grounding MCP tools.

Pipeline per turn: microphone -> ElevenLabs Scribe STT -> intent routing ->
tool call (find_connections / get_station_board / find_disruptions /
aviation tools) -> spoken-summary renderer -> ElevenLabs TTS -> speaker.

Usage (from server/):
    ./.venv/Scripts/python voice_assistant.py              # full voice loop
    ./.venv/Scripts/python voice_assistant.py --text       # type instead of speak
    ./.venv/Scripts/python voice_assistant.py --self-test  # mock end-to-end check
    ./.venv/Scripts/python voice_assistant.py --list-devices

Requires ELEVENLABS_API_KEY in .env or .env.local.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)

import os

from elevenlabs import ElevenLabs

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import (
    AirportGuidanceResult,
    ConnectionSearchResult,
    DisruptionSearchResult,
    FlightLookupResult,
    FlightSearchResult,
    FlightToTrainResult,
    StationBoardResult,
)
from swiss_grounding_mcp.sources.aerodatabox.client import AerodataboxClient
from swiss_grounding_mcp.sources.ojp.client import OjpClient
from swiss_grounding_mcp.tools.connect_flight_to_train import (
    connect_flight_to_train,
)
from swiss_grounding_mcp.tools.find_connections import find_train_connections
from swiss_grounding_mcp.tools.find_disruptions import find_station_disruptions
from swiss_grounding_mcp.tools.find_flight_by_number import find_flight_by_number
from swiss_grounding_mcp.tools.get_airport_guidance import get_airport_guidance
from swiss_grounding_mcp.tools.search_airport_flights import search_airport_flights
from swiss_grounding_mcp.tools.station_timetable import get_station_board

MIC_RATE = 16_000          # Hz — mono 16-bit WAV sent to Scribe
TTS_RATE = 24_000          # pcm_24000 output format
MAX_UTTERANCE_S = 20.0
SILENCE_S = 1.3            # trailing silence that ends an utterance
SPEECH_RMS = 0.012         # energy gate — ignore quiet rooms
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel
TTS_MODEL = "eleven_multilingual_v2"
STT_MODEL = "scribe_v1"

# Canonical main stations — voice UX: a bare city name should reach the
# Hauptbahnhof, not stall on the LIR ambiguity between e.g. the airport
# and the city stop. The MCP tools keep their honest clarify behavior;
# this mapping is applied only in the conversational layer.
_CANONICAL_STATIONS = {
    "zurich": "Zürich HB", "zuerich": "Zürich HB", "zurigo": "Zürich HB",
    "geneva": "Genève", "geneve": "Genève", "genf": "Genève",
    "bern": "Bern", "basel": "Basel SBB", "bale": "Basel SBB",
    "luzern": "Luzern", "lucerne": "Luzern", "lausanne": "Lausanne",
    "lugano": "Lugano", "interlaken": "Interlaken Ost",
    "winterthur": "Winterthur", "chur": "Chur", "coire": "Chur",
    "st gallen": "St. Gallen", "sankt gallen": "St. Gallen",
    "sion": "Sion", "fribourg": "Fribourg", "freiburg": "Fribourg",
    "neuchatel": "Neuchâtel", "biel": "Biel/Bienne", "bienne": "Biel/Bienne",
    "thun": "Thun", "aarau": "Aarau", "olten": "Olten",
    "schaffhausen": "Schaffhausen", "zug": "Zug", "bellinzona": "Bellinzona",
    "locarno": "Locarno", "montreux": "Montreux", "davos": "Davos Platz",
    "st moritz": "St. Moritz", "sankt moritz": "St. Moritz",
    "zermatt": "Zermatt", "sierre": "Sierre/Siders", "martigny": "Martigny",
    "baden": "Baden", "brig": "Brig", "brigue": "Brig",
    "kreuzlingen": "Kreuzlingen", "rapperswil": "Rapperswil SG",
}


def _canonical_station(name: str) -> str:
    return _CANONICAL_STATIONS.get(_norm(name).strip(), name)


_GOODBYE = re.compile(
    r"\b(goodbye|bye|tsch[uü]ss|tschau|au revoir|adieu|arrivederci|addio|"
    r"ade|ciao|quit|exit|stop listening|that's all)\b",
    re.IGNORECASE,
)


def _norm(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def is_goodbye(text: str) -> bool:
    return bool(_GOODBYE.search(_norm(text)))


def load_elevenlabs_key(env: dict | None = None) -> str:
    source = env if env is not None else os.environ
    key = (source.get("ELEVENLABS_API_KEY") or source.get("ELEVEN_LABS_API_KEY") or "")
    key = key.strip().strip('"').strip("'").strip()
    # Guard against an accidentally doubled paste (key concatenated with itself).
    half = len(key) // 2
    if half and len(key) % 2 == 0 and key[:half] == key[half:]:
        key = key[:half]
    return key


# --------------------------------------------------------------------------
# ElevenLabs speech boundary
# --------------------------------------------------------------------------

class ElevenLabsSpeech:
    def __init__(self, api_key: str, voice_id: str = DEFAULT_VOICE_ID) -> None:
        self.client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id

    def transcribe(self, wav_bytes: bytes) -> str:
        resp = self.client.speech_to_text.convert(
            model_id=STT_MODEL,
            file=wav_bytes,
        )
        return (resp.text or "").strip()

    def synthesize(self, text: str) -> bytes:
        chunks = self.client.text_to_speech.convert(
            self.voice_id,
            text=text,
            model_id=TTS_MODEL,
            output_format="pcm_24000",
        )
        return b"".join(chunks)


# --------------------------------------------------------------------------
# Audio I/O boundary (injectable for tests)
# --------------------------------------------------------------------------

class MicRecorder:
    """Records one utterance from the default input device with a simple
    energy-based VAD: starts on speech, ends on trailing silence."""

    def record_utterance(
        self,
        max_seconds: float = MAX_UTTERANCE_S,
        no_speech_timeout: float = 15.0,
    ) -> bytes:
        import sounddevice as sd
        import soundfile as sf

        frames: list[np.ndarray] = []
        started = False
        silence = 0.0
        block = 0.05  # 50 ms
        block_frames = int(MIC_RATE * block)

        with sd.InputStream(
            samplerate=MIC_RATE, channels=1, dtype="float32", blocksize=block_frames
        ) as stream:
            while True:
                data, _ = stream.read(block_frames)
                frames.append(data.copy())
                rms = float(np.sqrt(np.mean(data**2)))
                if rms >= SPEECH_RMS:
                    started = True
                    silence = 0.0
                elif started:
                    silence += block
                total = len(frames) * block
                if started and silence >= SILENCE_S:
                    break
                if total >= max_seconds:
                    break
                if not started and total >= no_speech_timeout:
                    break  # never spoke

        audio = np.concatenate(frames, axis=0)
        buf = io.BytesIO()
        sf.write(buf, audio, MIC_RATE, format="WAV", subtype="PCM_16")
        return buf.getvalue()


def pcm_to_wav(pcm: bytes, rate: int = TTS_RATE) -> bytes:
    import soundfile as sf

    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    buf = io.BytesIO()
    sf.write(buf, audio, rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


class Speaker:
    def play_pcm(self, pcm: bytes, rate: int = TTS_RATE) -> None:
        import sounddevice as sd

        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(audio, rate)
        sd.wait()

    def play_wav_file(self, path: Path) -> None:
        import sounddevice as sd
        import soundfile as sf

        audio, rate = sf.read(str(path), dtype="float32")
        sd.play(audio, rate)
        sd.wait()


# --------------------------------------------------------------------------
# Intent routing -> tool calls
# --------------------------------------------------------------------------

_FLIGHT_NO = re.compile(r"\b([A-Za-z]{2})\s?(\d{1,4})\b")
_IATA = re.compile(r"\b([A-Z]{3})\b")


_TIME_TAIL = re.compile(
    r"\b(?:in \d+ (?:hours?|hrs?|minutes?|mins?|stunden|minuten|heures?)|"
    r"next \d+ \w+|within \d+ \w+|today|tomorrow|tonight|"
    r"this (?:morning|afternoon|evening)|right now|"
    r"heute|morgen|jetzt|demain|maintenant|ce soir)\b.*$",
    re.IGNORECASE,
)


def _clean_name(value: str) -> str:
    name = _TIME_TAIL.sub("", value)
    return name.strip().strip("?!.,;:'\" ").strip()


def _parse_station_pair(text: str) -> tuple[str | None, str | None]:
    t = _norm(text)
    for pattern in (
        r"\bfrom (.+?) to (.+)$",
        r"\b(.+?) nach (.+)$",
        r"\bde (.+?) a (.+)$",
        r"\b(.+?) to (.+)$",
    ):
        m = re.search(pattern, t)
        if m:
            return _clean_name(m.group(1)), _clean_name(m.group(2))
    return None, None


_GUIDANCE_KEYWORDS = {
    "arrival_process": ["arrival process", "landside", "after landing", "customs", "passport"],
    "transfers": ["transfer", "connecting flight", "umsteig", "correspondance"],
    "baggage": ["baggage", "luggage", "gepack", "bagages", "suitcase"],
    "airport_rail_access": ["rail access", "train to the airport", "airport station"],
    "flight_status_verification": ["verify flight", "flight status source"],
}


def route_intent(text: str, tools: "ToolBox") -> tuple[str, object]:
    """Map a transcript to a tool call. Returns (tool_name, result)."""
    t = _norm(text)
    flight_m = _FLIGHT_NO.search(text)

    if any(w in t for w in ("flight", "flug", "vol ", "volo", "plane", "airport", "flughafen")):
        if "train" in t or "zug" in t or "onward" in t:
            _, dest = _parse_station_pair(text)
            if dest is None:
                m = re.search(r"\bto ([a-zA-Z .\-']+)$", text, re.IGNORECASE)
                dest = _clean_name(m.group(1)) if m else None
            if dest:
                return "connect_flight_to_train", tools.connect_flight_to_train(
                    dest,
                    45,
                    flight_m.group(0).replace(" ", "").upper() if flight_m else None,
                    date.today().isoformat() if flight_m else None,
                )
        if flight_m:
            direction = "arrival" if any(w in t for w in ("arriv", "ankunft")) else (
                "departure" if any(w in t for w in ("depart", "abflug")) else None
            )
            return "find_flight_by_number", tools.find_flight_by_number(
                flight_m.group(0).replace(" ", "").upper(),
                date.today().isoformat(),
                direction,
            )
        for topic, keys in _GUIDANCE_KEYWORDS.items():
            if any(k in t for k in keys):
                return "get_airport_guidance", tools.get_airport_guidance(topic)
        m = _IATA.search(text.upper())
        if m and any(w in t for w in ("arriv", "depart", "flights")):
            direction = "arrival" if "arriv" in t else "departure"
            return "search_airport_flights", tools.search_airport_flights(
                direction, date.today().isoformat(), m.group(1), None, None, 10
            )
        return "get_airport_guidance", tools.get_airport_guidance("arrival_process")

    if any(w in t for w in ("disruption", "delayed", "cancelled", "storing", "storung",
                            "perturbation", "incident", "ausfall", "verspatung")):
        m = re.search(r"\b(?:at|in|an|am) ([a-zA-Z0-9 .\-']+)$", text, re.IGNORECASE)
        station = _clean_name(m.group(1)) if m else text
        return "find_disruptions", tools.find_disruptions(station)

    if any(w in t for w in ("departure", "departures", "abfahrt", "depart",
                            "arrival", "arrivals", "ankunft", "arrivee", "board")):
        m = re.search(r"\b(?:from|at|in|von|ab|an) ([a-zA-Z0-9 .\-']+)$", text, re.IGNORECASE)
        station = _clean_name(m.group(1)) if m else ""
        mode = "arrivals" if any(w in t for w in ("arrival", "ankunft", "arrivee")) else "departures"
        return "get_station_board", tools.get_station_board(station, mode)

    origin, dest = _parse_station_pair(text)
    if origin and dest:
        return "find_connections", tools.find_connections(origin, dest)

    # Bare short utterance — e.g. a multi-turn clarification answer like
    # "bern hauptbahnhof": interpret as a departures-board query.
    if len(text.split()) <= 4:
        return "get_station_board", tools.get_station_board(
            _clean_name(text) or text, "departures")

    return "clarify", (
        "I can help with Swiss trains and station boards, disruptions, and "
        "Zurich airport flights. For example, ask: when is the next train "
        "from Bern to Zurich?"
    )


# --------------------------------------------------------------------------
# Spoken-answer rendering
# --------------------------------------------------------------------------

def _hhmm(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        return None


def _say(result: object) -> str:
    if isinstance(result, ConnectionSearchResult):
        if result.status != "ok":
            return _fallback(result.status, result.message, result.candidates)
        out = []
        for c in result.connections[:2]:
            dep, arr = _hhmm(c.departure), _hhmm(c.arrival)
            chg = "direct" if c.changes == 0 else f"{c.changes} change{'s' if c.changes > 1 else ''}"
            out.append(f"departure at {dep}, arriving {arr}, {c.duration_minutes} minutes, {chg}")
        return "Next connections: " + "; ".join(out) + ". Source: opentransportdata.swiss."

    if isinstance(result, StationBoardResult):
        if result.status != "ok":
            return _fallback(result.status, result.message, result.candidates)
        kind = "Departures" if result.event_type == "departure" else "Arrivals"
        items = []
        for e in result.events[:3]:
            t = _hhmm(e.estimated_time or e.planned_time)
            bit = f"{e.line or 'service'} to {e.direction_name or 'unknown'} at {t}"
            if e.platform:
                bit += f", platform {e.platform}"
            if e.delay_minutes:
                bit += f", {e.delay_minutes} minutes late"
            items.append(bit)
        return f"{kind} at {result.station_name}: " + "; ".join(items) + "."

    if isinstance(result, DisruptionSearchResult):
        if result.status != "ok":
            return _fallback(result.status, result.message, result.candidates)
        first = result.disruptions[0]
        return (
            f"{len(result.disruptions)} affected services found. "
            f"First: {first.title or 'unnamed disruption'}."
        )

    if isinstance(result, FlightLookupResult):
        if result.status != "answered":
            return _fallback(result.status, result.message, [])
        f = result.flight
        dep = _hhmm(f.departure.actual or f.departure.estimated or f.departure.scheduled)
        arr = _hhmm(f.arrival.actual or f.arrival.estimated or f.arrival.scheduled)
        gate = f.departure.gate or f.arrival.gate
        s = f"Flight {f.flight_number}: departs {dep}, arrives {arr}, status {f.flight_status or 'unknown'}"
        if gate:
            s += f", gate {gate}"
        return s + "."

    if isinstance(result, FlightSearchResult):
        if result.status != "answered":
            return _fallback(result.status, result.message, [])
        if not result.flights:
            return "No matching flights found."
        names = ", ".join(f.flight_number for f in result.flights[:3])
        return f"Found {len(result.flights)} flights: {names}."

    if isinstance(result, AirportGuidanceResult):
        if result.status != "answered":
            return _fallback(result.status, result.message, [])
        g = (result.guidance or "")[:400]
        return g + (" Source: flughafen-zuerich.ch." if result.source_url else "")

    if isinstance(result, FlightToTrainResult):
        if result.status != "answered":
            return _fallback(result.status, result.message, [])
        parts = [result.message or "Onward trains:"]
        for c in result.train_connections[:2]:
            dep, arr = _hhmm(c.departure), _hhmm(c.arrival)
            parts.append(f"train at {dep} arriving {arr}")
        return " ".join(parts)

    return str(result)


def _fallback(status: str, message: str | None, candidates: list) -> str:
    if status in ("needs_clarification", "needs_context") and candidates:
        names = ", ".join(c.name for c in candidates[:3])
        return f"{message or 'Please clarify.'} Did you mean: {names}?"
    return message or "Sorry, I could not answer that."


# --------------------------------------------------------------------------
# Tool wiring
# --------------------------------------------------------------------------

class ToolBox:
    """Thin facade matching the MCP tool surface, callable in-process."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ojp = OjpClient(settings)
        self.aviation = AerodataboxClient(settings)

    def find_connections(self, origin, destination, departure_time=None,
                         arrival_time=None, results=3):
        return find_train_connections(
            origin, destination, departure_time, arrival_time, results,
            client=self.ojp, settings=self.settings)

    def get_station_board(self, station, mode="departures", when=None, results=5):
        return get_station_board(station, mode, when, results,
                                 client=self.ojp, settings=self.settings)

    def find_disruptions(self, stop):
        return find_station_disruptions(stop, client=self.ojp, settings=self.settings)

    def find_flight_by_number(self, number, flight_date, direction=None):
        return find_flight_by_number(number, flight_date, direction,
                                     client=self.aviation, settings=self.settings)

    def search_airport_flights(self, direction, flight_date, iata=None,
                               icao=None, airline=None, limit=10):
        return search_airport_flights(direction, flight_date, iata, icao,
                                      airline, limit, client=self.aviation,
                                      settings=self.settings)

    def get_airport_guidance(self, topic):
        return get_airport_guidance(topic)

    def connect_flight_to_train(self, destination, buffer, flight_number=None,
                                flight_date=None, confirmed_arrival=None):
        return connect_flight_to_train(
            flight_number, flight_date, confirmed_arrival, destination,
            buffer, 3, aviation_client=self.aviation, ojp_client=self.ojp,
            settings=self.settings)


# --------------------------------------------------------------------------
# LLM brain — OpenAI-compatible function calling + multi-turn memory
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a Swiss public-transport voice assistant. You answer
questions about Swiss trains, station departure/arrival boards, service
disruptions, and Zurich Airport (ZRH) flights, using the provided tools for
all real data. Rules:
- Reply in the user's language (English, German, French, Italian).
- Keep every reply short — 1 to 3 spoken sentences. No markdown, no lists,
  no emoji; it will be read aloud by text-to-speech.
- If the request is ambiguous or incomplete (e.g. just a city name), ask ONE
  short clarifying question. Never guess station names or times.
- Once you know origin and destination, call find_connections immediately —
  assume "depart now" unless the user gave a time. Do not ask follow-up
  questions when you already have enough information to call a tool.
- For flight_date, default to today: {today}.
- Scope: Swiss domestic journeys, cross-border journeys touching
  Switzerland, and ZRH flights. Politely refuse anything else.
- When giving facts, briefly name the source (opentransportdata.swiss or
  aerodatabox.com)."""


def _fn(name, description, properties, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


_S = {"type": "string"}  # shorthand

TOOL_SCHEMAS = [
    _fn("find_connections",
        "Find Swiss train connections between two stations (domestic or "
        "cross-border touching Switzerland). Returns live OJP 2.0 data.",
        {"origin": _S, "destination": _S,
         "departure_time": _S, "arrival_time": _S,
         "results": {"type": "integer"}},
        ["origin", "destination"]),
    _fn("get_station_board",
        "Show upcoming departures or arrivals at a Swiss station.",
        {"station": _S,
         "mode": {"type": "string", "enum": ["departures", "arrivals"]},
         "when": _S, "results": {"type": "integer"}},
        ["station"]),
    _fn("find_disruptions",
        "Check current service disruptions at a Swiss station.",
        {"stop": _S}, ["stop"]),
    _fn("find_flight_by_number",
        "Look up a Zurich Airport flight by number and date (YYYY-MM-DD).",
        {"flight_number": _S, "flight_date": _S,
         "direction": {"type": "string", "enum": ["arrival", "departure"]}},
        ["flight_number", "flight_date"]),
    _fn("search_airport_flights",
        "Search ZRH arrivals or departures for a date, filtered by the other "
        "airport's IATA/ICAO code or an airline code.",
        {"direction": {"type": "string", "enum": ["arrival", "departure"]},
         "flight_date": _S, "airport_iata": _S, "airport_icao": _S,
         "airline_iata": _S, "limit": {"type": "integer"}},
        ["direction", "flight_date"]),
    _fn("get_airport_guidance",
        "Official Zurich Airport passenger guidance. Topics: "
        "arrival_process, transfers, baggage, airport_rail_access, "
        "flight_status_verification.",
        {"topic": _S}, ["topic"]),
    _fn("connect_flight_to_train",
        "Connect a ZRH flight arrival to onward Swiss trains, applying an "
        "explicit transfer buffer.",
        {"destination_station": _S,
         "transfer_buffer_minutes": {"type": "integer"},
         "flight_number": _S, "flight_date": _S,
         "confirmed_arrival_time": _S,
         "rail_results": {"type": "integer"}},
        ["destination_station"]),
]

MAX_TOOL_ROUNDS = 4


def _dispatch_tool(tools: ToolBox, name: str, args: dict) -> str:
    """Execute one LLM tool call against ToolBox; returns canonical JSON."""
    args = dict(args or {})
    today = date.today().isoformat()
    if name == "find_connections":
        r = tools.find_connections(
            args.get("origin", ""), args.get("destination", ""),
            args.get("departure_time"), args.get("arrival_time"),
            int(args.get("results") or 3))
    elif name == "get_station_board":
        r = tools.get_station_board(
            args.get("station", ""), args.get("mode") or "departures",
            args.get("when"), int(args.get("results") or 5))
    elif name == "find_disruptions":
        r = tools.find_disruptions(args.get("stop", ""))
    elif name == "find_flight_by_number":
        r = tools.find_flight_by_number(
            args.get("flight_number", ""),
            args.get("flight_date") or today, args.get("direction"))
    elif name == "search_airport_flights":
        r = tools.search_airport_flights(
            args.get("direction", "departure"),
            args.get("flight_date") or today,
            args.get("airport_iata"), args.get("airport_icao"),
            args.get("airline_iata"), int(args.get("limit") or 10))
    elif name == "get_airport_guidance":
        r = tools.get_airport_guidance(args.get("topic", ""))
    elif name == "connect_flight_to_train":
        r = tools.connect_flight_to_train(
            args.get("destination_station", ""),
            int(args.get("transfer_buffer_minutes") or 45),
            args.get("flight_number"),
            args.get("flight_date") or (today if args.get("flight_number") else None),
            args.get("confirmed_arrival_time"))
    else:
        return json.dumps({"status": "error", "message": f"unknown tool {name}"})
    return r.model_dump_json()


class Conversation:
    """Multi-turn dialogue state: full chat history + tool-call loop.

    `brain` is a callable(messages) -> assistant message dict shaped like an
    OpenAI chat completion message ({role, content, tool_calls?}). The same
    loop therefore works with a real LLM and with the RegexBrain fallback.
    """

    def __init__(self, brain, tools: ToolBox) -> None:
        self.brain = brain
        self.tools = tools
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(today=date.today().isoformat())}
        ]

    def answer(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})
        for _ in range(MAX_TOOL_ROUNDS):
            msg = self.brain(self.messages)
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                content = msg.get("content") or "Sorry, I have no answer."
                self.messages.append({"role": "assistant", "content": content})
                return content
            self.messages.append(msg)
            for tc in tool_calls:
                fn = tc.get("function", {})
                try:
                    out = _dispatch_tool(self.tools, fn.get("name", ""),
                                         json.loads(fn.get("arguments") or "{}"))
                except Exception as exc:  # noqa: BLE001 - report honestly to the LLM
                    out = json.dumps({"status": "error", "message": str(exc)})
                self.messages.append(
                    {"role": "tool", "tool_call_id": tc.get("id", ""), "content": out}
                )
        return "Sorry, I could not complete that request."


def make_llm_brain(env=None):
    """Return an OpenAI-compatible brain callable, or None if no key.

    Auto-detects OPENAI_API_KEY (+ OPENAI_BASE_URL/OPENAI_MODEL overrides),
    GROQ_API_KEY, or OPENROUTER_API_KEY — any chat-completions+tools endpoint.
    """
    env = env if env is not None else os.environ
    key = (env.get("OPENAI_API_KEY") or "").strip()
    base_url = (env.get("OPENAI_BASE_URL") or "").strip() or None
    model = (env.get("OPENAI_MODEL") or "").strip() or "gpt-4o-mini"
    if not key:
        key = (env.get("GROQ_API_KEY") or "").strip()
        if key:
            base_url = "https://api.groq.com/openai/v1"
            model = (env.get("GROQ_MODEL") or "llama-3.3-70b-versatile").strip()
    if not key:
        key = (env.get("OPENROUTER_API_KEY") or "").strip()
        if key:
            base_url = "https://openrouter.ai/api/v1"
            model = (env.get("OPENROUTER_MODEL") or "openai/gpt-4o-mini").strip()
    if not key:
        return None

    from openai import OpenAI
    client = OpenAI(api_key=key, base_url=base_url)

    def brain(messages):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=TOOL_SCHEMAS,
            tool_choice="auto", temperature=0.3,
        )
        return resp.choices[0].message.model_dump(exclude_none=True)

    brain.model = model
    brain.provider = base_url or "api.openai.com"
    return brain


class RegexBrain:
    """Deterministic fallback when no LLM key is configured.

    Reuses route_intent/_say, plus one piece of multi-turn memory: a bare
    station name (e.g. "Zurich") triggers a clarifying question and stores
    it as a pending origin; the next utterance ("to Bern" / "Bern" /
    "departures") completes the intent.
    """

    def __init__(self, tools: ToolBox) -> None:
        self.tools = tools
        self.pending_station = None

    def __call__(self, messages):
        text = messages[-1]["content"]
        t = _norm(text)

        if self.pending_station:
            station = _canonical_station(self.pending_station)
            if any(w in t for w in ("departure", "arrival", "board", "abfahrt", "ankunft")):
                mode = "arrivals" if any(w in t for w in ("arrival", "ankunft")) else "departures"
                self.pending_station = None
                return self._say(self.tools.get_station_board(station, mode))
            m = re.search(r"\bto ([a-zA-Z0-9 .\-']+)$", t)
            dest = _clean_name(m.group(1)) if m else (
                _clean_name(t) if len(t.split()) <= 3 else None)
            if dest:
                self.pending_station = None
                return self._say(self.tools.find_connections(
                    station, _canonical_station(dest)))
            self.pending_station = None  # give up after one missed turn

        # Bare short utterance with no intent keyword -> clarify instead of
        # guessing (voice UX); "departures bern" still reaches route_intent.
        _kw = ("depart", "arriv", "board", "abfahrt", "ankunft", "arrivee",
               "train", "zug", "connection", "verbindung", "disruption",
               "delayed", "cancelled", "storing", "storung", "perturbation",
               "flight", "flug", "vol", "volo", "airport", "flughafen")
        if (len(t.split()) <= 3 and not _parse_station_pair(text)[0]
                and not any(w in t for w in _kw)):
            station = _clean_name(t)
            if station:
                self.pending_station = station
                return {"role": "assistant", "content": (
                    f"Sure — do you want the departures board at "
                    f"{station.title()}, or a connection from "
                    f"{station.title()} to another city?")}

        name, result = route_intent(text, self.tools)
        return self._say(result if name != "clarify" else None, clarify=result)

    def _say(self, result, clarify=None):
        text = clarify if result is None else _say(result)
        return {"role": "assistant", "content": text}


# --------------------------------------------------------------------------
# Assistant loop
# --------------------------------------------------------------------------

class Assistant:
    def __init__(self, tools, speech=None, recorder=None, speaker=None,
                 speak: bool = True, conversation: Conversation | None = None) -> None:
        self.tools = tools
        self.speech = speech
        self.recorder = recorder
        self.speaker = speaker
        self.speak_enabled = speak
        self.conversation = conversation or Conversation(RegexBrain(tools), tools)

    def listen(self) -> str:
        wav = self.recorder.record_utterance()
        return self.speech.transcribe(wav)

    def answer(self, text: str) -> str:
        spoken = self.conversation.answer(text)
        print(f"assistant> {spoken}", flush=True)
        return spoken

    def say(self, text: str) -> None:
        if self.speak_enabled and self.speech and self.speaker:
            self.speaker.play_pcm(self.speech.synthesize(text))


class _SpyTools:
    """Wraps ToolBox and records every tool invocation."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.calls: list[str] = []

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def wrapper(*a, **k):
            self.calls.append(name)
            return attr(*a, **k)

        return wrapper


def _self_test(tools, speech, speaker, out_dir: Path, brain) -> int:
    """Live end-to-end check of every pipeline stage.

    Real mic capture (ambient), a real speech round-trip through Scribe STT
    (synthesized voice -> WAV -> transcribe), multi-turn conversation with
    real tool calls, real TTS, real speaker playback."""
    checks = []

    # 1. Real microphone capture — verifies the input device opens and
    #    produces valid WAV audio (ambient sound; speech not required).
    try:
        wav = MicRecorder().record_utterance(max_seconds=4.0, no_speech_timeout=4.0)
        ok = wav.startswith(b"RIFF") and len(wav) > 10_000
        checks.append((f"mic-capture ({len(wav)} bytes)", ok))
    except Exception as exc:  # noqa: BLE001
        checks.append((f"mic-capture FAILED: {exc}", False))

    # 2. Real STT round-trip — synthesize a question, wrap as WAV, send it
    #    through the exact transcribe() path the mic feeds.
    transcript = ""
    probe = "When is the next train from Bern to Zurich HB?"
    try:
        wav = pcm_to_wav(speech.synthesize(probe))
        transcript = speech.transcribe(wav)
        ok = "bern" in transcript.lower() and "zurich" in _norm(transcript)
        checks.append((f"stt-roundtrip ({transcript!r})", ok))
    except Exception as exc:  # noqa: BLE001
        checks.append((f"stt-roundtrip FAILED: {exc}", False))

    # 3. Multi-turn conversation: "Zurich" alone must trigger a clarifying
    #    question; subsequent turns must complete the intent and execute
    #    find_connections via the active brain (LLM or fallback).
    ok = True
    spy = _SpyTools(tools)
    if isinstance(brain, RegexBrain):
        brain = RegexBrain(spy)  # RegexBrain calls tools directly — spy it
    conversation = Conversation(brain, spy)
    assistant = Assistant(spy, speech, recorder=None, speaker=speaker,
                          conversation=conversation)
    script = ["Zurich", "to Geneva", "as soon as possible", "right now"]
    answers = []
    for t in script:
        if "find_connections" in spy.calls:
            break  # intent fulfilled — stop the dialogue
        try:
            answers.append(assistant.answer(t))
        except Exception as exc:  # noqa: BLE001
            ok = False
            answers.append("")
            print(f"  '{t}' -> ERROR: {exc}", flush=True)
    clarifying = "?" in (answers[0] or "")
    called_connections = "find_connections" in spy.calls
    checks.append((f"turn1-clarifies ({answers[0][:80]!r})", ok and clarifying))
    checks.append((f"tool-called-in-dialogue ({spy.calls}) -> "
                   f"{answers[-1][:80]!r}", ok and called_connections))
    checks.append(("goodbye-detected", is_goodbye("goodbye")))

    # 4. Real TTS + real speaker playback of the answer.
    try:
        pcm = speech.synthesize(answers[0])
        wav_path = out_dir / "selftest_reply.wav"
        wav_path.write_bytes(pcm_to_wav(pcm))
        checks.append((f"tts-synthesis ({len(pcm)} bytes)", len(pcm) > 1000))
        speaker.play_pcm(pcm)
        checks.append((f"speaker-playback (saved {wav_path.name})", True))
    except Exception as exc:  # noqa: BLE001
        checks.append((f"tts/playback FAILED: {exc}", False))

    print("\nSelf-test results:")
    failed = 0
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        failed += not passed
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", action="store_true", help="type instead of speaking")
    parser.add_argument("--mute", action="store_true", help="print answers, no TTS/playback")
    parser.add_argument("--self-test", action="store_true", help="mock end-to-end pipeline check")
    parser.add_argument("--list-devices", action="store_true")
    args = parser.parse_args()

    if args.list_devices:
        import sounddevice as sd
        print(sd.query_devices())
        return 0

    key = load_elevenlabs_key()
    if not key:
        print("ELEVENLABS_API_KEY missing in .env / .env.local")
        return 1

    settings = Settings.from_env()
    speech = ElevenLabsSpeech(
        key, voice_id=os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    )
    tools = ToolBox(settings)
    speaker = Speaker()

    llm_brain = make_llm_brain()
    if llm_brain:
        print(f"[brain] LLM: {llm_brain.model} via {llm_brain.provider}", flush=True)
    else:
        print("[brain] no LLM key found (OPENAI/GROQ/OPENROUTER) — using "
              "deterministic routing fallback", flush=True)
    brain = llm_brain or RegexBrain(tools)
    conversation = Conversation(brain, tools)

    if args.self_test:
        return _self_test(tools, speech, speaker, BASE_DIR, brain)

    assistant = Assistant(
        tools, speech,
        recorder=None if args.text else MicRecorder(),
        speaker=speaker,
        speak=not args.mute,
        conversation=conversation,
    )

    greeting = (
        "Swiss travel assistant ready. Ask me about trains, station boards, "
        "disruptions, or Zurich airport flights. Say goodbye to stop."
    )
    print(greeting, flush=True)
    assistant.say(greeting)

    while True:
        try:
            if args.text:
                transcript = input("you> ").strip()
            else:
                print("listening...", flush=True)
                transcript = assistant.listen()
            if not transcript:
                continue
            print(f"you> {transcript}", flush=True)
            if is_goodbye(transcript):
                farewell = "Goodbye!"
                print(farewell, flush=True)
                assistant.say(farewell)
                break
            assistant.say(assistant.answer(transcript))
        except KeyboardInterrupt:
            print("\nstopped.")
            break
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on device/API errors
            print(f"[error] {exc}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
