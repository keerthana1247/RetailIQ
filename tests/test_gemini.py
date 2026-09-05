"""
RetailIQ - Unit Tests for Gemini Integration Layer
NexusTiQ24 Hackathon | Track: PS03 - Retail: Sales and Inventory Copilot
"""

import unittest
import os
import sys

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app
from src import config
from src.gemini_client import GeminiClient


class TestGeminiIntegration(unittest.TestCase):
    def test_config_defaults(self):
        """Verify centralized model configuration constants."""
        self.assertEqual(config.GEMINI_MODEL, "gemini-3.5-flash-lite")
        self.assertEqual(config.GEMINI_EMBEDDING_MODEL, "gemini-embedding-001")

    def test_missing_api_key_handling(self):
        """Verify graceful behavior when GEMINI_API_KEY is not configured."""
        client = GeminiClient(api_key="")
        self.assertFalse(client.is_configured())

        status = client.check_availability()
        self.assertFalse(status["configured"])
        self.assertFalse(status["available"])
        self.assertEqual(status["model"], "gemini-3.5-flash-lite")
        self.assertIn("not configured", status["message"].lower())

        gen = client.generate("test prompt")
        self.assertFalse(gen["success"])
        self.assertIsNone(gen["text"])
        self.assertIn("not configured", gen["error"].lower())

    def test_placeholder_api_key_handling(self):
        """Verify placeholder values from .env.example are treated as unconfigured."""
        client = GeminiClient(api_key="your_gemini_api_key_here")
        self.assertFalse(client.is_configured())

    def test_invalid_api_key_fails_gracefully(self):
        """Verify that an invalid API key fails gracefully without crashing or leaking secrets."""
        client = GeminiClient(api_key="AIzaSyDummyKeyForTestingGracefulFailure123")
        self.assertTrue(client.is_configured())

        # check_availability must handle API failure gracefully
        status = client.check_availability()
        self.assertTrue(status["configured"])
        self.assertFalse(status["available"])

        # generate must catch exception and return error dictionary
        gen = client.generate("Hello")
        self.assertFalse(gen["success"])
        self.assertIsNone(gen["text"])
        self.assertIsNotNone(gen["error"])
        # Ensure raw key is never leaked in error
        self.assertNotIn("AIzaSyDummyKeyForTestingGracefulFailure123", gen["error"])

    def test_gemini_status_endpoint(self):
        """Verify GET /api/gemini/status returns valid schema."""
        status = app.gemini_status()
        self.assertIn("configured", status)
        self.assertIn("model", status)
        self.assertIn("available", status)
        self.assertEqual(status["model"], "gemini-3.5-flash-lite")

    def test_gemini_test_endpoint_schema(self):
        """Verify GET /api/gemini/test returns expected test response structure."""
        res = app.gemini_test()
        self.assertEqual(res["endpoint"], "dev_test")
        self.assertEqual(res["model"], "gemini-3.5-flash-lite")
        self.assertIn("result", res)
        self.assertIn("success", res["result"])


if __name__ == "__main__":
    unittest.main()
