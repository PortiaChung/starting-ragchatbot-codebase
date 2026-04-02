# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Always use `uv` to manage dependencies and run Python commands — never use `pip` or `python` directly.

**Install dependencies:**
```bash
uv sync
```

**Run the application:**
```bash
# From repo root
./run.sh

# Or manually
cd backend && uv run uvicorn app:app --reload --port 8000
```

The app serves at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

**Environment setup:**
Requires a `.env` file in the repo root with `ANTHROPIC_API_KEY=...` (see `.env.example`).

## Architecture

This is a RAG (Retrieval-Augmented Generation) chatbot that answers questions about course materials. The backend is FastAPI served on a single port that also serves the static frontend.

### Request flow

1. Frontend (`frontend/script.js`) POSTs `{ query, session_id }` to `/api/query`
2. `backend/app.py` delegates to `RAGSystem.query()`
3. `RAGSystem` fetches conversation history from `SessionManager`, then calls `AIGenerator`
4. `AIGenerator` sends the query to Claude with a `search_course_content` tool available
5. If Claude invokes the tool, `ToolManager` executes `CourseSearchTool`, which queries ChromaDB
6. ChromaDB resolves the course name semantically, then returns the top-5 matching content chunks
7. A second Claude call synthesizes the chunks into a final answer
8. Sources and answer are returned up the chain; session history is updated

### Key design decisions

- **Tool-based retrieval**: Claude decides when to search rather than retrieval always being forced. General knowledge questions skip ChromaDB entirely.
- **Two ChromaDB collections**: `course_catalog` stores course-level metadata (title, instructor, links, lessons JSON); `course_content` stores chunked lesson text. Searching always goes through `course_catalog` first to fuzzy-resolve course names before filtering `course_content`.
- **Session history is in-memory**: `SessionManager` stores sessions in a plain dict — no persistence across server restarts. Capped at the last 2 exchanges (`MAX_HISTORY=2`).
- **Deduplication on load**: On startup, courses already present in ChromaDB (matched by title) are skipped, so restarting the server doesn't re-embed documents.

### Document format

Course files in `docs/` must follow this structure for `DocumentProcessor` to parse them correctly:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 1: <title>
Lesson Link: <url>
<content...>

Lesson 2: <title>
...
```

Supported file types: `.txt`, `.pdf`, `.docx`. Chunks are 800 chars with 100-char sentence-aware overlap.

### Adding a new tool

1. Subclass `Tool` (abstract base in `backend/search_tools.py`) and implement `get_tool_definition()` and `execute()`
2. Register it with `ToolManager.register_tool()` in `RAGSystem.__init__()`

The tool definition must conform to the Anthropic tool-use schema. Claude will automatically decide when to invoke it based on the description.
