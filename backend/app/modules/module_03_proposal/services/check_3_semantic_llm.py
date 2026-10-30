"""Optional local Ollama chain-of-logic audit with strict unavailable handling."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def _unavailable(message: str, *, model: str | None, started_at: str) -> dict[str, Any]:
    return {"status": "UNAVAILABLE", "message": message, "coherence_status": "UNAVAILABLE", "supported_links": [], "missing_links": [], "contradictions": [], "policy_issues": [], "suggestions": [], "confidence": "UNKNOWN", "uncertainty": "The local advisory runtime did not return a validated result.", "runtime": "ollama-local", "model": model, "timestamp": started_at, "advisory": True}


async def run_semantic_check(ast: dict[str, Any], *, url: str | None = None, model: str | None = None, timeout: float | None = None, max_input: int | None = None) -> dict[str, Any]:
    base_url = (url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
    runtime_model = model or os.getenv("OLLAMA_MODEL", "")
    request_timeout = timeout if timeout is not None else float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "8"))
    input_limit = max_input if max_input is not None else int(os.getenv("OLLAMA_MAX_INPUT_CHARS", "12000"))
    started_at = datetime.now(timezone.utc).isoformat()
    if not runtime_model:
        return _unavailable("Ollama is not configured; Check 3 is advisory and unavailable.", model=None, started_at=started_at)
    text = "\n".join(str(item.get("text", "")) for item in ast.get("paragraphs", []))[:input_limit]
    prompt = "Return one JSON object with exactly these advisory fields: coherence_status, supported_links, missing_links, contradictions, policy_issues, suggestions, confidence, uncertainty. Never approve or reject. Do not invent facts.\nProposal:\n" + text
    try:
        import httpx
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            response = await client.post(f"{base_url}/api/generate", json={"model": runtime_model, "prompt": prompt, "stream": False, "format": "json"})
            response.raise_for_status()
            body = response.json()
        raw = body.get("response") if isinstance(body, dict) else None
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        required = {"coherence_status", "supported_links", "missing_links", "contradictions", "policy_issues", "suggestions", "confidence", "uncertainty"}
        if not isinstance(parsed, dict) or not required.issubset(parsed) or any(not isinstance(parsed[key], list) for key in ("supported_links", "missing_links", "contradictions", "policy_issues", "suggestions")):
            raise ValueError("Ollama response failed schema validation")
        return {"status": "AVAILABLE", "advisory": True, **parsed, "runtime": "ollama-local", "model": runtime_model, "timestamp": started_at}
    except Exception as error:
        return _unavailable(f"Ollama was unavailable or returned invalid advisory JSON ({type(error).__name__}).", model=runtime_model, started_at=started_at)
