import asyncio
import base64
import math
import os
import platform
import shlex
import shutil
import tempfile
import time
from enum import StrEnum
from pathlib import Path
from typing import Literal, TypedDict
from uuid import uuid4

# 导入 PyAutoGUI 用于计算机控制
import pyautogui
try:
    from deepseek.types.beta import BetaToolComputerUse20241022Param  # DeepSeek API 类型
except ImportError:
    BetaToolComputerUse20241022Param = dict

from .base import BaseDeepSeekTool, ToolError, ToolResult
from .run import run

# 常量定义
OUTPUT_DIR = "/tmp/outputs"                  # 临时输出目录
TYPING_DELAY_MS = 12                         # 打字延迟（毫秒）
TYPING_GROUP_SIZE = 50                       # 分组打字大小

# 支持的操作类型枚举
Action = Literal[
    "key",                # 按键操作
    "type",               # 文本输入
    "mouse_move",         # 鼠标移动
    "left_click",         # 左键单击
    "left_click_drag",    # 左键拖拽
    "right_click",        # 右键单击
    "middle_click",       # 中键单击
    "double_click",       # 双击
    "screenshot",         # 截屏
    "cursor_position",    # 获取光标位置
]

# 分辨率类型定义
class Resolution(TypedDict):
    width: int   # 宽度
    height: int  # 高度

# 最大缩放目标分辨率
MAX_SCALING_TARGETS: dict[str, Resolution] = {
    "XGA": Resolution(width=1024, height=768),    # 4:3 标准分辨率
    "WXGA": Resolution(width=1280, height=800),   # 16:10 宽屏
    "FWXGA": Resolution(width=1366, height=768),  # ~16:9 全高清
}

# 缩放来源枚举
class ScalingSource(StrEnum):
    COMPUTER = "computer"  # 来自计算机
    API = "api"            # 来自API

# 计算机工具选项
class ComputerToolOptions(TypedDict):
    display_height_px: int      # 显示高度(像素)
    display_width_px: int       # 显示宽度(像素)
    display_number: int | None  # 显示器编号

# 字符串分块函数
def chunks(s: str, chunk_size: int) -> list[str]:
    """将字符串分割成指定大小的块"""
    return [s[i : i + chunk_size] for i in range(0, len(s), chunk_size)]

# 平滑移动鼠标函数
def smooth_move_to(x, y, duration=1.2):
    """实现鼠标平滑移动到目标位置
    
    参数:
        x, y: 目标坐标
        duration: 移动持续时间(秒)
    """
    start_x, start_y = pyautogui.position()  # 获取起始位置
    dx = x - start_x
    dy = y - start_y
    
    start_time = time.time()
    
    # 使用缓动函数实现平滑移动
    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time > duration:
            break
            
        t = elapsed_time / duration
        # 使用正弦缓动函数 (easeInOutSine)
        eased_t = (1 - math.cos(t * math.pi)) / 2
        
        # 计算中间位置
        target_x = start_x + dx * eased_t
        target_y = start_y + dy * eased_t
        pyautogui.moveTo(target_x, target_y)
    
    # 确保到达目标位置
    pyautogui.moveTo(x, y)

