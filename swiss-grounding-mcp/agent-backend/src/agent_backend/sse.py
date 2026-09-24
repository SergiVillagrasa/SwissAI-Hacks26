from __future__ import annotations

import json


def format_sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"
