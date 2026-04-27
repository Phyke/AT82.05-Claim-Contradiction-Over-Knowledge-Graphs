from pathlib import Path

import numpy as np
import torch
from loguru import logger
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from config import settings


class NliScorer:
    def __init__(self, checkpoint_path: str | None = None):
        path = Path(checkpoint_path or settings.nli_checkpoint_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"NLI checkpoint not found: {path}")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("Loading NLI checkpoint from {} on {}", path, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path).to(self.device)
        self.model.eval()
        id2label = self.model.config.id2label
        self.contra_idx = next(i for i, v in id2label.items() if "contradiction" in v.lower() and "not" not in v.lower())
        logger.info("NLI loaded. id2label={}, contra_idx={}", id2label, self.contra_idx)

    @torch.no_grad()
    def score(self, premises: list[str], hypotheses: list[str]) -> list[float]:
        if not premises:
            return []
        scores: list[float] = []
        bs = settings.nli_batch_size
        for start in range(0, len(premises), bs):
            end = start + bs
            enc = self.tokenizer(
                premises[start:end],
                hypotheses[start:end],
                padding=True,
                truncation=True,
                max_length=settings.nli_max_len,
                return_tensors="pt",
            ).to(self.device)
            logits = self.model(**enc).logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()
            scores.extend(float(p[self.contra_idx]) for p in probs)
        return scores

    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        forward = self.score([a for a, _ in pairs], [b for _, b in pairs])
        backward = self.score([b for _, b in pairs], [a for a, _ in pairs])
        return [float(np.maximum(f, b)) for f, b in zip(forward, backward)]
