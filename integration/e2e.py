#!/usr/bin/env python3
"""端到端集成验证：Python 客户端 → Go 连接器 → Node DSH 宿主 shim → 市场插件。

覆盖链路：
  1. 能力注册表同步（插件工具出现在 Butler 的 LLM 工具表）
  2. 普通工具调用（invoke → result）
  3. 流式工具调用（invoke → chunk × N → result）
  4. 权限代理闭环（策略 ask → approve.ask → approve.answer → 工具拿到结论）
  5. 审计日志落盘
  6. 活性探测

用法：在工作区根目录执行  python3 integration/e2e.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "connector"))

from butler_dsh.client import ConnectorClient  # noqa: E402

SOCK = os.path.join(ROOT, "integration", "connector.sock")
CONNECTOR_BIN = os.path.join(ROOT, "connector", "bin", "butler-dsh-connector")
AUDIT_LOG = os.path.join(ROOT, "integration", "logs", "audit.jsonl")

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        PASSED.append(name)
        print(f"  ✅ {name}")
    else:
        FAILED.append(name)
        print(f"  ❌ {name}  {detail}")


def main() -> int:
    print("== Butler × DSH 插件搬运 · 端到端集成验证 ==\n")

    if os.path.exists(SOCK):
        os.unlink(SOCK)

    log = open(os.path.join(ROOT, "integration", "logs", "connector.log"), "w")
    proc = subprocess.Popen(
        [CONNECTOR_BIN, "-config", "integration/connector.json"],
        cwd=ROOT,
        stdout=log,
        stderr=log,
    )

    try:
        # 等 socket 就绪 + 连接重试
        # 审批回调从一开始就挂上：风险 unknown 的工具默认 ask（fail-closed），
        # 没人应答 = 拒绝，所以真实部署里 Butler 必须提供审批 UI。
        approvals_seen: list[dict] = []

        def auto_approve(req: dict) -> dict:
            approvals_seen.append(req)
            return {"allowed": True, "reason": "e2e operator approved", "remember": False}

        client = ConnectorClient(SOCK, on_approve_ask=auto_approve)
        for _ in range(50):
            if os.path.exists(SOCK):
                try:
                    client.start()
                    break
                except OSError:
                    pass
            time.sleep(0.2)
        else:
            print("connector socket never appeared")
            return 1

        client.wait_ready(timeout=10)
        print("\n[1] 能力注册表")
        caps = client.capabilities()
        names = {c["name"] for c in caps}
        check("插件工具进入能力表", names == {"hello.greet", "hello.count", "hello.ask"}, f"got {names}")
        greet = next((c for c in caps if c["name"] == "hello.greet"), None)
        check("工具带描述（触发率保障）", bool(greet and greet["description"]))
        check("工具带 schema", bool(greet and greet.get("schema")))
        check("风险分类已标注", bool(greet and greet.get("risk")), f"got {greet and greet.get('risk')}")

        print("\n[2] 普通工具调用")
        call = client.invoke("hello.greet", {"name": "张三"})
        res = call.result(timeout=15)
        content = res.get("content") or {}
        check("invoke → result 回流", "张三" in str(content.get("greeting", "")), f"got {content}")

        print("\n[3] 流式工具调用")
        call = client.invoke("hello.count", {"to": 3})
        chunks = list(call.chunks(timeout=15))
        call.result(timeout=15)
        seqs = [c.get("seq") for c in chunks]
        check("chunk × 3 顺序回流", seqs == [0, 1, 2], f"got {seqs}")

        print("\n[4] 权限代理闭环（策略 ask → 人工审批 → 放行）")
        call = client.invoke("hello.ask", {})
        res = call.result(timeout=15)
        content = res.get("content") or {}
        check("审批结论回流插件", content.get("approved") is True, f"got {content}")
        # hello.ask 触发两次审批：调用级（策略 ask）+ 插件内部（askApproval）；
        # 加上 greet/count 各一次，共 4 次审批闭环。
        ask_approvals = [r for r in approvals_seen if r.get("tool") == "hello.ask"]
        check("approve.ask 到达 Butler", len(ask_approvals) == 2, f"got {len(ask_approvals)}")
        check("全部未知风险调用均触发审批", len(approvals_seen) == 4, f"got {len(approvals_seen)}")

        print("\n[5] 基础设施")
        check("审计日志落盘", os.path.exists(AUDIT_LOG) and os.path.getsize(AUDIT_LOG) > 0)
        with open(AUDIT_LOG) as f:
            audit = f.read()
        check("审计含审批记录", "human" in audit or "policy" in audit)
        check("health ping/pong", client.ping())

        client.close()
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()

    print(f"\n== 结果: {len(PASSED)} 通过, {len(FAILED)} 失败 ==")
    if FAILED:
        print("失败项:", ", ".join(FAILED))
        return 1
    print("🎉 全链路（Python → Go → Node → 插件）验证通过")
    return 0


if __name__ == "__main__":
    os.makedirs(os.path.join(ROOT, "integration", "logs"), exist_ok=True)
    sys.exit(main())
