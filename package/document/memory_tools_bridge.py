import os
import sys
import json

# Add project root to sys.path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from package.document.memory_tools import memory_tools


def run(intent=None, entities=None, **kwargs):
    """
    Entry point for memory tools, dispatched from intent_dispatcher.
    """
    if intent in ["memory_search", "内存搜索", "记忆搜索"]:
        query = entities.get("query")
        if query:
            return memory_tools.memory_search(query)
        return "Please provide a search query."

    elif intent in ["memory_get", "记忆读取"]:
        path = entities.get("path")
        line_start = int(entities.get("line_start", 1))
        num_lines = int(entities.get("num_lines", -1))
        if path:
            return memory_tools.memory_get(path, line_start, num_lines)
        return "Please provide a file path."

    elif intent in ["memory_record", "记录记忆", "长期记忆", "每日日志"]:
        content = entities.get("content")
        mem_type = entities.get("type", "daily")
        if content:
            return memory_tools.memory_record(content, mem_type)
        return "Please provide content to record."

    return "Unknown memory operation."


if __name__ == "__main__":
    # For testing
    if len(sys.argv) > 1:
        test_intent = sys.argv[1]
        test_entities = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        print(run(test_intent, test_entities))
