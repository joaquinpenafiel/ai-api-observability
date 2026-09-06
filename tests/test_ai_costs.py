from src.services.ai_costs import estimate_ai_cost_usd


def test_gemini_cost_estimation():
    cost = estimate_ai_cost_usd(
        provider="gemini",
        model="gemini-3.1-flash-lite",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    assert cost == 1.75


def test_anthropic_cost_estimation():
    cost = estimate_ai_cost_usd(
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    assert cost == 18.0


def test_unknown_model_cost_is_zero():
    cost = estimate_ai_cost_usd(
        provider="unknown",
        model="unknown-model",
        input_tokens=1000,
        output_tokens=1000,
    )

    assert cost == 0.0
