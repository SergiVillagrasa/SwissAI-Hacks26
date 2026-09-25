# Workflow Execution Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separate, read-only Workflow page that visualizes frontend-initiated agent runs live with LangGraph and React Flow without changing the standalone MCP contract.

**Architecture:** The agent backend replaces its handwritten orchestration loop with a small LangGraph while preserving the `run_chat()` generator and existing token/widget event contract. A backend adapter emits sanitized, sequenced execution events; a frontend reducer above the two page surfaces keeps the current run alive while users move between Home and Workflow. The Workflow page projects that state into custom, non-editable React Flow nodes styled after the approved white-and-green reference.

**Tech Stack:** Python 3.10+, FastAPI, OpenAI Python SDK, LangGraph 1.2.x, pytest, React 19, TypeScript 6, Vite 8, Tailwind CSS 3, `@xyflow/react` 12.11.6, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-25-workflow-execution-graph-design.md`

## Global Constraints

- LangGraph belongs only to `swiss-grounding-mcp/agent-backend`; React Flow belongs only to `swiss-grounding-mcp/frontend`.
- Do not change MCP tool names, descriptions, argument schemas, result schemas, or transport behavior.
- Preserve existing `token`, `widget`, and `done` event shapes and widget-before-final-text ordering.
- Preserve the existing maximum of four model/tool rounds.
- Raw LangGraph events, prompts, credentials, provider payloads, stack traces, and hidden reasoning must never reach the frontend.
- Workflow visual-event failures must never terminate the underlying model or tool execution.
- Workflow stores only the current frontend-initiated run; refresh and backend-restart recovery remain out of scope.
- Home keeps its current liquid-glass visual treatment; the restrained white/green reference style applies only inside Workflow.
- Nodes are selectable and expandable but never draggable, connectable, deletable, or editable.
- Pin dependencies through the existing package managers. Use `langgraph==1.2.10` (published more than seven days before this plan) and `@xyflow/react@12.11.6` (published 2026-09-01).

## Review Focus

- A stream can deliver duplicate, stale, or unknown execution events; the reducer must ignore them without corrupting the latest valid state.
- Navigation during a live request can unmount route content; the stream consumer and run state must remain mounted above both pages.
- An SSE disconnect does not prove the tool failed; preserve the graph and mark only the visualization connection interrupted.
- Sanitized event details can receive unexpected mappings or exception strings; only allowlisted scalar display fields may cross the backend boundary.
- A model can return no tools, multiple tools, malformed arguments, or exhaust four rounds; every path must end with coherent graph and chat events.

---

### Task 1: Add orchestration and canvas dependencies

**Files:**
- Modify: `swiss-grounding-mcp/agent-backend/pyproject.toml`
- Modify: `swiss-grounding-mcp/agent-backend/uv.lock`
- Modify: `swiss-grounding-mcp/frontend/package.json`
- Modify: `swiss-grounding-mcp/frontend/package-lock.json`

**Interfaces:**
- Consumes: existing uv and npm project manifests.
- Produces: importable `langgraph.graph.StateGraph` and `@xyflow/react` APIs for later tasks.

- [ ] **Step 1: Add the backend dependency through uv**

Run:

```bash
cd swiss-grounding-mcp/agent-backend && uv add 'langgraph==1.2.10'
```

Expected: `pyproject.toml` and `uv.lock` record LangGraph 1.2.10; no server manifest changes.

- [ ] **Step 2: Verify the backend dependency imports**

Run:

```bash
cd swiss-grounding-mcp/agent-backend && uv run python -c 'from langgraph.graph import END, START, StateGraph; print("langgraph-ok")'
```

Expected: prints `langgraph-ok`.

- [ ] **Step 3: Add React Flow through npm**

Run:

```bash
npm --prefix swiss-grounding-mcp/frontend install @xyflow/react@12.11.6
```

Expected: frontend manifest and lockfile record exactly 12.11.6; no router dependency is added.

- [ ] **Step 4: Verify the unchanged baseline suites**

Run:

```bash
cd swiss-grounding-mcp/agent-backend && uv run pytest -q
npm --prefix swiss-grounding-mcp/frontend test -- --run
```

Expected: both existing suites pass before behavior changes.

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/agent-backend/pyproject.toml swiss-grounding-mcp/agent-backend/uv.lock swiss-grounding-mcp/frontend/package.json swiss-grounding-mcp/frontend/package-lock.json
git commit -m "build: add workflow graph dependencies"
```

### Task 2: Define and sanitize backend execution events

