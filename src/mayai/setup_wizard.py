"""Interactive first-run setup wizard for non-technical users."""

from __future__ import annotations

import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import CONFIG_DIR, CONFIG_FILE, Config

console = Console(highlight=False)


def _input_safe(prompt: str, default: str = "") -> str:
    try:
        val = input(prompt).strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        return default


def _check_ollama() -> bool:
    """Try to connect to local Ollama server."""
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def run_setup_wizard() -> Config:
    """Run the interactive setup wizard and return the configured Config."""
    console.print(Panel(
        "[bold white]Welcome to MAYAI Setup![/bold white]\n\n"
        "Let's get you set up so you can start chatting with AI, "
        "researching topics, and managing your files.\n\n"
        "This will only take a minute.",
        title="[bold magenta]MAYAI[/bold magenta]",
        border_style="magenta",
        padding=(1, 2),
    ))

    providers_config: dict = {}
    default_provider = "openai"

    # Check for Ollama first (free, no key)
    console.print("\n[bold cyan]Step 1:[/bold cyan] Checking for local AI (Ollama)...")
    if _check_ollama():
        console.print("[bold green]  Ollama detected![/bold green] You can use local AI models for free.")
        providers_config["ollama"] = {
            "base_url": "http://localhost:11434",
            "default_model": "llama3.2",
        }
        default_provider = "ollama"
    else:
        console.print("  [dim]Ollama not found. No worries — you can set it up later.[/dim]")
        console.print("  [dim]Get it free at: https://ollama.com[/dim]")

    # Provider table
    console.print("\n[bold cyan]Step 2:[/bold cyan] Which AI providers do you have API keys for?\n")

    provider_info = [
        ("openai", "OPENAI_API_KEY", "OpenAI (GPT-4o, etc.)", "https://platform.openai.com/api-keys"),
        ("anthropic", "ANTHROPIC_API_KEY", "Anthropic (Claude)", "https://console.anthropic.com/"),
        ("gemini", "GEMINI_API_KEY", "Google Gemini", "https://aistudio.google.com/apikey"),
        ("perplexity", "PERPLEXITY_API_KEY", "Perplexity (web search)", "https://www.perplexity.ai/settings/api"),
        ("groq", "GROQ_API_KEY", "Groq (fast inference)", "https://console.groq.com/keys"),
    ]

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Provider")
    table.add_column("Get a key at")
    for i, (_, _, label, url) in enumerate(provider_info, 1):
        table.add_row(str(i), label, f"[dim]{url}[/dim]")
    console.print(table)

    console.print("\n[dim]Enter your API keys below. Press Enter to skip any you don't have.[/dim]\n")

    for name, env_var, label, _ in provider_info:
        env_key = os.environ.get(env_var, "")
        if env_key:
            console.print(f"  [green]{label}:[/green] detected from environment variable")
            providers_config[name] = {"api_key": env_key}
            continue

        key = _input_safe(f"  {label} API key (or Enter to skip): ")
        if key:
            providers_config[name] = {"api_key": key}

    # Pick default provider:
    # - Prefer OpenAI if an OpenAI key is available (user request)
    # - Else prefer Ollama if detected
    # - Else pick the first configured provider in the list above
    if "openai" in providers_config:
        default_provider = "openai"
    elif "ollama" in providers_config:
        default_provider = "ollama"
    else:
        for name, _, _, _ in provider_info:
            if name in providers_config:
                default_provider = name
                break

    # Choose default
    configured = [name for name in providers_config if name != "ollama" or _check_ollama()]
    if len(configured) > 1:
        console.print(f"\n[bold cyan]Step 3:[/bold cyan] Your default provider will be: [bold]{default_provider}[/bold]")
        change = _input_safe("  Change it? Enter provider name or press Enter to keep: ")
        if change and change.lower() in configured:
            default_provider = change.lower()

    # Build and save config
    config_data = {
        "defaults": {
            "provider": default_provider,
            "system_prompt": "Be precise and concise.",
        },
        "providers": {},
        "patterns": {
            "research": {
                "system_prompt": (
                    "You are a thorough research assistant. "
                    "Search for current, accurate information. "
                    "Always cite your sources and include URLs."
                ),
                "provider": "perplexity",
                "model": "sonar-pro",
            },
            "summarize": {
                "system_prompt": (
                    "Summarize the following content concisely. "
                    "Use bullet points for key information. Be brief and direct."
                ),
            },
            "explain": {
                "system_prompt": (
                    "Explain this clearly and simply as if teaching someone new to the topic. "
                    "Use concrete examples and analogies where helpful."
                ),
            },
        },
    }

    # Merge provider configs with defaults
    default_models = {
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-20250514",
        "gemini": "gemini-2.0-flash",
        "perplexity": "sonar-pro",
        "groq": "llama-3.3-70b-versatile",
        "ollama": "llama3.2",
    }
    for name, pconf in providers_config.items():
        pconf.setdefault("default_model", default_models.get(name, ""))
        config_data["providers"][name] = pconf

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import tomli_w
        with open(CONFIG_FILE, "wb") as f:
            tomli_w.dump(config_data, f)
    except ImportError:
        console.print("[yellow]Warning: tomli-w not installed. Config saved to memory only.[/yellow]")

    console.print(Panel(
        f"[bold green]Setup complete![/bold green]\n\n"
        f"  Default provider: [bold]{default_provider}[/bold]\n"
        f"  Providers ready:  [bold]{', '.join(sorted(providers_config.keys())) or 'none'}[/bold]\n"
        f"  Config saved to:  [dim]{CONFIG_FILE}[/dim]\n\n"
        "You're ready to go! Just type [bold]mayai[/bold] to start chatting.\n\n"
        "[dim]Quick start:[/dim]\n"
        "  [cyan]mayai[/cyan]                              Start chatting\n"
        "  [cyan]mayai --research 'your question'[/cyan]   Get answers with sources\n"
        "  [cyan]mayai --find 'tax documents'[/cyan]       Find files on your computer\n"
        "  [cyan]mayai --compare 'your question'[/cyan]    Compare multiple AI models",
        title="[bold magenta]All Set![/bold magenta]",
        border_style="green",
        padding=(1, 2),
    ))

    return Config(config_data)
