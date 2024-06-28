import os
import sys
import re
import time
import ctypes
import subprocess
import contextlib
import itertools
from prettytable import PrettyTable
import wcwidth
from typing import Literal, Union
from packaging.version import Version, InvalidVersion
from shutil import get_terminal_size
from ColorStr import *


def version_parse(version: str):
    """解析版本字符串，若解析失败则会依次尝试继续解析，直到返回"0"版本。"""
    try:
        return Version(version)
    except InvalidVersion:
        version = re.sub(r"[^a-zA-Z0-9]", ".", version)
        while version:
            try:
                return Version(version)
            except InvalidVersion:
                version = version[:-1]
        return Version("0")


def remove_color_from_str(colorful_str: str) -> str:
    """移除字符串中的颜色控制字符。"""
    return re.sub(r"\x1b\[[0-9;]*m", "", colorful_str)


def fast_get_terminal_size() -> os.terminal_size:
    """带缓存的快速获取终端大小，若有缓存且距今不超过0.25秒，则直接返回缓存值。"""
    cache = getattr(fast_get_terminal_size, "cache", None)
    if cache and time.time() - cache["time"] < 0.25:
        return cache["size"]

    size = get_terminal_size()
    fast_get_terminal_size.cache = {"size": size, "time": time.time()}

    return size


def count_width_per_line(s: str) -> list[int]:
    """返回多行字符串每行的实际打印宽度列表

    Notes:
        1. 颜色控制字符会被移除。
        2. 函数能正确处理以下特殊字符：制表符\\t (tab_size=8)、回车符\\r、换行符\\n、垂直制表符\\v、换页符\\f
           (其他不受支持的特殊字符则会被忽略)。
        3. 对于\\v、\\f的行为，以bash终端的垂直下移换行为准
           (win11的Windows terminal则将其视为普通的换行符\\n, 而win10及以下的默认终端则无法正常显示)。
    """
    _TAB_SIZE = 8
    terminal_width = fast_get_terminal_size().columns

    s = remove_color_from_str(s)

    widths_per_line = []
    line_width = 0
    current_pos = 0

    idx = 0
    num_chars = len(s)
    while idx < num_chars:
        char = s[idx]
        next_char = s[idx + 1] if idx + 1 < num_chars else ""
        char_width = wcwidth.wcwidth(char)

        pos_in_line = current_pos % terminal_width

        if char == "\t" and next_char and (not current_pos or pos_in_line != 0):
            # 需满足两个条件：1. 下一个字符不为空；2. 当前位置为0或当前位置不在行末
            space_to_next_tab_stop = _TAB_SIZE - (pos_in_line % _TAB_SIZE)
            if pos_in_line + space_to_next_tab_stop >= terminal_width:
                if current_pos >= line_width:
                    line_width += terminal_width - pos_in_line
                current_pos = (current_pos + terminal_width - 1) // terminal_width * terminal_width
                if wcwidth.wcwidth(next_char) <= 1:
                    idx += 1  # 跳过下一个字符
            else:
                line_width += space_to_next_tab_stop
                current_pos += space_to_next_tab_stop
        elif char == "\r":
            current_pos = current_pos // terminal_width * terminal_width
        elif char == "\n":
            widths_per_line.append(line_width)
            line_width = 0
            current_pos = 0
        elif char in {"\v", "\f"}:
            widths_per_line.append(line_width)
            line_width = pos_in_line
            current_pos = pos_in_line
        elif char_width > 0:
            if pos_in_line + char_width > terminal_width:
                if current_pos >= line_width:
                    line_width += terminal_width - pos_in_line + char_width
                current_pos = (current_pos + terminal_width - 1) // terminal_width * terminal_width + char_width
            else:
                if current_pos >= line_width:
                    line_width += char_width
                current_pos += char_width

        idx += 1
    widths_per_line.append(line_width)

    return widths_per_line


def len_to_print(s: str) -> int:
    """返回字符串在控制台中的实际打印宽度，并能正确处理制表符 (tab_size=8) 的宽度计算。

    Notes:
        1. 若字符串存在多行，则返回最宽行的打印宽度。
        2. 其他同 count_width_per_line() 函数。
    """
    return max(count_width_per_line(s))


