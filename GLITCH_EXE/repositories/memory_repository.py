import sqlite3
from pathlib import Path


class MemoryRepository:
    """
    Handles all direct SQLite access for GLITCH memory.
    """

    def __init__(
        self,
        database_path
    ):

        self.database_path = Path(
            database_path
        )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.connection = sqlite3.connect(
            self.database_path,
            check_same_thread=False
        )

        self.create_tables()


    # ---------------------------------------------------------
    # DATABASE SETUP
    # ---------------------------------------------------------

    def create_tables(self):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.connection.commit()


    # ---------------------------------------------------------
    # DUPLICATE CHECK
    # ---------------------------------------------------------

    def memory_exists(
        self,
        content
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM memories
            WHERE content = ?
            """,
            (
                content,
            )
        )

        return (
            cursor.fetchone()
            is not None
        )


    # ---------------------------------------------------------
    # INSERT MEMORY
    # ---------------------------------------------------------

    def add_memory(
        self,
        category,
        content
    ):

        cursor = self.connection.cursor()

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

        return cursor.lastrowid


    # ---------------------------------------------------------
    # GET ALL
    # ---------------------------------------------------------

    def get_all_memories(self):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT category, content
            FROM memories
            ORDER BY id DESC
            """
        )

        return cursor.fetchall()


    # ---------------------------------------------------------
    # SEARCH BY WORD
    # ---------------------------------------------------------

    def search_by_word(
        self,
        word,
        limit=10
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT category, content
            FROM memories
            WHERE content LIKE ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                f"%{word}%",
                limit
            )
        )

        return cursor.fetchall()


    # ---------------------------------------------------------
    # COUNT
    # ---------------------------------------------------------

    def count_memories(self):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM memories
            """
        )

        return cursor.fetchone()[0]


    # ---------------------------------------------------------
    # CLEAN SHUTDOWN
    # ---------------------------------------------------------

    def close(self):

        try:

            self.connection.close()

        except Exception:

            pass