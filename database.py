
import sqlite3
import uuid

from pathlib import Path
from datetime import datetime, timezone


# Ubicación de la base de datos
DB_PATH = Path(__file__).resolve().parent / "aichat.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database():

    connection = get_connection()

    try:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK(role IN ('system', 'user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,

                FOREIGN KEY (conversation_id)
                    REFERENCES conversations(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS message_search_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                title TEXT,
                url TEXT,
                content TEXT,
                published_date TEXT,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id);

            CREATE TABLE IF NOT EXISTS usage_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                success INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_usage_provider_model
            ON usage_records(provider, model);

            CREATE INDEX IF NOT EXISTS idx_usage_created_at
            ON usage_records(created_at);
        """)

        # Migración compatible con bases de datos existentes
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(usage_records)"
            ).fetchall()
        }

        if "web_search_requests" not in columns:
            connection.execute("""
                ALTER TABLE usage_records
                ADD COLUMN web_search_requests INTEGER NOT NULL DEFAULT 0
            """)

        if "browser_open_requests" not in columns:
            connection.execute("""
                ALTER TABLE usage_records
                ADD COLUMN browser_open_requests INTEGER NOT NULL DEFAULT 0
            """)

        connection.commit()

    finally:
        connection.close()


def create_conversation(provider, model, title="Nueva conversación"):

    conversation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    connection = get_connection()

    try:
        connection.execute("""
            INSERT INTO conversations (
                id, title, provider, model, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            conversation_id,
            title,
            provider,
            model,
            now,
            now
        ))

        connection.commit()

        return conversation_id

    finally:
        connection.close()


def save_message(conversation_id, role, content, results=None):

    now = datetime.now(timezone.utc).isoformat()

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO messages (
                conversation_id, role, content, created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            conversation_id,
            role,
            content,
            now
        ))

        if results:
            connection.executemany("""
                INSERT INTO message_search_results (
                    message_id, title, url, content, published_date
                ) VALUES (?, ?, ?, ?, ?)
            """, [
                (cursor.lastrowid, item.get("title"), item.get("url"),
                 item.get("content"), item.get("published_date"))
                for item in results
            ])

        connection.execute("""
            UPDATE conversations
            SET updated_at = ?
            WHERE id = ?
        """, (now, conversation_id))

        connection.commit()

    finally:
        connection.close()


def get_conversation_messages(conversation_id):

    connection = get_connection()

    try:
        rows = connection.execute("""
            SELECT id, role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
        """, (conversation_id,)).fetchall()

        messages = [dict(row) for row in rows]
        for message in messages:
            results = connection.execute("""
                SELECT title, url, content, published_date
                FROM message_search_results
                WHERE message_id = ? ORDER BY id ASC
            """, (message.pop("id"),)).fetchall()
            if results:
                message["results"] = [dict(row) for row in results]
        return messages
    finally:
        connection.close()


def save_turn(conversation_id, user_content, assistant_content, results=None):
    """Persist both messages and their search sources in one transaction."""
    now = datetime.now(timezone.utc).isoformat()
    connection = get_connection()
    try:
        connection.execute("""
            INSERT INTO messages (conversation_id, role, content, created_at)
            VALUES (?, 'user', ?, ?)
        """, (conversation_id, user_content, now))
        assistant_cursor = connection.execute("""
            INSERT INTO messages (conversation_id, role, content, created_at)
            VALUES (?, 'assistant', ?, ?)
        """, (conversation_id, assistant_content, now))
        if results:
            connection.executemany("""
                INSERT INTO message_search_results
                    (message_id, title, url, content, published_date)
                VALUES (?, ?, ?, ?, ?)
            """, [
                (assistant_cursor.lastrowid, item.get("title"), item.get("url"),
                 item.get("content"), item.get("published_date"))
                for item in results
            ])
        connection.execute("""
            UPDATE conversations SET updated_at = ? WHERE id = ?
        """, (now, conversation_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def get_conversation(conversation_id):

    connection = get_connection()

    try:
        row = connection.execute("""
            SELECT *
            FROM conversations
            WHERE id = ?
        """, (conversation_id,)).fetchone()

        return dict(row) if row else None

    finally:
        connection.close()


def get_all_conversations():

    connection = get_connection()

    try:
        rows = connection.execute("""
            SELECT *
            FROM conversations
            ORDER BY updated_at DESC
        """).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def delete_conversation(conversation_id):

    connection = get_connection()

    try:
        cursor = connection.execute("""
            DELETE FROM conversations
            WHERE id = ?
        """, (conversation_id,))

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()


def update_conversation_title(conversation_id, new_title):

    now = datetime.now(timezone.utc).isoformat()

    connection = get_connection()

    try:
        cursor = connection.execute("""
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ?
        """, (
            new_title,
            now,
            conversation_id
        ))

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()


def update_conversation_model(conversation_id, provider, model):

    now = datetime.now(timezone.utc).isoformat()

    connection = get_connection()

    try:
        cursor = connection.execute("""
            UPDATE conversations
            SET provider = ?, model = ?, updated_at = ?
            WHERE id = ?
        """, (
            provider,
            model,
            now,
            conversation_id
        ))

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()