def get_printed_line_count(text: str) -> int:
    """统计字符串输出时占用终端的实际行数，返回值恒 >= 1  (即使text为空字符串)。

    Notes:
        1. 注意：默认字符串用于print(text, end="\\n")，即本函数默认text被输出后会自动换行。
        2. 其他同 count_width_per_line() 函数。
    """
    terminal_width = fast_get_terminal_size().columns
    num_lines = 0

    line_widths = count_width_per_line(text)

    for line_width in line_widths:
        if line_width:
            num_lines += (line_width + terminal_width - 1) // terminal_width
        else:
            num_lines += 1

    return num_lines


def format_size(fsize: int, sig_digits: int = 3, B_suffix: bool = True) -> str:
    """返回文件大小的格式化的字符串（有效数字 sig_digits 小于3不会阻止整数部分的显示）。"""
    # 转换为合适的单位
    units_B = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    units_non_B = ["B", "K", "M", "G", "T", "P"]
    units = units_B if B_suffix else units_non_B
    sign = "" if fsize >= 0 else "-"
    fsize = abs(fsize)
    if fsize == 0:
        return f"0 {units[0]}"
    for i in range(len(units) - 1):
        if fsize < 9.95:
            return f"{sign}{fsize:.{max(0,sig_digits-1)}f} {units[i]}"
        elif fsize < 99.5:
            return f"{sign}{fsize:.{max(0,sig_digits-2)}f} {units[i]}"
        elif fsize < 999.5:
            return f"{sign}{fsize:.{max(0,sig_digits-3)}f} {units[i]}"
        fsize /= 1024  # type: ignore
    return f"{sign}{fsize:.2f} {units[-1]}"


def clear_lines_above(num_lines: int):
    """清除当前及上 num_lines(非负数) 行的终端内容。

    Notes:
        1. 注意：该函数只能清除当前显示区域内的行，不能清除已经滚动出显示区域的内容。
        2. 对于不支持ASCII转义序列的win32终端：通过colorama.init()，可支持部分转义序列。
        3. 为什么不用"\\033[F"? 因为该转义序列不受colorama支持，所以在win32终端下无效。
    """
    num_lines = -1 if num_lines < 1 else num_lines
    print(f"\r\033[{num_lines}A\033[J", end="")


def get_folder_size(folder_path: str, verbose: bool = True) -> int:
    """计算包括所有内容在内的文件夹的总大小。

    Warning:
        Windows 下会重复统计硬链接，导致统计结果大于实际磁盘占用。

    Returns:
        int: 文件夹的总大小（以字节为单位）。
    """
    error_msg = LIGHT_RED(f"[Error]: The folder {folder_path} does not exist.")
    if os.name == "posix":
        command = ["du", "-s", folder_path]
        result = subprocess.run(command, capture_output=True, text=True)
        if not result.stdout or result.returncode != 0:
            if verbose:
                print(RED(error_msg))
            return 0
        kilo_totalsize = result.stdout.strip().split("\t")[0]
        total_size = int(kilo_totalsize) * 1024  # 转换为字节
        return total_size
    else:  # os.name == "nt":
        command = ["dir", folder_path, "/S", "/-C"]
        # command = f'dir "{folder_path}" /S /-C' # 若要用字符串形式，则path记得加引号（左为正确形式）
        if not os.path.exists(folder_path):
            if verbose:
                print(RED(error_msg))
            return 0
        try:
            result = subprocess.check_output(command, shell=True)
            line_bytes = result.splitlines()[-2]
            total_size = re.findall(rb"\d+", line_bytes)[-1]
            return int(total_size)
        except Exception as e:
            if verbose:
                print(RED(e))
            return 0


def get_char(echo: bool = False) -> str:
    """从标准输入流中读取单个字符，不等待回车。"""
    print("", end="", flush=True)

    if os.name == "posix":
        import tty
        import fcntl
        import termios
        from locale import getpreferredencoding

        terminal_encoding = getpreferredencoding()
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            str_bytes = os.read(fd, 1)
            # 检查是否有更多的字符可用
            fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
            with contextlib.suppress(BlockingIOError):
                while True:
                    if char := os.read(fd, 1):
                        str_bytes += char
                    else:
                        break
            fcntl.fcntl(fd, fcntl.F_SETFL, 0)  # 恢复阻塞模式
            if echo and str_bytes.decode(terminal_encoding).isprintable():
                print(str_bytes.decode(terminal_encoding), end="", flush=True)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)  # 恢复终端设置

        return str_bytes.decode(terminal_encoding)

    elif os.name == "nt":
        import msvcrt

        key = msvcrt.getwch()
        if key == "\xe0":
            # 如果按下了特殊键，则继续读取下一个字节
            key += msvcrt.getwch()
        if echo and key.isprintable() and len(key) == 1:
            print(key, end="", flush=True)
        return key


