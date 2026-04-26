import json
from collections.abc import AsyncIterator

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, ValidationError

from config import settings


class ContradictionPair(BaseModel):
    sentence_a: str
    sentence_b: str
    explanation: str


SYSTEM_PROMPT = """You are a contradiction detector. Read the user's document and identify pairs of sentences within it that contradict each other.

Output format: emit ONE JSON object per line in JSONL format. Each object MUST have exactly these three keys:
- "sentence_a": the first sentence (string, copied or closely paraphrased from the document)
- "sentence_b": the second sentence that contradicts it (string)
- "explanation": a brief explanation of why they contradict (string)

Strict rules:
- Output ONLY JSONL. No preamble, no postamble, no markdown code fences, no commentary.
- One JSON object per line. Each line is a complete, valid JSON object terminated by a newline.
- Sentence text inside JSON values may use markdown formatting (bold, italics, code spans) if helpful.
- If no contradictions exist in the document, output nothing (empty response).
"""


def _build_llm(model: str) -> ChatAnthropic | ChatOpenAI:
    if model.startswith("claude-"):
        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key.get_secret_value(),
            streaming=True,
        )
    if model.startswith("gpt-"):
        return ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key.get_secret_value(),
            streaming=True,
        )
    raise ValueError(f"Unrecognized model: {model}")


def _coerce_text(content: str | list) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _try_emit(line: str) -> ContradictionPair | None:
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except json.JSONDecodeError as e:
        logger.warning("Skipping non-JSON line: {!r} ({})", line[:200], e)
        return None
    try:
        return ContradictionPair(**data)
    except (ValidationError, TypeError) as e:
        logger.warning("Skipping invalid pair: {!r} ({})", line[:200], e)
        return None


async def stream_contradictions(document: str, model: str) -> AsyncIterator[ContradictionPair]:
    logger.info("Starting extraction: model={}, doc_chars={}", model, len(document))
    llm = _build_llm(model)
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=document)]

    buffer = ""
    async for chunk in llm.astream(messages):
        buffer += _coerce_text(chunk.content)
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            pair = _try_emit(line)
            if pair is not None:
                yield pair

    pair = _try_emit(buffer)
    if pair is not None:
        yield pair
