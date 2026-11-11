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
    def test_summary_context_expands_to_preserve_full_input(self):
        from pydantic import BaseModel
        class Summary(BaseModel):
            summary: str
        class SummaryResponse(_Response):
            def json(self):
                return {"message": {"content": '{"summary":"A complete generated summary."}'}}
        class SummaryClient(_Client):
            async def post(self, url, **kwargs):
                _Client.last = (url, kwargs)
                return SummaryResponse()
        cfg = {"provider":"ollama", "key":"", "base_url":"", "ollama_url":"http://ollama:11434", "proposal_model":"llama3.1:8b", "agent_model":"llama3.1:8b", "timeout":120, "retries":0, "rate_limit":10}
        prompt = "All document content " * 1000 + "DOCUMENT_END"
        with patch("app.ai_provider.provider_config", return_value=cfg), patch("app.ai_provider.httpx.AsyncClient", SummaryClient):
            result = asyncio.run(run_ai_json(prompt, Summary, model_kind="proposal", rate_key="full-summary"))
        self.assertEqual(result["status"], "COMPLETED")
        payload = _Client.last[1]["json"]
        self.assertEqual(payload["messages"][1]["content"], prompt)
        self.assertGreater(payload["options"]["num_ctx"], len(prompt.encode()))

    def test_oversize_input_fails_explicitly_without_truncation(self):
        from pydantic import BaseModel
        class Summary(BaseModel):
            summary: str
        cfg = {"provider":"ollama", "key":"", "base_url":"", "ollama_url":"http://ollama:11434", "proposal_model":"llama3.1:8b", "agent_model":"llama3.1:8b", "timeout":120, "retries":0, "rate_limit":10}
        with patch("app.ai_provider.provider_config", return_value=cfg), patch("app.ai_provider.httpx.AsyncClient") as client:
            result = asyncio.run(run_ai_json("x" * 140000, Summary, model_kind="proposal", rate_key="oversize-summary"))
        self.assertEqual(result["fallback_reason"], "model_context_exceeded")
        client.assert_not_called()

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
