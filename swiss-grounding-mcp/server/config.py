"""Standalone environment check for the Swiss Grounding MCP server.

Loads `.env` from this directory via python-dotenv and reports which
credentials are configured. Never prints secret values.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

OJP_API_TOKEN = os.getenv("OJP_API_TOKEN", "").strip()
OJP_BASE_URL = os.getenv("OJP_BASE_URL", "https://api.opentransportdata.swiss/ojp20")
OJP_REQUESTOR_REF = os.getenv("OJP_REQUESTOR_REF", "swiss-grounding-mcp")
OJP_TIMEOUT_SECONDS = float(os.getenv("OJP_TIMEOUT_SECONDS", "10"))

RESPECT_ROBOTS_TXT = os.getenv("RESPECT_ROBOTS_TXT", "true").lower() == "true"

MCP_HTTP_HOST = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
MCP_HTTP_PORT = int(os.getenv("MCP_HTTP_PORT", "8000"))


def _mask(token: str) -> str:
    if not token:
        return "(not set)"
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}...{token[-4:]} (len={len(token)})"


def check_environment() -> None:
    print("=== Swiss Grounding MCP configuration ===")
    print(f"OJP_API_TOKEN:       {'[CONFIGURED] ' + _mask(OJP_API_TOKEN) if OJP_API_TOKEN else '[MISSING]'}")
    print(f"OJP_BASE_URL:        {OJP_BASE_URL}")
    print(f"OJP_REQUESTOR_REF:   {OJP_REQUESTOR_REF}")
    print(f"OJP_TIMEOUT_SECONDS: {OJP_TIMEOUT_SECONDS}")
    print(f"RESPECT_ROBOTS_TXT:  {RESPECT_ROBOTS_TXT}")
    print(f"MCP_HTTP endpoint:   {MCP_HTTP_HOST}:{MCP_HTTP_PORT}")
    print("=========================================")


if __name__ == "__main__":
    check_environment()
