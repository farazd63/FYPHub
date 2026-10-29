"""Optional local AI template extraction layered over deterministic AST facts."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


async def extract_template_rules(ast: dict[str, Any], proposal_type: str, *, checksum: str) -> dict[str, Any]:
    """Return validated advisory metadata; never invent a missing rule.

    Deterministic extraction remains the source of truth when Ollama is absent.
    """
    model = os.getenv("OLLAMA_MODEL", "")
    started = datetime.now(timezone.utc).isoformat()
    if not model:
        return {"status": "UNAVAILABLE", "proposal_type": proposal_type, "rules": {}, "warnings": ["Ollama is not configured; deterministic extraction retained."], "runtime": "ollama-local", "model": None, "timestamp": started, "source_checksum": checksum}
    text = "\n".join(str(item.get("text", "")) for item in ast.get("paragraphs", []))[: int(os.getenv("OLLAMA_MAX_INPUT_CHARS", "12000"))]
    prompt = "Return JSON only with proposal_type, required_sections, optional_sections, expected_section_order, formatting, citations, confidence, warnings. Use null/unknown for facts not visible in the source. Do not invent rules.\n" + text
    try:
        import httpx

        async with httpx.AsyncClient(timeout=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "8"))) as client:
            response = await client.post(f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')}/api/generate", json={"model": model, "prompt": prompt, "stream": False, "format": "json"})
            response.raise_for_status()
            body = response.json()
        raw = body.get("response") if isinstance(body, dict) else None
        result = json.loads(raw) if isinstance(raw, str) else raw
        required = {"proposal_type", "required_sections", "optional_sections", "expected_section_order", "formatting", "citations", "confidence", "warnings"}
        if not isinstance(result, dict) or not required.issubset(result) or result["proposal_type"] != proposal_type:
            raise ValueError("template response failed schema validation")
        return {"status": "AVAILABLE", "rules": result, "runtime": "ollama-local", "model": model, "timestamp": started, "source_checksum": checksum}
    except Exception as error:
        return {"status": "UNAVAILABLE", "proposal_type": proposal_type, "rules": {}, "warnings": [f"Ollama template extraction unavailable ({type(error).__name__}); deterministic extraction retained."], "runtime": "ollama-local", "model": model, "timestamp": started, "source_checksum": checksum}
