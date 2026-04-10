from .base import Tool, ToolFactory
from .registry import ToolRegistration, get_repl_commands, get_tool, get_tools, register_tool

__all__ = [
    "Tool",
    "ToolFactory",
    "ToolRegistration",
    "get_repl_commands",
    "get_tool",
    "get_tools",
    "register_tool",
]

from .agent_tools import FileReadTool, BashTool, FileEditTool
register_tool("file_read", FileReadTool, source="core")
register_tool("bash", BashTool, source="core")
register_tool("file_edit", FileEditTool, source="core")

