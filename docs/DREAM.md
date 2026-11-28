# Dream：递归自我改进引擎（做梦 × 发现历史回放）

> 论文：《Dream-RSI: Recursive Self-Improvement through Evolving Worlds》
> Tong Zheng et al. — Google / University of Maryland / Google DeepMind / UVA
> 本模块是该论文在 Butler 上的工程实现：`butler/core/dream/`
> 当前版本对齐论文正文 §2–§3 与附录 B.2（网格规划、beta 扫描、失败分类）。

## 1. 论文核心思想

递归自我改进（RSI）的瓶颈不在发现本身，而在**探索策略的管理**：
固定策略无法随搜索空间规模适应；在线优化策略又面临巨大的元搜索空间、
延迟且昂贵的反馈。Dream 的关键洞察：

**累积的发现历史 = 已实现搜索空间的回放模拟器（replay simulator）。**

一次昂贵的在线探索会留下结构化的**发现树**（每个节点 = 一次尝试的完整结果）。
在这些树上"做梦"——回放成千上万个替代探索策略——只需要**揭示已录结果**，
零执行成本、即时反馈。改进后的策略再部署回在线探索，持续扩张模拟器池，
形成自我强化闭环。

## 2. 论文 ↔ 实现映射

| 论文概念 | Butler 实现 | 说明 |
|---|---|---|
| Discovery tree（节点=尝试+工作区+得分+观察） | `discovery_tree.py` `Node`/`DiscoveryTree` | 根=初始工作区；`add_child` = 一次 CONTINUE 落账 |
| 发现历史 H_t = (T₁,…,T_t) | `discovery_tree.py` `DiscoveryForest` | 持久化于 `data/dream/forest.json`；每棵树记录本轮网格 |
| 原子操作 CONTINUE(v) | `orchestrator.py` `online_rollout` + `attempt_fn` 插件口 | 恢复父工作区→生成→评估一个子节点；`W` 个 worker 并行 |
| 可继续集合 A(T;W)、批次 C | `policy.py` `select_batch(view, W, k)` | {根}∪{叶子}，\|C\|≤W，C=∅ 终止 |
| Replay simulator（确定性揭示） | `replay.py` `ReplayView` / `replay_policy` | 策略只见已揭示子树；Child(v;T) 确定性揭示 |
| 回放目标 V（公式 1） | `replay.py` `V = max s − β1·N + β2·N/max{1,k★}` | 质量 − 执行代价 + 并行度奖励 |
| 附录 B.2 attainment / parallel penalty / Pareto | `replay.py` `attainment_auc`、`parallel_penalty`、`pareto_reward` | `pareto = AUC − λ·(effective_rounds/N)` |
| Grid planning（分支×细化网格） | `grid.py` `GridPlan`/`GridPlanningContext`；`policy.plan_grid` | 每个在线 rollout 前显式规划；只读上一轮之前的统计 |
| beta 调度 | `policy.py` `AdaptivePolicy.beta`、`plan_grid` | 单次回放内 beta 固定；高 beta=更宽/更深/更弱剪枝 |
| beta 扫描（跨版本评估） | `dreamer.py` `Dreamer.sweep_beta`/`BetaSweep` | 固定 beta 网格回放，按 `objective` 选最优 beta |
| 失败分类 / 修复队列 | `signals.py`、`Node.fail_class` | 可修复失败不永久关闭分支；环境/依赖/资源硬失败才剪枝 |
| 做梦：M 版修订 + argmax 选择 | `dreamer.py` `Dreamer.dream` | 候选含当前策略 → **保证不退化**；修订逐版链式进行 |
| policy-development agent | `dreamer.py` `LLMDeveloper` / `ParametricDeveloper` | LLM 修订策略参数；无 LLM 时参数化进化兜底 |
| 外层循环（在线 ⟲ 离线） | `orchestrator.py` `DreamOrchestrator.run` | rollout → 入史 → 做梦 → 重部署 |
| 重部署持久化 | `butler_adapter.py` `policy.json` | π_{t+1} 落盘，下个进程/下一轮继续使用 |
| 初始策略 Parallel Refine | `policy.py` `ParallelRefinePolicy` | 多工作区并行细化（论文基线初始策略） |

## 3. 架构

```
            ┌──────────────── 外层迭代 t ────────────────┐
            │                                            │
   π_t ──▶ plan_grid（分支数 × 细化数）                │
            │        │                                   │
            │        ▼                                   │
            │  在线 rollout（≤K1 轮，W 并行）──▶ 发现树 T_t
            │        attempt_fn(工作区)→得分/失败分类     │
            │                 │                          │
            │                 ▼                          │
            │          历史 H_t = (T₁…T_t)               │
            │                 │                          │
            │                 ▼                          │
   π_{t+1} ◀── argmax 选择 ◀── 做梦：M 版策略回放评估/修订
             （含当前策略→不退化）    beta 扫描 + 揭示已录结果
             （写回 policy.json）
```

