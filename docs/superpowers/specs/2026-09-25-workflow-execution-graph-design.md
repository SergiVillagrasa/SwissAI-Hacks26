# Swiss Grounding MCP — Workflow Execution Graph Design Spec

Status: approved by user on 2026-09-25, ready for implementation planning.

## 1. Purpose

Add a separate Workflow page that lets end users understand the progress of
requests submitted through the existing Home chat. The page presents the
current execution as a read-only graph: what stage is active, what has
completed, which authoritative Swiss source or tool is being used, and whether
the run needs input or encountered an error.

The feature is a trust and progress surface, not a developer trace viewer. It
must never expose hidden model reasoning, system prompts, credentials, raw
provider payloads, or stack traces.

Success means:

- The application has exactly two primary destinations: Home and Workflow.
- Home retains its existing chat, voice, liquid-glass styling, and widgets.
- A request submitted from Home immediately creates the current Workflow run.
- Navigation between Home and Workflow does not restart, cancel, or duplicate
  the request.
- Workflow advances live as the agent executes and retains its completed state
  until the next Home request starts.
- Tool and source details are understandable by default and safely expandable.
- The standalone MCP server and its public tool contract remain unchanged and
  independently usable by external MCP clients.

## 2. Scope

### In scope

- LangGraph orchestration in `swiss-grounding-mcp/agent-backend`.
- A stable, application-owned execution-event protocol over the existing SSE
  response.
- Shared current-run state above the Home and Workflow routes.
- A read-only React Flow canvas on the Workflow page.
- A two-item Home / Workflow navigation shell.
- Human-readable execution stages, expandable safe details, timing, status,
  accessibility, and failure states.
- Preservation of existing `token`, `widget`, and `done` behavior.

### Out of scope

- Changes to MCP tool names, descriptions, arguments, results, or transport.
- Visualization of requests initiated by external MCP clients.
- Conversation or workflow history.
- Persistence across a full browser refresh or backend restart.
- Editable graphs, draggable nodes, user-created edges, or workflow authoring.
- LangSmith as a runtime requirement.
- Display of chain-of-thought or private model reasoning.
- Parallel tool execution as part of the initial migration.

## 3. Architectural Boundary

```text
Frontend
  Application shell
    Home route       — existing chat and widgets
    Workflow route   — React Flow execution view
  Shared current-run store
            │
            │ application SSE events
            ▼
Agent backend
  LangGraph orchestration
  execution-event adapter
  existing dispatch and widget mapping
            │
            │ existing Python domain calls
            ▼
Shared server/domain implementation
            ▲
            │ MCP protocol
Standalone MCP server
```

LangGraph belongs only to `agent-backend`. React Flow belongs only to
`frontend`. The MCP server receives neither dependency and remains unaware of
runs, graph nodes, UI status, and visualization metadata.

The current agent backend imports the same underlying Python tool
implementation used by the MCP server rather than making an MCP transport hop.
That reuse remains valid. The LangGraph migration must wrap the agent backend's
orchestration around those calls, not move orchestration into MCP tools.

Visualization is non-critical. Failure to create, translate, transmit, or
render a progress event must not cancel the underlying model or tool operation.

## 4. Agent Graph

The initial graph reproduces the current bounded model/tool loop rather than
introducing new agent behavior.

```text
START
  ↓
call_model
  ├── no tool calls ───────────────→ finish
  └── tool calls
          ↓
      execute_tools
          ↓
      map_widgets
          ↓
      call_model
```

The current maximum of four model/tool rounds remains enforced through an
explicit graph step or recursion limit. Reaching it yields the existing
user-facing incomplete message and a completed run with an `incomplete`
outcome, rather than an endlessly running graph.

The public Workflow stages are a projection of this internal graph. They use
friendly labels and do not claim access to model thought:

1. Understand request
2. Choose action
3. Invoke Swiss tool
4. Verify result
5. Prepare response