class AlwaysTrueVersion(Version):
    def __lt__(self, other):
        return True

    def __le__(self, other):
        return True

    def __gt__(self, other):
        return True

    def __ge__(self, other):
        return True

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return True


class AlwaysFalseVersion(Version):
    def __lt__(self, other):
        return False

    def __le__(self, other):
        return False

    def __gt__(self, other):
        return False

    def __ge__(self, other):
        return False

    def __eq__(self, other):
        return False

    def __ne__(self, other):
        return False


class CachedIterator:
    """带缓存功能的迭代器，用于缓存生成器中的值。

    可以将其视为一个普通的列表 (list): 即允许多次迭代、判断是否为空、根据索引获取对应的值。
    """

    def __init__(self, generator):
        self.generator = generator
        self.stored_values = []
        self.iterated = False
        self.i = 0

    def __iter__(self):
        self.i = 0
        return self

    def __next__(self):
        # 如果已迭代完 generator，则抛出 StopIteration
        if self.iterated and self.i >= len(self.stored_values):
            raise StopIteration

        # 如果当前迭代的位置小于缓存值的长度，则返回对应位置的值
        if self.i < len(self.stored_values):
            value = self.stored_values[self.i]
        # 否则，从 generator 中获取值并缓存
        else:
            try:
                value = next(self.generator)
                self.stored_values.append(value)
            except StopIteration:
                self.iterated = True  # 标记已迭代完 generator
                raise  # 重新抛出 StopIteration

        self.i += 1
        return value

    def __bool__(self) -> bool:
        return bool(self.stored_values) or not self.iterated

    def __getitem__(self, index):
        """返回指定索引位置的值。

        Note:
            如果索引超出当前缓存长度，则继续从生成器获取值并缓存，直到达到该索引。
        """
        if not self.iterated:
            for _ in range(index - len(self.stored_values) + 1):
                try:
                    value = next(self.generator)
                    self.stored_values.append(value)
                except StopIteration:
                    self.iterated = True
                    break
        # 返回指定索引位置的值
        return self.stored_values[index]


def get_version_constraints_units(
    ver_constraints_str: str, always_true_strs: list = [], always_false_strs: list = []
) -> list[dict]:
    """将版本约束字符串解析为约束单元列表。

    Args:
        ver_constraints_str (str): 版本约束字符串，用管道符 "|" 分隔多个约束单元。
        always_true_strs (list): 始终为真的字符串列表。
        always_false_strs (list): 始终为假的字符串列表。

    Returns:
        list: 每个约束单元包含 "ands" 和 "ors" 的字典列表。
    """
    constraints_units = ver_constraints_str.split("|")

    constraints_cons_units = []

    for constraint_unit in constraints_units:
        if constraint_unit in always_true_strs:
            constraint_ands = [("=", AlwaysTrueVersion("1"))]
            constraint_ors = []
        elif constraint_unit in always_false_strs:
            constraint_ands = [("=", AlwaysFalseVersion("0"))]
            constraint_ors = []
        else:
            constraint_ands, constraint_ors = parse_constraints(constraint_unit)
        constraints_cons_units.append({"ands": constraint_ands, "ors": constraint_ors})

    return constraints_cons_units


