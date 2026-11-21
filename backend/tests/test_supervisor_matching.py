"""Deterministic supervisor matching scoring and contract tests."""

import math
import unittest

from pydantic import ValidationError

from app.schemas.supervisor_matching import AIRankingPayload, MatchingConfigWrite, ProposalExtraction
from app.supervisor_matching import DEFAULT_WEIGHTS, _cosine, _embedding, _history_text, _merge_ai_ranking, _text_score


class SupervisorMatchingContractTests(unittest.TestCase):
    def test_default_weights_are_normalized(self):
        self.assertTrue(math.isclose(sum(DEFAULT_WEIGHTS.values()), 1.0))

    def test_matching_configuration_requires_exact_weight_set(self):
        payload = MatchingConfigWrite(weights=DEFAULT_WEIGHTS)
        self.assertEqual(set(payload.weights), set(DEFAULT_WEIGHTS))
        with self.assertRaises(ValueError):
            MatchingConfigWrite(weights={**DEFAULT_WEIGHTS, "extra": 0})

    def test_ai_extraction_schema_rejects_unknown_keys(self):
        with self.assertRaises(ValidationError):
            ProposalExtraction.model_validate({"title": "A proposal", "supervisor_recommendation": "Dr. X"})

    def test_embedding_is_reproducible_and_normalized(self):
        first = _embedding("machine learning information retrieval")
        second = _embedding("machine learning information retrieval")
        self.assertEqual(first, second)
        self.assertAlmostEqual(math.sqrt(sum(value * value for value in first)), 1.0, places=5)

    def test_related_terms_produce_a_positive_score(self):
        proposal = _embedding("machine learning information retrieval")
        score = _text_score({"machine", "learning", "retrieval"}, {"machine", "learning", "nlp"}, proposal)
        self.assertGreater(score, 0)

    def test_pgvector_array_values_are_supported(self):
        class ArrayLike:
            def tolist(self):
                return [1.0, 0.0]

        self.assertEqual(_cosine(ArrayLike(), [1.0, 0.0]), 1.0)

    def test_history_text_normalizes_extracted_metadata(self):
        self.assertEqual(_history_text({"value": "The extracted methodology"}), "The extracted methodology")
        self.assertEqual(_history_text({"display": "Not detected in PDF"}), "Not detected in PDF")
        self.assertEqual(_history_text(["NLP", "Python"]), "NLP; Python")

    def test_ai_ranking_contract_requires_unique_candidates(self):
        with self.assertRaises(ValueError):
            AIRankingPayload.model_validate({"rankings": [{"candidate_id": 1, "score": 80, "rationale": "fit"}, {"candidate_id": 1, "score": 70, "rationale": "fit"}]})

    def test_ai_ranking_blends_with_deterministic_score(self):
        candidates = [
            {"supervisor_id": 1, "final_score": 90, "score_components": {}, "explanation": {}},
            {"supervisor_id": 2, "final_score": 80, "score_components": {}, "explanation": {}},
        ]
        ranked = _merge_ai_ranking(candidates, {"rankings": [
            {"candidate_id": 1, "score": 50, "rationale": "Relevant verified evidence."},
            {"candidate_id": 2, "score": 100, "rationale": "Strong relevant evidence."},
        ]}, model="llama3.1:8b")
        self.assertIsNotNone(ranked)
        self.assertEqual([item["supervisor_id"] for item in ranked or []], [2, 1])
        self.assertEqual((ranked or [])[0]["ranking_method"], "llama3.1-assisted")


if __name__ == "__main__":
    unittest.main()

