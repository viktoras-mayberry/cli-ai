from .openai_compat import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    BASE_URL = "https://api.openai.com/v1"
    default_model = "gpt-4o"
    # MODELS left empty so list_models() queries /v1/models live
    MODELS: list[str] = []
