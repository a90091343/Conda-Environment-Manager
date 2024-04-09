import contextlib
import itertools
import os
import sys
import re
import ColorStr
from packaging.version import Version, InvalidVersion


def version_parse(version: str):
    try:
        return Version(version)
    except InvalidVersion:
        try:
            from packaging.version import LegacyVersion

            return LegacyVersion(version)
        except ImportError:
            return Version("0")


def remove_color_from_str(colorful_str: str) -> str:
    # 使用正则表达式匹配颜色控制字符串并将其移除
    return re.sub(r"\x1b\[\d+m", "", colorful_str)


def printlen(s: str) -> int:
    "返回字符串在控制台的打印格数，英文占1格，中文占2格"
    length = 0
    s = remove_color_from_str(s)
    for char in s:
        # 获取字符的 Unicode 编码
        char_code = ord(char)
        # 判断字符是否是中文
        if 0x4E00 <= char_code <= 0x9FFF:
            length += 2
        else:
            length += 1
    return length


def cut_printstr(lim, s):
    "lim:限制打印格数，返回截断的字符串"
    if printlen(s) <= lim:
        return s
    s = str(s)
    rs = ""
    lth = 0

    for c in s:
        lth += printlen(c)
        rs += c
        if lth >= lim:
            break
    return rs


def path_intable(n, path: str):
    "n:控制台打印限制格数，返回路径的多行字符串，并将文件名标黄"

    p1 = path
    p2 = ""
    p3 = ""
    while printlen(p1) > n:
        p1, pt = os.path.split(p1)
        p2 = os.path.join(pt, p2)
    while printlen(p2) > n + 1:
        p2, pt = os.path.split(p2)
        if pt == "":
            p2 += "\\"
            break
        p3 = os.path.join(pt, p3)
    if p2 == "":
        pt1, pt2 = os.path.split(path)
        return os.path.join(pt1, ColorStr.LIGHT_GREEN(pt2))
    elif p3 == "":
        pt1, pt2 = os.path.split(p2[:-1])
        return os.path.join(p1, "") + "\n" + os.path.join(pt1, ColorStr.LIGHT_GREEN(pt2))
    else:
        pt1, pt2 = os.path.split(p3[:-1])
        return (
            os.path.join(p1, "")
            + "\n"
            + os.path.join(p2, "")
            + "\n"
            + os.path.join(pt1, ColorStr.LIGHT_GREEN(pt2))
        )


def show_indir(workdir, showhat="all"):
    "展示目录下文件表格,返回所选项的绝对路径,showhat参数选项：'all','dir','file'"
    from prettytable import PrettyTable

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
                    ColorStr.LIGHT_GREEN(obj.name)
                    if obj.is_file()
                    else ColorStr.BLUE(obj.name, backclr="lg")
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


def print_fsize_smart(fsize: int, precision: int = 3) -> str:
    """
    返回文件大小的格式化的字符串
    by chatGPT
    """
    assert type(fsize) == int, "fsize must be an integer"
    # 转换为合适的单位
    units = ["B", "KB", "MB", "GB", "TB"]
    sign = "" if fsize >= 0 else "-"
    fsize = abs(fsize)
    if fsize == 0:
        return "0"
    for i in range(len(units)):
        if fsize < 1024:
            if fsize > 1000:
                return f"{sign}{fsize/1024:.{max(0,precision-4)}f} {units[i+1]}"
            elif fsize > 100:
                return f"{sign}{fsize:.{max(0,precision-3)}f} {units[i]}"
            elif fsize > 10:
                return f"{sign}{fsize:.{max(0,precision-2)}f} {units[i]}"
            else:
                return f"{sign}{fsize:.{max(0,precision-1)}f} {units[i]}"
        fsize /= 1024  # type: ignore
    return f"{sign}{fsize:.2f} PB"
    # import math
    # size_bytes = fsize
    # size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    # i = int(math.floor(math.log(size_bytes, 1024)))
    # p = math.pow(1024, i)
    # s = round(size_bytes / p, 2)
    # return "{} {}".format(s, size_name[i])


def clear_lines_above(num_lines: int):
    """
    清除并覆盖指定行数以上的输出，注意！不能清除被终端隐藏的未显示的行。
    :param num_lines: int, 要清除并覆盖的行数
    """
    for _ in range(num_lines):
        print("\033[F\033[K", end="")


def get_folder_size(folder_path: str) -> int:
    """
    计算包括所有内容在内的文件夹的总大小。
    返回:  int: 文件夹的总大小（以字节为单位）。
    """
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                total_size += os.path.getsize(file_path)
    except Exception as e:
        print(ColorStr.LIGHT_RED(f"[An error occurred while calculating the folder size]: {e}"))
    return total_size


