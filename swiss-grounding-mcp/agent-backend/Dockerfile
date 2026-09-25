# Agent backend (FastAPI chat service).
#
# Build context MUST be swiss-grounding-mcp/ (the parent of this
# directory), not agent-backend/ itself: this package depends on the MCP
# server's tool functions via an editable path dependency (`../server` in
# pyproject.toml / uv.lock), so the server source has to be present in the
# build context at that same relative location.
#
# Railway service settings: Root Directory = swiss-grounding-mcp,
# Dockerfile Path = agent-backend/Dockerfile.
FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY server ./server
COPY agent-backend ./agent-backend

WORKDIR /app/agent-backend
RUN uv sync --frozen --no-dev

ENV PATH="/app/agent-backend/.venv/bin:${PATH}"

EXPOSE 3001

CMD ["sh", "-c", "uvicorn agent_backend.main:app --host 0.0.0.0 --port ${PORT:-3001}"]
