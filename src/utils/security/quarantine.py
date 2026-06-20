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
        
        # 模块特定的允许属性
        self.module_attributes = {
            'sys': {'version', 'version_info', 'platform', 'argv', 'path', 'modules'},
            'os': {'name', 'environ', 'pathsep', 'sep', 'linesep'},
        }
    
    def import_module(self, name, globals=None, locals=None, fromlist=(), level=0):
        """安全的模块导入函数"""
        # 检查模块是否允许导入
        if name not in self.allowed_modules:
            raise SecurityError(f"禁止导入模块: {name}")
        
        # 实际导入模块
        module = __import__(name, globals, locals, fromlist, level)
        
        # 如果是从模块导入特定属性，检查这些属性是否允许
        if fromlist:
            for attr in fromlist:
                if attr.startswith('_'):
                    raise SecurityError(f"禁止访问以下划线开头的属性: {attr}")
                
                # 检查模块特定的属性限制
                if name in self.module_attributes and attr not in self.module_attributes[name]:
                    raise SecurityError(f"禁止从模块 {name} 导入属性: {attr}")
        
        return module

class ASTValidator(ast.NodeVisitor):
    """AST 验证器，用于检查和限制代码结构"""
    
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
            
            # 其他
            ast.Slice, ast.Index, ast.ExtSlice, ast.comprehension, ast.arguments,
            ast.arg, ast.keyword, ast.alias, ast.withitem, ast.excepthandler,
        }
        
        # 禁止的节点类型黑名单
        self.forbidden_nodes = {
            ast.Yield, ast.YieldFrom, ast.Await,  # 生成器和协程
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
            '__contains__', '__len__', '__iter__', '__reversed__', '__add__',
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
            '__sizeof__', '__dir__', '__init__', '__subclasshook__',
        }
    
    def validate(self, node):
        """验证 AST 节点"""
        if type(node) not in self.allowed_nodes:
            raise SecurityError(f"禁止的语法结构: {type(node).__name__}")
        
        if type(node) in self.forbidden_nodes:
            raise SecurityError(f"明确禁止的语法结构: {type(node).__name__}")
        
        self.generic_visit(node)
    
    def visit_Import(self, node):
        """检查导入语句"""
        for alias in node.names:
            if alias.name.startswith('_'):
                raise SecurityError(f"禁止导入以下划线开头的模块: {alias.name}")
            
            # 检查模块黑名单
            forbidden_modules = {'os', 'sys', 'io', 'socket', 'subprocess', 'ctypes',
                                'mmap', 'fcntl', 'select', 'selectors', 'signal',
                                'resource', 'pwd', 'grp', 'termios', 'tty', 'pty',
                                'fcntl', 'posix', 'nt', '_winreg', 'winreg', 'msvcrt'}
            
            if alias.name in forbidden_modules:
                raise SecurityError(f"禁止导入模块: {alias.name}")
        
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """检查从模块导入语句"""
        if node.module and node.module.startswith('_'):
            raise SecurityError(f"禁止从以下划线开头的模块导入: {node.module}")
        
        # 检查模块黑名单
        forbidden_modules = {'os', 'sys', 'io', 'socket', 'subprocess', 'ctypes',
                            'mmap', 'fcntl', 'select', 'selectors', 'signal',
                            'resource', 'pwd', 'grp', 'termios', 'tty', 'pty',
                            'fcntl', 'posix', 'nt', '_winreg', 'winreg', 'msvcrt'}
        
        if node.module in forbidden_modules:
            raise SecurityError(f"禁止从模块导入: {node.module}")
        
        # 检查导入的属性
        for alias in node.names:
            if alias.name.startswith('_'):
                raise SecurityError(f"禁止导入以下划线开头的属性: {alias.name}")
            
            if alias.name in self.forbidden_attributes:
                raise SecurityError(f"禁止导入属性: {alias.name}")
        
        self.generic_visit(node)
    
    def visit_Call(self, node):
        """检查函数调用"""
        # 检查直接调用危险函数
        if isinstance(node.func, ast.Name):
            if node.func.id in self.forbidden_calls:
                raise SecurityError(f"禁止调用函数: {node.func.id}")
        
        # 检查调用危险方法
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
    """字节码验证器，用于检查和过滤危险操作码"""
    
    def __init__(self):
        # 允许的操作码白名单
        self.allowed_opcodes = {
            opcode.opmap['POP_TOP'],
            opcode.opmap['ROT_TWO'],
            opcode.opmap['ROT_THREE'],
            opcode.opmap['DUP_TOP'],
            opcode.opmap['DUP_TOP_TWO'],
            opcode.opmap['NOP'],
            opcode.opmap['UNARY_POSITIVE'],
            opcode.opmap['UNARY_NEGATIVE'],
            opcode.opmap['UNARY_NOT'],
            opcode.opmap['UNARY_INVERT'],
            opcode.opmap['BINARY_POWER'],
            opcode.opmap['BINARY_MULTIPLY'],
            opcode.opmap['BINARY_FLOOR_DIVIDE'],
            opcode.opmap['BINARY_TRUE_DIVIDE'],
            opcode.opmap['BINARY_MODULO'],
            opcode.opmap['BINARY_ADD'],
            opcode.opmap['BINARY_SUBTRACT'],
            opcode.opmap['BINARY_SUBSCR'],
            opcode.opmap['BINARY_LSHIFT'],
            opcode.opmap['BINARY_RSHIFT'],
            opcode.opmap['BINARY_AND'],
            opcode.opmap['BINARY_XOR'],
            opcode.opmap['BINARY_OR'],
            opcode.opmap['INPLACE_ADD'],
            opcode.opmap['INPLACE_SUBTRACT'],
            opcode.opmap['INPLACE_MULTIPLY'],
            opcode.opmap['INPLACE_FLOOR_DIVIDE'],
            opcode.opmap['INPLACE_TRUE_DIVIDE'],
            opcode.opmap['INPLACE_MODULO'],
            opcode.opmap['INPLACE_POWER'],
            opcode.opmap['INPLACE_LSHIFT'],
            opcode.opmap['INPLACE_RSHIFT'],
            opcode.opmap['INPLACE_AND'],
            opcode.opmap['INPLACE_XOR'],
            opcode.opmap['INPLACE_OR'],
            opcode.opmap['STORE_SUBSCR'],
            opcode.opmap['DELETE_SUBSCR'],
            opcode.opmap['GET_ITER'],
            opcode.opmap['GET_YIELD_FROM_ITER'],
            opcode.opmap['PRINT_EXPR'],
            opcode.opmap['LOAD_BUILD_CLASS'],
            opcode.opmap['YIELD_FROM'],
            opcode.opmap['SET_ADD'],
            opcode.opmap['LIST_APPEND'],
            opcode.opmap['MAP_ADD'],
            opcode.opmap['LOAD_CONST'],
            opcode.opmap['LOAD_NAME'],
            opcode.opmap['LOAD_GLOBAL'],
            opcode.opmap['LOAD_ATTR'],
            opcode.opmap['COMPARE_OP'],
            opcode.opmap['IMPORT_NAME'],
            opcode.opmap['IMPORT_FROM'],
            opcode.opmap['JUMP_FORWARD'],
            opcode.opmap['JUMP_IF_FALSE_OR_POP'],
            opcode.opmap['JUMP_IF_TRUE_OR_POP'],
            opcode.opmap['JUMP_ABSOLUTE'],
            opcode.opmap['POP_JUMP_IF_FALSE'],
            opcode.opmap['POP_JUMP_IF_TRUE'],
            opcode.opmap['LOAD_FAST'],
            opcode.opmap['STORE_FAST'],
            opcode.opmap['DELETE_FAST'],
            opcode.opmap['LOAD_CLOSURE'],
            opcode.opmap['LOAD_DEREF'],
            opcode.opmap['STORE_DEREF'],
            opcode.opmap['DELETE_DEREF'],
            opcode.opmap['RAISE_VARARGS'],
            opcode.opmap['CALL_FUNCTION'],
            opcode.opmap['CALL_FUNCTION_KW'],
            opcode.opmap['CALL_FUNCTION_EX'],
            opcode.opmap['LOAD_METHOD'],
            opcode.opmap['CALL_METHOD'],
            opcode.opmap['LIST_EXTEND'],
            opcode.opmap['SET_UPDATE'],
            opcode.opmap['DICT_UPDATE'],
            opcode.opmap['DICT_MERGE'],
            opcode.opmap['FORMAT_VALUE'],
            opcode.opmap['BUILD_CONST_KEY_MAP'],
            opcode.opmap['BUILD_STRING'],
            opcode.opmap['BUILD_TUPLE'],
            opcode.opmap['BUILD_LIST'],
            opcode.opmap['BUILD_SET'],
            opcode.opmap['BUILD_MAP'],
            opcode.opmap['SETUP_ANNOTATIONS'],
            opcode.opmap['LOAD_ASSERTION_ERROR'],
            opcode.opmap['LIST_TO_TUPLE'],
        }
        
        # 禁止的操作码黑名单
        self.forbidden_opcodes = {
            opcode.opmap['IMPORT_STAR'],  # 禁止from module import *
            opcode.opmap['EXEC_STMT'],    # 禁止exec语句
            opcode.opmap['BREAK_LOOP'],   # 禁止break循环
            opcode.opmap['CONTINUE_LOOP'],# 禁止continue循环
            opcode.opmap['SETUP_WITH'],   # 禁止with语句
            opcode.opmap['WITH_CLEANUP'], # 禁止with语句
            opcode.opmap['SETUP_ASYNC_WITH'], # 禁止async with语句
            opcode.opmap['BEFORE_ASYNC_WITH'], # 禁止async with语句
            opcode.opmap['END_ASYNC_FOR'], # 禁止async for语句
            opcode.opmap['SETUP_FINALLY'], # 禁止try/finally语句
            opcode.opmap['POP_BLOCK'],    # 禁止块操作
            opcode.opmap['SETUP_EXCEPT'], # 禁止try/except语句
            opcode.opmap['SETUP_LOOP'],   # 禁止循环
        }
    
    def validate(self, code_obj):
        """验证字节码"""
        instructions = dis.get_instructions(code_obj)
        
        for instr in instructions:
            if instr.opcode in self.forbidden_opcodes:
                raise SecurityError(f"禁止的操作码: {instr.opname}")
            
            if instr.opcode not in self.allowed_opcodes:
                raise SecurityError(f"不允许的操作码: {instr.opname}")

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
        # 这是一个简化的实现，实际中可能需要更精确的内存监控
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
        
        # 验证AST
        try:
            self.ast_validator.validate(tree)
        except SecurityError as e:
            raise e
        
        # 编译AST
        try:
            code_obj = compile(tree, '<string>', 'exec')
        except Exception as e:
            raise SandboxError(f"编译错误: {e}")
        
        # 验证字节码
        try:
            self.bytecode_validator.validate(code_obj)
        except SecurityError as e:
            raise e
        
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
