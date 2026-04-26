"""Provider-agnostic chat-model factory and per-call usage accounting."""

from typing import Any

from pydantic import SecretStr

from config import MODEL_PRICING


def init_extraction_llm(
    model: str,
    openai_key: SecretStr,
    anthropic_key: SecretStr,
    **kwargs: Any,
):
    """Return a LangChain chat model selected by `model` name prefix.

    `gpt-*` -> ChatOpenAI, `claude-*` -> ChatAnthropic. Extra kwargs (e.g.
    temperature) pass through to the chosen client. Raises ValueError on
    unknown prefix.
    """
    if model.startswith("claude-"):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, api_key=anthropic_key, **kwargs)
    if model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, api_key=openai_key, **kwargs)
    raise ValueError(f"Unknown provider for model: {model!r}")


def usage_from_raw(raw_message, model: str) -> dict:
    """Pull token counts off a raw AIMessage and compute USD cost using
    config.MODEL_PRICING. Tolerates both new-style usage_metadata and the
    older OpenAI response_metadata.token_usage shape.
    """
    if model not in MODEL_PRICING:
        raise KeyError(f"{model!r} not in MODEL_PRICING")
    pricing = MODEL_PRICING[model]

    um = getattr(raw_message, "usage_metadata", None) or {}
    if not um:
        token_usage = (getattr(raw_message, "response_metadata", None) or {}).get("token_usage", {})
        um = {
            "input_tokens": token_usage.get("prompt_tokens", 0),
            "output_tokens": token_usage.get("completion_tokens", 0),
            "total_tokens": token_usage.get("total_tokens", 0),
        }

    in_tok = int(um.get("input_tokens", 0))
    out_tok = int(um.get("output_tokens", 0))
    total_tok = int(um.get("total_tokens", in_tok + out_tok))
    in_cost = in_tok / 1_000_000 * pricing["input_per_m"]
    out_cost = out_tok / 1_000_000 * pricing["output_per_m"]
    return {
        "model": model,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": total_tok,
        "input_token_details": um.get("input_token_details"),
        "output_token_details": um.get("output_token_details"),
        "input_cost": round(in_cost, 6),
        "output_cost": round(out_cost, 6),
        "total_cost": round(in_cost + out_cost, 6),
    }
