import os
import datetime
from typing import Dict, Any, List
from butler.core.hybrid_link import HybridLinkClient
from package.core_utils.log_manager import LogManager


class HybridMemoryManager:
    """
    Manages the memory system using a Go-based BHL backend for search.
    """

    def __init__(self, memory_root: str = None):
        self._logger = LogManager.get_logger(__name__)
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        if memory_root is None:
            self.memory_root = os.path.join(project_root, "data", "butler_memory")
        else:
            self.memory_root = memory_root

        self.daily_log_dir = os.path.join(self.memory_root, "memory")
        self.long_term_file = os.path.join(self.memory_root, "MEMORY.md")

        os.makedirs(self.daily_log_dir, exist_ok=True)

        # Initialize BHL client
        executable_path = os.path.join(
            project_root, "programs/hybrid_memory/memory_service"
        )
        self._client = HybridLinkClient(
            executable_path=executable_path, fallback_enabled=True
        )
        self._client.start()

    def add_daily_log(self, content: str):
        """Appends content to today's daily log file."""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(self.daily_log_dir, f"{today}.md")

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_content = f"\n### {timestamp}\n{content}\n"

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(formatted_content)
        self._logger.info(f"Added daily log to {file_path}")

    def add_long_term_memory(self, content: str):
        """Adds durable facts or decisions to the long-term MEMORY.md file."""
        with open(self.long_term_file, "a", encoding="utf-8") as f:
            f.write(f"\n- {content}\n")
        self._logger.info(f"Added long-term memory to {self.long_term_file}")

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Searches the memory using the Go BHL module."""
        try:
            result = self._client.call(
                "search",
                {"root": self.memory_root, "query": query, "max_results": max_results},
            )
            return result if result else []
        except Exception as e:
            self._logger.error(f"Memory search failed: {e}")
            return []

    def get_file_content(
        self, relative_path: str, line_start: int = 1, num_lines: int = -1
    ) -> str:
        """Reads a specific memory file's content."""
        full_path = os.path.join(self.memory_root, relative_path)
        if not os.path.exists(full_path):
            return ""

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            start_idx = max(0, line_start - 1)
            if num_lines == -1:
                return "".join(lines[start_idx:])
            else:
                return "".join(lines[start_idx : start_idx + num_lines])
        except Exception as e:
            self._logger.error(f"Failed to read file {full_path}: {e}")
            return ""

    def get_stats(self) -> Dict[str, Any]:
        """Gets memory system statistics."""
        try:
            return self._client.call("get_stats", {"root": self.memory_root})
        except Exception:
            return {"error": "BHL call failed"}


# Global instance
hybrid_memory_manager = HybridMemoryManager()
