import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from vector_store import SearchResults, VectorStore
from config import Config


class TestRAGSystemQueryOrchestration(unittest.TestCase):
    """Verify: RAGSystem.query() calls ai_generator.generate_response() correctly."""

    def _make_rag(self, max_results=5):
        """Build a RAGSystem with all external dependencies mocked out."""
        with patch("rag_system.VectorStore"), \
             patch("rag_system.AIGenerator") as MockAI, \
             patch("rag_system.SessionManager") as MockSM, \
             patch("rag_system.ToolManager") as MockTM, \
             patch("rag_system.CourseSearchTool"), \
             patch("rag_system.CourseOutlineTool"):

            self.mock_ai = MagicMock()
            self.mock_ai.generate_response.return_value = "Mock AI answer"
            MockAI.return_value = self.mock_ai

            self.mock_sm = MagicMock()
            self.mock_sm.get_conversation_history.return_value = None
            MockSM.return_value = self.mock_sm

            self.mock_tm = MagicMock()
            self.mock_tm.get_last_sources.return_value = []
            self.mock_tm.get_tool_definitions.return_value = []
            MockTM.return_value = self.mock_tm

            from rag_system import RAGSystem
            cfg = Config(ANTHROPIC_API_KEY="test", MAX_RESULTS=max_results)
            rag = RAGSystem(cfg)
            rag.ai_generator = self.mock_ai
            rag.tool_manager = self.mock_tm
            rag.session_manager = self.mock_sm
            return rag

    def test_query_calls_ai_generator_with_prompt(self):
        rag = self._make_rag()
        rag.query("What is a neural network?")

        self.mock_ai.generate_response.assert_called_once()
        call_kwargs = self.mock_ai.generate_response.call_args[1]
        self.assertIn("neural network", call_kwargs["query"])

    def test_query_returns_ai_response_and_sources(self):
        with patch("rag_system.VectorStore"), \
             patch("rag_system.AIGenerator") as MockAI, \
             patch("rag_system.SessionManager"), \
             patch("rag_system.ToolManager") as MockTM, \
             patch("rag_system.CourseSearchTool"), \
             patch("rag_system.CourseOutlineTool"):

            mock_ai = MagicMock()
            mock_ai.generate_response.return_value = "The answer is 42"
            MockAI.return_value = mock_ai

            mock_tm = MagicMock()
            mock_tm.get_last_sources.return_value = [{"label": "Course A", "url": None}]
            mock_tm.get_tool_definitions.return_value = []
            MockTM.return_value = mock_tm

            from rag_system import RAGSystem
            cfg = Config(ANTHROPIC_API_KEY="test", MAX_RESULTS=5)
            rag = RAGSystem(cfg)
            rag.ai_generator = mock_ai
            rag.tool_manager = mock_tm

            response, sources = rag.query("something")

            self.assertEqual(response, "The answer is 42")
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]["label"], "Course A")

    def test_get_last_sources_called_after_query(self):
        rag = self._make_rag()
        rag.query("question")
        self.mock_tm.get_last_sources.assert_called_once()


class TestRAGSystemSessionHistory(unittest.TestCase):
    """Verify: session history is updated correctly after each query."""

    def test_session_history_updated_after_query(self):
        with patch("rag_system.VectorStore"), \
             patch("rag_system.AIGenerator") as MockAI, \
             patch("rag_system.SessionManager") as MockSM, \
             patch("rag_system.ToolManager") as MockTM, \
             patch("rag_system.CourseSearchTool"), \
             patch("rag_system.CourseOutlineTool"):

            mock_ai = MagicMock()
            mock_ai.generate_response.return_value = "The response"
            MockAI.return_value = mock_ai

            mock_sm = MagicMock()
            mock_sm.get_conversation_history.return_value = None
            MockSM.return_value = mock_sm

            mock_tm = MagicMock()
            mock_tm.get_last_sources.return_value = []
            mock_tm.get_tool_definitions.return_value = []
            MockTM.return_value = mock_tm

            from rag_system import RAGSystem
            cfg = Config(ANTHROPIC_API_KEY="test", MAX_RESULTS=5)
            rag = RAGSystem(cfg)
            rag.ai_generator = mock_ai
            rag.tool_manager = mock_tm
            rag.session_manager = mock_sm

            rag.query("user question", session_id="session_1")

            mock_sm.add_exchange.assert_called_once_with(
                "session_1", "user question", "The response"
            )

    def test_no_session_history_update_without_session_id(self):
        with patch("rag_system.VectorStore"), \
             patch("rag_system.AIGenerator") as MockAI, \
             patch("rag_system.SessionManager") as MockSM, \
             patch("rag_system.ToolManager") as MockTM, \
             patch("rag_system.CourseSearchTool"), \
             patch("rag_system.CourseOutlineTool"):

            mock_ai = MagicMock()
            mock_ai.generate_response.return_value = "answer"
            MockAI.return_value = mock_ai

            mock_sm = MagicMock()
            MockSM.return_value = mock_sm

            mock_tm = MagicMock()
            mock_tm.get_last_sources.return_value = []
            mock_tm.get_tool_definitions.return_value = []
            MockTM.return_value = mock_tm

            from rag_system import RAGSystem
            cfg = Config(ANTHROPIC_API_KEY="test", MAX_RESULTS=5)
            rag = RAGSystem(cfg)
            rag.ai_generator = mock_ai
            rag.tool_manager = mock_tm
            rag.session_manager = mock_sm

            rag.query("question without session")

            mock_sm.add_exchange.assert_not_called()


