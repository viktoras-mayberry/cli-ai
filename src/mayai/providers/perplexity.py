from .openai_compat import OpenAICompatibleProvider


class PerplexityProvider(OpenAICompatibleProvider):
    name = "perplexity"
    BASE_URL = "https://api.perplexity.ai"
    default_model = "sonar-pro"
    # Perplexity does not expose a /models endpoint; use a curated list
    MODELS = [
        "sonar-reasoning-pro",
        "sonar-reasoning",
        "sonar-pro",
        "sonar",
    ]
