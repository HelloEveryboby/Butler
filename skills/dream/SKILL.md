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
- **网格规划（GridPlan）**：每个在线 rollout 前由 `plan_grid` 显式决定
  "开几条分支 × 每条分支细化几次"，只读上一轮之前的统计。
- **做梦（Dreaming）**：固定历史上评估 M 个策略版本并逐版修订（LLM 或参数化进化），
  取 argmax（含当前策略 → 评估分**保证不退化**）。
- **回放目标**：`V = 最佳得分 − β1·尝试数 + β2·尝试数/轮数`（质量-代价-并行度）；
  附录 B.2 另记 `AUC`、并行惩罚与 `pareto = AUC − λ·并行惩罚`。
- **beta 调度**：单次回放内 beta 固定；高 beta=更宽/更深/更弱剪枝，
  低 beta=更少 probe、更早停滞停止。
- **失败分类**：编译/形状/正确性等实现层失败可修复；环境/依赖/资源/权限
  等硬失败才剪枝，单次失败不会永久饿死分支。

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
| `dream_admin.status()` | 历史规模、最佳得分、已部署策略与运行参数 |
| `dream_admin.trigger_dream()` | 手动触发一次做梦，并写回 `policy.json` |
| `dream_admin.get_policy()` | 查看当前探索策略及参数语义 |
| `dream_admin.set_params(...)` | 调整并持久化策略参数（beta / branch_count / refine_count / explore_weight / refine_bias / batch_fill / stop_threshold） |
| `dream_admin.sweep_beta()` | 在固定历史上扫描 beta，返回 Pareto 前沿 |
| `dream_admin.plan_preview()` | 预览下一轮在线网格（分支数 × 细化数） |

## 设计红线（论文 §3 / §5.1）

1. **只修订探索策略**：discovery agent、evaluator、执行接口固定，防止自我改进回路失控。
2. **历史当回放用，不当提示词用**：实证表明把历史蒸馏成语义引导注入提示词会
   过度约束搜索、损害多样性探索（论文 Figure 5）。
3. **单调不退化**：策略选择包含当前策略版本，重部署的策略在固定历史上的分数不会更差。
4. **重部署持久化**：做梦选出的策略写入 `data/dream/policy.json`，
   下个进程/下一轮继续使用，而不是每次从默认参数重来。
