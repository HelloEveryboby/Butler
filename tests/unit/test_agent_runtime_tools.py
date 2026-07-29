"""
Comprehensive tests for agent_runtime tool_registry and permission modules.

Covers:
    - ToolRegistry: register, unregister, decorator, execute, schemas, definitions,
      read-only / concurrency-safe queries, parameter validation.
    - ToolExecutor: validate_arguments, execute (dict / ToolResult / string / exception).
    - ToolDefinition.to_openai_schema format.
    - PermissionRule: parse, matches (tool name, Bash command, file path, generic).
    - PermissionSystem: check with all PermissionMode variants, allow/deny rules,
      is_read_only_command, is_dangerous_command, set_mode, add_allow/deny_rule.
    - PermissionConfig: from_dict / to_dict round-trip.
"""

from __future__ import annotations

import pytest

from butler.core.agent_runtime.tool_registry import ToolRegistry, ToolExecutor
from butler.core.agent_runtime.permission import (
    PermissionSystem,
    PermissionDecision,
    PermissionMode,
    PermissionRule,
    PermissionConfig,
)
from butler.core.agent_runtime.types import (
    PermissionLevel,
    ToolDefinition,
    ToolResult,
)


# ─── helpers ────────────────────────────────────────────────────────────

SAMPLE_PARAMS = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "File path"},
        "content": {"type": "string", "description": "Content to write"},
    },
    "required": ["path"],
}


def _make_handler(return_value):
    """Create a handler that returns *return_value* when called."""
    def handler(arguments: dict, **ctx) -> dict:
        return return_value
    return handler


# ═══════════════════════════════════════════════════════════════════════
#  ToolRegistry
# ═══════════════════════════════════════════════════════════════════════

class TestToolRegistryRegister:

    def test_register_appears_in_list_names(self):
        registry = ToolRegistry()
        registry.register(
            handler=_make_handler({"success": True}),
            name="read_file",
            description="Read a file",
            parameters=SAMPLE_PARAMS,
        )
        assert "read_file" in registry.list_names()

    def test_register_appears_in_get(self):
        registry = ToolRegistry()
        registry.register(
            handler=_make_handler({"success": True}),
            name="read_file",
            description="Read a file",
            parameters=SAMPLE_PARAMS,
        )
        executor = registry.get("read_file")
        assert executor is not None
        assert executor.name == "read_file"

    def test_register_appears_in_get_schemas(self):
        registry = ToolRegistry()
        registry.register(
            handler=_make_handler({"success": True}),
            name="read_file",
            description="Read a file",
            parameters=SAMPLE_PARAMS,
        )
        schemas = registry.get_schemas()
        assert len(schemas) == 1
        schema = schemas[0]
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "read_file"

    def test_register_appears_in_get_definitions(self):
        registry = ToolRegistry()
        registry.register(
            handler=_make_handler({"success": True}),
            name="read_file",
            description="Read a file",
            parameters=SAMPLE_PARAMS,
        )
        defs = registry.get_definitions()
        assert len(defs) == 1
        assert defs[0].name == "read_file"


class TestToolRegistryDecorator:

    def test_tool_decorator_registers(self):
        registry = ToolRegistry()

        @registry.tool(
            name="grep_search",
            description="Search with grep",
            parameters=SAMPLE_PARAMS,
            permission_level=PermissionLevel.ALWAYS_ALLOW,
            is_read_only=True,
        )
        def grep_search(arguments: dict, **ctx) -> dict:
            return {"content": "results"}

        assert "grep_search" in registry.list_names()
        executor = registry.get("grep_search")
        assert executor is not None
        # The decorated function should still be callable
        result = grep_search(arguments={"path": "/tmp/a"})
        assert result == {"content": "results"}


class TestToolRegistryUnregister:

    def test_unregister_existing(self):
        registry = ToolRegistry()
        registry.register(
            handler=_make_handler({"success": True}),
            name="read_file",
            description="Read a file",
            parameters=SAMPLE_PARAMS,
        )
        assert registry.unregister("read_file") is True
        assert "read_file" not in registry.list_names()
        assert registry.get("read_file") is None

    def test_unregister_nonexistent(self):
        registry = ToolRegistry()
        assert registry.unregister("no_such_tool") is False


