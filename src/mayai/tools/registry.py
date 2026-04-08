from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import Tool, ToolFactory


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    tool: Tool
    source: str = "plugin"


_TOOLS: dict[str, ToolRegistration] = {}


def register_tool(name: str, obj: Any, *, allow_override: bool = False, source: str = "plugin") -> bool:
    key = name.lower().strip()
    if not key:
        return False
    if not allow_override and key in _TOOLS:
        return False

    tool: Tool
    if isinstance(obj, Tool):
        tool = obj
    elif callable(obj):
        tool = obj()  # type: ignore[misc]
        if not isinstance(tool, Tool):
            return False
    else:
        return False

    _TOOLS[key] = ToolRegistration(name=key, tool=tool, source=source)
    return True


def get_tools() -> dict[str, ToolRegistration]:
    return dict(_TOOLS)


def get_tool(name: str) -> ToolRegistration | None:
    return _TOOLS.get(name.lower().strip())


def get_repl_commands() -> dict[str, ToolRegistration]:
    """Map explicit repl_command strings (e.g. '/jira') to tools."""
    out: dict[str, ToolRegistration] = {}
    for reg in _TOOLS.values():
        cmd = getattr(reg.tool, "repl_command", None)
        if isinstance(cmd, str) and cmd.startswith("/"):
            out[cmd.lower()] = reg
    return out

