from package.core_utils.hybrid_memory_manager import hybrid_memory_manager
from package.core_utils.log_manager import LogManager


class MemoryTools:
    """
    Implements memory search and retrieval tools for the AI agent.
    """

    def __init__(self):
        self._logger = LogManager.get_logger(__name__)

    def memory_search(self, query: str, max_results: int = 5) -> str:
        """
        Performs a semantic/keyword search over indexed memory snippets.
        """
        results = hybrid_memory_manager.search(query, max_results)
        if not results:
            return "No matching memories found."

        output = f"Memory Search Results for '{query}':\n\n"
        for i, res in enumerate(results):
            output += f"--- Result {i + 1} ---\n"
            output += f"Path: {res['path']}\n"
            output += f"Lines: {res['line_start']} - {res['line_end']}\n"
            output += f"Snippet: {res['content'][:500]}...\n\n"

        return output

    def memory_get(self, path: str, line_start: int = 1, num_lines: int = -1) -> str:
        """
        Retrieves targeted content from a specific memory Markdown file.
        """
        # Ensure the path is within the memory root for security
        if ".." in path or path.startswith("/"):
            return "Error: Invalid path. Path must be relative to the memory root and not contain '..'."

        content = hybrid_memory_manager.get_file_content(path, line_start, num_lines)
        if not content:
            return f"No content found in memory file: {path}."

        return f"Content of {path} (Lines {line_start} to {line_start + num_lines if num_lines > 0 else 'end'}):\n\n{content}"

    def memory_record(self, content: str, type: str = "daily") -> str:
        """
        Records a new memory. Type can be 'daily' or 'long-term'.
        """
        if type == "long-term":
            hybrid_memory_manager.add_long_term_memory(content)
            return "Recorded in long-term memory (MEMORY.md)."
        else:
            hybrid_memory_manager.add_daily_log(content)
            return "Recorded in daily log (memory/YYYY-MM-DD.md)."


# Global instance for tool registration
memory_tools = MemoryTools()
