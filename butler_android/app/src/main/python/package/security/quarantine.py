import ast
import sys
import types
import inspect
import builtins
import functools
import opcode
import dis
import threading
import time
import gc
import collections
from collections.abc import Mapping
from types import CodeType, FunctionType

class SandboxError(Exception):
    """沙盒执行错误基类"""
    pass

class SecurityError(SandboxError):
    """安全违规错误"""
    pass

class TimeoutError(SandboxError):
    """执行超时错误"""
    pass

class ResourceLimitError(SandboxError):
    """资源限制错误"""
    pass

class RestrictedBuiltins(Mapping):
    """受限制的内置函数集合"""
    def __init__(self):
        # 允许的安全内置函数白名单
        self._safe_builtins = {
            'abs': abs,
            'all': all,
            'any': any,
            'ascii': ascii,
            'bin': bin,
            'bool': bool,
            'bytearray': bytearray,
            'bytes': bytes,
            'chr': chr,
            'complex': complex,
            'dict': dict,
            'dir': dir,
            'enumerate': enumerate,
            'filter': filter,
            'float': float,
            'format': format,
            'frozenset': frozenset,
            'hash': hash,
            'hex': hex,
            'int': int,
            'iter': iter,
            'len': len,
            'list': list,
            'map': map,
            'max': max,
            'min': min,
            'next': next,
            'oct': oct,
            'ord': ord,
            'pow': pow,
            'range': range,
            'repr': repr,
            'reversed': reversed,
            'round': round,
            'set': set,
            'slice': slice,
            'sorted': sorted,
            'str': str,
            'sum': sum,
            'tuple': tuple,
            'zip': zip,
            'type': type,
            'isinstance': isinstance,
            'issubclass': issubclass,
            'hasattr': hasattr,
            'getattr': getattr,
            'setattr': setattr,
            'delattr': delattr,
            'property': property,
            'staticmethod': staticmethod,
            'classmethod': classmethod,
            'super': super,
            'id': id,
            'vars': vars,
            'locals': locals,
            'globals': globals,
            '__build_class__': __build_class__,
            '__name__': '__main__',
            '__debug__': __debug__,
        }

    def __getitem__(self, key):
        if key in self._safe_builtins:
            return self._safe_builtins[key]
        raise SecurityError(f"访问受限内置函数 '{key}'")

    def __iter__(self):
        return iter(self._safe_builtins)

    def __len__(self):
        return len(self._safe_builtins)

class SafeImporter:
    """安全的模块导入器"""
    def __init__(self, allowed_modules=None):
        # 允许导入的模块白名单
        self.allowed_modules = allowed_modules or {
            'math', 'cmath', 'decimal', 'fractions', 'random', 'statistics',
            'datetime', 'calendar', 'collections', 'heapq', 'bisect', 'array',
            'queue', 'itertools', 'functools', 'operator', 'copy', 'pprint',
            'string', 're', 'json', 'struct', 'hashlib', 'hmac', 'secrets',
            'time', 'threading', 'contextlib', 'abc', 'atexit', 'logging',
            'typing', 'enum', 'numbers', 'html', 'xml', 'unicodedata', 'base64',
            'zlib', 'gzip', 'bz2', 'lzma', 'zipfile', 'tarfile', 'csv', 'configparser',
            'argparse', 'getopt', 'readline', 'getpass', 'cmd', 'shlex', 'sysconfig',
        }

        # 模块特定的允许属性（采用白名单机制）
        self.module_attributes = {
            'sys': {'version', 'version_info', 'platform', 'argv', 'path', 'modules'},
            'os': {'name', 'environ', 'pathsep', 'sep', 'linesep'},
        }

    def import_module(self, name, globals=None, locals=None, fromlist=(), level=0):
        """安全的模块导入函数"""
        # 严格限制：只允许从白名单中的模块导入[cite: 1]
        if name not in self.allowed_modules:
            raise SecurityError(f"禁止导入模块: {name}")

        # 实际导入模块
        module = __import__(name, globals, locals, fromlist, level)

        # 如果是从模块导入特定属性，检查这些属性是否在允许范围中
        if fromlist:
            # 1. 显式拦截 `from x import *`
            if '*' in fromlist:
                raise SecurityError(f"禁止使用 'from {name} import *' 通配符导入")

            for attr in fromlist:
                if attr.startswith('_'):
                    raise SecurityError(f"禁止访问以下划线开头的属性: {attr}")

                # 如果存在针对特定模块的属性白名单，则进行白名单匹配检查
                if name in self.module_attributes and attr not in self.module_attributes[name]:
                    raise SecurityError(f"禁止从模块 {name} 导入属性: {attr}")

        return module