# do_version_constraints_intersect
def is_version_within_constraints(
    version_str: str, constraints_str: str, always_true_strs: list = [], always_false_strs: list = []
) -> bool:
    """判断版本字符串是否符合约束条件。

    Args:
        version_str (str): 版本字符串。
        constraints_str (str): 约束条件字符串。
        always_true_strs (list): 始终为真的字符串列表。
        always_false_strs (list): 始终为假的字符串列表。

    Returns:
        bool: 如果版本符合约束条件则返回 True，否则返回 False。
    """
    version_cons_units = get_version_constraints_units(version_str, always_true_strs, always_false_strs)
    constraints_cons_units = get_version_constraints_units(constraints_str, always_true_strs, always_false_strs)

    for version_cons_unit, constraints_cons_unit in itertools.product(version_cons_units, constraints_cons_units):
        version_cons_unit_ands = version_cons_unit["ands"]
        version_cons_unit_ors = version_cons_unit["ors"]
        constraints_cons_unit_ands = constraints_cons_unit["ands"]
        constraints_cons_unit_ors = constraints_cons_unit["ors"]

        if version_cons_unit_ands and constraints_cons_unit_ands:
            if not all(
                compare_versions(version_ver, version_op, constraint_ver, constraint_op)
                for version_op, version_ver in version_cons_unit_ands
                for constraint_op, constraint_ver in constraints_cons_unit_ands
            ):
                continue

        if version_cons_unit_ors and constraints_cons_unit_ors:
            if not any(
                compare_versions(version_ver, version_op, constraint_ver, constraint_op)
                for version_op, version_ver in version_cons_unit_ors
                for constraint_op, constraint_ver in constraints_cons_unit_ors
            ):
                continue

        if version_cons_unit_ands and constraints_cons_unit_ors:
            if not any(
                all(
                    compare_versions(version_ver, version_op, constraint_ver, constraint_op)
                    for version_op, version_ver in version_cons_unit_ands
                )
                for constraint_op, constraint_ver in constraints_cons_unit_ors
            ):
                continue

        if version_cons_unit_ors and constraints_cons_unit_ands:
            if not any(
                all(
                    compare_versions(version_ver, version_op, constraint_ver, constraint_op)
                    for constraint_op, constraint_ver in constraints_cons_unit_ands
                )
                for version_op, version_ver in version_cons_unit_ors
            ):
                continue

        # 验证*_cons_unit_ands自身是否矛盾
        if constraints_cons_unit_ands:
            combinations = itertools.combinations(constraints_cons_unit_ands, 2)
            # 对组合中的每对元素进行比较
            if not all(
                compare_versions(constraint_ver1, constraint_op1, constraint_ver2, constraint_op2)
                for (constraint_op1, constraint_ver1), (constraint_op2, constraint_ver2) in combinations
            ):
                continue

        if version_cons_unit_ands:
            combinations = itertools.combinations(version_cons_unit_ands, 2)
            if not all(
                compare_versions(version_ver1, version_op1, version_ver2, version_op2)
                for (version_op1, version_ver1), (version_op2, version_ver2) in combinations
            ):
                continue

        return True

    return False


def increment_suffix(s: str) -> str:
    """递增字符串末尾的数字或字母部分。"""
    if s.isdigit():
        return str(int(s) + 1)

    if len(s) == 1:
        return chr(ord(s) + 1)

    i = 0
    tmp = ""
    while i < len(s) and s[-(i + 1)].isdigit():
        tmp = s[-(i + 1)] + tmp
        i += 1

    return s[:-1] + chr(ord(s[-1]) + 1) if i == 0 else s[:-i] + increment_suffix(tmp)


def _generate_and_constraints(and_constraints):
    for version_op, version_ver in and_constraints:
        if "*" in version_ver:
            version_ver_parts = version_ver.split(".")
            first_star_index = next((i for i, part in enumerate(version_ver_parts) if "*" in part), None)
            # 如果找到了星号，则截取列表到第一个星号的位置
            if first_star_index is not None:
                version_ver_parts = version_ver_parts[: first_star_index + 1]

            if version_op == "=":
                if version_ver_parts[0] == "*":
                    yield "=", AlwaysTrueVersion("1")
                # 与逻辑
                elif version_ver_parts[-1] == "*":
                    yield ">=", version_parse(".".join(version_ver_parts[:-1]))
                    version_ver_parts[-2] = increment_suffix(version_ver_parts[-2])
                    yield "<", version_parse(".".join(version_ver_parts[:-1]))
                else:
                    version_ver_parts[-1] = version_ver_parts[-1].replace("*", "")
                    yield ">=", version_parse(".".join(version_ver_parts))
                    version_ver_parts[-1] = increment_suffix(version_ver_parts[-1])
                    yield "<", version_parse(".".join(version_ver_parts))
            else:
                yield version_op, version_parse(version_ver.replace("*", ""))
        else:
            yield version_op, version_parse(version_ver)


