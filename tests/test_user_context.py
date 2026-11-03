import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from llama.memory_support.memory_support import Memory_support


class TestUserScopedMemory(unittest.TestCase):
    def setUp(self):
        self.memory = Memory_support.__new__(Memory_support)
        self.memory.embedding_model = None
        self.memory.threshold_distance = 0.7
        self.memory.collection = Mock()
        self.memory.collection.query.side_effect = lambda **kwargs: {
            "documents": [[f"Memória privada de {kwargs['where']['user_id']}"]],
            "distances": [[0.1]],
        }

    def test_memory_search_is_scoped_to_user(self):
        with patch("builtins.print"):
            first_user = self.memory.mount_prompt_memory("pergunta", user_id=17)
            second_user = self.memory.mount_prompt_memory("pergunta", user_id=29)

        self.assertIn("17", first_user)
        self.assertNotIn("29", first_user)
        self.assertIn("29", second_user)
        self.assertNotIn("17", second_user)
        self.assertEqual(self.memory.collection.query.call_count, 2)
        self.assertEqual(
            self.memory.collection.query.call_args_list[0].kwargs["where"],
            {"user_id": "17"},
        )
        self.assertEqual(
            self.memory.collection.query.call_args_list[1].kwargs["where"],
            {"user_id": "29"},
        )

    def test_memory_cleanup_only_loads_selected_user(self):
        self.memory.collection.get.return_value = {
            "ids": ["memory-1"],
            "documents": ["USER: pergunta\nLLM: resposta suficientemente longa"],
            "metadatas": [{"timestamp": 1, "user_id": "17"}],
            "embeddings": [None],
        }
        self.memory.cleaner = Mock()
        self.memory.cleaner.deduplicate.side_effect = lambda entries, _model: entries
        self.memory.purifier = Mock()
        self.memory.purifier.enforce_memory_limit.side_effect = lambda entries: entries

        with patch("builtins.print"):
            self.memory._auto_clean_and_purify(user_id=17)

        self.memory.collection.get.assert_called_once_with(
            where={"user_id": "17"},
            include=["documents", "metadatas", "embeddings"],
        )

    def test_saved_memory_contains_user_scope(self):
        self.memory.db_path = tempfile.gettempdir()
        self.memory.collection.add = Mock()
        self.memory.collection.count.return_value = 1
        with patch("builtins.print"), patch.object(
            self.memory, "_auto_clean_and_purify"
        ) as cleanup:
            self.memory.append_on_memory_database(
                "pergunta", "resposta", user_id=17
            )

        metadata = self.memory.collection.add.call_args.kwargs["metadatas"][0]
        self.assertEqual(metadata["user_id"], "17")
        cleanup.assert_called_once_with(17)
