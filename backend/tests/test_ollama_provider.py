import asyncio
import unittest
from unittest.mock import patch
import httpx

from app.ai_provider import ProposalProviderPayload, run_ai_json


class _Response:
    status_code = 200
    def raise_for_status(self): return None
    def json(self):
        sections = ["problem_statement", "objectives", "scope", "methodology", "abstract_purpose", "expected_outcomes", "proposed_solution"]
        findings = [{"section": section, "status": "PASS", "feedback": "Clear and relevant.", "suggestion": "Keep this aligned.", "confidence": 0.9, "page": 1, "evidence": "short evidence", "source": "AI"} for section in sections]
        import json
        return {"message": {"content": json.dumps({"findings": findings})}}


class _Client:
    last = None
    def __init__(self, *args, **kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    async def post(self, url, **kwargs):
        self.__class__.last = (url, kwargs)
        return _Response()


class OllamaProviderTests(unittest.TestCase):
    def test_chat_request_is_local_non_streaming_and_schema_validated(self):
        cfg = {"provider":"ollama", "key":"", "base_url":"https://api.groq.com/openai/v1", "ollama_url":"http://127.0.0.1:11434", "proposal_model":"llama3.1:8b", "agent_model":"llama3.1:8b", "timeout":8.0, "retries":0, "rate_limit":10}
        with patch("app.ai_provider.provider_config", return_value=cfg), patch("app.ai_provider.httpx.AsyncClient", _Client):
            result = asyncio.run(run_ai_json("data", ProposalProviderPayload, model_kind="proposal", rate_key="ollama-test"))
        self.assertEqual(result["source"], "AI")
        url, kwargs = _Client.last
        self.assertEqual(url, "http://127.0.0.1:11434/api/chat")
        self.assertFalse(kwargs["json"]["stream"])
        self.assertIsInstance(kwargs["json"]["format"], dict)
        self.assertIn("properties", kwargs["json"]["format"])
        self.assertEqual(kwargs["json"]["model"], "llama3.1:8b")
        self.assertNotIn("Authorization", kwargs["headers"])

    def test_invalid_response_returns_fallback(self):
        class InvalidResponse(_Response):
            def json(self):
                return {"message": {"content": "not json"}}
        class InvalidClient(_Client):
            async def post(self, url, **kwargs):
                return InvalidResponse()
        cfg = {"provider":"ollama", "key":"", "base_url":"https://api.groq.com/openai/v1", "ollama_url":"http://127.0.0.1:11434", "proposal_model":"llama3.1:8b", "agent_model":"llama3.1:8b", "timeout":8.0, "retries":0, "rate_limit":10}
        with patch("app.ai_provider.provider_config", return_value=cfg), patch("app.ai_provider.httpx.AsyncClient", InvalidClient):
            result = asyncio.run(run_ai_json("data", ProposalProviderPayload, model_kind="proposal", rate_key="ollama-invalid"))
        self.assertEqual(result["source"], "DETERMINISTIC_FALLBACK")

    def test_timeout_returns_fallback(self):
        class TimeoutClient(_Client):
            async def post(self, url, **kwargs):
                raise httpx.ReadTimeout("timeout")
        cfg = {"provider":"ollama", "key":"", "base_url":"https://api.groq.com/openai/v1", "ollama_url":"http://127.0.0.1:11434", "proposal_model":"llama3.1:8b", "agent_model":"llama3.1:8b", "timeout":8.0, "retries":0, "rate_limit":10}
        with patch("app.ai_provider.provider_config", return_value=cfg), patch("app.ai_provider.httpx.AsyncClient", TimeoutClient):
            result = asyncio.run(run_ai_json("data", ProposalProviderPayload, model_kind="proposal", rate_key="ollama-timeout"))
        self.assertEqual(result["fallback_reason"], "timeout")


if __name__ == "__main__":
    unittest.main()
