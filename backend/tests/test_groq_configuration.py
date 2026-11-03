import unittest

from app.config import settings


class GroqConfigurationTests(unittest.TestCase):
    def test_key_is_optional_for_ollama(self):
        self.assertEqual(settings.AI_PROVIDER, "ollama")
        self.assertFalse(bool(settings.GROQ_API_KEY))


if __name__ == "__main__":
    unittest.main()