**Files:**
- Create: `swiss-grounding-mcp/agent-backend/src/agent_backend/execution_events.py`
- Create: `swiss-grounding-mcp/agent-backend/tests/test_execution_events.py`

**Interfaces:**
- Consumes: public labels, stable node IDs, optional safe scalar details.
- Produces: `ExecutionEventEmitter(run_id: str, now: Callable[[], datetime] | None = None)`, `emitter.emit(event_type, *, node_id, label, status, summary, **optional) -> dict`, and `sanitize_details(value: object) -> dict[str, str | int | float | bool | None]`.

- [ ] **Step 1: Write failing tests for sequence, timestamp, and allowlisting**

Create tests that assert:

```python
emitter = ExecutionEventEmitter("run-1", now=lambda: fixed_now)
first = emitter.emit("node_started", node_id="model-1", label="Understand request", status="running", summary="Interpreting your request")
second = emitter.emit("node_completed", node_id="model-1", label="Understand request", status="completed", summary="Request understood", duration_ms=12)
assert first["sequence"] == 1
assert second["sequence"] == 2
assert first["timestamp"] == "2026-09-25T10:15:30+00:00"
assert "duration_ms" not in first
assert second["duration_ms"] == 12

assert sanitize_details({"origin": "Bern", "count": 3, "nested": {"secret": "x"}, "items": [1]}) == {
    "origin": "Bern",
    "count": 3,
}
```

Also assert unsupported optional keys and exception objects are omitted, and an unsupported event type raises `ValueError` before serialization.

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```bash
cd swiss-grounding-mcp/agent-backend && uv run pytest tests/test_execution_events.py -v
```

Expected: FAIL because `agent_backend.execution_events` does not exist.

- [ ] **Step 3: Implement the event emitter**

Implement immutable allowlists:

```python
_EVENT_TYPES = {
    "run_started", "node_started", "node_completed", "node_skipped",
    "node_failed", "tool_started", "tool_completed", "tool_failed",
    "run_waiting", "run_completed",
}
_OPTIONAL_FIELDS = {"tool", "source", "duration_ms", "details", "outcome", "error"}
_SCALAR_TYPES = (str, int, float, bool, type(None))
```

`emit()` increments sequence only after validation, creates an ISO-8601 UTC timestamp, includes required fields, sanitizes `details`, and copies only allowlisted optional fields with scalar values. Keep the module independent of LangGraph so it can be tested without graph execution.

- [ ] **Step 4: Run the focused tests**

Run:

```bash
cd swiss-grounding-mcp/agent-backend && uv run pytest tests/test_execution_events.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/agent-backend/src/agent_backend/execution_events.py swiss-grounding-mcp/agent-backend/tests/test_execution_events.py
git commit -m "feat: define sanitized execution events"
```

### Task 3: Reproduce the current agent loop with LangGraph

**Files:**
- Create: `swiss-grounding-mcp/agent-backend/src/agent_backend/agent_graph.py`
- Create: `swiss-grounding-mcp/agent-backend/tests/test_agent_graph.py`
- Modify: `swiss-grounding-mcp/agent-backend/src/agent_backend/agent_loop.py`
- Modify: `swiss-grounding-mcp/agent-backend/tests/test_agent_loop.py`

**Interfaces:**
- Consumes: existing OpenAI client, `dispatch()`, `map_result()`, `TOOL_SCHEMAS`, service clients, settings, model, and optional clock.
- Produces: `build_agent_graph(dependencies: AgentDependencies) -> CompiledStateGraph`; keeps `run_chat(messages, *, ..., run_id=None, now=None) -> Iterator[dict]` as the compatibility facade.

- [ ] **Step 1: Write failing graph-routing tests**

Define fake OpenAI responses using the existing `_FakeOpenAI` helpers and assert:

```python
events = list(run_chat([...], openai_client=fake_openai, ..., run_id="run-1", now=fixed_now))
assert events[0]["type"] == "run_started"
assert [event["type"] for event in events if event["type"] in {"token", "widget", "done"}] == ["widget", "token", "done"]
assert next(event for event in events if event["type"] == "tool_started")["tool"] == "find_connections"
assert next(event for event in events if event["type"] == "run_completed")["outcome"] == "completed"
assert events[-1] == {"type": "done"}
```

