# Claim Contradiction Detection over Knowledge Graphs

Detecting internal contradictions across claims about the same event, without relying on external knowledge bases. 

## Dataset
- From `Find Contradictions in Text` (de Marneffe et al., 2008):
  - Real-Life Contradiction Corpus (131 pairs of contradictory claims about the same event, annotated by experts) (de Marneffe et al., 2008) as positive examples.
  - RTE2_negated - 397 + 51 = 448 pairs of claims that are not contradictory, but rather entailment or neutral (Giampiccolo et al., 2007; Dagan et al., 2006) as negative examples.
- From `ContraDoc` (Li et al., 2024):
  - ContraDoc - 891 pairs of claims from Wikipedia articles that are either contradictory or non-contradictory.


## References

de Marneffe, M.-C., Rafferty, A. N., & Manning, C. D. (2008). Finding contradictions in text. In *Proceedings of ACL-08: HLT* (pp. 1039–1047). Association for Computational Linguistics. https://aclanthology.org/P08-1118/

Li, J., Raheja, V., & Kumar, D. (2024). ContraDoc: Understanding self-contradictions in documents with large language models. In *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)* (pp. 6509–6523). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.naacl-long.362

Kim, J., Park, S., Kwon, Y., Jo, Y., Thorne, J., & Choi, E. (2023). FactKG: Fact verification via reasoning on knowledge graphs. In *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 16190–16206). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.acl-long.895

Giampiccolo, D., Magnini, B., Dagan, I., & Dolan, B. (2007). The third PASCAL recognizing textual entailment challenge. In *Proceedings of the ACL-PASCAL Workshop on Textual Entailment and Paraphrasing* (pp. 1–9). Association for Computational Linguistics. https://aclanthology.org/W07-1401/

Dagan, I., Glickman, O., & Magnini, B. (2006). The PASCAL recognising textual entailment challenge. In J. Quiñonero-Candela, I. Dagan, B. Magnini, & F. d'Alché-Buc (Eds.), *Machine learning challenges: Evaluating predictive uncertainty, visual object classification, and recognising textual entailment* (Lecture Notes in Computer Science, Vol. 3944, pp. 177–190). Springer. https://doi.org/10.1007/11736790_9

van Cauter, Z., & Yakovets, N. (2024). Ontology-guided knowledge graph construction from maintenance short texts. In *Proceedings of the 1st Workshop on Knowledge Graphs and Large Language Models (KaLLM 2024)* (pp. 75–84). Association for Computational Linguistics. https://aclanthology.org/2024.kallm-1.8/

