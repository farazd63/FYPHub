import unittest
from app.team_compatibility import aggregate_compatibility

class TeamCompatibilityTests(unittest.TestCase):
    def test_equal_weight_and_unanswered_excluded(self):
        result = aggregate_compatibility({"skills": True, "domain": False, "availability": None})
        self.assertEqual(result, {"categories": {"skills": True, "domain": False}, "matched": 1, "answered": 2, "fraction": 0.5})
    def test_no_answers_is_not_zero_score(self):
        self.assertEqual(aggregate_compatibility({})["fraction"], None)
    def test_unknown_or_non_boolean_assessment_is_rejected(self):
        for value in ({"performance": True}, {"skills": 1}, {"skills": "yes"}):
            with self.subTest(value=value), self.assertRaises(ValueError): aggregate_compatibility(value)