Add separate tests for plain text with tool stages skipped, malformed JSON arguments becoming `{}`, unknown tools producing `tool_failed` plus the existing source-error widget, multiple tool calls retaining order, OpenAI failure producing `node_failed` and `run_completed(outcome="failed")`, clarification producing `run_waiting`, and four rounds producing `outcome="incomplete"`.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
cd swiss-grounding-mcp/agent-backend && uv run pytest tests/test_agent_graph.py tests/test_agent_loop.py -v
```

Expected: FAIL because execution events and LangGraph routing are not wired into `run_chat()`.

- [ ] **Step 3: Implement focused graph state and dependencies**

In `agent_graph.py`, define:

```python
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
```

Build nodes `call_model`, `execute_tools`, and `finish`. Use conditional routing after `call_model`; route back to `call_model` after tools. Keep external effects inside nodes and append public events to `output_events` in exact emission order.

- [ ] **Step 4: Preserve the facade and non-critical event emission**

Keep `_SYSTEM_PROMPT_TEMPLATE` and `_MAX_TOOL_ROUNDS = 4`. `run_chat()` creates a run ID when absent, builds the graph, invokes it, and yields `output_events` followed by exactly one `done` event. Wrap execution-event creation in a narrow fallback so a visualization serialization failure does not suppress token/widget output; do not catch or hide the existing model/tool error handling.

- [ ] **Step 5: Run focused and full backend tests**

Run:

```bash
cd swiss-grounding-mcp/agent-backend && uv run pytest tests/test_agent_graph.py tests/test_agent_loop.py -v
cd swiss-grounding-mcp/agent-backend && uv run pytest -q
```

Expected: all pass; original chat behavior assertions remain valid after filtering execution events.

- [ ] **Step 6: Commit**

```bash
git add swiss-grounding-mcp/agent-backend/src/agent_backend/agent_graph.py swiss-grounding-mcp/agent-backend/src/agent_backend/agent_loop.py swiss-grounding-mcp/agent-backend/tests/test_agent_graph.py swiss-grounding-mcp/agent-backend/tests/test_agent_loop.py
git commit -m "feat: orchestrate chat runs with LangGraph"
```

### Task 4: Stream run IDs and execution events through FastAPI

**Files:**
- Modify: `swiss-grounding-mcp/agent-backend/src/agent_backend/main.py`
- Modify: `swiss-grounding-mcp/agent-backend/tests/test_main.py`
- Modify: `swiss-grounding-mcp/agent-backend/README.md`

**Interfaces:**
- Consumes: `run_chat(..., run_id: str)` from Task 3.
- Produces: `/api/chat` SSE stream containing execution events plus the unchanged chat events.

- [ ] **Step 1: Write failing endpoint tests**

Update the mocked `fake_run_chat` to capture `run_id`, yield a representative `run_started`, token, `run_completed`, and `done`, and assert the response preserves that order. Add a missing-key test asserting a generated run ID, `run_started`, safe failure state, and `done` are emitted even when OpenAI is unavailable.

- [ ] **Step 2: Run endpoint tests and verify failure**

Run:

```bash
cd swiss-grounding-mcp/agent-backend && uv run pytest tests/test_main.py -v
```

Expected: FAIL because the endpoint does not create or pass a run ID and its missing-key path has no execution lifecycle.

- [ ] **Step 3: Implement endpoint run creation**

Generate `run_id = str(uuid.uuid4())` once per request and pass it to `run_chat()`. For the missing-key path, emit a sanitized `run_started`, the existing source-error widget, a failed `run_completed`, and `done`. Do not add a run ID to the request body or MCP arguments.

- [ ] **Step 4: Update endpoint documentation**

Document the added execution event family and state explicitly that clients may ignore unknown event types while `token`, `widget`, and `done` remain compatible.

- [ ] **Step 5: Run backend tests**

Run:

```bash
cd swiss-grounding-mcp/agent-backend && uv run pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add swiss-grounding-mcp/agent-backend/src/agent_backend/main.py swiss-grounding-mcp/agent-backend/tests/test_main.py swiss-grounding-mcp/agent-backend/README.md
git commit -m "feat: stream workflow lifecycle events"
```

### Task 5: Add typed current-run state and resilient event reduction

**Files:**
- Modify: `swiss-grounding-mcp/frontend/src/lib/types.ts`
- Modify: `swiss-grounding-mcp/frontend/src/lib/sse.test.ts`
- Create: `swiss-grounding-mcp/frontend/src/workflow/runState.ts`
- Create: `swiss-grounding-mcp/frontend/src/workflow/runState.test.ts`
- Create: `swiss-grounding-mcp/frontend/src/workflow/RunProvider.tsx`
- Create: `swiss-grounding-mcp/frontend/src/workflow/RunProvider.test.tsx`

**Interfaces:**
- Consumes: `AgentEvent` from `streamChat()`.
- Produces: `ExecutionEvent`, `RunState`, `runReducer(state, event)`, and `useRun(): { state, acceptEvent, markDisconnected }`.

- [ ] **Step 1: Define failing reducer tests**

Tests must cover:

```typescript
const started = event({ type: "run_started", run_id: "r1", sequence: 1, node_id: "run", status: "running" });
const running = event({ type: "node_started", run_id: "r1", sequence: 2, node_id: "tool-1", status: "running" });
const stale = event({ type: "node_completed", run_id: "r1", sequence: 1, node_id: "tool-1", status: "completed" });
expect(runReducer(runReducer(emptyRunState, started), running).nodes["tool-1"].status).toBe("running");
expect(runReducer(runReducer(runReducer(emptyRunState, started), running), stale).nodes["tool-1"].status).toBe("running");
```

Also test duplicate sequence rejection, events for an old run, unknown event types, new `run_started` replacing the prior run, ordered operation rows, completed state retention, and `markDisconnected` preserving node status while setting `connectionStatus: "interrupted"`.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
npm --prefix swiss-grounding-mcp/frontend test -- --run src/workflow/runState.test.ts src/lib/sse.test.ts
```

