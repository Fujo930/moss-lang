"""Corvus LLM adapter — unified interface to AI model providers.

Supports:
  openai        →  api.openai.com (and any OpenAI-compatible endpoint)
  claude        →  api.anthropic.com
  local         →  OpenAI-compatible local server (LM Studio / Ollama / vLLM)

Configuration via environment variables:
  LLM_API_KEY    —  API key (required for openai/claude, optional for local)
  LLM_MODEL      —  model name (default: gpt-4o / claude-sonnet-4-20250514)
  LLM_BASE_URL   —  override base URL (for openai-compatible endpoints)

Usage:
    from mossagent.llm import create_adapter

    adapter = create_adapter("openai")
    result = adapter.generate("Write a Moss function that sorts a list.")
"""

from __future__ import annotations

import json as _json
import os
import urllib.request
import urllib.error
from typing import Protocol


class LLMAdapter(Protocol):
    """Callable that takes a prompt string and returns generated text."""
    def generate(self, prompt: str) -> str: ...


# ── OpenAI & OpenAI-compatible adapter ─────────────────────────────

class OpenAIAdapter:
    """Adapter for OpenAI and any OpenAI-compatible API (LM Studio, Ollama, etc.)."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = int(os.environ.get("LLM_TIMEOUT", "60"))

    def generate(self, prompt: str) -> str:
        return self.generate_messages([{"role": "user", "content": prompt}])

    def generate_messages(self, messages: list[dict]) -> str:
        """Send a full message array. API caches the prefix for subsequent calls."""
        url = f"{self.base_url}/chat/completions"

        body = _json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API error {e.code}: {body[:500]}")
        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}")


# ── Claude adapter ────────────────────────────────────────────────

class ClaudeAdapter:
    """Adapter for Anthropic Claude Messages API."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = int(os.environ.get("LLM_TIMEOUT", "60"))

    def generate(self, prompt: str) -> str:
        return self.generate_messages([{"role": "user", "content": prompt}])

    def generate_messages(self, messages: list[dict]) -> str:
        url = "https://api.anthropic.com/v1/messages"

        # Claude API: system is a separate field, not a message role
        system_content = ""
        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                system_content = m["content"]
            else:
                chat_messages.append({"role": m["role"], "content": m["content"]})

        body_dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": chat_messages,
        }
        if system_content:
            body_dict["system"] = system_content

        body = _json.dumps(body_dict).encode("utf-8")

        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("x-api-key", self.api_key)
        req.add_header("anthropic-version", "2023-06-01")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Claude API error {e.code}: {body[:500]}")
        except Exception as e:
            raise RuntimeError(f"Claude call failed: {e}")


# ── Factory ───────────────────────────────────────────────────────

def create_adapter(
    provider: str = "openai",
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> LLMAdapter:
    """Create an LLM adapter from a provider name.

    Args:
        provider: "openai", "claude", or "local"
        model: Override default model.
        api_key: Override API key.
        base_url: Override base URL (openai-compatible endpoints).
        temperature: Generation temperature (default 0.0 = deterministic).
        max_tokens: Max tokens to generate.

    Returns:
        An LLMAdapter with a .generate(prompt) method.

    Provider details:
        openai  →  api.openai.com/v1 (or LLM_BASE_URL if set)
        local   →  same as openai, but defaults to http://localhost:1234/v1
        claude  →  api.anthropic.com/v1
    """
    provider = provider.lower()

    if provider == "claude":
        return ClaudeAdapter(
            model=model or os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514"),
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # openai or local
    default_model = "gpt-4o"
    default_url = "https://api.openai.com/v1"

    if provider == "local":
        default_url = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1")
        default_model = os.environ.get("LLM_MODEL", "local-model")

    return OpenAIAdapter(
        model=model or os.environ.get("LLM_MODEL", default_model),
        api_key=api_key,
        base_url=base_url or os.environ.get("LLM_BASE_URL", default_url),
        temperature=temperature,
        max_tokens=max_tokens,
    )
