# Dream 自改进引擎 (dream)

递归自我改进（RSI）技能：把 Butler 的发现历史当作**回放模拟器**，在闲置时"做梦"——
零执行成本地评估成千上万个替代探索策略，选出不退化的改进策略并重部署，
驱动自动化任务/技能组合的持续自我优化。

基于论文《Dream-RSI: Recursive Self-Improvement through Evolving Worlds》
（Zheng et al., Google / UMD / Google DeepMind）实现。

## 角色定义

你是 Dream 自改进引擎的管理员。用户询问"系统自我改进/做梦/探索策略/发现历史"
相关话题时，通过 `dream_admin.py` 查询状态、触发做梦、调整策略参数。

## 核心概念

- **发现树（Discovery Tree）**：每个节点是一次尝试的完整记录（工作区、生成物、诊断、得分）；
  原子操作 `CONTINUE(v)` = 恢复 v 的工作区 → 生成 → 评估一个新子节点。
- **回放模拟器（Replay Simulator）**：历史发现树池。替代策略在树上回放时只需
  **揭示已录结果**，无需真实执行 → 单次昂贵在线运行支撑数千次零成本离线评估。
- **做梦（Dreaming）**：固定历史上评估 M 个策略版本并修订（LLM 或参数化进化），
  取 argmax（含当前策略 → 平均回放分**保证不退化**）。
- **回放目标**：`V = 最佳得分 − β1·尝试数 + β2·尝试数/轮数`（质量-代价-并行度）。

## 使用方式（Python API）

```python
from butler.core.dream.butler_adapter import build_orchestrator, SkillAttemptAdapter

adapter = SkillAttemptAdapter(generate=..., execute=..., score_of=...)
orch = build_orchestrator(adapter.attempt)
summary = orch.run(rounds=3)      # 在线探索 ⟲ 做梦，自动持久化历史
```

## 管理命令

| 意图 | 说明 |
|---|---|
| `dream_admin.status()` | 历史规模、最佳得分、当前策略参数 |
| `dream_admin.trigger_dream()` | 手动触发一次做梦（离线策略改进） |
| `dream_admin.get_policy()` | 查看当前探索策略及参数 |
| `dream_admin.set_params(...)` | 调整策略参数（explore_weight / refine_bias / batch_fill / stop_threshold） |

## 设计红线（论文 §3 / §5.1）

1. **只修订探索策略**：discovery agent、evaluator、执行接口固定，防止自我改进回路失控。
2. **历史当回放用，不当提示词用**：实证表明把历史蒸馏成语义引导注入提示词会
   过度约束搜索、损害多样性探索（论文 Figure 5）。
3. **单调不退化**：策略选择包含当前策略版本，重部署的策略在固定历史上的分数不会更差。