Expected: FAIL because workflow types and reducer do not exist.

- [ ] **Step 3: Add execution event types**

Extend `AgentEvent` with a discriminated `ExecutionEvent` whose `type` is the ten event names from the spec, `status` is `pending | running | completed | waiting_for_input | failed | skipped`, and optional values are explicitly typed. Do not use `any` for event payloads.

- [ ] **Step 4: Implement the pure reducer**

Represent nodes by stable ID plus an ordered `nodeOrder`. Accept a new run only on `run_started`; ignore stale sequences and foreign run IDs. Map `tool_*` events to operation rows under their owning node. Preserve only details already sanitized by the backend. Unknown runtime data returned by JSON parsing must be ignored by a type guard rather than cast into state.

- [ ] **Step 5: Implement the provider**

Use `useReducer` and expose stable callbacks. The provider contains no fetch call: `App` remains the stream owner and forwards each execution event through `acceptEvent`. `markDisconnected` only changes visualization connection status.

- [ ] **Step 6: Run focused frontend tests**

Run:

```bash
npm --prefix swiss-grounding-mcp/frontend test -- --run src/workflow/runState.test.ts src/workflow/RunProvider.test.tsx src/lib/sse.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add swiss-grounding-mcp/frontend/src/lib/types.ts swiss-grounding-mcp/frontend/src/lib/sse.test.ts swiss-grounding-mcp/frontend/src/workflow/runState.ts swiss-grounding-mcp/frontend/src/workflow/runState.test.ts swiss-grounding-mcp/frontend/src/workflow/RunProvider.tsx swiss-grounding-mcp/frontend/src/workflow/RunProvider.test.tsx
git commit -m "feat: track the current workflow run"
```

### Task 6: Add the two-page shell without interrupting Home

**Files:**
- Create: `swiss-grounding-mcp/frontend/src/navigation/usePage.ts`
- Create: `swiss-grounding-mcp/frontend/src/navigation/usePage.test.tsx`
- Create: `swiss-grounding-mcp/frontend/src/components/AppShell.tsx`
- Create: `swiss-grounding-mcp/frontend/src/components/AppShell.test.tsx`
- Create: `swiss-grounding-mcp/frontend/src/pages/HomePage.tsx`
- Modify: `swiss-grounding-mcp/frontend/src/App.tsx`
- Modify: `swiss-grounding-mcp/frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: existing Home UI and `RunProvider` from Task 5.
- Produces: `usePage(): { page: "home" | "workflow"; navigate(page): void }`, a two-item shell, and a Home page whose active stream remains owned above route content.

- [ ] **Step 1: Write failing navigation and stream-lifetime tests**

Test that Home is the default, clicking Workflow changes the URL to `/workflow` with `history.pushState`, browser `popstate` returns Home, and only Home/Workflow appear as primary navigation items. In `App.test.tsx`, use a controlled `ReadableStream`: submit from Home, navigate to Workflow before closing the stream, enqueue an execution event, return Home, enqueue a widget/token/done, and assert `fetch` was called exactly once and the final Home result rendered.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
npm --prefix swiss-grounding-mcp/frontend test -- --run src/navigation/usePage.test.tsx src/components/AppShell.test.tsx src/App.test.tsx
```

