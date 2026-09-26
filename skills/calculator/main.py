"""Butler Calculator Skill - Safe expression evaluator and unit converter."""
import ast
import math
import operator
from typing import Any, Dict

logger_name = "calculator"

# 安全的运算符白名单
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# 允许的常量
_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
}

# 允许的函数
_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "exp": math.exp,
}


def _safe_eval(node):
    """递归求值 AST 节点，只允许白名单内的运算。"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"不支持的常量类型: {type(node.value).__name__}")
    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise ValueError(f"未定义的变量: {node.id}")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise ValueError(f"不支持的运算符: {op_type.__name__}")
        return _BIN_OPS[op_type](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"不支持的一元运算符: {op_type.__name__}")
        return _UNARY_OPS[op_type](_safe_eval(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("只支持直接函数调用")
        fname = node.func.id
        if fname not in _FUNCTIONS:
            raise ValueError(f"未定义的函数: {fname}")
        args = [_safe_eval(a) for a in node.args]
        if node.keywords:
            raise ValueError("不支持关键字参数")
        return _FUNCTIONS[fname](*args)
    raise ValueError(f"不支持的语法节点: {type(node).__name__}")


def calculate(expression: str) -> str:
    """安全求值数学表达式。"""
    if not expression or not expression.strip():
        return "错误：表达式不能为空。"
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(tree)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"= {result}"
    except (SyntaxError, ValueError) as e:
        return f"错误：{str(e)}"
    except ZeroDivisionError:
        return "错误：除数不能为零。"
    except Exception as e:
        return f"计算出错：{str(e)}"


# 单位换算表 (统一到基准单位)
_LENGTH = {
    "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
    "inch": 0.0254, "in": 0.0254, "foot": 0.3048, "ft": 0.3048,
    "yard": 0.9144, "yd": 0.9144, "mile": 1609.344, "mi": 1609.344,
}
_WEIGHT = {
    "mg": 0.000001, "g": 0.001, "kg": 1.0, "t": 1000.0,
    "oz": 0.0283495, "lb": 0.453592,
}
_TIME = {
    "ms": 0.001, "s": 1.0, "min": 60.0, "minute": 60.0,
    "hour": 3600.0, "h": 3600.0, "day": 86400.0, "d": 86400.0,
}
_DATA = {
    "b": 1.0, "kb": 1024.0, "mb": 1024.0 ** 2, "gb": 1024.0 ** 3,
    "tb": 1024.0 ** 4, "pb": 1024.0 ** 5,
}
_SPEED = {
    "m/s": 1.0, "km/h": 1 / 3.6, "mph": 0.44704, "knot": 0.514444,
}

_UNIT_CATEGORIES = [_LENGTH, _WEIGHT, _TIME, _DATA, _SPEED]


def _find_category(unit: str):
    for cat in _UNIT_CATEGORIES:
        if unit in cat:
            return cat
    return None


def convert(value: float, from_unit: str, to_unit: str) -> str:
    """单位换算。"""
    from_unit = from_unit.strip().lower()
    to_unit = to_unit.strip().lower()

    # 温度特殊处理
    _TEMP = {"celsius", "c", "℃", "fahrenheit", "f", "℉", "kelvin", "k"}
    if from_unit in _TEMP or to_unit in _TEMP:
        return _convert_temperature(value, from_unit, to_unit)

    from_cat = _find_category(from_unit)
    to_cat = _find_category(to_unit)

    if from_cat is None or to_cat is None:
        return f"错误：不支持的单位 '{from_unit}' 或 '{to_unit}'。"
    if from_cat is not to_cat:
        return f"错误：'{from_unit}' 和 '{to_unit}' 不属于同一类别，无法换算。"

    base = value * from_cat[from_unit]
    result = base / to_cat[to_unit]
    return f"{value} {from_unit} = {result:g} {to_unit}"


def _convert_temperature(value: float, from_u: str, to_u: str) -> str:
    """温度换算。"""
    # 归一化
    fn = from_u
    tn = to_u
    if fn in ("celsius", "c", "℃"):
        celsius = value
    elif fn in ("fahrenheit", "f", "℉"):
        celsius = (value - 32) * 5 / 9
    elif fn in ("kelvin", "k"):
        celsius = value - 273.15
    else:
        return f"错误：不支持的温度单位 '{from_u}'。"

    if tn in ("celsius", "c", "℃"):
        result = celsius
    elif tn in ("fahrenheit", "f", "℉"):
        result = celsius * 9 / 5 + 32
    elif tn in ("kelvin", "k"):
        result = celsius + 273.15
    else:
        return f"错误：不支持的温度单位 '{to_u}'。"

    return f"{value} {from_u} = {result:g} {to_u}"


def handle_request(action: str, **kwargs) -> Any:
    """Butler 技能入口。"""
    if action in ("calculate", "calc", "eval", "run"):
        expr = kwargs.get("expression") or kwargs.get("expr") or kwargs.get("input", "")
        return calculate(expr)

    if action in ("convert", "conversion"):
        value = kwargs.get("value")
        from_unit = kwargs.get("from") or kwargs.get("from_unit", "")
        to_unit = kwargs.get("to") or kwargs.get("to_unit", "")
        if value is None:
            return "错误：请提供 value 参数。"
        try:
            value = float(value)
        except (TypeError, ValueError):
            return f"错误：'{value}' 不是有效的数值。"
        return convert(value, from_unit, to_unit)

    # 兼容直接传入表达式字符串的情况
    if not action or action == "help":
        return (
            "### 🧮 Butler 全能计算器\n\n"
            "**数学求值** (action: `calculate`):\n"
            "- 支持 + - * / % // ** 以及括号\n"
            "- 常量: pi, e, tau\n"
            "- 函数: sin, cos, tan, log, sqrt, abs, round, floor, ceil 等\n"
            "- 示例: `sin(pi/2) + sqrt(16)`\n\n"
            "**单位换算** (action: `convert`):\n"
            "- 长度: mm, cm, m, km, inch, foot, mile\n"
            "- 重量: mg, g, kg, t, oz, lb\n"
            "- 温度: celsius, fahrenheit, kelvin\n"
            "- 存储: B, KB, MB, GB, TB\n"
            "- 时间: ms, s, min, hour, day\n"
            "- 示例: value=100, from=km, to=mile"
        )

    # 兜底：如果 action 本身像表达式，尝试计算
    return calculate(action)
