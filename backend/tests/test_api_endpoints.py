"""Tests for the FastAPI API endpoints.

Uses the ``api_client`` and ``mock_rag`` fixtures from conftest.py, which
spin up a minimal FastAPI app that mirrors the real routes without mounting
the ``../frontend`` static files directory.
"""

import pytest


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:
    """Verify request/response handling for POST /api/query."""

    def test_returns_200_with_answer_and_sources(self, api_client, mock_rag):
        mock_rag.query.return_value = (
            "Neural networks are...",
            [{"label": "Deep Learning - Lesson 2", "url": "https://example.com/2"}],
        )
        mock_rag.session_manager.create_session.return_value = "sess-abc"

        response = api_client.post(
            "/api/query",
            json={"query": "What is a neural network?"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "Neural networks are..."
        assert body["session_id"] == "sess-abc"
        assert len(body["sources"]) == 1
        assert body["sources"][0]["label"] == "Deep Learning - Lesson 2"

    def test_creates_session_when_none_provided(self, api_client, mock_rag):
        mock_rag.session_manager.create_session.return_value = "new-session"
        mock_rag.query.return_value = ("answer", [])

        response = api_client.post("/api/query", json={"query": "Hello"})

        assert response.status_code == 200
        assert response.json()["session_id"] == "new-session"
        mock_rag.session_manager.create_session.assert_called_once()

    def test_reuses_provided_session_id(self, api_client, mock_rag):
        mock_rag.query.return_value = ("follow-up answer", [])

        response = api_client.post(
            "/api/query",
            json={"query": "Follow-up question", "session_id": "existing-session"},
        )

        assert response.status_code == 200
        assert response.json()["session_id"] == "existing-session"
        mock_rag.session_manager.create_session.assert_not_called()

    def test_passes_query_text_to_rag_system(self, api_client, mock_rag):
        mock_rag.query.return_value = ("ok", [])

        api_client.post("/api/query", json={"query": "specific question text"})

        call_args = mock_rag.query.call_args
        assert call_args[0][0] == "specific question text"

    def test_returns_500_when_rag_raises(self, api_client, mock_rag):
        mock_rag.query.side_effect = RuntimeError("ChromaDB unavailable")

        response = api_client.post("/api/query", json={"query": "anything"})

        assert response.status_code == 500
        assert "ChromaDB unavailable" in response.json()["detail"]

    def test_missing_query_field_returns_422(self, api_client):
        response = api_client.post("/api/query", json={"session_id": "s1"})
        assert response.status_code == 422

    def test_source_url_can_be_null(self, api_client, mock_rag):
        mock_rag.query.return_value = (
            "answer",
            [{"label": "Course X", "url": None}],
        )
        mock_rag.session_manager.create_session.return_value = "s"

        response = api_client.post("/api/query", json={"query": "q"})

        assert response.status_code == 200
        assert response.json()["sources"][0]["url"] is None

    def test_empty_sources_list_is_valid(self, api_client, mock_rag):
        mock_rag.query.return_value = ("general answer", [])
        mock_rag.session_manager.create_session.return_value = "s"

        response = api_client.post("/api/query", json={"query": "general knowledge?"})

        assert response.status_code == 200
        assert response.json()["sources"] == []


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:
    """Verify request/response handling for GET /api/courses."""

    def test_returns_200_with_course_stats(self, api_client, mock_rag):
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": ["Python 101", "ML Basics", "Web Dev"],
        }

        response = api_client.get("/api/courses")

        assert response.status_code == 200
        body = response.json()
        assert body["total_courses"] == 3
        assert "Python 101" in body["course_titles"]
        assert len(body["course_titles"]) == 3

    def test_returns_empty_list_when_no_courses(self, api_client, mock_rag):
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }

        response = api_client.get("/api/courses")

        assert response.status_code == 200
        body = response.json()
        assert body["total_courses"] == 0
        assert body["course_titles"] == []

    def test_returns_500_when_analytics_raises(self, api_client, mock_rag):
        mock_rag.get_course_analytics.side_effect = Exception("vector store error")

        response = api_client.get("/api/courses")

        assert response.status_code == 500
        assert "vector store error" in response.json()["detail"]

    def test_total_courses_matches_titles_length(self, api_client, mock_rag):
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": ["Course A", "Course B"],
        }

        response = api_client.get("/api/courses")

        body = response.json()
        assert body["total_courses"] == len(body["course_titles"])


# ---------------------------------------------------------------------------
# DELETE /api/session/{session_id}
# ---------------------------------------------------------------------------

class TestDeleteSessionEndpoint:
    """Verify DELETE /api/session/{session_id} delegates to session_manager."""

    def test_returns_200_cleared_status(self, api_client):
        response = api_client.delete("/api/session/my-session")

        assert response.status_code == 200
        assert response.json() == {"status": "cleared"}

    def test_calls_clear_session_with_correct_id(self, api_client, mock_rag):
        api_client.delete("/api/session/target-session")

        mock_rag.session_manager.clear_session.assert_called_once_with("target-session")

    def test_different_session_ids_are_forwarded(self, api_client, mock_rag):
        api_client.delete("/api/session/session-123")
        api_client.delete("/api/session/session-456")

        calls = [c[0][0] for c in mock_rag.session_manager.clear_session.call_args_list]
        assert "session-123" in calls
        assert "session-456" in calls