Expected: FAIL because no page shell exists.

- [ ] **Step 3: Implement lightweight History API navigation**

Normalize only `/workflow` to Workflow; every other path is Home. `navigate()` calls `history.pushState` and updates state. Subscribe to `popstate` and clean up the listener. This avoids adding a router dependency for two static client-side pages.

- [ ] **Step 4: Extract Home without moving stream ownership below the page boundary**

Move only Home presentation into `HomePage`. Keep turns, history, pending state, `handleSubmit`, and `streamChat()` in `App`, wrapped by `RunProvider`. For each execution event call `acceptEvent`; continue handling token/widget events exactly as before. In `catch`, call `markDisconnected()` before producing the existing Home fallback.

- [ ] **Step 5: Implement the shell and temporary Workflow placeholder**

Render the two-item navigation and route content. The placeholder reads current run state from `useRun()` so Task 7 can replace it without changing App ownership. Scope shell styling so Home's existing canvas remains unchanged.

- [ ] **Step 6: Run focused and full frontend tests**

Run:

```bash
npm --prefix swiss-grounding-mcp/frontend test -- --run src/navigation/usePage.test.tsx src/components/AppShell.test.tsx src/App.test.tsx
npm --prefix swiss-grounding-mcp/frontend test -- --run
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add swiss-grounding-mcp/frontend/src/navigation swiss-grounding-mcp/frontend/src/components/AppShell.tsx swiss-grounding-mcp/frontend/src/components/AppShell.test.tsx swiss-grounding-mcp/frontend/src/pages/HomePage.tsx swiss-grounding-mcp/frontend/src/App.tsx swiss-grounding-mcp/frontend/src/App.test.tsx
git commit -m "feat: add Home and Workflow navigation"
```

### Task 7: Build the read-only React Flow Workflow page

**Files:**
- Create: `swiss-grounding-mcp/frontend/src/pages/WorkflowPage.tsx`
- Create: `swiss-grounding-mcp/frontend/src/pages/WorkflowPage.test.tsx`
- Create: `swiss-grounding-mcp/frontend/src/workflow/ExecutionNode.tsx`
- Create: `swiss-grounding-mcp/frontend/src/workflow/ExecutionNode.test.tsx`
- Create: `swiss-grounding-mcp/frontend/src/workflow/toFlowElements.ts`
- Create: `swiss-grounding-mcp/frontend/src/workflow/toFlowElements.test.ts`
- Create: `swiss-grounding-mcp/frontend/src/styles/workflow.css`
- Modify: `swiss-grounding-mcp/frontend/src/components/AppShell.tsx`
- Modify: `swiss-grounding-mcp/frontend/src/styles/index.css`

**Interfaces:**
- Consumes: `RunState` and ordered run nodes from Task 5.
- Produces: `toFlowElements(state) -> { nodes: Node<ExecutionNodeData>[]; edges: Edge[] }`, `ExecutionNode`, and `WorkflowPage`.

- [ ] **Step 1: Write failing projection tests**

Assert that ordered run nodes become a horizontal Deployment Strip with stable IDs and orthogonal edges; repeated tool rounds receive distinct positions; pending/skipped/failed statuses map to explicit node data; empty state produces no nodes; and an operation row keeps only sanitized details.

- [ ] **Step 2: Write failing component tests**

Mock `@xyflow/react` at the component boundary and assert:

- Empty state contains `Go to Home`.
- Running and completed labels are visible as text.
- Operation details start collapsed and expand with `aria-expanded`.
- The canvas receives `nodesDraggable={false}`, `nodesConnectable={false}`, `elementsSelectable`, `fitView`, and no minimap.
- `Connection interrupted` appears without changing a running tool to failed.
- A polite live region announces state transitions.

- [ ] **Step 3: Run focused tests and verify failure**

Run:

```bash
npm --prefix swiss-grounding-mcp/frontend test -- --run src/workflow/toFlowElements.test.ts src/workflow/ExecutionNode.test.tsx src/pages/WorkflowPage.test.tsx
```

Expected: FAIL because Workflow rendering does not exist.

- [ ] **Step 4: Implement graph projection**

Use deterministic horizontal positions and a wider active node. Build `smoothstep` edges with green styling and no animation under reduced motion. Keep labels and details in node data so React Flow remains a rendering library rather than application state.

- [ ] **Step 5: Implement accessible custom nodes**