Stages may be repeated or inserted for additional tool rounds. A model response
that needs no tool marks tool-related stages as `skipped`. The labels used for
a skipped stage depend on whether any tool has already run in an earlier
round of the same request: the first round uses "Invoke Swiss tool" / "Verify
result" (nothing was looked up at all), while later rounds use "Additional
Swiss tool call" / "Additional verification" (a tool already ran earlier and
this round simply didn't need another one) so the graph never implies that an
already-completed lookup was skipped. A clarification result marks the run
`waiting_for_input`; the next Home submission starts a new execution under the
existing conversation behavior. Durable LangGraph interrupt/resume semantics
are deferred with persistence.

## 5. Execution Event Contract

Raw LangGraph events never cross the backend boundary. An adapter emits an
allowlisted application protocol alongside the existing chat events.

Supported execution event types:

- `run_started`
- `node_started`
- `node_completed`
- `node_skipped`
- `node_failed`
- `tool_started`
- `tool_completed`
- `tool_failed`
- `run_waiting`
- `run_completed`

Every execution event includes:

```json
{
  "type": "node_started",
  "run_id": "opaque-run-id",
  "sequence": 4,
  "timestamp": "2026-09-25T10:15:30.000Z",
  "node_id": "invoke-tool-1",
  "label": "Check connections",
  "status": "running",
  "summary": "Searching authoritative Swiss transport data"
}
```

Optional fields are allowlisted by event type:

- `tool`: stable safe tool name.
- `source`: public source/provider name.
- `duration_ms`: completed operation duration.
- `details`: sanitized display key/value pairs.
- `outcome`: `completed`, `waiting`, `failed`, or `incomplete`.
- `error`: safe user-facing error summary.

`sequence` is monotonic within a run. The frontend ignores duplicate or stale
sequence numbers, preventing delayed SSE chunks from reverting graph state.
Unknown event types are ignored safely.

Existing events retain their established shapes:

- `token`
- `widget`
- `done`

`done` terminates the network stream. `run_completed` describes execution
state and must occur before `done` for a normally completed run.

## 6. Sanitization

The event adapter, not the frontend, is the security boundary. It may emit:

- Public stage labels and summaries.
- Tool names already exposed by the application.
- Sanitized route locations, station names, airport codes, dates, and times.
- Public source names and links.
- Duration and completion status.
- User-safe error summaries.

It must not emit:

- System or developer prompts.
- Hidden reasoning or chain-of-thought.
- Raw model request/response objects.
- Credentials, tokens, request headers, or environment values.
- Raw provider payloads.
- Internal exception text or stack traces.
- Arbitrary dictionaries supplied by tools without explicit mapping.

## 7. Frontend State and Navigation

A run-level provider lives above both routes and owns:

- Current `run_id`.
- Original user request summary.
- Ordered nodes and edges.
- Last accepted sequence number.
- Overall run status and outcome.
- Start time and completed duration.
- Connection status.

Home continues owning conversation turns and rendered widgets. Workflow consumes
the run projection. The active SSE consumer must also live above route-specific
content so route changes do not unmount it.

Submitting a Home request replaces the previous Workflow state with the new
run. A completed run remains visible until replacement. The first version does
not restore state after a full refresh and makes no persistence claim.

Client-side routing should avoid a full-page navigation. The application has
exactly two primary menu items:

- Home
- Workflow

## 8. Workflow Page Visual Design

The Workflow page deliberately uses the supplied reference's restrained
operational style only inside this route. Home preserves its existing blue
Apple Liquid Glass world.

Workflow visual language:

- White primary surface.
- Slim left navigation rail.
- Large, lightly dotted graph canvas.
- Compact near-white nodes with pale green borders.
- Orthogonal green connectors and small connection handles.
- Fine gray dividers and sparse typography.
- Small green status pills.
- Generous whitespace around the graph.
- No liquid-glass blur inside the Workflow content area.

The page anatomy is:

1. Navigation rail with product name, Home, and Workflow.
2. Run header with the request, timing, overall status, and Back to Home.
3. React Flow canvas containing the current Deployment Strip.
4. Empty state before the first run.

The selected composition is the **Deployment Strip**: a horizontal execution
journey in which the active stage expands to reveal operations while completed
stages compress into settled proof. This composition should match the supplied
reference closely without copying its product content.

