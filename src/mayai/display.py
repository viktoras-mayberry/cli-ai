import sys

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

# Output mode: "normal" | "raw" | "json"
# - normal: full decorators, streaming
# - raw:    bare response text only, streaming, no decorators
# - json:   full response collected then printed as JSON
_output_mode: str = "normal"


def set_output_mode(mode: str) -> None:
    global _output_mode
    _output_mode = mode


def get_output_mode() -> str:
    return _output_mode


def is_silent() -> bool:
    """True when decorative output should be suppressed (raw / json modes)."""
    return _output_mode in ("raw", "json")


# ------------------------------------------------------------------ #
# Streaming                                                            #
# ------------------------------------------------------------------ #

def print_stream_chunk(text: str) -> None:
    """Print a streaming text chunk. Suppressed in json mode (we buffer instead)."""
    if _output_mode != "json":
        print(text, end="", flush=True)


def print_response_end() -> None:
    if _output_mode != "json":
        print()


# ------------------------------------------------------------------ #
# Informational (suppressed in raw/json modes)                        #
# ------------------------------------------------------------------ #

def print_info(message: str) -> None:
    if not is_silent():
        console.print(f"[bold cyan]{message}[/bold cyan]")


def print_error(message: str) -> None:
    # Errors always go to stderr regardless of output mode
    err_console.print(f"[bold red]Error:[/bold red] {message}")


def print_warning(message: str) -> None:
    if not is_silent():
        console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


def print_success(message: str) -> None:
    if not is_silent():
        console.print(f"[bold green]{message}[/bold green]")


def print_provider_header(provider: str, model: str) -> None:
    if not is_silent():
        console.print(
            f"\n[bold green]MAYAI[/bold green] "
            f"[dim]({provider} / {model})[/dim]"
        )


def print_user_prompt(provider: str, model: str) -> None:
    if not is_silent():
        console.print(
            f"\n[bold yellow]You[/bold yellow] "
            f"[dim]({provider} / {model})[/dim]: ",
            end="",
        )


# ------------------------------------------------------------------ #
# Cost display                                                         #
# ------------------------------------------------------------------ #

def print_cost_line(
    input_tokens: int,
    output_tokens: int,
    cost: float | None,
    session_cost: float | None = None,
) -> None:
    """Show a subtle cost line after each response in normal mode."""
    if is_silent():
        return
    parts = [
        f"~{_fmt_tok(input_tokens)} in",
        f"~{_fmt_tok(output_tokens)} out",
    ]
    if cost is not None:
        from .costs import format_cost
        parts.append(f"est. {format_cost(cost)}")
        if session_cost is not None and session_cost > cost:
            parts.append(f"session total: {format_cost(session_cost)}")
    console.print("[dim]" + " | ".join(parts) + "[/dim]")


def _fmt_tok(n: int) -> str:
    return f"{n / 1000:.1f}K tokens" if n >= 1000 else f"{n} tokens"


# ------------------------------------------------------------------ #
# Tables & structured output                                           #
# ------------------------------------------------------------------ #

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
            preview = preview[:200] + "..."
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


