from typing import Literal

from langchain_anthropic import ChatAnthropic
from loguru import logger
from pydantic import BaseModel, Field

from config import settings


class Triple(BaseModel):
    s: str = Field(
        description="Subject - noun phrase, with pronouns and bare definites resolved to their antecedent using document context."
    )
    p: str = Field(
        description=(
            "Predicate - short verbal phrase in its affirmative, certain form. Do NOT bake polarity ('not') or modality "
            "('may', 'might') into the predicate; report those via the polarity / modality fields below. Use the surface "
            "form of the verb only (e.g. 'donate', 'born_in', 'manage_to_enter')."
        )
    )
    o: str = Field(
        description="Object - noun phrase, numeric value (or 'Q' placeholder when quantity is annotated below), date, or short complement."
    )

    polarity: Literal["+", "-"] = Field(
        default="+",
        description="'+' if the relation is asserted positively, '-' if the sentence negates it ('not', 'never', 'no', 'none', 'nothing').",
    )
    polarity_marker: str | None = Field(
        default=None,
        description="The exact negation word from the source sentence when polarity is '-' (e.g. 'not', 'never'). None when polarity is '+'.",
    )
    modality: Literal["CT", "PS"] = Field(
        default="CT",
        description=(
            "'CT' (certain) by default. 'PS' (possible) if the relation is hedged with modals ('may', 'might', 'could', "
            "'should', 'would'), adverbs ('probably', 'possibly', 'maybe', 'likely'), or 'it is possible that...' framings."
        ),
    )
    modality_marker: str | None = Field(
        default=None,
        description="The exact possibility word/phrase from the source sentence when modality is 'PS'. None when modality is 'CT'.",
    )
    attribution: str | None = Field(
        default=None,
        description=(
            "Supplier of information when the claim is reported speech, belief, or attributed via 'according to'. "
            "E.g. for 'Pinocchio believes that Superman was born on Krypton' the triple (Superman, born_on, Krypton) "
            "has attribution='Pinocchio'. None for direct factual statements."
        ),
    )
    quantity: str | None = Field(
        default=None,
        description=(
            "Original surface form of any cardinal/quantity expression that has been replaced by the placeholder 'Q' in s or o. "
            "E.g. if o='Q cats' then quantity='9' (or 'all', 'almost 100', etc.). None if no quantity normalization was applied."
        ),
    )


class SentenceExtraction(BaseModel):
    sentence_id: int = Field(description="1-indexed sentence position within the document, in original order.")
    source_text: str = Field(description="Verbatim sentence text, exactly as it appears in the document. Do not paraphrase, normalize, or trim.")
    triples: list[Triple] = Field(description="All claim triples extracted from this sentence. Empty list if the sentence has no extractable claim.")


class DocumentExtraction(BaseModel):
    sentences: list[SentenceExtraction]


SYSTEM_PROMPT = """You are an information extractor. Given a document, split it into sentences and extract all claim triples (subject, predicate, object) per sentence.

Rules for extraction:
- Resolve pronouns and bare definites to their antecedents using surrounding context (e.g., 'she' -> 'Mrs. Tittlemouse'; 'the company' -> 'Microsoft Israel').
- Predicates are in their AFFIRMATIVE, CERTAIN form. Do NOT bake polarity or modality into the predicate string. Use polarity / modality fields instead.
- Subjects and objects should be noun phrases, numeric values, or dates - concise but specific.
- Replace cardinal/quantity expressions in s or o with the placeholder 'Q' and report the original form via the quantity field.
- Set polarity='-' when the source sentence negates the relation; record the marker word in polarity_marker.
- Set modality='PS' when the source hedges the relation with modals/adverbs; record the marker in modality_marker.
- Set attribution when the claim is reported speech / belief / 'according to X' framing; otherwise leave it None.
- A sentence with no extractable claim has an empty triples list, but the sentence MUST still appear in the output (with its source_text) so sentence_id stays aligned with the document.
- Preserve sentences in document order. Do not split, merge, paraphrase, or omit them.
- source_text must match the document character-for-character (including punctuation and casing).
"""


_extractor = None


def _get_extractor():
    global _extractor
    if _extractor is None:
        llm = ChatAnthropic(
            model=settings.triples_extraction_model,
            api_key=settings.anthropic_api_key,
            timeout=120,
        )
        _extractor = llm.with_structured_output(DocumentExtraction)
    return _extractor


async def extract_document(text: str) -> DocumentExtraction:
    logger.info("Extracting triples: model={}, doc_chars={}", settings.triples_extraction_model, len(text))
    extractor = _get_extractor()
    result = await extractor.ainvoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Document:\n{text}"},
        ]
    )
    n_triples = sum(len(s.triples) for s in result.sentences)
    logger.info("Extracted {} sentences, {} triples", len(result.sentences), n_triples)
    return result
