class MayaiError(Exception):
    """Base class for all MAYAI exceptions."""


class ConfigError(MayaiError):
    """Raised for missing or malformed configuration."""


class ApiKeyError(MayaiError):
    """Raised when an API key is not found in config or environment."""


class ProviderError(MayaiError):
    """Raised for provider-level communication failures."""


class ModelNotFoundError(MayaiError):
    """Raised when the requested model is not available for a provider."""


class StreamError(MayaiError):
    """Raised when SSE stream parsing fails."""
