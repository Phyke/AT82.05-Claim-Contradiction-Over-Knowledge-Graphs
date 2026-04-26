# 02b MinIE Extraction - Debug Notes

Pilot then full run on `experiments/02b_triples_extraction_minie_style.ipynb` using `claude-opus-4-7` against the balanced ContraDoc YES sample (150 docs). Five debugging issues surfaced during the pilot and were fixed. This file captures root cause + fix for each, plus the final 150-doc run results.

## Final 150-doc result (high effort, default)

| Metric | Value |
|---|---|
| Docs extracted | 150 / 150 |
| Sentences | 5,651 (avg 37.7 / doc) |
| Triples | 9,189 (avg 61.3 / doc) |
| Evidence resolution | 134 `llm_tag` (89.3%), 3 fuzzy fallback, **13 unmatched (8.7%)** |
| Reference resolution | 136 `llm_tag` (90.7%), 4 fuzzy fallback, **26 unmatched (17.3%)** |
| **Gold-pair usability for downstream NLI** | **123 / 150 (82%)** |
| Token overlap (hallucination heuristic) | mean 88.1%, median 100%, >=80% on 76.7% |
| MinIE annotation rates | polarity '-' 5.4%, modality 'PS' 5.5%, attribution 13.4%, quantity 6.3% |
| Recorded cost | $23.82 (+ ~$0.50 untracked retry calls) = **~$24.30 total** |
| Per-doc wall time | ~30-60 s (avg ~45 s); full run ~2 h |
| Transient parse failures | ~1-3% required retries; one doc needed 8 attempts |

The 27 docs that didn't produce a usable `(evidence_triples, ref_triples)` pair are listed in `experiments/data/processed/ContraDoc/triples_minie_unusable.json`. Failure modes: 13 docs the LLM didn't tag any sentence as `is_evidence`, the rest are residual sentence bundling that the strict prompt didn't fully prevent (line breaks / run-on punctuation in the source). Decision: accept and proceed; downstream NLI pair builder will skip these.

## Pilot result (10 docs - reference for prompt iteration)

| Metric | Value |
|---|---|
| Docs extracted | 10 / 10 |
| Sentences | 308 (avg 30.8) |
| Triples | 584 (avg 58.4) |
| Evidence + ref resolution | 10 / 10 `llm_tag` |
| Recorded cost | $1.36 (+ ~$0.30 untracked retries) |

The 100% pilot success on resolution did not extrapolate cleanly to 150 - the larger sample exposed an ~9% bundling residual that 10 docs missed.

## Issues and fixes

### 1. `temperature` deprecated on `claude-opus-4-7`

First API call failed with:
```
BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error',
'message': '`temperature` is deprecated for this model.'}}
```

`init_extraction_llm(..., temperature=0)` is no longer accepted on adaptive-thinking Claude models. Per Anthropic docs, only OpenAI and older Claude models still take `temperature`.

**Fix in `cell-5`:** make `temperature` provider-conditional.

```python
llm_kwargs = {"openai_key": ..., "anthropic_key": ..., "max_tokens": MAX_TOKENS}
if not LLM_MODEL.startswith("claude-"):
    llm_kwargs["temperature"] = 0
```

**Side note on reasoning effort.** The notebook also exposes a `REASONING_EFFORT` knob, but the original mapping (`thinking={"type": "enabled", "budget_tokens": ...}`) is rejected by Opus 4.7. The model only accepts `thinking={"type": "adaptive"}` and effort is set via `output_config={"effort": "low"|"medium"|"high"|"xhigh"|"max"}` (default `high`). The current notebook keeps `REASONING_EFFORT = None` (no thinking, fast path) for the pilot. If we later want to dial effort, the knob needs rewriting against the new API surface.

### 2. Sentence chunking - LLM bundling adjacent sentences

First pilot run had 4 / 10 docs with `gold_evidence_sentence_id = None` (unmatched after fuzzy fallback). All four had the same root cause: the LLM produced a single `SentenceExtraction` whose `source_text` glued together two or three of the original document sentences.

Examples (LLM output, gold evidence in **bold**):

