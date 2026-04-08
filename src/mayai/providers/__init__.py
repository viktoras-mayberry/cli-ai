from .anthropic import AnthropicProvider
from .base import BaseProvider
from .gemini import GeminiProvider
from .groq import GroqProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .perplexity import PerplexityProvider

# Providers are registered into this mutable runtime registry.
# Built-ins are registered at import time; plugins may register later.
PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "claude": AnthropicProvider,       # convenience alias
    "gemini": GeminiProvider,
    "google": GeminiProvider,          # convenience alias
    "perplexity": PerplexityProvider,
    "groq": GroqProvider,
    "ollama": OllamaProvider,
}

_PROVIDER_ALIASES: set[str] = {"claude", "google"}


def get_provider_names(*, include_aliases: bool = False) -> list[str]:
    """Return provider names for display/help."""
    names = list(PROVIDER_REGISTRY.keys())
    if not include_aliases:
        names = [n for n in names if n not in _PROVIDER_ALIASES]
    return sorted(set(names))


def register_provider(
    name: str,
    cls: type[BaseProvider],
    *,
    allow_override: bool = False,
) -> bool:
    """Register a provider class under a name.

    Returns True if registered, False if skipped due to a collision.
    """
    key = name.lower().strip()
    if not key:
        return False
    if not allow_override and key in PROVIDER_REGISTRY:
        return False
    PROVIDER_REGISTRY[key] = cls
    return True


def get_provider(
    name: str,
    api_key: str | None,
    model: str,
    base_url: str | None = None,
) -> BaseProvider:
    """Factory: return a configured provider instance."""
    cls = PROVIDER_REGISTRY.get(name.lower())
    if cls is None:
        from ..exceptions import ProviderError
        raise ProviderError(
            f"Unknown provider '{name}'. "
            f"Available: {', '.join(get_provider_names())}"
        )
    return cls(api_key=api_key, model=model, base_url=base_url)


__all__ = [
    "BaseProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "PerplexityProvider",
    "GroqProvider",
    "OllamaProvider",
    "PROVIDER_REGISTRY",
    "get_provider_names",
    "register_provider",
    "get_provider",
]
