"""
Dream 核心机制测试（对应论文 §3）。

覆盖：发现树结构与持久化、回放目标（公式 1）数值正确性、
回放终止规则、回放确定性、做梦选择的单调不退化、
编排器在线⟲做梦端到端闭环、参数化策略修订的合法域。
"""

import math

import pytest

from butler.core.dream import (
    AdaptivePolicy,
    DiscoveryForest,
    DiscoveryTree,
    Dreamer,
    DreamOrchestrator,
    ExplorationPolicy,
    GridPlan,
    GridPlanningContext,
    ParallelRefinePolicy,
    ParametricDeveloper,
    ReplayView,
    DreamConfig,
    policy_from_dict,
    replay_policy,
)
from butler.core.dream import signals
from butler.core.dream.discovery_tree import Node
from butler.core.dream.orchestrator import AttemptResult


# ─────────────────────────────────────────────
# 测试辅助
# ─────────────────────────────────────────────

class DepthFirstPolicy(ExplorationPolicy):
    """测试脚本策略：优先续细化最深链尾，否则由根开新分支。"""

    name = "depth_first"

    def select_batch(self, view, W, round_idx):
        leaves = [v for v in view.eligible() if v != view.root_id]
        if leaves:
            leaves.sort(key=lambda v: view.node(v).depth, reverse=True)
            return leaves[:W]
        return [view.root_id] if view.root_id in view.eligible() else []


def build_chain_tree():
    """构造手工树：root → A(1.0) → A1(1.5) → A2(2.5)，另有 root → B(2.0)。"""
    tree = DiscoveryTree(tree_id="t-hand")
    a = tree.add_child("root", {"x": 0.1}, score=1.0)
    a1 = tree.add_child(a.id, {"x": 0.2}, score=1.5)
    tree.add_child(a1.id, {"x": 0.3}, score=2.5)
    tree.add_child("root", {"x": 0.9}, score=2.0)
    return tree


class RngAttempt:
    """合成域的 discovery agent：f(x) = 1 − (x − 0.7)²，扰动细化。"""

    def __init__(self, seed=0, noise=0.15):
        import random
        self.rng = random.Random(seed)
        self.noise = noise

    def __call__(self, parent_ws):
        x = parent_ws.get("x", 0.0)
        x = max(0.0, min(1.0, x + self.rng.gauss(0.0, self.noise)))
        score = 1.0 - (x - 0.7) ** 2
        return AttemptResult(workspace={"x": x}, score=score,
                             artifact=x, diagnostics={"noise": self.noise})


# ─────────────────────────────────────────────
# 发现树
# ─────────────────────────────────────────────

class TestDiscoveryTree:
    def test_eligible_is_root_plus_leaves(self):
        tree = build_chain_tree()
        eligible = tree.eligible_nodes()
        assert "root" in eligible
        # A 有子节点 A1 → 不可继续；叶子是 A2 与 B
        assert set(eligible) == {"root", tree.nodes["root"].children[0] and
                                 next(n.id for n in tree.nodes.values()
                                      if n.score == 2.5),
                                 next(n.id for n in tree.nodes.values()
                                      if n.score == 2.0)}

    def test_child_of_unique_and_none(self):
        tree = build_chain_tree()
        a = tree.nodes["root"].children[0]
        assert tree.child_of(a) is not None
        leaf = next(n for n in tree.nodes.values() if n.score == 2.5)
        assert tree.child_of(leaf.id) is None
        assert tree.child_of("missing") is None

    def test_best_score_excludes_root(self):
        tree = DiscoveryTree()
        assert tree.best_score() is None
        tree.add_child("root", {}, score=1.0)
        tree.add_child("root", {}, score=3.0)
        assert tree.best_score() == 3.0

    def test_forest_persistence_roundtrip(self, tmp_path):
        forest = DiscoveryForest([build_chain_tree()])
        path = tmp_path / "forest.json"
        forest.save(path)
        loaded = DiscoveryForest.load(path)
        assert len(loaded) == 1
        assert loaded.trees[0].best_score() == 2.5
        assert len(loaded.trees[0].nodes) == len(forest.trees[0].nodes)