def _generate_or_constraints(or_constraints):
    # version_op固定为"!="，version_ver含有"*"的情况
    for _, version_ver in or_constraints:
        version_ver_parts = version_ver.split(".")
        first_star_index = next((i for i, part in enumerate(version_ver_parts) if "*" in part), None)
        # 如果找到了星号，则截取列表到第一个星号的位置
        if first_star_index is not None:
            version_ver_parts = version_ver_parts[: first_star_index + 1]

        if version_ver_parts[0] == "*":
            yield "!=", AlwaysFalseVersion("0")
        # 或逻辑
        elif version_ver_parts[-1] == "*":
            yield "<", version_parse(".".join(version_ver_parts[:-1]))
            version_ver_parts[-2] = increment_suffix(version_ver_parts[-2])
            yield ">=", version_parse(".".join(version_ver_parts[:-1]))
        else:
            version_ver_parts[-1] = version_ver_parts[-1].replace("*", "")
            yield "<", version_parse(".".join(version_ver_parts))
            version_ver_parts[-1] = increment_suffix(version_ver_parts[-1])
            yield ">=", version_parse(".".join(version_ver_parts))


def _generate_and_constraints_without_star(constraints_str: str):
    for constraint in _all_op_vers_pattern.finditer(constraints_str):
        version_op, version_ver = constraint.groups()
        if version_op == "!":
            version_op = "!="
        elif version_op in ("==", ""):
            version_op = "="

        yield version_op, version_parse(version_ver)


_all_op_vers_pattern = re.compile(r"([~<>=!]{0,2})\s*([\w.*]+)")


def parse_constraints(constraints_str: str) -> tuple[Union[CachedIterator, list], Union[CachedIterator, list]]:
    """解析约束字符串，返回二元元组，每个元素为带缓存迭代器CachedIterator或空列表。

    Args:
        constraints_str (str): 约束字符串。

    Returns:
        (Union[CachedIterator, list], Union[CachedIterator, list]): 包含两个元素的元组，第一个元素是AND约束条件，
        第二个元素是OR约束条件。如果没有对应的约束条件，则返回空列表。
    """
    # v2.0 支持星号通配符

    if not constraints_str:
        return [], []

    if "*" not in constraints_str:
        return CachedIterator(_generate_and_constraints_without_star(constraints_str)), []

    constraints = _all_op_vers_pattern.findall(constraints_str)

    and_constraints = []
    or_constraints = []

    for constraint in constraints:
        version_op, version_ver = constraint
        if version_op == "!":
            version_op = "!="
        elif version_op in ("==", ""):
            version_op = "="

        if version_op == "!=" and "*" in version_ver:
            or_constraints.append((version_op, version_ver))
        else:
            and_constraints.append((version_op, version_ver))

    if and_constraints:
        ands = CachedIterator(_generate_and_constraints(and_constraints))
    else:
        ands = []

    if or_constraints:
        ors = CachedIterator(_generate_or_constraints(or_constraints))
    else:
        ors = []

    return ands, ors


def compare_versions(version_ver: Version, version_op: str, constraint_ver: Version, constraint_op: str) -> bool:
    """判断2个版本约束条件是否相交,约束符号仅能取"=", "!=", "<", "<=", ">", ">=","~=" """
    # assert version_op in ["=", "!=", "<", "<=", ">", ">="]
    # assert constraint_op in ["=", "!=", "<", "<=", ">", ">="]

    if version_op == "=":
        if constraint_op == "!=":
            return version_ver != constraint_ver
        elif constraint_op == "<":
            return version_ver < constraint_ver
        elif constraint_op == "<=":
            return version_ver <= constraint_ver
        elif constraint_op == "=":
            return version_ver == constraint_ver
        elif constraint_op == ">":
            return version_ver > constraint_ver
        elif constraint_op == ">=":
            return version_ver >= constraint_ver
    elif version_op == "!=":
        if constraint_op == "=":
            return version_ver != constraint_ver
    elif version_op == "<":
        if constraint_op in (">", ">=", "="):
            return version_ver > constraint_ver
    elif version_op == "<=":
        if constraint_op == ">":
            return version_ver > constraint_ver
        elif constraint_op in (">=", "="):
            return version_ver >= constraint_ver
    elif version_op == ">":
        if constraint_op in ("<", "<=", "="):
            return version_ver < constraint_ver
    elif version_op == ">=":
        if constraint_op == "<":
            return version_ver < constraint_ver
        elif constraint_op in ("<=", "="):
            return version_ver <= constraint_ver
    return True


