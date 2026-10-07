import sqlite3
from pathlib import Path


class MemoryManager:
    def __init__(self):
        data_folder = Path("data")
        data_folder.mkdir(exist_ok=True)

        self.db_path = data_folder / "glitch_memory.db"

        self.connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False
        )

        self.create_tables()

    def create_tables(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.connection.commit()

    def remember(self, content, category="general"):
        content = content.strip()

        if not content:
            return False

        cursor = self.connection.cursor()

        # Avoid exact duplicates
        cursor.execute(
            """
            SELECT id
            FROM memories
            WHERE content = ?
            """,
            (content,)
        )

        if cursor.fetchone():
            return False

        cursor.execute(
            """
            INSERT INTO memories (
                category,
                content
            )
            VALUES (?, ?)
            """,
            (
                category,
                content
            )
        )

        self.connection.commit()

        return True

    def get_all_memories(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT category, content
            FROM memories
            ORDER BY id DESC
        """)

        return cursor.fetchall()

    def search_memories(self, query):
        cursor = self.connection.cursor()

        words = [
            word.strip()
            for word in query.split()
            if len(word.strip()) > 2
        ]

        if not words:
            return []

        results = []

        for word in words:
            cursor.execute(
                """
                SELECT category, content
                FROM memories
                WHERE content LIKE ?
                ORDER BY id DESC
                LIMIT 10
                """,
                (f"%{word}%",)
            )

            for row in cursor.fetchall():
                if row not in results:
                    results.append(row)

        return results[:10]

    def count_memories(self):
        cursor = self.connection.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM memories"
        )

        return cursor.fetchone()[0]