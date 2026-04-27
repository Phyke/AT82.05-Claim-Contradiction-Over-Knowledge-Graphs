import hashlib
import json
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from cascade import stream_cascade
from config import settings
from extraction import stream_contradictions
from neo4j_store import Neo4jStore
from nli_scorer import NliScorer

KNOWN_MODELS: set[str] = {
    settings.llm_model_anthropic_opus_4_7,
    settings.llm_model_anthropic_sonnet_4_6,
    settings.llm_model_anthropic_haiku_4_5,
    settings.llm_model_openai_gpt_5_4,
    settings.llm_model_openai_gpt_5_4_mini,
}

_store: Neo4jStore | None = None
_nli_scorer: NliScorer | None = None
_sbert: SentenceTransformer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store, _nli_scorer, _sbert
    try:
        _store = Neo4jStore()
    except Exception as e:
        logger.warning("Neo4j init failed (cascade unavailable until fixed): {}", e)
    try:
        _nli_scorer = NliScorer()
    except Exception as e:
        logger.warning("NLI scorer init failed (cascade unavailable until fixed): {}", e)
    try:
        _sbert = SentenceTransformer(settings.sbert_model)
        logger.info("SBERT loaded: {}", settings.sbert_model)
    except Exception as e:
        logger.warning("SBERT init failed (cascade unavailable until fixed): {}", e)
    yield
    if _store is not None:
        _store.close()


app = FastAPI(title="Contradiction Extractor", lifespan=lifespan)


class ExtractRequest(BaseModel):
    document: str
    model: str | None = None
    method: Literal["naive", "cascade"] = "naive"


def resolve_model(requested: str | None) -> str:
    if requested and requested in KNOWN_MODELS:
        return requested
    if requested:
        logger.warning("Unrecognized model {!r}, falling back to {}", requested, settings.default_model)
    return settings.default_model


def _doc_id_for(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:32]


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _save_run(run_id: str, doc_id: str, method: str, model: str, events: list, pair_count: int, total_elapsed: float):
    if _store is None:
        return
    try:
        _store.save_run(
            run_id=run_id,
            doc_id=doc_id,
            method=method,
            verifier_model=model,
            events_json=json.dumps(events),
            pair_count=pair_count,
            total_elapsed=total_elapsed,
        )
    except Exception as e:
        logger.warning("Failed to save run {}: {}", run_id, e)


async def _sse_naive(document: str, model: str):
    doc_id = _doc_id_for(document)
    run_id = str(uuid.uuid4())
    if _store is not None:
        try:
            _store.ensure_doc_stub(doc_id, document, document.strip()[:200])
        except Exception as e:
            logger.warning("Could not create doc stub: {}", e)

    start_time = time.time()
    events: list = []
    pair_count = 0

    started = {"event": "started", "doc_id": doc_id, "run_id": run_id, "method": "naive", "verifier_model": model}
    events.append(started)
    yield _sse(started)

    try:
        async for pair in stream_contradictions(document, model):
            data = pair.model_dump()
            ev = {"event": "pair", **data}
            events.append(ev)
            pair_count += 1
            yield _sse(ev)
    except Exception as e:
        logger.error("Naive stream error: {}", e)
        err = {"event": "error", "message": str(e)}
        events.append(err)
        yield _sse(err)

    total_elapsed = time.time() - start_time
    _save_run(run_id, doc_id, "naive", model, events, pair_count, total_elapsed)
    yield "data: [DONE]\n\n"


async def _sse_cascade(document: str, model: str):
    doc_id = _doc_id_for(document)
    run_id = str(uuid.uuid4())
    start_time = time.time()
    events: list = []
    pair_count = 0

    try:
        if _store is None:
            raise RuntimeError("Neo4j store not initialized; check NEO4J_PASSWORD and that Neo4j is running")
        if _nli_scorer is None:
            raise RuntimeError(f"NLI checkpoint not loaded; check nli_checkpoint_path={settings.nli_checkpoint_path}")
        if _sbert is None:
            raise RuntimeError("SBERT model not loaded; check sbert_model setting and network access")

        async for event in stream_cascade(document, model, _store, _nli_scorer, _sbert):
            if event.get("event") == "started":
                event["run_id"] = run_id
                event["method"] = "cascade"
                event["verifier_model"] = model
            elif event.get("event") == "pair":
                pair_count += 1
            events.append(event)
            yield _sse(event)
    except Exception as e:
        logger.error("Cascade stream error: {}", e)
        err = {"event": "error", "message": str(e)}
        events.append(err)
        yield _sse(err)

    total_elapsed = time.time() - start_time
    _save_run(run_id, doc_id, "cascade", model, events, pair_count, total_elapsed)
    yield "data: [DONE]\n\n"


@app.post("/api/extract-contradictions")
async def extract_contradictions(req: ExtractRequest):
    model = resolve_model(req.model)
    logger.info("Extract: method={}, model={}, doc_chars={}", req.method, model, len(req.document))
    generator = _sse_cascade(req.document, model) if req.method == "cascade" else _sse_naive(req.document, model)
    return StreamingResponse(generator, media_type="text/event-stream")


@app.get("/api/runs")
def list_runs() -> list[dict]:
    if _store is None:
        raise HTTPException(503, "Neo4j store not initialized")
    return _store.list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    if _store is None:
        raise HTTPException(503, "Neo4j store not initialized")
    run = _store.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str) -> dict[str, str]:
    if _store is None:
        raise HTTPException(503, "Neo4j store not initialized")
    _store.delete_run(run_id)
    return {"status": "deleted", "run_id": run_id}


@app.delete("/api/runs")
def clear_runs() -> dict[str, str]:
    if _store is None:
        raise HTTPException(503, "Neo4j store not initialized")
    _store.clear_all()
    return {"status": "cleared"}


@app.get("/health")
def health_check() -> dict[str, object]:
    return {
        "status": "healthy",
        "neo4j": _store is not None,
        "nli": _nli_scorer is not None,
        "sbert": _sbert is not None,
    }