class ASTValidator(ast.NodeVisitor):
    """AST 验证器，用于递归检查和限制代码结构"""

    def __init__(self):
        # 允许的节点类型白名单
        self.allowed_nodes = {
            # 模块和函数定义
            ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,

            # 控制流
            ast.If, ast.For, ast.AsyncFor, ast.While, ast.Break, ast.Continue,
            ast.Try, ast.With, ast.AsyncWith, ast.Raise, ast.Assert, ast.Pass,

            # 作用域和变量
            ast.Global, ast.Nonlocal, ast.Delete, ast.Assign, ast.AugAssign, ast.AnnAssign,
            ast.NamedExpr,

            # 表达式
            ast.Expr, ast.UnaryOp, ast.BinOp, ast.BoolOp, ast.Compare, ast.Call,
            ast.IfExp, ast.Attribute, ast.Subscript, ast.Starred, ast.Name, ast.Constant,
            ast.JoinedStr, ast.FormattedValue,

            # 集合
            ast.List, ast.Tuple, ast.Set, ast.Dict, ast.ListComp, ast.SetComp,
            ast.DictComp, ast.GeneratorExp,

            # 其他基础/必需节点
            ast.Slice, ast.comprehension, ast.arguments,
            ast.arg, ast.keyword, ast.alias, ast.withitem, ast.excepthandler,

            # 修复递归漏洞后引入的 AST 上下文基础节点 (Load / Store / Del)[cite: 1]
            ast.Load, ast.Store, ast.Del,
        }

        # 禁止的节点类型黑名单
        self.forbidden_nodes = {
            ast.Yield, ast.YieldFrom, ast.Await,  # 强制禁止异步生成器和部分特殊协程
        }

        # 禁止的函数和属性黑名单
        self.forbidden_calls = {
            'eval', 'exec', 'execfile', 'compile', 'input', 'open',
            'exit', 'quit', 'help', 'license', 'copyright', 'credits',
        }

        self.forbidden_attributes = {
            '__subclasses__', '__bases__', '__mro__', '__class__', '__dict__',
            '__globals__', '__closure__', '__code__', '__func__', '__self__',
            '__module__', '__builtins__', '__import__', '__getattribute__',
            '__getattr__', '__setattr__', '__delattr__', '__dir__', '__get__',
            '__set__', '__delete__', '__slots__', '__weakref__', '__next__',
            '__enter__', '__exit__', '__aenter__', '__aexit__', '__iter__',
            '__anext__', '__await__', '__call__', '__new__', '__init__',
            '__init_subclass__', '__prepare__', '__instancecheck__',
            '__subclasscheck__', '__getitem__', '__setitem__', '__delitem__',
            '__contains__', '__len__', '__reversed__', '__add__',
            '__sub__', '__mul__', '__matmul__', '__truediv__', '__floordiv__',
            '__mod__', '__divmod__', '__pow__', '__lshift__', '__rshift__',
            '__and__', '__xor__', '__or__', '__radd__', '__rsub__', '__rmul__',
            '__rmatmul__', '__rtruediv__', '__rfloordiv__', '__rmod__',
            '__rdivmod__', '__rpow__', '__rlshift__', '__rrshift__', '__rand__',
            '__rxor__', '__ror__', '__iadd__', '__isub__', '__imul__',
            '__imatmul__', '__itruediv__', '__ifloordiv__', '__imod__',
            '__ipow__', '__ilshift__', '__irshift__', '__iand__', '__ixor__',
            '__ior__', '__neg__', '__pos__', '__abs__', '__invert__', '__complex__',
            '__int__', '__float__', '__index__', '__round__', '__trunc__',
            '__floor__', '__ceil__', '__bool__', '__hash__', '__str__',
            '__repr__', '__bytes__', '__format__', '__lt__', '__le__', '__eq__',
            '__ne__', '__gt__', '__ge__', '__getnewargs__', '__getnewargs_ex__',
            '__getstate__', '__setstate__', '__reduce__', '__reduce_ex__',
            '__sizeof__', '__subclasshook__',
        }

    def validate(self, node):
        """执行 AST 递归验证入口"""
        self.visit(node)

    def visit(self, node):
        """覆盖基类的 visit 行为，对所有遍历到的节点进行拦截和白名单过滤[cite: 1]"""
        node_type = type(node)
        
        # 1. 节点类型必须在白名单内[cite: 1]
        if node_type not in self.allowed_nodes:
            raise SecurityError(f"禁止的语法结构: {node_type.__name__}")

        # 2. 节点类型不得在硬性黑名单内
        if node_type in self.forbidden_nodes:
            raise SecurityError(f"明确禁止的语法结构: {node_type.__name__}")

        # 继续向下递归子节点[cite: 1]
        return super().visit(node)

    def visit_Import(self, node):
        """检查 import xxx 语句"""
        for alias in node.names:
            if alias.name.startswith('_'):
                raise SecurityError(f"禁止导入以下划线开头的模块: {alias.name}")

            # 导入黑名单模块过滤（作为双重保护，实际加载端由 SafeImporter 负责把关）
            forbidden_modules = {'os', 'sys', 'io', 'socket', 'subprocess', 'ctypes',
                                'mmap', 'fcntl', 'select', 'selectors', 'signal',
                                'resource', 'pwd', 'grp', 'termios', 'tty', 'pty',
                                'posix', 'nt', '_winreg', 'winreg', 'msvcrt'}

            if alias.name in forbidden_modules:
                raise SecurityError(f"禁止导入模块: {alias.name}")

        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """检查 from xxx import yyy 语句[cite: 1]"""
        if node.module and node.module.startswith('_'):
            raise SecurityError(f"禁止从以下划线开头的模块导入: {node.module}")

        # 显式拦截 `from x import *`[cite: 1]
        for alias in node.names:
            if alias.name == '*':
                raise SecurityError(f"禁止使用 'from {node.module} import *' 通配符导入")

        forbidden_modules = {'os', 'sys', 'io', 'socket', 'subprocess', 'ctypes',
                            'mmap', 'fcntl', 'select', 'selectors', 'signal',
                            'resource', 'pwd', 'grp', 'termios', 'tty', 'pty',
                            'posix', 'nt', '_winreg', 'winreg', 'msvcrt'}

        if node.module in forbidden_modules:
            raise SecurityError(f"禁止从模块导入: {node.module}")

        # 检查具体导入的属性
        for alias in node.names:
            if alias.name.startswith('_'):
                raise SecurityError(f"禁止导入以下划线开头的属性: {alias.name}")

            if alias.name in self.forbidden_attributes:
                raise SecurityError(f"禁止导入属性: {alias.name}")

        self.generic_visit(node)

    def visit_Call(self, node):
        """检查函数与方法调用"""
        # 直接函数名调用限制
        if isinstance(node.func, ast.Name):
            if node.func.id in self.forbidden_calls:
                raise SecurityError(f"禁止调用函数: {node.func.id}")

        # 方法调用属性拦截
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in self.forbidden_calls:
                raise SecurityError(f"禁止调用方法: {node.func.attr}")

            if node.func.attr in self.forbidden_attributes:
                raise SecurityError(f"禁止调用方法: {node.func.attr}")

        self.generic_visit(node)

    def visit_Attribute(self, node):
        """检查属性访问"""
        if node.attr in self.forbidden_attributes:
            raise SecurityError(f"禁止访问属性: {node.attr}")

        self.generic_visit(node)

