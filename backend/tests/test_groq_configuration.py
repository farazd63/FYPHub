import unittest

from app.config import settings


class GroqConfigurationTests(unittest.TestCase):
    def test_key_presence_only(self):
        key_present = bool(settings.GROQ_API_KEY)
        self.assertTrue(key_present)


if __name__ == "__main__":
    unittest.main()
