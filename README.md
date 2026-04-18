## References

de Marneffe, M.-C., Rafferty, A. N., & Manning, C. D. (2008). Finding contradictions in text. In *Proceedings of ACL-08: HLT* (pp. 1039–1047). Association for Computational Linguistics. https://aclanthology.org/P08-1118/

Li, J., Raheja, V., & Kumar, D. (2024). ContraDoc: Understanding self-contradictions in documents with large language models. In *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)* (pp. 6509–6523). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.naacl-long.362

Kim, J., Park, S., Kwon, Y., Jo, Y., Thorne, J., & Choi, E. (2023). FactKG: Fact verification via reasoning on knowledge graphs. In *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 16190–16206). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.acl-long.895

Giampiccolo, D., Magnini, B., Dagan, I., & Dolan, B. (2007). The third PASCAL recognizing textual entailment challenge. In *Proceedings of the ACL-PASCAL Workshop on Textual Entailment and Paraphrasing* (pp. 1–9). Association for Computational Linguistics. https://aclanthology.org/W07-1401/

Dagan, I., Glickman, O., & Magnini, B. (2006). The PASCAL recognising textual entailment challenge. In J. Quiñonero-Candela, I. Dagan, B. Magnini, & F. d'Alché-Buc (Eds.), *Machine learning challenges: Evaluating predictive uncertainty, visual object classification, and recognising textual entailment* (Lecture Notes in Computer Science, Vol. 3944, pp. 177–190). Springer. https://doi.org/10.1007/11736790_9

van Cauter, Z., & Yakovets, N. (2024). Ontology-guided knowledge graph construction from maintenance short texts. In *Proceedings of the 1st Workshop on Knowledge Graphs and Large Language Models (KaLLM 2024)* (pp. 75–84). Association for Computational Linguistics. https://aclanthology.org/2024.kallm-1.8/

---
---
# Old README (for reference)
---
---

# Claim Contradiction Detection over Social Media Knowledge Graphs

Detecting internal contradictions across social media claims about the same event, without relying on external knowledge bases.

## Overview

Social media streams contain contradictory assertions about the same event across multiple sources, yet existing fact-checking systems verify claims against external knowledge bases rather than detecting internal inconsistencies within a user-controlled corpus. This project proposes an end-to-end claim contradiction detection system that constructs a knowledge graph via LLM triplet extraction, applies structural pre-filtering, and scores candidate pairs with a domain-adapted NLI model.

## Research Questions

- **RQ1 - Structural Filter:** Among structural filtering strategies S-SR (same subject and relation, differing object), S-SO (same subject and object, differing relation), and S-Union (either condition), which achieves the best precision-recall tradeoff for candidate contradiction pair retrieval from a social media claim knowledge graph?
- **RQ2 - Retrieval Method:** Does combining structural and vector similarity retrieval (R-Union) improve candidate coverage over structural-only (R-Struct) and vector-only (R-Vector) retrieval?
- **RQ3 - NLI Fine-tuning:** Does weak supervision constructed by cross-pairing veracity-labeled social media threads into FactRel-style labels (NLI-PHEME) provide a cost-effective substitute for manually annotated NLI data; does pre-training on factual contradiction data (NLI-Factual; VitaminC) transfer factual discrimination capability to a new domain; and does sequential combination of both (NLI-Seq) yield further improvement over either alone?

## Architecture

The system is composed of two sub-systems:

### Ingestion Pipeline
1. Raw social media text is passed to an LLM triplet extractor, producing (Subject, Relation, Object) triplets
2. Triplets are stored as directed edges in a Neo4j knowledge graph
3. Source text embeddings are stored in a Neo4j vector index

### Query Pipeline
1. User query is mapped to canonical entity names
2. Matched entities are looked up in Neo4j to retrieve all relation edges
3. A configurable query engine applies structural filtering and/or vector retrieval
4. Candidate pairs are scored by the best NLI variant
5. Entity subgraphs are expanded via Graph RAG (BFS 2-hop) for context
6. An LLM generates natural language explanations citing specific claims and sources
7. Conversational interface supports per-pair Confirm/Dismiss feedback

