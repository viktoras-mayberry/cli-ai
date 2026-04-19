"""Multi-model comparison: query several providers in parallel."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from .providers import PROVIDER_REGISTRY, get_provider, get_provider_names

if TYPE_CHECKING:
    from .config import Config


def _collect_response(provider_name: str, model: str, api_key: str | None,
                      base_url: str | None, messages: list[dict],
                      system_prompt: str) -> dict:
    """Run a single provider query and return the result dict."""
    try:
        provider = get_provider(
            name=provider_name, api_key=api_key,
            model=model, base_url=base_url,
        )
        chunks: list[str] = []
        for chunk in provider.stream_chat(messages, system_prompt):
            chunks.append(chunk)
        return {
            "provider": provider_name,
            "model": model,
            "response": "".join(chunks),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": provider_name,
            "model": model,
            "response": "",
            "error": str(exc),
        }


def compare_providers(
    question: str,
    config: "Config",
    system_prompt: str = "Be precise and concise.",
) -> list[dict]:
    """Query all configured providers with API keys and return results.

    Returns a list of dicts with keys: provider, model, response, error.
    """
    _ALIAS_NAMES = {"claude", "google"}
    targets: list[tuple[str, str, str | None, str | None]] = []

    for name in get_provider_names():
        if name in _ALIAS_NAMES:
            continue

        cls = PROVIDER_REGISTRY[name]
        api_key = config.resolve_api_key(name)
        if name != "ollama" and not api_key:
            continue

        model = config.get_default_model(name) or cls.default_model
        base_url = config.get_ollama_base_url() if name == "ollama" else None

        if name == "ollama":
            try:
                from .providers.ollama import OllamaProvider
                available = OllamaProvider.list_models(base_url=base_url)
                if not available:
                    continue
            except Exception:
                continue

        targets.append((name, model, api_key, base_url))

    if not targets:
        return []

    messages = [{"role": "user", "content": question}]
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        futures = {
            pool.submit(
                _collect_response, name, model, api_key, base_url,
                messages, system_prompt,
            ): name
            for name, model, api_key, base_url in targets
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda r: r["provider"])
    return results
