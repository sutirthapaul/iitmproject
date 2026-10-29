"""LLM clients.

OpenAI, Groq and Google Gemini all expose an OpenAI-compatible Chat Completions endpoint,
so one client class covers all three. MockLLM is a deterministic keyword-based stand-in
used for demos, tests and grading without an API key.
"""
from __future__ import annotations

from typing import Protocol

import config


class LLMError(RuntimeError):
    """Raised for provider/API failures (auth, rate limit, timeout, network)."""


class LLMClient(Protocol):
    provider: str
    model: str

    def complete(self, messages: list[dict], context: dict) -> str: ...


class OpenAICompatibleClient:
    def __init__(self, provider: str, api_key: str, model: str, base_url: str | None = None):
        from openai import OpenAI

        if not api_key:
            raise LLMError(f"No API key configured for {provider}.")
        self.provider = provider
        self.model = model
        self._json_mode = True
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=config.LLM_TIMEOUT_SECONDS,
                              max_retries=2)   # SDK retries 429/5xx with exponential backoff

    def complete(self, messages: list[dict], context: dict) -> str:
        import openai

        kwargs = dict(model=self.model, messages=messages, temperature=config.LLM_TEMPERATURE)
        if self._json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except openai.BadRequestError as exc:
            # Some models reject response_format; fall back to prompt-only JSON once.
            if self._json_mode and "response_format" in str(exc):
                self._json_mode = False
                return self.complete(messages, context)
            raise LLMError(f"{self.provider} rejected the request: {exc.message}") from exc
        except openai.AuthenticationError as exc:
            raise LLMError(f"{self.provider} authentication failed - check the API key.") from exc
        except openai.RateLimitError as exc:
            raise LLMError(f"{self.provider} rate limit or quota exceeded. Wait and retry, or use Mock mode.") from exc
        except openai.APITimeoutError as exc:
            raise LLMError(f"{self.provider} request timed out after {config.LLM_TIMEOUT_SECONDS}s.") from exc
        except openai.APIConnectionError as exc:
            raise LLMError(f"Could not reach {self.provider}: {exc}") from exc
        except openai.APIError as exc:
            raise LLMError(f"{self.provider} API error: {exc}") from exc
        return resp.choices[0].message.content or ""


def build_client(provider: str, api_key: str | None = None, model: str | None = None,
                 fault_target: str | None = None) -> LLMClient:
    if provider not in config.LLM_PROVIDERS:
        raise LLMError(f"Unknown provider: {provider}")
    spec = config.LLM_PROVIDERS[provider]
    if spec["key"] is None:
        from llm.mock_llm import MockLLM

        return MockLLM(fault_target=fault_target)
    return OpenAICompatibleClient(provider, api_key or "", model or spec["default_model"], spec["base_url"])
