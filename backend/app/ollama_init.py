"""Ensure the fixed chatbot model is present in the shared Ollama server."""

from __future__ import annotations

import json
import os
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
MODEL = os.environ.get("OLLAMA_AGENT_MODEL", "llama3.1:8b")


def _get_tags() -> set[str]:
    for attempt in range(30):
        try:
            with urlopen(f"{OLLAMA_URL}/api/tags", timeout=30) as response:
                data = json.load(response)
            return {str(item.get("name", "")) for item in data.get("models", [])}
        except (OSError, URLError):
            if attempt == 29:
                raise
            time.sleep(2)
    return set()


def main() -> None:
    for attempt in range(30):
        try:
            if MODEL in _get_tags():
                print(f"{MODEL} is already available.", flush=True)
                return
            break
        except (OSError, URLError):
            if attempt == 29:
                raise
            time.sleep(2)

    payload = json.dumps({"model": MODEL, "stream": True}).encode("utf-8")
    request = Request(
        f"{OLLAMA_URL}/api/pull",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=3600) as response:
        for line in response:
            if not line.strip():
                continue
            status = json.loads(line)
            if status.get("error"):
                raise RuntimeError(str(status["error"]))
            if status.get("status"):
                print(status["status"], flush=True)
    if MODEL not in _get_tags():
        raise RuntimeError(f"Ollama did not install {MODEL}.")


if __name__ == "__main__":
    main()
