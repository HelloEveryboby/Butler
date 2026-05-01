#!/usr/bin/env python3
"""运行 评估 + 改进 循环，直到所有测试通过或达到最大迭代次数。

在一个循环中结合 run_eval.py 和 improve_description.py，跟踪历史记录，
并返回发现的最佳描述。支持 训练集/测试集 划分以防止过度拟合。
"""

import argparse
import json
import random
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

from scripts.generate_report import generate_html
from scripts.improve_description import improve_description
from scripts.run_eval import find_project_root, run_eval
from scripts.utils import parse_skill_md


def split_eval_set(eval_set: list[dict], holdout: float, seed: int = 42) -> tuple[list[dict], list[dict]]:
    """将评估集划分为训练集和测试集，按 should_trigger 进行分层抽样。"""
    random.seed(seed)

    # 按 should_trigger 分类
    trigger = [e for e in eval_set if e["should_trigger"]]
    no_trigger = [e for e in eval_set if not e["should_trigger"]]

    # 分别洗牌
    random.shuffle(trigger)
    random.shuffle(no_trigger)

    # 计算切分点
    n_trigger_test = max(1, int(len(trigger) * holdout))
    n_no_trigger_test = max(1, int(len(no_trigger) * holdout))

    # 切分
    test_set = trigger[:n_trigger_test] + no_trigger[:n_no_trigger_test]
    train_set = trigger[n_trigger_test:] + no_trigger[n_no_trigger_test:]

    return train_set, test_set