def ordered_unique(input_list: list) -> list:
    """去除列表中的重复元素，并保持元素的原始顺序。"""
    seen = set()
    output_list = []
    for item in input_list:
        if item not in seen:
            output_list.append(item)
            seen.add(item)
    return output_list


def get_cluster_size_windows(path: str) -> int:
    """获取Windows的NTFS簇大小"""
    sectorsPerCluster = ctypes.c_ulonglong(0)
    bytesPerSector = ctypes.c_ulonglong(0)
    rootPathName = ctypes.c_wchar_p(path)

    ctypes.windll.kernel32.GetDiskFreeSpaceW(
        rootPathName,
        ctypes.pointer(sectorsPerCluster),
        ctypes.pointer(bytesPerSector),
        None,
        None,
    )

    return sectorsPerCluster.value * bytesPerSector.value


def clear_screen(hard: bool = True):
    """清空终端屏幕。

    Args:
        hard (bool):
            True (默认): 清空终端上的所有内容；
            False: 仅清空终端当前屏幕显示。
    """
    if hard:
        os.system("cls" if os.name == "nt" else "clear")
    else:
        print("\033[H\033[J", flush=True, end="")


def input_strip(prompt: str = "") -> str:
    """从标准输入中获取用户输入，并去除两端的空白字符。"""
    return input(prompt).strip()


def get_prettytable_width(table: PrettyTable) -> int:
    """获取 PrettyTable 对象的实际打印宽度。

    Notes:
        1. 表格两边的空格也会被计算在内；
        2. 空列表的宽度为 0。
    """
    return len_to_print(table.get_string().split("\n", 1)[0])


class ResponseChecker:
    YES_RESPONSES = ("y", "yes")
    NO_RESPONSES = ("n", "no")
    VALID_RESPONSES = YES_RESPONSES + NO_RESPONSES

    def __init__(self, input_str: str, default: Literal["yes", "no", "unknown"] = "unknown"):
        """初始化ResponseChecker对象并判断输入。

        Args:
            input_str (str): 用户输入的字符串。
            default (Literal["yes", "no", "unknown"]): 默认值，当输入为空时表示的默认回答。默认为 "unknown"。
        """
        self.input_str = input_str.strip().lower()
        self.default = default

    def is_yes(self) -> bool:
        """判断输入是否为肯定回答。

        Returns:
            bool: 如果是肯定回答返回 True，否则返回 False。
        """
        if self.input_str == "":
            return self.default == "yes"
        return self.input_str in self.YES_RESPONSES

    def is_no(self) -> bool:
        """判断输入是否为否定回答。

        Returns:
            bool: 如果是否定回答返回 True，否则返回 False。
        """
        if self.input_str == "":
            return self.default == "no"
        return self.input_str in self.NO_RESPONSES

    def is_other(self) -> bool:
        """判断输入是否为其他非确定性回答。

        Returns:
            bool: 如果是其他回答返回True，否则返回False
        """
        if self.input_str == "":
            return self.default == "unknown"
        return self.input_str not in self.VALID_RESPONSES


