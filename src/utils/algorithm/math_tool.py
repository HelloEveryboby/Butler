import math

# 自定义四舍五入函数
def custom_round(x, decimal_places=2):
    str_x = f"{x:.10f}"
    before_decimal = str_x.split('.')[0]
    after_decimal = str_x.split('.')[1]
    leading_zeros = len(after_decimal) - len(after_decimal.lstrip('0'))
    
    if leading_zeros >= 1 and before_decimal == "0":
        return round(x, leading_zeros + 2)
    else:
        return round(x, decimal_places)

# 科学计数法转换为十进制
def scito_decimal(sci_str):
    def split_exponent(number_str):
        parts = number_str.split("e")
        coefficient = parts[0]
        exponent = int(parts[1]) if len(parts) == 2 else 0
        return coefficient, exponent

    def multiplyby_10(number_str, exponent):
        if exponent == 0:
            return number_str

        if exponent > 0:
            index = number_str.index(".") if "." in number_str else len(number_str)
            number_str = number_str.replace(".", "")
            new_index = index + exponent
            number_str += "0" * (new_index - len(number_str))
            if new_index < len(number_str):
                number_str = number_str[:new_index] + "." + number_str[new_index:]
            return number_str

        if exponent < 0:
            index = number_str.index(".") if "." in number_str else len(number_str)
            number_str = number_str.replace(".", "")
            new_index = index + exponent
            number_str = "0" * (-new_index) + number_str
            number_str = "0." + number_str
            return number_str

    coefficient, exponent = split_exponent(sci_str)
    decimal_str = multiplyby_10(coefficient, exponent)

    # 去除尾随零
    if "." in decimal_str:
        decimal_str = decimal_str.rstrip("0")

    return decimal_str

# 将结果归一化为小数点后2位并删除后面的零
def normalize(res, round_to=2):
        # 我们把结果四舍五入到小数点后两位
        res = custom_round(res, round_to)
        res = str(res)
        if "." in res:
            while res[-1] == "0":
                res = res[:-1]
            res = res.strip(".")
        
        # scientific notation
        if "e" in res:
            res = scito_decimal(res)

        return res

# 加法
def add_(args):
    if not all(isinstance(arg, (int, float)) for arg in args):
        raise TypeError("所有参数必须是数字")
    return normalize(sum(args))

# 减法
def subtract_(args):
    if not all(isinstance(arg, (int, float)) for arg in args):
        raise TypeError("所有参数必须是数字")
    res = args[0]
    for arg in args[1:]:
        res -= arg
    return normalize(res)

# 乘法
def multiply_(args):
    if not all(isinstance(arg, (int, float)) for arg in args):
        raise TypeError("所有参数必须是数字")
    res = args[0]
    for arg in args[1:]:
        res *= arg
    return normalize(res)

# 除法
def divide_(args):

    res = args[0]
    for arg in args[1:]:
        res /= arg
    return normalize(res)

# 幂
def power_(args):
        
    res = args[0]
    for arg in args[1:]:
        res **= arg
    return normalize(res)

# 平方根
def sqrt_(args):
    res = args[0]
    return normalize(math.sqrt(res))

# 对数
def log_(args):
    # if only one argument is passed, it is 10th log
    if len(args) == 1:
        res = args[0]
        return normalize(math.log10(res))
    # if two arguments are passed, it is log with base as the second argument   
    elif len(args) == 2:
        res = args[0]
        base = args[1]
        return normalize(math.log(res, base))
    else:
        raise Exception("Invalid number of arguments passed to log function")

# 自然对数
def ln_(args):
    res = args[0]
    return normalize(math.log(res))

# 绝对值
def abs_(args):
    if len(args) != 1:
        raise ValueError("绝对值只接受一个参数")
    return normalize(abs(args[0]))

# 三角函数
def sin_(args):
    if len(args) != 1:
        raise ValueError("正弦只接受一个参数")
    return normalize(math.sin(args[0]))

def cos_(args):
    if len(args) != 1:
        raise ValueError("余弦只接受一个参数")
    return normalize(math.cos(args[0]))

def tan_(args):
    if len(args) != 1:
        raise ValueError("正切只接受一个参数")
    return normalize(math.tan(args[0]))

# 反三角函数
def arcsin_(args):
    if len(args) != 1:
        raise ValueError("反正弦只接受一个参数")
    return normalize(math.asin(args[0]))

def arccos_(args):
    if len(args) != 1:
        raise ValueError("反余弦只接受一个参数")
    return normalize(math.acos(args[0]))

def arctan_(args):
    if len(args) != 1:
        raise ValueError("反正切只接受一个参数")
    return normalize(math.atan(args[0]))

# 指数函数
def exp_(args):
    if len(args) != 1:
        raise ValueError("指数函数只接受一个参数")
    return normalize(math.exp(args[0]))

# 组合
def choose_(args):
    n = args[0]
    r = args[1]
    return normalize(math.comb(n, r))

# 排列
def permutate_(args):
    n = args[0]
    r = args[1]
    return normalize(math.perm(n, r))

# 最大公约数
def gcd_(args):
    res = args[0]
    for arg in args[1:]:
        res = math.gcd(res, arg)
    return normalize(res)

# 最小公倍数
def lcm_(args):
    res = args[0]
    for arg in args[1:]:
        res = res * arg // math.gcd(res, arg)
    return normalize(res)

# 余数
def remainder_(args):
    dividend = args[0]
    divisor = args[1]
    return normalize(dividend % divisor)

# 平均值
def mean_(args):
    if not all(isinstance(arg, (int, float)) for arg in args):
        raise TypeError("所有参数必须是数字")
    return normalize(sum(args) / len(args))

# 标准差 (Welford's algorithm for numerical stability)
def stddev_(args):
    if not all(isinstance(arg, (int, float)) for arg in args):
        raise TypeError("所有参数必须是数字")
    n = 0
    mean = 0.0
    m2 = 0.0
    for x in args:
        n += 1
        delta = x - mean
        mean += delta / n
        delta2 = x - mean
        m2 += delta * delta2

    if n < 2:
        return 0.0

    variance = m2 / n
    return normalize(math.sqrt(variance))

# n次方根
def nth_root(args):
    if len(args) != 2 or args[1] <= 0:
        raise ValueError("n次方根函数接受两个参数，且n必须为正数")
    return normalize(args[0] ** (1 / args[1]))