### 3.1 在线阶段

- 先调用 `policy.plan_grid(context)` 得到 `GridPlan(branch_count, refine_count, reason)`；
- 根节点开 `branch_count` 条独立分支（每轮最多 `W` 个并发请求），
  之后每条分支在 `refine_count` 额度内继续细化/修复；
- `AttemptResult` 携带 `evaluated/valid/fail_class/error/n_valid/n_total`，
  落账到 `Node`，供后续回放与失败分类使用；
- 批次通过 `ThreadPoolExecutor` 并行执行，`max_workers=0` 时使用 `W`。

### 3.2 做梦阶段

- 在固定的历史 H_t 上，每个候选策略版本都从根开始、在**每棵树**上回放；
- 若有 `betas`，先对每个版本做 beta 扫描，按 `objective` 选该版本的最优 beta；
- 依次修订 M-1 次（π⁰=π_t → π¹ → …），最后 `argmax` 选择；
- 候选包含当前策略，因此重部署策略在固定历史上的评估分不会更差。

## 4. 使用

```python
from butler.core.dream.butler_adapter import build_orchestrator, SkillAttemptAdapter

# discovery agent 插件口：生成候选 + 执行 + 评分 + 观察信号
adapter = SkillAttemptAdapter(
    generate=gen, execute=run, score_of=score,
    evaluation_of=lambda r: {"fail_class": r.get("fail_class", "ok")},
)
orch = build_orchestrator(adapter.attempt)   # 自动加载 forest.json + policy.json

summary = orch.run(rounds=5, root_workspace={"task": "..."})
```

只做离线做梦（无需在线执行）：

```python
from butler.core.dream import Dreamer
from butler.core.dream import butler_adapter

settings = butler_adapter.load_settings()
forest = butler_adapter.load_forest(settings)
policy = butler_adapter.load_policy(settings)
report = Dreamer(forest, betas=[0.4, 0.6, 0.8]).dream(policy)
butler_adapter.save_policy(report.best_policy, settings)
```

- 配置：`config/config.yaml` → `dream:` 段
  （K1/W/K2/M/β1/β2/beta/betas/lambda_parallel/objective/max_workers/dream_every）。
- 做梦引擎集成：`DreamEngine.dream()` 在记忆整合后自动执行 RSI 做梦阶段，
  并写回 `data/dream/policy.json`。
- 技能入口：`skills/dream/dream_admin.py`（状态 / 手动做梦 / beta 扫描 /
  网格预览 / 策略参数管理）。

## 5. 设计红线（论文实证结论）

1. **只修订探索策略**：discovery agent、evaluator、执行接口固定不变（论文 §3）。
   这是自我改进不失控的边界。
2. **历史当回放模拟器用，不当提示词用**：论文 §5.1 实证——把历史蒸馏成
   语义方向性引导注入提示词，在长时程发现中会**过度约束搜索空间、损害多样性**，
   一致地劣于不做引导的版本。因此本实现的反馈以"轨迹+分数"结构化形式
   交给策略开发 agent，不做语义总结式注入。
3. **单调不退化**：策略选择的候选集包含当前策略（π⁰_t = π_t），
   在选定目标（V 或 Pareto）上重部署策略的评估分不低于当前策略。
4. **规划只用前缀信息**：`plan_grid` 只读历史摘要/结构上限，不读当前
   episode 结果、不写死具体节点 id 或绝对分数目标。

## 6. 与 Butler 现有能力的关系

| Butler 模块 | 关系 |
|---|---|
| `dream_engine.py`（做梦引擎） | 原有"记忆整合"不变；RSI 做梦是第二阶段（策略自改进） |
| `self_healing.py`（自愈） | 自愈处理异常恢复；Dream 处理"如何更好地探索解法" |
| `skill_manager` / `skills/` | discovery agent 的执行载体（通过 `SkillAttemptAdapter` 接入） |
| `verification/` | evaluator 的天然落点（任务评分/验收） |
| `time_machine.py` | 发现树可视为结构化的执行轨迹，与时光机互补 |
| BHL / hybrid_link | attempt_fn 内部可调用 hybrid_* 高性能模块 |

## 7. 已知边界

- `LLMDeveloper` 修订的是**策略参数**（beta/网格/批次倾向），不是任意
  Python 代码；论文的完整 policy-development agent 会直接编辑策略源码。
  Butler 选择参数化是为了可校验、可回放、不引入执行任意代码的风险。
- `plan_grid` 目前作用于"根分支 × 链式细化"这一受限网格；复杂 DAG 工作区
  仍可由自定义 `select_batch` 策略表达。
- 在线 `attempt_fn` 默认并行；若底层 skill 非线程安全，请把
  `dream.max_workers` 设为 1。
