###### 实现一个anaconda3或Miniforge3环境快捷选择进入命令行的脚本，方便快速进入不同的环境，不用每次都激活环境，然后再进入命令行。例如键入1即进入base环境，键入2即进入自定义1环境，键入3即进入自定义2环境，以此类推。
###### 使用方法：将该脚本放在某文件夹下，然后创建快捷方式，右键选择以管理员方式运行，然后将此快捷方式固定到开始菜单上即可。
###### """ 脚本思路：
###### 1、先通过\miniforge3\Scripts\conda.exe env list命令获取所有环境的名称，然后将其存入一个列表中。
###### 2、格式化输出列表中的环境名称，然后提示用户输入数字，要求1对应base，等等。
###### 3、获取键盘输入的值，然后将其转换为数字，然后通过列表的索引值获取对应的环境名称。
###### 4、通过os.system()命令运行%windir%\System32\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy ByPass -NoExit -Command "& 'C:\\Users\\*\\miniforge3\\shell\\condabin\\conda-hook.ps1' ; conda activate '对应环境名称' "激活环境，然后进入命令行。
###### """
# 2023-9-26 v1 稳定版
# 2023-9-27 v2 稳定版,增加了对Linux系统的全面适配
# 2023-9-27 23:29 v2.10 完全版,优化了一些细节
# 2023-9-28 v2.100 完全版,增加了探测所有可用发行版的功能，修复了一些错误
# 2023-9-28 16:19--20:08 v3 稳定完全版,优化显示模块,优化逻辑，修复小错误，全面完善功能
# 2023-9-28 22:50 v3.100 发行版,增加搜索包功能，增加退出功能
# 2023-9-29 中秋 验收完毕
# 2023-10-12 v5.0 大大增强了发行版的识别成功率
# 2024-3-16 v5.1 (Release 0.1.rc0) 改善代码逻辑，修复若干问题，添加复制环境功能[P]，打开环境主目录功能[=编号]；优化使用体验
# 致谢：ChatGPT v3.5，Github Copilot
# 2024-4-1 v5.2 (Release 1.0) 全新的[S]搜索功能，臻品打造，全面重构了代码，完善了相应功能，优化了用户体验
# 2024-4-2 v5.2.1 (Release 1.0.1) fix some bugs ; 2024-4-3 fix some bugs ; 2024-4-4 增加健康报告[H]功能，优化主界面显示，fix bugs ; 2024-4-5 fix bugs

# This code is authored by azhan.

# 为了兼容Python 3.8
from __future__ import annotations

import os
import re
import sys
import json
import time
from packaging.version import Version
from glob import glob
from typing import Union
import ColorStr
from prettytable import PrettyTable
from MyTools import (
    printlen,
    version_parse,
    clear_lines_above,
    get_version_constraints_units,
    ordered_unique,
    print_fsize_smart,
    get_folder_size,
    get_char,
    count_lines_and_print,
    is_version_within_constraints,
)

INDEX_CHECK_INTERVAL = 30  # min分钟检查一次，搜索功能的索引文件在这期间内使用缓存搜索
USER_HOME = os.path.expanduser("~")

allowed_release_names = [
    "CONDA_PREFIX",
    "miniforge3",
    "anaconda3",
    "miniconda3",
    "mambaforge",
    "miniforge-pypy3",
    "mambaforge-pypy3",
]
illegal_env_namelist = ["base", "root", "conda", "mamba", "envs"]
source_priority_table = {
    "pytorch": 1,
    "Paddle": 1,
    "nvidia": 2,
    "intel": 2,
    "pytorch-lts": 3,
    "msys2": 3,
    "bioconda": 3,
    "menpo": 3,
    "simpleitk": 3,
    "deepmodeling": 3,
    "conda-forge": 4,
    "defaults": 5,
}


def pkgs_index_last_update_time():
    pkg_cache_path = os.path.join(CONDA_HOME, "pkgs", "cache")
    lastupdate_time = 0
    if glob_res := glob(os.path.join(pkg_cache_path, "*.json")):
        for i in glob_res:
            if os.path.getmtime(i) > lastupdate_time:
                lastupdate_time = os.path.getmtime(i)
    return lastupdate_time


def filter_and_sort_sources_by_priority(
    sources: Union[list[str], set[str], tuple[str]], keep_url=False, enable_default_src=True
) -> list[str]:
    # Step 1
    unique_src_set = set()
    for source in sources:
        if (not keep_url) and "/" in source:
            unique_src_set.add(
                source.rsplit("/", 1)[1]
                if source.rsplit("/", 1)[1] in source_priority_table
                or source.rsplit("/", 1)[1] in sources
                else source
            )
        else:
            unique_src_set.add(source)
    # Step 2
    unique_src_set.discard("pypi")
    for source in {"main", "free", "r", "pro", "msys2"}:
        if source in unique_src_set:
            unique_src_set.remove(source)
            unique_src_set.add("defaults")
    # Step 3
    sourcelist = sorted(
        unique_src_set,
        key=lambda x: source_priority_table.get(x, 0),
    )
    if not enable_default_src:
        sourcelist = [source for source in sourcelist if source not in ["conda-forge", "defaults"]]
    return sourcelist


def is_legal_envname(envname: str, env_namelist: list):
    return (
        envname not in env_namelist
        and envname not in illegal_env_namelist
        and envname != ""
        and "/" not in envname
        and ":" not in envname
        and " " not in envname
        and "#" not in envname
    )


def replace_user_path(path: str):
    """
    将用户的主目录路径替换为'~'，以提高可读性。
    """
    return f"~{path[len(USER_HOME):]}" if path.startswith(USER_HOME) else path


def input_with_arrows(prompt):
    if os.name == "posix":
        import readline

        readline.parse_and_bind('"\\e[D": backward-char')
        readline.parse_and_bind('"\\e[C": forward-char')
    return input(prompt)


def get_valid_input(prompt: str, condition_func, error_msg_func=None, max_errors=5):
    """
    获取有效输入，并处理输入错误
    :param prompt: str, 输入提示信息
    :param condition_func: function, 判断输入是否有效的函数
    :param error_msg_func: function, 显示输入错误提示信息的函数,其应当仅接受一个str参数，即用户输入的值
    :param max_errors: int, 允许的最大错误次数，默认为5
    :return: str, 用户输入的值
    """
    error_count = 0
    if error_msg_func is None:
        error_msg_func = lambda input_str: f"输入错误{ColorStr.LIGHT_RED(error_count)}次，请重新输入: "
    inp = input_with_arrows(prompt)
    while not condition_func(inp):
        error_count += 1
        if error_count == 1:
            clear_lines_above(prompt.count("\n") + 1)
        else:
            clear_lines_above(prompt.count("\n") + 1 + error_msg_func(inp).count("\n") + 1)
        print(error_msg_func(inp))
        if error_count > max_errors:
            print(f"输入错误达到最大次数({ColorStr.LIGHT_RED(max_errors)})，程序退出")
            sys.exit(1)
        inp = input_with_arrows(prompt)
    if error_count > 0:
        clear_lines_above(prompt.count("\n") + 1 + error_msg_func(inp).count("\n") + 1)
        print(prompt + inp)
    return inp


