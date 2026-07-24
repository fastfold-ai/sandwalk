"""Unified LLM client supporting Anthropic, OpenAI, and OpenAI-compatible providers."""

from __future__ import annotations

import os
from collections.abc import Generator

from models.llm import anthropic_backend, openai_backend
from models.llm.helpers import retry_with_backoff
from models.llm.pricing import UsageTracker
from models.llm.response import LLMResponse


class LLMClient:
    """Unified LLM client supporting multiple providers."""

    # Default models per provider
    DEFAULT_MODELS = {
        "anthropic": "claude-sonnet-4-5-20250929",
        "openai": "gpt-5.6-sol",
        "xai": "grok-4.5",
        "google": "gemini-3.5-flash",
        "moonshot": "kimi-k2.6",
        "nvidia": "nvidia/nemotron-3-ultra-550b-a55b",
        "opencode": "kimi-k2.7-code",
        "deepseek": "deepseek-v4-flash",
        "minimax": "MiniMax-M2.5",
        "mistral": "mistral-large-latest",
        "qwen": "qwen3-max",
        "together": "zai-org/GLM-5.2",
    }

    # First-party OpenAI-compatible providers: fixed base URL + env fallback.
    OPENAI_COMPATIBLE_BASE_URLS = {
        "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
        "google": (
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            "GEMINI_API_KEY",
        ),
        "moonshot": ("https://api.moonshot.ai/v1", "MOONSHOT_API_KEY"),
        "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
        "opencode": ("https://opencode.ai/zen/v1", "OPENCODE_API_KEY"),
        "deepseek": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
        "minimax": ("https://api.minimax.io/v1", "MINIMAX_API_KEY"),
        "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
        "qwen": (
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            "DASHSCOPE_API_KEY",
        ),
        "together": ("https://api.together.xyz/v1", "TOGETHER_API_KEY"),
    }

    def __init__(self, provider: str = "openai", model: str = None,
                 api_key: str = None, base_url: str | None = None):
        self.provider = provider
        self.model = model or self.DEFAULT_MODELS.get(provider)
        self.api_key = api_key
        self.base_url = str(base_url).strip().rstrip("/") if base_url else None
        self._client = None
        self.usage = UsageTracker()

    def _get_client(self):
        """Lazily initialize the appropriate client."""
        if self._client is not None:
            return self._client

        if self.provider == "anthropic":
            import anthropic
            if os.environ.get("ANTHROPIC_FOUNDRY_API_KEY") or os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE"):
                self._client = anthropic.AnthropicFoundry()
            else:
                self._client = anthropic.Anthropic(
                    api_key=self.api_key or os.environ.get("ANTHROPIC_API_KEY")
                )

        elif self.provider == "openai":
            import openai
            client_kwargs = {
                "api_key": self.api_key or os.environ.get("OPENAI_API_KEY")
            }
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            self._client = openai.OpenAI(**client_kwargs)

        elif self.provider in self.OPENAI_COMPATIBLE_BASE_URLS:
            import openai
            default_base_url, env_var = self.OPENAI_COMPATIBLE_BASE_URLS[self.provider]
            self._client = openai.OpenAI(
                api_key=self.api_key or os.environ.get(env_var),
                base_url=self.base_url or default_base_url,
            )

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        return self._client

    def _retry(self, fn, max_retries: int = 3, base_delay: float = 2.0):
        """Retry a function with exponential backoff on transient errors."""
        return retry_with_backoff(fn, max_retries=max_retries, base_delay=base_delay)

    def chat(self, system: str, messages: list[dict], temperature: float = 0.1,
             max_tokens: int = 4096, tools: list[dict] | None = None) -> LLMResponse:
        """Send a chat completion request.

        Args:
            tools: Optional list of tool definitions (Anthropic tool_use format).
                   When provided, the response may contain tool_use content blocks
                   accessible via ``response.content_blocks``.
        """
        client = self._get_client()

        if self.provider == "anthropic":
            resp = self._retry(
                lambda: anthropic_backend.call(
                    client, self.model, system, messages, temperature, max_tokens, tools=tools
                )
            )
        elif self.provider == "openai" or self.provider in self.OPENAI_COMPATIBLE_BASE_URLS:
            resp = self._retry(
                lambda: openai_backend.call(client, self.model, system, messages, temperature, max_tokens)
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        if resp.usage:
            self.usage.record(resp.model, resp.usage)

        return resp

    def stream(self, system: str, messages: list[dict], temperature: float = 0.1,
               max_tokens: int = 4096) -> Generator[str, None, LLMResponse]:
        """Stream a chat completion, yielding text chunks.

        Yields individual text deltas. After the generator is exhausted,
        send() returns the final LLMResponse with full content and usage.

        Usage:
            gen = llm.stream(system, messages)
            chunks = []
            for chunk in gen:
                print(chunk, end="", flush=True)
                chunks.append(chunk)
            # Full response available after iteration
        """
        client = self._get_client()

        if self.provider == "anthropic":
            yield from anthropic_backend.stream(
                client, self.model, system, messages, temperature, max_tokens, self.usage
            )
        elif self.provider == "openai" or self.provider in self.OPENAI_COMPATIBLE_BASE_URLS:
            yield from openai_backend.stream(
                client, self.model, system, messages, temperature, max_tokens, self.usage
            )
        else:
            # Fallback: non-streaming providers just yield the full response
            resp = self.chat(system, messages, temperature, max_tokens)
            yield resp.content
