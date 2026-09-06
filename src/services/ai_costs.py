PRICING_PER_MILLION_TOKENS = {
    ("gemini", "gemini-3.1-flash-lite"): {
        "input": 0.25,
        "output": 1.50,
    },
    ("anthropic", "claude-sonnet-4-6"): {
        "input": 3.00,
        "output": 15.00,
    },
}


def estimate_ai_cost_usd(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    pricing = PRICING_PER_MILLION_TOKENS.get(
        (provider, model)
    )

    if pricing is None:
        return 0.0

    input_cost = (
        input_tokens
        / 1_000_000
        * pricing["input"]
    )

    output_cost = (
        output_tokens
        / 1_000_000
        * pricing["output"]
    )

    return round(
        input_cost + output_cost,
        8,
    )
