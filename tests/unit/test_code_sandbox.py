"""CodeSandbox 受限执行环境单元测试。"""


from butler.core.code_sandbox import CodeSandbox


class TestCodeSandboxValidation:
    """CodeSandbox 静态安全检查测试。"""

    def setup_method(self):
        self.sandbox = CodeSandbox()

    def test_safe_code_passes(self):
        """安全的代码通过检查。"""
        ok, msg = self.sandbox.validate("result = 1 + 2\n")
        assert ok is True

    def test_import_os_blocked(self):
        """禁止导入 os 模块。"""
        ok, msg = self.sandbox.validate("import os\n")
        assert ok is False
        assert "os" in msg

    def test_import_subprocess_blocked(self):
        """禁止导入 subprocess 模块。"""
        ok, msg = self.sandbox.validate("import subprocess\n")
        assert ok is False
        assert "subprocess" in msg

    def test_from_os_import_blocked(self):
        """禁止从 os 导入。"""
        ok, msg = self.sandbox.validate("from os import path\n")
        assert ok is False
        assert "os" in msg

    def test_open_call_blocked(self):
        """禁止调用 open 内置函数。"""
        ok, msg = self.sandbox.validate("f = open('/etc/passwd')\n")
        assert ok is False
        assert "open" in msg

    def test_exec_call_blocked(self):
        """禁止调用 exec。"""
        ok, msg = self.sandbox.validate("exec('print(1)')\n")
        assert ok is False
        assert "exec" in msg

    def test_dunder_subclasses_blocked(self):
        """禁止访问 __subclasses__。"""
        ok, msg = self.sandbox.validate("x = object.__subclasses__()\n")
        assert ok is False
        assert "__subclasses__" in msg

    def test_syntax_error_reported(self):
        """语法错误被捕获。"""
        ok, msg = self.sandbox.validate("def broken(:\n")
        assert ok is False
        assert "语法错误" in msg

    def test_safe_math_passes(self):
        """数学计算代码通过。"""
        ok, _ = self.sandbox.validate("result = sum(range(100))\n")
        assert ok is True


class TestCodeSandboxExecution:
    """CodeSandbox 执行测试。"""

    def setup_method(self):
        self.sandbox = CodeSandbox()

    def test_execute_safe_code(self):
        """安全代码成功执行并返回结果。"""
        result = self.sandbox.execute("result = 3 * 7\n")
        assert result["success"] is True
        assert result["result"] == 21

    def test_execute_blocked_code(self):
        """危险代码不执行。"""
        result = self.sandbox.execute("import os\nos.system('rm -rf /')\n")
        assert result["success"] is False
        assert "安全检查" in result["error"]

    def test_execute_with_print(self):
        """print 输出被捕获。"""
        result = self.sandbox.execute("print('hello world')\nresult = 42\n")
        assert result["success"] is True
        assert "hello world" in result["stdout"]

    def test_execute_runtime_error(self):
        """运行时错误被捕获。"""
        result = self.sandbox.execute("result = 1 / 0\n")
        assert result["success"] is False
        assert "ZeroDivision" in result["error"]

    def test_safe_open_with_allowed_paths(self):
        """配置 allowed_paths 后允许访问白名单内路径。"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            f.flush()
            path = f.name

        import os
        sandbox = CodeSandbox(allowed_paths=[os.path.dirname(path)])
        code = f"data = open('{path}').read()\nresult = data\n"
        result = sandbox.execute(code)
        assert result["success"] is True
        assert "test content" in result["result"]
