"""Interactive multi-turn REPL session."""

import sys

from .config import Config
from .conversation import Conversation
from .display import (
    print_banner,
    print_error,
    print_help,
    print_history,
    print_info,
    print_models_table,
    print_provider_header,
    print_response_end,
    print_sessions_table,
    print_stream_chunk,
    print_success,
    print_user_prompt,
    print_warning,
)
from .exceptions import MayaiError
from .providers import PROVIDER_NAMES, BaseProvider, get_provider
from .providers.ollama import OllamaProvider
from .sessions import auto_name, delete_session, list_sessions, load_session, save_session


class REPLSession:
    def __init__(
        self,
        provider: BaseProvider,
        provider_name: str,
        config: Config,
        session_name: str = "",
    ) -> None:
        self._provider = provider
        self._provider_name = provider_name
        self._config = config
        self._system_prompt = config.get_system_prompt()
        self._conversation = Conversation(system_prompt=self._system_prompt)
        self._session_name = session_name  # tracks the last saved/loaded name

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _pop_last_user_message(self) -> None:
        """Remove the last user message (used when a request fails)."""
        msgs = self._conversation.get_messages()
        self._conversation.clear()
        for m in msgs[:-1]:
            if m["role"] == "user":
                self._conversation.add_user(m["content"])
            else:
                self._conversation.add_assistant(m["content"])

    # ------------------------------------------------------------------ #
    # Command handlers                                                     #
    # ------------------------------------------------------------------ #

    def _cmd_clear(self) -> None:
        self._conversation.clear()
        self._session_name = ""
        print_success("Conversation history cleared.")

    def _cmd_models(self) -> None:
        try:
            if isinstance(self._provider, OllamaProvider):
                models = self._provider.list_models(
                    base_url=getattr(self._provider, "base_url", None)
                )
                default = self._provider.model
            else:
                models = type(self._provider).list_models(
                    api_key=self._provider.api_key
                )
                default = type(self._provider).default_model
            print_models_table(self._provider_name, models, default)
        except MayaiError as exc:
            print_error(str(exc))

    def _cmd_history(self) -> None:
        print_history(self._conversation.get_messages())

    def _cmd_help(self) -> None:
        print_help()

    def _cmd_switch(self, args: list[str]) -> None:
        if not args:
            print_warning("Usage: /switch <provider> [model]")
            print_info(f"Available providers: {', '.join(PROVIDER_NAMES)}")
            return

        new_provider_name = args[0].lower()
        new_model_arg = args[1] if len(args) > 1 else None

        new_model = new_model_arg or self._config.get_default_model(new_provider_name)
        if new_model is None:
            from .providers import PROVIDER_REGISTRY
            cls = PROVIDER_REGISTRY.get(new_provider_name)
            new_model = cls.default_model if cls else "default"

        api_key = self._config.resolve_api_key(new_provider_name)
        if new_provider_name != "ollama" and not api_key:
            print_error(
                f"No API key found for '{new_provider_name}'.\n"
                f"Run: mayai config set providers.{new_provider_name}.api_key YOUR_KEY"
            )
            return

        base_url = (
            self._config.get_ollama_base_url() if new_provider_name == "ollama" else None
        )

        try:
            new_provider = get_provider(
                name=new_provider_name,
                api_key=api_key,
                model=new_model,
                base_url=base_url,
            )
        except MayaiError as exc:
            print_error(str(exc))
            return

        self._provider = new_provider
        self._provider_name = new_provider_name
        print_success(
            f"Switched to [bold]{new_provider_name}[/bold] / {new_model}. "
            "History preserved."
        )

    def _cmd_save(self, args: list[str]) -> None:
        if self._conversation.is_empty():
            print_warning("Nothing to save — conversation is empty.")
            return
        name = args[0] if args else auto_name(self._provider_name)
        try:
            path = save_session(
                name=name,
                provider=self._provider_name,
                model=self._provider.model,
                system_prompt=self._system_prompt,
                messages=self._conversation.get_messages(),
            )
            self._session_name = name
            print_success(f"Session saved as '[bold]{name}[/bold]'  ({path})")
        except Exception as exc:
            print_error(f"Failed to save session: {exc}")

    def _cmd_load(self, args: list[str]) -> None:
        if not args:
            print_warning("Usage: /load <session-name>")
            return
        name = args[0]
        try:
            data = load_session(name)
        except FileNotFoundError as exc:
            print_error(str(exc))
            print_info("Run /sessions to see available sessions.")
            return

        # Restore conversation
        self._conversation.clear()
        for msg in data.get("messages", []):
            if msg["role"] == "user":
                self._conversation.add_user(msg["content"])
            elif msg["role"] == "assistant":
                self._conversation.add_assistant(msg["content"])

        self._session_name = name
        msg_count = len(self._conversation.get_messages())
        print_success(
            f"Loaded session '[bold]{name}[/bold]' "
            f"({msg_count} messages, originally on "
            f"{data.get('provider', '?')} / {data.get('model', '?')})"
        )

    def _cmd_sessions(self, args: list[str]) -> None:
        if args and args[0] == "delete":
            if len(args) < 2:
                print_warning("Usage: /sessions delete <name>")
                return
            try:
                delete_session(args[1])
                print_success(f"Deleted session '{args[1]}'.")
                if self._session_name == args[1]:
                    self._session_name = ""
            except FileNotFoundError as exc:
                print_error(str(exc))
            return

        print_sessions_table(list_sessions())

    def _cmd_exit(self, _: list[str]) -> None:
        self._auto_save_on_exit()
        print("\nExiting MAYAI. Goodbye!")
        sys.exit(0)

    def _auto_save_on_exit(self) -> None:
        """If there's unsaved conversation history, auto-save it."""
        if self._conversation.is_empty():
            return
        name = self._session_name or auto_name(self._provider_name)
        try:
            save_session(
                name=name,
                provider=self._provider_name,
                model=self._provider.model,
                system_prompt=self._system_prompt,
                messages=self._conversation.get_messages(),
            )
            print_info(f"Session auto-saved as '[bold]{name}[/bold]'.")
        except Exception:
            pass  # Don't block exit on save failure

    def _handle_command(self, raw: str) -> None:
        parts = raw.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]

        dispatch = {
            "/exit":     self._cmd_exit,
            "/quit":     self._cmd_exit,
            "/clear":    lambda _: self._cmd_clear(),
            "/models":   lambda _: self._cmd_models(),
            "/history":  lambda _: self._cmd_history(),
            "/help":     lambda _: self._cmd_help(),
            "/switch":   self._cmd_switch,
            "/save":     self._cmd_save,
            "/load":     self._cmd_load,
            "/sessions": self._cmd_sessions,
        }

        handler = dispatch.get(cmd)
        if handler is None:
            print_warning(f"Unknown command: {cmd}  - type /help to see available commands.")
            return
        handler(args)

    # ------------------------------------------------------------------ #
    # Main loop                                                            #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        print_banner(self._provider_name, self._provider.model, self._session_name)

        while True:
            try:
                print_user_prompt(self._provider_name, self._provider.model)
                user_input = input().strip()
            except (EOFError, KeyboardInterrupt):
                print()
                self._auto_save_on_exit()
                print("Exiting MAYAI. Goodbye!")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                self._handle_command(user_input)
                continue

            # Send to provider
            self._conversation.add_user(user_input)
            print_provider_header(self._provider_name, self._provider.model)

            full_response = ""
            try:
                for chunk in self._provider.stream_chat(
                    self._conversation.get_messages(),
                    self._system_prompt,
                ):
                    print_stream_chunk(chunk)
                    full_response += chunk
                print_response_end()

            except KeyboardInterrupt:
                print_response_end()
                print_warning("Response interrupted.")
                if full_response:
                    self._conversation.add_assistant(full_response)
                else:
                    self._pop_last_user_message()
                continue

            except MayaiError as exc:
                print_response_end()
                print_error(str(exc))
                self._pop_last_user_message()
                continue

            self._conversation.add_assistant(full_response)
