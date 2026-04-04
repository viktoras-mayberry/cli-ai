from typing import Generator

import httpx

from .openai_compat import OpenAICompatibleProvider
from ..exceptions import ProviderError


class OllamaProvider(OpenAICompatibleProvider):
    name = "ollama"
    # "/v1" suffix is required — Ollama routes OpenAI-compat under /v1
    BASE_URL = "http://localhost:11434/v1"
    default_model = "llama3.2"
    MODELS: list[str] = []  # Dynamic — fetched from the running server

    def __init__(
        self,
        api_key: str | None,
        model: str,
        base_url: str | None = None,
    ) -> None:
        super().__init__(api_key=api_key, model=model)
        # Store the configurable base URL (strip trailing slash + add /v1 if needed)
        raw = (base_url or "http://localhost:11434").rstrip("/")
        if not raw.endswith("/v1"):
            raw = raw + "/v1"
        self.base_url = raw

    def _get_headers(self) -> dict[str, str]:
        # Ollama does not require auth
        return {"Content-Type": "application/json"}

    def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str = "Be precise and concise.",
    ) -> Generator[str, None, None]:
        try:
            yield from super().stream_chat(messages, system_prompt)
        except ProviderError as exc:
            if "Could not connect" in str(exc):
                raise ProviderError(
                    f"Cannot reach Ollama at {self.base_url}. "
                    "Make sure Ollama is running (ollama serve)."
                ) from exc
            raise

    @classmethod
    def list_models(
        cls,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> list[str]:
        """Fetch available models from the running Ollama instance."""
        raw = (base_url or "http://localhost:11434").rstrip("/")
        # Strip /v1 suffix if present — /api/tags is on the root
        if raw.endswith("/v1"):
            raw = raw[:-3]
        tags_url = f"{raw}/api/tags"
        try:
            resp = httpx.get(tags_url, timeout=5.0)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except httpx.ConnectError:
            raise ProviderError(
                "Cannot reach Ollama. Make sure Ollama is running (ollama serve)."
            )
        except Exception:
            return []