# ─────────────────────────────────────────────
# 回放模拟器
# ─────────────────────────────────────────────

class TestReplay:
    def test_objective_formula(self):
        """手工验证公式 1：V = max s − β1·N + β2·N/max{1,k★}。"""
        tree = build_chain_tree()
        # DepthFirst 策略依次揭示 A、A1、A2（N=3），第 4 轮无已录延续终止（k★=4）
        result = replay_policy(DepthFirstPolicy(), tree, W=1, K2=10,
                               beta1=0.1, beta2=0.1)
        assert result.n_attempts == 3
        assert result.rounds == 4
        assert result.max_score == 2.5
        expected = 2.5 - 0.1 * 3 + 0.1 * 3 / 4
        assert math.isclose(result.value, expected, rel_tol=1e-9)

    def test_termination_on_empty_batch(self):
        tree = DiscoveryTree()
        tree.add_child("root", {"x": 0.5}, score=2.0)  # 首个揭示结果即达标
        policy = AdaptivePolicy(stop_threshold=1.5)
        result = replay_policy(policy, tree, W=2, K2=10)
        assert result.rounds == 1       # 第 1 轮揭示后，第 2 轮选空批次 → 终止
        assert result.n_attempts == 1

    def test_termination_when_no_recorded_continuation(self):
        tree = DiscoveryTree()
        tree.add_child("root", {"x": 0.5}, score=1.0)  # 单节点分支，无更深延续
        result = replay_policy(DepthFirstPolicy(), tree, W=1, K2=10)
        # 第 1 轮揭示该子节点；第 2 轮选中链尾但无已录子节点 → 终止
        assert result.n_attempts == 1
        assert result.rounds == 2

    def test_replay_is_deterministic(self):
        tree = build_chain_tree()
        r1 = replay_policy(AdaptivePolicy(seed=7), tree, W=2, K2=10)
        r2 = replay_policy(AdaptivePolicy(seed=7), tree, W=2, K2=10)
        assert r1.value == r2.value
        assert r1.revealed_ids == r2.revealed_ids

    def test_reveal_root_branches_sequentially(self):
        """根的多个分支（开新枝）必须逐个可揭示（回归：child_of 只看首个子节点）。"""
        tree = DiscoveryTree()
        for s in (1.0, 2.0, 3.0):
            tree.add_child("root", {"x": s}, score=s)

        class RootOnly(ExplorationPolicy):
            name = "root_only"

            def select_batch(self, view, W, round_idx):
                return [view.root_id] if view.root_id in view.eligible() else []

        result = replay_policy(RootOnly(), tree, W=1, K2=10)
        assert result.n_attempts == 3          # 三个分支全部揭示
        assert result.max_score == 3.0
        assert result.rounds == 4              # 4 轮：3 次揭示 + 1 次无延续终止

    def test_policy_cannot_see_unrevealed_nodes(self):
        tree = build_chain_tree()
        seen = {}

        class Spy(DepthFirstPolicy):
            def select_batch(self, view, W, round_idx):
                seen[round_idx] = set(view.revealed_ids())
                return super().select_batch(view, W, round_idx)

        replay_policy(Spy(), tree, W=1, K2=10)
        assert seen[0] == {"root"}          # 初始只见根
        assert seen[1] == {"root", *seen[1] - {"root"}}  # 视图单调扩张
        assert all(len(seen[k]) <= len(tree.nodes) for k in seen)

    def test_view_hides_unrevealed_child_ids(self):
        """策略不能通过 Node.children 偷看未揭示节点 id。"""
        tree = build_chain_tree()
        seen = {}

        class Spy(DepthFirstPolicy):
            def select_batch(self, view, W, round_idx):
                seen[round_idx] = list(view.node(view.root_id).children)
                return super().select_batch(view, W, round_idx)

        replay_policy(Spy(), tree, W=1, K2=10)
        assert seen[0] == []                # 根的两个分支均未揭示
        assert all(cid in tree.nodes for ids in seen.values() for cid in ids)


