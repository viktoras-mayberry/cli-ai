"""Interactive multi-turn REPL session."""

import sys

from .config import Config
from .conversation import Conversation
from .costs import (
    count_conversation_tokens,
    estimate_cost,
    estimate_tokens,
    format_cost,
    format_tokens,
)
from .display import (
    print_banner,
    print_branches_table,
    print_cost_line,
    print_error,
    print_help,
    print_history,
    print_info,
    print_models_table,
    print_patterns_table,
    print_provider_header,
    print_response_end,
    print_sessions_table,
    print_stream_chunk,
    print_success,
    print_user_prompt,
    print_warning,
)
from .exceptions import MayaiError
from .history import log_exchange
from .providers import BaseProvider, get_provider, get_provider_names
from .providers.ollama import OllamaProvider
from .sessions import auto_name, delete_session, list_sessions, load_session, save_session
from .tools import get_repl_commands, get_tool, get_tools


class REPLSession:
    def __init__(
        self,
        provider: BaseProvider,
        provider_name: str,
        config: Config,
        session_name: str = "",
        pattern_name: str = "",
        agent_mode: bool = False,
    ) -> None:
        self._provider = provider
        self._provider_name = provider_name
        self._config = config
        self._session_name = session_name
        self._pattern_name = pattern_name
        self._system_prompt = config.get_system_prompt()
        self._agent_mode = agent_mode
        if self._agent_mode:
            agent_instructions = (
                "\n\nYou are operating in AGENT MODE with access to tools.\n"
                "To use a tool, you MUST output a section exactly matching this format:\n"
                "<tool_call>\n<name>tool_name</name>\n<args>arg1 arg2...</args>\n</tool_call>\n"
                "Available tools:\n"
                "- file_read: args is the simple filepath.\n"
                "- file_edit: args are exactly `<filename> <search_text> ||| <replace_text>`. Extremely important: Include exact leading/trailing whitespaces. Do not use markdown backticks around the code blocks in the search and replace texts.\n"
                "- bash: args form the terminal command.\n"
                "After the tool executes, its standard output will be passed back to you as a user message."
            )
            self._system_prompt += agent_instructions

        self._conversation = Conversation(system_prompt=self._system_prompt)

        # Cost tracking
        self._session_cost: float = 0.0
        self._session_input_tokens: int = 0
        self._session_output_tokens: int = 0

        # Apply pattern if provided at startup
        if pattern_name:
            self._apply_pattern(pattern_name, announce=False)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _pop_last_user_message(self) -> None:
        msgs = self._conversation.get_messages()
        self._conversation.clear()
        for m in msgs[:-1]:
            if m["role"] == "user":
                self._conversation.add_user(m["content"])
            else:
                self._conversation.add_assistant(m["content"])

    def _apply_pattern(self, name: str, announce: bool = True) -> bool:
        """Apply a pattern by name. Returns True on success."""
        pat = self._config.get_pattern(name)
        if pat is None:
            print_error(
                f"Pattern '{name}' not found. "
                "Run /patterns to see available patterns."
            )
            return False

        self._system_prompt = pat.get("system_prompt", self._config.get_system_prompt())
        self._pattern_name = name

        # Optionally switch provider/model if pattern specifies one
        new_provider_name = pat.get("provider")
        new_model = pat.get("model")
        if new_provider_name and new_provider_name != self._provider_name:
            api_key = self._config.resolve_api_key(new_provider_name)
            base_url = (
                self._config.get_ollama_base_url()
                if new_provider_name == "ollama"
                else None
            )
            if not api_key and new_provider_name != "ollama":
                print_warning(
                    f"Pattern '{name}' prefers provider '{new_provider_name}' "
                    "but no API key found — keeping current provider."
                )
            else:
                try:
                    resolved_model = new_model or self._config.get_default_model(new_provider_name)
                    from .providers import PROVIDER_REGISTRY
                    cls = PROVIDER_REGISTRY.get(new_provider_name)
                    resolved_model = resolved_model or (cls.default_model if cls else "default")
                    self._provider = get_provider(
                        name=new_provider_name,
                        api_key=api_key,
                        model=resolved_model,
                        base_url=base_url,
                    )
                    self._provider_name = new_provider_name
                except MayaiError as exc:
                    print_warning(f"Could not switch provider for pattern: {exc}")
        elif new_model and new_model != self._provider.model:
            self._provider.model = new_model

        if announce:
            print_success(
                f"Pattern '[bold]{name}[/bold]' applied. "
                f"Provider: {self._provider_name} / {self._provider.model}"
            )
        return True

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
                models = type(self._provider).list_models(api_key=self._provider.api_key)
                default = type(self._provider).default_model
            print_models_table(self._provider_name, models, default)
        except MayaiError as exc:
            print_error(str(exc))

    def _cmd_history(self) -> None:
        print_history(self._conversation.get_messages())

    def _cmd_help(self) -> None:
        print_help()

    def _cmd_cost(self) -> None:
        from rich.console import Console
        c = Console(highlight=False)
        c.print(
            f"\n[bold cyan]Session cost estimate[/bold cyan]\n"
            f"  Input tokens:  ~{format_tokens(self._session_input_tokens)}\n"
            f"  Output tokens: ~{format_tokens(self._session_output_tokens)}\n"
            f"  Total cost:    {format_cost(self._session_cost) if self._session_cost else 'N/A (no pricing data for this model)'}"
        )

    def _cmd_switch(self, args: list[str]) -> None:
        if not args:
            print_warning("Usage: /switch <provider> [model]")
            print_info(f"Available providers: {', '.join(get_provider_names())}")
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

    def _cmd_tool(self, args: list[str]) -> None:
        if not args:
            print_warning("Usage: /tool <name> [args...]")
            tools = get_tools()
            if tools:
                print_info(f"Available tools: {', '.join(sorted(tools.keys()))}")
            return

        name = args[0].lower()
        reg = get_tool(name)
        if not reg:
            print_error(f"Unknown tool '{name}'.")
            tools = get_tools()
            if tools:
                print_info(f"Available tools: {', '.join(sorted(tools.keys()))}")
            return

        try:
            reg.tool.run_repl(args[1:], self)
        except MayaiError as exc:
            print_error(str(exc))
        except Exception as exc:  # noqa: BLE001
            print_error(f"Tool '{name}' failed: {exc}")

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

    def _cmd_pattern(self, args: list[str]) -> None:
        if not args:
            print_warning("Usage: /pattern <name>")
            print_info("Run /patterns to see available patterns.")
            return
        self._apply_pattern(args[0], announce=True)

    def _cmd_patterns(self) -> None:
        print_patterns_table(self._config.list_patterns())

    def _cmd_branch(self, args: list[str]) -> None:
        if not args:
            print_warning("Usage: /branch <name>")
            return
        name = args[0]
        if self._conversation.branch(name):
            print_success(
                f"Branched to '[bold]{name}[/bold]' "
                f"({len(self._conversation)} messages copied from previous branch)."
            )
        else:
            print_error(f"Branch '{name}' already exists. Use /checkout {name} to switch to it.")

    def _cmd_checkout(self, args: list[str]) -> None:
        if not args:
            print_warning("Usage: /checkout <branch-name>")
            return
        name = args[0]
        if self._conversation.checkout(name):
            print_success(
                f"Switched to branch '[bold]{name}[/bold]' "
                f"({len(self._conversation)} messages)."
            )
        else:
            print_error(
                f"Branch '{name}' not found. "
                "Use /branches to see available branches, or /branch <name> to create one."
            )

    def _cmd_branches(self) -> None:
        print_branches_table(self._conversation.branch_info())

    def _cmd_exit(self, _: list[str]) -> None:
        self._auto_save_on_exit()
        print("\nExiting MAYAI. Goodbye!")
        sys.exit(0)

    def _auto_save_on_exit(self) -> None:
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
            pass

    def _handle_command(self, raw: str) -> None:
        parts = raw.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]

        # Tool plugins can optionally register dedicated slash commands.
        tool_cmds = get_repl_commands()
        if cmd in tool_cmds:
            try:
                tool_cmds[cmd].tool.run_repl(args, self)
            except MayaiError as exc:
                print_error(str(exc))
            except Exception as exc:  # noqa: BLE001
                print_error(f"Tool '{tool_cmds[cmd].name}' failed: {exc}")
            return

        dispatch = {
            "/exit":     self._cmd_exit,
            "/quit":     self._cmd_exit,
            "/clear":    lambda _: self._cmd_clear(),
            "/models":   lambda _: self._cmd_models(),
            "/history":  lambda _: self._cmd_history(),
            "/help":     lambda _: self._cmd_help(),
            "/cost":     lambda _: self._cmd_cost(),
            "/switch":   self._cmd_switch,
            "/tool":     self._cmd_tool,
            "/save":     self._cmd_save,
            "/load":     self._cmd_load,
            "/sessions": self._cmd_sessions,
            "/pattern":  self._cmd_pattern,
            "/patterns": lambda _: self._cmd_patterns(),
            "/branch":   self._cmd_branch,
            "/checkout": self._cmd_checkout,
            "/branches": lambda _: self._cmd_branches(),
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
        print_banner(
            self._provider_name,
            self._provider.model,
            self._session_name,
            self._pattern_name,
        )

        pending_agent_input: str | None = None

        while True:
            if pending_agent_input is not None:
                user_input = pending_agent_input
                pending_agent_input = None
            else:
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

            # Count input tokens before sending
            self._conversation.add_user(user_input)
            input_tokens = count_conversation_tokens(self._conversation.get_messages())

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

            # Cost tracking
            output_tokens = estimate_tokens(full_response)
            cost = estimate_cost(self._provider.model, input_tokens, output_tokens)
            if cost is not None:
                self._session_cost += cost
            self._session_input_tokens += input_tokens
            self._session_output_tokens += output_tokens

            print_cost_line(
                input_tokens,
                output_tokens,
                cost,
                self._session_cost if self._session_cost > 0 else None,
            )

            # Log to SQLite history (best-effort, never blocks)
            log_exchange(
                provider=self._provider_name,
                model=self._provider.model,
                user_message=user_input,
                response=full_response,
                system_prompt=self._system_prompt,
                pattern=self._pattern_name,
                session_name=self._session_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )

            if getattr(self, "_agent_mode", False):
                import re
                match = re.search(r"<tool_call>\s*<name>(.*?)</name>\s*<args>(.*?)</args>\s*</tool_call>", full_response, re.DOTALL)
                if match:
                    tool_name = match.group(1).strip()
                    tool_args_str = match.group(2)
                    from .tools import get_tool
                    reg = get_tool(tool_name)
                    if reg:
                        print_info(f"\n[bold magenta]Agent Executing Tool:[/bold magenta] {tool_name}")
                        try:
                            out = reg.tool.run_repl([tool_args_str], self)
                            tool_output = out if out else "Execution finished with no output."
                        except Exception as e:
                            tool_output = f"Tool crashed: {e}"
                    else:
                        tool_output = f"Error: Tool '{tool_name}' not found."
                        
                    pending_agent_input = f"<tool_response>\n{tool_output}\n</tool_response>"
                    print_info(f"[dim]Passing output back to agent...[/dim]\n")
