"""ColorStr 颜色字符串模块

该模块提供用于终端显示的带有 字体颜色[、背景色、字体粗亮/细暗样式] 的字符串的函数。

颜色参数的可选项：
    'RED': 红色; 'LIGHT_RED': 亮红色;
    'GREEN': 绿色; 'LIGHT_GREEN': 亮绿色;
    'YELLOW': 黄色; 'LIGHT_YELLOW': 黄色;
    'BLUE': 深蓝色; 'LIGHT_BLUE': 深蓝色加亮;
    'CYAN': 浅蓝色; 'LIGHT_CYAN': 浅蓝色加亮;
    'MAGENTA': 紫色; 'LIGHT_MAGENTA': 亮紫色;
    'WHITE': 白色; 'LIGHT_WHITE': 亮白色;
    'BLACK': 黑色; 'LIGHT_BLACK': 黑色加亮。

字体风格样式参数的可选项：
    'BOLD': 粗体与高亮显示;
    'DIM': 较细与变暗。    
"""

from typing import Literal, Optional
from colorama import init as _init
from colorama import Fore as _Fore
from colorama import Back as _Back
from colorama import Style as _Style

_init(autoreset=False)

ColorType = Optional[
    Literal[
        "BLACK",
        "RED",
        "GREEN",
        "YELLOW",
        "BLUE",
        "MAGENTA",
        "CYAN",
        "WHITE",
        "LIGHT_BLACK",
        "LIGHT_RED",
        "LIGHT_GREEN",
        "LIGHT_YELLOW",
        "LIGHT_BLUE",
        "LIGHT_MAGENTA",
        "LIGHT_CYAN",
        "LIGHT_WHITE",
    ]
]
FontStyleType = Optional[Literal["BOLD", "DIM"]]

_color_map = {  # 前景色
    "BLACK": _Fore.BLACK,
    "RED": _Fore.RED,
    "GREEN": _Fore.GREEN,
    "YELLOW": _Fore.YELLOW,
    "BLUE": _Fore.BLUE,
    "MAGENTA": _Fore.MAGENTA,
    "CYAN": _Fore.CYAN,
    "WHITE": _Fore.WHITE,
    "LIGHT_BLACK": _Fore.LIGHTBLACK_EX,
    "LIGHT_RED": _Fore.LIGHTRED_EX,
    "LIGHT_GREEN": _Fore.LIGHTGREEN_EX,
    "LIGHT_YELLOW": _Fore.LIGHTYELLOW_EX,
    "LIGHT_BLUE": _Fore.LIGHTBLUE_EX,
    "LIGHT_MAGENTA": _Fore.LIGHTMAGENTA_EX,
    "LIGHT_CYAN": _Fore.LIGHTCYAN_EX,
    "LIGHT_WHITE": _Fore.LIGHTWHITE_EX,
}
_bg_color_map = {  # 背景色
    "BLACK": _Back.BLACK,
    "RED": _Back.RED,
    "GREEN": _Back.GREEN,
    "YELLOW": _Back.YELLOW,
    "BLUE": _Back.BLUE,
    "MAGENTA": _Back.MAGENTA,
    "CYAN": _Back.CYAN,
    "WHITE": _Back.WHITE,
    "LIGHT_BLACK": _Back.LIGHTBLACK_EX,
    "LIGHT_RED": _Back.LIGHTRED_EX,
    "LIGHT_GREEN": _Back.LIGHTGREEN_EX,
    "LIGHT_YELLOW": _Back.LIGHTYELLOW_EX,
    "LIGHT_BLUE": _Back.LIGHTBLUE_EX,
    "LIGHT_MAGENTA": _Back.LIGHTMAGENTA_EX,
    "LIGHT_CYAN": _Back.LIGHTCYAN_EX,
    "LIGHT_WHITE": _Back.LIGHTWHITE_EX,
}
_font_style_map = {  # 字体样式
    "BOLD": _Style.BRIGHT,
    "DIM": _Style.DIM,
}


