"""Shared base for all OpenAI-compatible providers (OpenAI, Perplexity, Groq, Gemini, Ollama)."""

import json
from typing import Generator

import httpx

from .base import BaseProvider
from ..exceptions import ProviderError, StreamError


class OpenAICompatibleProvider(BaseProvider):
    """Implements stream_chat over the OpenAI /chat/completions SSE format.

    Subclasses must set:
        BASE_URL: str   — e.g. "https://api.openai.com/v1"
        name: str
        default_model: str
        MODELS: list[str]  — hardcoded list; empty means query the /models endpoint
    """

    BASE_URL: str
    MODELS: list[str] = []

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

    def _get_base_url(self) -> str:
        return getattr(self, "base_url", self.BASE_URL)

    def _build_request_body(
        self, messages: list[dict], system_prompt: str
    ) -> dict:
        # Prepend a system message if the history doesn't already have one
        # and a system_prompt is provided
        has_system = any(m["role"] == "system" for m in messages)
        if system_prompt and not has_system:
            messages = [{"role": "system", "content": system_prompt}] + messages

        return {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

    # ------------------------------------------------------------------ #
    # Public interface                                                      #
    # ------------------------------------------------------------------ #

    def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str = "Be precise and concise.",
    ) -> Generator[str, None, None]:
        url = f"{self._get_base_url()}/chat/completions"
        headers = self._get_headers()
        body = self._build_request_body(messages, system_prompt)

        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                with client.stream("POST", url, headers=headers, json=body) as response:
                    if response.status_code == 401:
                        raise ProviderError(
                            f"Invalid API key for {self.name}. "
                            "Check your config or environment variable."
                        )
                    if response.status_code != 200:
                        body_text = response.read().decode()
                        raise ProviderError(
                            f"{self.name} returned HTTP {response.status_code}: {body_text}"
                        )

                    for line in response.iter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data = line[len("data: "):]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError as exc:
                            raise StreamError(f"Failed to parse SSE chunk: {data!r}") from exc

                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            yield delta

        except httpx.ConnectError as exc:
            raise ProviderError(
                f"Could not connect to {self.name} at {url}. "
                "Check your network connection."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(f"Request to {self.name} timed out.") from exc

    @classmethod
    def list_models(
        cls,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> list[str]:
        # If the subclass has a hardcoded list, return it immediately
        if cls.MODELS:
            return cls.MODELS

        # Otherwise query the /models endpoint
        url = f"{base_url or cls.BASE_URL}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            resp = httpx.get(url, headers=headers, timeout=10.0)
            resp.raise_for_status()
            return sorted(item["id"] for item in resp.json().get("data", []))
        except Exception:
            return []
