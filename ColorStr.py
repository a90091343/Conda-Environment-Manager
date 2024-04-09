from colorama import init, Fore, Back, Style

init(autoreset=False)


def background(colorfunc):
    def wrapper(s, backclr=None):
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
        s = str(s)
        if not isinstance(backclr, str) or backclr == "":
            return colorfunc(s, None)
        elif backclr[0] == "l":
            if backclr == "lr":
                return colorfunc(s, Back.LIGHTRED_EX)
            elif backclr == "lg":
                return colorfunc(s, Back.LIGHTGREEN_EX)
            elif backclr == "ly":
                return colorfunc(s, Back.LIGHTYELLOW_EX)
            elif backclr == "lb":
                return colorfunc(s, Back.LIGHTBLUE_EX)
            elif backclr == "lc":
                return colorfunc(s, Back.LIGHTCYAN_EX)
            elif backclr in ["lm", "lp"]:
                return colorfunc(s, Back.LIGHTMAGENTA_EX)
            elif backclr == "lw":
                return colorfunc(s, Back.LIGHTWHITE_EX)
            elif backclr == "lbk":
                return colorfunc(s, Back.LIGHTBLACK_EX)
            else:
                return colorfunc(s, None)
        else:
            if backclr == "r":
                return colorfunc(s, Back.RED)
            elif backclr == "g":
                return colorfunc(s, Back.GREEN)
            elif backclr == "y":
                return colorfunc(s, Back.YELLOW)
            elif backclr == "b":
                return colorfunc(s, Back.BLUE)
            elif backclr == "c":
                return colorfunc(s, Back.CYAN)
            elif backclr in ["m", "p"]:
                return colorfunc(s, Back.MAGENTA)
            elif backclr == "w":
                return colorfunc(s, Back.WHITE)
            elif backclr == "bk":
                return colorfunc(s, Back.BLACK)
            else:
                return colorfunc(s, None)

    return wrapper


@background
def LIGHT_WHITE(s, backclr=None):
    if backclr is None:
        return Fore.LIGHTWHITE_EX + s + Style.RESET_ALL
    else:
        return Fore.LIGHTWHITE_EX + backclr + s + Style.RESET_ALL


@background
def LIGHT_CYAN(s, backclr=None):
    if backclr is None:
        return Fore.LIGHTCYAN_EX + s + Style.RESET_ALL
    else:
        return Fore.LIGHTCYAN_EX + backclr + s + Style.RESET_ALL


@background
def LIGHT_MAGENTA(s, backclr=None):
    if backclr is None:
        return Fore.LIGHTMAGENTA_EX + s + Style.RESET_ALL
    else:
        return Fore.LIGHTMAGENTA_EX + backclr + s + Style.RESET_ALL


@background
def LIGHT_BLUE(s, backclr=None):
    if backclr is None:
        return Fore.LIGHTBLUE_EX + s + Style.RESET_ALL
    else:
        return Fore.LIGHTBLUE_EX + backclr + s + Style.RESET_ALL


@background
def LIGHT_YELLOW(s, backclr=None):
    if backclr is None:
        return Fore.LIGHTYELLOW_EX + s + Style.RESET_ALL
    else:
        return Fore.LIGHTYELLOW_EX + backclr + s + Style.RESET_ALL


@background
def LIGHT_GREEN(s, backclr=None):
    if backclr is None:
        return Fore.LIGHTGREEN_EX + s + Style.RESET_ALL
    else:
        return Fore.LIGHTGREEN_EX + backclr + s + Style.RESET_ALL


@background
def LIGHT_RED(s, backclr=None):
    if backclr is None:
        return Fore.LIGHTRED_EX + s + Style.RESET_ALL
    else:
        return Fore.LIGHTRED_EX + backclr + s + Style.RESET_ALL


@background
def RED(s, backclr=None):
    if backclr is None:
        return Fore.RED + s + Style.RESET_ALL
    else:
        return Fore.RED + backclr + s + Style.RESET_ALL


@background
def GREEN(s, backclr=None):
    if backclr is None:
        return Fore.GREEN + s + Style.RESET_ALL
    else:
        return Fore.GREEN + backclr + s + Style.RESET_ALL


@background
def YELLOW(s, backclr=None):
    if backclr is None:
        return Fore.YELLOW + s + Style.RESET_ALL
    else:
        return Fore.YELLOW + backclr + s + Style.RESET_ALL


@background
def BLUE(s, backclr=None):
    if backclr is None:
        return Fore.BLUE + s + Style.RESET_ALL
    else:
        return Fore.BLUE + backclr + s + Style.RESET_ALL


@background
def MAGENTA(s, backclr=None):
    if backclr is None:
        return Fore.MAGENTA + s + Style.RESET_ALL
    else:
        return Fore.MAGENTA + backclr + s + Style.RESET_ALL


@background
def CYAN(s, backclr=None):
    if backclr is None:
        return Fore.CYAN + s + Style.RESET_ALL
    else:
        return Fore.CYAN + backclr + s + Style.RESET_ALL


@background
def WHITE(s, backclr=None):
    if backclr is None:
        return Fore.WHITE + s + Style.RESET_ALL
    else:
        return Fore.WHITE + backclr + s + Style.RESET_ALL


@background
def BLACK(s, backclr=None):
    if backclr is None:
        return Fore.BLACK + s + Style.RESET_ALL
    else:
        return Fore.BLACK + backclr + s + Style.RESET_ALL
