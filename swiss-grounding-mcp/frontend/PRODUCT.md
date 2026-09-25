# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Travelers and residents in Switzerland asking natural-language questions about
their journey (trains, flights, connections, fares, disruptions, airport
guidance) through a conversational chat interface backed by an MCP-grounded
agent.

## Product Purpose

A chat frontend for the Swiss Grounding MCP agent (built for the Swisscom
myAI challenge at Swiss AI Weeks Zurich). Every travel-tool result the agent
retrieves renders as a visual widget (train connections, station board,
fares, disruptions, flight info, flight-to-train handoff, airport guidance,
route map) instead of chat prose, so answers stay verifiable and scannable.
Non-success tool results render an honest status banner (including
clarification prompts, e.g. "which stop did you mean") rather than a guess.

## Positioning

Grounded, source-backed Swiss travel answers assembled from authoritative
tool calls (SBB/transit APIs, flight data, disruption feeds) and presented as
structured, verifiable widgets rather than free-form generated text.

## Operating Context

- Requires the companion `agent-backend` service running locally (SSE chat
  stream at `VITE_AGENT_BACKEND_URL`, default `http://127.0.0.1:3001`).
- Route maps use Mapbox GL (`VITE_MAPBOX_TOKEN`); map widget degrades to a
  text fallback when unavailable.
- Widgets carry provenance/source links back to the origin data source.

## Capabilities and Constraints

- Stack (existing): Vite + React 19 + TypeScript + Tailwind CSS 3, Vitest +
  Testing Library for tests, oxlint for linting.
- Widget types today: train connections, station board, fares, disruptions,
  flight, flight search, flight-to-train, airport guidance, route map,
  status banner (fallback/clarification).
- Chat model: linear turn list (`user` / `assistant`), assistant turns can
  carry zero or more widgets alongside streamed text.
- Desktop/tablet is the primary target for this hackathon demo; mobile must
  not be broken but is not the optimization priority.
- Brand commitment: the product presents as **"Swiss Travel by Swisscom"** on
  its landing surface — `SWISS TRAVEL` wordmark plus the Swisscom dual-color
  emblem (`#001AFF` / `#E30613`). Behind that surface the codebase name remains
  Swiss Grounding MCP.

## Product Principles

- Verifiable over generated: every travel fact traces to a widget with a
  source, never bare prose the agent invented.
- Honest failure over guessing: missing/ambiguous input surfaces a status
  banner or clarification prompt, never a fabricated answer.
- Scannable structure: journey data (times, platforms, gates, delays) reads
  as structured widget content, not paragraphs.
- Demo-ready polish: desktop/tablet experience is the one that gets judged.
