# AI Memory Service (AI 记忆服务)

基于 `ai-memory` 架构思想的本地 AI 记忆系统：
- **事实来源 (Source of Truth)**：Markdown 文件 (`.butler-memory/YYYY-MM-DD-标题.md` 与 FrontMatter 元数据)。
- **索引层 (Index Layer)**：SQLite FTS5 全文检索 + Zvec 嵌入式向量语义搜索。
- **混合检索 (Hybrid Search)**：RRF (Reciprocal Rank Fusion) 倒数排名融合算法，无缝支持降级。
- **协议与接口 (MCP Server)**：符合 MCP (Model Context Protocol JSON-RPC 2.0) 标准，可被 Claude Code、Cursor、Butler 外部客户端直接调用。

---

## 核心接口 (Actions)

1. `search`: 混合检索记忆 (`query`, `limit`)
2. `save`: 保存新记忆 (`title`, `content`, `session_summary`, `decisions`, `open_questions`, `project`, `tags`)
3. `create_handoff`: 创建交接/接棒文档 (`project_name`, `session_summary`, `decisions`, `open_questions`)
4. `get_latest_handoff`: 获取最近一次交接文档 (`project_name`)
5. `index_file`: 对外部 Markdown 建立索引 (`file_path`)
6. `session_start`: 会话开始生命周期 Hook
7. `session_end`: 会话结束生命周期 Hook

---

## MCP 服务器启动

```bash
python -m skills.ai_memory.mcp_server
```

在 Claude Code / Cursor `mcpServers` 配置：

```json
{
  "mcpServers": {
    "butler-ai-memory": {
      "command": "python3",
      "args": ["-m", "skills.ai_memory.mcp_server"]
    }
  }
}
```
