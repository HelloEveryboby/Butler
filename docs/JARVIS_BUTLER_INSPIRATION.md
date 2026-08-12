# Butler ✖️ Microsoft JARVIS (HuggingGPT) 融合技术蓝皮书

本设计文档旨在探讨如何将微软开源项目 **JARVIS (HuggingGPT)** 的“大模型大脑 + 领域专家模型/工具”的协同范式，深度融合进 Butler 的 **BHL (Binary Hybrid Link) 混合链路** 与 **One Folder = One Skill** 本地优先（Local-First）架构中。

通过本次融合，Butler 将实现从“基于关键词/强规则触发技能”到“基于语义理解与 4 阶段动态生命周期调度（Task Planning, Model Selection, Task Execution, Response Generation）”的智能升级，实现更具鲁棒性、高观测度、高自愈性的个人 AI 助手。

---

## 一、 核心架构映射与边界设计

为了保持 Butler 主流程的极高稳定性，我们遵循**“不改造核心 Jarvis 结构体，而是引入智能中间件装饰/包装”**的无损嫁接原则。

### 1. 概念对照与映射
| 微软 JARVIS (HuggingGPT) 阶段 | Butler 映射与 BHL 分层设计 | 改造方向与核心增量 |
| :--- | :--- | :--- |
| **Stage 1: Task Planning** | 强化现有的 `Planner` | 让 LLM 解析用户的复合意图，拆解为具有依赖关系（DAG）的子任务列表，而非单步串行指令。 |
| **Stage 2: Model Selection** | 引入 `DynamicSkillRouter` | **核心看点**：动态读取本地 Skill 目录下的 `manifest.json` 与 `SKILL.md`，解析并自动构建 Tool Calling Schema。LLM 根据语义描述“挑出”最合适的 Local Skill 文件夹，实现智能路由。 |
| **Stage 3: Task Execution** | 复用现有的 `Executor` 与 BHL 链路 | 调起 `PackageLoader` / Go-runner 节点或 Python 底层脚本，支持多技能管道级传参，附带失败自动回退（Fallback）到硬编码规则。 |
| **Stage 4: Response Generation** | 增强 `Complete` 与结果聚合 | 将多个 Skill 的原始输出（如 JSON 数据）收集，并使用轻量级 NLU 重新整合成自然语言、Markdown 格式返回。 |

### 2. 架构拓扑图

```text
    +--------------------------------------------------------+
    |                     用户输入 (Command)                 |
    +---------------------------+----------------------------+
                                |
                                v
               +----------------------------------+
               |  HuggingFaceRouter / Middleware  | <--- 装饰器/代理模式
               +----------------+-----------------+
                                |
        +-----------------------+-----------------------+
        |                                               |
        v [语义/动态路由成功]                           v [路由失败/异常]
+-------------------------------+             +-------------------------------+
|     DynamicSkillRouter        |             |  Fallback: 强规则关键词匹配   |
|   (Task Planning & Selection) |             |  (Original Butler Hardcode)   |
+---------------+---------------+             +---------------+---------------+
                |                                             |
                v                                             v
+-------------------------------+                             |
|      One Folder = One Skill   | <---------------------------+
|    (BHL Layer / Local Exec)   |
+---------------+---------------+
                |
                v
+-------------------------------+
|     Response Generation       | ---> Markdown 终端折叠块展示 (4 阶段可视化)
+-------------------------------+
```

---

## 二、 核心机制设计

### 1. 动态技能描述发现（Dynamic Skill Discovery）
每个 Local Skill 包含 `manifest.json` 或 `SKILL.md`。例如：
```json
{
  "name": "pixel_pet",
  "description": "控制桌面像素宠物，支持切换宠物表情、播放粒子动画、修改宠物属性（饱食度、心情值）。",
  "actions": ["set_expression", "spawn_particles"]
}
```
`DynamicSkillRouter` 在系统启动或有新 Skill 加入时，自动扫描所有 `skills/` 文件夹：
- 解析每个 Skill 提供的功能，合并为 LLM Function-Calling 兼容的工具描述（JSON Schema）。
- 运行时，将此 Schema 与上下文一起发送给大模型，避免了传统云端嵌入向量（Embedding & Vector DB）的同步与多余运维开销，精准而轻量。

### 2. 容错兜底机制 (Resilient Fallback)
由于大模型在进行函数调用或意图识别时偶有幻觉：
1. **优先路径**：大模型进行 4 阶段规划和动态路由。
2. **熔断与拦截**：若模型指定的 Skill ID 不存在、参数严重缺失，或者 BHL 链路调用报错（超时/二进制抛错），自动触发 Butler 自愈（Self-Healing）与经典 Hardcoded 正则匹配：
   ```python
   # 伪代码逻辑
   try:
       result = run_dynamic_router(command)
   except Exception as e:
       result = run_legacy_hardcoded_pipeline(command)
   ```
3. 确保任何时候系统均能优雅响应，提供“永不死机”的管家体验。

### 3. 多模态网关接口预留 (Multimodal Gateway Interface)
虽然第一步专注于文本指令的稳定调度，但在架构上预先定义多模态处理器接口：
- `process_image(image_b64)`: 用于“截图即排障”或像素宠物的视觉侦测。
- `process_audio(audio_stream)`: 本地语音引擎（Whisper/Baidu TTS）无缝转化器。
- `route_multimodal(payload)`: 接收包含多种感知模态的统一载荷，分发到对应多模态专家包。

---

## 三、 中间态可视化设计

为了提升用户对 Butler 执行复杂任务时的掌控感与极客体验，我们设计了 **4 阶段 Markdown 渐进式日志展示**：

```markdown
### 🧠 Butler 智能思考与执行链 (Thinking Chain)

<details>
<summary><b>📋 第一阶段：任务规划 (Task Planning)</b></summary>
- 拆解主任务为 2 个子步骤。
- 步骤 1: `collect_system_status` (优先级: 高)
- 步骤 2: `notify_user` (依赖步骤 1)
</details>

<details>
<summary><b>🎯 第二阶段：技能选择 (Model Selection)</b></summary>
- 步骤 1 路由至本地物理包: `sys_cleaner` (匹配度: 94.2%)
- 步骤 2 路由至本地物理包: `pixel_pet` (匹配度: 89.1%)
</details>

<details>
<summary><b>⚙️ 第三阶段：技能执行 (Task Execution)</b></summary>
- [✓] `sys_cleaner` 执行成功。返回: `{"freed_mb": 420}`
- [✓] `pixel_pet` 执行成功。动作: `spawn_particles`
</details>

<details>
<summary><b>✨ 第四阶段：成果整合 (Response Generation)</b></summary>
- **Butler 的最终汇报**:
  > “主人，我刚才已为您清理了 420MB 缓存垃圾，并让小宠物为您撒花庆祝啦！🎉”
</details>
```

这种交互模式通过 PyWebView 前端或 Textual 终端无损渲染，带来流畅的渐进式“全知视角”。

---

## 四、 后续研发规划

1. **第一阶段 (当前)**：编写核心技术蓝皮书与智能路由中间件 `DynamicSkillRouter` 的 POC。
2. **第二阶段**：为该中间件编写完整的单元与端到端测试用例，保障其与 Butler 现存的 `Planner`、`Executor` 的 100% 兼容。
3. **第三阶段**：在 BHL 底层 Go 节点上接入多机热备或并行模型调用优化，提升极致的本地响应体验。
