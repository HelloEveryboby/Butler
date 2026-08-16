# -*- coding: utf-8 -*-
"""
Butler AI Memory MCP (Model Context Protocol) Server
符合 MCP 规范 (JSON-RPC 2.0)，为 Claude Code、Cursor 等客户端提供标准化的 AI 记忆读写接口。
"""

import sys
import json
import logging
from typing import Dict, Any, Optional

from skills.ai_memory.memory_service import MemoryService
from skills.ai_memory.data_model import MemoryDocument

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mcp_memory_server")


class MCPMemoryServer:
    """
    MCP (Model Context Protocol) JSON-RPC 2.0 服务器
    """
    def __init__(self, project_root: Optional[str] = None):
        self.service = MemoryService(project_root=project_root)

    def get_tool_definitions(self) -> list:
        return [
            {
                "name": "search_memory",
                "description": "通过 RRF 倒数排名融合算法（混合 SQLite FTS5 与 Zvec 向量检索）搜索 AI 历史记忆",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词或语义问题"},
                        "limit": {"type": "integer", "description": "返回结果最大条目数 (默认 5)", "default": 5}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "save_memory",
                "description": "保存一条新的 AI 记忆文档 (包含 YAML FrontMatter 与 Markdown 正文)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "记忆标题"},
                        "content": {"type": "string", "description": "Markdown 详细正文"},
                        "session_summary": {"type": "string", "description": "会话核心摘要"},
                        "decisions": {"type": "array", "items": {"type": "string"}, "description": "决议事项列表"},
                        "open_questions": {"type": "array", "items": {"type": "string"}, "description": "待决/遗留问题列表"},
                        "project": {"type": "string", "description": "项目标识 (默认为当前项目)"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表"}
                    },
                    "required": ["title", "content"]
                }
            },
            {
                "name": "create_handoff",
                "description": "生成当前会话的交接/接棒文档 (用于无缝切换 AI 助手或新会话)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string", "description": "项目名称"},
                        "session_summary": {"type": "string", "description": "本次会话主要工作与进展摘要"},
                        "decisions": {"type": "array", "items": {"type": "string"}, "description": "本次会话达成的技术架构与设计决议"},
                        "open_questions": {"type": "array", "items": {"type": "string"}, "description": "下一个 AI 接棒需要关注的未决问题/待办"},
                        "title": {"type": "string", "description": "交接文档标题 (可选)"}
                    },
                    "required": ["project_name", "session_summary"]
                }
            },
            {
                "name": "get_latest_handoff",
                "description": "查询获取最新一次的 AI 待办交接信息 (SessionStart 时自动恢复上下文)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string", "description": "项目名称 (可选)"}
                    }
                }
            },
            {
                "name": "index_file",
                "description": "对指定的外部 Markdown 记忆文件建立全文与向量索引",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Markdown 文件路径"}
                    },
                    "required": ["file_path"]
                }
            }
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """执行具体的 MCP Tool 并返回文本结果"""
        if tool_name == "search_memory":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 5)
            results = self.service.hybrid_search(query, limit=limit)
            return json.dumps(results, ensure_ascii=False, indent=2)

        elif tool_name == "save_memory":
            doc = MemoryDocument(
                title=arguments.get("title", "Untitled Memory"),
                content=arguments.get("content", ""),
                session_summary=arguments.get("session_summary", ""),
                decisions=arguments.get("decisions", []),
                open_questions=arguments.get("open_questions", []),
                project=arguments.get("project", "default"),
                tags=arguments.get("tags", ["ai-memory"])
            )
            saved_path = self.service.save_memory(doc)
            return json.dumps({"status": "success", "file_path": saved_path, "doc_id": doc.doc_id}, ensure_ascii=False)

        elif tool_name == "create_handoff":
            p_name = arguments.get("project_name", "default")
            summary = arguments.get("session_summary", "")
            decisions = arguments.get("decisions", [])
            questions = arguments.get("open_questions", [])
            title = arguments.get("title", "Session Handoff")
            doc = self.service.create_handoff(p_name, summary, decisions, questions, title=title)
            return json.dumps({"status": "success", "file_path": doc.file_path, "handoff_id": doc.doc_id}, ensure_ascii=False)

        elif tool_name == "get_latest_handoff":
            p_name = arguments.get("project_name")
            res = self.service.get_latest_handoff(project_name=p_name)
            if not res:
                return json.dumps({"status": "not_found", "message": "未找到任何交接记录"}, ensure_ascii=False)
            return json.dumps({"status": "success", "handoff": res}, ensure_ascii=False)

        elif tool_name == "index_file":
            fp = arguments.get("file_path", "")
            doc = self.service.index_file(fp)
            if not doc:
                return json.dumps({"status": "error", "message": f"文件不存在: {fp}"}, ensure_ascii=False)
            return json.dumps({"status": "success", "doc_id": doc.doc_id, "title": doc.title}, ensure_ascii=False)

        else:
            raise ValueError(f"未知工具: {tool_name}")

    def handle_rpc_message(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理符合 JSON-RPC 2.0 规范的请求"""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "butler-ai-memory", "version": "1.0.0"}
                }
            }

        elif method == "notifications/initialized":
            return None

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.get_tool_definitions()}
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                text_result = self.execute_tool(tool_name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": text_result}]
                    }
                }
            except Exception as e:
                logger.error(f"执行工具 '{tool_name}' 抛出异常: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                }

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        else:
            if req_id is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
            return None

    def run_stdio_loop(self):
        """标准 stdio JSON-RPC 事件循环"""
        logger.info("Butler AI Memory MCP Server 启动 (STDIO 模式)...")
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                line_str = line.strip()
                if not line_str:
                    continue

                # 处理可能的前缀 headers (例如 Content-Length)
                if line_str.startswith("Content-Length:"):
                    length = int(line_str.split(":")[1].strip())
                    sys.stdin.readline() # blank line
                    body = sys.stdin.read(length)
                    request = json.loads(body)
                else:
                    request = json.loads(line_str)

                response = self.handle_rpc_message(request)
                if response:
                    out_json = json.dumps(response, ensure_ascii=False)
                    sys.stdout.write(out_json + "\n")
                    sys.stdout.flush()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"STDIO 循环解析错误: {e}")


if __name__ == "__main__":
    server = MCPMemoryServer()
    server.run_stdio_loop()
