.PHONY: dev-api dev-web

# Run the agent backend (FastAPI/uvicorn) on http://127.0.0.1:3001
dev-api:
	cd swiss-grounding-mcp/agent-backend && uv run uvicorn agent_backend.main:app --reload --port 3001

# Run the frontend (Vite) dev server on http://localhost:3000
dev-web:
	npm --prefix swiss-grounding-mcp/frontend run dev -- --port 3000
