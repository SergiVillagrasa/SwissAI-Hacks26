"""Mock end-to-end tests for the voice assistant pipeline.

No microphone, speaker, or ElevenLabs calls — recorder/STT/TTS/playback
boundaries are replaced by fakes; tool calls are replaced by a stub ToolBox.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import voice_assistant as va
from swiss_grounding_mcp.domain.models import (
    Connection,
    ConnectionSearchResult,
    StationBoardResult,
    StopCandidate,
    StopEvent,
)


class StubTools:
    def __init__(self):
        self.calls = []

    def find_connections(self, origin, destination, *a, **k):
        self.calls.append(("find_connections", origin, destination))
        return ConnectionSearchResult(
            status="ok",
            connections=[Connection(
                departure="2026-03-01T10:04:00+01:00",
                arrival="2026-03-01T11:00:00+01:00",
                duration_minutes=56, changes=0)],
        )

    def get_station_board(self, station, mode="departures", *a, **k):
        self.calls.append(("get_station_board", station, mode))
        return StationBoardResult(
            status="ok", station_name=station, event_type="departure",
            events=[StopEvent(line="IC1", direction_name="Genève",
                              planned_time="2026-03-01T10:32:00+01:00",
                              platform="7", delay_minutes=2)],
        )

    def find_disruptions(self, stop):
        self.calls.append(("find_disruptions", stop))
        from swiss_grounding_mcp.domain.models import DisruptionSearchResult
        return DisruptionSearchResult(status="not_found", message="none")

    def find_flight_by_number(self, number, flight_date, direction=None):
        self.calls.append(("find_flight_by_number", number))
        from swiss_grounding_mcp.domain.models import FlightLookupResult
        return FlightLookupResult(status="insufficient_evidence", message="none")

    def search_airport_flights(self, *a, **k):
        self.calls.append(("search_airport_flights", a))
        from swiss_grounding_mcp.domain.models import FlightSearchResult
        return FlightSearchResult(status="answered", flights=[])

    def get_airport_guidance(self, topic):
        self.calls.append(("get_airport_guidance", topic))
        from swiss_grounding_mcp.domain.models import AirportGuidanceResult
        return AirportGuidanceResult(status="answered", topic=topic,
                                     guidance="Follow signs.", source_url="x")

    def connect_flight_to_train(self, dest, buffer, flight_number=None,
                                flight_date=None, confirmed_arrival=None):
        self.calls.append(("connect_flight_to_train", dest, flight_number))
        from swiss_grounding_mcp.domain.models import FlightToTrainResult
        return FlightToTrainResult(status="answered", message="trains found")


class FakeSpeech:
    def __init__(self):
        self.spoken = []

    def transcribe(self, wav: bytes) -> str:
        return "simulated transcript"

    def synthesize(self, text: str) -> bytes:
        self.spoken.append(text)
        return b"\x01\x02" * 4800  # fake pcm_24000


class FakeRecorder:
    def record_utterance(self) -> bytes:
        return b"RIFFfake-wav-bytes"


class FakeSpeaker:
    def __init__(self):
        self.played = []

    def play_pcm(self, pcm: bytes, rate: int = 24000) -> None:
        self.played.append((pcm, rate))


# -- microphone simulation --------------------------------------------------

def test_fake_recorder_produces_wav_bytes():
    assert FakeRecorder().record_utterance().startswith(b"RIFF")


def test_listen_uses_recorder_and_stt():
    a = va.Assistant(StubTools(), FakeSpeech(), FakeRecorder(), FakeSpeaker())
    assert a.listen() == "simulated transcript"


# -- intent routing ---------------------------------------------------------

@pytest.mark.parametrize("text", [
    "When is the next train from Bern to Zurich?",
    "Bern nach Zurich",
    "I want to go from Lausanne to Geneva",
])
def test_routes_to_find_connections(text):
    tools = StubTools()
    name, result = va.route_intent(text, tools)
    assert name == "find_connections"
    assert tools.calls[0][0] == "find_connections"
    assert result.status == "ok"


@pytest.mark.parametrize("text,mode", [
    ("departures from Zurich HB", "departures"),
    ("arrivals at Bern", "arrivals"),
    ("Abfahrten ab Basel SBB", "departures"),
])
def test_routes_to_station_board(text, mode):
    tools = StubTools()
    name, _ = va.route_intent(text, tools)
    assert name == "get_station_board"
    assert tools.calls[0][2] == mode


@pytest.mark.parametrize("text,expected_station", [
    ("departures from bern next 2 hours", "bern"),
    ("departures from bern in 30 minutes", "bern"),
    ("departures from Bern tomorrow", "bern"),
    ("Abfahrten ab Basel SBB heute", "basel sbb"),
])
def test_board_station_strips_time_qualifiers(text, expected_station):
    tools = StubTools()
    va.route_intent(text, tools)
    assert tools.calls[0][1].lower() == expected_station


def test_routes_to_disruptions():
    tools = StubTools()
    name, _ = va.route_intent("any disruptions at Bern?", tools)
    assert name == "find_disruptions"


def test_routes_to_flight_by_number():
    tools = StubTools()
    name, _ = va.route_intent("what is the status of flight LX14?", tools)
    assert name == "find_flight_by_number"
    assert tools.calls[0][1] == "LX14"


def test_routes_to_guidance():
    tools = StubTools()
    name, _ = va.route_intent("how do airport transfers work?", tools)
    assert name == "get_airport_guidance"
    assert tools.calls[0][1] == "transfers"


def test_unmatched_returns_clarify():
    name, msg = va.route_intent("what is the weather today?", StubTools())
    assert name == "clarify"
    assert "trains" in msg


# -- goodbye ----------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "goodbye", "bye bye", "tschüss", "au revoir", "arrivederci", "stop listening",
])
def test_goodbye_detected(text):
    assert va.is_goodbye(text)


@pytest.mark.parametrize("text", ["from Bern to Zurich", "departures at Bern"])
def test_not_goodbye(text):
    assert not va.is_goodbye(text)


# -- rendering --------------------------------------------------------------

def test_connection_rendered_for_speech():
    text = va._say(StubTools().find_connections("Bern", "Zurich"))
    assert "10:04" in text and "direct" in text and "opentransportdata" in text


def test_board_rendered_with_platform_and_delay():
    text = va._say(StubTools().get_station_board("Zurich HB"))
    assert "IC1" in text and "platform 7" in text and "2 minutes late" in text


def test_needs_clarification_speaks_candidates():
    r = ConnectionSearchResult(
        status="needs_clarification",
        message="Which station?",
        candidates=[StopCandidate(name="Bellevue Zürich", stop_ref="ch:1")],
    )
    assert "Bellevue Zürich" in va._say(r)


# -- full pipeline (all boundaries faked) ------------------------------------

def test_end_to_end_turn_pipeline():
    speech, speaker, tools = FakeSpeech(), FakeSpeaker(), StubTools()
    a = va.Assistant(tools, speech, FakeRecorder(), speaker)
    transcript = a.listen()                       # simulated mic + STT
    assert transcript == "simulated transcript"
    answer = a.answer("from Bern to Zurich")      # routing + tool + render
    a.say(answer)                                 # TTS + playback
    assert tools.calls[0][0] == "find_connections"
    assert speech.spoken == [answer]
    assert speaker.played == [(b"\x01\x02" * 4800, 24000)]


def test_mute_mode_skips_tts_and_playback():
    speech, speaker = FakeSpeech(), FakeSpeaker()
    a = va.Assistant(StubTools(), speech, FakeRecorder(), speaker, speak=False)
    a.say("hello")
    assert speech.spoken == [] and speaker.played == []


# -- API key handling ---------------------------------------------------------

def test_key_dedupes_doubled_paste():
    key = "sk_abcdef" * 2
    assert va.load_elevenlabs_key({"ELEVENLABS_API_KEY": key}) == "sk_abcdef"


def test_key_fallback_name_and_whitespace():
    env = {"ELEVEN_LABS_API_KEY": ' "sk_xyz" '}
    assert va.load_elevenlabs_key(env) == "sk_xyz"


def test_missing_key_returns_empty():
    assert va.load_elevenlabs_key({}) == ""


# -- conversational brain ----------------------------------------------------

class FakeLLMBrain:
    """Scripted OpenAI-shaped brain: first call requests a tool, second
    returns final text once a tool result exists in history."""

    def __init__(self):
        self.invocations = 0

    def __call__(self, messages):
        self.invocations += 1
        if not any(m.get("role") == "tool" for m in messages):
            return {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "find_connections",
                             "arguments": '{"origin":"Zurich","destination":"Bern"}'},
            }]}
        return {"role": "assistant", "content": "Direct train to Bern at 10:04."}


def test_conversation_executes_tool_calls_and_keeps_history():
    tools = StubTools()
    brain = FakeLLMBrain()
    conv = va.Conversation(brain, tools)
    out = conv.answer("train from zurich to bern please")
    assert tools.calls[0][0] == "find_connections"
    assert tools.calls[0][1] == "Zurich" and tools.calls[0][2] == "Bern"
    roles = [m["role"] for m in conv.messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    assert out == "Direct train to Bern at 10:04."
    assert brain.invocations == 2


def test_conversation_plain_reply_without_tools():
    conv = va.Conversation(lambda msgs: {"role": "assistant", "content": "Hi!"},
                           StubTools())
    assert conv.answer("hello") == "Hi!"
    assert len(conv.messages) == 3


def test_tool_error_reported_back_to_brain():
    class BoomTools(StubTools):
        def find_disruptions(self, stop):
            raise RuntimeError("ojp down")

    def brain(messages):
        if not any(m.get("role") == "tool" for m in messages):
            return {"role": "assistant", "content": None, "tool_calls": [{
                "id": "c", "type": "function",
                "function": {"name": "find_disruptions",
                             "arguments": '{"stop":"Bern"}'}}]}
        tool_msg = [m for m in messages if m.get("role") == "tool"][-1]
        assert '"error"' in tool_msg["content"] and "ojp down" in tool_msg["content"]
        return {"role": "assistant", "content": "The data source is down."}

    conv = va.Conversation(brain, BoomTools())
    assert conv.answer("disruptions at bern?") == "The data source is down."


def test_regexbrain_bare_station_asks_clarifying_question():
    tools = StubTools()
    conv = va.Conversation(va.RegexBrain(tools), tools)
    a1 = conv.answer("Zurich")
    assert "?" in a1 and "departures" in a1.lower() and "connection" in a1.lower()
    assert tools.calls == []  # no guessing


def test_regexbrain_pending_station_then_destination():
    tools = StubTools()
    conv = va.Conversation(va.RegexBrain(tools), tools)
    conv.answer("Zurich")
    a2 = conv.answer("to Bern")
    assert tools.calls[-1][:3] == ("find_connections", "Zürich HB", "Bern")
    assert "10:04" in a2


def test_regexbrain_pending_station_then_board():
    tools = StubTools()
    conv = va.Conversation(va.RegexBrain(tools), tools)
    conv.answer("Zurich")
    conv.answer("departures please")
    assert tools.calls[-1][:3] == ("get_station_board", "Zürich HB", "departures")


def test_regexbrain_short_intent_not_swallowed_by_clarify():
    tools = StubTools()
    conv = va.Conversation(va.RegexBrain(tools), tools)
    conv.answer("departures bern")
    assert tools.calls[0][0] == "get_station_board"


def test_make_llm_brain_returns_none_without_keys():
    assert va.make_llm_brain({}) is None


def test_make_llm_brain_detects_groq():
    brain = va.make_llm_brain({"GROQ_API_KEY": "gsk_test", "GROQ_MODEL": "m"})
    assert brain is not None and brain.provider == "https://api.groq.com/openai/v1"
