import sys
import os
from typing import List, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Add the backend directory to sys.path so imports like
# "from search_tools import CourseSearchTool" work from any working directory.
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


# ---------------------------------------------------------------------------
# Pydantic models mirroring app.py (kept here so test_api_endpoints.py can
# import them without triggering the static-files mount in the real app).
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class SourceItem(BaseModel):
    label: str
    url: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceItem]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rag():
    """Pre-configured MagicMock standing in for RAGSystem."""
    rag = MagicMock()
    rag.session_manager.create_session.return_value = "test-session-id"
    rag.query.return_value = (
        "Test answer",
        [{"label": "Course A - Lesson 1", "url": "https://example.com/lesson/1"}],
    )
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    return rag


@pytest.fixture
def api_client(mock_rag):
    """TestClient backed by a minimal FastAPI app that mirrors the real API.

    Defining the app inline avoids importing backend/app.py, which mounts
    static files from ``../frontend`` — a path that doesn't exist in the
    test environment.
    """
    test_app = FastAPI()

    @test_app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag.session_manager.create_session()
            answer, sources = mock_rag.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @test_app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        mock_rag.session_manager.clear_session(session_id)
        return {"status": "cleared"}

    @test_app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return TestClient(test_app)
