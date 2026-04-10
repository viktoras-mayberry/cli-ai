from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from .base import Tool

if TYPE_CHECKING:
    from ..repl import REPLSession

class FileReadTool(Tool):
    name = "file_read"
    help = "Read the contents of a local file"

    def run(self, args: object, config: object) -> int | None:
        return 0

    def run_repl(self, raw_args: list[str], session: "REPLSession") -> str | None:
        if not raw_args:
            return "Error: missing filename"
        filename = raw_args[0]
        try:
            content = Path(filename).read_text(encoding="utf-8")
            return f"--- {filename} ---\n{content}\n--- end of {filename} ---"
        except Exception as e:
            return f"Error reading {filename}: {e}"

class BashTool(Tool):
    name = "bash"
    help = "Execute a bash command"

    def run(self, args: object, config: object) -> int | None:
        return 0

    def run_repl(self, raw_args: list[str], session: "REPLSession") -> str | None:
        if not raw_args:
            return "Error: missing command"
        cmd = " ".join(raw_args)
        
        # Human confirmation
        from ..display import print_warning
        print_warning(f"\nAgent wants to run command:\n  [bold yellow]{cmd}[/bold yellow]")
        try:
            ans = input("Allow execution? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                return f"Error: Command execution cancelled by user."
        except (EOFError, KeyboardInterrupt):
            return "Error: Command execution cancelled by user."

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            output = ""
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            output += f"Exit code: {result.returncode}"
            return output
        except Exception as e:
            return f"Command failed: {e}"

class FileEditTool(Tool):
    name = "file_edit"
    help = "Edit a file using search and replace."

    def run(self, args: object, config: object) -> int | None:
        return 0

    def run_repl(self, raw_args: list[str], session: "REPLSession") -> str | None:
        if not raw_args:
            return "Error: missing arguments"
        
        full_args = " ".join(raw_args)
        parts = full_args.split("|||")
        if len(parts) != 2:
            return "Error: format must be `<filename> <search_text> ||| <replace_text>`"
        
        left = parts[0].strip().split(" ", 1)
        if len(left) < 2:
            return "Error: format must be `<filename> <search_text>` before `|||`"
        
        filename = left[0].strip()
        search_text = left[1]
        replace_text = parts[1]

        # Strip outer quotes or codeblock fences if AI added them
        if search_text.startswith("```"):
            search_text = search_text.split("\n", 1)[-1]
        if search_text.endswith("```"):
            search_text = search_text.rsplit("\n", 1)[0]
            
        if replace_text.startswith("```"):
            replace_text = replace_text.split("\n", 1)[-1]
        if replace_text.endswith("```"):
            replace_text = replace_text.rsplit("\n", 1)[0]
            
        try:
            file_path = Path(filename)
            if not file_path.exists():
                return f"Error: {filename} does not exist."
                
            content = file_path.read_text(encoding="utf-8")
            if search_text not in content:
                return f"Error: The exact search string was not found in the file."
            
            new_content = content.replace(search_text, replace_text)
            file_path.write_text(new_content, encoding="utf-8")
            return f"Successfully updated {filename}."
        except Exception as e:
            return f"Failed to edit {filename}: {e}"
