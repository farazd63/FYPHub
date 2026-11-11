"""Focused contract tests for the private Module 2 collaboration channel API."""

import unittest

from pydantic import ValidationError

from app.collaboration_channels import MessageWrite
from app.main import app


class CollaborationChannelContractTests(unittest.TestCase):
    def test_blank_messages_are_rejected(self):
        with self.assertRaises(ValidationError):
            MessageWrite(message_text="   ")

    def test_message_indentation_and_line_breaks_are_preserved(self):
        value = "  if ready:\n      send()\n"
        self.assertEqual(MessageWrite(message_text=value).message_text, value)

    def test_private_channel_routes_exist(self):
        paths = set(app.openapi()["paths"])
        self.assertIn("/api/v1/student/collaboration/channels", paths)
        self.assertIn("/api/v1/supervisor/collaboration/channels", paths)
        self.assertTrue(any(path.endswith("/messages") for path in paths if "collaboration/channels" in path))


if __name__ == "__main__":
    unittest.main()
