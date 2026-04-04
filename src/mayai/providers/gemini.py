from .openai_compat import OpenAICompatibleProvider


class GeminiProvider(OpenAICompatibleProvider):
    name = "gemini"
    # Google's OpenAI-compatible endpoint — accepts Authorization: Bearer <key>
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
    default_model = "gemini-2.0-flash"
    # Curated list — the live /models endpoint returns dozens of non-chat models
    MODELS = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
    ]
