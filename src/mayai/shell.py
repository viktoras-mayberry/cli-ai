"""Shell command generation mode.

Translates natural language into a shell command using the AI, shows the
command to the user, and asks for confirmation before executing it.
"""

import os
import platform
import subprocess
import sys

from .display import print_error, print_info, print_success, print_warning
from .exceptions import MayaiError
from .providers.base import BaseProvider

_SYSTEM_PROMPT = """You are a shell command expert.
The user will describe what they want to do in plain English.
Your ONLY output must be the exact shell command to run — nothing else.
No explanation, no markdown, no code fences, no commentary.
Just the raw command string on a single line.

Rules:
- Output exactly one command (chain with && or | if needed)
- Use flags appropriate for the detected OS and shell
- Prefer safe, non-destructive operations where possible
- If the request is ambiguous, output the safest interpretation
- Never output multiple lines or explanations"""


def _detect_shell_info() -> str:
    """Return a short string describing the OS and shell for context."""
    os_name = platform.system()  # Windows / Linux / Darwin
    shell = os.environ.get("SHELL", "") or os.environ.get("COMSPEC", "")
    shell_name = os.path.basename(shell) if shell else "unknown"
    return f"OS: {os_name}, Shell: {shell_name}"


def generate_shell_command(
    description: str,
    provider: BaseProvider,
) -> str | None:
    """Ask the provider to generate a shell command. Returns the command string or None."""
    shell_info = _detect_shell_info()
    messages = [
        {
            "role": "user",
            "content": f"[{shell_info}]\n{description}",
        }
    ]
    try:
        chunks = []
        for chunk in provider.stream_chat(messages, _SYSTEM_PROMPT):
            chunks.append(chunk)
        return "".join(chunks).strip()
    except MayaiError as exc:
        print_error(f"Failed to generate command: {exc}")
        return None


def run_shell_mode(
    description: str,
    provider: BaseProvider,
    provider_name: str,
    model: str,
    auto_confirm: bool = False,
) -> None:
    """Full shell mode flow: generate → confirm → execute."""
    from rich.console import Console
    from rich.panel import Panel
    c = Console(highlight=False)

    print_info(f"Generating command via {provider_name} / {model}...")
    command = generate_shell_command(description, provider)

    if not command:
        print_error("No command generated.")
        sys.exit(1)

    # Display the generated command prominently
    c.print(
        Panel(
            f"[bold yellow]{command}[/bold yellow]",
            title="[bold cyan]Generated Command[/bold cyan]",
            border_style="cyan",
            padding=(0, 2),
        )
    )

    if auto_confirm:
        confirmed = True
    else:
        try:
            c.print("[bold]Run this command?[/bold] [dim]\\[y/N][/dim] ", end="")
            answer = input().strip().lower()
            confirmed = answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            confirmed = False

    if not confirmed:
        print_warning("Cancelled.")
        return

    print_info("Running...")
    try:
        # Use shell=True so the command string is interpreted by the OS shell
        result = subprocess.run(command, shell=True)
        if result.returncode == 0:
            print_success(f"Done (exit code 0).")
        else:
            print_warning(f"Command exited with code {result.returncode}.")
    except Exception as exc:
        print_error(f"Execution failed: {exc}")
        sys.exit(1)