def get_char(prompt: str = "", echo: bool = True) -> str:
    """
    从标准输入流中读取单个字符，不等待回车。
    """
    print(prompt, end="", flush=True)

    if os.name == "posix":
        import tty
        import termios
        import fcntl
        from locale import getpreferredencoding

        terminal_encoding = getpreferredencoding()
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            if echo:
                # 设置终端属性以启用回显
                new_settings = termios.tcgetattr(fd)
                new_settings[3] |= termios.ECHO
                termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)

            ch = os.read(fd, 1)
            # 检查是否有更多的字符可用
            fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
            extra_chars = b""
            with contextlib.suppress(BlockingIOError):
                while True:
                    if char := os.read(fd, 1):
                        extra_chars += char
                    else:
                        break
            fcntl.fcntl(fd, fcntl.F_SETFL, 0)  # 恢复阻塞模式
            ch += extra_chars
        finally:
            # 恢复终端设置
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        return ch.decode(terminal_encoding)

    elif os.name == "nt":
        import msvcrt

        while True:
            if msvcrt.kbhit():
                key = msvcrt.getwch()
                if key == "\xe0":
                    # 如果按下了特殊键，则继续读取下一个字节
                    key += msvcrt.getwch()
                if echo and key.isprintable():
                    print(key, end="", flush=True)
                return key


def count_lines_and_print(text, end="\n") -> int:
    """
    统计字符串输出时占用的行数，并打印每一行。
    """
    print(text, end=end)
    return text.count("\n") + end.count("\n")


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

    def __bool__(self):
        return bool(self.stored_values) or not self.iterated

    def __getitem__(self, index):
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
):
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

    version_cons_units = get_version_constraints_units(version_str, always_true_strs, always_false_strs)
    constraints_cons_units = get_version_constraints_units(
        constraints_str, always_true_strs, always_false_strs
    )

    for version_cons_unit, constraints_cons_unit in itertools.product(
        version_cons_units, constraints_cons_units
    ):
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


def increment(s):
    if s.isdigit():
        return str(int(s) + 1)

    if len(s) == 1:
        return chr(ord(s) + 1)

    i = 0
    tmp = ""
    while i < len(s) and s[-(i + 1)].isdigit():
        tmp = s[-(i + 1)] + tmp
        i += 1

    return s[:-1] + chr(ord(s[-1]) + 1) if i == 0 else s[:-i] + increment(tmp)


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
                    version_ver_parts[-2] = increment(version_ver_parts[-2])
                    yield "<", version_parse(".".join(version_ver_parts[:-1]))
                else:
                    version_ver_parts[-1] = version_ver_parts[-1].replace("*", "")
                    yield ">=", version_parse(".".join(version_ver_parts))
                    version_ver_parts[-1] = increment(version_ver_parts[-1])
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
            version_ver_parts[-2] = increment(version_ver_parts[-2])
            yield ">=", version_parse(".".join(version_ver_parts[:-1]))
        else:
            version_ver_parts[-1] = version_ver_parts[-1].replace("*", "")
            yield "<", version_parse(".".join(version_ver_parts))
            version_ver_parts[-1] = increment(version_ver_parts[-1])
            yield ">=", version_parse(".".join(version_ver_parts))


def _generate_and_constraints_without_star(constraints_str: str):
    for constraint in all_op_vers_pattern.finditer(constraints_str):
        version_op, version_ver = constraint.groups()
        if version_op == "!":
            version_op = "!="
        elif version_op in ("==", ""):
            version_op = "="

        yield version_op, version_parse(version_ver)


all_op_vers_pattern = re.compile(r"([~<>=!]{0,2})\s*([\w.*]+)")


def parse_constraints(constraints_str: str):
    # v2.0 支持星号通配符,返回带缓存迭代器CachedIterator或空列表

    if not constraints_str:
        return [], []

    if "*" not in constraints_str:
        return CachedIterator(_generate_and_constraints_without_star(constraints_str)), []

    constraints = all_op_vers_pattern.findall(constraints_str)

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


def compare_versions(version_ver, version_op, constraint_ver, constraint_op):
    # 判断2个版本约束条件是否相交,约束符号仅能取"=", "!=", "<", "<=", ">", ">=","~="
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
        else:
            return True
    elif version_op == "!=":
        return version_ver != constraint_ver if constraint_op == "=" else True
    elif version_op == "<":
        if constraint_op in ("<", "<=", "!="):
            return True
        elif constraint_op in (">", ">=", "="):
            return version_ver > constraint_ver
        else:
            return True
    elif version_op == "<=":
        if constraint_op in ("<", "<=", "!="):
            return True
        elif constraint_op == ">":
            return version_ver > constraint_ver
        elif constraint_op in (">=", "="):
            return version_ver >= constraint_ver
        else:
            return True
    elif version_op == ">":
        if constraint_op in ("<", "<=", "="):
            return version_ver < constraint_ver
        elif constraint_op in (">", ">=", "!="):
            return True
        else:
            return True
    elif version_op == ">=":
        if constraint_op == "<":
            return version_ver < constraint_ver
        elif constraint_op in ("<=", "="):
            return version_ver <= constraint_ver
        elif constraint_op in (">", ">=", "!="):
            return True
        else:
            return True

    else:
        return True


def ordered_unique(input_list):
    seen = set()
    output_list = []
    for item in input_list:
        if item not in seen:
            output_list.append(item)
            seen.add(item)
    return output_list