class TestToolRegistryExecute:

    def test_execute_success(self):
        registry = ToolRegistry()
        registry.register(
            handler=_make_handler({"success": True, "content": "hello world"}),
            name="read_file",
            description="Read a file",
            parameters=SAMPLE_PARAMS,
        )
        result = registry.execute("read_file", {"path": "/tmp/test.txt"})
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.content == "hello world"

    def test_execute_missing_required_params(self):
        registry = ToolRegistry()
        registry.register(
            handler=_make_handler({"success": True}),
            name="read_file",
            description="Read a file",
            parameters=SAMPLE_PARAMS,  # requires "path"
        )
        result = registry.execute("read_file", {})  # missing path
        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "Missing required parameters" in result.error

    def test_execute_unregistered_tool_raises(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.execute("nonexistent_tool", {})


class TestToolRegistryQueries:

    def test_get_read_only_tools(self):
        registry = ToolRegistry()
        registry.register(
            handler=_make_handler({}),
            name="read_tool",
            description="Read",
            parameters=SAMPLE_PARAMS,
            is_read_only=True,
        )
        registry.register(
            handler=_make_handler({}),
            name="write_tool",
            description="Write",
            parameters=SAMPLE_PARAMS,
            is_read_only=False,
        )
        assert registry.get_read_only_tools() == ["read_tool"]

    def test_get_concurrency_safe_tools(self):
        registry = ToolRegistry()
        registry.register(
            handler=_make_handler({}),
            name="safe_tool",
            description="Safe",
            parameters=SAMPLE_PARAMS,
            is_concurrency_safe=True,
        )
        registry.register(
            handler=_make_handler({}),
            name="unsafe_tool",
            description="Unsafe",
            parameters=SAMPLE_PARAMS,
            is_concurrency_safe=False,
        )
        assert registry.get_concurrency_safe_tools() == ["safe_tool"]


# ═══════════════════════════════════════════════════════════════════════
#  ToolExecutor
# ═══════════════════════════════════════════════════════════════════════

class TestToolExecutorValidation:

    def test_validate_arguments_all_present(self):
        defn = ToolDefinition(
            name="test",
            description="Test tool",
            parameters_schema=SAMPLE_PARAMS,
        )
        executor = ToolExecutor(defn, lambda arguments, **kw: {})
        ok, msg = executor.validate_arguments({"path": "/tmp/a"})
        assert ok is True
        assert msg == ""

    def test_validate_arguments_missing_required(self):
        defn = ToolDefinition(
            name="test",
            description="Test tool",
            parameters_schema=SAMPLE_PARAMS,
        )
        executor = ToolExecutor(defn, lambda arguments, **kw: {})
        ok, msg = executor.validate_arguments({})
        assert ok is False
        assert "path" in msg

    def test_validate_arguments_no_required(self):
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        defn = ToolDefinition(
            name="test",
            description="Test tool",
            parameters_schema=schema,
        )
        executor = ToolExecutor(defn, lambda arguments, **kw: {})
        ok, msg = executor.validate_arguments({})
        assert ok is True


class TestToolExecutorExecute:

    def test_execute_dict_result_wrapping_success(self):
        defn = ToolDefinition(
            name="test",
            description="Test tool",
            parameters_schema={"type": "object", "properties": {}},
        )
        executor = ToolExecutor(defn, _make_handler({"success": True, "content": "ok"}))
        result = executor.execute({})
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.content == "ok"

    def test_execute_dict_result_wrapping_failure(self):
        defn = ToolDefinition(
            name="test",
            description="Test tool",
            parameters_schema={"type": "object", "properties": {}},
        )
        executor = ToolExecutor(
            defn, _make_handler({"success": False, "error": "something failed"})
        )
        result = executor.execute({})
        assert isinstance(result, ToolResult)
        assert result.success is False
        assert result.error == "something failed"

    def test_execute_tool_result_passthrough(self):
        defn = ToolDefinition(
            name="test",
            description="Test tool",
            parameters_schema={"type": "object", "properties": {}},
        )
        expected = ToolResult(
            tool_call_id="tc_1",
            content="passthrough",
            success=True,
        )
        executor = ToolExecutor(defn, lambda arguments, **kw: expected)
        result = executor.execute({})
        assert result is expected

    def test_execute_string_result(self):
        defn = ToolDefinition(
            name="test",
            description="Test tool",
            parameters_schema={"type": "object", "properties": {}},
        )
        executor = ToolExecutor(defn, lambda arguments, **kw: "plain string")
        result = executor.execute({})
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.content == "plain string"

    def test_execute_handler_exception(self):
        defn = ToolDefinition(
            name="test",
            description="Test tool",
            parameters_schema={"type": "object", "properties": {}},
        )

        def bad_handler(arguments: dict, **kw) -> dict:
            raise RuntimeError("boom")

        executor = ToolExecutor(defn, bad_handler)
        result = executor.execute({})
        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "RuntimeError" in result.error
        assert "boom" in result.error

    def test_execute_dict_result_uses_output_key(self):
        """Handler may return {'output': ...} instead of {'content': ...}."""
        defn = ToolDefinition(
            name="test",
            description="Test tool",
            parameters_schema={"type": "object", "properties": {}},
        )
        executor = ToolExecutor(
            defn, _make_handler({"success": True, "output": "via output key"})
        )
        result = executor.execute({})
        assert result.success is True
        assert result.content == "via output key"

    def test_execute_metadata_elapsed(self):
        defn = ToolDefinition(
            name="test",
            description="Test tool",
            parameters_schema={"type": "object", "properties": {}},
        )
        executor = ToolExecutor(defn, _make_handler({"success": True, "content": "x"}))
        result = executor.execute({})
        assert "elapsed_ms" in result.metadata


# ═══════════════════════════════════════════════════════════════════════
#  ToolDefinition.to_openai_schema
# ═══════════════════════════════════════════════════════════════════════

class TestToolDefinitionOpenAISchema:

    def test_schema_format(self):
        defn = ToolDefinition(
            name="my_tool",
            description="Does things",
            parameters_schema=SAMPLE_PARAMS,
        )
        schema = defn.to_openai_schema()
        assert schema == {
            "type": "function",
            "function": {
                "name": "my_tool",
                "description": "Does things",
                "parameters": SAMPLE_PARAMS,
            },
        }

    def test_schema_contains_all_fields(self):
        defn = ToolDefinition(
            name="x",
            description="y",
            parameters_schema={"type": "object", "properties": {}},
        )
        s = defn.to_openai_schema()
        fn = s["function"]
        assert fn["name"] == "x"
        assert fn["description"] == "y"
        assert fn["parameters"] == {"type": "object", "properties": {}}


# ═══════════════════════════════════════════════════════════════════════
#  PermissionRule
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionRuleParse:

    def test_parse_with_parens(self):
        rule = PermissionRule.parse("Read(*)")
        assert rule.tool_name == "Read"
        assert rule.pattern == "*"

    def test_parse_bash_command(self):
        rule = PermissionRule.parse("Bash(git *)")
        assert rule.tool_name == "Bash"
        assert rule.pattern == "git *"

    def test_parse_no_parens(self):
        rule = PermissionRule.parse("Write")
        assert rule.tool_name == "Write"
        assert rule.pattern == "*"


class TestPermissionRuleMatches:

    def test_tool_name_match(self):
        rule = PermissionRule.parse("Read(*)")
        assert rule.matches("Read", {"path": "/tmp/a"}) is True
        assert rule.matches("Write", {"path": "/tmp/a"}) is False

    def test_bash_command_pattern(self):
        rule = PermissionRule.parse("Bash(git *)")
        assert rule.matches("Bash", {"command": "git status"}) is True
        assert rule.matches("Bash", {"command": "ls -la"}) is False

    def test_bash_command_pattern_shell(self):
        """shell should also match Bash-like command patterns."""
        rule = PermissionRule.parse("Shell(git *)")
        assert rule.matches("Shell", {"command": "git log"}) is True

    def test_file_path_pattern(self):
        rule = PermissionRule.parse("Read(/tmp/*)")
        assert rule.matches("Read", {"path": "/tmp/file.txt"}) is True
        assert rule.matches("Read", {"path": "/etc/passwd"}) is False

    def test_file_path_pattern_write_with_file_path(self):
        rule = PermissionRule.parse("Write(/src/*.py)")
        # matches on file_path key
        assert rule.matches("Write", {"file_path": "/src/main.py"}) is True
        assert rule.matches("Write", {"file_path": "/src/test.rs"}) is False

    def test_generic_string_argument_match(self):
        """For non-Bash/non-file tools, any string value is checked."""
        rule = PermissionRule.parse("Grep(*.py)")
        assert rule.matches("Grep", {"pattern": "*.py"}) is True
        assert rule.matches("Grep", {"pattern": "*.txt"}) is False

    def test_wildcard_pattern_always_matches_tool(self):
        rule = PermissionRule.parse("Read(*)")
        assert rule.matches("Read", {}) is True
        assert rule.matches("Read", {"any_key": "anything"}) is True

    def test_non_string_value_ignored(self):
        rule = PermissionRule.parse("Tool(some_pattern)")
        assert rule.matches("Tool", {"count": 42}) is False


# ═══════════════════════════════════════════════════════════════════════
#  PermissionSystem — ALWAYS_ALLOW / NEVER_ALLOW tool levels
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionSystemToolLevels:

    def test_always_allow_level(self):
        ps = PermissionSystem()
        decision = ps.check("Read", {"path": "/a"}, tool_permission_level=PermissionLevel.ALWAYS_ALLOW)
        assert decision == PermissionDecision.ALLOW

    def test_never_allow_level(self):
        ps = PermissionSystem()
        decision = ps.check("Danger", {}, tool_permission_level=PermissionLevel.NEVER_ALLOW)
        assert decision == PermissionDecision.DENY

    def test_require_confirm_default(self):
        ps = PermissionSystem()
        decision = ps.check("Write", {"path": "/a"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ASK


# ═══════════════════════════════════════════════════════════════════════
#  PermissionSystem — BYPASS_PERMISSIONS mode
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionSystemBypass:

    def test_bypass_allows_everything(self):
        cfg = PermissionConfig(mode=PermissionMode.BYPASS_PERMISSIONS)
        ps = PermissionSystem(cfg)
        # Even a dangerous tool is allowed under BYPASS (NEVER_ALLOW is checked
        # before BYPASS mode, so we use REQUIRE_CONFIRM here)
        decision = ps.check("Bash", {"command": "rm -rf /"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ALLOW

    def test_bypass_does_not_override_never_allow(self):
        cfg = PermissionConfig(mode=PermissionMode.BYPASS_PERMISSIONS)
        ps = PermissionSystem(cfg)
        decision = ps.check("Danger", {}, tool_permission_level=PermissionLevel.NEVER_ALLOW)
        # NEVER_ALLOW check happens before BYPASS mode
        assert decision == PermissionDecision.DENY


# ═══════════════════════════════════════════════════════════════════════
#  PermissionSystem — PLAN mode
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionSystemPlan:

    def test_plan_allows_always_allow(self):
        cfg = PermissionConfig(mode=PermissionMode.PLAN)
        ps = PermissionSystem(cfg)
        decision = ps.check("Read", {"path": "/a"}, tool_permission_level=PermissionLevel.ALWAYS_ALLOW)
        assert decision == PermissionDecision.ALLOW

    def test_plan_denies_require_confirm(self):
        cfg = PermissionConfig(mode=PermissionMode.PLAN)
        ps = PermissionSystem(cfg)
        decision = ps.check("Write", {"path": "/a"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.DENY


# ═══════════════════════════════════════════════════════════════════════
#  PermissionSystem — AUTO mode
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionSystemAuto:

    def test_auto_readonly_bash_allowed(self):
        cfg = PermissionConfig(mode=PermissionMode.AUTO)
        ps = PermissionSystem(cfg)
        decision = ps.check("Bash", {"command": "ls -la"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ALLOW

    def test_auto_dangerous_bash_denied(self):
        cfg = PermissionConfig(mode=PermissionMode.AUTO)
        ps = PermissionSystem(cfg)
        decision = ps.check("Bash", {"command": "rm -rf /"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.DENY

    def test_auto_unknown_bash_asked(self):
        cfg = PermissionConfig(mode=PermissionMode.AUTO)
        ps = PermissionSystem(cfg)
        decision = ps.check("Bash", {"command": "npm install"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ASK

    def test_auto_read_tool_allowed(self):
        cfg = PermissionConfig(mode=PermissionMode.AUTO)
        ps = PermissionSystem(cfg)
        decision = ps.check("Read", {"path": "/tmp/a"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ALLOW

    def test_auto_glob_tool_allowed(self):
        cfg = PermissionConfig(mode=PermissionMode.AUTO)
        ps = PermissionSystem(cfg)
        decision = ps.check("glob", {"pattern": "*.py"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ALLOW

    def test_auto_write_relative_path_allowed(self):
        cfg = PermissionConfig(mode=PermissionMode.AUTO)
        ps = PermissionSystem(cfg)
        decision = ps.check("Write", {"path": "src/main.py"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ALLOW

    def test_auto_write_absolute_path_asked(self):
        cfg = PermissionConfig(mode=PermissionMode.AUTO)
        ps = PermissionSystem(cfg)
        decision = ps.check("Write", {"path": "/etc/passwd"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ASK


# ═══════════════════════════════════════════════════════════════════════
#  PermissionSystem — ACCEPT_EDITS mode
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionSystemAcceptEdits:

    def test_accept_edits_write_allowed(self):
        cfg = PermissionConfig(mode=PermissionMode.ACCEPT_EDITS)
        ps = PermissionSystem(cfg)
        decision = ps.check("Write", {"path": "/a"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ALLOW

    def test_accept_edits_edit_allowed(self):
        cfg = PermissionConfig(mode=PermissionMode.ACCEPT_EDITS)
        ps = PermissionSystem(cfg)
        decision = ps.check("Edit", {"path": "/a"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ALLOW

    def test_accept_edits_multi_edit_allowed(self):
        cfg = PermissionConfig(mode=PermissionMode.ACCEPT_EDITS)
        ps = PermissionSystem(cfg)
        decision = ps.check("multi_edit", {"path": "/a"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ALLOW

    def test_accept_edits_other_tool_asks(self):
        cfg = PermissionConfig(mode=PermissionMode.ACCEPT_EDITS)
        ps = PermissionSystem(cfg)
        decision = ps.check("Bash", {"command": "npm install"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ASK


# ═══════════════════════════════════════════════════════════════════════
#  PermissionSystem — DONT_ASK mode
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionSystemDontAsk:

    def test_dont_ask_denies_unlisted(self):
        cfg = PermissionConfig(mode=PermissionMode.DONT_ASK)
        ps = PermissionSystem(cfg)
        decision = ps.check("Write", {"path": "/a"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.DENY

    def test_dont_ask_allows_explicit_allow_rule(self):
        cfg = PermissionConfig(mode=PermissionMode.DONT_ASK)
        ps = PermissionSystem(cfg)
        ps.add_allow_rule("Write(*)")
        decision = ps.check("Write", {"path": "/a"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        assert decision == PermissionDecision.ALLOW


# ═══════════════════════════════════════════════════════════════════════
#  PermissionSystem — deny / allow rules
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionSystemRules:

    def test_deny_rule_blocks(self):
        ps = PermissionSystem()
        ps.add_deny_rule("Bash(rm -rf *)")
        decision = ps.check("Bash", {"command": "rm -rf /home"})
        assert decision == PermissionDecision.DENY

    def test_allow_rule_permits(self):
        ps = PermissionSystem()
        ps.add_allow_rule("Read(*)")
        decision = ps.check("Read", {"path": "/tmp/a"}, tool_permission_level=PermissionLevel.REQUIRE_CONFIRM)
        # allow rule takes precedence over default ASK
        assert decision == PermissionDecision.ALLOW

    def test_deny_rule_takes_priority_over_allow(self):
        ps = PermissionSystem()
        ps.add_allow_rule("Bash(*)")
        ps.add_deny_rule("Bash(rm -rf *)")
        # deny check is step 4, allow check is step 5 in the check() logic,
        # so deny should fire first
        decision = ps.check("Bash", {"command": "rm -rf /home"})
        assert decision == PermissionDecision.DENY


# ═══════════════════════════════════════════════════════════════════════
#  PermissionSystem — set_mode / add_allow_rule / add_deny_rule
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionSystemMutations:

    def test_set_mode(self):
        ps = PermissionSystem()
        assert ps.mode == PermissionMode.DEFAULT
        ps.set_mode(PermissionMode.BYPASS_PERMISSIONS)
        assert ps.mode == PermissionMode.BYPASS_PERMISSIONS

    def test_add_allow_rule(self):
        ps = PermissionSystem()
        ps.add_allow_rule("Read(*)")
        assert len(ps.config.allow_rules) == 1
        assert ps.config.allow_rules[0].tool_name == "Read"

    def test_add_deny_rule(self):
        ps = PermissionSystem()
        ps.add_deny_rule("Bash(rm -rf *)")
        assert len(ps.config.deny_rules) == 1
        assert ps.config.deny_rules[0].pattern == "rm -rf *"


# ═══════════════════════════════════════════════════════════════════════
#  PermissionSystem — is_read_only_command / is_dangerous_command
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionSystemCommandClassification:

    def test_is_read_only_command_true(self):
        ps = PermissionSystem()
        assert ps.is_read_only_command("ls -la") is True
        assert ps.is_read_only_command("git status") is True
        assert ps.is_read_only_command("cat /tmp/a") is True
        assert ps.is_read_only_command("pwd") is True
        assert ps.is_read_only_command("whoami") is True

    def test_is_read_only_command_false(self):
        ps = PermissionSystem()
        assert ps.is_read_only_command("rm -rf /") is False
        assert ps.is_read_only_command("npm install") is False

    def test_is_dangerous_command_true(self):
        ps = PermissionSystem()
        assert ps.is_dangerous_command("rm -rf /") is True
        assert ps.is_dangerous_command("rm -rf /*") is True
        assert ps.is_dangerous_command("shutdown now") is True

    def test_is_dangerous_command_false(self):
        ps = PermissionSystem()
        assert ps.is_dangerous_command("ls -la") is False
        assert ps.is_dangerous_command("git status") is False


# ═══════════════════════════════════════════════════════════════════════
#  PermissionConfig — from_dict / to_dict
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionConfigRoundTrip:

    def test_from_dict_defaults(self):
        cfg = PermissionConfig.from_dict({})
        assert cfg.mode == PermissionMode.DEFAULT
        assert cfg.allow_rules == []
        assert cfg.deny_rules == []

    def test_from_dict_with_values(self):
        d = {
            "mode": "auto",
            "allow": ["Read(*)", "Bash(git *)"],
            "deny": ["Bash(rm -rf *)"],
        }
        cfg = PermissionConfig.from_dict(d)
        assert cfg.mode == PermissionMode.AUTO
        assert len(cfg.allow_rules) == 2
        assert len(cfg.deny_rules) == 1
        assert cfg.deny_rules[0].tool_name == "Bash"
        assert cfg.deny_rules[0].pattern == "rm -rf *"

    def test_from_dict_invalid_mode_fallback(self):
        cfg = PermissionConfig.from_dict({"mode": "nonexistent_mode"})
        assert cfg.mode == PermissionMode.DEFAULT

    def test_to_dict(self):
        cfg = PermissionConfig.from_dict({
            "mode": "accept_edits",
            "allow": ["Read(*)"],
            "deny": ["Bash(rm -rf *)"],
        })
        d = cfg.to_dict()
        assert d["mode"] == "accept_edits"
        assert "Read(*)" in d["allow"]
        assert "Bash(rm -rf *)" in d["deny"]

    def test_round_trip(self):
        original = {
            "mode": "auto",
            "allow": ["Read(*)", "Bash(git *)"],
            "deny": ["Bash(rm -rf *)"],
        }
        cfg = PermissionConfig.from_dict(original)
        restored = cfg.to_dict()
        assert restored["mode"] == "auto"
        assert set(restored["allow"]) == set(original["allow"])
        assert set(restored["deny"]) == set(original["deny"])
