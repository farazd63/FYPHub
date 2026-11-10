import asyncio
import os
import unittest
from unittest.mock import patch

from app.ai_provider import ProposalProviderPayload, run_groq_json


class _Response:
    status_code = 200
    request = object()
    def raise_for_status(self): return None
    def json(self):
        return {"choices": [{"message": {"content": '{"coherence_status":"PASS","supported_links":[],"missing_links":[],"contradictions":[],"policy_issues":[],"suggestions":[],"confidence":0.9,"uncertainty":"none"}'}}]}

class _StatusClient:
    status = 401
    def __init__(self, *args, **kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    async def post(self, url, **kwargs):
        response = _Response(); response.status_code = self.status; return response


class _Client:
    last = None
    def __init__(self, *args, **kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    async def post(self, url, **kwargs): self.__class__.last = (url, kwargs); return _Response()


class GroqProviderTests(unittest.TestCase):
    def test_success_uses_exact_endpoint_headers_and_model(self):
        env = {"AI_PROVIDER":"groq", "GROQ_API_KEY":"test-key", "GROQ_BASE_URL":"https://api.groq.com/openai/v1", "GROQ_PROPOSAL_MODEL":"test-model", "AI_MAX_RETRIES":"0"}
        cfg = {"provider":"groq","key":"gsk_test_key_12345678901234567890","base_url":env["GROQ_BASE_URL"],"proposal_model":"test-model","agent_model":"agent","timeout":8.0,"retries":0,"rate_limit":10}
        with patch("app.ai_provider.provider_config", return_value=cfg), patch("app.ai_provider.httpx.AsyncClient", _Client):
            result = asyncio.run(run_groq_json("data", ProposalProviderPayload, model_kind="proposal", rate_key="test-success"))
        self.assertEqual(result["source"], "AI")
        url, kwargs = _Client.last
        self.assertEqual(url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer gsk_test_key_12345678901234567890")
        self.assertEqual(kwargs["json"]["model"], "test-model")

    def test_missing_key_falls_back_without_request(self):
        cfg = {"provider":"groq","key":"","base_url":"https://api.groq.com/openai/v1","proposal_model":"model","agent_model":"agent","timeout":8.0,"retries":0,"rate_limit":10}
        with patch("app.ai_provider.provider_config", return_value=cfg):
            result = asyncio.run(run_groq_json("data", ProposalProviderPayload, model_kind="proposal", rate_key="test-missing"))
        self.assertEqual(result["source"], "DETERMINISTIC_FALLBACK")

    def test_unauthorized_and_invalid_model_are_classified(self):
        for status_code, reason in ((401, "invalid_api_key"), (404, "invalid_model"), (429, "rate_limited")):
            _StatusClient.status = status_code
            env = {"AI_PROVIDER":"groq", "GROQ_API_KEY":"test-key", "GROQ_PROPOSAL_MODEL":"model", "AI_MAX_RETRIES":"0"}
            cfg = {"provider":"groq","key":"gsk_test_key_12345678901234567890","base_url":"https://api.groq.com/openai/v1","proposal_model":"model","agent_model":"agent","timeout":8.0,"retries":0,"rate_limit":10}
            with patch("app.ai_provider.provider_config", return_value=cfg), patch("app.ai_provider.httpx.AsyncClient", _StatusClient):
                result = asyncio.run(run_groq_json("data", ProposalProviderPayload, model_kind="proposal", rate_key=f"test-status-{status_code}"))
            self.assertEqual(result["fallback_reason"], reason)
            self.assertEqual(result["source"], "DETERMINISTIC_FALLBACK")


if __name__ == "__main__":
    unittest.main()
