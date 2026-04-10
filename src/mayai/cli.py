"""MAYAI — Multi-provider AI CLI entry point."""

import argparse
import json
import sys

from . import __version__
from .config import CONFIG_FILE, Config
from .conversation import Conversation
from .costs import count_conversation_tokens, estimate_cost, estimate_tokens, format_cost
from .history import delete_history, get_stats, log_exchange, search_history
from .display import (
    get_output_mode,
    print_error,
    print_history_detail,
    print_history_table,
    print_info,
    print_models_table,
    print_patterns_table,
    print_response_end,
    print_sessions_table,
    print_stats,
    print_stream_chunk,
    print_success,
    print_warning,
    set_output_mode,
)
from .exceptions import MayaiError
from .providers import PROVIDER_REGISTRY, get_provider, get_provider_names
from .providers.ollama import OllamaProvider
from .plugins import get_last_loaded_plugins, load_plugins
from .repl import REPLSession
from .sessions import delete_session, list_sessions, load_session
from .shell import run_shell_mode
from .tools import get_tool, get_tools


# ------------------------------------------------------------------ #
# Provider resolution                                                  #
# ------------------------------------------------------------------ #

def _resolve_provider(provider_name: str, model_arg: str | None, config: Config):
    """Return (provider_instance, resolved_model_name)."""
    provider_name = provider_name.lower()

    if provider_name not in PROVIDER_REGISTRY:
        print_error(
            f"Unknown provider '{provider_name}'.\n"
            f"Available: {', '.join(get_provider_names())}"
        )
        sys.exit(1)

    cls = PROVIDER_REGISTRY[provider_name]

    model = (
        model_arg
        or config.get_default_model(provider_name)
        or cls.default_model
    )

    if provider_name != "ollama" and hasattr(cls, "MODELS") and cls.MODELS:
        if model not in cls.MODELS:
            print_error(
                f"Model '{model}' is not available for {provider_name}.\n"
                f"Run 'mayai models -p {provider_name}' to see available models."
            )
            sys.exit(1)

    api_key = config.resolve_api_key(provider_name)
    if provider_name != "ollama" and not api_key:
        print_error(
            f"No API key found for '{provider_name}'.\n"
            f"Set it with: mayai config set providers.{provider_name}.api_key YOUR_KEY\n"
            f"Or set the {provider_name.upper()}_API_KEY environment variable."
        )
        sys.exit(1)

    base_url = config.get_ollama_base_url() if provider_name == "ollama" else None

    try:
        provider = get_provider(
            name=provider_name,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
    except MayaiError as exc:
        print_error(str(exc))
        sys.exit(1)

    return provider, model


# ------------------------------------------------------------------ #
# Subcommand handlers                                                  #
# ------------------------------------------------------------------ #

def _cmd_config(args: argparse.Namespace, config: Config) -> None:
    action = getattr(args, "config_action", None)

    if action == "show":
        print(json.dumps(config.as_dict(), indent=2))

    elif action == "set":
        if not args.key or not args.value:
            print_error("Usage: mayai config set <key.path> <value>")
            sys.exit(1)
        config.set(args.key, args.value)
        try:
            config.save()
            print_success(f"Saved: {args.key} = {args.value}")
        except RuntimeError as exc:
            print_error(str(exc))
            sys.exit(1)

    elif action == "path":
        print(str(CONFIG_FILE))

    elif action == "init":
        try:
            config.init()
            print_success(f"Config initialised at: {CONFIG_FILE}")
        except RuntimeError as exc:
            print_error(str(exc))
            sys.exit(1)

    else:
        print_warning("Usage: mayai config [show|set|path|init]")


def _cmd_sessions(args: argparse.Namespace) -> None:
    action = getattr(args, "sessions_action", None)
    if action == "delete":
        if not args.name:
            print_error("Usage: mayai sessions delete <name>")
            sys.exit(1)
        try:
            delete_session(args.name)
            print_success(f"Deleted session '{args.name}'.")
        except FileNotFoundError as exc:
            print_error(str(exc))
            sys.exit(1)
    else:
        print_sessions_table(list_sessions())


def _cmd_models(args: argparse.Namespace, config: Config) -> None:
    target = getattr(args, "provider", None)

    if target:
        target = target.lower()
        if target not in PROVIDER_REGISTRY:
            print_error(
                f"Unknown provider '{target}'. Available: {', '.join(get_provider_names())}"
            )
            sys.exit(1)
        cls = PROVIDER_REGISTRY[target]
        api_key = config.resolve_api_key(target)
        if target == "ollama":
            base_url = config.get_ollama_base_url()
            models = OllamaProvider.list_models(api_key=None, base_url=base_url)
            if not models:
                print_warning("No Ollama models found. Is Ollama running? (ollama serve)")
                return
        else:
            models = cls.list_models(api_key=api_key)
        print_models_table(target, models, cls.default_model)
    else:
        for name in get_provider_names():
            cls = PROVIDER_REGISTRY[name]
            if name == "ollama":
                print_models_table(name, ["(run 'mayai models -p ollama' to list local models)"], "")
            else:
                print_models_table(name, getattr(cls, "MODELS", ["(dynamic)"]), cls.default_model)


def _cmd_patterns(args: argparse.Namespace, config: Config) -> None:
    print_patterns_table(config.list_patterns())


def _cmd_plugins() -> None:
    loaded = get_last_loaded_plugins()
    if not loaded:
        print_warning("Plugins have not been loaded yet.")
        return

    if loaded.providers:
        print_info(f"Providers: {', '.join(sorted(loaded.providers.keys()))}")
    else:
        print_info("Providers: (none)")

    tools = get_tools()
    if tools:
        print_info(f"Tools: {', '.join(sorted(tools.keys()))}")
    else:
        print_info("Tools: (none)")

    if loaded.errors:
        print_warning("Some plugins failed to load:")
        for msg in loaded.errors:
            print_warning(f"- {msg}")


def _cmd_tool(args: argparse.Namespace, config: Config) -> None:
    tool_name = getattr(args, "tool_name", "") or ""
    if not tool_name:
        print_warning("Usage: mayai tool <name> [args...]")
        tools = get_tools()
        if tools:
            print_info(f"Available tools: {', '.join(sorted(tools.keys()))}")
        return

    reg = get_tool(tool_name)
    if not reg:
        print_error(f"Unknown tool '{tool_name}'.")
        tools = get_tools()
        if tools:
            print_info(f"Available tools: {', '.join(sorted(tools.keys()))}")
        sys.exit(1)

    try:
        code = reg.tool.run(args, config)
    except MayaiError as exc:
        print_error(str(exc))
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print_error(f"Tool '{tool_name}' failed: {exc}")
        sys.exit(1)

    if isinstance(code, int) and code != 0:
        sys.exit(code)


def _cmd_history(args: argparse.Namespace) -> None:
    action = getattr(args, "history_action", None)

    if action == "stats":
        print_stats(get_stats())
        return

    if action == "clear":
        confirm = getattr(args, "yes", False)
        if not confirm:
            print_warning(
                "This will delete your entire query history. "
                "Pass --yes to confirm: mayai history clear --yes"
            )
            return
        deleted = delete_history()
        print_success(f"Deleted {deleted} history entries.")
        return

    # Default: list / search
    query = getattr(args, "search", "") or ""
    provider = getattr(args, "provider", "") or ""
    limit = getattr(args, "limit", 20) or 20
    detail_id = getattr(args, "id", None)

    if detail_id is not None:
        rows = search_history(limit=1000)
        match = next((r for r in rows if r["id"] == detail_id), None)
        if match:
            print_history_detail(match)
        else:
            print_error(f"No history entry with id {detail_id}.")
        return

    rows = search_history(query=query, provider=provider, limit=limit)
    print_history_table(rows)


# ------------------------------------------------------------------ #
# Stdin detection                                                      #
# ------------------------------------------------------------------ #

def _read_stdin() -> str | None:
    """Return piped stdin content, or None if stdin is a TTY (interactive)."""
    if not sys.stdin.isatty():
        content = sys.stdin.read().strip()
        return content if content else None
    return None


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #

def main() -> None:
    config = Config.load()
    # Load entry-point plugins early so providers/tools appear everywhere.
    load_plugins(config)

    parser = argparse.ArgumentParser(
        prog="mayai",
        description="MAYAI — Chat with any AI model from your terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  mayai                                        Start interactive chat\n"
            "  mayai 'What is 2+2?'                         Single-shot query\n"
            "  mayai -p anthropic -m claude-opus-4-6        Use specific provider/model\n"
            "  cat code.py | mayai 'Review this'            Pipe file content as context\n"
            "  mayai -P code-review < myfile.py             Apply a pattern with file input\n"
            "  mayai --json 'Summarize X'                   Output as JSON\n"
            "  mayai --raw 'Explain Y' | pbcopy             Pipe plain text output\n"
            "  mayai --shell 'find files over 100MB'        Generate and run a shell command\n"
            "  mayai --shell 'kill port 8080' --yes         Run without confirmation\n"
            "  mayai history                                Show recent query history\n"
            "  mayai history --search kubernetes            Search history\n"
            "  mayai history stats                          Show usage statistics\n"
            "  mayai models -p openai                       List OpenAI models\n"
            "  mayai patterns                               List prompt patterns\n"
            "  mayai config init                            Create config file\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"mayai {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # --- plugins ---
    subparsers.add_parser("plugins", help="List discovered plugins (providers/tools)")

    # --- tool ---
    tool_parser = subparsers.add_parser("tool", help="Run a tool plugin")
    tool_sub = tool_parser.add_subparsers(dest="tool_name")
    for name, reg in sorted(get_tools().items()):
        p = tool_sub.add_parser(name, help=getattr(reg.tool, "help", "") or None)
        try:
            reg.tool.add_arguments(p)
        except Exception:
            # Tool errors should not break the CLI parser.
            pass

    # --- config ---
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_sub = config_parser.add_subparsers(dest="config_action")
    config_sub.add_parser("show", help="Print current config as JSON")
    config_sub.add_parser("path", help="Print config file path")
    config_sub.add_parser("init", help="Create default config file")
    set_parser = config_sub.add_parser("set", help="Set a config value")
    set_parser.add_argument("key", help="Dot-separated key (e.g. providers.openai.api_key)")
    set_parser.add_argument("value", help="Value to set")

    # --- models ---
    models_parser = subparsers.add_parser("models", help="List available models")
    models_parser.add_argument(
        "-p", "--provider", metavar="PROVIDER",
        help=f"Filter by provider ({', '.join(get_provider_names())})",
    )

    # --- sessions ---
    sessions_parser = subparsers.add_parser("sessions", help="Manage saved sessions")
    sessions_sub = sessions_parser.add_subparsers(dest="sessions_action")
    sessions_sub.add_parser("list", help="List saved sessions (default)")
    del_parser = sessions_sub.add_parser("delete", help="Delete a saved session")
    del_parser.add_argument("name", help="Session name to delete")

    # --- patterns ---
    subparsers.add_parser("patterns", help="List prompt patterns")

    # --- history ---
    history_parser = subparsers.add_parser("history", help="Browse and search query history")
    history_sub = history_parser.add_subparsers(dest="history_action")
    history_sub.add_parser("stats", help="Show usage statistics")
    clear_parser = history_sub.add_parser("clear", help="Delete history entries")
    clear_parser.add_argument("--yes", action="store_true", help="Confirm deletion")
    history_parser.add_argument(
        "--search", "-q", type=str, metavar="TERM",
        help="Search query or response text",
    )
    history_parser.add_argument(
        "--provider", "-p", type=str, metavar="PROVIDER",
        help="Filter by provider",
    )
    history_parser.add_argument(
        "--limit", "-n", type=int, default=20, metavar="N",
        help="Number of results to show (default: 20)",
    )
    history_parser.add_argument(
        "--id", type=int, metavar="ID",
        help="Show full detail for a specific history entry",
    )

    # --- root-level args ---
    parser.add_argument(
        "query", nargs="?", type=str,
        help="Query in single-shot mode. Omit to start interactive REPL.",
    )
    parser.add_argument(
        "-p", "--provider", type=str, metavar="PROVIDER",
        help=f"Provider ({', '.join(get_provider_names())})",
    )
    parser.add_argument(
        "-m", "--model", type=str, metavar="MODEL",
        help="Model (overrides config default)",
    )
    parser.add_argument(
        "-s", "--session", type=str, metavar="NAME",
        help="Load a saved session by name",
    )
    parser.add_argument(
        "-P", "--pattern", type=str, metavar="PATTERN",
        help="Apply a prompt pattern by name",
    )

    # Output mode (mutually exclusive)
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--raw", action="store_true",
        help="Output bare response text only (no decorators). Good for piping.",
    )
    output_group.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output response as a JSON object.",
    )

    parser.add_argument(
        "--shell", action="store_true",
        help="Generate a shell command from natural language, then confirm and run it.",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompts (use with --shell).",
    )
    parser.add_argument(
        "--estimate", action="store_true",
        help="Show token/cost estimate before sending. Prompts for confirmation.",
    )
    parser.add_argument(
        "--agent", action="store_true",
        help="Enable agent mode (loop autonomously with tools).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        )

    # Set output mode early so all subsequent print_ calls respect it
    if getattr(args, "json_output", False):
        set_output_mode("json")
    elif getattr(args, "raw", False):
        set_output_mode("raw")
    # Config is now loaded at the start of main()

    # ---- dispatch subcommands ----
    if args.command == "plugins":
        _cmd_plugins()
        return
    if args.command == "tool":
        _cmd_tool(args, config)
        return
    if args.command == "config":
        _cmd_config(args, config)
        return
    if args.command == "models":
        _cmd_models(args, config)
        return
    if args.command == "sessions":
        _cmd_sessions(args)
        return
    if args.command == "patterns":
        _cmd_patterns(args, config)
        return
    if args.command == "history":
        _cmd_history(args)
        return

    # ---- resolve provider ----
    provider_name = getattr(args, "provider", None) or config.get_default_provider()
    model_arg = getattr(args, "model", None)
    pattern_name = getattr(args, "pattern", None) or ""

    # Apply pattern overrides before resolving provider
    if pattern_name:
        pat = config.get_pattern(pattern_name)
        if pat is None:
            print_error(
                f"Pattern '{pattern_name}' not found. "
                "Run 'mayai patterns' to see available patterns."
            )
            sys.exit(1)
        # Pattern can override provider/model if not explicitly set on CLI
        if not getattr(args, "provider", None) and pat.get("provider"):
            provider_name = pat["provider"]
        if not model_arg and pat.get("model"):
            model_arg = pat["model"]

    provider, model = _resolve_provider(provider_name, model_arg, config)

    # ---- load session ----
    session_name = getattr(args, "session", None) or ""
    preloaded_messages: list[dict] = []
    if session_name:
        try:
            data = load_session(session_name)
            preloaded_messages = data.get("messages", [])
            print_success(
                f"Loaded session '[bold]{session_name}[/bold]' "
                f"({len(preloaded_messages)} messages)"
            )
        except FileNotFoundError as exc:
            print_error(str(exc))
            sys.exit(1)

    # ---- shell command mode ----
    if getattr(args, "shell", False):
        description = args.query or ""
        has_stdin = not sys.stdin.isatty()
        if not description:
            stdin_text = _read_stdin()
            description = stdin_text or ""
        if not description:
            print_error("Provide a description: mayai --shell 'find large files'")
            sys.exit(1)
            
        auto_confirm = getattr(args, "yes", False)
        if has_stdin and auto_confirm:
            print_warning("Cannot use --yes when piping input to --shell. Forcing manual confirmation.")
            auto_confirm = False
            
        run_shell_mode(
            description=description,
            provider=provider,
            provider_name=provider_name,
            model=model,
            auto_confirm=auto_confirm,
        )
        return

    # ---- read stdin ----
    stdin_content = _read_stdin()

    # ---- single-shot mode ----
    if args.query or stdin_content:
        pat = config.get_pattern(pattern_name) if pattern_name else None
        system_prompt = (
            str(pat.get("system_prompt", config.get_system_prompt()))
            if pat else config.get_system_prompt()
        )

        conversation = Conversation(system_prompt=system_prompt)
        for msg in preloaded_messages:
            if msg["role"] == "user":
                conversation.add_user(msg["content"])
            elif msg["role"] == "assistant":
                conversation.add_assistant(msg["content"])

        # Build the user message — combine query + stdin
        user_message_parts = []
        if args.query:
            user_message_parts.append(args.query)
        if stdin_content:
            user_message_parts.append(stdin_content)
        user_message = "\n\n".join(user_message_parts)
        conversation.add_user(user_message)

        # Cost estimate check
        if args.estimate:
            input_tokens = count_conversation_tokens(conversation.get_messages())
            cost = estimate_cost(model, input_tokens, 500)
            print_info(
                f"Estimated input: ~{input_tokens} tokens"
                + (f" | cost: ~{format_cost(cost)}" if cost else "")
                + "\nContinue? [y/N] "
            )
            try:
                if input().strip().lower() not in ("y", "yes"):
                    print_info("Cancelled.")
                    sys.exit(0)
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)

        full_response = ""
        try:
            for chunk in provider.stream_chat(conversation.get_messages(), system_prompt):
                print_stream_chunk(chunk)
                full_response += chunk
            print_response_end()
        except MayaiError as exc:
            print_response_end()
            print_error(str(exc))
            sys.exit(1)

        # Log to SQLite history
        out_tokens = estimate_tokens(full_response)
        in_tokens = count_conversation_tokens(conversation.get_messages())
        cost = estimate_cost(model, in_tokens, out_tokens)
        log_exchange(
            provider=provider_name,
            model=model,
            user_message=user_message,
            response=full_response,
            system_prompt=system_prompt,
            pattern=pattern_name,
            session_name=session_name,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=cost,
        )

        # JSON output mode — emit structured result
        if get_output_mode() == "json":
            output_tokens = estimate_tokens(full_response)
            input_tokens = count_conversation_tokens(conversation.get_messages())
            cost = estimate_cost(model, input_tokens, output_tokens)
            result = {
                "response": full_response,
                "provider": provider_name,
                "model": model,
                "tokens": {
                    "estimated_input": input_tokens,
                    "estimated_output": output_tokens,
                },
            }
            if cost is not None:
                result["estimated_cost_usd"] = round(cost, 6)
            print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        # ---- interactive REPL ----
        repl = REPLSession(
            provider=provider,
            provider_name=provider_name,
            config=config,
            session_name=session_name,
            pattern_name=pattern_name,
            agent_mode=getattr(args, "agent", False),
        )
        for msg in preloaded_messages:
            if msg["role"] == "user":
                repl._conversation.add_user(msg["content"])
            elif msg["role"] == "assistant":
                repl._conversation.add_assistant(msg["content"])
        repl.run()


if __name__ == "__main__":
    main()
