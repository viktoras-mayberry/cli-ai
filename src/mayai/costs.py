"""Token estimation and cost calculation for all supported models."""

# Pricing in USD per 1 million tokens (input / output).
# Approximate as of early 2026 — update as providers change pricing.
PRICING: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o":                        {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":                   {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":                   {"input": 10.00, "output": 30.00},
    "o1":                            {"input": 15.00, "output": 60.00},
    "o3-mini":                       {"input": 1.10,  "output": 4.40},
    # Anthropic
    "claude-opus-4-6":               {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6":             {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001":     {"input": 0.80,  "output": 4.00},
    "claude-3-5-sonnet-20241022":    {"input": 3.00,  "output": 15.00},
    "claude-3-5-haiku-20241022":     {"input": 0.80,  "output": 4.00},
    "claude-3-opus-20240229":        {"input": 15.00, "output": 75.00},
    # Gemini
    "gemini-2.0-flash":              {"input": 0.10,  "output": 0.40},
    "gemini-2.0-flash-lite":         {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro":                {"input": 1.25,  "output": 5.00},
    "gemini-1.5-flash":              {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash-8b":           {"input": 0.0375,"output": 0.15},
    # Perplexity
    "sonar-pro":                     {"input": 3.00,  "output": 15.00},
    "sonar-reasoning-pro":           {"input": 2.00,  "output": 8.00},
    "sonar-reasoning":               {"input": 1.00,  "output": 5.00},
    "sonar":                         {"input": 1.00,  "output": 1.00},
    # Groq (very low cost)
    "llama-3.3-70b-versatile":       {"input": 0.59,  "output": 0.79},
    "llama-3.1-8b-instant":          {"input": 0.05,  "output": 0.08},
    "llama-3.2-90b-vision-preview":  {"input": 0.90,  "output": 0.90},
    "mixtral-8x7b-32768":            {"input": 0.24,  "output": 0.24},
    "gemma2-9b-it":                  {"input": 0.20,  "output": 0.20},
    "deepseek-r1-distill-llama-70b": {"input": 0.75,  "output": 0.99},
    # Ollama — free (runs locally)
}


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token (works for most models)."""
    return max(1, len(text) // 4)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Return estimated cost in USD, or None if the model has no pricing data."""
    pricing = PRICING.get(model)
    if not pricing:
        return None
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return cost


def format_cost(usd: float) -> str:
    if usd == 0:
        return "$0.0000"
    if usd < 0.0001:
        return "< $0.0001"
    return f"${usd:.4f}"


def format_tokens(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


def count_conversation_tokens(messages: list[dict]) -> int:
    """Estimate total tokens in a list of messages."""
    return sum(estimate_tokens(m.get("content", "")) for m in messages)
