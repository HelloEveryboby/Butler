# -*- coding: utf-8 -*-
import pytest
from butler.agent.dynamic_router import DynamicSkillRouter
from butler.core.skill_manager import SkillManager

class MockSkillManager:
    """Mock SkillManager for clean, isolation unit testing of DynamicSkillRouter."""
    def __init__(self):
        self.manifests = {
            "memos": {
                "name": "Memos",
                "description": "本地双语闪卡式结构化速记备忘录组件",
                "actions": ["create", "delete", "list"]
            },
            "sys_cleaner": {
                "name": "System Cleaner",
                "description": "进行本地垃圾清理和临时文件数据回收",
                "actions": ["run_clean", "get_status"]
            }
        }
        self.skill_contents = {
            "memos": "### memos SKILL.md body...",
            "sys_cleaner": "### sys_cleaner SKILL.md body..."
        }

    def execute(self, skill_id: str, action: str, **kwargs):
        if skill_id == "sys_cleaner":
            return {"status": "success", "freed_mb": 420}
        if skill_id == "memos":
            return {"status": "success", "memo_id": "memo_123"}
        return {"status": "success"}

    def match_skill(self, command: str) -> str:
        if "清理" in command or "clean" in command:
            return "sys_cleaner"
        if "备忘" in command or "memo" in command:
            return "memos"
        return None

def test_dynamic_router_schema_generation():
    """验证 DynamicSkillRouter 的 Tool Schema 自动生成逻辑是否正确。"""
    mock_sm = MockSkillManager()
    router = DynamicSkillRouter(skill_manager=mock_sm) # type: ignore
    schemas = router.generate_tool_schemas()

    assert len(schemas) == 2
    names = [s["name"] for s in schemas]
    assert "memos" in names
    assert "sys_cleaner" in names

    memos_schema = next(s for s in schemas if s["name"] == "memos")
    assert "Memos" in memos_schema["description"]
    assert "create" in memos_schema["parameters"]["properties"]["action"]["enum"]

def test_dynamic_router_pipeline_mock_execution():
    """验证 DynamicSkillRouter 4阶段管道在 Mock 模式下的表现。"""
    mock_sm = MockSkillManager()
    router = DynamicSkillRouter(skill_manager=mock_sm) # type: ignore
    router.use_mock = True  # 强制进入 mock 模式保证无网络也能 100% 运行通过

    report, metrics = router.execute_pipeline("我想进行系统垃圾清理")

    # 验证返回结构
    assert report is not None
    assert "Thinking Chain" in report
    assert "第一阶段" in report
    assert "第二阶段" in report
    assert "第三阶段" in report
    assert "第四阶段" in report

    # 验证指标与解析运行日志
    assert "plan_steps" in metrics
    assert "resolved_steps" in metrics
    assert "execution_results" in metrics
    assert "final_answer" in metrics

    # 验证匹配和执行流
    assert len(metrics["resolved_steps"]) > 0
    resolved_step = metrics["resolved_steps"][0]
    assert resolved_step["skill_id"] in ["sys_cleaner", "memos"]
