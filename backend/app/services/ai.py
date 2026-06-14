"""Anthropic API helpers.

Centralises model selection and structured-JSON extraction so call sites stay
small. Model per stage is config (`MODEL_DEFAULT`=Sonnet, `MODEL_HIGH`=Opus,
`MODEL_CHEAP`=Haiku) — tune in env without code changes.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)

# Per-1M-token prices (USD) for a rough running cost estimate (§9).
_PRICES = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, outp = _PRICES.get(model, (3.0, 15.0))
    return (input_tokens / 1_000_000) * inp + (output_tokens / 1_000_000) * outp


def get_client():
    """Return an Anthropic client. Raises if no key (callers should gate on
    settings.anthropic_enabled first)."""
    import anthropic

    if not settings.anthropic_enabled:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def complete_json(
    *,
    model: str,
    system: str,
    user: str,
    schema: dict,
    max_tokens: int = 4096,
) -> tuple[dict[str, Any], float]:
    """Run a structured-JSON completion. Returns (parsed_dict, cost_usd).

    Uses output_config.format to constrain output to the given JSON schema.
    """
    client = get_client()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    cost = estimate_cost(model, resp.usage.input_tokens, resp.usage.output_tokens)
    try:
        return json.loads(text), cost
    except json.JSONDecodeError:
        log.warning("complete_json: model returned non-JSON; returning empty")
        return {}, cost
