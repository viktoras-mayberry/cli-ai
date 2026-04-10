"""Anthropic (Claude) provider — uses the official anthropic SDK.

The Anthropic Messages API differs from OpenAI in four key ways:
  1. Auth header: x-api-key (not Authorization: Bearer)
  2. System prompt: top-level "system" key, NOT inside messages[]
  3. Message alternation: strict user/assistant alternation required
  4. max_tokens must be specified explicitly
"""

from typing import Generator

import anthropic as _anthropic

from .base import BaseProvider
from ..exceptions import ProviderError


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    default_model = "claude-opus-4-6"
    MODELS = [
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ]

    def _convert_messages(
        self, messages: list[dict], system_prompt: str
    ) -> tuple[str, list[dict]]:
        """Extract system messages and enforce user/assistant alternation.

        Returns (resolved_system_prompt, cleaned_messages).
        """
        system_parts: list[str] = []
        if system_prompt:
            system_parts.append(system_prompt)

        chat_messages: list[dict] = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
                continue
            chat_messages.append({"role": msg["role"], "content": msg["content"]})

        # Merge consecutive same-role messages (defensive — REPL shouldn't produce these)
        merged: list[dict] = []
        for msg in chat_messages:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] += "\n\n" + msg["content"]
            else:
                merged.append(dict(msg))

        return "\n\n".join(system_parts), merged

    def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str = "Be precise and concise.",
    ) -> Generator[str, None, None]:
        resolved_system, chat_messages = self._convert_messages(messages, system_prompt)

        if not chat_messages:
            raise ProviderError("No user messages to send to Anthropic.")

        client = _anthropic.Anthropic(api_key=self.api_key)

        try:
            from typing import Any
            stream: Any
            with client.messages.stream(
                model=self.model,
                max_tokens=8192,
                system=resolved_system or "Be precise and concise.",
                messages=chat_messages,  # type: ignore
            ) as stream:
                for text_chunk in stream.text_stream:
                    yield text_chunk

        except _anthropic.AuthenticationError as exc:
            raise ProviderError(
                "Invalid Anthropic API key. "
                "Check your config or the ANTHROPIC_API_KEY environment variable."
            ) from exc
        except _anthropic.BadRequestError as exc:
            raise ProviderError(f"Anthropic rejected the request: {exc}") from exc
        except _anthropic.RateLimitError as exc:
            raise ProviderError("Anthropic rate limit reached. Try again shortly.") from exc
        except _anthropic.APIConnectionError as exc:
            raise ProviderError(
                "Could not connect to Anthropic. Check your network connection."
            ) from exc
        except _anthropic.APIStatusError as exc:
            raise ProviderError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc

    @classmethod
    def list_models(
        cls,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> list[str]:
        return cls.MODELS
