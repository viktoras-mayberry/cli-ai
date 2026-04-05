import copy
import os
import tomllib
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "mayai"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Canonical environment variable names for each provider
_ENV_VARS: dict[str, str | None] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "groq": "GROQ_API_KEY",
    "ollama": None,  # No API key needed for local Ollama
}

DEFAULT_CONFIG: dict = {
    "defaults": {
        "provider": "openai",
        "system_prompt": "Be precise and concise.",
    },
    "providers": {
        "openai": {"api_key": "", "default_model": "gpt-4o"},
        "anthropic": {"api_key": "", "default_model": "claude-opus-4-6"},
        "gemini": {"api_key": "", "default_model": "gemini-2.0-flash"},
        "perplexity": {"api_key": "", "default_model": "sonar-pro"},
        "groq": {"api_key": "", "default_model": "llama-3.3-70b-versatile"},
        "ollama": {"base_url": "http://localhost:11434", "default_model": "llama3.2"},
    },
    "patterns": {
        "code-review": {
            "system_prompt": (
                "You are a senior software engineer doing a thorough code review. "
                "Focus on security vulnerabilities, bugs, performance issues, and code quality. "
                "Be specific and actionable."
            ),
            "provider": "anthropic",
            "model": "claude-opus-4-6",
        },
        "summarize": {
            "system_prompt": (
                "Summarize the following content concisely. "
                "Use bullet points for key information. Be brief and direct."
            ),
        },
        "search": {
            "system_prompt": (
                "Search for current, accurate information. "
                "Always cite your sources and include relevant URLs."
            ),
            "provider": "perplexity",
            "model": "sonar-pro",
        },
        "explain": {
            "system_prompt": (
                "Explain this clearly and simply as if teaching someone new to the topic. "
                "Use concrete examples and analogies where helpful."
            ),
        },
        "fix": {
            "system_prompt": (
                "You are a debugging expert. Identify the root cause of the problem, "
                "explain why it happens, and provide a minimal, correct fix with explanation."
            ),
        },
    },
}


class Config:
    def __init__(self, data: dict) -> None:
        self._data = data

    @classmethod
    def load(cls) -> "Config":
        """Load config from disk, falling back to defaults if file doesn't exist."""
        if not CONFIG_FILE.exists():
            return cls(copy.deepcopy(DEFAULT_CONFIG))
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
        return cls(data)

    def save(self) -> None:
        """Write current config to disk as TOML."""
        try:
            import tomli_w
        except ImportError:
            raise RuntimeError(
                "tomli-w is required to save config.\n"
                "Install it with: pip install tomli-w"
            )
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "wb") as f:
            tomli_w.dump(self._data, f)

    def init(self) -> None:
        """Write the default config to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            import tomli_w
        except ImportError:
            raise RuntimeError(
                "tomli-w is required to initialise config.\n"
                "Install it with: pip install tomli-w"
            )
        with open(CONFIG_FILE, "wb") as f:
            tomli_w.dump(copy.deepcopy(DEFAULT_CONFIG), f)

    # ------------------------------------------------------------------ #
    # Accessors                                                            #
    # ------------------------------------------------------------------ #

    def get_default_provider(self) -> str:
        return self._data.get("defaults", {}).get("provider", "openai")

    def get_system_prompt(self) -> str:
        return self._data.get("defaults", {}).get(
            "system_prompt", "Be precise and concise."
        )

    def get_default_model(self, provider: str) -> str | None:
        return (
            self._data.get("providers", {})
            .get(provider, {})
            .get("default_model")
        )

    def get_ollama_base_url(self) -> str:
        return (
            self._data.get("providers", {})
            .get("ollama", {})
            .get("base_url", "http://localhost:11434")
        )

    def resolve_api_key(self, provider: str) -> str | None:
        """Return API key: config file value takes priority over env var."""
        # 1. Config file
        key = (
            self._data.get("providers", {})
            .get(provider, {})
            .get("api_key", "")
        )
        if key:
            return key

        # 2. Environment variable fallback
        env_var = _ENV_VARS.get(provider)
        if env_var:
            return os.environ.get(env_var)

        # 3. Secondary Gemini env var fallback
        if provider == "gemini":
            return os.environ.get("GOOGLE_API_KEY")

        return None

    def set(self, key_path: str, value: str) -> None:
        """Set a nested config value using dot notation (e.g. providers.openai.api_key)."""
        parts = key_path.split(".")
        target = self._data
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value

    def list_patterns(self) -> dict[str, dict]:
        """Return all defined patterns."""
        return copy.deepcopy(self._data.get("patterns", {}))

    def get_pattern(self, name: str) -> dict | None:
        """Return a single pattern by name, or None if not found."""
        return copy.deepcopy(self._data.get("patterns", {}).get(name))

    def as_dict(self) -> dict:
        return copy.deepcopy(self._data)