- `sid=16: Chapter 6 analyses the resistance Hallery's quasi-religious concept inspires. **Chapter 7 praises the thought of Friedrich Nietzsche...**`
- `sid=16: At first blush, that sounds like it fits perfectly, right? **The Columbia report may not go a long way toward establishing at least a modicum of the required intent.** But that's only half the battle.`
- `sid=10: It is "all so convenient!"**Tom Thumb discovers the food is plaster and finds it amusing.**` (note also: dropped space between sentences)

The original prompt only said *"Preserve sentences in document order. Do not split, merge, paraphrase, or omit them."* - too soft.

**Fix in `cell-5` SYSTEM_PROMPT** (Document-structure rules section):

- Lead with `EXACTLY ONE sentence per SentenceExtraction entry. Never bundle two or more sentences...`
- Define the boundary explicitly: ends at first `.`, `!`, `?` or `."`/`?"`/`!"` followed by capital or EOD; abbreviations (`Mr.`, `Dr.`, `U.S.`) excepted.
- Add a CORRECT vs INCORRECT example using verbatim notebook schema syntax.
- Restate the rule again on `is_evidence`: the matched sentence MUST be a single sentence, not bundled.

After this change the 3 problem docs that re-extracted (the 4th hit a separate parse failure) all came back with evidence resolved as `llm_tag` cleanly.

### 3. UTF-8-as-Latin-1 mojibake in source data

ContraDoc has rows with mojibake - bytes like `â\x80\x93` are UTF-8 en-dash (`U+2013`) misinterpreted as Latin-1 somewhere upstream. Those `\x80` and `\x93` are control characters in Latin-1 / cp1252 and confuse Claude's tool-call JSON output.

Concrete case: `doc_id=3488771838_4` had `â\x80\x93` in its `ref_sentences` field. With these bytes in the prompt, Opus 4.7 returned a tool call whose args langchain could not parse into the Pydantic schema (`parsed=None`).

**Fix:** add `ftfy` as a dependency and apply `fix_text(...)` to `text`, `evidence`, and each `ref_sentence` before passing to `extract_document`. Save the *fixed* strings back to the record so downstream consumers (NLI pair builder, Neo4j inserter, retrieval) see clean text consistently.

```python
text = fix_text(row.text)
evidence_clean = fix_text(row.evidence) if row.contradiction == "YES" else None
refs_clean = [fix_text(r) for r in row.ref_sentences.split("|")] if row.contradiction == "YES" else []
```

Verified: `'The two smash every dish on the table â\x80\x93 "bang, ...'` becomes `'The two smash every dish on the table - "bang, ...'` (en-dash properly rendered).

### 4. Intermittent `parsed=None` from langchain

After fixing temperature + prompt + mojibake, doc `3488771838_4` *still* failed with:
```
RuntimeError: Structured-output parsing returned None (stop_reason=tool_use).
```

`stop_reason=tool_use` means the LLM completed a tool call - the API call itself succeeded (we still pay for the tokens) but langchain could not parse the tool-call args. A standalone debug script issuing the same call with the same prompt then *succeeded* on the first try.

Conclusion: this failure mode is **flaky**, not deterministic. Likely an interaction between the long system prompt, structured-output parsing, and Opus 4.7. Retries recover.

**Initial fix:** raise `RuntimeError` on `parsed=None` so the loop's `try / except` logs `FAILED doc_id=...` and continues. Single attempt per doc.

**Better fix (now in `cell-5`):** retry up to 3 times inside `extract_document` with a 2-second sleep between attempts. The pilot's "deterministic" failure was actually flaky - retries recover most cases. Without this, the sanity cell at the top of the notebook crashes the whole run on its first parse failure.

```python
EXTRACT_MAX_RETRIES = 3

def extract_document(text, evidence=None, refs=None, max_retries=EXTRACT_MAX_RETRIES):
    ...
    last_stop_reason = None
    for attempt in range(1, max_retries + 1):
        out = extractor.invoke([...])
        parsed = out["parsed"]
        if parsed is not None:
            return parsed, usage_from_raw(out["raw"], LLM_MODEL)
        last_stop_reason = getattr(out["raw"], "response_metadata", {}).get("stop_reason")
        if attempt < max_retries:
            _time.sleep(2)
    raise RuntimeError(f"... after {max_retries} attempts (last stop_reason={last_stop_reason}).")
```