def three_line_table(
    table: PrettyTable,
    body_color: ColorType = None,
    title: Optional[str] = None,
    footer: Optional[str] = None,
    top_bottom_line_char: Optional[str] = "─",
) -> str:
    """
    将 PrettyTable 对象转换为三线表字符串，表头加粗。

    本函数生成的表格包含表头、表体、以及可选的顶线和底线。顶线和底线由 `top_bottom_line_char` 指定。
    如果 `top_bottom_line_char` 为 None，则不添加顶线和底线。

    Args:
    - table (PrettyTable): 要转换的 PrettyTable 对象。
    - body_color (Optional[str]): 表体部分的颜色字符串，可选。
    - title (Optional[str]): 表格的标题，可选。如果提供了标题，则标题会居中显示在顶线上。
    - footer (Optional[str]): 表格的页脚，可选。如果提供了页脚，则页脚会居中显示在底线上。
    - top_bottom_line_char (Optional[str]): 顶线和底线使用的字符。如果为 None，则不添加顶线和底线。默认值为 "─"。

    Returns:
    - str: 转换后的三线表字符串。
    """
    is_border = table.border
    table.border = False
    header, body = (table.get_string() + "\n").split("\n", 1)
    body = body.strip("\n")
    table_width = get_prettytable_width(table)
    table.border = is_border
    terminal_width = fast_get_terminal_size().columns
    line_length = min(table_width, terminal_width)

    top_str = table_str = bottom_str = ""
    if table_width:
        header = BOLD(header)
        body = ColorStr(body, color=body_color)
        table_str = os.linesep.join([header, "-" * line_length, body])
    if top_bottom_line_char:
        char_width = len_to_print(top_bottom_line_char)  # 确定组成顶线和底线的字符的宽度
        if title:
            title_width = len_to_print(title)
            top_str += top_bottom_line_char * ((line_length - title_width) // 2 // char_width)
            top_str += title
            top_str += top_bottom_line_char * ((line_length - title_width + 1) // 2 // char_width)
        else:
            top_str += top_bottom_line_char * (line_length // char_width)
        if footer:
            tail_width = len_to_print(footer)
            bottom_str += top_bottom_line_char * ((line_length - tail_width) // 2 // char_width)
            bottom_str += footer
            bottom_str += top_bottom_line_char * ((line_length - tail_width + 1) // 2 // char_width)
        else:
            bottom_str += top_bottom_line_char * (line_length // char_width)

    return os.linesep.join([top_str, table_str, bottom_str]).strip(os.linesep)


#  ----- * 以下函数编写于多年前，可能已经过时 * -----


def cut_printstr(lim: int, s: str):
    """lim:限制打印格数，返回截断的字符串"""
    if len_to_print(s) <= lim:
        return s
    s = str(s)
    rs = ""
    lth = 0
    for i, c in enumerate(s):
        lth += len_to_print(c)
        if lth >= lim:
            rs = s[: i + 1]
            break
    return rs


def path_intable(n: int, path: str):
    """n:控制台打印限制格数，返回路径的多行字符串，并将文件名标黄"""
    p1 = path
    p2 = ""
    p3 = ""
    while len_to_print(p1) > n:
        p1, pt = os.path.split(p1)
        p2 = os.path.join(pt, p2)
    while len_to_print(p2) > n + 1:
        p2, pt = os.path.split(p2)
        if pt == "":
            p2 += "\\"
            break
        p3 = os.path.join(pt, p3)
    if p2 == "":
        pt1, pt2 = os.path.split(path)
        return os.path.join(pt1, LIGHT_GREEN(pt2))
    elif p3 == "":
        pt1, pt2 = os.path.split(p2[:-1])
        return os.path.join(p1, "") + "\n" + os.path.join(pt1, LIGHT_GREEN(pt2))
    else:
        pt1, pt2 = os.path.split(p3[:-1])
        return os.path.join(p1, "") + "\n" + os.path.join(p2, "") + "\n" + os.path.join(pt1, LIGHT_GREEN(pt2))


def show_indir(workdir, showhat="all"):
    """展示目录下文件表格,返回所选项的绝对路径,showhat参数选项：'all','dir','file'"""
    objs = []
    if showhat != "file":
        objs.extend([i for i in os.scandir(workdir) if i.is_dir()])
    if showhat != "dir":
        objs.extend([i for i in os.scandir(workdir) if i.is_file()])
    tb = PrettyTable()
    if showhat == "dir":
        tb.field_names = ["序号", "目录名"]
        tb.align["目录名"] = "l"
    elif showhat == "file":
        tb.field_names = ["序号", "文件名"]
        tb.align["文件名"] = "l"
    else:
        tb.field_names = ["序号", "名称"]
        tb.align["名称"] = "l"
    for sn, obj in enumerate(objs, start=1):
        tb.add_row(
            [
                sn,
                (
                    LIGHT_GREEN(obj.name)
                    if obj.is_file()
                    else ColorStr(obj.name, color="BLUE", bg_color="LIGHT_GREEN")
                ),
            ]
        )
    print(tb)
    rlist = []
    while True:
        cn = input("请输入选择的文件/目录序号 (可多选，空格分开，全选输入all)\n")
        if len(cn) == 0:
            continue
        elif cn == "all":
            rlist = [i.path for i in objs]
            break
        else:
            for i in cn.split():
                try:
                    rlist.append(objs[(int(i) - 1)].path)
                except:
                    continue
            break
    return rlist
