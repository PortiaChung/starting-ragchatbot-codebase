import unittest
from unittest.mock import MagicMock

from search_tools import CourseSearchTool
from vector_store import SearchResults


def make_mock_store():
    """Return a MagicMock preconfigured to stand in for VectorStore."""
    store = MagicMock()
    store.get_lesson_link.return_value = None
    return store


class TestCourseSearchToolHappyPath(unittest.TestCase):
    """Verify: non-empty results with no error → formatted string returned."""

    def test_happy_path_returns_formatted_results(self):
        store = make_mock_store()
        store.search.return_value = SearchResults(
            documents=["Chunk content about transformers"],
            metadata=[{"course_title": "ML Basics", "lesson_number": 3}],
            distances=[0.25],
        )
        store.get_lesson_link.return_value = "https://example.com/lesson/3"

        tool = CourseSearchTool(store)
        result = tool.execute(query="what are transformers")

        self.assertIn("[ML Basics - Lesson 3]", result)
        self.assertIn("Chunk content about transformers", result)

    def test_happy_path_header_without_lesson_number(self):
        """Metadata without lesson_number omits '- Lesson X' from header."""
        store = make_mock_store()
        store.search.return_value = SearchResults(
            documents=["Some content"],
            metadata=[{"course_title": "Design Patterns"}],
            distances=[0.1],
        )

        tool = CourseSearchTool(store)
        result = tool.execute(query="singleton")

        self.assertIn("[Design Patterns]", result)
        self.assertNotIn("Lesson", result)


class TestCourseSearchToolErrorPropagation(unittest.TestCase):
    """Verify: results.error → execute() returns that error string verbatim.

    This is the exact path that fires in the broken system:
    VectorStore.search() catches the ChromaDB exception (n_results=0)
    and returns SearchResults.empty("Search error: ...").
    CourseSearchTool.execute() hits `if results.error: return results.error`.
    """

    def test_error_in_results_is_returned_verbatim(self):
        store = make_mock_store()
        store.search.return_value = SearchResults.empty(
            "Search error: n_results must be a positive integer"
        )

        tool = CourseSearchTool(store)
        result = tool.execute(query="tell me about lesson 1")

        self.assertEqual(result, "Search error: n_results must be a positive integer")

    def test_custom_error_message_is_returned(self):
        """Course-not-found error (from _resolve_course_name) propagates correctly."""
        store = make_mock_store()
        store.search.return_value = SearchResults.empty(
            "No course found matching 'Nonexistent Course'"
        )

        tool = CourseSearchTool(store)
        result = tool.execute(query="anything", course_name="Nonexistent Course")

        self.assertEqual(result, "No course found matching 'Nonexistent Course'")


class TestCourseSearchToolEmptyResults(unittest.TestCase):
    """Verify: search returns zero documents with no error → "No relevant content found"."""

    def test_empty_results_no_filters(self):
        store = make_mock_store()
        store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        tool = CourseSearchTool(store)
        result = tool.execute(query="obscure topic")

        self.assertIn("No relevant content found", result)

    def test_empty_results_with_course_filter_mentions_course(self):
        store = make_mock_store()
        store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        tool = CourseSearchTool(store)
        result = tool.execute(query="topic", course_name="Python Basics")

        self.assertIn("No relevant content found", result)
        self.assertIn("Python Basics", result)

    def test_empty_results_with_lesson_filter_mentions_lesson(self):
        store = make_mock_store()
        store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        tool = CourseSearchTool(store)
        result = tool.execute(query="topic", lesson_number=5)

        self.assertIn("No relevant content found", result)
        self.assertIn("lesson 5", result)


class TestCourseSearchToolParameterForwarding(unittest.TestCase):
    """Verify: execute() forwards course_name and lesson_number to store.search()."""

    def test_course_name_forwarded_to_store_search(self):
        store = make_mock_store()
        store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

        tool = CourseSearchTool(store)
        tool.execute(query="some query", course_name="Advanced Python")

        store.search.assert_called_once_with(
            query="some query",
            course_name="Advanced Python",
            lesson_number=None,
        )

    def test_lesson_number_forwarded_to_store_search(self):
        store = make_mock_store()
        store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

        tool = CourseSearchTool(store)
        tool.execute(query="loops", lesson_number=2)

        store.search.assert_called_once_with(
            query="loops",
            course_name=None,
            lesson_number=2,
        )

    def test_both_filters_forwarded_together(self):
        store = make_mock_store()
        store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

        tool = CourseSearchTool(store)
        tool.execute(query="decorators", course_name="Advanced Python", lesson_number=4)

        store.search.assert_called_once_with(
            query="decorators",
            course_name="Advanced Python",
            lesson_number=4,
        )


class TestCourseSearchToolLastSources(unittest.TestCase):
    """Verify: last_sources is correctly populated (or not) after execute()."""

    def test_last_sources_populated_after_successful_search(self):
        store = make_mock_store()
        store.search.return_value = SearchResults(
            documents=["Content A", "Content B"],
            metadata=[
                {"course_title": "Course X", "lesson_number": 1},
                {"course_title": "Course X", "lesson_number": 2},
            ],
            distances=[0.1, 0.2],
        )
        store.get_lesson_link.side_effect = lambda title, num: f"https://x.com/{num}"

        tool = CourseSearchTool(store)
        tool.execute(query="something")

        self.assertEqual(len(tool.last_sources), 2)
        self.assertEqual(tool.last_sources[0]["label"], "Course X - Lesson 1")
        self.assertEqual(tool.last_sources[0]["url"], "https://x.com/1")
        self.assertEqual(tool.last_sources[1]["label"], "Course X - Lesson 2")

    def test_last_sources_empty_on_error(self):
        """last_sources is not populated when an error is returned."""
        store = make_mock_store()
        store.search.return_value = SearchResults.empty(
            "Search error: n_results must be a positive integer"
        )

        tool = CourseSearchTool(store)
        tool.execute(query="something")

        self.assertEqual(tool.last_sources, [])

    def test_last_sources_empty_on_empty_results(self):
        """last_sources stays empty when search returns zero documents."""
        store = make_mock_store()
        store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

        tool = CourseSearchTool(store)
        tool.execute(query="something")

        self.assertEqual(tool.last_sources, [])


if __name__ == "__main__":
    unittest.main()
