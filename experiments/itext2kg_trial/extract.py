"""
Run iText2KG_Star on a stratified sample of 30 ContraDoc docs (10 wiki + 10 news + 10 story,
balanced YES/NO within each doc_type). Resumable: skips docs already in the output JSONL.

Uses LLM = gpt-5.4 (matches notebook 02 baseline) and embeddings = sentence-transformers/all-MiniLM-L6-v2
(matches notebook 03/05).

Output: triples_v2.jsonl (one JSON record per doc, parallel to the naive triples.jsonl schema
plus iText2KG-specific fields).
"""

import asyncio
import json
import logging
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from itext2kg import iText2KG_Star
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
logging.getLogger("itext2kg").setLevel(logging.WARNING)

load_dotenv(Path(__file__).parent.parent / ".env")

NAIVE_PATH = Path(__file__).parent.parent / "data" / "processed" / "ContraDoc" / "triples.jsonl"
OUTPUT_PATH = Path(__file__).parent / "triples_v2.jsonl"
LLM_MODEL = "gpt-5.4"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SEED = 42
N_PER_TYPE_PER_LABEL = 5  # 5 YES + 5 NO per doc_type, 3 doc_types -> 30 docs


def stratified_sample() -> list[dict]:
    docs = [json.loads(line) for line in NAIVE_PATH.open(encoding="utf-8")]
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for d in docs:
        if d["contradiction"] == "YES":
            if d.get("gold_evidence_sentence_id") is None or not d.get("gold_ref_sentence_ids"):
                continue
        strata[(d["doc_type"], d["contradiction"])].append(d)
    rnd = random.Random(SEED)
    sampled: list[dict] = []
    for stratum in sorted(strata):
        lst = strata[stratum]
        rnd.shuffle(lst)
        n = min(N_PER_TYPE_PER_LABEL, len(lst))
        sampled.extend(lst[:n])
        print(f"  stratum {stratum}: sampled {n}/{len(lst)}", flush=True)
    return sampled


def rel_key(r) -> tuple[str, str, str]:
    return (r.startEntity.name, r.name, r.endEntity.name)


async def extract_doc(extractor: iText2KG_Star, doc: dict) -> dict:
    per_sentence: list[dict] = []
    failed: list[int] = []
    kg = None
    prev_rel_keys: set[tuple[str, str, str]] = set()
    for s in doc["sentences"]:
        sid = s["sentence_id"]
        text = s["source_text"]
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
        except Exception as exc:  # noqa: BLE001 - want to capture & continue on any extractor failure
            failed.append(sid)
            per_sentence.append(
                {
                    "sentence_id": sid,
                    "source_text": text,
                    "triples": [],
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        new_rels = [r for r in kg.relationships if rel_key(r) not in prev_rel_keys]
        prev_rel_keys.update(rel_key(r) for r in kg.relationships)
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

    return {
        "doc_id": doc["doc_id"],
        "doc_type": doc["doc_type"],
        "contradiction": doc["contradiction"],
        "contra_type": doc.get("contra_type"),
        "gold_evidence_sentence_id": doc.get("gold_evidence_sentence_id"),
        "gold_ref_sentence_ids": doc.get("gold_ref_sentence_ids", []),
        "n_sentences": len(doc["sentences"]),
        "n_failed_sentences": len(failed),
        "per_sentence": per_sentence,
        "final_kg": {
            "entities": [{"name": e.name, "label": e.label} for e in (kg.entities if kg else [])],
            "relationships": [
                {"s": r.startEntity.name, "p": r.name, "o": r.endEntity.name}
                for r in (kg.relationships if kg else [])
            ],
        },
    }


async def main():
    print(f"LLM={LLM_MODEL}  embeddings={EMBED_MODEL}  seed={SEED}", flush=True)
    print("Stratified sample:", flush=True)
    sampled = stratified_sample()
    print(f"Total sampled: {len(sampled)} docs", flush=True)

    done: set[str] = set()
    if OUTPUT_PATH.exists():
        for line in OUTPUT_PATH.open(encoding="utf-8"):
            done.add(json.loads(line)["doc_id"])
        print(f"Resuming: {len(done)} docs already done", flush=True)

    todo = [d for d in sampled if d["doc_id"] not in done]
    print(f"To extract: {len(todo)} docs", flush=True)
    if not todo:
        print("Nothing to do.", flush=True)
        return

    api_key = os.environ["OPENAI_API_KEY"]
    llm = ChatOpenAI(model=LLM_MODEL, api_key=api_key, temperature=0)
    embed = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    extractor = iText2KG_Star(llm_model=llm, embeddings_model=embed)

    with OUTPUT_PATH.open("a", encoding="utf-8") as f:
        for i, doc in enumerate(todo, start=1):
            print(
                f"[{i}/{len(todo)}] {doc['doc_id']:<22} {doc['doc_type']}/{doc['contradiction']:<3} "
                f"{len(doc['sentences'])} sentences",
                flush=True,
            )
            try:
                rec = await extract_doc(extractor, doc)
            except Exception as exc:  # noqa: BLE001 - whole-doc fallback
                print(f"  DOC FAILED: {type(exc).__name__}: {exc}", flush=True)
                continue
            n_triples = sum(len(s["triples"]) for s in rec["per_sentence"])
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(
                f"  -> {n_triples} triples, "
                f"{rec['n_failed_sentences']} sentence failures, "
                f"{len(rec['final_kg']['entities'])} entities, "
                f"{len(rec['final_kg']['relationships'])} relationships",
                flush=True,
            )

    print(f"\nDone. Output: {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