class BytecodeValidator:
    """版本安全的字节码验证器"""

    def __init__(self):
        # 1. 动态且版本安全地构建【允许操作码】白名单（不因 Python 版本迭代直接报错崩溃）[cite: 1]
        raw_allowed_names = {
            # 基础数据栈操作
            'POP_TOP', 'NOP', 'COPY', 'SWAP', 'PUSH_NULL',
            'ROT_TWO', 'ROT_THREE', 'ROT_FOUR', 'DUP_TOP', 'DUP_TOP_TWO',
            
            # 算术、一元和位运算（兼容现代 Python 将 BINARY_ADD 等合并为 BINARY_OP / BINARY_SUBSCR 的变动）
            'UNARY_POSITIVE', 'UNARY_NEGATIVE', 'UNARY_NOT', 'UNARY_INVERT',
            'BINARY_OP', 'BINARY_SUBSCR', 'STORE_SUBSCR', 'DELETE_SUBSCR',
            'BINARY_POWER', 'BINARY_MULTIPLY', 'BINARY_FLOOR_DIVIDE', 'BINARY_TRUE_DIVIDE',
            'BINARY_MODULO', 'BINARY_ADD', 'BINARY_SUBTRACT', 'BINARY_LSHIFT', 'BINARY_RSHIFT',
            'BINARY_AND', 'BINARY_XOR', 'BINARY_OR',
            'INPLACE_ADD', 'INPLACE_SUBTRACT', 'INPLACE_MULTIPLY', 'INPLACE_FLOOR_DIVIDE',
            'INPLACE_TRUE_DIVIDE', 'INPLACE_MODULO', 'INPLACE_POWER', 'INPLACE_LSHIFT',
            'INPLACE_RSHIFT', 'INPLACE_AND', 'INPLACE_XOR', 'INPLACE_OR',

            # 迭代、生成与类构造
            'GET_ITER', 'GET_YIELD_FROM_ITER', 'PRINT_EXPR', 'LOAD_BUILD_CLASS',
            'YIELD_FROM', 'SET_ADD', 'LIST_APPEND', 'MAP_ADD',
            
            # 变量加载与检索
            'LOAD_CONST', 'LOAD_NAME', 'LOAD_GLOBAL', 'LOAD_ATTR', 'LOAD_SUPER_ATTR',
            'COMPARE_OP', 'IS_OP', 'CONTAINS_OP',
            'IMPORT_NAME', 'IMPORT_FROM',
            
            # 分支跳转
            'JUMP_FORWARD', 'JUMP_BACKWARD', 'JUMP_IF_FALSE_OR_POP', 'JUMP_IF_TRUE_OR_POP',
            'POP_JUMP_IF_FALSE', 'POP_JUMP_IF_TRUE', 'POP_JUMP_IF_NONE', 'POP_JUMP_IF_NOT_NONE',
            'JUMP_ABSOLUTE',
            
            # 局部变量/闭包/异常控制
            'LOAD_FAST', 'STORE_FAST', 'DELETE_FAST', 'LOAD_FAST_CHECK', 'LOAD_FAST_AND_CLEAR',
            'LOAD_CLOSURE', 'LOAD_DEREF', 'STORE_DEREF', 'DELETE_DEREF', 'LOAD_FROM_DICT_OR_DEREF',
            'RAISE_VARARGS', 'RERAISE', 'PUSH_EXC_INFO', 'CHECK_EXC_MATCH', 'POP_EXCEPT',
            
            # 函数与方法调用（兼容现代 Python 3.11/3.12 引入的 CALL 族指令）
            'CALL', 'CALL_FUNCTION', 'CALL_FUNCTION_KW', 'CALL_FUNCTION_EX', 'CALL_KW',
            'LOAD_METHOD', 'CALL_METHOD', 'KW_NAMES',
            
            # 数据结构构造
            'LIST_EXTEND', 'SET_UPDATE', 'DICT_UPDATE', 'DICT_MERGE',
            'FORMAT_VALUE', 'BUILD_CONST_KEY_MAP', 'BUILD_STRING', 'BUILD_TUPLE',
            'BUILD_LIST', 'BUILD_SET', 'BUILD_MAP',
            
            # 其它
            'SETUP_ANNOTATIONS', 'LOAD_ASSERTION_ERROR', 'LIST_TO_TUPLE', 'RETURN_VALUE', 'RETURN_CONST'
        }

        # 2. 动态且版本安全地构建【绝对禁止操作码】黑名单[cite: 1]
        raw_forbidden_names = {
            'IMPORT_STAR',       # 显式阻止通配符导入
            'EXEC_STMT',         # 阻止古老的 exec 语句指令
            'BREAK_LOOP', 'CONTINUE_LOOP', 'SETUP_LOOP',  # 早期旧循环栈控制
            'SETUP_WITH', 'WITH_CLEANUP', 'WITH_CLEANUP_START', 'WITH_CLEANUP_FINISH',
            'SETUP_ASYNC_WITH', 'BEFORE_ASYNC_WITH', 'END_ASYNC_FOR',
            'SETUP_FINALLY', 'SETUP_EXCEPT', 'POP_BLOCK',
        }

        # 通过读取当前环境下的实际 opcode.opmap，动态转化名称为真实的机器码数字[cite: 1]
        self.allowed_opcodes = {
            opcode.opmap[name] for name in raw_allowed_names if name in opcode.opmap
        }
        self.forbidden_opcodes = {
            opcode.opmap[name] for name in raw_forbidden_names if name in opcode.opmap
        }

    def validate(self, code_obj):
        """遍历并验证字节码安全合法性[cite: 1]"""
        # 利用标准库 dis.get_instructions 遍历解析，并针对闭包、内部函数对象递归审查[cite: 1]
        instructions = dis.get_instructions(code_obj)

        for instr in instructions:
            # 1. 遭遇显式黑名单指令直接抛异常阻断
            if instr.opcode in self.forbidden_opcodes:
                raise SecurityError(f"使用了被绝对禁止的字节码指令: {instr.opname}")

            # 2. 如果不处于任何允许的白名单内，则判为安全越界
            if instr.opcode not in self.allowed_opcodes:
                raise SecurityError(f"未受信任的字节码指令: {instr.opname}")

        # 递归检查嵌套的代码对象（例如函数、列表推导、Lambda 内部）[cite: 1]
        for const in code_obj.co_consts:
            if isinstance(const, types.CodeType):
                self.validate(const)