def get_conda_home(detect_mode=False):
    available_conda_home = []
    if os.name == "nt":
        # 获取ProgramData路径
        progradata_path = os.environ["ProgramData"]
        for i in allowed_release_names:
            if i == "CONDA_PREFIX" and "CONDA_PREFIX" in os.environ:
                available_conda_home.append(os.environ["CONDA_PREFIX"])
                if not detect_mode:
                    break
            elif os.path.exists(os.path.join(USER_HOME, i, "conda-meta")):
                available_conda_home.append(os.path.join(USER_HOME, i))
                if not detect_mode:
                    break
            elif os.path.exists(os.path.join(progradata_path, i, "conda-meta")):
                available_conda_home.append(os.path.join(progradata_path, i))
                if not detect_mode:
                    break
        else:
            import win32com.client

            def get_shortcut_arguments(shortcut_path):
                try:
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shortcut = shell.CreateShortCut(shortcut_path)
                    arguments = shortcut.Arguments
                    return arguments
                except Exception as e:
                    print(f"无法读取快捷方式文件：{e}")
                    return None

            is_find = False
            for i in os.listdir(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"):
                if is_find and not detect_mode:
                    break
                path = os.path.join(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs", i)
                # print(path)
                if os.path.isdir(path):
                    for j in allowed_release_names:
                        if j in i.lower():
                            for k in os.listdir(path):
                                if (
                                    k.endswith(".lnk")
                                    and k.lower().find("prompt") != -1
                                    and k.lower().find("powershell") == -1
                                ):
                                    shortcut_path = os.path.join(path, k)
                                    arguments = get_shortcut_arguments(shortcut_path)
                                    if arguments is not None:
                                        available_conda_home.append(arguments.split()[-1])
                                        is_find = True
                                        if not detect_mode:
                                            break
                            if is_find and not detect_mode:
                                break
            if not is_find or detect_mode:
                for i in os.listdir(
                    os.path.join(
                        os.environ["APPDATA"],
                        "Microsoft",
                        "Windows",
                        "Start Menu",
                        "Programs",
                    )
                ):
                    if is_find and not detect_mode:
                        break
                    path = os.path.join(
                        os.path.join(
                            os.environ["APPDATA"],
                            "Microsoft",
                            "Windows",
                            "Start Menu",
                            "Programs",
                        ),
                        i,
                    )
                    # print(path)
                    if os.path.isdir(path):
                        for j in allowed_release_names:
                            if j in i.lower():
                                for k in os.listdir(path):
                                    if (
                                        k.endswith(".lnk")
                                        and k.lower().find("prompt") != -1
                                        and k.lower().find("powershell") == -1
                                    ):
                                        shortcut_path = os.path.join(path, k)
                                        arguments = get_shortcut_arguments(shortcut_path)
                                        if arguments is not None:
                                            available_conda_home.append(arguments.split()[-1])
                                            is_find = True
                                            if not detect_mode:
                                                break
                                if is_find and not detect_mode:
                                    break
    else:
        for i in allowed_release_names:
            if i == "CONDA_PREFIX" and "CONDA_PREFIX" in os.environ:
                available_conda_home.append(os.environ["CONDA_PREFIX"])
                if not detect_mode:
                    break
            elif os.path.exists(os.path.join(USER_HOME, i, "conda-meta")):
                available_conda_home.append(os.path.join(USER_HOME, i))
                if not detect_mode:
                    break
            elif os.path.exists(os.path.join("root", i, "conda-meta")):
                available_conda_home.append(os.path.join("root", i))
                if not detect_mode:
                    break

    return available_conda_home


def detect_conda_mamba_infos(conda_home: str):
    is_mamba = (
        os.path.exists(os.path.join(conda_home, "Scripts", "mamba.exe"))
        if os.name == "nt"
        else os.path.exists(os.path.join(conda_home, "bin", "mamba"))
    )
    mamba_version = None
    if is_mamba:
        if glob_res := glob(os.path.join(conda_home, "conda-meta", "mamba-*.json")):
            for i in glob_res:
                if match := re.search(r"mamba-(\d+\.\d+(?:\.\d+)?)", i):
                    mamba_version = match[1]
                    break
    libmamba_solver_version = None
    if glob_res := glob(os.path.join(conda_home, "conda-meta", "conda-libmamba-solver-*.json")):
        for i in glob_res:
            if match := re.search(r"conda-libmamba-solver-(\d+\.\d+(?:\.\d+)?)", i):
                libmamba_solver_version = match[1]
                break
    conda_version = None
    if glob_res := glob(os.path.join(conda_home, "conda-meta", "conda-*.json")):
        for i in glob_res:
            if match := re.search(r"conda-(\d+\.\d+(?:\.\d+)?)", i):
                conda_version = match[1]
                break

    return is_mamba, mamba_version, libmamba_solver_version, conda_version


def detect_conda_installation(prior_release_name: str = ""):
    global allowed_release_names
    if prior_release_name != "" and prior_release_name in allowed_release_names:
        allowed_release_names.insert(0, prior_release_name)

    available_conda_home = get_conda_home()
    # 判断是否安装了conda/mamba
    if len(available_conda_home) == 0:
        print(ColorStr.LIGHT_RED("未检测到conda/mamba的安装，请先安装conda/mamba后再运行此脚本！"))
        return "error", False, None, None, None
    else:
        conda_home = available_conda_home[0]
    is_mamba, mamba_version, libmamba_solver_version, conda_version = detect_conda_mamba_infos(
        conda_home
    )
    return conda_home, is_mamba, mamba_version, libmamba_solver_version, conda_version


CONDA_HOME, IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = detect_conda_installation()


# 检测是否启用了libmamba求解器
def detect_conda_libmamba_solver_enabled():
    if not LIBMAMBA_SOLVER_VERSION:
        return False
    user_condarc_path = os.path.join(USER_HOME, ".condarc")
    sys_condarc_path = os.path.join(CONDA_HOME, ".condarc")
    if os.path.exists(user_condarc_path):
        with open(user_condarc_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                if match := re.match(r"(?:solver|experimental_solver)\s*:\s+(\w+)", line):
                    if match[1] == "libmamba":
                        return True
                    elif match[1] == "classic":
                        return False
    if os.path.exists(sys_condarc_path):
        with open(sys_condarc_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                if match := re.match(r"(?:solver|experimental_solver)\s*:\s+(\w+)", line):
                    if match[1] == "libmamba":
                        return True
                    elif match[1] == "classic":
                        return False
    if CONDA_VERSION and Version(CONDA_VERSION) >= Version("23.10"):
        return True
    return False


def get_linux_activation_cmd(conda_home: str, is_mamba: bool):
    return f"""__conda_setup="$({os.path.join(CONDA_HOME, 'bin', 'conda')} 'shell.bash' 'hook' 2> /dev/null)"
    if [ $? -eq 0 ]; then
        eval "$__conda_setup"
    else
        if [ -f "{os.path.join(CONDA_HOME, 'etc', 'profile.d', 'conda.sh')}" ]; then
            . "{os.path.join(CONDA_HOME, 'etc', 'profile.d', 'conda.sh')}"
        else
            export PATH="{os.path.join(CONDA_HOME, 'bin')}:$PATH"
        fi
    fi
    unset __conda_setup

    if [ -f "{os.path.join(CONDA_HOME, 'etc', 'profile.d', 'mamba.sh')}" ]; then
        . "{os.path.join(CONDA_HOME, 'etc', 'profile.d', 'mamba.sh')}"
    fi """


def get_cmd(cmdlist: list, discard_stderr=False):
    if not IS_MAMBA:
        cmdlist = [i.replace("mamba", "conda", 1) if i.startswith("mamba") else i for i in cmdlist]

    if os.name == "nt":
        cmd = f'%windir%\\system32\\cmd.exe /C "{os.path.join(CONDA_HOME,"Scripts","activate.bat")} {CONDA_HOME} '
        for i in cmdlist:
            cmd += f"&& {i}"
            if discard_stderr:
                cmd += " 2> nul"
        cmd += '"'
    else:
        LINUX_ACTIVATION_CMD = get_linux_activation_cmd(CONDA_HOME, IS_MAMBA)
        cmd = LINUX_ACTIVATION_CMD
        for i in cmdlist:
            cmd += f"&& {i}"
            if discard_stderr:
                cmd += " 2> /dev/null"

    return cmd


def get_all_env(is_print=True):
    # 获取所有环境的名称
    if os.name == "nt":
        with os.popen(
            f"{os.path.join(CONDA_HOME,'Scripts','mamba.exe' if IS_MAMBA else 'conda.exe')} env list"
        ) as f:
            env_output = [l + "\n" for l in f.buffer.read().decode("utf-8").splitlines()]
    else:
        with os.popen(
            f"{os.path.join(CONDA_HOME,'bin','mamba' if IS_MAMBA else 'conda')} env list"
        ) as f:
            env_output = f.readlines()
    allow_input = [
        "-",
        "+",
        "I",
        "i",
        "R",
        "r",
        "J",
        "j",
        "C",
        "c",
        "V",
        "v",
        "U",
        "u",
        "S",
        "s",
        "Q",
        "q",
        "P",
        "p",
        "H",
        "h",
        "\x03",
    ]
    env_num = len(env_output) - 3
    env_namelist = []
    env_pathlist = []
    env_pyverlist = []
    others_env_namelist = []
    for i in range(env_num):
        if len(env_output[int(i) + 2].split()) < 2:
            env_num -= 1
            others_env_namelist.append(env_output[int(i) + 2].split()[0])
            continue
        else:
            env_namelist.append(env_output[int(i) + 2].split()[0])
            env_pathlist.append(env_output[int(i) + 2].split()[-1])
    env_lastmodified_timelist = [
        time.strftime(
            "%Y-%m-%d",
            time.gmtime(os.path.getmtime(os.path.join(i, "conda-meta", "history"))),
        )
        for i in env_pathlist
    ]
    env_installation_time_list = []
    for i in env_pathlist:
        with open(os.path.join(i, "conda-meta", "history")) as f:
            lines = f.buffer.read().decode("utf-8").splitlines()
            for line in lines:
                if line.startswith("==>"):
                    if match := re.search(r"\d{4}-\d{2}-\d{2}", line):
                        env_installation_time_list.append(match.group(0))
                        break
            else:
                env_installation_time_list.append("Unknown")
    # t0 = time.time()
    for env_path in env_pathlist:
        if os.name == "nt":
            import win32api

            def get_file_version(file_path):
                try:
                    info = win32api.GetFileVersionInfo(file_path, "\\")
                    # 提取版本号
                    file_version = f"{info['FileVersionMS'] // 65536}.{info['FileVersionMS'] % 65536}.{info['FileVersionLS'] // 65536}.{info['FileVersionLS'] % 65536}"
                    return file_version
                except Exception as e:
                    print(f"Error: {e}")
                    return ""

            if os.path.exists(py_path := os.path.join(env_path, "python.exe")):
                if match := re.match(r"(\d\.\d{1,2}\.\d{1,2})150\.1013", get_file_version(py_path)):
                    env_pyverlist.append(match.group(1))
                else:
                    with os.popen(f"{py_path} --version") as f:
                        result_text = f.buffer.read().decode("utf-8")
                    match = re.search(r"Python (\d\.\d{1,2}\.\d{1,2})", result_text) or re.search(
                        r"python (\d\.\d{1,2})\.\d{1,2}", result_text
                    )
                    env_pyverlist.append(match.group(1) if match else "Unknown")
            else:
                env_pyverlist.append("Unknown")
        else:
            if os.path.exists(py_symlimk_path := os.path.join(env_path, "bin", "python")):
                if glob_res := glob(os.path.join(env_path, "conda-meta", "python-*.json")):
                    for i in glob_res:
                        if match := re.search(r"python-(\d\.\d{1,2}\.\d{1,2})", i):
                            env_pyverlist.append(match[1])
                            break
                else:
                    result_text = os.popen(f"{py_symlimk_path} --version").read()
                    match = re.search(r"Python (\d\.\d{1,2}\.\d{1,2})", result_text) or re.search(
                        r"python (\d\.\d{1,2}\.\d{1,2})", result_text
                    )
                    env_pyverlist.append(match.group(1) if match else "Unknown")
            else:
                env_pyverlist.append("Unknown")
    # print(f"{time.time()-t0:.4f} s")
    assert (
        len(env_namelist)
        == len(env_pyverlist)
        == len(env_lastmodified_timelist)
        == len(env_installation_time_list)
        == len(env_pathlist)
    )

    if others_env_namelist:
        print(
            ColorStr.YELLOW(
                f"[提示] 检测到多个发行版安装,目前默认管理的是{os.path.split(CONDA_HOME)[1]},其他发行版的环境{others_env_namelist}将不会被显示！"
            )
        )

    allow_input.extend(str(i) for i in range(1, env_num + 1))
    allow_input.extend(f"={str(i)}" for i in range(1, env_num + 1))

    print_str = " ("
    if IS_MAMBA:
        print_str += "mamba "
        if MAMBA_VERSION:
            print_str += f"{ColorStr.LIGHT_GREEN(MAMBA_VERSION)}"
        else:
            print_str += ColorStr.LIGHT_GREEN("supported".upper())
        print_str += ", "
    print_str += "conda "
    if CONDA_VERSION and Version(CONDA_VERSION) >= Version("23.10"):
        print_str += f'{ColorStr.LIGHT_GREEN(f"{CONDA_VERSION}")}'
    elif CONDA_VERSION and Version(CONDA_VERSION) >= Version("22.12"):
        print_str += f'{ColorStr.LIGHT_YELLOW(f"{CONDA_VERSION}")}'
    elif CONDA_VERSION:
        print_str += f'{ColorStr.YELLOW(f"{CONDA_VERSION}")}'
    else:
        print_str += ColorStr.LIGHT_RED("NO")
    if not IS_MAMBA:
        print_str += ", conda-libmamba-solver "
        if LIBMAMBA_SOLVER_VERSION and Version(LIBMAMBA_SOLVER_VERSION) >= Version("23.9"):
            print_str += f'{ColorStr.LIGHT_GREEN(f"{LIBMAMBA_SOLVER_VERSION}")}'
        elif LIBMAMBA_SOLVER_VERSION:
            print_str += f'{ColorStr.YELLOW(f"{LIBMAMBA_SOLVER_VERSION}")}'
        else:
            print_str += ColorStr.LIGHT_RED("NO")
        if LIBMAMBA_SOLVER_VERSION:
            print_str += " ["
            if detect_conda_libmamba_solver_enabled():
                print_str += ColorStr.LIGHT_GREEN("Used")
            else:
                print_str += ColorStr.LIGHT_RED("Not Used")
            print_str += "]"
    print_str += "):"

    for i in range(len(env_output)):
        if i == 0:
            if is_print:
                print(
                    env_output[i]
                    .replace("conda", os.path.split(CONDA_HOME)[1].capitalize())
                    .replace(":", print_str),
                    end="",
                )
            continue
        elif len(env_output[i]) < 3:
            continue

    # 格式化输出环境名称:路径、最后修改时间，并且左对齐,去网格
    def _print_colorstr_interval(s, i):
        return ColorStr.LIGHT_YELLOW(s) if i % 2 == 0 else ColorStr.LIGHT_CYAN(s)

    _max_name_length = max((len(i) for i in env_namelist), default=0)

    table = PrettyTable()
    table.field_names = [
        "No.",
        "Env Name"
        + " " * (_max_name_length + 10 - (len("Env Name" + "(Python Version)")))
        + "(Python Version)",
        "Last Updated/Installation",
        "Environment Home",
    ]

    env_pathlist_toshow = list(map(replace_user_path, env_pathlist))
    for i in range(env_num):
        table.add_row(
            [
                _print_colorstr_interval(f"[{str(i + 1)}]", i),
                _print_colorstr_interval(
                    env_namelist[i]
                    + " " * (_max_name_length - printlen(env_namelist[i]) + 1)
                    + f"({env_pyverlist[i]})",
                    i,
                ),
                _print_colorstr_interval(
                    f"{env_lastmodified_timelist[i]} / {env_installation_time_list[i]}",
                    i,
                ),
                _print_colorstr_interval(env_pathlist_toshow[i], i),
            ]
        )
    table.align = "l"
    table.border = False
    table.padding_width = 1
    # table.hrules = HEADER
    # table.header = False
    # table.max_width = {"Env Name": 20, "Environment Home": 50, "Last Updated": 15}
    if is_print:
        print(table)
    env_infolist_dict = {
        "env_namelist": env_namelist,
        "env_pathlist": env_pathlist,
        "env_lastmodified_timelist": env_lastmodified_timelist,
        "env_installation_time_list": env_installation_time_list,
        "env_pyverlist": env_pyverlist,
    }
    return allow_input, env_infolist_dict, env_num


def ask_to_get_inp(prefix_str, askstr, allow_input=None):
    def _to_print(print_str, is_clear_lines_above=False):
        if is_clear_lines_above:
            clear_lines_above(2)
        print(print_str + ",以回车结束:")

    _to_print(prefix_str + "请输入" + askstr)
    inp = input_with_arrows(">>> ")
    # 判断输入是否合法，不合法则重新输入
    if allow_input is not None:
        error_count = 0
        while inp not in allow_input:
            error_count += 1
            if error_count > 5:
                clear_lines_above(2)
                print(ColorStr.RED(f"输入错误次数({error_count})过多，已退出！"))
                sys.exit(1)
            _to_print(
                f"{prefix_str}输入错误({ColorStr.RED(error_count)})次!请重新输入{askstr}",
                True,
            )
            inp = input_with_arrows(">>> ")

    return inp


def show_info_and_get_input(allow_input, env_num):
    # 提示用户输入数字
    print(
        f"""
允许的操作指令如下:
    激活环境对应命令行输入编号{ColorStr.LIGHT_YELLOW(f"[1-{env_num}]")};浏览环境主目录输入{ColorStr.LIGHT_GREEN("[=编号]")};
    删除环境按{ColorStr.RED("[-]")};新建环境按{ColorStr.LIGHT_GREEN("[+]")};重命名环境按{ColorStr.LIGHT_BLUE("[R]")};复制环境按{ColorStr.LIGHT_CYAN("[P]")};
    对应环境查看并回退至历史版本按{ColorStr.LIGHT_MAGENTA("[V]")};
    更新指定环境的所有包按{ColorStr.GREEN("[U]")};
    查看及清空 pip/mamba/conda 缓存按{ColorStr.LIGHT_RED("[C]")};
    将指定环境注册到 Jupyter 按{ColorStr.LIGHT_CYAN("[I]")};
    显示、管理所有已注册的 Jupyter 环境及清理弃用项按{ColorStr.LIGHT_BLUE("[J]")};
    检查环境完整性并显示健康报告按{ColorStr.LIGHT_GREEN("[H]")};
    搜索 Conda 软件包按{ColorStr.LIGHT_CYAN("[S]")};
    退出按{ColorStr.YELLOW("[Q]")};
    """,
    )
    return ask_to_get_inp(prefix_str="", askstr="对应指令", allow_input=allow_input)


def do_correct_action(inp, env_infolist_dict, env_num):
    # 根据用户输入的值执行相应的操作,并返回两种状态码，1表示需要继续显示环境列表，0表示正常进入环境
    # 如果输入的是[-]，则删除环境
    env_namelist = env_infolist_dict["env_namelist"]
    env_pathlist = env_infolist_dict["env_pathlist"]
    env_lastmodified_timelist = env_infolist_dict["env_lastmodified_timelist"]
    env_installation_time_list = env_infolist_dict["env_installation_time_list"]
    env_pyverlist = env_infolist_dict["env_pyverlist"]

    def _print_table(envnames, field_name_env="Env Name", color_func=lambda x: x):
        if not envnames:
            print("[错误] 未检测到有效的环境编号！")
            return False
        table = PrettyTable([field_name_env, "PyVer", "Last Updated/Installation"])
        table.align = "l"
        table.border = False
        for i in envnames:
            table.add_row(
                [
                    i,
                    env_pyverlist[env_namelist.index(i)],
                    env_lastmodified_timelist[env_namelist.index(i)]
                    + " / "
                    + env_installation_time_list[env_namelist.index(i)],
                ]
            )
        count = 0
        for i in table.get_string().splitlines():
            count += 1
            if count == 1:
                print(i)
                print("-" * len(i))
            else:
                print(color_func(i))
        print("-" * len(i))
        return True

    res = 0
    if inp == "-":
        print("(1) 请输入想要删除的环境的编号(或all=全部),多个以空格隔开,以回车结束: ")
        inp = input_with_arrows(f"[2-{env_num} | all] >>> ")
        if inp.lower() == "all":
            env_delete_names = [i for i in env_namelist if i not in illegal_env_namelist]
        else:
            env_delete_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
            env_delete_names = [
                env_namelist[i] for i in env_delete_nums if env_namelist[i] not in illegal_env_namelist
            ]
        if not _print_table(
            env_delete_names, field_name_env="Env to Delete", color_func=ColorStr.LIGHT_RED
        ):
            return 1
        print("(2) 确认删除以上环境吗？[y(回车)/n]")

        inp = input_with_arrows("[(Y)/n] >>> ")
        if inp not in ("y", "Y", "\r", "\n", ""):
            return 1
        for i in env_delete_names:
            command = get_cmd(
                [
                    f"mamba remove -n {i} --all --yes --quiet 1>&2",
                    f"jupyter kernelspec list --json",
                ]
            )
            # os.system(command=command)
            with os.popen(command) as f:
                result_text = f.buffer.read().decode("utf-8")
            # 清除可能的Jupyter注册
            try:
                result_json_dic = json.loads(result_text)
            except:
                print(
                    ColorStr.LIGHT_YELLOW(
                        "[警告] base环境未安装Jupyter,无法管理相关环境的jupyter注册,请在主界面按[J]以安装"
                    )
                )
                return 1
            _this_env_pypath = (
                result_json_dic.get("kernelspecs", {}).get(i, {}).get("spec", {}).get("argv", [""])[0]
            )
            if _this_env_pypath and not os.path.exists(_this_env_pypath):
                command = get_cmd([f"jupyter kernelspec uninstall {i} -y"])
                os.system(command=command)
                print(ColorStr.LIGHT_GREEN(f"[提示] 已清除需卸载环境{i}的Jupyter注册"))

        res = 1
    # 如果输入的是[+]，则新建环境
    elif inp == "+":
        print("(1) 请输入想要新建的环境的名称,以回车结束: ")
        inp1 = get_valid_input(
            ">>> ",
            lambda x: is_legal_envname(x, env_namelist),
            lambda input_str: f"新环境名称{ColorStr.LIGHT_CYAN(input_str)}"
            + ColorStr.LIGHT_RED("已存在或不符合规范")
            + "，请重新输入: ",
        )
        py_pattern = r"(?:py|pypy|python)[^A-Za-z0-9]{0,2}(\d)\.?(\d{1,2})"
        py_match = re.search(py_pattern, inp1)
        if py_match:
            inp2 = py_match.group(1) + "." + py_match.group(2)
            print(
                f"(2)[提示] 检测到环境名称{ColorStr.LIGHT_CYAN(inp1)}符合python环境命名规范,"
                + ColorStr.LIGHT_GREEN(f"已自动指定python版本={inp2}")
            )
        else:
            print("(2) 请指定python版本(为空默认最新版)，以回车结束:")
            inp2 = get_valid_input(
                "[x.x] >>> ",
                lambda x: re.match(r"\d\.\d", x) or x == "",
            )
        if inp2 != "":
            inp2 = "=" + inp2
        pre_install_pkgs = "numpy pandas matplotlib scipy scikit-learn ipykernel"  # 预安装的包
        print(
            f"(3) 请指定预安装参数(如{ColorStr.LIGHT_YELLOW('spyder')}包等,{ColorStr.LIGHT_GREEN('-c nvidia')}源等,以空格隔开)，以回车结束:"
        )
        print(
            ColorStr.LIGHT_YELLOW("[提示]")
            + f" 如输入了独立的\"{ColorStr.LIGHT_GREEN('--+')}\",则等效于预安装\"{ColorStr.LIGHT_YELLOW(pre_install_pkgs)}\"包(并将该环境注册到用户Jupyter)"
        )
        inp3 = input_with_arrows(">>> ")
        is_register_jupyter = False
        if inp3.find("--+") != -1:
            inp3 = inp3.replace("--+", pre_install_pkgs)
            is_register_jupyter = True
        command = get_cmd([f"mamba create -n {inp1} python{inp2} {inp3}"])

        cmd_res = os.system(command=command)
        # 如果安装不成功则尝试使用更多的源
        if cmd_res != 0:
            print(ColorStr.LIGHT_RED("安装失败！"))
            inp = input_with_arrows(ColorStr.LIGHT_YELLOW("(3a) 是否启用更多的源重新安装[(Y)/n] >>> "))
            if inp not in ("y", "Y", "\r", "\n", ""):
                return 1
            else:
                print(
                    ColorStr.LIGHT_YELLOW("[提示]")
                    + " 常用第三方源有:"
                    + ColorStr.LIGHT_GREEN("pytorch nvidia intel Paddle ...")
                )
                print("(3b) 请输入更多的源,以空格隔开: ")
                inp_sources = input_with_arrows(">>> ")
                inp_source_str = " ".join(f"-c {i}" for i in inp_sources.split())
                command = get_cmd([f"mamba create -n {inp1} python{inp2} {inp3} {inp_source_str}"])
                os.system(command=command)
                # 将启用的源添加为当前新环境的默认源
                if inp1 in get_all_env(is_print=False)[1]["env_namelist"]:
                    inp_source_str = " ".join(f"--add channels {i}" for i in inp_sources.split()[::-1])
                    command = get_cmd(
                        [
                            f"mamba activate {inp1}",
                            f"conda config --env {inp_source_str}",
                        ]
                    )
                    os.system(command=command)
                    print(f"(3c) 已将{ColorStr.LIGHT_GREEN(inp_sources)}添加为新环境{inp1}的默认源")

        if is_register_jupyter and inp1 in get_all_env(is_print=False)[1]["env_namelist"]:
            print(f"(4) 请输入此环境注册到Jupyter的显示名称(为空使用默认值):")
            inp11 = input_with_arrows(f"[{inp1}] >>> ")
            if inp11 == "":
                inp11 = inp1

            command = get_cmd(
                [
                    f"mamba activate {inp1}",
                    f"python -m ipykernel install --user --name {inp1} --display-name {inp11}",
                ]
            )
            os.system(command=command)
        res = 1
    # 如果输入的是[I]，则将指定环境注册到Jupyter
    elif inp in ["I", "i"]:
        print("(1) 请输入想要注册到用户级Jupyter的环境的编号(或all=全部),多个以空格隔开,以回车结束: ")
        inp = input_with_arrows(f"[2-{env_num} | all] >>> ")
        if inp.lower() == "all":
            env_reg_names = [i for i in env_namelist if i not in illegal_env_namelist]
        else:
            env_reg_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
            env_reg_names = [
                env_namelist[i] for i in env_reg_nums if env_namelist[i] not in illegal_env_namelist
            ]
        if not _print_table(
            env_reg_names, field_name_env="Env to Register", color_func=ColorStr.LIGHT_CYAN
        ):
            return 1
        print("(2) 确认注册以上环境的Jupyter到用户吗？[y(回车)/n]")
        inp = input_with_arrows("[(Y)/n] >>> ")
        if inp not in ("y", "Y", "\r", "\n", ""):
            return 1
        for j, i in enumerate(env_reg_names, 1):
            print(f"(3.{j}) 请输入环境{ColorStr.LIGHT_CYAN(i)}注册到Jupyter的显示名称(为空使用默认值):")
            ii = input_with_arrows(f"[{i}] >>> ")
            if ii == "":
                ii = i
            command = get_cmd([f"mamba list -n {i} --json"])
            with os.popen(command) as f:
                result_text = f.buffer.read().decode("utf-8")
            if result_text.find("ipykernel") == -1:
                print(
                    ColorStr.LIGHT_YELLOW(
                        "[提示] 该环境中未检测到ipykernel包，正在为环境安装ipykernel包..."
                    )
                )
                command = get_cmd(
                    [
                        f"mamba activate {i}",
                        f"mamba install ipykernel --no-update-deps --yes --quiet",
                        f"python -m ipykernel install --user --name {i} --display-name {ii}",
                    ]
                )
            else:
                command = get_cmd(
                    [
                        f"mamba activate {i}",
                        f"python -m ipykernel install --user --name {i} --display-name {ii}",
                    ]
                )
            os.system(command=command)
        res = 1
    # 如果输入的是[R]，则重命名环境
    elif inp in ["R", "r"]:
        print("(1) 请输入想要重命名的环境的编号,多个以空格隔开,以回车结束: ")
        inp = input_with_arrows(f"[2-{env_num}] >>> ")
        env_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
        env_names = [env_namelist[i] for i in env_nums if env_namelist[i] not in illegal_env_namelist]
        if not _print_table(env_names, field_name_env="Env to Rename", color_func=ColorStr.LIGHT_CYAN):
            return 1
        print("(2) 确认重命名以上环境吗？[y(回车)/n]")
        inp = input_with_arrows("[(Y)/n] >>> ")
        if inp not in ("y", "Y", "\r", "\n", ""):
            return 1
        for j, i in enumerate(env_names, 1):
            print(f"(3.{j}) 请输入环境{ColorStr.LIGHT_CYAN(i)}重命名后的环境名称:")
            ii = get_valid_input(
                ">>> ",
                lambda x: is_legal_envname(x, env_namelist) and x != i,
                lambda input_str: f"新环境名称{ColorStr.LIGHT_YELLOW(input_str)}"
                + ColorStr.LIGHT_RED("已存在或不符合规范")
                + f",请重新为{ColorStr.LIGHT_CYAN(i)}重命名: ",
            )
            command = get_cmd(
                [
                    f"mamba create -n {ii} --clone {i} 1>&2",
                    f"mamba remove -n {i} --all --yes --quiet 1>&2",
                    f"jupyter kernelspec list --json",
                ]
            )
            # os.system(command=command)
            with os.popen(command) as f:
                result_text = f.buffer.read().decode("utf-8")
            # 重新可能的Jupyter注册
            try:
                result_json_dic = json.loads(result_text)
            except:
                print(
                    ColorStr.LIGHT_YELLOW(
                        "[警告] base环境未安装Jupyter,无法管理相关环境的jupyter注册,请在主界面按[J]以安装"
                    )
                )
                return 1
            _this_env_pypath = (
                result_json_dic.get("kernelspecs", {}).get(i, {}).get("spec", {}).get("argv", [""])[0]
            )
            if _this_env_pypath and not os.path.exists(_this_env_pypath):
                print(
                    ColorStr.LIGHT_YELLOW(
                        "[提示] 检测到原环境的Jupyter注册已失效，正在为新环境重新注册Jupyter"
                    )
                )
                print("(4) 请输入注册到Jupyter的显示名称(为空使用默认值):")
                iii = input_with_arrows(f"[{ii}] >>> ")
                if iii == "":
                    iii = ii
                command = get_cmd(
                    [
                        f"jupyter kernelspec uninstall {i} -y",
                        f"mamba activate {ii}",
                        f"python -m ipykernel install --user --name {ii} --display-name {iii}",
                    ]
                )
                os.system(command=command)
                print(ColorStr.LIGHT_GREEN(f"已重新注册新环境{ii}的Jupyter"))
            # os.system(command=command)
        res = 1
    # 如果输入的是[P]，则复制环境
    elif inp in ["P", "p"]:
        print("(1) 请输入想要复制的环境的编号,多个以空格隔开,以回车结束: ")
        inp = input_with_arrows(f"[1-{env_num}] >>> ")
        env_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
        env_names = [env_namelist[i] for i in env_nums]
        if not _print_table(env_names, field_name_env="Env to Copy"):
            return 1
        print("(2) 确认复制以上环境吗？[y(回车)/n]")
        inp = input_with_arrows("[(Y)/n] >>> ")
        if inp not in ("y", "Y", "\r", "\n", ""):
            return 1
        for j, i in enumerate(env_names, 1):
            print(f"(3.{j}) 请输入环境{ColorStr.LIGHT_CYAN(i)}复制后的环境名称(为空使用默认值):")
            default_envname = i + "_copy"
            iii = 1
            while default_envname in env_namelist:
                iii += 1
                default_envname = i + "_copy" + "_" + str(iii)
            ii = get_valid_input(
                f"[{default_envname}] >>> ",
                lambda x: is_legal_envname(x, env_namelist) or x == "",
                lambda input_str: f"新环境名称{ColorStr.LIGHT_YELLOW(input_str)}"
                + ColorStr.LIGHT_RED("已存在或不符合规范")
                + f",请重新为{ColorStr.LIGHT_CYAN(i)}命名: ",
            )
            if ii == "":
                ii = default_envname
            command = get_cmd([f"mamba create -n {ii} --clone {i} --quiet"])
            os.system(command=command)
        res = 1
    # 如果输入的是[J]，则显示、管理所有已注册的Jupyter环境及清理弃用项
    elif inp in ["J", "j"]:
        print("当前用户已注册的Jupyter环境如下:")
        if os.name == "nt":
            if (
                os.system("where jupyter >nul 2>nul") != 0
                and os.path.exists(os.path.join(CONDA_HOME, "Scripts", "jupyter.exe")) == False
            ):
                print(
                    ColorStr.LIGHT_YELLOW("[提示] 未检测到jupyter命令，正尝试向base环境安装ipykernel...")
                )
                command = get_cmd(["mamba install ipykernel -y"])
                if os.system(command=command):
                    print(
                        ColorStr.LIGHT_RED("安装失败，请手动安装ipykernel后重试！"),
                        ColorStr.LIGHT_YELLOW("[提示] 已打开base环境的powershell"),
                    )
                    conda_hook_path = os.path.join(CONDA_HOME, "shell", "condabin", "conda-hook.ps1")
                    command = f"%windir%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -ExecutionPolicy ByPass -NoExit -Command \"& '{conda_hook_path}' ; conda activate \""
                    os.system(command=command)
                else:
                    print(ColorStr.LIGHT_GREEN("base环境中ipykernel安装成功！"))

            command = f"where jupyter >nul 2>nul && jupyter kernelspec list"
        else:
            command = f"""
if command -v jupyter >/dev/null 2>&1; then
    jupyter kernelspec list
else
    {"mamba" if IS_MAMBA else "conda"} install ipykernel -y >/dev/null 2>&1 && jupyter kernelspec list
fi
"""
        command = get_cmd([command])
        with os.popen(command) as f:
            kernel_output = f.buffer.read().decode("utf-8").splitlines()
        # 创建表格对象
        table = PrettyTable(["No.", "Kernel Name", "Py Ver.", "Install Time", "Location"])
        table.align = "l"
        table.border = False
        table.padding_width = 1
        kernel_names = []
        invalid_kernel_names = []
        try:
            python3_str_index = kernel_output.index(
                next((item for item in kernel_output if "python3" in item))
            )
            if python3_str_index != 1:  # 如果 "python3" 不在第二项的位置
                kernel_output.insert(1, kernel_output.pop(python3_str_index))
        except:
            pass
        for i in range(len(kernel_output)):
            if i == 0:
                # print(kernel_output[i], end="")
                continue
            elif len(kernel_output[i]) < 3:
                continue
            kernel_dir = kernel_output[i].split()[1]
            with open(os.path.join(kernel_dir, "kernel.json"), "r") as f:
                kernel_info = json.load(f)
                if os.path.exists(kernel_info["argv"][0]):
                    name = kernel_output[i].split()[0]
                    kernel_names.append(name)
                    if name == "python3":
                        table.add_row(
                            [
                                ColorStr.LIGHT_CYAN(f"[{i}]"),
                                ColorStr.LIGHT_CYAN(name + " (base)"),
                                ColorStr.LIGHT_CYAN(env_pyverlist[env_namelist.index("base")]),
                                ColorStr.LIGHT_CYAN(
                                    time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(kernel_dir)))
                                ),
                                ColorStr.LIGHT_CYAN(replace_user_path(kernel_dir)),
                            ]
                        )
                    else:
                        table.add_row(
                            [
                                f"[{i}]",
                                name,
                                (
                                    env_pyverlist[env_namelist.index(name)]
                                    if name in env_namelist
                                    else "Unknown"
                                ),
                                time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(kernel_dir))),
                                replace_user_path(kernel_dir),
                            ]
                        )
                else:
                    name = kernel_output[i].split()[0]
                    invalid_kernel_names.append(name)
                    table.add_row(
                        [
                            ColorStr.LIGHT_RED(f"[{i}]"),
                            ColorStr.LIGHT_RED(name + " (已失效)"),
                            ColorStr.LIGHT_RED("Unknown"),
                            time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(kernel_dir))),
                            ColorStr.LIGHT_RED(replace_user_path(kernel_dir)),
                        ]
                    )
        # 打印表格
        print(table)
        if not table._rows:
            print(ColorStr.LIGHT_YELLOW("未检测到任何Jupyter环境"))
            return 1
        print()
        # 询问清理失效项
        if len(invalid_kernel_names) > 0:
            print(ColorStr.LIGHT_YELLOW("(0a) 确认清理以上失效项吗？[y(回车)/n]"))
            inp = input_with_arrows("[(Y)/n] >>> ")
            if inp in ("y", "Y", "\r", "\n", ""):
                for i in invalid_kernel_names:
                    command = get_cmd([f"jupyter kernelspec uninstall {i} -y"])
                    os.system(command=command)

        # 删除对应Jupyter环境
        print("(1) 请输入想要删除的Jupyter环境的编号(或all=全部),多个以空格隔开,以回车结束: ")
        inp = input_with_arrows(f"[2-{len(kernel_names)} | all] >>> ")
        if inp.lower() == "all":
            kernel_nums_todelete = range(len(kernel_names))
        else:
            kernel_nums_todelete = [
                int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= len(kernel_names)
            ]
        kernel_names_todelete = [
            kernel_names[i] for i in kernel_nums_todelete if kernel_names[i] != "python3"
        ]
        if kernel_names_todelete:
            print("-" * max(len(i) for i in kernel_names_todelete))
            for i in kernel_names_todelete:
                print(ColorStr.LIGHT_RED(i))
            print("-" * max(len(i) for i in kernel_names_todelete))
        else:
            print("[错误] 未检测到有效的Jupyter环境编号！")
            return 1
        print("(2) 确认删除以上Jupyter环境吗？[y(回车)/n]")
        inp = input_with_arrows("[(Y)/n] >>> ")
        if inp not in ("y", "Y", "\r", "\n", ""):
            return 1
        for i in kernel_names_todelete:
            command = get_cmd([f"jupyter kernelspec uninstall {i} -y"])
            os.system(command=command)
        res = 1
    # 对应环境查看并回退至历史版本按[V]
    elif inp in ["V", "v"]:
        inp = ask_to_get_inp(
            prefix_str="(1) ",
            askstr="需要查看及回退历史版本的环境编号",
            allow_input=[str(i) for i in range(1, env_num + 1)],
        )
        env_name = env_namelist[int(inp) - 1]
        print(f"环境{ColorStr.LIGHT_CYAN(env_name)}的历史版本如下:")
        command = get_cmd([f"conda list -n {env_name} --revisions"])
        with os.popen(command) as f:
            result_text = f.buffer.read().decode("utf-8")
        print(result_text)
        raw_src_set = set(
            source.rsplit("/", 1)[0]
            for source in re.findall(r"\(([^()]+)\)", result_text)
            if "/" in source and " " not in source.rsplit("/", 1)[0]
        )
        sourceslist = filter_and_sort_sources_by_priority(
            raw_src_set, keep_url=True, enable_default_src=False
        )
        valid_rev_nums = [i for i in re.findall((r"(?i)\(rev\s+(\d+)\)"), result_text)]
        print(
            f"(2) 请输入环境{ColorStr.LIGHT_CYAN(env_name)}的历史版本编号["
            + ColorStr.LIGHT_YELLOW(f"0-{max(int(i) for i in valid_rev_nums)}")
            + "],以回车结束: "
        )
        inp = get_valid_input(
            "[rev后的数字] >>> ",
            lambda x: x in valid_rev_nums or x == "",
        )
        if inp != "":
            formatted_sources = " ".join(["-c " + source for source in sourceslist])
            if formatted_sources:
                print(
                    ColorStr.LIGHT_YELLOW("[提示] 根据历史记录已自动启用附加源:"),
                    ColorStr.LIGHT_GREEN(formatted_sources),
                )
            command = get_cmd(
                [f"conda install -n {env_name} --revision {inp} {formatted_sources}"],
            )
            os.system(command)

        res = 1
    # 如果输入的是[C]，则运行pip cache purge和mamba clean --all -y来清空所有pip与conda缓存
    elif inp in ["C", "c"]:
        command = get_cmd(
            ["mamba clean --all --dry-run --json --quiet", "pip cache dir"], discard_stderr=True
        )
        with os.popen(command) as f:
            result_text = f.buffer.read().decode("utf-8")
        try:
            if match := re.search(r"(\{.*\})(.*)", result_text, re.DOTALL):
                result_text_conda = match.group(1)
                result_text_pip = match.group(2)
            result_json_dic = json.loads(result_text_conda)
            index_cache_size = 0
            for folder_path in result_json_dic["index_cache"]["files"]:
                if os.path.exists(folder_path):
                    index_cache_size += get_folder_size(folder_path)
            index_cache_row = [
                "[1]",
                "Conda Index Caches",
                print_fsize_smart(index_cache_size),
                os.path.join("$CONDA_HOME", "pkgs", "cache", "*.json"),
            ]
            tarballs_cache_row = [
                "[2]",
                "Conda Unused Tarballs",
                print_fsize_smart(tarballs_cache_size := result_json_dic["tarballs"]["total_size"]),
                os.path.join("$CONDA_HOME", "pkgs", "(*.tar.bz2|*.conda)"),
            ]
            pkgs_cache_row = [
                "[3]",
                "Conda Unused Packages",
                print_fsize_smart(pkgs_cache_size := result_json_dic["packages"]["total_size"]),
                os.path.join("$CONDA_HOME", "pkgs", "(包文件夹)"),
            ]
            logfiles_and_locks_size = 0
            for _path in result_json_dic["logfiles"] + result_json_dic["tempfiles"]:
                if os.path.isdir(_path):
                    logfiles_and_locks_size += get_folder_size(_path)
                elif os.path.isfile(_path):
                    logfiles_and_locks_size += os.path.getsize(_path)
            logfiles_and_locks_row = [
                "[4]",
                "Conda Logs & Temps",
                print_fsize_smart(logfiles_and_locks_size),
                "To delete log files & lock files",
            ]
            if os.path.isdir(result_text_pip):
                pip_cache_size = get_folder_size(result_text_pip)
                pip_cache_Description = "Index page cache & Locally built wheels"
            else:
                pip_cache_size = 0
                pip_cache_Description = "Pipe cache is disabled"
            pip_cache_row = [
                "[5]",
                "Pip Cache",
                print_fsize_smart(pip_cache_size),
                pip_cache_Description,
            ]
            total_size = (
                index_cache_size
                + tarballs_cache_size
                + pkgs_cache_size
                + logfiles_and_locks_size
                + pip_cache_size
            )
            table = PrettyTable(["No.", "Items to Clean", "Size", "Description"])
            table.add_row(index_cache_row)
            table.add_row(tarballs_cache_row)
            table.add_row(pkgs_cache_row)
            table.add_row(logfiles_and_locks_row)
            table.add_row(pip_cache_row)
            table.align = "l"
            table.border = False
            table.padding_width = 1
            max_row_length = max(len(row) for row in table.get_string().splitlines())
            print(
                "=" * ((max_row_length - 20) // 2 - 3)
                + " "
                + ("Mamba" if IS_MAMBA else "Conda")
                + " 及 Pip 缓存情况"
                + " "
                + "=" * ((max_row_length - 20) // 2 + 3)
            )
            print(table)
            print(
                "=" * ((max_row_length - 14 - len(print_fsize_smart(total_size))) // 2 - 3)
                + " "
                + f"总缓存大小: {print_fsize_smart(total_size)}"
                + " "
                + "=" * ((max_row_length - 14 - len(print_fsize_smart(total_size))) // 2 + 3)
            )
            print("(1) 请输入Y(回车:全部清理)/N,或想要清理的缓存项编号,多个以空格隔开: ")

            def _valid_input_condition(x: str):
                if x in ["Y", "y", "N", "n", "\r", "\n", ""]:
                    return True
                for i in x.split():
                    if not (i.isdigit() and 1 <= int(i) <= 5):
                        return False
                return True

            inp = get_valid_input(
                "[(Y:All)/n | 1-5] >>> ",
                _valid_input_condition,
                lambda x: "输入"
                + ColorStr.LIGHT_RED(x)
                + "应为空或Y或N或数字[1-5]的以空格隔开的组合,请重新输入: ",
            )
            if inp in ("N", "n"):
                return 1
            elif inp in ("y", "Y", "\r", "\n", ""):
                command = get_cmd(["mamba clean --all -y", "pip cache purge"])
            else:
                command_list = []
                for i in inp.split():
                    if i == "1":
                        command_list.append("mamba clean --index-cache -y")
                    elif i == "2":
                        command_list.append("mamba clean --tarballs -y")
                    elif i == "3":
                        command_list.append("mamba clean --packages -y")
                    elif i == "4":
                        command_list.append("mamba clean --logfiles --locks -y")
                    elif i == "5":
                        command_list.append("pip cache purge")
                command = get_cmd(command_list)
            os.system(command=command)
        except Exception as e:
            print(
                ColorStr.LIGHT_RED(ColorStr.LIGHT_RED("[错误] ") + str(e)),
                ColorStr.LIGHT_RED(
                    "[错误] mamba clean --all --dry-run --json命令输出有误！无法解析,输出如下:"
                ),
                result_text,
                ColorStr.LIGHT_YELLOW("[提示] 已启动默认清理程序"),
                sep="\n",
            )
            print("(1) 确认清空所有pip/mamba/conda缓存吗？[y(回车)/n]")
            inp = input_with_arrows("[(Y)/n] >>> ")
            if inp not in ("y", "Y", "\r", "\n", ""):
                return 1
            command = get_cmd(["mamba clean --all -y", "pip cache purge"])
            os.system(command=command)

        res = 1
    # 如果输入的是[U]，则更新指定环境的所有包
    elif inp in ["U", "u"]:
        print(ColorStr.LIGHT_YELLOW("[提示] 慎用，请仔细检查更新前后的包对应源的变化！"))
        print("(1) 请输入想要更新的环境的编号(或all=全部),多个以空格隔开,以回车结束: ")
        inp = input_with_arrows(f"[1-{env_num} | all] >>> ")
        if inp.lower() == "all":
            env_names = env_namelist
        else:
            env_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
            env_names = [env_namelist[i] for i in env_nums]
        if not _print_table(env_names, field_name_env="Env to Update", color_func=ColorStr.LIGHT_CYAN):
            return 1
        print("(2) 确认更新以上环境吗？[y(回车)/n]")
        inp = input_with_arrows("[(Y)/n] >>> ")
        if inp not in ("y", "Y", "\r", "\n", ""):
            return 1
        for j, i in enumerate(env_names, 1):
            if i == "base":
                strict_channel_priority = False
            else:
                strict_channel_priority = True
            print(
                f"[{j}/{len(env_names)}] 正在更新环境{ColorStr.LIGHT_CYAN(i)}的所有包...",
                "(strict-channel-priority:",
                (
                    ColorStr.LIGHT_GREEN("True") + ")"
                    if strict_channel_priority
                    else ColorStr.LIGHT_RED("False") + ")"
                ),
            )
            command = get_cmd([f"conda list -n {i} --json"])
            with os.popen(command) as f:
                result_text = f.buffer.read().decode("utf-8")
            result_json_list = json.loads(result_text)
            raw_src_set = set()
            for pkginfo_dict in result_json_list:
                if source_str := pkginfo_dict.get("channel"):
                    raw_src_set.add(source_str.rsplit("/", 1)[-1])
            if "pypi" in raw_src_set:
                print(ColorStr.LIGHT_RED("[警告] 检测到如下由Pip管理的包，更新可能会出现问题！"))
                table = PrettyTable(["Package from Pip", "Version"])
                table.align = "l"
                table.border = False
                for pkginfo_dict in result_json_list:
                    if pkginfo_dict.get("channel") == "pypi":
                        table.add_row([pkginfo_dict["name"], pkginfo_dict["version"]])
                print(table.get_string().splitlines()[0])
                print("-" * 50)
                print(*(i for i in table.get_string().splitlines()[1:]), sep="\n")
                print("-" * 50)
                print(f"(i) 是否继续更新环境{ColorStr.LIGHT_CYAN(i)}？[y/n(回车)]")
                inp1 = input_with_arrows("[y/(N)] >>> ")
                if inp1 not in ("y", "Y"):
                    continue
            sourceslist = filter_and_sort_sources_by_priority(raw_src_set, enable_default_src=False)
            formatted_sources = " ".join(["-c " + source for source in sourceslist])
            if formatted_sources:
                print(
                    ColorStr.LIGHT_YELLOW("[提示] 已自动启用附加源: ")
                    + ColorStr.LIGHT_GREEN(formatted_sources)
                )
            if strict_channel_priority:
                command_str = f"mamba update -n {i} {formatted_sources} --all --strict-channel-priority"
            else:
                command_str = f"mamba update --all {formatted_sources}"
            command = get_cmd([command_str])
            os.system(command=command)
        res = 1
    # 如果输入的是[S]，则搜索指定Python版本下的包
    elif inp in ["S", "s"]:
        if not IS_MAMBA and (
            not LIBMAMBA_SOLVER_VERSION or Version(LIBMAMBA_SOLVER_VERSION) < Version("23.9")
        ):
            print(
                ColorStr.LIGHT_YELLOW(
                    "[提示] 您的conda-libmamba-solver未安装或版本过低，无法使用搜索功能，请将conda-libmamba-solver升级到23.9及以上版本"
                )
            )
            if CONDA_VERSION and Version(CONDA_VERSION) < Version("23"):
                print("[提示] 您的conda版本过低，建议先升级conda到23.10及以上版本")
                print("升级conda命令: conda update -n base -c defaults conda")

            if LIBMAMBA_SOLVER_VERSION:
                print("升级libmamba命令: conda update conda-libmamba-solver --freeze-installed")
            else:
                print("安装libmamba命令: conda install -n base conda-libmamba-solver")
            print(ColorStr.LIGHT_YELLOW("请在base环境下执行以上命令。"))
            return 1

        print("(1) 请指定python版本(为空默认全版本)，以回车结束:")
        target_py_version = get_valid_input(
            "[x.x] >>> ",
            lambda x: re.match(r"\d\.\d", x) or x == "",
        )

        def _get_pyversion_from_build(build_str):
            py_pattern = r"(?<![A-Za-z])(?:py|pypy|python)(2|3)\.?(\d{1,2})(?!\d)"
            if py_match := re.search(py_pattern, build_str):
                return py_match.group(1) + "." + py_match.group(2)
            else:
                return None

        def _get_cuda_version_from_build(build_str):
            cuda_pattern = r"(?<![A-Za-z])(?:cuda|cu)(\d{1,2})\.?(\d)(?!\d)"
            if cuda_match := re.search(cuda_pattern, build_str):
                if cuda_match.group(1) == "0" or cuda_match.group(1) == "1":
                    return None
                return cuda_match.group(1) + "." + cuda_match.group(2)
            else:
                return None

        def _get_channel_from_url(url_str):
            subdirs = [
                "linux-32",
                "linux-64",
                "linux-aarch64",
                "linux-armv6l",
                "linux-armv7l",
                "linux-ppc64le",
                "noarch",
                "osx-32",
                "osx-64",
                "osx-arm64",
                "win-32",
                "win-64",
            ]
            parts = url_str.split("/")
            for i, j in enumerate(parts):
                if j in subdirs:
                    if parts[i - 1] in ("main", "free", "r", "pro"):
                        return "defaults"
                    return parts[i - 1]
            return None

        def shorten_version(match):
            major, minor = match.groups()
            return f"{major}.{minor}"

        def _pure_cuda_version(version_str):

            version_pattern = re.compile(r"(\d{1,2})\.([a-zA-Z\d*]{1,3})(?:\.[a-zA-Z\d.*]+)?")
            version_gtlt_pattern = re.compile(r">=(\d{1,2}\.[\da]+),<(\d{1,2}\.[\da]+)")
            new_version_str = version_pattern.sub(shorten_version, version_str)

            # if new_version_str.endswith("*") and new_version_str.rsplit(".", 1)[-1] != "*":
            #     new_version_str = new_version_str[:-1]
            if new_version_str.endswith(".0a0"):
                # 在比较版本号时，如果用户输入预览版版本号，结果可能会有歧义，但不重要，因为没人会用预览版
                new_version_str = new_version_str[:-4]

            if res := new_version_str.split("|"):
                if len(res) == 2 and res[0] == res[1]:
                    new_version_str = res[0]

            if match := version_gtlt_pattern.match(new_version_str):
                first_version_1, first_version_2 = match[1].split(".")
                second_version_1, second_version_2 = match[2].split(".")
                if first_version_1 == second_version_1 and int(first_version_2) + 1 == int(
                    second_version_2
                ):
                    new_version_str = match[1]
                elif match[1] == "11.8" and second_version_1 == "12":
                    new_version_str = match[1]

            return new_version_str

        def _pure_python_version(version_str):
            version_str = version_str.replace(" ", "")

            notequal_3vers_pattern = re.compile(r"(,?!=\d+\.\d+\.\d+)(?=,|$)")
            if len(res := notequal_3vers_pattern.sub("", version_str)) > 1:
                version_str = res

            version_pattern = re.compile(r"(2|3|4)\.([a-zA-Z\d*]{1,5})(?:\.[a-zA-Z\d.*]+)?")
            new_version_str = version_pattern.sub(shorten_version, version_str)

            # 由于python >3.6允许3.6.x进行安装，所以需要将>转换为>=
            gt_pattern = re.compile(r">(?!=)")
            new_version_str = gt_pattern.sub(">=", new_version_str)

            if new_version_str.endswith("0a0"):
                new_version_str = new_version_str[:-2]

            if not new_version_str[-1].isdigit():
                while len(new_version_str) > 0 and not new_version_str[-1].isdigit():
                    new_version_str = new_version_str[:-1]

            new_version_str = new_version_str.replace(",<4.0a0", "")
            new_version_str = new_version_str.replace(",<4.dev0", "")
            new_version_str = new_version_str.replace(",<4.0", "")
            new_version_str = new_version_str.replace(",<4", "")

            if new_version_str == "2":
                new_version_str = "<3"
            elif new_version_str == "3":
                new_version_str = ">3"

            if new_version_str in ("<4.0", "<4", "*", ""):
                return None

            if res := new_version_str.split("|"):
                if len(res) == 2 and res[0] == res[1]:
                    new_version_str = res[0]

            return new_version_str

        def filter_pkg_info(raw_pkginfo_dict):
            build_prefix = None
            build_rsplit_list = raw_pkginfo_dict["build"].rsplit("_", 2)
            if build_rsplit_list[-1].isdigit():
                if len(build_rsplit_list) > 1:
                    build_prefix = "_".join(build_rsplit_list[:-1])
                else:
                    build_prefix = raw_pkginfo_dict["build"]
            elif len(build_rsplit_list) == 3:
                if build_rsplit_list[2] == str(raw_pkginfo_dict["build_number"]):
                    build_prefix = build_rsplit_list[0] + "_" + build_rsplit_list[1]
                elif build_rsplit_list[1] == str(raw_pkginfo_dict["build_number"]):
                    build_prefix = build_rsplit_list[0]
            elif len(build_rsplit_list) == 2:
                if build_rsplit_list[1] == str(raw_pkginfo_dict["build_number"]):
                    build_prefix = build_rsplit_list[0]
            if not build_prefix:
                build_number_length = len(str(raw_pkginfo_dict["build_number"]))
                if raw_pkginfo_dict["build"].split("_", 1)[0] == str(raw_pkginfo_dict["build_number"]):
                    build_prefix = "_".join(raw_pkginfo_dict["build"].split("_")[1:])
                elif (
                    len(build_rsplit_list[-1]) <= (3 + build_number_length)
                    and (not build_rsplit_list[-1].startswith("cu"))
                    and build_rsplit_list[-1][-build_number_length:]
                    == str(raw_pkginfo_dict["build_number"])
                ):
                    build_prefix = "_".join(build_rsplit_list[:-1])
                else:
                    build_prefix = raw_pkginfo_dict["build"]

            channel = _get_channel_from_url(raw_pkginfo_dict["url"])

            is_cuda = False

            python_version = None
            cuda_version = None
            # utc 8:00am 2016-02-20
            TIMESTAMP_20160220 = 1455955200
            py_pattern = re.compile(r"python\s+(\S+)")
            py_equal_pattern = re.compile(r"python\s+(?:~=)?((?:2|3|4)\.[\d.*]+)(?!.*[|>=~<])")
            py_gtlt_pattern = re.compile(
                r"python\s+>=((?:2|3|4)\.\d{1,2})(?:\.[\d*a-z]+)?,<((?:2|3|4)\.\d{1,2})(?:\.[\d*a-z]+)?"
            )
            py_abi_pattern = re.compile(r"python_abi\s+((?:2|3|4)\.\d{1,2})")
            # gpu_pattern = re.compile(r"(?<![a-zA-Z0-9])gpu(?![a-zA-Z0-9])")
            cuda_ver_pattern = re.compile(
                r"cuda(?:-?toolkit|-?runtime|-?cudart|-?nvcc|-?nvrtc|-?version)?\s+(\S+)"
            )
            gpu_pattern = re.compile(r"\bgpu\b(?!\s+999)")
            cpu_pattern = re.compile(r"\bcpu\b")

            if cuda_version := _get_cuda_version_from_build(raw_pkginfo_dict["build"]):
                is_cuda = True

            depends = raw_pkginfo_dict["depends"]
            constrains = raw_pkginfo_dict.get("constrains", [])
            depends_combined_list = depends + constrains

            cuda_version_tmp = None
            python_version_tmp = None
            for dep in depends_combined_list:
                if not python_version_tmp and (match := py_pattern.match(dep)):
                    python_version_tmp = match.group(1)

                if not python_version and (match := py_abi_pattern.match(dep)):
                    python_version = match.group(1)
                elif not python_version and (match := py_equal_pattern.match(dep)):
                    python_version_split = match.group(1).split(".")
                    if python_version_split[1].replace("*", "").isdigit():
                        python_version = (
                            python_version_split[0] + "." + python_version_split[1].replace("*", "")
                        )
                elif not python_version and (match := py_gtlt_pattern.match(dep)):
                    first_python_version = match.group(1)
                    second_python_version = match.group(2)
                    if first_python_version[0] == second_python_version[0] and (
                        int(first_python_version[2:]) + 1
                    ) == int(second_python_version[2:]):
                        python_version = first_python_version
                elif not cuda_version and ("cuda" in dep):
                    is_cuda = True
                    if match := _get_cuda_version_from_build(dep):
                        cuda_version = match
                    elif match := cuda_ver_pattern.match(dep):
                        if dep.startswith("cuda-version"):
                            cuda_version_tmp = match.group(1)
                        else:
                            cuda_version = match.group(1)
                elif gpu_pattern.search(dep):
                    is_cuda = True

                if not python_version and (python_version := _get_pyversion_from_build(dep)):
                    if (python_version == "3.1" or python_version == "3.2") and raw_pkginfo_dict[
                        "timestamp"
                    ] > TIMESTAMP_20160220:
                        python_version = None

                if python_version and cuda_version:
                    break

            if not cuda_version and cuda_version_tmp:
                cuda_version = cuda_version_tmp

            if not python_version and (
                python_version := _get_pyversion_from_build(raw_pkginfo_dict["build"])
            ):
                if (python_version == "3.1" or python_version == "3.2") and raw_pkginfo_dict[
                    "timestamp"
                ] > TIMESTAMP_20160220:
                    python_version = None

            if not is_cuda and gpu_pattern.search(raw_pkginfo_dict["build"]):
                is_cuda = True
            if is_cuda and not cuda_version and cpu_pattern.search(raw_pkginfo_dict["build"]):
                is_cuda = False

            if cuda_version:
                cuda_version = _pure_cuda_version(cuda_version)

            if not python_version and python_version_tmp:
                python_version = _pure_python_version(python_version_tmp)

            raw_pkginfo_dict["build_prefix"] = build_prefix
            raw_pkginfo_dict["python_version"] = python_version
            raw_pkginfo_dict["cuda_version"] = cuda_version
            raw_pkginfo_dict["is_cuda"] = is_cuda
            raw_pkginfo_dict["channel"] = channel

        def find_python_version_range(python_version_str):
            """
            Return: 最小支持Python版本:str，最大支持Python版本:str
            """
            if not python_version_str:
                return None, None

            # 基本条件判断
            if match := re.fullmatch(r"([<>=]{0,2})((?:2|3|4)\.\d{1,2})", python_version_str):
                op, ver = match.groups()
                if op in ("=", "", "=="):
                    return ver, ver
                elif op in (">=", ">"):
                    return ver, None
                elif op == "<=":
                    return None, ver
                elif op == "<" and len(ver) > 2 and ver[-1] != "0":
                    return f"{ver[0]}.{int(ver[2])-1}", None

            # 若基本判断无法得到结果，则进行更复杂的判断，时间复杂度大大增加
            constraints_cons_units = get_version_constraints_units(python_version_str)
            min_version = Version("99999.9")
            max_version = Version("0.0")

            for constraints_cons_unit in constraints_cons_units:
                constraints_cons_unit_ands = constraints_cons_unit["ands"]
                for constraint_op, constraint_ver in constraints_cons_unit_ands:
                    if constraint_op == "=":
                        max_version = min_version = constraint_ver
                        break
                    elif constraint_op in (">=", ">"):
                        if constraint_ver < min_version:
                            min_version = constraint_ver
                    elif constraint_op == "<":
                        if constraint_ver.minor == 0:
                            if constraint_ver.major == 3:
                                max_version = Version("2.7")
                        else:
                            if Version(f"{constraint_ver.major}.{constraint_ver.minor-1}") > max_version:
                                max_version = Version(f"{constraint_ver.major}.{constraint_ver.minor-1}")
                    elif constraint_op == "<=":
                        if constraint_ver > max_version:
                            max_version = constraint_ver

            if min_version == Version("99999.9") or is_version_within_constraints(
                "0.0", python_version_str
            ):
                min_version_str = None
            else:
                min_version_str = str(min_version)
            if max_version == Version("0.0") or is_version_within_constraints(
                "99999.9", python_version_str
            ):
                max_version_str = None
            else:
                max_version_str = str(max_version)

            return min_version_str, max_version_str

        def find_cuda110_12later_support(cuda_version_str):
            if match := re.fullmatch(r"(\d{2})(?:\.[\d*]{1,2})?", cuda_version_str):
                if "*" in cuda_version_str:
                    if match[1] == "11":
                        return "11.8"
                    elif int(match[1]) >= 12:
                        return match[1]
                    else:
                        return None
                elif int(match[1]) >= 11:
                    return cuda_version_str
                else:
                    return None
            if match := re.search(r"(<=|<)(\d{2}(?:\.\d{1,2})?)", cuda_version_str):
                if match[1] == "<=":
                    if int(match[2].split(".")[0]) >= 11:
                        return match[2]
                    else:
                        return None
                else:  # match[1]=="<"
                    major, _, minor = match[2].partition(".")
                    if int(major) >= 11 and minor and minor != "0":
                        return f"{major}.{int(minor)-1}"

            if is_version_within_constraints(cuda_version_str, ">=12"):
                if matches := re.findall(r"(12\.\d{1,2})", cuda_version_str):
                    for match in reversed(matches):
                        if match != "12.0" and is_version_within_constraints(cuda_version_str, match):
                            return match
                return "12"
            if is_version_within_constraints(cuda_version_str, ">=11.8"):
                return "11.8"
            if match := re.search(r">=(11\.\d{1,2})", cuda_version_str):
                return match.group(1)

        class MergePkgInfos:
            """
            合并包信息列表。
            1. ref提供初筛结果，key为(name,version)，供后续为无Python版本的包提供最大最小Python版本的参考
            2. 第一遍合并需考虑build_prefix一样，按build_number大小合并
            3. 第二遍合并只考虑name, version, channel，并注明支持的最大Python版本，与是否存在CUDA包
            """

            def __init__(self, pkginfo_dicts_list):
                self.pkginfo_ref_dict = {}
                for pkginfo_dict in pkginfo_dicts_list:
                    name = pkginfo_dict["name"]
                    version = pkginfo_dict["version"]
                    channel = pkginfo_dict["channel"]
                    python_version = pkginfo_dict["python_version"]
                    min_py_ver, max_py_ver = find_python_version_range(python_version)
                    key = (name, version, channel)
                    if key in self.pkginfo_ref_dict:
                        if max_py_ver:
                            if not self.pkginfo_ref_dict[key]["max_py_ver"]:
                                self.pkginfo_ref_dict[key]["max_py_ver"] = max_py_ver
                            elif max_py_ver != self.pkginfo_ref_dict[key][
                                "max_py_ver"
                            ] and version_parse(max_py_ver) > version_parse(
                                self.pkginfo_ref_dict[key]["max_py_ver"]
                            ):
                                self.pkginfo_ref_dict[key]["max_py_ver"] = max_py_ver
                        if min_py_ver:
                            if not self.pkginfo_ref_dict[key]["min_py_ver"]:
                                self.pkginfo_ref_dict[key]["min_py_ver"] = min_py_ver
                            elif min_py_ver != self.pkginfo_ref_dict[key][
                                "min_py_ver"
                            ] and version_parse(min_py_ver) < version_parse(
                                self.pkginfo_ref_dict[key]["min_py_ver"]
                            ):
                                self.pkginfo_ref_dict[key]["min_py_ver"] = min_py_ver
                    else:
                        self.pkginfo_ref_dict[key] = {
                            "max_py_ver": max_py_ver,
                            "min_py_ver": min_py_ver,
                        }

            def get_ref_dict(self):
                # 第0遍提供初筛结果，key为(name,version)，供后续为无Python版本的包提供最大最小Python版本的参考
                ref_dict = {}
                for key, py_ver_dict in self.pkginfo_ref_dict.items():
                    name, version, _ = key
                    max_py_ver = py_ver_dict["max_py_ver"]
                    min_py_ver = py_ver_dict["min_py_ver"]
                    if (name, version) in ref_dict:
                        if max_py_ver:
                            if not ref_dict[(name, version)]["max_py_ver"]:
                                ref_dict[(name, version)]["max_py_ver"] = max_py_ver
                            elif max_py_ver != ref_dict[(name, version)]["max_py_ver"] and version_parse(
                                max_py_ver
                            ) > version_parse(ref_dict[(name, version)]["max_py_ver"]):
                                ref_dict[(name, version)]["max_py_ver"] = max_py_ver
                        if min_py_ver:
                            if not ref_dict[(name, version)]["min_py_ver"]:
                                ref_dict[(name, version)]["min_py_ver"] = min_py_ver
                            elif min_py_ver != ref_dict[(name, version)]["min_py_ver"] and version_parse(
                                min_py_ver
                            ) < version_parse(ref_dict[(name, version)]["min_py_ver"]):
                                ref_dict[(name, version)]["min_py_ver"] = min_py_ver
                    else:
                        ref_dict[(name, version)] = {"max_py_ver": max_py_ver, "min_py_ver": min_py_ver}
                return ref_dict

            def merge_1st(self, pkginfo_dicts_list):
                # 第一遍合并需考虑build_prefix一样，按build_number大小合并
                merged_pkginfos_dict = {}
                for pkginfo_dict in pkginfo_dicts_list:
                    name = pkginfo_dict["name"]
                    version = pkginfo_dict["version"]
                    channel = pkginfo_dict["channel"]
                    python_version = pkginfo_dict["python_version"]
                    is_cuda = pkginfo_dict["is_cuda"]
                    build_prefix = pkginfo_dict["build_prefix"]
                    key = (name, build_prefix, version, channel, python_version, is_cuda)

                    if key in merged_pkginfos_dict:
                        existing_build_count = merged_pkginfos_dict[key]["build_count"]

                        existing_build_number = int(merged_pkginfos_dict[key]["build_number"])
                        current_build_number = int(pkginfo_dict["build_number"])

                        # Choose the package with higher build number
                        if current_build_number > existing_build_number or (
                            current_build_number == existing_build_number
                            and pkginfo_dict["timestamp"] > merged_pkginfos_dict[key]["timestamp"]
                        ):
                            merged_pkginfos_dict[key] = pkginfo_dict.copy()

                        merged_pkginfos_dict[key]["build_count"] = existing_build_count + 1
                    else:
                        merged_pkginfos_dict[key] = pkginfo_dict.copy()
                        merged_pkginfos_dict[key]["build_count"] = 1
                return list(merged_pkginfos_dict.values())

            def merge_2nd(self, pkginfo_dicts_list):
                # 第二遍合并只考虑name, version, channel，并注明支持的最大Python版本，与是否存在CUDA包
                # 注意！这不是merge_iteration == 1的基础上再合并，而是重新从pkginfos_list_raw开始合并
                merged_pkginfos_dict = {}
                for pkginfo_dict in pkginfo_dicts_list:
                    name = pkginfo_dict["name"]
                    version = pkginfo_dict["version"]
                    channel = pkginfo_dict["channel"]
                    current_timestamp = pkginfo_dict["timestamp"]
                    is_cuda = pkginfo_dict["is_cuda"]
                    if pkginfo_dict["python_version"]:
                        key = (name, version, channel)
                        min_py_ver = self.pkginfo_ref_dict[key]["min_py_ver"]
                        max_py_ver = self.pkginfo_ref_dict[key]["max_py_ver"]
                    elif py_ver_limits := pkginfo_dict.get("py_ver_limits"):
                        min_py_ver, max_py_ver = py_ver_limits
                    else:
                        min_py_ver, max_py_ver = None, None
                    if cuda_version := pkginfo_dict["cuda_version"]:
                        cuda110_12later_support = find_cuda110_12later_support(cuda_version)
                    else:
                        cuda110_12later_support = None

                    key = (name, version, channel)
                    if key in merged_pkginfos_dict:
                        merged_pkginfos_dict[key]["build_count"] += pkginfo_dict.get("build_count", 1)
                        if max_py_ver:
                            if not merged_pkginfos_dict[key]["max_py_ver"]:
                                merged_pkginfos_dict[key]["max_py_ver"] = max_py_ver
                            elif max_py_ver != merged_pkginfos_dict[key]["max_py_ver"] and version_parse(
                                max_py_ver
                            ) > version_parse(merged_pkginfos_dict[key]["max_py_ver"]):
                                merged_pkginfos_dict[key]["max_py_ver"] = max_py_ver
                        if min_py_ver:
                            if not merged_pkginfos_dict[key]["min_py_ver"]:
                                merged_pkginfos_dict[key]["min_py_ver"] = min_py_ver
                            elif min_py_ver != merged_pkginfos_dict[key]["min_py_ver"] and version_parse(
                                min_py_ver
                            ) < version_parse(merged_pkginfos_dict[key]["min_py_ver"]):
                                merged_pkginfos_dict[key]["min_py_ver"] = min_py_ver
                        if is_cuda:
                            merged_pkginfos_dict[key]["is_cuda"] = True
                        if cuda110_12later_support:
                            if not merged_pkginfos_dict[key]["cuda110_12"]:
                                merged_pkginfos_dict[key]["cuda110_12"] = cuda110_12later_support
                            elif cuda110_12later_support != merged_pkginfos_dict[key][
                                "cuda110_12"
                            ] and version_parse(cuda110_12later_support) > version_parse(
                                merged_pkginfos_dict[key]["cuda110_12"]
                            ):
                                merged_pkginfos_dict[key]["cuda110_12"] = cuda110_12later_support
                        if current_timestamp > merged_pkginfos_dict[key]["timestamp"]:
                            merged_pkginfos_dict[key]["timestamp"] = current_timestamp
                    else:
                        merged_pkginfos_dict[key] = {
                            "name": pkginfo_dict["name"],
                            "version": pkginfo_dict["version"],
                            "channel": pkginfo_dict["channel"],
                            "max_py_ver": max_py_ver,
                            "min_py_ver": min_py_ver,
                            "is_cuda": is_cuda,
                            "cuda110_12": cuda110_12later_support,
                            "timestamp": current_timestamp,
                            "build_count": pkginfo_dict.get("build_count", 1),
                        }
                return list(merged_pkginfos_dict.values())

            def merge_3rd(self, pkginfo_dicts_list):
                # 第三遍合并只考虑name, channel, 并注明支持的最大Python版本，与是否存在CUDA包
                merged_pkginfos_dict = {}
                for pkginfo_dict in pkginfo_dicts_list:
                    name = pkginfo_dict["name"]
                    version = pkginfo_dict["version"]
                    is_cuda = pkginfo_dict["is_cuda"]
                    channel = pkginfo_dict["channel"]
                    current_timestamp = pkginfo_dict["timestamp"]
                    max_py_ver = pkginfo_dict["max_py_ver"]
                    min_py_ver = pkginfo_dict["min_py_ver"]
                    cuda110_12later_support = pkginfo_dict["cuda110_12"]

                    key = (name, channel)
                    if key in merged_pkginfos_dict:
                        merged_pkginfos_dict[key]["build_count"] = (
                            merged_pkginfos_dict[key]["build_count"] + pkginfo_dict["build_count"]
                        )
                        if max_py_ver:
                            if not merged_pkginfos_dict[key]["max_py_ver"]:
                                merged_pkginfos_dict[key]["max_py_ver"] = max_py_ver
                            elif max_py_ver != merged_pkginfos_dict[key]["max_py_ver"] and version_parse(
                                max_py_ver
                            ) > version_parse(merged_pkginfos_dict[key]["max_py_ver"]):
                                merged_pkginfos_dict[key]["max_py_ver"] = max_py_ver
                        if min_py_ver:
                            if not merged_pkginfos_dict[key]["min_py_ver"]:
                                merged_pkginfos_dict[key]["min_py_ver"] = min_py_ver
                            elif min_py_ver != merged_pkginfos_dict[key]["min_py_ver"] and version_parse(
                                min_py_ver
                            ) < version_parse(merged_pkginfos_dict[key]["min_py_ver"]):
                                merged_pkginfos_dict[key]["min_py_ver"] = min_py_ver
                        if not merged_pkginfos_dict[key]["version"]:
                            merged_pkginfos_dict[key]["version"] = version
                        elif version:
                            if version != merged_pkginfos_dict[key]["version"] and version_parse(
                                version
                            ) > version_parse(merged_pkginfos_dict[key]["version"]):
                                merged_pkginfos_dict[key]["version"] = version
                        if is_cuda:
                            merged_pkginfos_dict[key]["is_cuda"] = True
                        if cuda110_12later_support:
                            if not merged_pkginfos_dict[key]["cuda110_12"]:
                                merged_pkginfos_dict[key]["cuda110_12"] = cuda110_12later_support
                            elif version_parse(cuda110_12later_support) > version_parse(
                                merged_pkginfos_dict[key]["cuda110_12"]
                            ):
                                merged_pkginfos_dict[key]["cuda110_12"] = cuda110_12later_support
                        if current_timestamp > merged_pkginfos_dict[key]["timestamp"]:
                            merged_pkginfos_dict[key]["timestamp"] = current_timestamp
                    else:
                        merged_pkginfos_dict[key] = {
                            "name": pkginfo_dict["name"],
                            "version": version,
                            "channel": pkginfo_dict["channel"],
                            "max_py_ver": max_py_ver,
                            "min_py_ver": min_py_ver,
                            "cuda110_12": cuda110_12later_support,
                            "is_cuda": is_cuda,
                            "timestamp": current_timestamp,
                            "build_count": pkginfo_dict["build_count"],
                        }
                return list(merged_pkginfos_dict.values())

        def search_pkgs(target_py_version):

            print("-" * 100)
            print(
                "[提示1] 搜索默认启用的源为"
                + ColorStr.LIGHT_GREEN("pytorch,nvidia,intel,conda-forge,defaults")
                + ","
                + ColorStr.LIGHT_YELLOW("如需额外源请在末尾添加 -c 参数")
            )
            print(
                "[提示2] 可用mamba repoquery depends/whoneeds命令列出包的依赖项/列出需要给定包的程序包"
            )
            print(
                "[提示3] 搜索语法为Name=Version=Build,后两项可选 (示例:numpy>1.17,<1.19.2 *numpy*=1.17.*=py38*)"
            )
            print(
                "        (详见https://github.com/conda/conda/blob/main/docs/source/user-guide/concepts/pkg-search.rst)"
            )
            print("-" * 100)
            if target_py_version:
                print(f"(2) 请输入想要搜索的包 (适用于Python {target_py_version}),以回车结束:")
            else:
                print("(2) 请输入想要搜索的包 (适用于全部Python版本),以回车结束:")
            inp = get_valid_input(
                ">>> ",
                lambda x: x,
                lambda x: "输入" + ColorStr.LIGHT_RED("不能为空") + ",请重新输入: ",
            )
            if inp.find(" -c ") != -1:
                add_channels = [i for i in inp[inp.find(" -c ") :].split(" -c ") if i != ""]
                print(
                    ColorStr.LIGHT_YELLOW(
                        "[提示] 检测到-c参数，已自动添加相应源: "
                        + ColorStr.LIGHT_GREEN(", ".join(add_channels))
                    )
                )
                inp = inp[: inp.find(" -c ")]
            else:
                add_channels = []

            total_channels = add_channels + ["pytorch", "nvidia", "intel", "conda-forge", "defaults"]
            total_channels = ordered_unique(total_channels)
            if pkgs_index_last_update_time() < (time.time() - INDEX_CHECK_INTERVAL * 60):
                command_str = f'mamba repoquery search "{inp}" {" ".join(["-c "+i for i in total_channels])} --json --quiet'
            else:
                command_str = f'mamba repoquery search "{inp}" {" ".join(["-c "+i for i in total_channels])} --json --quiet --use-index-cache'
            command = get_cmd([command_str], discard_stderr=True)
            # print("command:", command)
            print(f"正在搜索({ColorStr.LIGHT_CYAN(inp)})...")
            t0_search = time.time()
            with os.popen(command) as f:
                result_text = f.buffer.read().decode("utf-8")
            clear_lines_above(1)
            pkg_name_to_search = inp.split("=", 1)[0]
            try:
                result_json = json.loads(result_text)
            except json.JSONDecodeError:
                print(ColorStr.LIGHT_RED("搜索结果解析失败!原始结果如下:"))
                print(result_text)
                exit(1)

            if not result_json.get("result", {}).get("pkgs"):
                if not result_json.get("result"):
                    print(json.dumps(result_json, indent=4))
                print(
                    ColorStr.LIGHT_YELLOW(
                        f"[警告] 未搜索到任何相关包({round(time.time() - t0_search, 2)} s)！"
                    )
                )
                return
            pkginfos_list_raw = result_json["result"]["pkgs"]
            # pkginfos_list_* :list[dict]每一dict是一个包的信息，list是不同的包组成的列表

            for pkginfo_dict in pkginfos_list_raw:
                filter_pkg_info(pkginfo_dict)

            merge_pkginfos = MergePkgInfos(pkginfos_list_raw)

            pkginfos_ref_dict = merge_pkginfos.get_ref_dict()

            # 为那些没有python版本信息的包，根据depends找到可能的最大最小Python版本
            pkg_eq_ver_pattern = re.compile(r"(\w+)\s+(={0,2}\d+\.[*\d]+(?:\.[*\d]+)?)")
            for i in range(len(pkginfos_list_raw)):
                if pkginfos_list_raw[i]["python_version"] is None:
                    max_py_ver = None
                    min_py_ver = None
                    for dep in pkginfos_list_raw[i]["depends"]:
                        if match := pkg_eq_ver_pattern.search(dep):
                            pkg_name = match[1]
                            pkg_version = match[2]
                            if pkg_version[-1] == "*" and pkg_version[-2] != ".":
                                pkg_version = pkg_version[:-1]
                            if matching_ref := pkginfos_ref_dict.get((pkg_name, pkg_version)):
                                if matching_ref["max_py_ver"]:
                                    if not max_py_ver:
                                        max_py_ver = matching_ref["max_py_ver"]
                                    elif version_parse(matching_ref["max_py_ver"]) > version_parse(
                                        max_py_ver
                                    ):
                                        max_py_ver = matching_ref["max_py_ver"]
                                if matching_ref["min_py_ver"]:
                                    if not min_py_ver:
                                        min_py_ver = matching_ref["min_py_ver"]
                                    elif version_parse(matching_ref["min_py_ver"]) < version_parse(
                                        min_py_ver
                                    ):
                                        min_py_ver = matching_ref["min_py_ver"]

                    if max_py_ver or min_py_ver:
                        pkginfos_list_raw[i]["py_ver_limits"] = (min_py_ver, max_py_ver)

            if target_py_version:
                pkginfos_list_0 = []
                for pkg in pkginfos_list_raw:
                    if pkg["python_version"]:
                        if is_version_within_constraints(pkg["python_version"], target_py_version):
                            pkginfos_list_0.append(pkg)
                    elif pkg.get("py_ver_limits"):
                        pkg_min_py_ver, pkg_max_py_ver = pkg["py_ver_limits"]
                        if (
                            not pkg_min_py_ver
                            or version_parse(pkg_min_py_ver) <= version_parse(target_py_version)
                        ) and (
                            not pkg_max_py_ver
                            or version_parse(pkg_max_py_ver) >= version_parse(target_py_version)
                        ):
                            pkginfos_list_0.append(pkg)
                    else:
                        pkginfos_list_0.append(pkg)

                pkginfos_list_raw = pkginfos_list_0

            class ReverseStr(str):
                def __lt__(self, other):
                    return self > other

            def _sort_by_name(name_str: str):  # v2.0版
                search_name = pkg_name_to_search.replace("*", "")
                if search_name:
                    forward, _, backward = name_str.partition(search_name)
                    return ReverseStr(forward), ReverseStr(backward)
                else:
                    return name_str

            def _sort_by_channel(channel_str):
                if channel_str in source_priority_table:
                    return (-source_priority_table[channel_str], channel_str)
                else:
                    return (0, channel_str)

            pkginfos_list_raw.sort(
                key=lambda x: (
                    _sort_by_name(x["name"]),
                    version_parse(x["version"]),
                    _sort_by_channel(x["channel"]),
                ),
                reverse=True,
            )
            # 第一遍合并需考虑build_prefix一样，按build_number大小合并
            pkginfos_list_iter1 = merge_pkginfos.merge_1st(pkginfos_list_raw)
            # 第二遍合并只考虑name, version, channel，按时间戳大小合并
            pkginfos_list_iter2 = merge_pkginfos.merge_2nd(pkginfos_list_raw)
            # 第三遍合并只考虑name, channel
            pkginfos_list_iter3 = merge_pkginfos.merge_3rd(pkginfos_list_iter2)

            def _get_overview_table(pkg_overviews_list, user_options):
                """适用于user_options["display_mode"]等于1的情况"""
                name_field = "Name"
                version_field = (
                    f"{ColorStr.LIGHT_GREEN('Latest')} Version"
                    if user_options["merge_version"]
                    else "Version"
                )
                build_count_field = "(Total Builds)"
                channel_field = "Channel"
                python_version_field = "MinMax PyVer"
                cuda_field = "CUDA" + f" (11 or later)"
                timestamp_field = "Last Update"

                table_fields = [
                    name_field,
                    version_field,
                    channel_field,
                    python_version_field,
                    cuda_field,
                    timestamp_field,
                    build_count_field,
                ]
                if user_options["select_mode"]:
                    table_fields.insert(0, "No.")

                table = PrettyTable(table_fields)
                table.align[name_field] = "l"
                table.align[version_field] = "c"
                table.align[channel_field] = "r"
                table.align[python_version_field] = "c"
                table.align[cuda_field] = "r"
                table.align[timestamp_field] = "r"
                table.border = False

                if len(pkg_overviews_list) == 0:
                    table.add_row(["-" for _ in range(len(table_fields))])
                    table.align = "l"
                    return table

                name_maxversion_dict = {}
                for pkg_overview in pkg_overviews_list:
                    name = pkg_overview["name"]
                    version = pkg_overview["version"]
                    if name in name_maxversion_dict:
                        if version_parse(version) > version_parse(name_maxversion_dict[name]):
                            name_maxversion_dict[name] = version
                    else:
                        name_maxversion_dict[name] = version

                for i, pkg_overview in enumerate(pkg_overviews_list, 1):
                    min_py_ver = pkg_overview["min_py_ver"]
                    max_py_ver = pkg_overview["max_py_ver"]
                    if min_py_ver and max_py_ver and min_py_ver == max_py_ver:
                        python_version_range = min_py_ver
                    elif min_py_ver and max_py_ver:
                        python_version_range = f"{min_py_ver:<4}~ {max_py_ver:4}"
                    elif min_py_ver:
                        python_version_range = f"{min_py_ver:<4}~  ?  "
                    elif max_py_ver:
                        python_version_range = f" ?  ~ {max_py_ver:4}"
                    else:
                        python_version_range = f"{'':4}-{'':5}"

                    if pkg_overview["is_cuda"]:
                        cuda_support = ColorStr.LIGHT_GREEN("Y")
                    else:
                        cuda_support = ColorStr.LIGHT_RED("N")

                    if pkg_overview["cuda110_12"]:
                        cuda110_12 = pkg_overview["cuda110_12"]
                        if version_parse(cuda110_12) >= version_parse("12"):
                            cuda110_12 = f'({ColorStr.LIGHT_GREEN(f"{cuda110_12:^10}")})'
                        elif version_parse(cuda110_12) >= version_parse("11.8"):
                            cuda110_12 = f'({ColorStr.LIGHT_CYAN(f"{cuda110_12:^10}")})'
                        else:
                            cuda110_12 = f"({cuda110_12:^10})"

                        cuda_support += f"{'':3}{cuda110_12}"
                    else:
                        cuda_support += f"{'':15}"

                    if len(pkg_overview["version"]) > 15:
                        version_str = pkg_overview["version"][:12] + "..."
                    else:
                        version_str = pkg_overview["version"]

                    name_str = pkg_overview["name"]
                    channel_str = pkg_overview["channel"]
                    if pkg_overview["name"] in name_maxversion_dict:
                        max_version = name_maxversion_dict[pkg_overview["name"]]
                        if max_version == pkg_overview["version"]:
                            # name_str = ColorStr.LIGHT_CYAN(name_str)
                            version_str = ColorStr.LIGHT_GREEN(version_str)
                            # channel_str = ColorStr.LIGHT_CYAN(channel_str)

                    row = [
                        name_str,
                        version_str,
                        channel_str,
                        python_version_range,
                        cuda_support,
                        time.strftime("%Y-%m-%d", time.gmtime(pkg_overview["timestamp"])),
                        f"({pkg_overview['build_count']:5d} builds)",
                    ]
                    if user_options["select_mode"]:
                        row.insert(0, f"[{i}]")
                    table.add_row(row)

                return table

            def beautify_version_constraints(constraints_str):
                constraints_units = constraints_str.split("|")
                merged_constraint_units = []
                only_version_units = set()

                for unit in constraints_units:
                    if "," in unit and "!=" in unit:
                        merged_unit = merge_not_equal_constraints(unit)
                        merged_constraint_units.append(merged_unit)
                    elif match := re.match(r"={0,2}(\d+)\.(\d+)", unit):
                        only_version_units.add((int(match[1]), int(match[2])))
                    else:
                        merged_constraint_units.append(unit)
                if only_version_units:
                    only_version_units = sorted(list(only_version_units))
                    start_version = end_version = (
                        f"{only_version_units[0][0]}.{only_version_units[0][1]}"
                    )

                    for i, unit in enumerate(only_version_units):
                        if i == 0:
                            continue
                        if (
                            unit[0] == only_version_units[i - 1][0]
                            and unit[1] == only_version_units[i - 1][1] + 1
                        ):
                            end_version = f"{unit[0]}.{unit[1]}"
                        else:
                            if (
                                start_version == end_version
                                and start_version not in merged_constraint_units
                            ):
                                merged_constraint_units.append(start_version)
                            else:
                                merged_constraint_units.append(f"{start_version}~{end_version}")
                            start_version = end_version = f"{unit[0]}.{unit[1]}"
                    if start_version == end_version and start_version not in merged_constraint_units:
                        merged_constraint_units.append(start_version)
                    else:
                        merged_constraint_units.append(f"{start_version}~{end_version}")

                def _sort_version(version_str):
                    pattern = re.compile(r"(\d+)\.([\d*]+)")
                    if match := pattern.search(version_str):
                        if "*" in match[2]:
                            return (int(match[1]), 0)
                        else:
                            return (int(match[1]), int(match[2]))
                    else:
                        return (0, 0)

                merged_constraint_units.sort(key=_sort_version)

                return "|".join(merged_constraint_units)

            def merge_not_equal_constraints(constraints_str):

                def _lazy_int(s):
                    return int(s) if s.isdigit() else s

                constraints_list = constraints_str.split(",")
                not_equal_versions = [c for c in constraints_list if c.startswith("!=")]
                not_equal_versions.sort(
                    key=lambda x: (_lazy_int(x[2:].split(".")[0]), _lazy_int(x[2:].split(".")[1]))
                )
                other_versions = [c for c in constraints_list if not c.startswith("!=")]

                merged_not_equal_versions = []
                current_group = [not_equal_versions[0]]
                for i in range(1, len(not_equal_versions)):
                    current = not_equal_versions[i]
                    prev = not_equal_versions[i - 1]
                    current_version = current[2:]  # 去除 "!=" 前缀
                    prev_version = prev[2:]  # 去除 "!=" 前缀
                    current_parts = current_version.split(".")
                    prev_parts = prev_version.split(".")

                    # 检查主版本号是否相等，并且次版本号相差 1
                    if (
                        current_parts[0] == prev_parts[0]
                        and int(current_parts[1]) == int(prev_parts[1]) + 1
                    ):
                        current_group.append(current)
                    else:
                        # 添加上一个分组的合并结果
                        if len(current_group) > 1:
                            start_version = current_group[0][2:]  # 去除 "!=" 前缀
                            end_version = prev_version  # 使用上一个版本号的结束作为当前范围的结束
                            merged_not_equal_versions.append(f"!={start_version}~{end_version}")
                        else:
                            merged_not_equal_versions.append(current_group[0])
                        # 重置当前分组
                        current_group = [current]

                # 处理最后一个分组
                if len(current_group) > 1:
                    start_version = current_group[0][2:]  # 去除 "!=" 前缀
                    end_version = current_group[-1][2:]  # 去除 "!=" 前缀
                    merged_not_equal_versions.append(f"!={start_version}~{end_version}")
                else:
                    merged_not_equal_versions.append(current_group[0])

                versions = other_versions + merged_not_equal_versions

                return ",".join(versions)

            def _get_pkgs_table(pkginfos_list, user_options):
                """适用于user_options["display_mode"]等于2或3的情况"""
                if user_options["display_mode"] == 1:
                    return _get_overview_table(pkginfos_list, user_options)

                if user_options["sort_by"][1]:
                    sort_flag = ColorStr.LIGHT_GREEN("▼")
                else:
                    sort_flag = ColorStr.LIGHT_GREEN("▲")

                if len(pkginfos_list) > 0:
                    build_lengths = list(map(lambda x: len(x["build"]), pkginfos_list))
                    build_lengths.sort()
                    if user_options["display_mode"] == 3:
                        max_build_length = build_lengths[-1]
                    else:
                        import math

                        # 计算90%位置的索引
                        index_90_percent = math.ceil(0.9 * len(build_lengths))
                        max_build_length = build_lengths[index_90_percent - 1]
                        if max_build_length < 15:
                            max_build_length = 15
                    # print("max_build_length:", max_build_length)
                    if max(map(lambda x: x.get("build_count", 1), pkginfos_list)) > 1:
                        build_field = (
                            "Build"
                            + " "
                            * (
                                max_build_length
                                + len(f"  (+{1:3d} builds)")
                                - len("Build")
                                - len("(similar builds)")
                            )
                            + "(similar builds)"
                        )
                    else:
                        build_field = "Build"
                else:
                    build_field = "Build"
                name_field = "Name" + (sort_flag if user_options["sort_by"][0] == "name/version" else "")
                version_field = "Version" + (
                    sort_flag if user_options["sort_by"][0] == "name/version" else ""
                )
                build_field = build_field + (sort_flag if user_options["sort_by"][0] == "build" else "")
                channel_field = "Channel" + (
                    sort_flag if user_options["sort_by"][0] == "channel" else ""
                )
                python_version_field = "Py Version" + (
                    sort_flag if user_options["sort_by"][0] == "python_version" else ""
                )
                cuda_version_field = "CUDA Version" + (
                    sort_flag if user_options["sort_by"][0] == "cuda_version" else ""
                )
                size_field = "Size" + (sort_flag if user_options["sort_by"][0] == "size" else "")
                timestamp_field = "Timestamp" + (
                    sort_flag if user_options["sort_by"][0] == "timestamp" else ""
                )

                table_fields = [
                    name_field,
                    version_field,
                    build_field,
                    channel_field,
                    python_version_field,
                    cuda_version_field,
                    size_field,
                    timestamp_field,
                ]
                if user_options["select_mode"]:
                    table_fields.insert(0, "No.")
                table = PrettyTable(table_fields)
                # table.align = "l"
                table.align[name_field] = "l"
                table.align[version_field] = "l"
                table.align[build_field] = "l"
                table.align[channel_field] = "r"
                table.align[python_version_field] = "c"
                table.align[cuda_version_field] = "c"
                table.align[size_field] = "r"
                table.align[timestamp_field] = "r"
                # table.padding_width = 1
                table.border = False

                if len(pkginfos_list) == 0:
                    table.add_row(["-" for _ in range(len(table_fields))])
                    table.align = "l"
                    return table

                for i, pkginfo_dict in enumerate(pkginfos_list, 1):
                    python_version = pkginfo_dict["python_version"] or "-"
                    python_version = beautify_version_constraints(python_version)

                    if pkginfo_dict["cuda_version"]:
                        cuda_info = pkginfo_dict["cuda_version"]
                    elif pkginfo_dict["is_cuda"]:
                        cuda_info = "UNKNOWN"
                    else:
                        cuda_info = "  "
                    build_count = pkginfo_dict.get("build_count", 1)
                    if build_count > 1:
                        build_count_str = f"  (+{build_count-1:3d} builds)"
                    else:
                        build_count_str = ""
                    build_length = len(pkginfo_dict["build"])
                    if build_length <= max_build_length:
                        build_str = "{:<{build_width}}".format(
                            pkginfo_dict["build"], build_width=max_build_length
                        )
                    else:
                        build_str = "{:<{build_width}}".format(
                            pkginfo_dict["build"][: max_build_length - 3] + "...",
                            build_width=max_build_length,
                        )
                    build_show_str = build_str + build_count_str
                    if len(pkginfo_dict["version"]) > 15:
                        version_str = pkginfo_dict["version"][:12] + "..."
                    else:
                        version_str = pkginfo_dict["version"]
                    row = [
                        pkginfo_dict["name"],
                        version_str,
                        build_show_str,
                        pkginfo_dict["channel"],
                        python_version,
                        cuda_info,
                        print_fsize_smart(pkginfo_dict["size"]),
                        time.strftime("%Y-%m-%d", time.gmtime(pkginfo_dict["timestamp"])),
                    ]
                    if user_options["select_mode"]:
                        row.insert(0, f"[{i}]")
                    table.add_row(row)

                return table

            def _print_transaction(user_options):
                def _get_python_versionstr(version_str):
                    if version_str and (
                        findall_list := re.findall(r"(?:2|3|4)(?:\.[a-zA-Z\d]{1,3})?", version_str)
                    ):
                        if (index := version_str.find(findall_list[-1])) > 0:
                            op = ""
                            while version_str[index - 1] in [
                                "<",
                                ">",
                                "=",
                                "!",
                            ]:
                                op += version_str[index - 1]
                                index -= 1
                            op = op[::-1]
                            if op == "=":
                                version_str = findall_list[-1]
                            elif op == "!=":
                                version_str = findall_list[-1] + ".3"
                            elif op == ">":
                                version_str = findall_list[-1] + ".2"
                            elif op == ">=":
                                version_str = findall_list[-1] + ".1"
                            elif op == "<":
                                version_str = findall_list[-1] + ".a0"
                            elif op == "<=":
                                version_str = findall_list[-1] + ".b0"
                            else:
                                version_str = findall_list[-1]
                    if not version_str:
                        version_str = "0.0"
                    return version_str

                def _get_cuda_versionstr_from_pkgdict(pkginfo_dict, filter_to_pure_version=True):
                    if filter_to_pure_version:
                        if pkginfo_dict["cuda_version"] and (
                            finall_list := re.findall(
                                r"\d{1,2}(?:\.[a-zA-Z\d]{1,3})?", pkginfo_dict["cuda_version"]
                            )
                        ):
                            version_str = finall_list[-1]
                        elif pkginfo_dict["is_cuda"]:
                            version_str = "UNKNOWN"
                        else:
                            version_str = "  "
                    else:
                        if pkginfo_dict["cuda_version"]:
                            version_str = pkginfo_dict["cuda_version"]
                        elif pkginfo_dict["is_cuda"]:
                            version_str = "UNKNOWN"
                        else:
                            version_str = "  "
                    return version_str

                def _parse_cuda_version(version_str):
                    if version_str == "  ":
                        return version_parse("0.0.0")
                    elif version_str == "UNKNOWN":
                        return version_parse("0.0.1")
                    else:
                        return version_parse(version_str)

                if not user_options["need_reprint"]:
                    return []
                display_mode = user_options["display_mode"]
                sort_by = user_options["sort_by"]
                filters = user_options["filters"]

                if display_mode == 1 and user_options["merge_version"]:
                    pkginfos_list = pkginfos_list_iter3
                elif display_mode == 1 and not user_options["merge_version"]:
                    pkginfos_list = pkginfos_list_iter2
                elif display_mode == 2:
                    pkginfos_list = pkginfos_list_iter1
                else:  # display_mode == 3
                    pkginfos_list = pkginfos_list_raw
                pkginfos_list = pkginfos_list.copy()

                if display_mode != 1:
                    for filter_name, filter_value in filters.items():
                        if filter_value:
                            if filter_name == "is_cuda_only":
                                pkginfos_list = [
                                    pkginfo_dict
                                    for pkginfo_dict in pkginfos_list
                                    if pkginfo_dict["is_cuda"]
                                ]
                            elif filter_name == "version":
                                pkginfos_list = [
                                    pkginfo_dict
                                    for pkginfo_dict in pkginfos_list
                                    if is_version_within_constraints(
                                        pkginfo_dict[filter_name], filter_value
                                    )
                                ]
                            elif filter_name == "python_version":
                                pkginfos_list_processed = []
                                for pkginfo_dict in pkginfos_list:
                                    if pkginfo_dict["python_version"]:
                                        if is_version_within_constraints(
                                            pkginfo_dict["python_version"], filter_value
                                        ):
                                            pkginfos_list_processed.append(pkginfo_dict)
                                    elif pkginfo_dict.get("py_ver_limits"):
                                        min_py_ver, max_py_ver = pkginfo_dict["py_ver_limits"]
                                        py_ver_constraint_list = []
                                        if min_py_ver:
                                            py_ver_constraint_list.append(f">={min_py_ver}")
                                        if max_py_ver:
                                            py_ver_constraint_list.append(f"<={max_py_ver}")
                                        py_ver_constraint_str = ",".join(py_ver_constraint_list)
                                        if is_version_within_constraints(
                                            py_ver_constraint_str, filter_value
                                        ):
                                            pkginfos_list_processed.append(pkginfo_dict)
                                    else:
                                        pkginfos_list_processed.append(pkginfo_dict)
                                pkginfos_list = pkginfos_list_processed

                            elif filter_name == "cuda_version":
                                pkginfos_list = [
                                    pkginfo_dict
                                    for pkginfo_dict in pkginfos_list
                                    if is_version_within_constraints(
                                        _get_cuda_versionstr_from_pkgdict(
                                            pkginfo_dict, filter_to_pure_version=False
                                        ),
                                        filter_value,
                                        always_true_strs=["UNKNOWN"],
                                        always_false_strs=["  "],
                                    )
                                ]
                            else:
                                pattern = re.compile("^" + filter_value.replace("*", ".*") + "$")
                                pkginfos_list = [
                                    pkginfo_dict
                                    for pkginfo_dict in pkginfos_list
                                    if pattern.match(pkginfo_dict[filter_name])
                                ]
                    # sort_by[0] == "name/version"就是按名称/版本排序
                    if sort_by[0] == "name/version":
                        pkginfos_list.sort(
                            key=lambda x: (
                                _sort_by_name(x["name"]),
                                version_parse(x["version"]),
                                # _sort_by_channel(x["channel"]),
                            ),
                            reverse=sort_by[1],
                        )
                    elif sort_by[0] == "python_version":
                        pkginfos_list.sort(
                            key=lambda x: version_parse(_get_python_versionstr(x[sort_by[0]])),
                            reverse=sort_by[1],
                        )
                    elif sort_by[0] == "cuda_version":
                        pkginfos_list.sort(
                            key=lambda x: _parse_cuda_version(_get_cuda_versionstr_from_pkgdict(x)),
                            reverse=sort_by[1],
                        )
                    elif sort_by[0] == "channel":
                        pkginfos_list.sort(
                            key=lambda x: _sort_by_channel(x[sort_by[0]]), reverse=sort_by[1]
                        )

                    elif sort_by[0]:
                        pkginfos_list.sort(
                            key=lambda x: x[sort_by[0]],
                            reverse=sort_by[1],
                        )
                elif display_mode == 1 and user_options["reversed_display"]:
                    pkginfos_list = pkginfos_list[::-1]
                table = _get_pkgs_table(pkginfos_list, user_options)

                table_header, table_body = table.get_string().split("\n", 1)
                print(table_header)
                print("-" * len(table_header))
                print(table_body)
                if user_options["select_mode"]:
                    print("-" * len(table_header))

                return pkginfos_list

            def _get_user_options(user_options, pkginfos_list):
                user_options["need_reprint"] = True

                num_lines = 0

                filters = user_options["filters"]
                sort_by = user_options["sort_by"]

                is_filtered = any(filter_value for filter_value in filters.values())

                if user_options["select_mode"]:
                    if user_options["display_mode"] != 1:
                        while user_options["select_mode"]:
                            num_lines += count_lines_and_print(
                                f"(i) 请输入要查看详细信息的包对应编号(带{ColorStr.LIGHT_CYAN('=')}号则显示安装命令行并拷贝到剪贴板): "
                            )
                            key = input_with_arrows(">>> ")
                            num_lines += 1
                            if key == "":
                                user_options["select_mode"] = False
                                return num_lines
                            elif key.isdigit():
                                if 1 <= int(key) <= len(pkginfos_list):
                                    clear_lines_above(num_lines)
                                    num_lines = 0
                                    pkginfo_dict = pkginfos_list[int(key) - 1].copy()
                                    pkginfo_dict["size"] = print_fsize_smart(pkginfo_dict["size"])
                                    pkginfo_dict["timestamp"] = time.strftime(
                                        "%Y-%m-%d %H:%M:%S", time.gmtime(pkginfo_dict["timestamp"])
                                    )
                                    print_str = "=" * 30
                                    print_str += f"[{key}]包{ColorStr.LIGHT_CYAN(pkginfo_dict['name'])} {ColorStr.LIGHT_GREEN(pkginfo_dict['version'])}的详细信息如下"
                                    print_str += "=" * 30
                                    num_lines += count_lines_and_print(print_str)
                                    pkginfo_dict_copy = pkginfo_dict.copy()
                                    pkginfo_dict_copy.pop("build_count", None)
                                    pkginfo_dict_copy.pop("build_prefix", None)
                                    pkginfo_dict_copy.pop("build_string", None)
                                    pkginfo_dict_copy.pop("python_version", None)
                                    pkginfo_dict_copy.pop("cuda_version", None)
                                    pkginfo_dict_copy.pop("is_cuda", None)
                                    if not pkginfo_dict_copy.get("track_features"):
                                        pkginfo_dict_copy.pop("track_features")
                                    if not pkginfo_dict_copy.get("constrains"):
                                        pkginfo_dict_copy.pop("constrains")
                                    print_str = json.dumps(pkginfo_dict_copy, indent=4, skipkeys=True)
                                    num_lines += count_lines_and_print(print_str)
                            elif key.find("=") != -1:
                                key = key.replace("=", "")
                                if key.isdigit() and 1 <= int(key) <= len(pkginfos_list):
                                    clear_lines_above(num_lines)
                                    num_lines = 0
                                    pkginfo_dict = pkginfos_list[int(key) - 1]
                                    name = pkginfo_dict["name"]
                                    version = pkginfo_dict["version"]
                                    build = pkginfo_dict["build"]
                                    channel = pkginfo_dict["channel"]
                                    print_str = "mamba" if IS_MAMBA else "conda"
                                    print_str += f" install {name}={version}={build}"
                                    if channel not in ("defaults", "conda-forge"):
                                        print_str += f" -c {channel}"
                                    num_lines += count_lines_and_print(print_str)
                                    if os.name == "posix":
                                        if (
                                            os.system(f'echo "{print_str}" | xclip -selection clipboard')
                                            == 0
                                        ):
                                            num_lines += count_lines_and_print(
                                                ColorStr.LIGHT_GREEN("[提示] 安装命令已拷贝到剪贴板！")
                                            )
                                    elif os.name == "nt":
                                        if os.system(f'echo "{print_str}" | clip') == 0:
                                            num_lines += count_lines_and_print(
                                                ColorStr.LIGHT_GREEN("[提示] 安装命令已拷贝到剪贴板！")
                                            )

                            else:
                                clear_lines_above(2)
                                num_lines -= 2
                    else:  # display_mode == 1
                        num_lines += count_lines_and_print(
                            "(i) 请输入要跳转到原始显示模式并过滤的包版本对应编号:"
                        )
                        key = input_with_arrows(">>> ")
                        num_lines += 1
                        if key.isdigit() and 1 <= int(key) <= len(pkginfos_list):
                            pkginfo_dict = pkginfos_list[int(key) - 1].copy()
                            filters["name"] = pkginfo_dict["name"]
                            if not user_options["merge_version"]:
                                filters["version"] = pkginfo_dict["version"]
                            filters["channel"] = pkginfo_dict["channel"]
                            user_options["display_mode"] = 3
                            user_options["select_mode"] = False
                            return num_lines
                        else:
                            user_options["select_mode"] = False
                            clear_lines_above(num_lines)
                            num_lines = 0

                if user_options["display_mode"] == 1:
                    print_str = (
                        ColorStr.LIGHT_CYAN("[1] 概览") + "\t" + "[2] 精简显示" + "\t" + "[3] 原始显示"
                    )
                elif user_options["display_mode"] == 2:
                    print_str = (
                        "[1] 概览" + "\t" + ColorStr.LIGHT_CYAN("[2] 精简显示") + "\t" + "[3] 原始显示"
                    )
                else:  # display_mode == 3
                    print_str = (
                        "[1] 概览" + "\t" + "[2] 精简显示" + "\t" + ColorStr.LIGHT_CYAN("[3] 原始显示")
                    )
                print_str += "\t"
                if user_options["display_mode"] != 1:
                    if is_filtered:
                        print_str += ColorStr.LIGHT_GREEN("[F] 过滤器")
                    else:
                        print_str += "[F] 过滤器"
                    print_str += "\t"
                    if sort_by[0]:
                        print_str += ColorStr.LIGHT_GREEN("[S] 排序")
                    else:
                        print_str += "[S] 排序"
                    print_str += "\t"
                    print_str += "[V] 查看包详情"
                else:
                    print_str += "[V] 选择以过滤原始显示"
                    print_str += "\t"
                    if user_options["merge_version"]:
                        print_str += ColorStr.LIGHT_GREEN("[M] 合并版本号")
                    else:
                        print_str += "[M] 合并版本号"
                    print_str += "\t"
                    if user_options["reversed_display"]:
                        print_str += ColorStr.LIGHT_CYAN("[R] 倒序显示")
                    else:
                        print_str += "[R] 倒序显示"
                print_str += "\t" + ColorStr.LIGHT_YELLOW("[Esc] 退出")
                num_lines += count_lines_and_print(print_str)

                filter_enable_list = []
                if filters["name"]:
                    filter_enable_list.append(("Name", filters["name"]))
                if filters["version"]:
                    filter_enable_list.append(("Version", filters["version"]))
                if filters["channel"]:
                    filter_enable_list.append(("Channel", filters["channel"]))
                if filters["python_version"]:
                    filter_enable_list.append(("Python_Version", filters["python_version"]))
                if filters["cuda_version"]:
                    filter_enable_list.append(("CUDA_Version", filters["cuda_version"]))
                if filters["is_cuda_only"]:
                    filter_enable_list.append(("CUDA_Only", filters["is_cuda_only"]))

                if sort_by[0]:
                    print_str = " " * 8 + "[排序] 依据为 "
                    print_str += ColorStr.LIGHT_GREEN(f'{sort_by[0]}{("▼" if sort_by[1] else "▲")}')

                    print_str += "  "
                    print_str += "(按↑ |↓ 键切换为升序|降序)"
                if filter_enable_list:
                    if sort_by[0]:
                        print_str += "  ;  [过滤器] "
                    else:
                        print_str = " " * 8 + "[过滤器] "
                    for i, (filter_name, filter_value) in enumerate(filter_enable_list):
                        if i:
                            print_str += ", "
                        print_str += (
                            f"{ColorStr.LIGHT_CYAN(filter_name)}({ColorStr.LIGHT_GREEN(filter_value)})"
                        )
                if sort_by[0] or filter_enable_list:
                    num_lines += count_lines_and_print(print_str)

                key = get_char(echo=False)

                if key == "1":
                    user_options["display_mode"] = 1
                    user_options["sort_by"] = ["", True]
                    user_options["filters"] = {
                        "name": None,
                        "version": None,
                        "channel": None,
                        "python_version": None,
                        "cuda_version": None,
                        "is_cuda_only": False,
                    }
                elif key == "2" or key == "3":
                    user_options["display_mode"] = int(key)
                elif key in ("S", "s") and user_options["display_mode"] != 1:
                    if sort_by[0]:
                        sort_by[0] = ""
                    else:
                        clear_lines_above(num_lines)
                        num_lines = 0
                        num_lines += count_lines_and_print("(i) 请按下排序依据对应的序号: ")
                        # (名称/版本/Channel/Python版本/大小/时间戳)
                        print_strs = [
                            (
                                ColorStr.LIGHT_GREEN("[1] 名称/版本")
                                if sort_by[0] == "name/version"
                                else "[1] 名称/版本"
                            ),
                            (
                                ColorStr.LIGHT_GREEN("[2] Channel")
                                if sort_by[0] == "channel"
                                else "[2] Channel"
                            ),
                            (
                                ColorStr.LIGHT_GREEN("[3] Python版本")
                                if sort_by[0] == "python_version"
                                else "[3] Python版本"
                            ),
                            (
                                ColorStr.LIGHT_GREEN("[4] CUDA版本")
                                if sort_by[0] == "cuda_version"
                                else "[4] CUDA版本"
                            ),
                            ColorStr.LIGHT_GREEN("[5] 大小") if sort_by[0] == "size" else "[5] 大小",
                            (
                                ColorStr.LIGHT_GREEN("[6] 时间戳")
                                if sort_by[0] == "timestamp"
                                else "[6] 时间戳"
                            ),
                        ]
                        num_lines += count_lines_and_print("\t".join(print_strs))

                        key1 = get_char(echo=False)
                        if key1 == "1":
                            sort_by[0] = "name/version"
                        elif key1 == "2":
                            sort_by[0] = "channel"
                        elif key1 == "3":
                            sort_by[0] = "python_version"
                        elif key1 == "4":
                            sort_by[0] = "cuda_version"
                        elif key1 == "5":
                            sort_by[0] = "size"
                        elif key1 == "6":
                            sort_by[0] = "timestamp"
                        else:
                            sort_by[0] = ""
                elif (
                    key in ("\x1b[A", "\x1b[B", "àH", "àP")
                    and sort_by[0]
                    and user_options["display_mode"] != 1
                ):
                    if key in ("\x1b[A", "àH") and sort_by[1]:
                        sort_by[1] = False
                    elif key in ("\x1b[B", "àP") and not sort_by[1]:
                        sort_by[1] = True
                    else:
                        user_options["need_reprint"] = False

                elif key in ("F", "f") and user_options["display_mode"] != 1:
                    clear_lines_above(num_lines)
                    num_lines = 0
                    num_lines += count_lines_and_print("(i) 请按下过滤目标对应的序号: ")
                    print_strs = [
                        ColorStr.LIGHT_GREEN("[1] 名称") if filters["name"] else "[1] 名称",
                        ColorStr.LIGHT_GREEN("[2] 版本") if filters["version"] else "[2] 版本",
                        ColorStr.LIGHT_GREEN("[3] Channel") if filters["channel"] else "[3] Channel",
                        (
                            ColorStr.LIGHT_GREEN("[4] Python版本")
                            if filters["python_version"]
                            else "[4] Python版本"
                        ),
                        (
                            ColorStr.LIGHT_GREEN("[5] CUDA版本")
                            if filters["cuda_version"]
                            else "[5] CUDA版本"
                        ),
                        (
                            ColorStr.LIGHT_GREEN("[6] 只显示CUDA")
                            if filters["is_cuda_only"]
                            else "[6] 只显示CUDA"
                        ),
                    ]
                    num_lines += count_lines_and_print("\t".join(print_strs))
                    key1 = get_char(echo=False)
                    if key1 == "1":
                        if filters["name"]:
                            filters["name"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += count_lines_and_print("(ii) 请输入名称过滤器(支持通配符*): ")
                            filters["name"] = input(">>> ")
                            num_lines += 1
                    elif key1 == "2":
                        if filters["version"]:
                            filters["version"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += count_lines_and_print(
                                "(ii) 请输入版本过滤器(支持比较式[示例: 1.19|<2|>=2.6,<2.10.0a0,!=2.9.*]): "
                            )
                            filters["version"] = input(">>> ")
                            num_lines += 1
                    elif key1 == "3":
                        if filters["channel"]:
                            filters["channel"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += count_lines_and_print("(ii) 请输入Channel过滤器(支持通配符*): ")
                            filters["channel"] = input(">>> ")
                            num_lines += 1
                    elif key1 == "4":
                        if filters["python_version"]:
                            filters["python_version"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += count_lines_and_print(
                                "(ii) 请输入Python版本过滤器(支持主次版本号比较式[示例: >=3.11|3.7|!=2.*,<3.10a0,!=3.8]): "
                            )
                            filters["python_version"] = input(">>> ")
                            num_lines += 1
                    elif key1 == "5":
                        if filters["cuda_version"]:
                            filters["cuda_version"] = None
                            filters["is_cuda_only"] = False
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += count_lines_and_print(
                                "(ii) 请输入CUDA版本过滤器(支持主次版本号比较式[示例: !=12.2,<=12.3|>=9,<13.0a0,!=10.*]): "
                            )
                            filters["cuda_version"] = input(">>> ")
                            filters["is_cuda_only"] = True
                            num_lines += 1
                    elif key1 == "6":
                        filters["is_cuda_only"] = not filters["is_cuda_only"]
                elif key == "V" or key == "v":
                    user_options["select_mode"] = True
                elif key == "M" or key == "m" and user_options["display_mode"] == 1:
                    user_options["merge_version"] = not user_options["merge_version"]
                elif key == "R" or key == "r" and user_options["display_mode"] == 1:
                    user_options["reversed_display"] = not user_options["reversed_display"]
                elif key == "\x1b" or key == "\x03":
                    user_options["exit"] = True
                else:
                    user_options["need_reprint"] = False

                return num_lines

            user_options = {
                "display_mode": 1,  # 显示模式(取值为1,2,3，由按键决定) 1对应pkginfos_list_iter2，2对应pkginfos_list_iter1，3对应pkginfos_list_raw
                "sort_by": [
                    "",
                    True,
                ],  # 排序依据，按键[S]
                "filters": {  # 过滤器字典，按键[F]
                    "name": None,  # 名称过滤器，取值为字符串或None
                    "version": None,  # 版本过滤器，取值为字符串或None
                    "channel": None,  # Channel过滤器，取值为字符串或None
                    "python_version": None,  # Python 版本过滤器，取值为字符串或None
                    "cuda_version": None,  # CUDA 版本过滤器，取值为字符串或None
                    "is_cuda_only": False,  # 是否 CUDA 过滤器，取值为布尔值
                },
                "select_mode": False,
                "merge_version": False,  # 是否合并版本号相同的包,dipslay_mode为1时有效
                "reversed_display": False,  # 倒序显示,display_mode为1时有效
                "exit": False,  # 退出标志，按键Esc或Ctrl+C为其赋值
                "need_reprint": True,
                # "hidden_columns": [],  # 不显示的列,取值为 name,version,build,channel,python_version,,cuda_version,size,timestamp
            }

            def filter_version_major_minor(version_str):
                pattern = re.compile(r"([\d*]{1,3})\.([\d*]{1,3})(?:\.[a-zA-Z\d.*]+)*")
                return pattern.sub(shorten_version, version_str)

            if os.name == "nt":
                os.system("cls")
            else:
                os.system("clear")
            pkginfos_list = _print_transaction(user_options)
            print("-" * 100)
            print(
                ColorStr.LIGHT_GREEN(f"搜索完成({round(time.time() - t0_search, 2)} s)！"),
                f"对于{ColorStr.LIGHT_CYAN(inp)},共找到{ColorStr.LIGHT_CYAN(len(pkginfos_list_raw))}个相关包,搜索结果如上",
            )
            print("-" * 100)
            num_lines_2 = _get_user_options(user_options, pkginfos_list)
            while not user_options["exit"]:
                if filter_value := user_options["filters"]["python_version"]:
                    user_options["filters"]["python_version"] = filter_version_major_minor(filter_value)
                if filter_value := user_options["filters"]["cuda_version"]:
                    user_options["filters"]["cuda_version"] = filter_version_major_minor(filter_value)
                if user_options["need_reprint"]:
                    if os.name == "nt":
                        os.system("cls")
                    else:
                        os.system("clear")
                else:
                    clear_lines_above(num_lines_2)
                pkginfos_list = _print_transaction(user_options)
                num_lines_2 = _get_user_options(user_options, pkginfos_list)

        while True:
            search_pkgs(target_py_version)
            print()
            if target_py_version:
                print(f"(i) 是否继续为 Python {target_py_version} 查找包? [Y(回车)/n]")
            else:
                print("(i) 是否继续为所有 Python 版本查找包? [Y(回车)/n]")
            inp = input_with_arrows("[(Y)/n] >>> ")
            if inp not in ("y", "Y", "\r", "\n", ""):
                break
        res = 1
    # 如果输入的是[H],则显示conda doctor健康报告
    elif inp in ["H", "h"]:
        if not CONDA_VERSION or Version(CONDA_VERSION) < Version("23.5.0"):
            print(
                ColorStr.LIGHT_RED(
                    "[错误] conda doctor命令需要conda 23.5.0及以上版本支持,请在base环境升级conda后重试!"
                )
            )
            print("升级conda命令: conda update -n base -c defaults conda")
            return 1
        print("(1) 请输入想要检查完整性的环境的编号(默认为全部),多个以空格隔开,以回车结束: ")
        inp = input_with_arrows(f"[(ALL) | 1-{env_num}] >>> ")
        if inp.lower() in ["all", ""]:
            env_check_names = [i for i in env_namelist]
        else:
            env_check_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
            env_check_names = [env_namelist[i] for i in env_check_nums]
        for i, env_name in enumerate(env_check_names, 1):
            print(
                f"[{i}/{len(env_check_names)}] 正在检查环境{ColorStr.LIGHT_CYAN(env_name)}的健康情况..."
            )
            command = get_cmd([f"conda doctor -n {env_name}"])
            print("-" * 50)
            os.system(command)
            print("-" * 50)

        res = 1
    # 如果输入的是[=编号]，则浏览环境主目录
    elif inp.find("=") != -1:
        inp = int(inp[1:])
        env_name = env_namelist[inp - 1]
        print(
            ColorStr.LIGHT_GREEN(
                f"[提示] 已在文件资源管理器中打开环境{ColorStr.LIGHT_CYAN(env_name)}的主目录:"
            )
        )
        env_path = env_pathlist[inp - 1]
        print(env_path)
        if os.name == "nt":
            os.system(f"start {env_path}")
        else:
            os.system(f"xdg-open {env_path}")
        res = 1
    # 如果输入的是[Q]，则退出
    elif inp in ["Q", "q", "\x03"]:
        res = 0
    # 如果输入的是数字，则进入对应的环境
    else:
        # 通过列表的索引值获取对应的环境名称
        env_name = env_namelist[int(inp) - 1]
        # 激活环境，然后进入命令行
        if os.name == "nt":
            os.system("cls")
            conda_hook_path = os.path.join(CONDA_HOME, "shell", "condabin", "conda-hook.ps1")
            command = f"%windir%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -ExecutionPolicy ByPass -NoExit -Command \"& '{conda_hook_path}' ; conda activate '{env_name}' \""
            os.system(command=command)
        else:
            os.system("clear")
            LINUX_ACTIVATION_CMD = get_linux_activation_cmd(CONDA_HOME, IS_MAMBA)
            cmd_str = (
                LINUX_ACTIVATION_CMD.replace("$", "\\$").replace('"', '\\"')
                + f" && conda activate {env_name}"
            )
            command = rf"""bash -c 'bash --init-file <(echo ". $HOME/.bashrc; {cmd_str}")' """
            os.system(command=command)
    return res


def main(workdir):
    global CONDA_HOME, IS_MAMBA
    if CONDA_HOME == "error":
        if os.name == "nt":
            print("请输入conda/mamba发行版的安装路径,如C:\\Users\\USER_NAME\\anaconda3: ")
        else:
            print("请输入conda/mamba发行版的安装路径,如/home/USER_NAME/anaconda3: ")
        conda_prefix = input_with_arrows(">>> ")
        if os.path.isdir(conda_prefix) and os.path.exists(os.path.join(conda_prefix, "conda-meta")):
            CONDA_HOME = conda_prefix
            IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = detect_conda_mamba_infos(
                CONDA_HOME
            )
        else:
            sys.exit(1)

    os.chdir(workdir)
    allow_input, env_infolist_dict, env_num = get_all_env()
    inp = show_info_and_get_input(allow_input, env_num)
    while do_correct_action(inp, env_infolist_dict, env_num):
        print()
        allow_input, env_infolist_dict, env_num = get_all_env()
        inp = show_info_and_get_input(allow_input, env_num)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="conda/mamba发行版环境管理工具")
    parser.add_argument(
        "-d",
        "-D",
        "--workdir",
        type=str,
        required=False,
        help="打开的路径，默认为当前路径",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-p",
        "--prefix",
        type=str,
        metavar="CONDA_HOME",
        required=False,
        help="conda/mamba发行版的安装路径,如C:\\Users\\USER_NAME\\miniforge3,/home/USER_NAME/miniconda3",
    )
    group.add_argument(
        "-n",
        "-N",
        "--distribution-name",
        type=str,
        required=False,
        help="发行版的名称,支持miniforge3,anaconda3,miniconda3,mambaforge,miniforge-pypy3,mambaforge-pypy3,默认顺序如前",
    )
    parser.add_argument(
        "--detect-distribution",
        action="store_true",
        help="探测并列出计算机中所有受支持的conda/mamba发行版",
    )
    args = parser.parse_args()
    if args.detect_distribution:
        print("计算机中所有受支持的conda/mamba发行版如下:")
        available_conda_home_raw = get_conda_home(detect_mode=True)
        available_conda_home = list(set(available_conda_home_raw))
        available_conda_home.sort(key=available_conda_home_raw.index)
        table = PrettyTable()
        table.field_names = [
            "No.",
            "Distribution Name",
            "",
            "Distribution Path",
            "conda",
            "mamba",
            "conda-libmamba-solver",
        ]
        for i in range(len(available_conda_home)):
            table.add_row(
                [
                    i + 1,
                    os.path.split(available_conda_home[i])[1],
                    "*" if i == 0 else "",
                    available_conda_home[i],
                    (
                        ColorStr.LIGHT_GREEN(detect_conda_mamba_infos(available_conda_home[i])[-1])
                        if detect_conda_mamba_infos(available_conda_home[i])[-1]
                        else ColorStr.LIGHT_RED("NO")
                    ),
                    (
                        ColorStr.LIGHT_GREEN(detect_conda_mamba_infos(available_conda_home[i])[1])
                        if detect_conda_mamba_infos(available_conda_home[i])[1]
                        else ColorStr.LIGHT_RED("NOT supported".upper())
                    ),
                    (
                        ColorStr.LIGHT_GREEN(detect_conda_mamba_infos(available_conda_home[i])[2])
                        if detect_conda_mamba_infos(available_conda_home[i])[2]
                        else "-"
                    ),
                ]
            )
        table.align = "l"
        table.border = False
        # table.padding_width = 2
        print(table)
        sys.exit(0)
    if args.prefix is not None:
        if os.path.isdir(args.prefix) and os.path.exists(os.path.join(args.prefix, "conda-meta")):
            CONDA_HOME = args.prefix
            IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = detect_conda_mamba_infos(
                CONDA_HOME
            )
        else:
            print(ColorStr.YELLOW(f'未在指定路径"{args.prefix}"检测到对应发行版，将使用默认发行版'))

    elif args.distribution_name is not None:
        CONDA_HOME, IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = (
            detect_conda_installation(args.distribution_name)
        )
        if os.path.split(CONDA_HOME)[1] != args.distribution_name:
            print(ColorStr.YELLOW(f"未检测到指定的发行版({args.distribution_name})，将使用默认发行版"))
    workdir = args.workdir if args.workdir is not None else USER_HOME
    if os.path.isdir(workdir):
        main(workdir)
    else:
        raise ValueError("传入的参数不是一个目录！")
