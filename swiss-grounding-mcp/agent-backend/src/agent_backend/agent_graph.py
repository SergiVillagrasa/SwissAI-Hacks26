from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agent_backend.dispatch import UnknownToolError, dispatch
from agent_backend.execution_events import ExecutionEventEmitter
from agent_backend.tools_registry import TOOL_SCHEMAS
from agent_backend.widget_mapper import map_result


class AgentState(TypedDict):
    chat_messages: list[dict]
    pending_tool_calls: list[object]
    round_count: int
    output_events: list[dict]
    outcome: str | None


@dataclass(frozen=True)
class AgentDependencies:
    openai_client: object
    ojp_client: object
    aviation_client: object
    flight_fares_client: object | None
    settings: object
    model: str
    emitter: ExecutionEventEmitter
    max_rounds: int


def build_agent_graph(dependencies: AgentDependencies):
    emitter = dependencies.emitter

    def call_model(state: AgentState) -> dict:
        round_number = state["round_count"] + 1
        node_id = f"model-{round_number}"
        events = [emitter.emit(
            "node_started",
            node_id=node_id,
            label="Understand request" if round_number == 1 else "Prepare response",
            status="running",
            summary="Interpreting your request" if round_number == 1 else "Preparing your travel answer",
        )]
        try:
            response = dependencies.openai_client.chat.completions.create(
                model=dependencies.model,
                messages=state["chat_messages"],
                tools=TOOL_SCHEMAS,
            )
        except Exception:
            events.extend([
                emitter.emit(
                    "node_failed",
                    node_id=node_id,
                    label="Assistant service",
                    status="failed",
                    summary="The assistant service is unavailable",
                ),
                {"type": "widget", "tool": None, "status": "source_error", "data": {"message": "The assistant service is unavailable."}},
            ])
            return {"output_events": events, "pending_tool_calls": [], "round_count": round_number, "outcome": "failed"}

        message = response.choices[0].message
        tool_calls = list(message.tool_calls or [])
        if message.content:
            events.append({"type": "token", "text": message.content})
        events.append(emitter.emit(
            "node_completed",
            node_id=node_id,
            label="Request understood" if tool_calls else "Response prepared",
            status="completed",
            summary="Selected the appropriate Swiss data source" if tool_calls else "Your answer is ready",
        ))
        messages = list(state["chat_messages"])
        if tool_calls:
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {"id": call.id, "type": "function", "function": {"name": call.function.name, "arguments": call.function.arguments}}
                    for call in tool_calls
                ],
            })
        return {
            "chat_messages": messages,
            "pending_tool_calls": tool_calls,
            "round_count": round_number,
            "output_events": events,
            "outcome": None if tool_calls else "completed",
        }

    def execute_tools(state: AgentState) -> dict:
        events: list[dict] = []
        messages = list(state["chat_messages"])
        for index, tool_call in enumerate(state["pending_tool_calls"]):
            name = tool_call.function.name
            node_id = f"tool-{state['round_count']}-{index + 1}"
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            events.append(emitter.emit(
                "tool_started",
                node_id=node_id,
                label=name.replace("_", " ").title(),
                status="running",
                summary="Checking authoritative Swiss travel data",
                tool=name,
                details=arguments,
            ))
            try:
                result = dispatch(
                    name,
                    arguments,
                    ojp_client=dependencies.ojp_client,
                    aviation_client=dependencies.aviation_client,
                    settings=dependencies.settings,
                    flight_fares_client=dependencies.flight_fares_client,
                )
                mapped = map_result(name, result)
                event_type = "tool_completed"
                summary = "Authoritative source returned a result"
            except UnknownToolError:
                mapped = {"status": "source_error", "data": {"message": f"Unknown tool requested: {name}"}}
                event_type = "tool_failed"
                summary = "The requested data tool is unavailable"
            except Exception:
                mapped = {"status": "source_error", "data": {"message": f"{name} failed"}}
                event_type = "tool_failed"
                summary = "The source request failed"
            events.extend([
                emitter.emit(
                    event_type,
                    node_id=node_id,
                    label=name.replace("_", " ").title(),
                    status="completed" if event_type == "tool_completed" else "failed",
                    summary=summary,
                    tool=name,
                ),
                {"type": "widget", "tool": name, "status": mapped["status"], "data": mapped["data"]},
            ])
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(mapped["data"])})
        return {"chat_messages": messages, "pending_tool_calls": [], "output_events": events}

    def route_after_model(state: AgentState) -> str:
        if state["outcome"] is not None:
            return "finish"
        if state["round_count"] >= dependencies.max_rounds:
            return "limit"
        return "execute_tools"

    def limit(state: AgentState) -> dict:
        return {
            "output_events": [{"type": "token", "text": "I've reached the maximum number of steps for this request."}],
            "outcome": "incomplete",
        }

    def finish(state: AgentState) -> dict:
        outcome = state["outcome"] or "completed"
        return {"output_events": [emitter.emit(
            "run_completed",
            node_id="run",
            label="Workflow complete",
            status="failed" if outcome == "failed" else "completed",
            summary="Your request could not be completed" if outcome == "failed" else "Your travel answer is ready",
            outcome=outcome,
        )]}

    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("limit", limit)
    graph.add_node("finish", finish)
    graph.add_edge(START, "call_model")
    graph.add_conditional_edges("call_model", route_after_model, {
        "execute_tools": "execute_tools",
        "limit": "limit",
        "finish": "finish",
    })
    graph.add_edge("execute_tools", "call_model")
    graph.add_edge("limit", "finish")
    graph.add_edge("finish", END)
    return graph.compile()
