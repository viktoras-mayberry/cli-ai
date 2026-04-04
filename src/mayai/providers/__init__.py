from .anthropic import AnthropicProvider
from .base import BaseProvider
from .gemini import GeminiProvider
from .groq import GroqProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .perplexity import PerplexityProvider

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

PROVIDER_NAMES = [
    "openai",
    "anthropic",
    "gemini",
    "perplexity",
    "groq",
    "ollama",
]


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
            f"Available: {', '.join(PROVIDER_NAMES)}"
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
    "PROVIDER_NAMES",
    "get_provider",
]