def run_loop(
    eval_set: list[dict],
    skill_path: Path,
    description_override: str | None,
    num_workers: int,
    timeout: int,
    max_iterations: int,
    runs_per_query: int,
    trigger_threshold: float,
    holdout: float,
    model: str,
    verbose: bool,
    live_report_path: Path | None = None,
    log_dir: Path | None = None,
) -> dict:
    """运行评估 + 改进循环。"""
    project_root = find_project_root()
    name, original_description, content = parse_skill_md(skill_path)
    current_description = description_override or original_description

    # 如果 holdout > 0，则划分为训练集和测试集
    if holdout > 0:
        train_set, test_set = split_eval_set(eval_set, holdout)
        if verbose:
            print(f"切分结果: {len(train_set)} 个训练查询, {len(test_set)} 个测试查询 (留出比例={holdout})", file=sys.stderr)
    else:
        train_set = eval_set
        test_set = []

    history = []
    exit_reason = "unknown"

    for iteration in range(1, max_iterations + 1):
        if verbose:
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"迭代 {iteration}/{max_iterations}", file=sys.stderr)
            print(f"描述: {current_description}", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)

        # 为了提高并行效率，将训练集和测试集放在一个批次中进行评估
        all_queries = train_set + test_set
        t0 = time.time()
        all_results = run_eval(
            eval_set=all_queries,
            skill_name=name,
            description=current_description,
            num_workers=num_workers,
            timeout=timeout,
            project_root=project_root,
            runs_per_query=runs_per_query,
            trigger_threshold=trigger_threshold,
            model=model,
        )
        eval_elapsed = time.time() - t0

        # 通过匹配查询内容将结果重新拆分为训练集和测试集
        train_queries_set = {q["query"] for q in train_set}
        train_result_list = [r for r in all_results["results"] if r["query"] in train_queries_set]
        test_result_list = [r for r in all_results["results"] if r["query"] not in train_queries_set]

        train_passed = sum(1 for r in train_result_list if r["pass"])
        train_total = len(train_result_list)
        train_summary = {"passed": train_passed, "failed": train_total - train_passed, "total": train_total}
        train_results = {"results": train_result_list, "summary": train_summary}

        if test_set:
            test_passed = sum(1 for r in test_result_list if r["pass"])
            test_total = len(test_result_list)
            test_summary = {"passed": test_passed, "failed": test_total - test_passed, "total": test_total}
            test_results = {"results": test_result_list, "summary": test_summary}
        else:
            test_results = None
            test_summary = None

        history.append({
            "iteration": iteration,
            "description": current_description,
            "train_passed": train_summary["passed"],
            "train_failed": train_summary["failed"],
            "train_total": train_summary["total"],
            "train_results": train_results["results"],
            "test_passed": test_summary["passed"] if test_summary else None,
            "test_failed": test_summary["failed"] if test_summary else None,
            "test_total": test_summary["total"] if test_summary else None,
            "test_results": test_results["results"] if test_results else None,
            # 为了与报告生成器向后兼容
            "passed": train_summary["passed"],
            "failed": train_summary["failed"],
            "total": train_summary["total"],
            "results": train_results["results"],
        })

        # 如果提供了路径，则编写实时报告
        if live_report_path:
            partial_output = {
                "original_description": original_description,
                "best_description": current_description,
                "best_score": "进行中",
                "iterations_run": len(history),
                "holdout": holdout,
                "train_size": len(train_set),
                "test_size": len(test_set),
                "history": history,
            }
            live_report_path.write_text(generate_html(partial_output, auto_refresh=True, skill_name=name), encoding="utf-8")

        if verbose:
            def print_eval_stats(label, results, elapsed):
                pos = [r for r in results if r["should_trigger"]]
                neg = [r for r in results if not r["should_trigger"]]
                tp = sum(r["triggers"] for r in pos)
                pos_runs = sum(r["runs"] for r in pos)
                fn = pos_runs - tp
                fp = sum(r["triggers"] for r in neg)
                neg_runs = sum(r["runs"] for r in neg)
                tn = neg_runs - fp
                total = tp + tn + fp + fn
                precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
                accuracy = (tp + tn) / total if total > 0 else 0.0
                print(f"{label}: {tp+tn}/{total} 正确, 精确率={precision:.0%} 召回率={recall:.0%} 准确率={accuracy:.0%} ({elapsed:.1f}s)", file=sys.stderr)
                for r in results:
                    status = "通过" if r["pass"] else "失败"
                    rate_str = f"{r['triggers']}/{r['runs']}"
                    print(f"  [{status}] 触发率={rate_str} 预期={r['should_trigger']}: {r['query'][:60]}", file=sys.stderr)

            print_eval_stats("训练集", train_results["results"], eval_elapsed)
            if test_summary:
                print_eval_stats("测试集 ", test_results["results"], 0)

        if train_summary["failed"] == 0:
            exit_reason = f"all_passed (第 {iteration} 次迭代)"
            if verbose:
                print(f"\n第 {iteration} 次迭代中所有训练查询均通过！", file=sys.stderr)
            break

        if iteration == max_iterations:
            exit_reason = f"max_iterations ({max_iterations})"
            if verbose:
                print(f"\n已达到最大迭代次数 ({max_iterations})。", file=sys.stderr)
            break

        # 根据训练结果改进描述
        if verbose:
            print(f"\n正在改进描述...", file=sys.stderr)

        t0 = time.time()
        # 从历史记录中剔除测试分数，以便改进模型无法看到它们
        blinded_history = [
            {k: v for k, v in h.items() if not k.startswith("test_")}
            for h in history
        ]
        new_description = improve_description(
            skill_name=name,
            skill_content=content,
            current_description=current_description,
            eval_results=train_results,
            history=blinded_history,
            model=model,
            log_dir=log_dir,
            iteration=iteration,
        )
        improve_elapsed = time.time() - t0

        if verbose:
            print(f"提议的新描述 ({improve_elapsed:.1f}s): {new_description}", file=sys.stderr)

        current_description = new_description

    # 找到测试集得分最高的一次迭代（如果没有测试集，则取训练集得分最高的）
    if test_set:
        best = max(history, key=lambda h: h["test_passed"] or 0)
        best_score = f"{best['test_passed']}/{best['test_total']}"
    else:
        best = max(history, key=lambda h: h["train_passed"])
        best_score = f"{best['train_passed']}/{best['train_total']}"

    if verbose:
        print(f"\n退出原因: {exit_reason}", file=sys.stderr)
        print(f"最佳得分: {best_score} (第 {best['iteration']} 次迭代)", file=sys.stderr)

    return {
        "exit_reason": exit_reason,
        "original_description": original_description,
        "best_description": best["description"],
        "best_score": best_score,
        "best_train_score": f"{best['train_passed']}/{best['train_total']}",
        "best_test_score": f"{best['test_passed']}/{best['test_total']}" if test_set else None,
        "final_description": current_description,
        "iterations_run": len(history),
        "holdout": holdout,
        "train_size": len(train_set),
        "test_size": len(test_set),
        "history": history,
    }


