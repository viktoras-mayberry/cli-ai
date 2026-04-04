import sys

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich import print as rprint

# force_terminal=True ensures rich uses ANSI sequences even in Windows terminals
# that don't advertise full VT support; highlight=False avoids spurious markup.
console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)


def print_stream_chunk(text: str) -> None:
    """Print a streaming text chunk immediately, no newline."""
    print(text, end="", flush=True)


def print_response_end() -> None:
    """Terminate the streaming line."""
    print()


def print_info(message: str) -> None:
    console.print(f"[bold cyan]{message}[/bold cyan]")


def print_error(message: str) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {message}")


def print_warning(message: str) -> None:
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


def print_success(message: str) -> None:
    console.print(f"[bold green]{message}[/bold green]")


def print_provider_header(provider: str, model: str) -> None:
    console.print(
        f"\n[bold green]MAYAI[/bold green] "
        f"[dim]({provider} / {model})[/dim]"
    )


def print_user_prompt(provider: str, model: str) -> None:
    console.print(
        f"\n[bold yellow]You[/bold yellow] "
        f"[dim]({provider} / {model})[/dim]: ",
        end="",
    )


def print_models_table(provider: str, models: list[str], default_model: str = "") -> None:
    table = Table(title=f"Models: {provider}", show_header=True, header_style="bold cyan")
    table.add_column("Model", style="white")
    table.add_column("Default", justify="center")
    for m in models:
        marker = "[bold green]*[/bold green]" if m == default_model else ""
        table.add_row(m, marker)
    console.print(table)


def print_history(messages: list[dict]) -> None:
    chat = [m for m in messages if m["role"] != "system"]
    if not chat:
        print_info("No conversation history yet.")
        return
    for msg in chat:
        role_label = (
            "[bold yellow]You[/bold yellow]"
            if msg["role"] == "user"
            else "[bold green]MAYAI[/bold green]"
        )
        preview = msg["content"]
        if len(preview) > 200:
            preview = preview[:200] + "…"
        console.print(f"{role_label}: {preview}")


def print_sessions_table(sessions: list[dict]) -> None:
    if not sessions:
        print_info("No saved sessions. Use /save to save the current conversation.")
        return
    table = Table(title="Saved Sessions", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold white")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Messages", justify="right")
    table.add_column("Saved At")
    for s in sessions:
        table.add_row(
            s["name"],
            s["provider"],
            s["model"],
            str(s["message_count"]),
            s["saved_at"],
        )
    console.print(table)


def print_banner(provider: str, model: str, session_name: str = "") -> None:
    session_line = (
        f"\n[dim]Session: [bold]{session_name}[/bold][/dim]" if session_name else ""
    )
    content = (
        f"[bold white]Provider:[/bold white] [cyan]{provider}[/cyan]   "
        f"[bold white]Model:[/bold white] [cyan]{model}[/cyan]{session_line}\n\n"
        "[dim]Commands: /clear  /switch <provider> [model]  /save [name]  "
        "/load <name>  /sessions  /models  /history  /help  /exit[/dim]"
    )
    console.print(
        Panel(
            content,
            title="[bold magenta]MAYAI - Multi-provider AI CLI[/bold magenta]",
            border_style="magenta",
            padding=(1, 2),
        )
    )


def print_help() -> None:
    table = Table(show_header=True, header_style="bold cyan", title="Available Commands")
    table.add_column("Command", style="bold yellow", no_wrap=True)
    table.add_column("Description")
    rows = [
        ("/clear", "Clear conversation history"),
        ("/switch <provider> [model]", "Switch to a different provider (and optionally model)"),
        ("/save [name]", "Save current conversation (auto-names if no name given)"),
        ("/load <name>", "Load a saved conversation"),
        ("/sessions", "List all saved sessions"),
        ("/models", "List available models for the current provider"),
        ("/history", "Show conversation history"),
        ("/help", "Show this help message"),
        ("/exit  or  /quit", "Exit MAYAI"),
    ]
    for cmd, desc in rows:
        table.add_row(cmd, desc)
    console.print(table)
