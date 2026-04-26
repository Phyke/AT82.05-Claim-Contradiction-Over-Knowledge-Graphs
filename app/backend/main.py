import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from config import settings
from extraction import stream_contradictions

KNOWN_MODELS: set[str] = {
    settings.llm_model_anthropic_opus_4_7,
    settings.llm_model_anthropic_sonnet_4_6,
    settings.llm_model_anthropic_haiku_4_5,
    settings.llm_model_openai_gpt_5_4,
    settings.llm_model_openai_gpt_5_4_mini,
}

app = FastAPI(title="Contradiction Extractor")


class ExtractRequest(BaseModel):
    document: str
    model: str | None = None


def resolve_model(requested: str | None) -> str:
    if requested and requested in KNOWN_MODELS:
        return requested
    if requested:
        logger.warning("Unrecognized model {!r}, falling back to {}", requested, settings.default_model)
    return settings.default_model


async def sse_stream(document: str, model: str):
    try:
        async for pair in stream_contradictions(document, model):
            yield f"data: {pair.model_dump_json()}\n\n"
    except Exception as e:
        logger.error("Stream error: {}", e)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/api/extract-contradictions")
async def extract_contradictions(req: ExtractRequest):
    model = resolve_model(req.model)
    logger.info("Extract request: model={}, doc_chars={}", model, len(req.document))
    return StreamingResponse(
        sse_stream(req.document, model),
        media_type="text/event-stream",
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
