"""Perplexity provider with citation support."""

import json
from typing import Generator

import httpx

from .openai_compat import OpenAICompatibleProvider
from ..exceptions import ProviderError, StreamError


class PerplexityProvider(OpenAICompatibleProvider):
    name = "perplexity"
    BASE_URL = "https://api.perplexity.ai"
    default_model = "sonar-pro"
    MODELS = [
        "sonar-reasoning-pro",
        "sonar-reasoning",
        "sonar-pro",
        "sonar",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_citations: list[str] = []

    def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str = "Be precise and concise.",
    ) -> Generator[str, None, None]:
        """Stream chat with citation extraction from Perplexity SSE responses."""
        url = f"{self._get_base_url()}/chat/completions"
        headers = self._get_headers()
        body = self._build_request_body(messages, system_prompt)

        self.last_citations = []

        try:
            with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
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

                        if "citations" in chunk:
                            self.last_citations = chunk["citations"]

                        choices = chunk.get("choices", [{}])
                        if choices:
                            citations_in_choice = choices[0].get("citations", [])
                            if citations_in_choice:
                                self.last_citations = citations_in_choice

                        delta = (
                            choices[0].get("delta", {}).get("content", "")
                            if choices else ""
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