## Tech Stack

| Component | Technology |
|-----------|------------|
| Knowledge Graph | Neo4j |
| Triplet Extraction | GPT-5.4 mini |
| NLI Verifier | DeBERTa-v3-base (fine-tuned) |
| Vector Embeddings | all-MiniLM-L6-v2 (Sentence Transformers) |
| Explanation Layer | GPT-5.4 mini |
| Graph RAG | Neo4j BFS traversal (2-hop) |
| Vector Index | Neo4j vector index |
| Language | Python |
| Package Manager | uv |
| <!-- TODO: Will add more later --> | |

## Dataset

- **PHEME** - 6,425 Twitter conversation threads across 9 events (2,402 rumor threads with veracity labels)
- **VitaminC** - 488,904 claim-evidence pairs from Wikipedia revisions (used for NLI pre-training)

## Ablation Study

Three-axis controlled ablation on the PHEME dataset:

| Step | Axis | Variants |
|------|------|----------|
| 4a | Structural Filter | S-SR, S-SO, S-Union |
| 4b | Retrieval Method | R-Struct, R-Vector, R-Union |
| 4c | NLI Verifier | NLI-Base, NLI-PHEME, NLI-Factual, NLI-Seq |

## Results

### Step 4a: Structural Filter (Candidate Pair Retrieval)

| Variant | Precision | Recall | F1 |
|---------|-----------|--------|----|
| S-SR    | -         | -      | -  |
| S-SO    | -         | -      | -  |
| S-Union | -         | -      | -  |

### Step 4b: Retrieval Method (Candidate Pair Retrieval)

| Variant  | Precision | Recall | F1 |
|----------|-----------|--------|----|
| R-Struct | -         | -      | -  |
| R-Vector | -         | -      | -  |
| R-Union  | -         | -      | -  |

### Step 4c: NLI Verifier (UNDERMINING Classification)

| Variant     | Precision | Recall | F1 |
|-------------|-----------|--------|----|
| NLI-Base    | -         | -      | -  |
| NLI-PHEME   | -         | -      | -  |
| NLI-Factual | -         | -      | -  |
| NLI-Seq     | -         | -      | -  |

## Installation

### Prerequisites
// TODO: Will add this later

### Setup

```bash
# TODO: Will add this later
```

### Neo4j Schema

```cypher
-- Node
(:Entity {name: String, type: String})

-- Edge
[:RELATION {
  claim_id: String,
  relation_type: String,
  post_time: DateTime,
  source_text: String,
  thread_id: String,
  event: String
}]

-- Vector Index (on source_text embeddings)
```

## Usage

```bash
# TODO: Will add this later
```


## Group Members

- st125923 Prombot Cherdchoo
- st125981 Muhammad Fahad Waqar
- st125983 Nariman Tursaliev
- st126127 Takdanai Ruxthawonwong

Asian Institute of Technology

## References

- Zubiaga et al. (2016). Analysing how people orient to and spread rumours in social media by looking at conversational threads. *PLOS ONE*.
- Mor-Lan & Levi (2024). Exploring factual entailment with NLI: A news media study. *\*SEM 2024*.
- Schuster et al. (2021). VitaminC: Robust fact verification with contrastive evidence. *NAACL 2021*.
- He et al. (2021). DeBERTa: Decoding-enhanced BERT with disentangled attention. *ICLR 2021*.
- Dougrez-Lewis et al. (2024). Knowledge graphs for real-world rumour verification. *LREC-COLING 2024*.
- Dammu et al. (2024). ClaimVer: Explainable claim-level verification through knowledge graphs. *Findings of EMNLP 2024*.
- Zhu et al. (2025). KG2RAG: Knowledge graph-guided retrieval augmented generation. *NAACL 2025*.
- TODO: Will add more later