## 9. React Flow Behavior

Use `@xyflow/react` with custom node components. React Flow owns:

- Node positioning.
- Orthogonal edge rendering.
- Pan and zoom.
- Initial fit-to-view.
- Responsive viewport behavior.

Application components own node content and state. Nodes are selectable and
expandable but not draggable, connectable, deletable, or editable. The canvas
provides a Fit workflow action. A minimap should be omitted unless real runs
become large enough to justify it.

Node states:

- `pending`: neutral gray, labeled Waiting.
- `running`: green emphasis and gentle pulse, labeled Running.
- `completed`: green check, labeled Completed.
- `waiting_for_input`: amber marker, labeled Needs input.
- `failed`: restrained red marker, labeled Failed.
- `skipped`: muted dashed treatment, labeled Not needed.

Color never communicates status alone. Text and icons accompany every state.
Completed nodes stop animating. Reduced-motion mode removes pulses and edge
drawing while preserving all status information.

Each node may contain operation rows. Selecting a row expands safe details
inline: tool, sanitized input summary, source, start/completion time, duration,
and safe outcome.

## 10. Empty, Loading, and Failure States

Before any Home request, Workflow explains that frontend-initiated executions
will appear there and provides a Go to Home action.

While the first graph event is pending, the header displays Starting and the
canvas shows a stable skeleton rather than an indefinite generic spinner.

An SSE disconnect is a visualization transport condition. The page says
`Connection interrupted` and preserves the last valid graph. It does not mark
the underlying tool as failed.

A tool failure marks its operation and owning node failed with a safe summary.
Other graph branches retain their valid state. A visualization rendering error
is caught within the Workflow route so Home remains usable.

## 11. Accessibility and Responsive Behavior

- Nodes and operation rows are keyboard reachable in execution order.
- Expand/collapse controls expose `aria-expanded` and an accessible name.
- Important status transitions use a polite live region.
- Focus remains stable as node status changes.
- Status uses text and iconography in addition to color.
- React Flow controls have accessible labels.
- Reduced-motion preferences disable nonessential animation.

Desktop and tablet are primary. On narrow screens, navigation becomes a compact
top-level control and the graph remains pannable instead of shrinking nodes
below readable sizes. Expanded details may use a compact sheet when inline
space is insufficient.

## 12. Dependencies

- Add LangGraph only to `agent-backend`.
- Add `@xyflow/react` only to `frontend`.
- Add no dependency to `server`.
- LangSmith remains optional and disabled by default; it is not required for
  execution, visualization, or testing.

Dependency versions must be pinned through the existing package managers and
must satisfy repository supply-chain policy at implementation time.

## 13. Verification

### MCP server

- Existing server tests pass without behavior changes.
- Public tool names and JSON input/output schemas remain unchanged.
- The server starts independently without LangGraph or frontend dependencies.

### Agent backend

- Graph routing reproduces plain replies, single and repeated tool calls,
  widget ordering, OpenAI failures, unknown tools, and the four-round limit.
- Every transition emits the expected sanitized execution event.
- Sequence numbers are monotonic.
- Event serialization failure cannot terminate tool execution.
- `run_completed` precedes `done` on normal completion.

### Frontend

- Existing Home and widget tests remain intact.
- Home / Workflow navigation does not restart an active stream.
- Starting a new request replaces prior Workflow state.
- Every node status and operation expansion renders correctly.
- Duplicate, stale, and unknown events are handled safely.
- Nodes cannot be dragged or connected.
- Keyboard navigation, live announcements, reduced motion, and narrow layouts
  are covered.

### End to end

1. Submit a representative request from Home.
2. Navigate to Workflow during execution.
3. Observe live stage advancement without restarting the request.
4. Return to Home and receive the expected text/widget output.
5. Reopen Workflow and see the completed graph.
6. Run the standalone MCP contract checks and confirm no public change.

## 14. Delivery Constraints

Implementation must preserve participant work and existing behavior. It should
be staged so the event schema and graph state reducer are testable independently
from React Flow rendering. Any checks reported as passing must actually have
been run; proposed and skipped checks must be identified explicitly.
