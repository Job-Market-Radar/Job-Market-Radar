# Paid-tier prices in USD per 1 million text tokens (ai.google.dev/pricing, checked 2026-11-26).
PRICES = {
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    # Introductory price until 2026-12-31; from 2027-01-01 it's 1.50 / 7.50.
    "gemini-3.8-flash": {"input": 0.75, "output": 3.75},
}


def cost_usd(model: str, input_tokens: float, output_tokens: float) -> float:
    """What these tokens would cost on the paid tier."""
    price = PRICES[model]
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000