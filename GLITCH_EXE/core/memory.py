from pathlib import Path

from repositories.memory_repository import (
    MemoryRepository
)


class MemoryManager:
    """
    Handles GLITCH memory rules.

    MemoryManager decides:
    - what should be remembered
    - whether a memory is valid
    - how search terms are interpreted

    MemoryRepository handles:
    - SQLite
    - queries
    - inserts
    - database persistence
    """

    def __init__(self):

        data_folder = Path(
            "data"
        )

        data_folder.mkdir(
            exist_ok=True
        )

        self.db_path = (
            data_folder
            / "glitch_memory.db"
        )


        self.repository = (
            MemoryRepository(
                self.db_path
            )
        )


    # ---------------------------------------------------------
    # REMEMBER
    # ---------------------------------------------------------

    def remember(
        self,
        content,
        category="general"
    ):

        content = (
            content.strip()
        )


        if not content:

            return False


        # Avoid exact duplicates.
        if self.repository.memory_exists(
            content
        ):

            return False


        self.repository.add_memory(
            category,
            content
        )


        return True


    # ---------------------------------------------------------
    # GET ALL MEMORIES
    # ---------------------------------------------------------

    def get_all_memories(self):

        return (
            self.repository
            .get_all_memories()
        )


    # ---------------------------------------------------------
    # SEARCH MEMORY
    # ---------------------------------------------------------

    def search_memories(
        self,
        query
    ):

        words = [

            word.strip()

            for word in query.split()

            if len(
                word.strip()
            ) > 2
        ]


        if not words:

            return []


        results = []


        for word in words:

            rows = (
                self.repository
                .search_by_word(
                    word,
                    limit=10
                )
            )


            for row in rows:

                if row not in results:

                    results.append(
                        row
                    )


        return results[:10]


    # ---------------------------------------------------------
    # COUNT
    # ---------------------------------------------------------

    def count_memories(self):

        return (
            self.repository
            .count_memories()
        )


    # ---------------------------------------------------------
    # CLEAN SHUTDOWN
    # ---------------------------------------------------------

    def close(self):

        self.repository.close()