from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone

from agent_backend.dispatch import UnknownToolError, dispatch
from agent_backend.tools_registry import TOOL_SCHEMAS
from agent_backend.widget_mapper import map_result

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
    "covered. Keep your own reply to "
    "one short sentence: the tool result is shown to the user as a "
    "visual card, so do not restate its details."
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
) -> Iterator[dict]:
    current_time = now or datetime.now(timezone.utc)
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(now=current_time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    chat_messages = [{"role": "system", "content": system_prompt}, *messages]

    for _ in range(_MAX_TOOL_ROUNDS):
        try:
            response = openai_client.chat.completions.create(
                model=model,
                messages=chat_messages,
                tools=TOOL_SCHEMAS,
            )
        except Exception as exc:  # SDK network/auth/rate-limit failure
            yield {
                "type": "widget",
                "tool": None,
                "status": "source_error",
                "data": {"message": f"The assistant service is unavailable: {exc}"},
            }
            yield {"type": "done"}
            return

        choice_message = response.choices[0].message
        tool_calls = list(choice_message.tool_calls or [])

        if choice_message.content:
            yield {"type": "token", "text": choice_message.content}

        if not tool_calls:
            yield {"type": "done"}
            return

        chat_messages.append(
            {
                "role": "assistant",
                "content": choice_message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.function.name, "arguments": call.function.arguments},
                    }
                    for call in tool_calls
                ],
            }
        )

        for tool_call in tool_calls:
            name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}

            try:
                result = dispatch(
                    name,
                    arguments,
                    ojp_client=ojp_client,
                    aviation_client=aviation_client,
                    settings=settings,
                    flight_fares_client=flight_fares_client,
                )
                mapped = map_result(name, result)
            except UnknownToolError:
                mapped = {
                    "widget_type": None,
                    "status": "source_error",
                    "data": {"message": f"Unknown tool requested: {name}"},
                }
            except Exception as exc:
                mapped = {
                    "widget_type": None,
                    "status": "source_error",
                    "data": {"message": f"{name} failed: {exc}"},
                }

            yield {
                "type": "widget",
                "tool": name,
                "status": mapped["status"],
                "data": mapped["data"],
            }

            chat_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(mapped["data"]),
                }
            )

    yield {"type": "token", "text": "I've reached the maximum number of steps for this request."}
    yield {"type": "done"}
