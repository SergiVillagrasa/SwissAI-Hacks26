# Swiss Grounding MCP server (Streamable HTTP transport).
# Build context: swiss-grounding-mcp/server
FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY src ./src

# Install only the runtime dependencies declared under [project], skipping
# the dev/eval/voice dependency groups (pytest, galtea, elevenlabs, ...)
# that this service does not need at runtime.
RUN uv sync --frozen --no-default-groups

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

# Railway (and most PaaS providers) inject PORT at runtime; fall back to
# 8000 for local `docker run`. The MCP endpoint is served at /mcp.
CMD ["sh", "-c", "swiss-grounding-mcp --transport streamable-http --host 0.0.0.0 --port ${PORT:-8000}"]