class ResourceMonitor(threading.Thread):
    """资源监视器，用于监控代码执行的资源使用情况"""

    def __init__(self, interval=0.1, memory_limit=100*1024*1024, instruction_limit=1000000):
        super().__init__()
        self.interval = interval
        self.memory_limit = memory_limit
        self.instruction_limit = instruction_limit
        self.stop_event = threading.Event()
        self.instruction_count = 0
        self.max_memory = 0
        self.daemon = True

    def run(self):
        """监控资源使用"""
        while not self.stop_event.wait(self.interval):
            # 检查内存使用
            current_memory = self.get_memory_usage()
            self.max_memory = max(self.max_memory, current_memory)

            if current_memory > self.memory_limit:
                raise ResourceLimitError(f"内存使用超过限制: {current_memory} > {self.memory_limit}")

    def stop(self):
        """停止监控"""
        self.stop_event.set()

    def get_memory_usage(self):
        """获取当前内存使用量"""
        return len(gc.get_objects()) * 100  # 近似值

    def count_instruction(self):
        """计数指令执行"""
        self.instruction_count += 1
        if self.instruction_count > self.instruction_limit:
            raise ResourceLimitError(f"指令执行超过限制: {self.instruction_count} > {self.instruction_limit}")

class Sandbox:
    """Python 沙盒执行环境"""

    def __init__(self, timeout=30, memory_limit=100*1024*1024, instruction_limit=1000000):
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.instruction_limit = instruction_limit
        self.ast_validator = ASTValidator()
        self.bytecode_validator = BytecodeValidator()
        self.importer = SafeImporter()
        self.resource_monitor = ResourceMonitor(
            memory_limit=memory_limit,
            instruction_limit=instruction_limit
        )

    def create_restricted_globals(self):
        """创建受限制的全局变量环境"""
        restricted_globals = {
            '__builtins__': RestrictedBuiltins(),
            '__name__': '__main__',
            '__file__': None,
            '__package__': None,
            '__doc__': None,
            '__loader__': None,
            '__spec__': None,
            '__import__': self.importer.import_module,
        }
        return restricted_globals

    def execute(self, code, globals_dict=None, locals_dict=None):
        """
        在沙盒中执行代码

        Args:
            code (str): 要执行的Python代码
            globals_dict (dict): 全局变量字典，如果为None则使用受限环境
            locals_dict (dict): 局部变量字典

        Returns:
            执行结果

        Raises:
            SecurityError: 如果检测到安全违规
            TimeoutError: 如果执行超时
            ResourceLimitError: 如果资源使用超过限制
        """
        # 解析代码为AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise SandboxError(f"语法错误: {e}")

        # 验证AST (深度遍历，不漏掉任何隐藏分支)[cite: 1]
        self.ast_validator.validate(tree)

        # 编译AST
        try:
            code_obj = compile(tree, '<string>', 'exec')
        except Exception as e:
            raise SandboxError(f"编译错误: {e}")

        # 验证字节码 (动态探测的 3.12 安全指令集 + 递归检查嵌套代码)[cite: 1]
        self.bytecode_validator.validate(code_obj)

        # 准备执行环境
        if globals_dict is None:
            globals_dict = self.create_restricted_globals()

        if locals_dict is None:
            locals_dict = globals_dict

        # 启动资源监控
        self.resource_monitor.start()

        # 设置执行超时
        result = None
        exception = None

        def run_code():
            nonlocal result, exception
            try:
                # 执行代码
                exec(code_obj, globals_dict, locals_dict)
                result = (globals_dict, locals_dict)
            except Exception as e:
                exception = e

        # 在单独的线程中执行代码
        thread = threading.Thread(target=run_code)
        thread.daemon = True
        thread.start()

        # 等待执行完成或超时
        thread.join(self.timeout)

        # 停止资源监控
        self.resource_monitor.stop()

        # 检查执行结果
        if thread.is_alive():
            raise TimeoutError(f"执行超时: {self.timeout}秒")

        if exception:
            if isinstance(exception, SecurityError):
                raise exception
            elif isinstance(exception, ResourceLimitError):
                raise exception
            else:
                raise SandboxError(f"执行错误: {exception}")

        return result

# 示例使用
if __name__ == '__main__':
    # 创建沙盒实例
    sandbox = Sandbox(timeout=10, memory_limit=50*1024*1024, instruction_limit=500000)
