"""MAYAI — Multi-provider AI CLI entry point."""

import argparse
import sys

from . import __version__
from .config import CONFIG_FILE, Config
from .conversation import Conversation
from .display import (
    print_error,
    print_info,
    print_models_table,
    print_response_end,
    print_sessions_table,
    print_stream_chunk,
    print_success,
    print_warning,
)
from .exceptions import ApiKeyError, MayaiError
from .providers import PROVIDER_NAMES, PROVIDER_REGISTRY, get_provider
from .providers.ollama import OllamaProvider
from .repl import REPLSession
from .sessions import delete_session, list_sessions, load_session


# ------------------------------------------------------------------ #
# Provider resolution helper                                           #
# ------------------------------------------------------------------ #

def _resolve_provider(provider_name: str, model_arg: str | None, config: Config):
    """Return (provider_instance, resolved_model_name)."""
    provider_name = provider_name.lower()

    if provider_name not in PROVIDER_REGISTRY:
        print_error(
            f"Unknown provider '{provider_name}'.\n"
            f"Available: {', '.join(PROVIDER_NAMES)}"
        )
        sys.exit(1)

    cls = PROVIDER_REGISTRY[provider_name]

    # Resolve model
    model = (
        model_arg
        or config.get_default_model(provider_name)
        or cls.default_model
    )

    # Validate model for providers with a fixed list
    if provider_name != "ollama" and hasattr(cls, "MODELS") and cls.MODELS:
        if model not in cls.MODELS:
            print_error(
                f"Model '{model}' is not available for {provider_name}.\n"
                f"Run 'mayai models -p {provider_name}' to see available models."
            )
            sys.exit(1)

    # Resolve API key
    api_key = config.resolve_api_key(provider_name)
    if provider_name != "ollama" and not api_key:
        print_error(
            f"No API key found for '{provider_name}'.\n"
            f"Set it with: mayai config set providers.{provider_name}.api_key YOUR_KEY\n"
            f"Or export the environment variable for {provider_name.upper()}."
        )
        sys.exit(1)

    # Resolve Ollama base URL
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
        import json
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
            print_error(f"Unknown provider '{target}'. Available: {', '.join(PROVIDER_NAMES)}")
            sys.exit(1)

        cls = PROVIDER_REGISTRY[target]
        api_key = config.resolve_api_key(target)

        if target == "ollama":
            base_url = config.get_ollama_base_url()
            models = OllamaProvider.list_models(api_key=None, base_url=base_url)
            if not models:
                print_warning(
                    "No Ollama models found. Is Ollama running? (ollama serve)"
                )
                return
        else:
            models = cls.list_models(api_key=api_key)

        print_models_table(target, models, cls.default_model)

    else:
        # Show all providers
        for name in PROVIDER_NAMES:
            cls = PROVIDER_REGISTRY[name]
            if name == "ollama":
                print_models_table(name, ["(run 'mayai models -p ollama' to list local models)"], "")
            else:
                print_models_table(name, cls.MODELS or ["(dynamic — requires API key)"], cls.default_model)


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mayai",
        description="MAYAI — Chat with any AI model from your terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  mayai                            Start interactive chat (default provider)\n"
            "  mayai 'What is 2+2?'             Single-shot query\n"
            "  mayai -p anthropic -m claude-opus-4-6\n"
            "  mayai models                     List all available models\n"
            "  mayai models -p openai           List OpenAI models\n"
            "  mayai config init                Create config file\n"
            "  mayai config set providers.openai.api_key sk-...\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"mayai {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # --- config subcommand ---
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_sub = config_parser.add_subparsers(dest="config_action")
    config_sub.add_parser("show", help="Print current config as JSON")
    config_sub.add_parser("path", help="Print config file path")
    config_sub.add_parser("init", help="Create default config file")
    set_parser = config_sub.add_parser("set", help="Set a config value")
    set_parser.add_argument("key", help="Dot-separated key path (e.g. providers.openai.api_key)")
    set_parser.add_argument("value", help="Value to set")

    # --- models subcommand ---
    models_parser = subparsers.add_parser("models", help="List available models")
    models_parser.add_argument(
        "-p", "--provider",
        metavar="PROVIDER",
        help=f"Filter by provider ({', '.join(PROVIDER_NAMES)})",
    )

    # --- sessions subcommand ---
    sessions_parser = subparsers.add_parser("sessions", help="Manage saved sessions")
    sessions_sub = sessions_parser.add_subparsers(dest="sessions_action")
    sessions_sub.add_parser("list", help="List saved sessions (default)")
    del_parser = sessions_sub.add_parser("delete", help="Delete a saved session")
    del_parser.add_argument("name", help="Session name to delete")

    # --- root-level args (query / REPL) ---
    parser.add_argument(
        "query",
        nargs="?",
        type=str,
        help="Query to send in single-shot mode. Omit to start interactive chat.",
    )
    parser.add_argument(
        "-p", "--provider",
        type=str,
        metavar="PROVIDER",
        help=f"Provider to use ({', '.join(PROVIDER_NAMES)})",
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        metavar="MODEL",
        help="Model to use (overrides config default)",
    )
    parser.add_argument(
        "-s", "--session",
        type=str,
        metavar="NAME",
        help="Load a saved session by name",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        )

    config = Config.load()

    # ---- dispatch subcommands ----
    if args.command == "config":
        _cmd_config(args, config)
        return

    if args.command == "models":
        _cmd_models(args, config)
        return

    if args.command == "sessions":
        _cmd_sessions(args)
        return

    # ---- main chat path ----
    provider_name = getattr(args, "provider", None) or config.get_default_provider()
    model_arg = getattr(args, "model", None)

    provider, model = _resolve_provider(provider_name, model_arg, config)

    # Load session if -s was specified
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

    if args.query:
        # Single-shot mode
        system_prompt = config.get_system_prompt()
        conversation = Conversation(system_prompt=system_prompt)
        for msg in preloaded_messages:
            if msg["role"] == "user":
                conversation.add_user(msg["content"])
            elif msg["role"] == "assistant":
                conversation.add_assistant(msg["content"])
        conversation.add_user(args.query)

        try:
            for chunk in provider.stream_chat(conversation.get_messages(), system_prompt):
                print_stream_chunk(chunk)
            print_response_end()
        except MayaiError as exc:
            print_response_end()
            print_error(str(exc))
            sys.exit(1)

    else:
        # Interactive REPL
        repl = REPLSession(
            provider=provider,
            provider_name=provider_name,
            config=config,
            session_name=session_name,
        )
        # Restore preloaded messages into conversation
        for msg in preloaded_messages:
            if msg["role"] == "user":
                repl._conversation.add_user(msg["content"])
            elif msg["role"] == "assistant":
                repl._conversation.add_assistant(msg["content"])
        repl.run()


if __name__ == "__main__":
    main()