# 1. >>>>> 内部事务函数 <<<<<
def _apply_color_style(s, color, bg_color, font_style):
    """根据颜色字符串设置对应的前景色、背景色、字体样式，并支持嵌套。"""
    if not isinstance(s, str):
        s = str(s)

    color_code = _color_map.get(color, "")
    bg_color_code = _bg_color_map.get(bg_color, "")
    font_style_code = _font_style_map.get(font_style, "")

    style_code = f"{font_style_code}{color_code}{bg_color_code}"

    if _Style.RESET_ALL in s:  # 支持嵌套应用
        s_list = s.split(_Style.RESET_ALL)
        color_str = "".join([f"{style_code}{part}{_Style.RESET_ALL}" for part in s_list])
    else:
        color_str = f"{style_code}{s}{_Style.RESET_ALL}"

    return color_str


# 2. >>>>> 普适性函数 ColorStr：综合控制字体的前景色、背景色、字体样式 <<<<<
def ColorStr(s, color: ColorType = None, bg_color: ColorType = None, font_style: FontStyleType = None):
    """设置可打印对象 s 在终端中的前景色、背景色、字体样式"""
    return _apply_color_style(s, color, bg_color, font_style)


# 3. >>>>> 控制字体的前景色，仅支持部分颜色；相当于 ColorStr(s, color=...) 的别名 <<<<<
def LIGHT_CYAN(s):
    """浅蓝色加亮（前景色）"""
    return _apply_color_style(s, "LIGHT_CYAN", None, None)


def LIGHT_MAGENTA(s):
    """亮紫色（前景色）"""
    return _apply_color_style(s, "LIGHT_MAGENTA", None, None)


def LIGHT_BLUE(s):
    """深蓝色加亮（前景色）"""
    return _apply_color_style(s, "LIGHT_BLUE", None, None)


def LIGHT_YELLOW(s):
    """亮黄色（前景色）"""
    return _apply_color_style(s, "LIGHT_YELLOW", None, None)


def LIGHT_GREEN(s):
    """亮绿色（前景色）"""
    return _apply_color_style(s, "LIGHT_GREEN", None, None)


def LIGHT_RED(s):
    """亮红色（前景色）"""
    return _apply_color_style(s, "LIGHT_RED", None, None)


def RED(s):
    """红色（前景色）"""
    return _apply_color_style(s, "RED", None, None)


def GREEN(s):
    """绿色（前景色）"""
    return _apply_color_style(s, "GREEN", None, None)


def YELLOW(s):
    """黄色（前景色）"""
    return _apply_color_style(s, "YELLOW", None, None)


def BLUE(s):
    """深蓝色（前景色）"""
    return _apply_color_style(s, "BLUE", None, None)


def MAGENTA(s):
    """紫色（前景色）"""
    return _apply_color_style(s, "MAGENTA", None, None)


def CYAN(s):
    """浅蓝色（前景色）"""
    return _apply_color_style(s, "CYAN", None, None)


# 4. >>>>> 控制字体的粗细与亮度（在Win下应该只变化了显示亮度）；相当于 ColorStr(s, font_style=...) 的别名 <<<<<
def BOLD(s):
    """粗体与高亮（字体样式）"""
    return _apply_color_style(s, None, None, "BOLD")


def DIM(s):
    """较细与变暗（字体样式）"""
    return _apply_color_style(s, None, None, "DIM")


# 5. >>>>> 仅分别输出 终端文字样式的开始ASCII控制字符 与 重置控制字符 的函数 <<<<<
def set_terminal_text_style(
    color: ColorType = None,
    bg_color: ColorType = None,
    font_style: FontStyleType = None,
):
    """指定 字体颜色[、背景色、字体粗亮/细暗样式] ，打印对应的ASCII控制字符，需要与 reset_text_style 配合使用"""

    color_str = _color_map.get(color, "")  # type: ignore
    bg_color_str = _bg_color_map.get(bg_color, "")  # type: ignore
    font_style_str = _font_style_map.get(font_style, "")  # type: ignore

    style_ctrl_str = color_str + bg_color_str + font_style_str
    print(style_ctrl_str, end="")


def reset_terminal_text_style():
    """打印重置控制字符，需要与 set_terminal_text_style 配合使用"""
    print(_Style.RESET_ALL, end="")
