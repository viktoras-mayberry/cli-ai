"""Research mode: web-grounded answers with cited sources via Perplexity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .providers import PROVIDER_REGISTRY, get_provider
from .providers.perplexity import PerplexityProvider

if TYPE_CHECKING:
    from .config import Config

RESEARCH_SYSTEM_PROMPT = (
    "You are a thorough research assistant. "
    "Search for current, accurate information on the user's question. "
    "Provide a well-structured answer with key findings. "
    "Always cite your sources."
)


def run_research(
    question: str,
    config: "Config",
    model: str | None = None,
) -> tuple[str, list[str]]:
    """Query Perplexity with a research question and return (answer, citations).

    Falls back to the default Perplexity model if none is specified.
    Raises RuntimeError if no Perplexity API key is configured.
    """
    api_key = config.resolve_api_key("perplexity")
    if not api_key:
        raise RuntimeError(
            "Research mode requires a Perplexity API key.\n"
            "Set it with: mayai config set providers.perplexity.api_key YOUR_KEY\n"
            "Or set the PERPLEXITY_API_KEY environment variable."
        )

    resolved_model = model or config.get_default_model("perplexity") or "sonar-pro"

    provider = get_provider(
        name="perplexity",
        api_key=api_key,
        model=resolved_model,
    )

    messages = [{"role": "user", "content": question}]
    chunks: list[str] = []
    for chunk in provider.stream_chat(messages, RESEARCH_SYSTEM_PROMPT):
        chunks.append(chunk)

    answer = "".join(chunks)
    citations: list[str] = []
    if isinstance(provider, PerplexityProvider):
        citations = provider.last_citations or []

    return answer, citations