# 计算机工具类
class ComputerTool(BaseDeepSeekTool):
    """DeepSeek计算机交互工具
    
    允许代理通过DeepSeek API控制主显示器的屏幕、键盘和鼠标
    """
    
    name: Literal["computer"] = "computer"  # 工具名称
    api_type: Literal["computer_20241022"] = "computer_20241022"  # API类型
    width: int  # 屏幕宽度
    height: int  # 屏幕高度
    display_num: None  # 显示器编号（简化为主显示器）
    
    # 配置参数
    _screenshot_delay = 2.0  # 截图延迟(秒)
    _scaling_enabled = True   # 启用坐标缩放

    @property
    def options(self) -> ComputerToolOptions:
        """获取工具选项配置"""
        width, height = self.scale_coordinates(
            ScalingSource.COMPUTER, self.width, self.height
        )
        return {
            "display_width_px": width,
            "display_height_px": height,
            "display_number": self.display_num,
        }

    def to_params(self) -> BetaToolComputerUse20241022Param:
        """转换为DeepSeek API参数格式"""
        return {"name": self.name, "type": self.api_type, **self.options}

    def __init__(self):
        """初始化工具，获取屏幕分辨率"""
        super().__init__()
        self.width, self.height = pyautogui.size()  # 获取屏幕尺寸
        self.display_num = None

    async def __call__(
        self,
        *,
        action: Action,  # 操作类型
        text: str | None = None,  # 文本内容
        coordinate: tuple[int, int] | None = None,  # 坐标
        **kwargs,
    ):
        """执行计算机操作
        
        参数:
            action: 操作类型
            text: 文本内容（用于键盘输入）
            coordinate: 坐标位置（用于鼠标操作）
        """
        # 鼠标移动和拖拽操作
        if action in ("mouse_move", "left_click_drag"):
            if coordinate is None:
                raise ToolError(f"{action}操作需要坐标参数")
            # 缩放坐标
            x, y = self.scale_coordinates(
                ScalingSource.API, coordinate[0], coordinate[1]
            )
            
            if action == "mouse_move":
                smooth_move_to(x, y)  # 平滑移动鼠标
            elif action == "left_click_drag":
                smooth_move_to(x, y)
                pyautogui.dragTo(x, y, button="left")  # 左键拖拽
        
        # 键盘操作
        elif action in ("key", "type"):
            if text is None:
                raise ToolError(f"{action}操作需要文本参数")
                
            if action == "key":
                # macOS特殊处理
                if platform.system() == "Darwin":
                    text = text.replace("super+", "command+")
                
                # 按键名称标准化
                def normalize_key(key):
                    """标准化按键名称"""
                    key = key.lower().replace("_", "")
                    key_map = {
                        "pagedown": "pgdn",
                        "pageup": "pgup",
                        "enter": "return",
                        "return": "enter",
                    }
                    return key_map.get(key, key)
                
                keys = [normalize_key(k) for k in text.split("+")]
                
                # 组合键处理
                if len(keys) > 1:
                    if "darwin" in platform.system().lower():
                        # macOS使用AppleScript处理组合键
                        keystroke, modifier = (keys[-1], "+".join(keys[:-1]))
                        modifier = modifier.lower() + " down"
                        if keystroke.lower() == "space":
                            keystroke = " "
                        elif keystroke.lower() == "enter":
                            keystroke = "\n"
                        # Standardize modifiers for AppleScript
                        mod_map = {"command": "command", "control": "control", "option": "option", "shift": "shift"}
                        mods = [mod_map.get(m.lower(), m) for m in keys[:-1]]
                        mod_string = "{" + ", ".join([f"{m} down" for m in mods]) + "}"

                        script = f'tell application "System Events" to keystroke "{keystroke}" using {mod_string}'
                        subprocess.run(["osascript", "-e", script], check=False)
                    else:
                        pyautogui.hotkey(*keys)  # 其他系统直接使用hotkey
                else:
                    pyautogui.press(keys[0])  # 单键按下
            
            elif action == "type":
                # 模拟真实打字
                pyautogui.write(text, interval=TYPING_DELAY_MS / 1000)
        
        # 鼠标点击操作
        elif action in ("left_click", "right_click", "double_click", "middle_click"):
            time.sleep(0.1)  # 短暂延迟
            button_map = {
                "left_click": "left",
                "right_click": "right",
                "middle_click": "middle",
            }
            
            if action == "double_click":
                pyautogui.click()  # 双击
                time.sleep(0.1)
                pyautogui.click()
            else:
                pyautogui.click(button=button_map.get(action, "left"))  # 单次点击
        
        # 截屏操作
        elif action == "screenshot":
            return await self.screenshot()
        
        # 获取光标位置
        elif action == "cursor_position":
            x, y = pyautogui.position()
            # 缩放坐标返回
            x, y = self.scale_coordinates(ScalingSource.COMPUTER, x, y)
            return ToolResult(output=f"X={x},Y={y}")
        
        else:
            raise ToolError(f"无效操作: {action}")
        
        # 操作后截屏（光标位置操作除外）
        if action != "cursor_position":
            return await self.screenshot()

    async def screenshot(self):
        """截取屏幕并返回base64编码的图像"""
        temp_dir = Path(tempfile.gettempdir())
        path = temp_dir / f"screenshot_{uuid4().hex}.png"  # 生成唯一文件名
        
        # 截屏并保存
        screenshot = pyautogui.screenshot()
        screenshot.save(str(path))
        
        # 缩放处理
        if self._scaling_enabled:
            x, y = self.scale_coordinates(
                ScalingSource.COMPUTER, self.width, self.height
            )
            # 使用PIL缩放图像
            from PIL import Image
            with Image.open(path) as img:
                img = img.resize((x, y), Image.Resampling.LANCZOS)
                img.save(path)
        
        # 返回base64编码
        if path.exists():
            base64_image = base64.b64encode(path.read_bytes()).decode()
            path.unlink()  # 删除临时文件
            return ToolResult(base64_image=base64_image)
        raise ToolError("截屏失败")

    async def shell(self, command: str, take_screenshot=True) -> ToolResult:
        """执行Shell命令并返回结果
        
        参数:
            command: 要执行的命令
            take_screenshot: 是否在命令执行后截屏
        """
        _, stdout, stderr = await run(command)
        base64_image = None
        
        if take_screenshot:
            # 延迟后截屏
            await asyncio.sleep(self._screenshot_delay)
            base64_image = (await self.screenshot()).base64_image
        
        return ToolResult(output=stdout, error=stderr, base64_image=base64_image)

    def scale_coordinates(self, source: ScalingSource, x: int, y: int):
        """坐标缩放处理
        
        参数:
            source: 坐标来源
            x, y: 原始坐标
        返回:
            缩放后的坐标
        """
        if not self._scaling_enabled:
            return x, y
        
        # 计算屏幕宽高比
        ratio = self.width / self.height
        target_dimension = None
        
        # 查找匹配的目标分辨率
        for dimension in MAX_SCALING_TARGETS.values():
            if abs(dimension["width"] / dimension["height"] - ratio) < 0.02:
                if dimension["width"] < self.width:
                    target_dimension = dimension
                break
        
        if target_dimension is None:
            return x, y
        
        # 计算缩放因子
        x_scaling_factor = target_dimension["width"] / self.width
        y_scaling_factor = target_dimension["height"] / self.height
        
        if source == ScalingSource.API:
            # API坐标 -> 计算机坐标（放大）
            if x > self.width or y > self.height:
                raise ToolError(f"坐标 {x}, {y} 超出范围")
            return round(x / x_scaling_factor), round(y / y_scaling_factor)
        else:
            # 计算机坐标 -> API坐标（缩小）
            return round(x * x_scaling_factor), round(y * y_scaling_factor)
