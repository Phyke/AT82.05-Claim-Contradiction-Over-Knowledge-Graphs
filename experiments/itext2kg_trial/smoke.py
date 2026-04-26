"""
Smoke test: run iText2KG_Star sentence-by-sentence on one ContraDoc document
and verify that incremental chaining lets us recover per-sentence triple
attribution (since Relationship has no native source-section field).

Run via:
    cd experiments/itext2kg_trial
    uv run python smoke.py
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from itext2kg import iText2KG_Star
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

# Force UTF-8 stdout so iText2KG's emoji log lines don't crash on Windows cp1252.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
# Mute iText2KG's verbose INFO logs (progress emojis); keep WARNING+ for real issues.
logging.getLogger("itext2kg").setLevel(logging.WARNING)

load_dotenv(Path(__file__).parent.parent / ".env")

TRIPLES_PATH = Path(__file__).parent.parent / "data" / "processed" / "ContraDoc" / "triples.jsonl"
DOC_ID = "3499318673_1"
N_SENTENCES: int | None = None  # None = all sentences
LLM_MODEL = "gpt-5.4-mini"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def load_doc(doc_id: str) -> dict:
    for line in TRIPLES_PATH.open(encoding="utf-8"):
        rec = json.loads(line)
        if rec["doc_id"] == doc_id:
            return rec
    raise SystemExit(f"doc {doc_id} not in {TRIPLES_PATH}")


def rel_key(r) -> tuple[str, str, str]:
    return (r.startEntity.name, r.name, r.endEntity.name)


async def main():
    doc = load_doc(DOC_ID)
    sentences = doc["sentences"] if N_SENTENCES is None else doc["sentences"][:N_SENTENCES]
    print(f"Doc {doc['doc_id']}: {len(sentences)} sentences  |  model={LLM_MODEL}  embeddings={EMBED_MODEL}")
    print("=" * 100)

    api_key = os.environ["OPENAI_API_KEY"]
    llm = ChatOpenAI(model=LLM_MODEL, api_key=api_key, temperature=0)
    embed = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    extractor = iText2KG_Star(llm_model=llm, embeddings_model=embed)

    per_sentence: list[dict] = []
    failed: list[tuple[int, str, str]] = []
    kg = None
    prev_rel_keys: set[tuple[str, str, str]] = set()
    prev_ent_names: set[str] = set()
    for s in sentences:
        sid = s["sentence_id"]
        text = s["source_text"]
        print(f"[{sid:>3}] {text[:90]}{'...' if len(text) > 90 else ''}", flush=True)

        if not text.strip():
            per_sentence.append({"sentence_id": sid, "source_text": text, "triples": [], "status": "empty"})
            continue

        try:
            kg = await extractor.build_graph(
                sections=[text],
                existing_knowledge_graph=kg.model_copy() if kg is not None else None,
                ent_threshold=0.8,
                rel_threshold=0.7,
            )
        except Exception as exc:
            print(f"      FAILED: {type(exc).__name__}: {exc}", flush=True)
            failed.append((sid, text, f"{type(exc).__name__}: {exc}"))
            per_sentence.append({"sentence_id": sid, "source_text": text, "triples": [], "status": "failed"})
            continue

        new_rels = [r for r in kg.relationships if rel_key(r) not in prev_rel_keys]
        prev_rel_keys.update(rel_key(r) for r in kg.relationships)
        prev_ent_names.update(e.name for e in kg.entities)

        per_sentence.append(
            {
                "sentence_id": sid,
                "source_text": text,
                "status": "ok",
                "triples": [
                    {
                        "s": r.startEntity.name,
                        "s_label": r.startEntity.label,
                        "p": r.name,
                        "o": r.endEntity.name,
                        "o_label": r.endEntity.label,
                    }
                    for r in new_rels
                ],
            }
        )

    # Pretty per-sentence output
    print("\nPer-sentence triples")
    print("-" * 100)
    for rec in per_sentence:
        sid, text, trips, status = rec["sentence_id"], rec["source_text"], rec["triples"], rec.get("status", "ok")
        snippet = text[:90] + ("..." if len(text) > 90 else "")
        tag = "" if status == "ok" else f"  [{status}]"
        print(f"\n[{sid:>3}]{tag} {snippet}")
        if not trips:
            print("       (no triples)")
            continue
        for t in trips:
            print(f"       ({t['s']}:{t['s_label']}, {t['p']}, {t['o']}:{t['o_label']})")

    if failed:
        print("\n" + "-" * 100)
        print(f"Failed sentences: {len(failed)}")
        for sid, text, err in failed:
            print(f"  [{sid}] {err}")
            print(f"       {text[:150]}")

    # Final canonical KG
    print("\n" + "=" * 100)
    print(f"Final canonical KG: {len(kg.entities)} entities, {len(kg.relationships)} relationships")
    print("\nEntities (canonical):")
    for e in sorted(kg.entities, key=lambda e: (e.label, e.name)):
        print(f"  {e.name:<35s} :{e.label}")
    print("\nRelationships:")
    for r in sorted(kg.relationships, key=lambda r: (r.startEntity.name, r.name)):
        print(f"  ({r.startEntity.name}, {r.name}, {r.endEntity.name})")

    # Persist for inspection
    out_path = Path(__file__).parent / "smoke_output.json"
    out_path.write_text(
        json.dumps(
            {
                "doc_id": doc["doc_id"],
                "n_sentences": len(sentences),
                "per_sentence": per_sentence,
                "final_kg": {
                    "entities": [{"name": e.name, "label": e.label} for e in kg.entities],
                    "relationships": [
                        {"s": r.startEntity.name, "p": r.name, "o": r.endEntity.name}
                        for r in kg.relationships
                    ],
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nFull output saved -> {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