def main():
    parser = argparse.ArgumentParser(description="运行 评估 + 改进 循环")
    parser.add_argument("--eval-set", required=True, help="评估集 JSON 文件的路径")
    parser.add_argument("--skill-path", required=True, help="技能目录路径")
    parser.add_argument("--description", default=None, help="覆盖起始描述")
    parser.add_argument("--num-workers", type=int, default=10, help="并行工作进程数")
    parser.add_argument("--timeout", type=int, default=30, help="每个查询的超时时间（秒）")
    parser.add_argument("--max-iterations", type=int, default=5, help="最大改进迭代次数")
    parser.add_argument("--runs-per-query", type=int, default=3, help="每个查询运行的次数")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="触发率阈值")
    parser.add_argument("--holdout", type=float, default=0.4, help="留出作为测试集的比例 (0 表示禁用)")
    parser.add_argument("--model", required=True, help="用于改进的模型")
    parser.add_argument("--verbose", action="store_true", help="打印进度到 stderr")
    parser.add_argument("--report", default="auto", help="在此路径生成 HTML 报告 (默认: 'auto' 使用临时文件, 'none' 禁用)")
    parser.add_argument("--results-dir", default=None, help="将所有输出（results.json, report.html, log.txt）保存到此处的带时间戳的子目录中")
    args = parser.parse_args()

    eval_set = json.loads(Path(args.eval_set).read_text(encoding="utf-8"))
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"错误: 在 {skill_path} 中未找到 SKILL.md", file=sys.stderr)
        sys.exit(1)

    name, _, _ = parse_skill_md(skill_path)

    # 设置实时报告路径
    if args.report != "none":
        if args.report == "auto":
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            live_report_path = Path(tempfile.gettempdir()) / f"skill_description_report_{skill_path.name}_{timestamp}.html"
        else:
            live_report_path = Path(args.report)
        # 立即开启报告以便用户观察
        live_report_path.write_text("<html><body><h1>正在启动优化循环...</h1><meta http-equiv='refresh' content='5'></body></html>", encoding="utf-8")
        webbrowser.open(str(live_report_path))
    else:
        live_report_path = None

    # 确定输出目录（在 run_loop 之前创建，以便写入日志）
    if args.results_dir:
        timestamp = time.strftime("%Y-%m-%d_%H%M%S")
        results_dir = Path(args.results_dir) / timestamp
        results_dir.mkdir(parents=True, exist_ok=True)
    else:
        results_dir = None

    log_dir = results_dir / "logs" if results_dir else None

    output = run_loop(
        eval_set=eval_set,
        skill_path=skill_path,
        description_override=args.description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        max_iterations=args.max_iterations,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        holdout=args.holdout,
        model=args.model,
        verbose=args.verbose,
        live_report_path=live_report_path,
        log_dir=log_dir,
    )

    # 保存 JSON 输出
    json_output = json.dumps(output, indent=2, ensure_ascii=False)
    print(json_output)
    if results_dir:
        (results_dir / "results.json").write_text(json_output, encoding="utf-8")

    # 编写最终的 HTML 报告（不带自动刷新）
    if live_report_path:
        live_report_path.write_text(generate_html(output, auto_refresh=False, skill_name=name), encoding="utf-8")
        print(f"\n报告: {live_report_path}", file=sys.stderr)

    if results_dir and live_report_path:
        (results_dir / "report.html").write_text(generate_html(output, auto_refresh=False, skill_name=name), encoding="utf-8")

    if results_dir:
        print(f"结果已保存至: {results_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
