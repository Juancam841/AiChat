import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database
import chat_service
import main
from fastapi.testclient import TestClient


class ChatRoutePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test-chat.db"
        self.database_path_patch = patch.object(database, "DB_PATH", database_path)
        self.database_path_patch.start()

        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()

        self.route_patches = [
            patch.object(
                chat_service,
                "get_model_quotas",
                return_value={"groq/openai/gpt-oss-20b": {}},
            ),
            patch.object(chat_service, "is_quota_available", return_value=True),
            patch.object(chat_service, "supports_tools", return_value=False),
            patch.object(chat_service, "get_context_window", return_value=None),
            patch.object(
                chat_service,
                "trim_conversation_history",
                side_effect=lambda messages, **kwargs: messages,
            ),
        ]
        for route_patch in self.route_patches:
            route_patch.start()

    def tearDown(self):
        for route_patch in reversed(self.route_patches):
            route_patch.stop()
        self.client_context.__exit__(None, None, None)
        self.database_path_patch.stop()
        self.temp_dir.cleanup()

    def _chat_payload(self):
        return {
            "message": "Hola, prueba de persistencia",
            "strategy": "manual",
            "provider": "groq",
            "model": "openai/gpt-oss-20b",
        }

    def _database_counts(self):
        connection = database.get_connection()
        try:
            conversations = connection.execute(
                "SELECT COUNT(*) FROM conversations"
            ).fetchone()[0]
            messages = connection.execute(
                "SELECT COUNT(*) FROM messages"
            ).fetchone()[0]
            return conversations, messages
        finally:
            connection.close()

    def test_successful_manual_chat_persists_conversation_and_turn(self):
        with patch.object(
            chat_service, "ask_model", return_value="Respuesta simulada"
        ):
            response = self.client.post("/chat", json=self._chat_payload())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["response"], "Respuesta simulada")
        self.assertEqual(body["provider"], "groq")
        self.assertEqual(body["model"], "openai/gpt-oss-20b")

        conversation = database.get_conversation(body["conversation_id"])
        self.assertIsNotNone(conversation)
        messages = database.get_conversation_messages(body["conversation_id"])
        self.assertEqual(
            [(message["role"], message["content"]) for message in messages],
            [
                ("user", "Hola, prueba de persistencia"),
                ("assistant", "Respuesta simulada"),
            ],
        )

    def test_provider_failure_returns_502_without_persisting(self):
        with self.assertLogs("main", level="ERROR"):
            with patch.object(
                chat_service,
                "ask_model",
                side_effect=RuntimeError("offline"),
            ):
                response = self.client.post("/chat", json=self._chat_payload())

        self.assertEqual(response.status_code, 502)
        self.assertEqual(self._database_counts(), (0, 0))

    def test_missing_conversation_detail_returns_404(self):
        response = self.client.get("/conversations/not-a-real-conversation")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "La conversación no existe.")


if __name__ == "__main__":
    unittest.main()