# ─────────────────────────────────────────────
# 做梦（策略修订与选择）
# ─────────────────────────────────────────────

class TestDreamer:
    def _forest(self):
        f = DiscoveryForest()
        for seed in (1, 2, 3):
            orch = DreamOrchestrator(RngAttempt(seed=seed),
                                        DepthFirstPolicy(),
                                        DreamConfig(K1=6, W=2, seed=seed))
            f.append(orch.online_rollout(root_workspace={"x": 0.0}))
        return f

    def test_selection_is_monotonic(self):
        """候选含当前策略 → best_value ≥ baseline_value（论文保证）。"""
        forest = self._forest()
        dreamer = Dreamer(forest, W=2, K2=8, M=4,
                          developer=ParametricDeveloper(seed=0))
        report = dreamer.dream(AdaptivePolicy(seed=3))
        assert report.best_value >= report.baseline_value - 1e-9
        assert len(report.evaluations) == 4
        assert report.trees_used == 3
        assert report.revisions_made == 3
        assert report.summary()["best_policy"]["name"] == "adaptive"

    def test_parametric_developer_stays_in_domain(self):
        dev = ParametricDeveloper(seed=0, step_scale=1.0)
        for _ in range(20):
            new = dev.revise(AdaptivePolicy(seed=1), "feedback", 0)
            p = new.get_params()
            assert 0.0 <= p["explore_weight"] <= 1.0
            assert -1.0 <= p["refine_bias"] <= 1.0
            assert 0.1 <= p["batch_fill"] <= 1.0

    def test_dream_on_empty_history_raises(self):
        with pytest.raises(RuntimeError):
            Dreamer(DiscoveryForest(), M=2).dream(AdaptivePolicy())


# ─────────────────────────────────────────────
# 编排器：在线探索 ⟲ 做梦
# ─────────────────────────────────────────────

class TestOrchestrator:
    def test_end_to_end_loop(self):
        orch = DreamOrchestrator(
            RngAttempt(seed=0), AdaptivePolicy(seed=0),
            DreamConfig(K1=5, W=2, K2=5, M=2, dream_every=1))
        summary = orch.run(rounds=3, root_workspace={"x": 0.0})

        assert summary["rounds_done"] == 3
        assert summary["trees"] == 3
        assert summary["attempts"] > 0
        # 每个外层迭代都触发了做梦并重部署
        assert all("dream" in h for h in summary["history"])
        assert orch.last_dream_report is not None
        # 重部署的策略是做梦选出的版本
        assert orch.policy is orch.last_dream_report.best_policy

    def test_budget_limits_attempts(self):
        orch = DreamOrchestrator(RngAttempt(seed=0), DepthFirstPolicy(),
                                    DreamConfig(K1=50, W=4))
        tree = orch.online_rollout(root_workspace={"x": 0.0}, budget=3)
        assert tree.non_root_count() == 3

    def test_parallel_batch_respects_W(self):
        captured = []

        class Capture(ParallelRefinePolicy):
            def select_batch(self, view, W, round_idx):
                batch = super().select_batch(view, W, round_idx)
                captured.append(len(batch))
                return batch

        orch = DreamOrchestrator(RngAttempt(seed=0), Capture(),
                                    DreamConfig(K1=3, W=2))
        orch.online_rollout(root_workspace={"x": 0.0})
        assert all(n <= 2 for n in captured)


# ─────────────────────────────────────────────
# 网格规划 / beta 扫描 / 观察信号（论文附录 B.2）
# ─────────────────────────────────────────────