def print_patterns_table(patterns: dict) -> None:
    if not patterns:
        print_info(
            "No patterns defined. Run 'mayai config init' or add "
            r"[patterns.\<name\>] sections to your config file."
        )
        return
    table = Table(title="Prompt Patterns", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold yellow")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("System Prompt Preview")
    for name, pat in patterns.items():
        preview = pat.get("system_prompt", "")[:60]
        if len(pat.get("system_prompt", "")) > 60:
            preview += "..."
        table.add_row(
            name,
            pat.get("provider", "(default)"),
            pat.get("model", "(default)"),
            preview,
        )
    console.print(table)


def print_banner(provider: str, model: str, session_name: str = "", pattern_name: str = "") -> None:
    extras = ""
    if session_name:
        extras += f"\n  [dim]Session:[/dim] [bold]{session_name}[/bold]"
    if pattern_name:
        extras += f"\n  [dim]Pattern:[/dim] [bold]{pattern_name}[/bold]"
    content = (
        "[bold white]Welcome to MAYAI — your AI assistant[/bold white]\n\n"
        f"  [dim]Provider:[/dim] [cyan]{provider}[/cyan]   "
        f"[dim]Model:[/dim] [cyan]{model}[/cyan]{extras}\n\n"
        "[bold white]What you can do:[/bold white]\n"
        "  [bold cyan]Chat[/bold cyan]        Just type your question to start a conversation\n"
        "  [bold cyan]/research[/bold cyan]   Search the web and get answers with sources\n"
        "  [bold cyan]/compare[/bold cyan]    Ask multiple AI models at once and compare\n"
        "  [bold cyan]/find[/bold cyan]       Search for files on your computer\n"
        "  [bold cyan]/open[/bold cyan]       Read and summarize any file (PDF, Word, Excel...)\n"
        "  [bold cyan]/help[/bold cyan]       See all commands\n"
    )
    console.print(
        Panel(
            content,
            title="[bold magenta]MAYAI[/bold magenta]",
            border_style="magenta",
            padding=(1, 2),
        )
    )


def print_branches_table(branches: list[dict]) -> None:
    if not branches:
        print_info("No branches yet. Use /branch <name> to create one.")
        return
    table = Table(title="Conversation Branches", show_header=True, header_style="bold cyan")
    table.add_column("Branch", style="bold white")
    table.add_column("Messages", justify="right")
    table.add_column("Active", justify="center")
    for b in branches:
        active_marker = "[bold green]*[/bold green]" if b["active"] else ""
        table.add_row(b["name"], str(b["messages"]), active_marker)
    console.print(table)


def print_history_table(rows: list[dict]) -> None:
    from .costs import format_cost, format_tokens
    if not rows:
        print_info("No history found. Start chatting to build up your log.")
        return
    table = Table(title="Query History", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("When", no_wrap=True)
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Query", max_width=48)
    table.add_column("Cost", justify="right")
    for row in rows:
        query_preview = (row["user_message"] or "")[:80]
        if len(row["user_message"] or "") > 80:
            query_preview += "..."
        cost_str = (
            format_cost(row["cost_usd"])
            if row.get("cost_usd") is not None
            else "-"
        )
        table.add_row(
            str(row["id"]),
            (row["ts"] or "")[:16].replace("T", " "),
            row["provider"],
            row["model"],
            query_preview,
            cost_str,
        )
    console.print(table)


def print_history_detail(row: dict) -> None:
    """Print a single history entry in full."""
    from .costs import format_cost, format_tokens
    console.print(f"\n[bold cyan]#{row['id']}[/bold cyan]  {row['ts']}")
    console.print(f"[dim]Provider:[/dim] {row['provider']} / {row['model']}")
    if row.get("pattern"):
        console.print(f"[dim]Pattern:[/dim] {row['pattern']}")
    if row.get("session_name"):
        console.print(f"[dim]Session:[/dim] {row['session_name']}")
    console.print(f"\n[bold yellow]You:[/bold yellow]\n{row['user_message']}")
    console.print(f"\n[bold green]MAYAI:[/bold green]\n{row['response']}")
    in_tok = row.get("input_tokens") or 0
    out_tok = row.get("output_tokens") or 0
    cost = row.get("cost_usd")
    console.print(
        f"\n[dim]Tokens: {format_tokens(in_tok)} in / {format_tokens(out_tok)} out"
        + (f"  |  Cost: {format_cost(cost)}" if cost is not None else "")
        + "[/dim]"
    )


def print_stats(stats: dict) -> None:
    from .costs import format_cost, format_tokens
    if not stats or not stats.get("total_queries"):
        print_info("No history yet. Start chatting to see stats.")
        return

    table = Table(title="MAYAI Usage Stats", show_header=False, box=None)
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Total queries",    str(stats["total_queries"]))
    table.add_row("Total cost",       format_cost(stats["total_cost_usd"]))
    table.add_row("Input tokens",     format_tokens(stats["total_input_tokens"]))
    table.add_row("Output tokens",    format_tokens(stats["total_output_tokens"]))
    table.add_row("First query",      (stats.get("first_query") or "-")[:16].replace("T", " "))
    table.add_row("Last query",       (stats.get("last_query") or "-")[:16].replace("T", " "))
    console.print(table)

    if stats.get("by_provider"):
        console.print("\n[bold cyan]By provider:[/bold cyan]")
        for p in stats["by_provider"]:
            console.print(f"  {p['provider']}: {p['cnt']} queries")

    if stats.get("top_models"):
        console.print("\n[bold cyan]Top models:[/bold cyan]")
        for m in stats["top_models"]:
            console.print(f"  {m['model']}: {m['cnt']} queries")


def print_help() -> None:
    table = Table(show_header=True, header_style="bold cyan", title="MAYAI Commands")
    table.add_column("Command", style="bold yellow", no_wrap=True)
    table.add_column("Description")

    section_rows = [
        ("[bold white]--- Core Features ---[/bold white]", ""),
        ("/research <question>", "Search the web and get answers with cited sources"),
        ("/compare <question>", "Ask multiple AI models and compare their answers"),
        ("/find <description>", "Search for files on your computer"),
        ("/open <filepath>", "Read any file (PDF, Word, Excel, images, text...)"),
        ("/move <description>", "Move, rename, or organize files"),
        ("/convert <file> to <format>", "Convert a file to another format"),
        ("", ""),
        ("[bold white]--- Chat ---[/bold white]", ""),
        ("/use <provider> [model]", "Switch AI provider (e.g. /use claude, /use gpt)"),
        ("/switch <provider> [model]", "Same as /use"),
        ("/clear", "Clear conversation history"),
        ("/models", "List models for the current provider"),
        ("/cost", "Show session token usage and cost estimate"),
        ("", ""),
        ("[bold white]--- Sessions ---[/bold white]", ""),
        ("/save [name]", "Save current conversation"),
        ("/load <name>", "Load a saved conversation"),
        ("/sessions", "List all saved sessions"),
        ("/sessions delete <name>", "Delete a saved session"),
        ("/branch <name>", "Fork conversation into a new branch"),
        ("/checkout <name>", "Switch to a different branch"),
        ("/branches", "List all branches"),
        ("", ""),
        ("[bold white]--- Other ---[/bold white]", ""),
        ("/pattern <name>", "Apply a prompt pattern"),
        ("/patterns", "List all defined patterns"),
        ("/history", "Show conversation history"),
        ("/help", "Show this message"),
        ("/exit  or  /quit  or  /bye", "Exit MAYAI (auto-saves conversation)"),
    ]
    for cmd, desc in section_rows:
        table.add_row(cmd, desc)
    console.print(table)


def print_suggestions() -> None:
    """Show contextual suggestions after a response."""
    if is_silent():
        return
    console.print(
        "[dim]Tip: /research for sourced answers | "
        "/compare to ask multiple AIs | "
        "/find to search your files[/dim]"
    )


def print_comparison(results: list[dict]) -> None:
    """Display multi-model comparison results as Rich panels."""
    if not results:
        print_warning("No providers are configured with API keys. Run: mayai config init")
        return

    for result in results:
        title = f"[bold]{result['provider']}[/bold] / {result['model']}"
        if result.get("error"):
            console.print(Panel(
                f"[red]Error: {result['error']}[/red]",
                title=title, border_style="red", padding=(1, 2),
            ))
        else:
            response_text = result["response"] or "(empty response)"
            console.print(Panel(
                response_text,
                title=title, border_style="cyan", padding=(1, 2),
            ))


def print_research_result(answer: str, citations: list[str] | None = None) -> None:
    """Display a research answer with numbered source citations."""
    console.print(Panel(
        answer,
        title="[bold green]Research Result[/bold green]",
        border_style="green", padding=(1, 2),
    ))
    if citations:
        sources_text = "\n".join(
            f"  [bold cyan][{i + 1}][/bold cyan] {url}"
            for i, url in enumerate(citations)
        )
        console.print(Panel(
            sources_text,
            title=f"[bold cyan]Sources ({len(citations)})[/bold cyan]",
            border_style="cyan", padding=(1, 2),
        ))


def print_file_results(files: list[dict]) -> None:
    """Display file search results in a table."""
    if not files:
        print_info("No files found matching your description.")
        return
    table = Table(title="Files Found", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", style="bold white")
    table.add_column("Path", style="dim")
    table.add_column("Match", justify="center")
    table.add_column("Snippet", style="white", max_width=48)
    table.add_column("Size", justify="right")
    table.add_column("Modified", no_wrap=True)
    for i, f in enumerate(files, 1):
        table.add_row(
            str(i),
            f.get("name", ""),
            f.get("path", ""),
            ("content" if f.get("match_type") == "content" else "name"),
            (f.get("snippet", "") or "").replace(">>>", "[bold yellow]").replace("<<<", "[/bold yellow]"),
            f.get("size", ""),
            f.get("modified", ""),
        )
    console.print(table)


def print_file_operation_preview(operations: list[dict]) -> None:
    """Display a preview of file operations before confirmation."""
    if not operations:
        return
    table = Table(title="Planned Operations", show_header=True, header_style="bold yellow")
    table.add_column("Action", style="bold")
    table.add_column("From")
    table.add_column("To")
    for op in operations:
        table.add_row(op.get("action", ""), op.get("source", ""), op.get("dest", ""))
    console.print(table)


