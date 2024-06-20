from typing import Literal, Optional
from colorama import init as _init
from colorama import Fore as _Fore
from colorama import Back as _Back
from colorama import Style as _Style

_init(autoreset=False)


def _background(colorfunc):
    def wrapper(s, color_str, backclr):
        """背景色设置参数bc,默认None
        可选参数有:\n
        'r':红色; 'lr':亮红色;\n
        'g':绿色; 'lg':亮绿色;\n
        'y':黄色; 'ly':黄色;\n
        'b':深蓝色; 'lb':深蓝色加亮;\n
        'c':浅蓝色; 'lc':浅蓝色加亮;\n
        'm'或'p':紫色; 'lm'或'lp':亮紫色;\n
        'w':白色; 'lw':亮白色;\n
        'bk':黑色; 'lbk':黑色加亮;
        """
        if not isinstance(backclr, str) or backclr == "":
            backclr = None
        elif backclr[0] == "l":
            if backclr == "lr":
                backclr = _Back.LIGHTRED_EX
            elif backclr == "lg":
                backclr = _Back.LIGHTGREEN_EX
            elif backclr == "ly":
                backclr = _Back.LIGHTYELLOW_EX
            elif backclr == "lb":
                backclr = _Back.LIGHTBLUE_EX
            elif backclr == "lc":
                backclr = _Back.LIGHTCYAN_EX
            elif backclr in ["lm", "lp"]:
                backclr = _Back.LIGHTMAGENTA_EX
            elif backclr == "lw":
                backclr = _Back.LIGHTWHITE_EX
            elif backclr == "lbk":
                backclr = _Back.LIGHTBLACK_EX
            else:
                backclr = None
        else:
            if backclr == "r":
                backclr = _Back.RED
            elif backclr == "g":
                backclr = _Back.GREEN
            elif backclr == "y":
                backclr = _Back.YELLOW
            elif backclr == "b":
                backclr = _Back.BLUE
            elif backclr == "c":
                backclr = _Back.CYAN
            elif backclr in ["m", "p"]:
                backclr = _Back.MAGENTA
            elif backclr == "w":
                backclr = _Back.WHITE
            elif backclr == "bk":
                backclr = _Back.BLACK
            else:
                backclr = None
        return colorfunc(s, color_str, backclr)

    return wrapper


@_background
def _color_str(s, c, backclr):
    color_str = ""
    if not isinstance(s, str):
        s = str(s)
    s_list = s.split(_Style.RESET_ALL)
    for s in s_list:
        color_str += c + s
        if backclr is not None:
            color_str += backclr
        color_str += _Style.RESET_ALL

    return color_str


# 1. >>>>> 控制字体的颜色 <<<<<


def LIGHT_WHITE(s, backclr=None):
    return _color_str(s, _Fore.LIGHTWHITE_EX, backclr)


def LIGHT_CYAN(s, backclr=None):
    return _color_str(s, _Fore.LIGHTCYAN_EX, backclr)


def LIGHT_MAGENTA(s, backclr=None):
    return _color_str(s, _Fore.LIGHTMAGENTA_EX, backclr)


def LIGHT_BLUE(s, backclr=None):
    return _color_str(s, _Fore.LIGHTBLUE_EX, backclr)


def LIGHT_YELLOW(s, backclr=None):
    return _color_str(s, _Fore.LIGHTYELLOW_EX, backclr)


def LIGHT_GREEN(s, backclr=None):
    return _color_str(s, _Fore.LIGHTGREEN_EX, backclr)


def LIGHT_RED(s, backclr=None):
    return _color_str(s, _Fore.LIGHTRED_EX, backclr)


def RED(s, backclr=None):
    return _color_str(s, _Fore.RED, backclr)


def GREEN(s, backclr=None):
    return _color_str(s, _Fore.GREEN, backclr)


def YELLOW(s, backclr=None):
    return _color_str(s, _Fore.YELLOW, backclr)


def BLUE(s, backclr=None):
    return _color_str(s, _Fore.BLUE, backclr)


def MAGENTA(s, backclr=None):
    return _color_str(s, _Fore.MAGENTA, backclr)


def CYAN(s, backclr=None):
    return _color_str(s, _Fore.CYAN, backclr)


def WHITE(s, backclr=None):
    return _color_str(s, _Fore.WHITE, backclr)


def BLACK(s, backclr=None):
    return _color_str(s, _Fore.BLACK, backclr)


# 2. >>>>> 控制字体的粗细与亮度（在Windows下应该只变化了显示亮度）<<<<<


def BOLD(s, backclr=None):
    """返回 粗体与高亮显示 的字符串"""
    return _color_str(s, _Style.BRIGHT, backclr)


def DIM(s, backclr=None):
    """返回 较细与变暗 的字符串"""
    return _color_str(s, _Style.DIM, backclr)


# 3. >>>>> 仅分别输出 终端文字样式的开始ASCII控制字符 与 重置控制字符 的函数 <<<<<
def set_terminal_text_style(
    color: Optional[
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
    ] = None,
    bg_color: Optional[
        Literal[
            "BLACK",
            "RED",
            "GREEN",
            "YELLOW",
            "BLUE",
            "MAGENTA",
            "CYAN",
            "WHITE",
            "LIGHTBLACK_EX",
            "LIGHTRED_EX",
            "LIGHTGREEN_EX",
            "LIGHTYELLOW_EX",
            "LIGHTBLUE_EX",
            "LIGHTMAGENTA_EX",
            "LIGHTCYAN_EX",
            "LIGHTWHITE_EX",
        ]
    ] = None,
    font_style: Optional[Literal["BOLD", "DIM"]] = None,
):
    """指定 字体颜色[、背景色、字体粗亮/细暗样式] ，打印对应的ASCII控制字符，需要与 reset_text_style 配合使用"""
    color_map = {
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
    bg_color_map = {
        "BLACK": _Back.BLACK,
        "RED": _Back.RED,
        "GREEN": _Back.GREEN,
        "YELLOW": _Back.YELLOW,
        "BLUE": _Back.BLUE,
        "MAGENTA": _Back.MAGENTA,
        "CYAN": _Back.CYAN,
        "WHITE": _Back.WHITE,
        "LIGHTBLACK_EX": _Back.LIGHTBLACK_EX,
        "LIGHTRED_EX": _Back.LIGHTRED_EX,
        "LIGHTGREEN_EX": _Back.LIGHTGREEN_EX,
        "LIGHTYELLOW_EX": _Back.LIGHTYELLOW_EX,
        "LIGHTBLUE_EX": _Back.LIGHTBLUE_EX,
        "LIGHTMAGENTA_EX": _Back.LIGHTMAGENTA_EX,
        "LIGHTCYAN_EX": _Back.LIGHTCYAN_EX,
        "LIGHTWHITE_EX": _Back.LIGHTWHITE_EX,
    }
    font_style_map = {
        "BOLD": _Style.BRIGHT,
        "DIM": _Style.DIM,
    }

    color_str = color_map.get(color, "")  # type: ignore
    bg_color_str = bg_color_map.get(bg_color, "")  # type: ignore
    font_style_str = font_style_map.get(font_style, "")  # type: ignore

    style_ctrl_str = color_str + bg_color_str + font_style_str
    print(style_ctrl_str, end="")


def reset_terminal_text_style():
    """打印重置控制字符，需要与 set_terminal_text_style 配合使用"""
    print(_Style.RESET_ALL, end="")
