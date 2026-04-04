class Conversation:
    """Maintains conversation history in OpenAI message format."""

    def __init__(self, system_prompt: str = "Be precise and concise.") -> None:
        self._system_prompt = system_prompt
        self._messages: list[dict] = []

    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> list[dict]:
        """Return the full message history (no system message injected here —
        providers handle the system prompt via the separate parameter)."""
        return list(self._messages)

    def clear(self) -> None:
        self._messages = []

    def is_empty(self) -> bool:
        return len(self._messages) == 0

    def __len__(self) -> int:
        return len(self._messages)