class TestGridPlanning:
    def _context(self, **over):
        base = dict(fallback_branch_count=4, fallback_refine_count=2,
                    hard_max_branch_count=4, hard_max_refine_count=5)
        base.update(over)
        return GridPlanningContext(**base)

    def test_beta_controls_width_and_depth(self):
        low = AdaptivePolicy(beta=0.2).plan_grid(self._context())
        mid = AdaptivePolicy(beta=0.6).plan_grid(self._context())
        high = AdaptivePolicy(beta=0.9).plan_grid(self._context())
        assert low.branch_count <= mid.branch_count <= high.branch_count
        assert low.refine_count <= mid.refine_count <= high.refine_count

    def test_plan_is_clamped_to_hard_caps(self):
        plan = AdaptivePolicy(beta=1.0).plan_grid(self._context())
        assert plan.branch_count <= 4
        assert plan.refine_count <= 5
        assert "裁剪" in plan.reason

    def test_stalled_history_increases_exploration(self):
        fresh = AdaptivePolicy(beta=0.6).plan_grid(self._context())
        stalled = AdaptivePolicy(beta=0.6).plan_grid(
            self._context(stalled_rounds=3))
        assert stalled.branch_count >= fresh.branch_count
        assert stalled.refine_count >= fresh.refine_count

    def test_explicit_grid_params_are_respected(self):
        policy = AdaptivePolicy(beta=0.6, branch_count=2, refine_count=1)
        plan = policy.plan_grid(self._context())
        assert plan.branch_count == 2
        assert plan.refine_count == 1

    def test_grid_batch_opens_roots_then_refines(self):
        tree = DiscoveryTree()
        policy = AdaptivePolicy(beta=0.6)
        policy.apply_plan(GridPlan(3, 1, "test"))
        view = ReplayView(tree, {"root"})
        batch = policy.select_batch(view, W=2, round_idx=0)
        assert batch == ["root", "root"]

        tree.add_child("root", {"x": 1}, score=1.0)
        tree.add_child("root", {"x": 2}, score=2.0)
        view = ReplayView(tree, set(tree.nodes))
        batch = policy.select_batch(view, W=2, round_idx=1)
        assert "root" in batch            # 还差一条分支
        assert len(batch) == 2
        assert len(set(batch)) == 2       # 根的重复只在开新分支时出现

    def test_hard_failure_branch_is_dropped(self):
        tree = DiscoveryTree()
        a = tree.add_child("root", {"x": 1}, score=None,
                           fail_class="dependency", error="missing lib")
        tree.add_child("root", {"x": 2}, score=2.0)
        policy = AdaptivePolicy(beta=0.6)
        policy.apply_plan(GridPlan(2, 2, "test"))
        view = ReplayView(tree, set(tree.nodes))
        batch = policy.select_batch(view, W=2, round_idx=1)
        assert a.id not in batch
        assert any(v != "root" for v in batch)


class TestReplayMetrics:
    def test_parallel_penalty_full_batch(self):
        tree = DiscoveryTree()
        tree.add_child("root", {"x": 1}, score=1.0)
        tree.add_child("root", {"x": 2}, score=2.0)

        class RootBatch(ExplorationPolicy):
            name = "root_batch"

            def select_batch(self, view, W, round_idx):
                n = min(len(view.eligible()) and 2, W)
                return [view.root_id] * n

        result = replay_policy(RootBatch(), tree, W=2, K2=5)
        assert result.n_attempts == 2
        assert math.isclose(result.parallel_penalty, 0.5, rel_tol=1e-9)

    def test_attainment_auc_rewards_early_ceiling(self):
        tree = DiscoveryTree()
        a = tree.add_child("root", {"x": 1}, score=1.0)
        b = tree.add_child(a.id, {"x": 2}, score=2.0)
        tree.add_child(b.id, {"x": 3}, score=3.0)
        result = replay_policy(DepthFirstPolicy(), tree, W=1, K2=5)
        assert result.n_attempts == 3
        assert math.isclose(result.attainment_auc, 2.0 / 3.0, rel_tol=1e-9)
        assert result.pareto_reward < 1.0

    def test_beta_sweep_returns_frontier(self):
        forest = DiscoveryForest()
        for seed in (1, 2):
            orch = DreamOrchestrator(RngAttempt(seed=seed),
                                     AdaptivePolicy(seed=seed),
                                     DreamConfig(K1=4, W=2, seed=seed))
            forest.append(orch.online_rollout(root_workspace={"x": 0.0}))
        dreamer = Dreamer(forest, W=2, K2=4, M=2,
                          betas=[0.2, 0.6, 0.9])
        sweep = dreamer.sweep_beta(AdaptivePolicy(seed=0))
        assert len(sweep.points) == 3
        assert sweep.best.beta in (0.2, 0.6, 0.9)
        assert all(math.isfinite(p.mean_pareto) for p in sweep.points)


