"""
Sketch: MinIE-inspired extension of notebook 02's extraction schema.

This is NOT a runnable notebook; it's the two cells (schema + system prompt)
to drop into a new `02b_triples_extraction_minie_style.ipynb`.  The rest of
notebook 02 (loading, fuzzy match, persistence loop) stays unchanged because
the new fields default to safe values ('+', 'CT', None) and old downstream
notebooks keep working.

Reference: Gashteovski, Gemulla, del Corro. "MinIE: Minimizing Facts in
Open Information Extraction." EMNLP 2017.
"""

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Cell: Pydantic schema (replaces the schema cell of notebook 02)
# ---------------------------------------------------------------------------


class Triple(BaseModel):
    # Core triple — same as notebook 02, with one important change to `p`.
    s: str = Field(
        description=(
            "Subject — noun phrase, with pronouns and bare definites resolved "
            "to their antecedent using document context."
        )
    )
    p: str = Field(
        description=(
            "Predicate — short verbal phrase. Express the relation in its "
            "AFFIRMATIVE, CERTAIN form. Do NOT include negation words "
            "('not', 'never') or modal/possibility words ('may', 'probably', "
            "'might') in the predicate; report those via the polarity / "
            "modality fields below. Use the surface form of the verb only "
            "(e.g. 'donate', 'born_in', 'manage_to_enter')."
        )
    )
    o: str = Field(
        description=(
            "Object — noun phrase, numeric value (use the placeholder 'Q' if "
            "quantity is annotated below), date, or short complement."
        )
    )

    # MinIE-style semantic annotations.
    polarity: Literal["+", "-"] = Field(
        default="+",
        description=(
            "'+' if the relation is asserted positively, '-' if the sentence "
            "negates it ('not', 'never', 'no', 'none', 'nothing')."
        ),
    )
    polarity_marker: str | None = Field(
        default=None,
        description=(
            "The exact negation word from the source sentence when polarity "
            "is '-' (e.g. 'not', 'never'). None when polarity is '+'."
        ),
    )
    modality: Literal["CT", "PS"] = Field(
        default="CT",
        description=(
            "'CT' (certain) by default. 'PS' (possible) if the relation is "
            "hedged with modals ('may', 'might', 'could', 'should', 'would'),"
            " adverbs ('probably', 'possibly', 'maybe', 'likely'), or "
            "infinitive phrases ('is going to', 'plans to', 'intends to')."
        ),
    )
    modality_marker: str | None = Field(
        default=None,
        description=(
            "The exact possibility word/phrase from the source sentence when "
            "modality is 'PS' (e.g. 'probably', 'may'). None when modality "
            "is 'CT'."
        ),
    )
    attribution: str | None = Field(
        default=None,
        description=(
            "Supplier of information when the claim is reported speech, "
            "belief, or attributed via 'according to'. E.g. for 'Pinocchio "
            "believes that Superman was born on Krypton' the triple "
            "(Superman, born_on, Krypton) has attribution='Pinocchio'. None "
            "for direct factual statements."
        ),
    )
    quantity: str | None = Field(
        default=None,
        description=(
            "Original surface form of any cardinal/quantity expression that "
            "has been replaced by the placeholder 'Q' in s or o. "
            "E.g. if o='Q cats' then quantity='9' (or 'all', 'almost 100', "
            "etc.). None if no quantity normalization was applied."
        ),
    )


class SentenceExtraction(BaseModel):
    sentence_id: int = Field(
        description="1-indexed sentence position within the document, in original order."
    )
    source_text: str = Field(
        description=(
            "Verbatim sentence text, exactly as it appears in the document. "
            "Do not paraphrase, normalize, or trim."
        )
    )
    triples: list[Triple] = Field(
        description=(
            "All claim triples extracted from this sentence. Empty list if "
            "the sentence has no extractable claim."
        )
    )
    is_evidence: bool = Field(
        default=False,
        description=(
            "True on the ONE sentence matching the Evidence metadata (YES "
            "docs only). False for all other sentences and for every "
            "sentence in NO docs."
        ),
    )
    ref_index: int | None = Field(
        default=None,
        description=(
            "0-based index into the Reference sentences list, set on the "
            "sentence matching that Reference (YES docs only). None "
            "otherwise."
        ),
    )


