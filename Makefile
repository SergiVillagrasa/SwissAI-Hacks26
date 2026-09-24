.PHONY: dev-api dev-web stop stop-api stop-web

# Run the agent backend (FastAPI/uvicorn) on http://127.0.0.1:3001
dev-api:
	cd swiss-grounding-mcp/agent-backend && uv run uvicorn agent_backend.main:app --reload --port 3001

# Run the frontend (Vite) dev server on http://localhost:3000
dev-web:
	npm --prefix swiss-grounding-mcp/frontend run dev -- --port 3000

# Stop the backend (port 3001)
stop-api:
	@-fuser -k 3001/tcp 2>/dev/null && echo "Backend (port 3001) stopped" || echo "Nothing on port 3001"

# Stop the frontend (port 3000)
stop-web:
	@-fuser -k 3000/tcp 2>/dev/null && echo "Frontend (port 3000) stopped" || echo "Nothing on port 3000"

# Stop everything
stop: stop-api stop-web
	@echo "All dev servers stopped"