class TestObservationSignals:
    def test_failure_classification(self):
        ok = Node(id="ok", parent_id="root", score=1.0, fail_class="ok")
        repairable = Node(id="r", parent_id="root", fail_class="compile_error",
                          error="syntax")
        hard = Node(id="h", parent_id="root", fail_class="dependency",
                    error="missing")
        assert signals.is_successful_observation(ok)
        assert signals.is_repairable_failure(repairable)
        assert not signals.is_hard_failure(repairable)
        assert signals.is_hard_failure(hard)
        assert not signals.is_repairable_failure(hard)

    def test_successful_anchor_ignores_failures(self):
        nodes = [
            Node(id="a", parent_id="root", score=1.0, fail_class="ok"),
            Node(id="b", parent_id="a", score=9.0, fail_class="compile_error"),
        ]
        assert signals.successful_anchor(nodes) == 1.0

    def test_observation_fields_persist(self, tmp_path):
        tree = DiscoveryTree()
        tree.add_child("root", {"x": 1}, score=0.5,
                       fail_class="runtime_error", error="boom",
                       valid=False, n_valid=0, n_total=3)
        forest = DiscoveryForest([tree])
        path = tmp_path / "forest.json"
        forest.save(path)
        node = DiscoveryForest.load(path).trees[0].nodes[
            tree.nodes["root"].children[0]]
        assert node.fail_class == "runtime_error"
        assert node.error == "boom"
        assert node.valid is False
        assert node.n_valid == 0
        assert node.n_total == 3


class TestPolicyPersistence:
    def test_policy_roundtrip(self):
        policy = AdaptivePolicy(seed=3, beta=0.9, branch_count=2,
                                refine_count=4)
        restored = policy_from_dict(policy.to_dict())
        assert isinstance(restored, AdaptivePolicy)
        assert restored.beta == 0.9
        assert restored.branch_count == 2
        assert restored.refine_count == 4

    def test_old_policy_json_is_accepted(self):
        restored = policy_from_dict(
            {"name": "adaptive", "params": {"seed": 1, "explore_weight": 0.5}})
        assert restored.explore_weight == 0.5

    def test_orchestrator_saves_deployed_policy(self, tmp_path):
        state = tmp_path / "policy.json"
        orch = DreamOrchestrator(
            RngAttempt(seed=0), AdaptivePolicy(seed=0),
            DreamConfig(K1=3, W=2, K2=3, M=1, betas=[]),
            state_path=state)
        orch.run(rounds=1, root_workspace={"x": 0.0})
        assert state.exists()
        restored = policy_from_dict(
            __import__("json").loads(state.read_text(encoding="utf-8")))
        assert restored.name == "adaptive"

    def test_adapter_save_load(self, tmp_path):
        from butler.core.dream import butler_adapter
        settings = {"data_dir": str(tmp_path), "seed": 0, "beta": 0.6}
        policy = AdaptivePolicy(seed=0, beta=0.8, branch_count=3)
        butler_adapter.save_policy(policy, settings)
        loaded = butler_adapter.load_policy(settings)
        assert loaded.beta == 0.8
        assert loaded.branch_count == 3
