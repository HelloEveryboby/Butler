#!/usr/bin/env python3
"""根据评估结果改进技能描述。

获取评估结果（来自 run_eval.py），并通过调用子进程 `claude -p` 生成改进后的描述
（与 run_eval.py 使用相同的身份验证模式 — 借用当前会话的 Claude Code 认证，
无需额外的 ANTHROPIC_API_KEY）。
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from scripts.utils import parse_skill_md


def _call_claude(prompt: str, model: str | None, timeout: int = 300) -> str:
    """通过 stdin 运行 `claude -p` 并返回文本响应。

    提示词通过 stdin 传递（而非 argv），因为它包含完整的 SKILL.md 正文，
    很容易超过 argv 的长度限制。
    """
    cmd = ["claude", "-p", "--output-format", "text"]
    if model:
        cmd.extend(["--model", model])

    # 移除 CLAUDECODE 环境变量，以便在 Claude Code 会话中嵌套调用 claude -p。
    # 该限制是为了防止交互式终端冲突；程序化子进程调用是安全的。与 run_eval.py 模式一致。
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude -p 退出码为 {result.returncode}\nstderr: {result.stderr}"
        )
    return result.stdout


def improve_description(
    skill_name: str,
    skill_content: str,
    current_description: str,
    eval_results: dict,
    history: list[dict],
    model: str,
    test_results: dict | None = None,
    log_dir: Path | None = None,
    iteration: int | None = None,
) -> str:
    """根据评估结果调用 Claude 改进描述。"""
    failed_triggers = [
        r for r in eval_results["results"]
        if r["should_trigger"] and not r["pass"]
    ]
    false_triggers = [
        r for r in eval_results["results"]
        if not r["should_trigger"] and not r["pass"]
    ]

    # 构建得分摘要
    train_score = f"{eval_results['summary']['passed']}/{eval_results['summary']['total']}"
    if test_results:
        test_score = f"{test_results['summary']['passed']}/{test_results['summary']['total']}"
        scores_summary = f"训练集: {train_score}, 测试集: {test_score}"
    else:
        scores_summary = f"训练集: {train_score}"

    prompt = f"""你正在为一个名为 "{skill_name}" 的 Claude Code 技能优化描述。所谓“技能”类似于提示词，但具有渐进式披露特性——Claude 在决定是否使用该技能时，首先会看到标题和描述。如果它决定使用该技能，就会读取 .md 文件，该文件包含更多细节，并可能链接到技能文件夹中的其他资源（如辅助文件、脚本、额外文档或示例）。

描述会出现在 Claude 的 "available_skills" 列表中。当用户发送查询时，Claude 仅根据标题和此描述来决定是否调用该技能。你的目标是编写一个描述，使其在相关查询时触发，而在不相关查询时不触发。

这是当前的描述：
<current_description>
"{current_description}"
</current_description>

当前得分 ({scores_summary})：
<scores_summary>
"""
    if failed_triggers:
        prompt += "未能触发（应该触发但没触发）：\n"
        for r in failed_triggers:
            prompt += f'  - "{r["query"]}" (触发次数: {r["triggers"]}/{r["runs"]})\n'
        prompt += "\n"

    if false_triggers:
        prompt += "错误触发（不该触发却触发了）：\n"
        for r in false_triggers:
            prompt += f'  - "{r["query"]}" (触发次数: {r["triggers"]}/{r["runs"]})\n'
        prompt += "\n"

    if history:
        prompt += "之前的尝试记录（不要重复这些——尝试结构上不同的方式）：\n\n"
        for h in history:
            train_s = f"{h.get('train_passed', h.get('passed', 0))}/{h.get('train_total', h.get('total', 0))}"
            test_s = f"{h.get('test_passed', '?')}/{h.get('test_total', '?')}" if h.get('test_passed') is not None else None
            score_str = f"训练={train_s}" + (f", 测试={test_s}" if test_s else "")
            prompt += f'<attempt {score_str}>\n'
            prompt += f'描述: "{h["description"]}"\n'
            if "results" in h:
                prompt += "训练集结果：\n"
                for r in h["results"]:
                    status = "通过" if r["pass"] else "失败"
                    prompt += f'  [{status}] "{r["query"][:80]}" (触发次数: {r["triggers"]}/{r["runs"]})\n'
            if h.get("note"):
                prompt += f'备注: {h["note"]}\n'
            prompt += "</attempt>\n\n"

    prompt += f"""</scores_summary>

技能内容（用于了解技能具体功能的上下文）：
<skill_content>
{skill_content}
</skill_content>

