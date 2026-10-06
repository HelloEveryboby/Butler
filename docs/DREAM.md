# Dream：递归自我改进引擎（做梦 × 发现历史回放）

> 论文：《Dream-RSI: Recursive Self-Improvement through Evolving Worlds》
> Tong Zheng et al. — Google / University of Maryland / Google DeepMind / UVA
> 本模块是该论文在 Butler 上的工程实现：`butler/core/dream/`

## 1. 论文核心思想

递归自我改进（RSI）的瓶颈不在发现本身，而在**探索策略的管理**：
固定策略无法随搜索空间规模适应；在线优化策略又面临巨大的元搜索空间、
延迟且昂贵的反馈。Dream 的关键洞察：

**累积的发现历史 = 已实现搜索空间的回放模拟器（replay simulator）。**

一次昂贵的在线探索会留下结构化的**发现树**（每个节点 = 一次尝试的完整结果）。
在这些树上"做梦"——回放成千上万个替代探索策略——只需要**揭示已录结果**，
零执行成本、即时反馈。改进后的策略再部署回在线探索，持续扩张模拟器池，
形成自我强化闭环。论文在算法工程、数学优化、GPU kernel 工程上取得
相当或更优的发现质量，同时大幅降低发现成本。

## 2. 论文 ↔ 实现映射

| 论文概念 | Butler 实现 | 说明 |
|---|---|---|
| Discovery tree（节点=尝试+工作区+得分） | `discovery_tree.py` `Node`/`DiscoveryTree` | 根=初始工作区；`add_child` = 一次 CONTINUE 落账 |
| 发现历史 H_t = (T₁,…,T_t) | `discovery_tree.py` `DiscoveryForest` | 持久化于 `data/dream/forest.json` |
| 原子操作 CONTINUE(v) | `orchestrator.py` `online_rollout` + `attempt_fn` 插件口 | 恢复父工作区→生成→评估一个子节点 |
| 可继续集合 A(T;W)、批次 C、W 并行 | `policy.py` `select_batch(view, W, k)` | {根}∪{叶子}，\|C\|≤W，C=∅ 终止 |
| Replay simulator（确定性揭示） | `replay.py` `ReplayView` / `replay_policy` | 策略只见已揭示子树；Child(v;T) 确定性揭示 |
| 回放目标 V（公式 1） | `replay.py` `V = max s − β1·N + β2·N/max{1,k★}` | 质量 − 执行代价 + 并行度奖励 |
| 做梦：M 版修订 + argmax 选择 | `dreamer.py` `Dreamer.dream` | 候选含当前策略 → **保证不退化** |
| policy-development agent | `dreamer.py` `LLMDeveloper` / `ParametricDeveloper` | LLM 修订策略参数；无 LLM 参数化进化兜底 |
| 外层循环（在线 ⟲ 离线） | `orchestrator.py` `DreamOrchestrator.run` | rollout → 入史 → 做梦 → 重部署 |
| 初始策略 Parallel Refine | `policy.py` `ParallelRefinePolicy` | 多工作区并行细化（论文基线初始策略） |

## 3. 架构

```
            ┌─────────────── 外层迭代 t ───────────────┐
            │                                          │
   π_t ──▶ 在线 rollout（≤K1 轮, W 并行）──▶ 发现树 T_t │
            │        attempt_fn(工作区)→得分            │
            │                 │                        │
            │                 ▼                        │
            │          历史 H_t = (T₁…T_t)             │
            │                 │                        │
            │                 ▼                        │
   π_{t+1} ◀── argmax 选择 ◀── 做梦：M 版策略回放评估/修订
             （含当前策略→不退化）    （零执行成本，揭示已录结果）
```

## 4. 使用

```python
from butler.core.dream.butler_adapter import build_orchestrator, SkillAttemptAdapter

# discovery agent 插件口：生成候选 + 执行 + 评分（接 skill_manager / verification）
adapter = SkillAttemptAdapter(generate=gen, execute=run, score_of=score)
orch = build_orchestrator(adapter.attempt)

# 外层循环：在线探索 ⟲ 做梦（每轮后自动做梦并重部署策略）
summary = orch.run(rounds=5, root_workspace={"task": "..."})
```

- 配置：`config/config.yaml` → `dream:` 段（K1/W/K2/M/β1/β2/dream_every）。
- 做梦引擎集成：`DreamEngine.dream()`（`butler/core/dream_engine.py`）在记忆整合后
  自动执行 RSI 做梦阶段（`dream.enabled` 控制）。
- 技能入口：`skills/dream/`（状态查询 / 手动触发做梦 / 策略参数管理）。

## 5. 设计红线（论文实证结论）

1. **只修订探索策略**：discovery agent、evaluator、执行接口固定不变（论文 §3）。
   这是自我改进不失控的边界。
2. **历史当回放模拟器用，不当提示词用**：论文 §5.1 实证——把历史蒸馏成
   语义方向性引导注入提示词，在长时程发现中会**过度约束搜索空间、损害多样性**，
   一致地劣于不做引导的版本。因此本实现的反馈以"轨迹+分数"结构化形式
   交给策略开发 agent，不做语义总结式注入。
3. **单调不退化**：策略选择的候选集包含当前策略（π⁰_t = π_t），
   重部署策略在固定历史上的平均回放分满足 V_{t+1} ≥ V_t。

## 6. 与 Butler 现有能力的关系

| Butler 模块 | 关系 |
|---|---|
| `dream_engine.py`（做梦引擎） | 原有"记忆整合"不变；RSI 做梦是新增第二阶段（策略自改进） |
| `self_healing.py`（自愈） | 自愈处理异常恢复；Dream 处理"如何更好地探索解法" |
| `skill_manager` / `skills/` | discovery agent 的执行载体（通过 `SkillAttemptAdapter` 接入） |
| `verification/` | evaluator 的天然落点（任务评分/验收） |
| `time_machine.py` | 发现树可视为结构化的执行轨迹，与时光机互补 |
| BHL / hybrid_link | attempt_fn 内部可调用 hybrid_* 高性能模块 |
