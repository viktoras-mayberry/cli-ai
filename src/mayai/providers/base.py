from abc import ABC, abstractmethod
from typing import Generator


class BaseProvider(ABC):
    # Subclasses must define these at the class level
    name: str
    default_model: str

    def __init__(
        self,
        api_key: str | None,
        model: str,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        # Subclasses that need a configurable base URL store it here
        if base_url is not None:
            self.base_url = base_url

    @abstractmethod
    def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str = "Be precise and concise.",
    ) -> Generator[str, None, None]:
        """Yield text chunks as they arrive from the provider.

        Parameters
        ----------
        messages:
            Conversation history in OpenAI format:
            [{"role": "user"|"assistant"|"system", "content": "..."}]
            System messages are handled by each provider as needed.
        system_prompt:
            The active system prompt. Passed separately so providers
            that do not support system messages in the array (e.g.
            Anthropic) can handle it correctly.
        """
        ...

    @classmethod
    @abstractmethod
    def list_models(
        cls,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> list[str]:
        """Return available model names for this provider."""
        ...