根据失败案例，编写一个新的、改进后的描述，使其更有可能被正确触发。当我说“根据失败案例”时，需要注意平衡，因为我们不希望对你看到的特定案例进行过度拟合。因此，我**不**希望你产生一个不断扩大的特定查询列表。相反，请尝试从失败案例中归纳出更广泛的用户意图类别，以及该技能有用或没用的具体场景。原因有二：

1. 避免过度拟合
2. 列表可能会变得非常长，而描述会被注入到所有查询中。如果技能很多，我们不希望单个描述占用太多空间。

具体来说，你的描述字数应控制在约 100-200 字以内，即使这会牺牲一定的准确性。长度有一个 1024 字符的硬性限制——超过该限制的描述将被截断，因此请保持在限制范围内。

以下是一些编写此类描述的技巧：
- 描述应采用祈使句开头 —— 比如“使用此技能进行...”，而不是“此技能可以...”
- 描述应专注于用户的意图和他们想要实现的目标，而不是技能如何运作的实现细节。
- 该描述与其他技能竞争 Claude 的注意力 —— 务必使其具有辨识度，能让人一眼认出。
- 如果多次尝试后仍然失败，请尝试改变策略。尝试不同的句式结构或措辞。

我鼓励你发挥创造力，在不同迭代中尝试不同的风格，因为你有多次机会，我们最终只会选取评分最高的一个。

请仅在 <new_description> 标签中返回新的描述文本，不要有其他多余内容。"""

    text = _call_claude(prompt, model)

    match = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    description = match.group(1).strip().strip('"') if match else text.strip().strip('"')

    transcript: dict = {
        "iteration": iteration,
        "prompt": prompt,
        "response": text,
        "parsed_description": description,
        "char_count": len(description),
        "over_limit": len(description) > 1024,
    }

    # 安全网：提示词中虽然规定了 1024 字符的硬性限制，但如果模型仍然超出了，
    # 则再进行一次单轮调用，引用过长的版本并要求缩减。
    if len(description) > 1024:
        shorten_prompt = (
            f"{prompt}\n\n"
            f"---\n\n"
            f"之前的尝试产生的描述长度为 {len(description)} 字符，超出了 1024 字符的硬性限制：\n\n"
            f'"{description}"\n\n'
            f"请将其改写为 1024 字符以内，同时保留最重要的触发关键词和意图覆盖。仅在 <new_description> 标签中返回新描述。"
        )
        shorten_text = _call_claude(shorten_prompt, model)
        match = re.search(r"<new_description>(.*?)</new_description>", shorten_text, re.DOTALL)
        shortened = match.group(1).strip().strip('"') if match else shorten_text.strip().strip('"')

        transcript["rewrite_prompt"] = shorten_prompt
        transcript["rewrite_response"] = shorten_text
        transcript["rewrite_description"] = shortened
        transcript["rewrite_char_count"] = len(shortened)
        description = shortened

    transcript["final_description"] = description

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"improve_iter_{iteration or 'unknown'}.json"
        log_file.write_text(json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8")

    return description


def main():
    parser = argparse.ArgumentParser(description="根据评估结果改进技能描述")
    parser.add_argument("--eval-results", required=True, help="评估结果 JSON 的路径 (来自 run_eval.py)")
    parser.add_argument("--skill-path", required=True, help="技能目录路径")
    parser.add_argument("--history", default=None, help="历史记录 JSON 的路径 (之前的尝试)")
    parser.add_argument("--model", required=True, help="用于改进的模型")
    parser.add_argument("--verbose", action="store_true", help="将思考过程打印到 stderr")
    args = parser.parse_args()

    skill_path = Path(args.skill_path)
    if not (skill_path / "SKILL.md").exists():
        print(f"错误: 在 {skill_path} 中未找到 SKILL.md", file=sys.stderr)
        sys.exit(1)

    eval_results = json.loads(Path(args.eval_results).read_text(encoding="utf-8"))
    history = []
    if args.history:
        history = json.loads(Path(args.history).read_text(encoding="utf-8"))

    name, _, content = parse_skill_md(skill_path)
    current_description = eval_results["description"]

    if args.verbose:
        print(f"当前描述: {current_description}", file=sys.stderr)
        print(f"得分: {eval_results['summary']['passed']}/{eval_results['summary']['total']}", file=sys.stderr)

    new_description = improve_description(
        skill_name=name,
        skill_content=content,
        current_description=current_description,
        eval_results=eval_results,
        history=history,
        model=args.model,
    )

    if args.verbose:
        print(f"改进后的描述: {new_description}", file=sys.stderr)

    # 以 JSON 格式输出新描述和更新后的历史记录
    output = {
        "description": new_description,
        "history": history + [{
            "description": current_description,
            "passed": eval_results["summary"]["passed"],
            "failed": eval_results["summary"]["failed"],
            "total": eval_results["summary"]["total"],
            "results": eval_results["results"],
        }],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