Render public label, summary, text status, status icon, and child operation rows. Expansion buttons use `aria-expanded`; rows use buttons rather than clickable divs. Include left/right handles but set connection behavior off at the canvas level.

- [ ] **Step 6: Implement the Workflow page and approved styling**

Import `@xyflow/react/dist/style.css` and `workflow.css`. Match the reference with a white surface, dotted canvas, restrained gray type, pale-green node borders, green orthogonal edges, compact status pills, and generous whitespace. Keep these selectors under `.workflow-page` so Home's liquid-glass styles do not change. Include Fit workflow controls and omit minimap.

- [ ] **Step 7: Run focused tests and mechanical frontend checks**

Run:

```bash
npm --prefix swiss-grounding-mcp/frontend test -- --run src/workflow/toFlowElements.test.ts src/workflow/ExecutionNode.test.tsx src/pages/WorkflowPage.test.tsx
npm --prefix swiss-grounding-mcp/frontend run lint
npm --prefix swiss-grounding-mcp/frontend run build
```

Expected: tests, lint, and build pass.

- [ ] **Step 8: Commit**

```bash
git add swiss-grounding-mcp/frontend/src/pages/WorkflowPage.tsx swiss-grounding-mcp/frontend/src/pages/WorkflowPage.test.tsx swiss-grounding-mcp/frontend/src/workflow/ExecutionNode.tsx swiss-grounding-mcp/frontend/src/workflow/ExecutionNode.test.tsx swiss-grounding-mcp/frontend/src/workflow/toFlowElements.ts swiss-grounding-mcp/frontend/src/workflow/toFlowElements.test.ts swiss-grounding-mcp/frontend/src/styles/workflow.css swiss-grounding-mcp/frontend/src/components/AppShell.tsx swiss-grounding-mcp/frontend/src/styles/index.css
git commit -m "feat: visualize live workflow execution"
```

### Task 8: Verify MCP isolation and the complete user journey

**Files:**
- Modify only if a discovered regression requires a scoped fix in files already named above.

**Interfaces:**
- Consumes: complete backend and frontend implementation.
- Produces: evidence that the feature works and the MCP contract remains unchanged.

- [ ] **Step 1: Run the server contract and registration tests**

Run:

```bash
cd swiss-grounding-mcp/server && uv run pytest tests/test_swisscom_compliance.py tests/unit/test_server_registration.py -v
```

Expected: PASS with no MCP schema changes.

- [ ] **Step 2: Run all backend and frontend tests**

Run:

```bash
cd swiss-grounding-mcp/agent-backend && uv run pytest -q
npm --prefix swiss-grounding-mcp/frontend test -- --run
```

Expected: PASS.

- [ ] **Step 3: Run frontend static verification**

Run:

```bash
npm --prefix swiss-grounding-mcp/frontend run lint
npm --prefix swiss-grounding-mcp/frontend run build
```

Expected: PASS.

- [ ] **Step 4: Run the app and inspect desktop and narrow layouts once**

Start backend and frontend using the documented project commands, submit a representative train request, navigate to Workflow while it runs, return Home for the widget, then reopen Workflow. Capture desktop and narrow screenshots in one inspection pass. Confirm the stream starts once, the completed graph remains, nodes cannot move, details expand, and Home retains its liquid-glass design.

- [ ] **Step 5: Run the Impeccable detector over changed frontend targets**

Run:

```bash
/home/sergi/.local/share/devin/cli/plugins/cache/github.com_pbakaus_impeccable-ec673bd7/4.3.1/.claude/skills/impeccable/scripts/impeccable detect --json swiss-grounding-mcp/frontend/src/components/AppShell.tsx swiss-grounding-mcp/frontend/src/pages/WorkflowPage.tsx swiss-grounding-mcp/frontend/src/workflow/ExecutionNode.tsx swiss-grounding-mcp/frontend/src/styles/workflow.css
```

Expected: no unresolved high-confidence findings. Fix findings in one bounded batch, rerun affected tests/build, and perform at most one confirmation screenshot pass.

- [ ] **Step 6: Review final diff for isolation and secrets**

Run:

```bash
git status --short
git diff --check
git diff --stat
git diff
```

Confirm no file under `swiss-grounding-mcp/server/` changed, except an explicitly justified regression fix; no credentials, raw traces, generated `.superpowers/` files, or screenshots are staged.

- [ ] **Step 7: Commit any verification fixes**

If verification required changes:

```bash
git add <only-the-files-fixed-during-verification>
git commit -m "fix: harden workflow execution view"
```

If no changes exist, do not create an empty commit.
