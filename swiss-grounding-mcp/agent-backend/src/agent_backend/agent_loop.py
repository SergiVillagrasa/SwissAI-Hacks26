from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import uuid4

from agent_backend.agent_graph import AgentDependencies, build_agent_graph
from agent_backend.execution_events import ExecutionEventEmitter

_SYSTEM_PROMPT_TEMPLATE = (
    "You are the Swiss Grounding travel assistant. The current date and "
    "time is {now} (UTC). Use this as the anchor for any relative time "
    "expression the user gives (e.g. 'tomorrow', 'this weekend', 'next "
    "Friday') and pass an absolute ISO 8601 date/time to tools -- never "
    "guess a date from memory. Use the provided tools for any question "
    "about Swiss train connections, station boards, fares, disruptions, "
    "Zurich Airport (ZRH) flights, or domestic Swiss flight fares. Never "
    "answer a travel question from memory; always call the matching tool. "
    "For anything outside these topics, say honestly that it is not "
    "covered. Keep your own reply to one short sentence: the tool result "
    "is shown to the user as a visual card, so do not restate its details.\n\n"
    "DISAMBIGUATION: When a tool returns status 'needs_clarification' "
    "with a list of candidate station names, the user's next message "
    "will be the exact candidate name they chose. You MUST re-call the "
    "same tool using that exact name as the station parameter (origin or "
    "destination). Do NOT paraphrase, shorten, or alter the chosen name. "
    "Do NOT ask for further confirmation -- proceed with the search immediately."
)

_MAX_TOOL_ROUNDS = 4


def run_chat(
    messages: list[dict],
    *,
    openai_client,
    ojp_client,
    aviation_client,
    settings,
    model: str,
    flight_fares_client=None,
    now: datetime | None = None,
    run_id: str | None = None,
) -> Iterator[dict]:
    current_time = now or datetime.now(timezone.utc)
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(now=current_time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    emitter = ExecutionEventEmitter(run_id or str(uuid4()))
    yield emitter.emit(
        "run_started",
        node_id="run",
        label="Workflow started",
        status="running",
        summary="Starting your request",
    )
    graph = build_agent_graph(AgentDependencies(
        openai_client=openai_client,
        ojp_client=ojp_client,
        aviation_client=aviation_client,
        flight_fares_client=flight_fares_client,
        settings=settings,
        model=model,
        emitter=emitter,
        max_rounds=_MAX_TOOL_ROUNDS,
    ))
    initial_state = {
        "chat_messages": [{"role": "system", "content": system_prompt}, *messages],
        "pending_tool_calls": [],
        "round_count": 0,
        "output_events": [],
        "outcome": None,
    }
    for update in graph.stream(initial_state, stream_mode="updates"):
        for node_update in update.values():
            yield from node_update.get("output_events", [])
    yield {"type": "done"}
