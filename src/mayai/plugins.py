from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Any

from .display import print_warning
from .providers import BaseProvider, register_provider
from .tools import register_tool


@dataclass(frozen=True)
class LoadedPlugins:
    providers: dict[str, type[BaseProvider]]
    tools: dict[str, Any]
    errors: list[str]


_LAST_LOADED: LoadedPlugins | None = None


def _iter_entry_points(group: str):
    eps = metadata.entry_points()
    # Python 3.10: returns dict-like; 3.11+: EntryPoints with .select()
    if hasattr(eps, "select"):
        return list(eps.select(group=group))
    return list(eps.get(group, []))  # type: ignore[no-any-return]


def load_plugins() -> LoadedPlugins:
    """Discover and load MAYAI plugins via Python entry points.

    This is intentionally best-effort: plugin failures are collected as warnings
    and do not break the CLI.
    """
    global _LAST_LOADED

    loaded_providers: dict[str, type[BaseProvider]] = {}
    loaded_tools: dict[str, Any] = {}
    errors: list[str] = []

    # --- Providers ---
    for ep in _iter_entry_points("mayai.providers"):
        try:
            obj = ep.load()
            if not isinstance(obj, type) or not issubclass(obj, BaseProvider):
                raise TypeError(
                    f"Entry point '{ep.name}' did not resolve to a BaseProvider subclass"
                )
            registered = register_provider(ep.name, obj, allow_override=False)
            if not registered:
                errors.append(
                    f"Provider plugin '{ep.name}' was not registered (name collision)"
                )
                continue
            loaded_providers[ep.name] = obj
        except Exception as exc:  # noqa: BLE001 - plugins must be isolated
            errors.append(f"Failed to load provider plugin '{ep.name}': {exc}")

    # --- Tools ---
    for ep in _iter_entry_points("mayai.tools"):
        try:
            obj = ep.load()
            if not register_tool(ep.name, obj, allow_override=False, source="plugin"):
                errors.append(f"Tool plugin '{ep.name}' was not registered (invalid or collision)")
                continue
            loaded_tools[ep.name] = obj
        except Exception as exc:  # noqa: BLE001 - plugins must be isolated
            errors.append(f"Failed to load tool plugin '{ep.name}': {exc}")

    loaded = LoadedPlugins(providers=loaded_providers, tools=loaded_tools, errors=errors)
    _LAST_LOADED = loaded

    for msg in errors:
        print_warning(msg)

    return loaded


def get_last_loaded_plugins() -> LoadedPlugins | None:
    return _LAST_LOADED

