# LLM Model Comparison: GPT-5.4 / GPT-5.5 / Claude

Snapshot as of 2026-04-26. Pricing is the standard API rate per **1 million tokens** (USD). Intelligence Index numbers are from [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models) (composite benchmark v4.0: GDPval-AA, t2-Bench Telecom, Terminal-Bench Hard, SciCode, AA-LCR, AA-Omniscience, IFBench, HLE, GPQA Diamond, CritPt).

## Headline table

| Model | Provider | Released | Context | Knowledge cutoff | Input $/M | Output $/M | Intelligence Index |
|---|---|---|---|---|---|---|---|
| GPT-5.5-pro | OpenAI | Apr 23, 2026 | 1M | Dec 1, 2025 | $30.00 | $180.00 | n/a (top tier) |
| GPT-5.5 (xhigh) | OpenAI | Apr 23, 2026 | 1M | Dec 1, 2025 | $5.00 | $30.00 | **60** |
| GPT-5.5 (high) | OpenAI | Apr 23, 2026 | 1M | Dec 1, 2025 | $5.00 | $30.00 | 59 |
| GPT-5.4 (xhigh) | OpenAI | Mar 6, 2026 | 1M | Aug 31, 2025 | $2.50 | $15.00 | 57 |
| GPT-5.4-mini | OpenAI | Mar 17, 2026 | 400K | Aug 31, 2025 | $0.75 | $4.50 | 49 |
| GPT-5.4-nano | OpenAI | Mar 17, 2026 | 400K | Aug 31, 2025 | $0.20 | $1.25 | 44 |
| Claude Opus 4.7 (max) | Anthropic | Apr 16, 2026 | 1M | Jan 2026 | $5.00 | $25.00 | 57 |
| Claude Opus 4.6 | Anthropic | late 2025 | 1M | Aug 2025 | $5.00 | $25.00 | ~53 |
| Claude Sonnet 4.6 (max) | Anthropic | late 2025 | 1M | Aug 2025 | $3.00 | $15.00 | 52 |
| Claude Sonnet 4.6 (non-reasoning) | Anthropic | late 2025 | 1M | Aug 2025 | $3.00 | $15.00 | 44 |
| Claude Haiku 4.5 (reasoning) | Anthropic | Oct 15, 2025 | 200K | Feb 2025 | $1.00 | $5.00 | 37 |
| Claude Haiku 4.5 (non-reasoning) | Anthropic | Oct 15, 2025 | 200K | Feb 2025 | $1.00 | $5.00 | 31 |

`xhigh` / `high` / `max` / `non-reasoning` denote reasoning-effort presets reported by Artificial Analysis. The same checkpoint is billed at the same per-token rate regardless of preset; cost differences come from how many reasoning tokens get generated.

## Notes and caveats

### Pricing modifiers
- **Batch API:** 50% discount on input + output for both providers (async, non-time-sensitive workloads).
- **Prompt caching (Claude):** 5-minute cache writes 1.25x base input, 1-hour writes 2x, cache reads 0.1x. So a cache hit saves ~90% on input tokens.
- **Prompt caching (OpenAI):** cached input is 0.1x base (e.g. GPT-5.5 cached input is $0.50/M).
- **Data residency:** OpenAI charges +10% for regional endpoints on GPT-5.4 / 5.4-mini; Claude charges +10% (1.1x) for `inference_geo=US` on Opus 4.7, Opus 4.6, and newer.

### Tokenization gotcha (Opus 4.7)
Opus 4.7 ships with a new tokenizer that can produce up to **35% more tokens** for the same input text vs. earlier Claude models. Per-token rate is unchanged from Opus 4.6, but per-request cost can rise. This matters when comparing 4.7 to 4.6 on a fixed text budget.

### GPT-5.5 mini / nano
**Not yet released as of 2026-04-26.** Public pattern-matching predictions place GPT-5.5-mini in late June through mid-August 2026.

### Why two Intelligence Index entries for some Claude models
Claude's reasoning effort is configurable. Artificial Analysis evaluates both the max-effort and non-reasoning configurations of the same checkpoint. Sonnet 4.6 jumps from 44 (non-reasoning) to 52 (max), Haiku 4.5 from 31 to 37. OpenAI exposes similar `xhigh` / `high` / `medium` reasoning levels.

### What "Intelligence Index" measures
A weighted composite of 10 evaluations spanning agentic coding, knowledge work, math, and reasoning. Useful for cross-model comparison; **not** a substitute for task-specific evaluation. A model that scores 49 on the Index can still beat a 60-scorer on a narrow domain (e.g. structured extraction, classification, RAG retrieval).

### Practical picks for this project (ContraDoc / KG extraction)
- **GPT-5.4-mini** (currently used in `02b_triples_extraction_minie_style.ipynb`): cheap enough for 50+50 doc sweeps; structured-output works well; Aug 2025 cutoff is fine since ContraDoc was published Aug 2024.
- **Claude Haiku 4.5** is the closest Anthropic equivalent to GPT-5.4-mini on price ($1/$5 vs $0.75/$4.50). Bigger reasoning gap (37 vs 49 Intelligence Index) but well-suited for structured extraction.
- **Claude Sonnet 4.6** at $3/$15 is the best value tier for higher-quality extraction once budget allows.

## Sources

- [OpenAI API Pricing (developer docs)](https://developers.openai.com/api/docs/pricing)
- [OpenAI Models page](https://developers.openai.com/api/docs/models)
- [GPT-5.4-mini model card](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [Claude API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Anthropic: Claude Haiku 4.5](https://www.anthropic.com/claude/haiku)
- [Anthropic: Claude Sonnet 4.6](https://www.anthropic.com/claude/sonnet)
- [Artificial Analysis - LLM Leaderboard](https://artificialanalysis.ai/leaderboards/models)
- [Artificial Analysis - GPT-5.4](https://artificialanalysis.ai/models/gpt-5-4)
- [Artificial Analysis - Claude Sonnet 4.6](https://artificialanalysis.ai/models/claude-sonnet-4-6-adaptive)
- [Artificial Analysis - Claude Haiku 4.5](https://artificialanalysis.ai/models/claude-4-5-haiku)
- [GPT-5.5 announcement (Artificial Analysis)](https://artificialanalysis.ai/articles/openai-gpt5-5-is-the-new-leading-AI-model)
- [Anthropic Transparency Hub (training cutoffs)](https://www.anthropic.com/transparency)
