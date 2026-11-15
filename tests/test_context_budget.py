import unittest

from conversation_context import (
    MAX_COMPLETION_TOKENS,
    MAX_CONTEXT_TOKENS,
    get_input_token_budget,
)
from models import get_context_window


class ContextBudgetTests(unittest.TestCase):
    def test_unknown_window_keeps_conservative_global_budget(self):
        self.assertEqual(get_input_token_budget(None), MAX_CONTEXT_TOKENS)

    def test_declared_window_reserves_completion_tokens(self):
        window = MAX_COMPLETION_TOKENS + 1024
        self.assertEqual(get_input_token_budget(window), 1024)

    def test_declared_large_window_does_not_raise_global_budget(self):
        self.assertEqual(get_input_token_budget(131072), MAX_CONTEXT_TOKENS)

    def test_declared_window_smaller_than_completion_budget(self):
        self.assertEqual(get_input_token_budget(1024), 0)

    def test_model_catalog_window_lookup(self):
        self.assertEqual(
            get_context_window("groq", "openai/gpt-oss-20b"),
            131072,
        )
        self.assertIsNone(get_context_window("groq", "unknown-model"))


if __name__ == "__main__":
    unittest.main()