In the 150-doc run, this caught most flakiness automatically. **One doc (`3489738254_8`) still failed after 3 retries.** Recovery: run the standalone script with up to 5 retries - it succeeded on attempt 5 (8 total attempts including the original 3).

For very stubborn docs, recovery snippet:

```python
for attempt in range(1, 6):
    out = extractor.invoke([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}])
    if out["parsed"] is not None:
        break
    time.sleep(3)
```

### 5. Windows cp1252 default codec breaks `jupyter execute`

After a run that wrote LLM output containing non-Latin-1 bytes into the `.ipynb` file, the next `jupyter execute` failed during *file load* with:
```
UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 28291
```

Python on Windows defaults to cp1252 when the locale is unset; `nbformat.read` opens the JSON file with that codec instead of UTF-8.

**Fix:** prefix the command with `PYTHONUTF8=1` (and `PYTHONIOENCODING=utf-8` for safety):
```bash
PYTHONUTF8=1 uv run --no-sync jupyter execute --inplace --timeout=1200 02b_triples_extraction_minie_style.ipynb
```

This should be the standard launch command on Windows.

### 6. CHUNK_SIZE side effect after partial deletion

When 4 problem records were removed from `triples_minie.jsonl` to retrigger their extraction, setting `CHUNK_SIZE=10` accidentally pulled in 6 brand-new docs alongside the 4 retries (because `remaining = contra_df - done_ids` had the 4 retries plus 140 new docs, and `head(10)` grabbed the first 10 of that). Spent ~$0.80 of unintended bonus extraction.

**Fix:** when retrying specific docs, set `CHUNK_SIZE` to exactly the number of retries (e.g., `CHUNK_SIZE=1`).

For the full 150-doc run this is moot - `CHUNK_SIZE = None` or any value `>=` remaining will process everything.

### 7. Cell IDs stripped by `jupyter execute`

`jupyter execute --inplace` rewrites cell IDs (e.g., `cell-5` becomes a hash like `122e8054`). Subsequent `NotebookEdit` calls keyed by the original cell ID fail with `cell not found`.

**Workaround:** when editing cells programmatically after a run, either (a) find the cell by content match, or (b) restore IDs after `nbclient` execution.

## How to launch the full 150-doc run (already done, kept for reproducibility)

1. Confirm `experiments/02b_triples_extraction_minie_style.ipynb` cell `fullrun` has `CHUNK_SIZE = None` (or set explicitly to the size you want).
2. Run from `experiments/`:
   ```bash
   PYTHONUTF8=1 uv run --no-sync jupyter execute --inplace --timeout=14400 02b_triples_extraction_minie_style.ipynb
   ```
   (`--timeout=14400` = 4 hours per cell, generous.)
3. Resume logic skips already-done docs. After the run, identify any missing doc_ids by comparing `data/processed/ContraDoc/triples_minie.jsonl` against `balanced_sample.json["doc_ids"]`. For each missing doc, run the recovery snippet with up to 5 retries.

Actual outcome (April 2026): 149 / 150 docs done in the main run, 1 doc recovered via standalone retry script. Total ~$24, ~2 hours wall.

## Known limitations of the final extraction

- **27 / 150 docs (18%) lack a usable gold pair.** List + failure modes in `experiments/data/processed/ContraDoc/triples_minie_unusable.json`. Two failure modes:
  1. LLM did not tag any sentence as `is_evidence=true` (13 docs).
  2. Sentence bundling - LLM glued the gold sentence with neighbors, breaking fuzzy match.
- The downstream NLI pair builder should skip these docs (or use them as YES-only without contradiction pairs). Retrieval can still ingest their triples - the gold pair is the only thing missing.
- If thesis evaluation later flags this as material, two recovery paths: (a) re-extract with a pre-segmentation step (run a sentence splitter, feed numbered sentences to the LLM), or (b) add a "second-pass" prompt that just asks the LLM to identify `is_evidence` on the existing chunks.
