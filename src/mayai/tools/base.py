from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import argparse

    from ..config import Config
    from ..repl import REPLSession


class Tool(ABC):
    """A MAYAI tool plugin.

    Tools can integrate with:
    - CLI: `mayai tool <name> ...`
    - REPL: `/tool <name> ...` and optionally a dedicated slash command.
    """

    name: str
    help: str = ""
    repl_command: str | None = None  # e.g. "/jira"

    def add_arguments(self, parser: "argparse.ArgumentParser") -> None:  # noqa: ARG002
        """Add CLI args for `mayai tool <name> ...`."""

    @abstractmethod
    def run(self, args: object, config: "Config") -> int | None:
        """Execute tool from CLI. Return process exit code (0/1) or None."""

    def run_repl(self, raw_args: list[str], session: "REPLSession") -> str | None:  # noqa: ARG002
        """Execute tool from REPL. Returns optional output to feed back to the AI."""
        return None


class ToolFactory(Protocol):
    def __call__(self) -> Tool: ...

