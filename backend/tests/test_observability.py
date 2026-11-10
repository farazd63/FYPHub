import unittest

from app.main import _workflow_name


class ObservabilityTests(unittest.TestCase):
    def test_workflow_names_are_safe_and_specific(self):
        self.assertEqual(_workflow_name("/api/v1/proposals/12/ai-review"), "proposal")
        self.assertEqual(_workflow_name("/api/v1/agent-supervision/2/runs"), "supervision")
        self.assertEqual(_workflow_name("/api/v1/auth/me"), "auth")
        self.assertEqual(_workflow_name("/api/v1/unknown"), "api")


if __name__ == "__main__":
    unittest.main()
