import sys
import os

# Add the backend directory to sys.path so imports like
# "from search_tools import CourseSearchTool" work from any working directory.
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