class TestRAGSystemToolErrorPropagation(unittest.TestCase):
    """Verify: tool error string flows correctly from VectorStore → CourseSearchTool → AI."""

    def test_tool_error_string_returned_from_execute(self):
        """CourseSearchTool.execute() returns error string when VectorStore returns error SearchResults."""
        from search_tools import CourseSearchTool

        mock_store = MagicMock()
        mock_store.search.return_value = SearchResults.empty(
            "Search error: n_results must be a positive integer"
        )

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="any content question")

        self.assertEqual(result, "Search error: n_results must be a positive integer")


class TestRAGSystemBugVerification(unittest.TestCase):
    """
    Bug-confirmation and fix-verification tests.

    test_config_max_results_is_zero:
        PASSES against CURRENT (broken) system.
        FAILS after Fix 1 (MAX_RESULTS changed to 5).

    test_max_results_zero_always_produces_search_error:
        PASSES against CURRENT (broken) system — confirms the bug.
        FAILS after Fix 2 (guard added in vector_store.py).

    test_vector_store_guard_prevents_zero_n_results:
        FAILS against CURRENT (broken) system.
        PASSES after Fix 2 is applied.
    """

    def test_config_max_results_is_positive(self):
        """Config.MAX_RESULTS default is 5 (was incorrectly 0, now fixed)."""
        cfg = Config()
        self.assertEqual(cfg.MAX_RESULTS, 5)

    def test_max_results_zero_always_produces_search_error(self):
        """
        VectorStore.search() with max_results=0 returns SearchResults with .error set,
        because ChromaDB rejects n_results=0.

        STATUS: PASSES against CURRENT system (bug confirmed).
                FAILS after Fix 2 (guard clamps to 5, so no exception occurs).
        """
        with patch("chromadb.PersistentClient") as MockChromaClient, \
             patch("chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction"):

            mock_collection = MagicMock()
            mock_collection.query.side_effect = Exception(
                "n_results must be a positive integer"
            )

            mock_client_instance = MagicMock()
            mock_client_instance.get_or_create_collection.return_value = mock_collection
            MockChromaClient.return_value = mock_client_instance

            store = VectorStore(
                chroma_path="./fake_path",
                embedding_model="all-MiniLM-L6-v2",
                max_results=0,
            )

            results = store.search(query="what is machine learning")

            self.assertIsNotNone(
                results.error,
                "Expected search error due to max_results=0, but no error was returned. "
                "This means Fix 2 has been applied.",
            )
            self.assertIn("n_results", results.error)

    def test_vector_store_guard_prevents_zero_n_results(self):
        """
        After Fix 2: VectorStore.search() with max_results=0 should clamp to 5
        and NOT pass n_results=0 to ChromaDB.

        STATUS: FAILS against CURRENT system (no guard exists yet).
                PASSES after Fix 2 is applied.
        """
        with patch("chromadb.PersistentClient") as MockChromaClient, \
             patch("chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction"):

            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
            }

            mock_client_instance = MagicMock()
            mock_client_instance.get_or_create_collection.return_value = mock_collection
            MockChromaClient.return_value = mock_client_instance

            store = VectorStore(
                chroma_path="./fake_path",
                embedding_model="all-MiniLM-L6-v2",
                max_results=0,
            )

            results = store.search(query="anything")

            self.assertIsNone(
                results.error,
                "Search returned an error — Fix 2 has not been applied yet."
            )
            call_kwargs = mock_collection.query.call_args[1]
            self.assertGreater(
                call_kwargs["n_results"], 0,
                "n_results was still 0 — the guard in vector_store.py was not added.",
            )


if __name__ == "__main__":
    unittest.main()