class DocumentExtraction(BaseModel):
    sentences: list[SentenceExtraction]


# ---------------------------------------------------------------------------
# Cell: System prompt (replaces SYSTEM_PROMPT in the client cell of notebook 02)
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """You are an information extractor. Given a document, split \
it into sentences and extract all claim triples (subject, predicate, object) \
per sentence, along with semantic annotations on each triple.

Rules for the core triple:
- Resolve pronouns and bare definites to their antecedents using surrounding \
context (e.g., 'she' -> 'Mrs. Tittlemouse'; 'the company' -> 'Microsoft \
Israel').
- Subjects and objects should be noun phrases, numeric values, or dates -- \
concise but specific.
- Express the predicate in its AFFIRMATIVE, CERTAIN form. Do NOT bake \
polarity, modality, or attribution into the predicate string. For example, \
from "Faust did not make a deal with the Devil", extract \
p='make_a_deal_with' with polarity='-' and polarity_marker='not'. From \
"Superman may have been born on Krypton", extract p='born_on' with \
modality='PS' and modality_marker='may'.

Rules for semantic annotations (per triple):
- polarity: '+' for affirmed claims, '-' if the sentence negates them. \
polarity_marker holds the exact negation word ('not', 'never', 'no'); None \
when '+'.
- modality: 'CT' (certain) by default. 'PS' (possible) for hedged claims \
with modals ('may', 'might', 'could'), adverbs ('probably', 'possibly', \
'likely', 'maybe'), or infinitive verbs ('is going to', 'plans to', \
'intends to'). modality_marker holds the exact word/phrase; None when 'CT'.
- attribution: when a claim is REPORTED through a believer/sayer ('X \
believes that Y', 'according to X, Y', 'X said Y'), set attribution=X and \
put the inner claim Y as the triple. For direct facts, attribution=None.
- quantity: when the subject or object contains a cardinal/quantity \
expression ('9 cats', 'all cats', 'almost 100 cats'), replace it with the \
placeholder 'Q' in s/o and put the original surface form in quantity ('9', \
'all', 'almost 100'). Skip when there is no quantity to normalize.

Document-structure rules (unchanged from naive extraction):
- A sentence with no extractable claim has an empty `triples` list, but the \
sentence MUST still appear in the output.
- Preserve sentences in document order. Do not split, merge, paraphrase, or \
omit them.
- `source_text` must match the document character-for-character.

Contradiction-metadata rules (unchanged): is_evidence/ref_index tagging \
applies when the user message includes Evidence/Reference blocks.
"""


# ---------------------------------------------------------------------------
# Notebook 03 update (sketch): persist new annotation fields on :RELATION
# ---------------------------------------------------------------------------
#
# In notebook 03's per-triple insert Cypher, add the new fields as edge
# properties so RQ1 patterns can filter on them:
#
#   MERGE (h)-[r:RELATION {
#       doc_id: $doc_id,
#       sentence_id: $sentence_id,
#       p: $p,
#       polarity: $polarity,
#       modality: $modality,
#       attribution: $attribution
#   }]->(t)
#
# Then RQ1 gains a polarity-flip pattern in addition to S-SR / S-SO:
#
#   MATCH (s)-[r1:RELATION]->(o), (s)-[r2:RELATION]->(o)
#   WHERE r1.doc_id = r2.doc_id
#     AND r1.sentence_id <> r2.sentence_id
#     AND r1.p = r2.p
#     AND r1.polarity <> r2.polarity
#   RETURN r1, r2  // direct contradiction signal: same (s, p, o), opposite polarity
