"""This code is authored by azhan."""

import argparse
import os
import asyncio
import subprocess
import re
import sys
import json
import time
from packaging.version import Version
from glob import glob
from shutil import rmtree
from threading import Event, Lock, Thread
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable, Literal, TypedDict, Union
from prettytable import PrettyTable
from ColorStr import *
from MyTools import *

if os.name == "posix":
    import readline  # 使Linux下的input()函数支持上下左右键
elif os.name == "nt":
    import win32api
    import win32com.client

USER_HOME = os.path.expanduser("~")

PROGRAM_NAME = "Conda-Environment-Manager"
PROGRAM_VERSION = "1.8.6"

# ***** Global User Settings *****
# <提示> 这些全局设置以CFG_开头，用于控制程序的默认行为，且在程序运行时*不可*更改。
# [设置 1] 控制[S]搜索功能在这期间内使用缓存搜索，而不重新联网下载索引（单位：分钟）。
CFG_SEARCH_CACHE_EXPIRE_MINUTES = 60
# [设置 2] 如果上次重新统计环境大小的耗时超过此设定，则下次需要手动按[D]以重新统计环境大小（单位：秒）。
CFG_MAX_ENV_SIZE_CALC_SECONDS = 3
# [设置 3] 控制 DISPLAY_MODE (int) 的初始值: 主界面环境表格显示模式，主界面按[Tab]键可切换，可以是以下值之一：
#   1: 显示环境的 最后更新时间 和 磁盘实际使用量。
#   2: 显示环境的 安装时间 和 磁盘总大小。
#   3: 同时显示 最后更新时间 和 安装时间，以及 磁盘实际使用量 和 总大小。
CFG_DEFAULT_DISPLAY_MODE = 1  # 默认值；
# [设置 4] 控制需要清空屏幕时，是否强制使用硬清屏（即清除整个终端，而不是只清除当前屏幕内的内容）
CFG_FULL_TERMINAL_CLEAR = True
# [设置 5] 在[+]安装环境功能时，输入快捷命令“--+”时所代表的Conda包合集（如果有ipykernel，则会自动注册到用户Jupyter）。
CFG_CMD_TRIGGERED_PKGS: str = "matplotlib scikit-learn numba pandas ipykernel"
# [设置 6] 在[S]搜索功能时，默认启用的 Channel 源，即 Conda 包的搜索范围
CFG_DEFAULT_SEARCH_CHANNELS: str = "pytorch nvidia intel conda-forge defaults"


allowed_release_names = [
    "CONDA_PREFIX",
    "miniforge3",
    "anaconda3",
    "miniconda3",
    "mambaforge",
    "miniforge-pypy3",
    "mambaforge-pypy3",
]
illegal_env_namelist = ["base", "root", "conda", "mamba", "envs", ""]
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


def filter_and_sort_sources_by_priority(
    sources: Iterable[str], keep_url=False, enable_default_src=True
) -> list[str]:
    """过滤并按优先级排序源。

    Args:
        keep_url (bool): 是否保留URL格式的源，默认为False。
        enable_default_src (bool): 是否启用默认源("conda-forge", "defaults")，默认为True。
    """
    # Step 1
    unique_src_set = set()
    for source in sources:
        if (not keep_url) and "/" in source:
            unique_src_set.add(
                source.rsplit("/", 1)[1]
                if source.rsplit("/", 1)[1] in source_priority_table or source.rsplit("/", 1)[1] in sources
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


class ProgramDataManager:
    """负责加载、存储和更新程序在用户计算机上存储的数据文件的类。

    Attributes:
        localappdata_home (str): 本地应用数据的目录路径，取决于操作系统。
        program_data_home (str): 程序数据的主目录路径。
        data_file (str): 数据文件的路径。
    """

    if os.name == "nt":
        localappdata_home = os.environ.get("LOCALAPPDATA", os.path.join(USER_HOME, "AppData", "Local"))
    else:  # os.name == "posix":
        localappdata_home = os.environ.get("XDG_DATA_HOME", os.path.join(USER_HOME, ".local", "share"))
    if os.path.exists(localappdata_home):
        program_data_home = os.path.join(localappdata_home, PROGRAM_NAME)
    else:
        program_data_home = os.path.join(USER_HOME, "." + PROGRAM_NAME.lower())
    data_file = os.path.join(program_data_home, "data.json")

    def __init__(self):
        self._all_data = self._load_data()
        self.env_info_data = self._all_data.get(CONDA_HOME, {})

    def _load_data(self):
        """私有方法，从数据文件加载数据。

        Returns:
            dict: 数据文件中的所有数据。如果文件不存在或无法解析，则返回空字典。
        """
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            os.remove(self.data_file)
            return {}
        except:
            return {}

    def _write_data(self):
        """私有方法，将当前数据写入数据文件。

        如果数据目录不存在，则创建该目录。
        """
        self._all_data[CONDA_HOME] = self.env_info_data
        if not os.path.exists(self.program_data_home):
            os.mkdir(self.program_data_home)
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self._all_data, f)

    def get_data(self, key: str) -> dict[str, Any]:
        """根据给定的键返回对应的数据字典。

        Args:
            key (str): 数据键，形如*_data，描述一个数据的字典。

        Returns:
            dict: 对应键的数据字典。如果键不存在，则返回空字典。
        """
        return self.env_info_data.get(key, {})

    def update_data(self, key: str, value: dict[str, Any]):
        """更新指定键的数据并写入文件。

        Args:
            key (str): 数据键，形如*_data，描述一个数据的字典。
            value (dict): 更新的单个数据字典。
        """
        self.env_info_data[key] = value
        self._write_data()


def is_legal_envname(env_name: str, env_namelist: Iterable[str]) -> bool:
    """检查环境名是否合法。"""
    return (
        len_to_print(env_name) > 0
        and env_name not in env_namelist
        and env_name not in illegal_env_namelist
        and "/" not in env_name
        and ":" not in env_name
        and " " not in env_name
        and "#" not in env_name
    )


def is_valid_env(env_path: str) -> bool:
    """检查环境目录env_path所存储的环境是否有效。"""
    meta_history_path = os.path.join(env_path, "conda-meta", "history")
    return os.path.isfile(meta_history_path)


def replace_user_path(path: str):
    """将用户的主目录路径替换为'~'，以提高可读性。"""
    return f"~{path[len(USER_HOME):]}" if path.startswith(USER_HOME) else path


def get_valid_input(prompt: str, condition_func, error_msg_func=None, max_errors=5):
    """获取有效输入，并处理输入错误。

    Args:
        prompt (str): 输入提示信息。
        condition_func (function): 判断输入是否有效的函数。
        error_msg_func (function): 显示输入错误提示信息的函数，其应当仅接受一个str参数，即用户输入的值。
        max_errors (int): 允许的最大错误次数，默认为5。

    Returns:
        str: 用户输入的值。
    """
    error_count = 0
    if error_msg_func is None:
        error_msg_func = lambda input_str: f"输入错误 {LIGHT_RED(error_count)} 次，请重新输入："
    inp = input_strip(prompt)
    while not condition_func(inp):
        error_count += 1
        if error_count == 1:
            clear_lines_above(get_printed_line_count(prompt))
        else:
            clear_lines_above(get_printed_line_count(prompt + "\n" + error_msg_func(inp)))
        if error_count > max_errors:
            print(prompt + LIGHT_RED(f"输入错误达到最大次数 ({max_errors})，程序退出。"))
            raise KeyboardInterrupt  # 重启重新主循环
        print(error_msg_func(inp))
        inp = input_strip(prompt)
    if error_count > 0:
        clear_lines_above(get_printed_line_count(prompt + "\n" + error_msg_func(inp)))
        print(prompt + inp)
    return inp


def get_pyvers_from_paths(pypathlist: Iterable[str]) -> list[str | None]:
    """通过 Python 路径列表获取 Python 版本号列表，并支持异步并行获取。

    Args:
        paths (list[str]): Python 路径列表。

    Returns:
        list[str | None]: 获取到的 Python 版本号列表，如果路径无效则为 None。
    """
    sem = asyncio.Semaphore(5)
    if os.name == "nt":

        def get_file_version(file_path: str):
            try:
                info = win32api.GetFileVersionInfo(file_path, "\\")
                file_version = ".".join(  # 提取版本号
                    map(str, divmod(info["FileVersionMS"], 65536) + divmod(info["FileVersionLS"], 65536)),
                )
                return file_version
            except:
                return ""

    async def get_pyver(pypath: str):
        if not os.path.exists(pypath):
            return None
        if os.name == "nt" and (match := re.match(r"(\d\.\d{1,2}\.\d{1,2})150\.1013", get_file_version(pypath))):
            return match.group(1)
        if os.name == "nt":
            probable_env_path = os.path.dirname(pypath)
        else:  # os.name == "posix":
            probable_env_path = os.path.dirname(os.path.dirname(pypath))
        if os.path.exists(conda_meta_path := os.path.join(probable_env_path, "conda-meta")):
            if glob_res := glob(os.path.join(conda_meta_path, "python-*.json")):
                for res in glob_res:
                    if match := re.search(r"python-(\d\.\d{1,2}\.\d{1,2})", res):
                        return match[1]
        async with sem:
            try:
                proc = await asyncio.create_subprocess_exec(
                    pypath,
                    "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()
                return stdout.decode().split()[1]
            except:
                return None

    async def main():
        tasks = [get_pyver(pypath) for pypath in pypathlist]
        return await asyncio.gather(*tasks)

    return asyncio.run(main())


def get_conda_homes(detect_mode=False) -> list[str]:
    """获取受支持的 conda 发行版的安装路径去重列表。

    Note:
        1. 默认仅返回第 1 个找到的项，若 detect_mode 为 True 则返回所有找到的项。

    Args:
        detect_mode (bool): 是否返回所有找到的项，默认为 False。
    """
    conda_homes = []
    if os.name == "nt":
        progradata_path = os.environ["ProgramData"]  # 获取ProgramData路径
        for release_name in allowed_release_names:
            if release_name == "CONDA_PREFIX" and "CONDA_PREFIX" in os.environ:
                conda_homes.append(os.environ["CONDA_PREFIX"])
                if not detect_mode:
                    break
            elif is_valid_env(os.path.join(USER_HOME, release_name)):
                conda_homes.append(os.path.join(USER_HOME, release_name))
                if not detect_mode:
                    break
            elif is_valid_env(os.path.join(progradata_path, release_name)):
                conda_homes.append(os.path.join(progradata_path, release_name))
                if not detect_mode:
                    break
        else:

            def get_shortcut_arguments(shortcut_path: str):
                try:
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shortcut = shell.CreateShortCut(shortcut_path)
                    arguments = shortcut.Arguments
                    return arguments
                except Exception as e:
                    print(LIGHT_RED("[错误] 无法读取快捷方式文件："), e)
                    return None

            is_find = False
            for i in os.listdir(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"):
                if is_find and not detect_mode:
                    break
                path = os.path.join(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs", i)

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
                                        conda_homes.append(arguments.split()[-1])
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
                                            conda_homes.append(arguments.split()[-1])
                                            is_find = True
                                            if not detect_mode:
                                                break
                                if is_find and not detect_mode:
                                    break
    else:
        for release_name in allowed_release_names:
            if release_name == "CONDA_PREFIX" and "CONDA_PREFIX" in os.environ:
                conda_homes.append(os.environ["CONDA_PREFIX"])
                if not detect_mode:
                    break
            elif is_valid_env(os.path.join(USER_HOME, release_name)):
                conda_homes.append(os.path.join(USER_HOME, release_name))
                if not detect_mode:
                    break
            elif is_valid_env(os.path.join("root", release_name)):
                conda_homes.append(os.path.join("root", release_name))
                if not detect_mode:
                    break

    if len(conda_homes) > 1:
        conda_homes_raw = conda_homes.copy()
        conda_homes = list(set(conda_homes_raw))
        conda_homes.sort(key=conda_homes_raw.index)

    for i, conda_home in enumerate(conda_homes):  # realpath 获取路径的真实大小写
        conda_homes[i] = os.path.realpath(conda_home)

    return conda_homes


def detect_conda_mamba_infos(conda_home: str):
    """检测 Conda 环境中是否安装了 Mamba 及其相关版本信息。

    Returns:
        tuple: 包含以下信息的元组：
            1. conda_exe_path (str): Conda 的可执行文件路径。
            2. is_mamba (bool): 是否安装了 Mamba。
            3. mamba_version (str | None): Mamba 的版本号，如果未安装则为 None。
            4. libmamba_solver_version (str | None): conda-libmamba-solver 的版本号，如果未安装则为 None。
            5. conda_version (str | None): Conda 的版本号，如果未安装则为 None。
    """
    conda_exe_path = (
        os.path.join(conda_home, "Scripts", "conda.exe")
        if os.name == "nt"
        else os.path.join(conda_home, "bin", "conda")
    )
    is_mamba = (
        os.path.exists(os.path.join(conda_home, "Scripts", "mamba.exe"))
        if os.name == "nt"
        else os.path.exists(os.path.join(conda_home, "bin", "mamba"))
    )
    mamba_version = None
    if is_mamba:
        if glob_res := glob(os.path.join(conda_home, "conda-meta", "mamba-*.json")):
            for res in glob_res:
                if match := re.search(r"mamba-(\d+\.\d+(?:\.\d+)?)", res):
                    mamba_version = match[1]
                    break
    libmamba_solver_version = None
    if glob_res := glob(os.path.join(conda_home, "conda-meta", "conda-libmamba-solver-*.json")):
        for res in glob_res:
            if match := re.search(r"conda-libmamba-solver-(\d+\.\d+(?:\.\d+)?)", res):
                libmamba_solver_version = match[1]
                break
    conda_version = None
    if glob_res := glob(os.path.join(conda_home, "conda-meta", "conda-*.json")):
        for res in glob_res:
            if match := re.search(r"conda-(\d+\.\d+(?:\.\d+)?)", res):
                conda_version = match[1]
                break

    return conda_exe_path, is_mamba, mamba_version, libmamba_solver_version, conda_version


def should_show_other_envs(other_envs: list[str]):
    """根据当前的其他环境的列表 other_envs 判断其他环境是否有变化，并返回 Conda 发行版的路径。"""
    is_changed = False
    last_other_envs = data_manager.get_data("other_envs_data").get("other_envs", [])
    is_changed = set(other_envs) != set(last_other_envs)
    if is_changed:
        available_conda_homes = get_conda_homes(detect_mode=True)
        data_manager.update_data("other_envs_data", {"other_envs": other_envs})
    else:
        available_conda_homes = [CONDA_HOME]

    return is_changed, available_conda_homes


def detect_conda_installation(prior_release_name: str = ""):
    """检测 Conda 安装情况，并返回相关信息。

    Args:
        prior_release_name (str, optional): 优先检测的发行版名称，默认为空字符串。

    Returns:
        tuple: 包含以下信息的元组：
            1. conda_home (str): Conda 的安装路径，如果未检测到则为 "error"。
            2. conda_exe_path (str): Conda 的可执行文件路径，若无则为 "error"。
            3. is_mamba (bool): 是否安装了 Mamba。
            4. mamba_version (str | None): Mamba 的版本号，如果未安装则为 None。
            5. libmamba_solver_version (str | None): conda-libmamba-solver 的版本号，如果未安装则为 None。
            6. conda_version (str | None): Conda 的版本号，如果未安装则为 None。
    """
    global allowed_release_names
    if prior_release_name != "" and prior_release_name in allowed_release_names:
        allowed_release_names.insert(0, prior_release_name)

    available_conda_homes = get_conda_homes()
    # 判断是否安装了Conda/Mamba
    if len(available_conda_homes) == 0:
        print(LIGHT_RED("[错误] 未检测到 Conda/Mamba 发行版的安装，请先安装相关发行版后再运行此脚本！"))
        return "error", "error", False, None, None, None
    else:
        conda_home = available_conda_homes[0]

    conda_exe_path, is_mamba, mamba_version, libmamba_solver_version, conda_version = detect_conda_mamba_infos(
        conda_home
    )
    return conda_home, conda_exe_path, is_mamba, mamba_version, libmamba_solver_version, conda_version


# ***** Global Literals & Control Variables *****
CONDA_HOME, CONDA_EXE_PATH, IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = (
    detect_conda_installation()
)
data_manager = ProgramDataManager()
main_display_mode = CFG_DEFAULT_DISPLAY_MODE
env_size_recalc_force_enable = False
env_size_recalc_need_confirm = False
action_status: Literal[0, 1] = 1  # 存储 do_action 函数执行后的状态，0 为退出，1 为继续


def detect_conda_libmamba_solver_enabled() -> bool:
    """通过 .condarc 文件检测是否启用了libmamba求解器"""
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


def get_linux_activation_shell_cmd():
    return f"""
    if [ -f "{os.path.join(CONDA_HOME, 'etc', 'profile.d', 'conda.sh')}" ]; then
        . "{os.path.join(CONDA_HOME, 'etc', 'profile.d', 'conda.sh')}"
    else
        export PATH="{os.path.join(CONDA_HOME, 'bin')}:$PATH"
    fi

    if [ -f "{os.path.join(CONDA_HOME, 'etc', 'profile.d', 'mamba.sh')}" ]; then
        . "{os.path.join(CONDA_HOME, 'etc', 'profile.d', 'mamba.sh')}"
    fi """


def get_cmd(cmdlist: Iterable[str]) -> str:
    """生成适用于当前环境的命令行字符串。"""
    if not IS_MAMBA:
        cmdlist = [i.replace("mamba", "conda", 1) if i.startswith("mamba") else i for i in cmdlist]

    if os.name == "nt":
        cmd = f'"{os.path.join(CONDA_HOME,"Scripts","activate.bat")}"'
        for one_cmd in cmdlist:
            cmd += f" && {one_cmd}"
        if not "".join(cmdlist).isascii():
            output = subprocess.run("chcp", capture_output=True, shell=True, text=True).stdout
            now_codepage = re.search(r"\d+", output).group(0)  # type: ignore
            echo_lines = f"({'&'.join(['echo.']*30)})"  # Only work for Windows Terminal
            cmd = f"{echo_lines} && chcp 65001 && " + cmd + f" && {echo_lines} && chcp {now_codepage}"
    else:
        linux_activation_cmd = get_linux_activation_shell_cmd()
        cmd = linux_activation_cmd + " && conda activate"
        for one_cmd in cmdlist:
            cmd += f" && {one_cmd}"

    return cmd


def _get_envpath_last_modified_time(path: str, pyver: str):
    """获取环境的最后修改时间(conda , pip)，用于判断是否需要重新计算环境大小"""
    conda_meta_path = os.path.join(path, "conda-meta")
    if os.name == "nt":
        site_packages_path = os.path.join(path, "Lib", "site-packages")
    else:  # os.name == "posix":
        site_packages_path = os.path.join(path, "lib", f"python{'.'.join(pyver.split('.')[:2])}", "site-packages")

    path_mtime = os.path.getmtime(path) if os.path.exists(path) else 0
    conda_meta_mtime = os.path.getmtime(conda_meta_path) if os.path.exists(conda_meta_path) else 0
    site_packages_mtime = os.path.getmtime(site_packages_path) if os.path.exists(site_packages_path) else 0

    return max(path_mtime, conda_meta_mtime), site_packages_mtime


def _get_base_env_modified_info():
    """获取 base 环境的(pkgs_item_count, pkgs_mtime)信息，用于判断是否需要重新计算所有环境大小"""
    pkgs_path = os.path.join(CONDA_HOME, "pkgs")
    pkgs_item_count = 0
    pkgs_mtime = 0
    if os.path.exists(pkgs_path):  # 忽略 cache 及 urls.txt 的变化，避免总是重新计算 base 环境大小
        for entry in os.scandir(pkgs_path):
            if entry.name not in ("cache", "urls.txt"):
                pkgs_mtime = max(pkgs_mtime, entry.stat().st_mtime)
                pkgs_item_count += 1
    cache_path = os.path.join(pkgs_path, "cache")
    cache_size = 0
    if os.path.exists(cache_path):
        for entry in os.scandir(cache_path):
            cache_size += entry.stat().st_size

    return pkgs_item_count, pkgs_mtime, cache_size


def get_paths_totalsize_list(pathlist: Iterable[str]) -> list[int]:
    """根据 文件夹路径列表 获取对应的 文件夹大小列表。"""
    sem = asyncio.Semaphore(8)

    async def get_folder_size_with_semaphore(path):
        async with sem:
            return await asyncio.to_thread(get_folder_size, path)

    async def get_sizes_async():
        tasks = [get_folder_size_with_semaphore(path) for path in pathlist]
        return await asyncio.gather(*tasks)

    return asyncio.run(get_sizes_async())


def _get_envsizes_linux(pathlist: list[str]):
    """Linux下获取各环境的磁盘占用情况。

    Returns:
        tuple: 包含以下信息的元组：
            - real_usage_list (list[int]): 环境实际磁盘占用大小列表。
            - total_size_list (list[int]): 环境表观总大小列表。
            - disk_usage (int): Conda 环境总磁盘占用大小。
    """

    class ProgressBar(Thread):
        def __init__(self, calc_cost_time: int):
            super().__init__(daemon=True)
            self.is_running = Event()
            self.calc_cost_time = calc_cost_time
            self.bar_length = 30

        def run(self):
            while True:
                if not self.is_running.is_set():
                    break
                self._show_process()
                time.sleep(0.02)

        def start(self):
            self.last_print_str = ""
            self.start_time = time.time()
            self.is_running.set()  # 设置运行信号
            super().start()

        def stop(self):
            self.is_running.clear()  # 清除运行信号

        def _show_process(self):
            elapsed_time = time.time() - self.start_time

            percentage_str = f"{elapsed_time / self.calc_cost_time :>5.0%}"

            num_blocks = int(elapsed_time / self.calc_cost_time * self.bar_length)
            if num_blocks <= self.bar_length:
                num_dots = self.bar_length - num_blocks - 1
                bar = "[" + "=" * num_blocks + ">" * min(1, num_dots + 1) + "." * num_dots + "]"
            else:
                num_blocks %= self.bar_length
                num_dots = self.bar_length - num_blocks - 1
                bar = "[" + "=" * num_blocks + ">" + "=" * num_dots + "]"

            elapsed_mins, elapsed_secs = map(int, divmod(elapsed_time, 60))
            elapsed_time_str = f"{elapsed_mins:02d}:{elapsed_secs:02d}"

            if elapsed_time < self.calc_cost_time:
                remaining_time = self.calc_cost_time - elapsed_time
                remaining_mins, remaining_secs = map(int, divmod(remaining_time, 60))
                remaining_time_str = f"{remaining_mins:02d}:{remaining_secs:02d}"
            else:
                remaining_time_str = "--:--"

            print_str = f"{percentage_str} {bar} {elapsed_time_str}<{remaining_time_str}"
            if print_str != self.last_print_str:
                self.last_print_str = print_str
                print(print_str, end="\r", flush=True)

    if calc_cost_time := data_manager.get_data("envs_size_data").get("calc_cost_time"):
        progress_bar = ProgressBar(calc_cost_time)
        progress_bar.start()

    disk_usage = 0
    real_usage_list = [0] * len(pathlist)

    dirs = []
    for direntry in os.scandir(CONDA_HOME):
        if direntry.is_dir() and direntry.name != "envs":
            dirs.append(direntry.path)
        elif direntry.is_file():
            disk_usage += direntry.stat().st_size
    dirs.extend([path for path in pathlist if path != CONDA_HOME])

    command = ["du", "-cd", "0", *dirs]
    du_result = subprocess.run(command, capture_output=True, text=True).stdout
    lines = du_result.splitlines()
    disk_usage = int(lines[-1].strip().split("\t")[0]) * 1024

    for line in lines[:-1]:
        size, path = line.strip().split("\t")
        size = int(size) * 1024

        try:
            index = pathlist.index(path)
            real_usage_list[index] = size
        except ValueError:
            pass

    base_index = pathlist.index(CONDA_HOME)
    real_usage_list[base_index] = disk_usage - sum(real_usage_list)

    total_size_list = get_paths_totalsize_list(pathlist[:base_index] + pathlist[base_index + 1 :])
    total_size_list.insert(base_index, real_usage_list[base_index])

    if "progress_bar" in locals():
        progress_bar.stop()

    return real_usage_list, total_size_list, disk_usage


def _get_envsizes_windows(pathlist: list[str]):
    """Windows下获取各环境的磁盘占用情况。

    Returns:
        tuple: 包含以下信息的元组：
            - real_usage_list (list[int]): 环境实际磁盘占用大小列表。
            - total_size_list (list[int]): 环境表观总大小列表。
            - disk_usage (int): Conda 环境总磁盘占用大小。
    """

    class ProgressBar(Thread):
        """进度条线程类，用于Windows下显示计算conda环境磁盘占用大小的进度信息。"""

        def __init__(self, num_files: Union[None, int] = None):
            super().__init__(daemon=True)
            self.is_running = Event()  # 默认处于非运行状态
            self.lock = Lock()
            self.num_files = num_files
            self.bar_length = 10

        def run(self):
            while True:
                if not self.is_running.is_set():
                    break
                self._show_process()
                time.sleep(1)

        def start(self):
            if self.num_files is None:
                self.idx = 0
            self.count = 0
            self.last_count = 0
            self.size = 0
            self.start_time = time.time()
            self.is_running.set()  # 设置运行信号
            super().start()

        def add(self, new_size):
            with self.lock:
                self.count += 1
                self.size += new_size

        def stop(self):
            self.is_running.clear()  # 清除运行信号
            clear_lines_above(1)  # 覆盖 “[提示] 正在计算环境大小及磁盘占用情况” 这条提示信息
            set_terminal_text_style("LIGHT_YELLOW")
            self._show_process(finished=True)
            reset_terminal_text_style()
            print("\n")  # 保证以上信息不被清除，且与正文空一行

        def _show_process(self, finished=False):
            if self.num_files:
                num_blocks = int(self.count / self.num_files * self.bar_length)
                num_blocks = min(self.bar_length, num_blocks)
                num_dots = self.bar_length - num_blocks - 1
                if num_blocks < self.bar_length:
                    bar = (
                        "|" + "#" * num_blocks + str(int(self.count / self.num_files * 10)) + "·" * num_dots + "|"
                    )
                else:
                    bar = "|" + "#" * self.bar_length + "|"
            else:
                bar = "|" + "·" * self.idx + "#" + "·" * (self.bar_length - self.idx - 1) + "|"
                self.idx = (self.idx + 1) % self.bar_length

            size_str = "Apparent Size: " + format_size(self.size)
            num_files_str = "Files: " + f"{self.count:,}"

            # 计算已消耗时间
            elapsed_time = time.time() - self.start_time
            elapsed_mins, elapsed_secs = map(int, divmod(elapsed_time, 60))
            elapsed_time_str = f"{elapsed_mins:02d}:{elapsed_secs:02d}"

            # 计算剩余时间
            if self.num_files and self.count > 0:
                time_per_file = elapsed_time / self.count
                remaining_time = time_per_file * (self.num_files - self.count)
                if remaining_time >= 0:
                    remaining_mins, remaining_secs = map(int, divmod(remaining_time, 60))
                    remaining_time_str = f"{remaining_mins:02d}:{remaining_secs:02d}"
                else:
                    remaining_time_str = "--:--"
            else:
                remaining_time_str = "--:--"

            file_count_speed = self.count - self.last_count
            self.last_count = self.count

            extra_info = f"[{elapsed_time_str}<{remaining_time_str}; {file_count_speed:,} f/s]"

            if not finished:
                print_str = bar + " - " + size_str + " - " + num_files_str + " " + extra_info
                print(f"{print_str:<{fast_get_terminal_size().columns}}", end="\r")
            else:
                print(size_str + " | " + num_files_str + " " + extra_info)

    num_files = 0
    real_usage_list = [0] * len(pathlist)
    total_size_list = [0] * len(pathlist)
    path_corresponding_index = {path: idx for idx, path in enumerate(pathlist)}
    seen_inodes = set()

    lock = Lock()
    cluster_size = get_cluster_size_windows(CONDA_HOME)

    last_num_files = data_manager.get_data("num_files_data").get("num_files")
    progress_bar = ProgressBar(num_files=last_num_files)
    progress_bar.start()

    def get_disk_usage(env_path, root, nondirs):
        nonlocal num_files

        for f in nondirs:
            try:
                stat = os.lstat(root + os.sep + f)
                size = stat.st_size
                inode = stat.st_ino
            except OSError:
                size = 0
                inode = 0

            if size > 500:  # 估算，存在误差，(或者试试 size>382)
                usage = (size + cluster_size - 1) // cluster_size * cluster_size  # 按簇向上对齐
            else:
                usage = 0  # 由于NTFS对过小的文件直接保存在MFT中，不占用簇

            progress_bar.add(new_size=size)

            with lock:
                num_files += 1
                total_size_list[path_corresponding_index[env_path]] += size
                if inode not in seen_inodes:
                    seen_inodes.add(inode)
                    real_usage_list[path_corresponding_index[env_path]] += usage

    with ThreadPoolExecutor(max_workers=8) as executor:
        # 获取base环境的大小
        walker_conda_home = os.walk(CONDA_HOME, followlinks=True)  # followlinks=True为了避免islink()判断，提高速度
        _, dirs_conda_home, nondirs_conda_home = next(walker_conda_home)
        if "envs" in dirs_conda_home:
            dirs_conda_home.remove("envs")
        get_disk_usage(CONDA_HOME, CONDA_HOME, nondirs_conda_home)
        for root, _, nondirs in walker_conda_home:
            executor.submit(get_disk_usage, CONDA_HOME, root, nondirs)

        # 分别获取其他各环境的大小
        for path in pathlist:
            if path != CONDA_HOME:
                for root, _, nondirs in os.walk(path, followlinks=True):
                    executor.submit(get_disk_usage, path, root, nondirs)

    progress_bar.stop()
    data_manager.update_data("num_files_data", {"num_files": num_files})

    disk_usage = sum(real_usage_list)

    return real_usage_list, total_size_list, disk_usage


def get_home_sizes(namelist: list[str], pathlist: list[str], pyverlist: list[str]):
    """获取环境的大小信息。

    Notes:
        1. 此函数是前面两个函数的高级封装版本，应该直接调用本函数。
        2. 因为同一conda包的多次安装只会在pkgs目录下创建一次，其余环境均为硬链接，故实际磁盘占用会远小于表观大小；

    Returns:
        tuple: 包含以下信息的元组：
            - name_sizes_dict (dict): 每个环境的大小信息字典。
                其中每个键值对的键为环境名 env_name，值为一个字典，包含以下键值对(key, value)：
                    - ("real_usage", int): 环境实际磁盘占用大小。
                    - ("total_size", int): 环境表观总大小。
                    - ("conda_mtime", int): conda-meta 目录的最后修改时间。
                    - ("pip_mtime", int): site-packages 目录的最后修改时间。
            - disk_usage (int): 总磁盘使用量。
    """
    envs_size_data = data_manager.get_data("envs_size_data")
    last_env_sizes = envs_size_data.get("env_sizes", {})
    disk_usage = envs_size_data.get("disk_usage", 0)
    calc_cost_time = envs_size_data.get("calc_cost_time", 0)

    name_sizes_dict = {}

    namelist_changed = []
    namelist_deleted = set(last_env_sizes.keys()) - set(namelist)
    pathlist_changed = []
    timestamplist_changed = []
    calc_all = False
    for name, path, pyver in zip(namelist, pathlist, pyverlist):
        c_conda_mtime, c_pip_mtime = _get_envpath_last_modified_time(path, pyver)
        if name not in last_env_sizes or c_conda_mtime != last_env_sizes[name]["conda_mtime"]:
            calc_all = True
            break
        elif c_pip_mtime != last_env_sizes[name]["pip_mtime"]:
            namelist_changed.append(name)
            pathlist_changed.append(path)
            timestamplist_changed.append({"conda_mtime": c_conda_mtime, "pip_mtime": c_pip_mtime})
        else:
            name_sizes_dict[name] = {
                "real_usage": last_env_sizes[name]["real_usage"],
                "total_size": last_env_sizes[name]["total_size"],
                "conda_mtime": c_conda_mtime,
                "pip_mtime": c_pip_mtime,
            }

    c_pkgs_item_count, c_pkgs_mtime, c_cache_size = _get_base_env_modified_info()
    last_base_pkgs_info = data_manager.get_data("base_pkgs_info")
    base_pkgs_info = {"pkgs_item_count": c_pkgs_item_count, "pkgs_mtime": c_pkgs_mtime}
    last_cache_size = last_base_pkgs_info.pop("cache_size", -1)
    if base_pkgs_info != last_base_pkgs_info:
        calc_all = True
    if not calc_all and last_cache_size != -1:
        name_sizes_dict["base"]["real_usage"] += c_cache_size - last_cache_size
        name_sizes_dict["base"]["total_size"] += c_cache_size - last_cache_size
        disk_usage += c_cache_size - last_cache_size
    base_pkgs_info["cache_size"] = c_cache_size
    data_manager.update_data("base_pkgs_info", base_pkgs_info)

    if not namelist_changed and not namelist_deleted and not calc_all:
        return name_sizes_dict, disk_usage

    print(f"{LIGHT_YELLOW('[提示]')} 正在计算环境大小及磁盘占用情况，请稍等...")

    global env_size_recalc_need_confirm, env_size_recalc_force_enable
    if calc_all:
        name_sizes_dict.clear()
        if env_size_recalc_force_enable or calc_cost_time <= CFG_MAX_ENV_SIZE_CALC_SECONDS:
            env_size_recalc_force_enable = False
            env_size_recalc_need_confirm = False
            calc_start_time = time.time()
            if os.name == "posix":
                real_usage_list, total_size_list, disk_usage = _get_envsizes_linux(pathlist)
            else:  # os.name == "nt":
                real_usage_list, total_size_list, disk_usage = _get_envsizes_windows(pathlist)

            for name, real_usage, total_size in zip(namelist, real_usage_list, total_size_list):
                c_conda_mtime, c_pip_mtime = _get_envpath_last_modified_time(
                    pathlist[namelist.index(name)], pyverlist[namelist.index(name)]
                )
                name_sizes_dict[name] = {
                    "real_usage": real_usage,
                    "total_size": total_size,
                    "conda_mtime": c_conda_mtime,
                    "pip_mtime": c_pip_mtime,
                }

            calc_cost_time = time.time() - calc_start_time
        else:  # 未获取磁盘使用量，重置所有环境的大小
            env_size_recalc_need_confirm = True
            disk_usage = 0
            for name in namelist:
                name_sizes_dict[name] = {
                    "real_usage": 0,
                    "total_size": 0,
                    "conda_mtime": 0,
                    "pip_mtime": 0,
                }
    else:  # 此分支仅在删除环境或环境的pip包时执行
        total_size_list = get_paths_totalsize_list(pathlist_changed)

        for idx, name in enumerate(namelist_changed):
            last_total_size = last_env_sizes[name]["total_size"]
            total_size = total_size_list[idx]
            diff_size = total_size - last_total_size
            real_usage = last_env_sizes[name]["real_usage"] + diff_size
            name_sizes_dict[name] = {
                "real_usage": real_usage,
                "total_size": total_size,
                "conda_mtime": timestamplist_changed[idx]["conda_mtime"],
                "pip_mtime": timestamplist_changed[idx]["pip_mtime"],
            }
            disk_usage += diff_size

        for name in namelist_deleted:
            disk_usage -= last_env_sizes[name]["real_usage"]

    envs_size_data = {"env_sizes": name_sizes_dict, "disk_usage": disk_usage, "calc_cost_time": calc_cost_time}
    data_manager.update_data("envs_size_data", envs_size_data)

    clear_lines_above(1)

    return name_sizes_dict, disk_usage


def _get_env_last_updated_date(env_path: str, pyver: str) -> str:
    """通过检查 conda 及 pip 的安装行为，获取环境的最后更新日期。

    Returns:
        str: 格式化的日期字符串 "%Y-%m-%d" 或 "Unknown"

    Note:
        用于 env_lastmodified_timelist
    """
    meta_history_path = os.path.join(env_path, "conda-meta", "history")
    if os.name == "nt":
        site_packages_path = os.path.join(env_path, "Lib", "site-packages")
    else:  # os.name == "posix":
        site_packages_path = os.path.join(
            env_path, "lib", f"python{'.'.join(pyver.split('.')[:2])}", "site-packages"
        )
    t1 = os.path.getmtime(meta_history_path) if os.path.exists(meta_history_path) else 0
    t2 = os.path.getmtime(site_packages_path) if os.path.exists(site_packages_path) else 0

    if max(t1, t2) == 0:
        return "Unknown"
    return time.strftime("%Y-%m-%d", time.localtime(max(t1, t2)))


def _get_env_installation_date(env_path: str) -> str:
    """获取环境的安装日期。

    Returns:
        str: 格式化的日期字符串 "%Y-%m-%d" 或 "Unknown"
    """
    meta_history_path = os.path.join(env_path, "conda-meta", "history")
    if os.path.exists(meta_history_path):
        with open(meta_history_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("==>"):
                    if match := re.search(r"\d{4}-\d{2}-\d{2}", line):
                        return match.group(0)
    return "Unknown"


def _get_env_basic_infos():
    """获取环境的基本信息。

    Returns:
        env_namelist: list[str], 环境名列表
        env_pathlist: list[str], 环境路径列表
        env_validity_list: list[bool], 环境是否有效的布尔值列表
        others_env_pathlist: list[str], 其他不受支持的环境路径列表

    Notes:
        1. 若 .condarc 文件定义了 envs_dirs: ，则可能会引入不属于 CONDA_HOME/envs 下但同样受支持的环境；
        2. 失效的环境为 CONDA_HOME/envs 和 .condarc 文件定义的 envs_dirs (但必须以 envs 结尾) 中的
           不包含 conda-meta/history 的目录；
        3. env_...list 的内容组成：CONDA_HOME/envs 下的环境 + (可能的)其它受支持的环境 + (可能的)已经失效的环境；
    """
    env_namelist = []
    env_pathlist = []
    env_namelist_users = []
    env_pathlist_users = []
    others_env_pathlist = []
    invalid_env_names = []
    invalid_env_paths = []

    conda_env_homes = []
    if os.path.exists(os.path.join(CONDA_HOME, "envs")):
        conda_env_homes.append(os.path.join(CONDA_HOME, "envs"))

    env_output = subprocess.check_output([CONDA_EXE_PATH, "env", "list"], text=True)
    env_list_lines = env_output.splitlines()[2:]

    for line in env_list_lines:
        items = line.split()
        if len(items) == 0:
            continue
        elif len(items) == 1:
            others_env_pathlist.append(items[0])
        else:
            if items[0] != "*":
                if items[-1].startswith(CONDA_HOME):
                    env_namelist.append(items[0])
                    env_pathlist.append(items[-1])
                else:  # 不独属于当前发行版的envs，位于公共区域，但仍能够受此发行版的正常管辖
                    env_namelist_users.append(items[0])
                    env_pathlist_users.append(items[-1])
            else:
                others_env_pathlist.append(items[-1])

    conda_env_homes.extend(
        ordered_unique(
            [dirpath for path in env_pathlist_users if (dirpath := os.path.dirname(path)).endswith("envs")]
        )
    )
    for env_home in conda_env_homes:
        with os.scandir(env_home) as entries:
            for entry in entries:
                if entry.is_dir() and not is_valid_env(entry.path):
                    invalid_env_names.append(entry.name)
                    invalid_env_paths.append(entry.path)

    env_namelist = env_namelist + env_namelist_users + invalid_env_names
    env_pathlist = env_pathlist + env_pathlist_users + invalid_env_paths

    env_validity_list = [env_path not in invalid_env_paths for env_path in env_pathlist]

    return env_namelist, env_pathlist, env_validity_list, others_env_pathlist


class EnvInfosDict(TypedDict):
    env_num: int
    valid_env_num: int
    disk_usage: int
    total_apparent_size: int
    env_namelist: list[str]
    env_pathlist: list[str]
    env_lastmodified_timelist: list[str]
    env_installation_time_list: list[str]
    env_pyverlist: list[str]
    env_realusage_list: list[int]
    env_totalsize_list: list[int]
    others_env_pathlist: list[str]
    env_validity_list: list[bool]


def get_env_infos() -> EnvInfosDict:
    """获取 Conda 环境的所有基本信息组成的字典类 EnvInfosDict。

    Attention:
        * * * * * 注意 * * * * *
        此函数是整个脚本的三个主函数其一，负责主循环中 “获取环境信息” 功能。
    """
    env_namelist, env_pathlist, env_validity_list, others_env_pathlist = _get_env_basic_infos()
    env_num = len(env_namelist)
    valid_env_num = sum(env_validity_list)
    # 获取所有环境的Python版本并存入env_pyverlist
    _env_pypathlist = [
        os.path.join(i, "python.exe") if os.name == "nt" else os.path.join(i, "bin", "python")
        for i in env_pathlist
    ]
    env_pyverlist = [i if i else "-" for i in get_pyvers_from_paths(_env_pypathlist)]
    env_lastmodified_timelist = [
        _get_env_last_updated_date(path, pyver) for path, pyver in zip(env_pathlist, env_pyverlist)
    ]
    env_installation_time_list = [_get_env_installation_date(path) for path in env_pathlist]

    name_sizes_dict, disk_usage = get_home_sizes(env_namelist, env_pathlist, env_pyverlist)
    env_realusage_list = [name_sizes_dict[i]["real_usage"] for i in env_namelist]
    env_totalsize_list = [name_sizes_dict[i]["total_size"] for i in env_namelist]
    total_apparent_size = sum(env_totalsize_list)

    env_infos_dict: EnvInfosDict = {
        "env_num": env_num,  # int
        "valid_env_num": valid_env_num,  # int
        "disk_usage": disk_usage,  # int
        "total_apparent_size": total_apparent_size,  # int
        "env_namelist": env_namelist,  # list[str]
        "env_pathlist": env_pathlist,  # list[str]
        "env_lastmodified_timelist": env_lastmodified_timelist,  # list[str]
        "env_installation_time_list": env_installation_time_list,  # list[str]
        "env_pyverlist": env_pyverlist,  # list[str]
        "env_realusage_list": env_realusage_list,  # list[int]
        "env_totalsize_list": env_totalsize_list,  # list[int]
        "others_env_pathlist": others_env_pathlist,  # list[str]
        "env_validity_list": env_validity_list,  # list[bool]
    }

    return env_infos_dict


def get_envs_prettytable(env_infos_dict: EnvInfosDict) -> PrettyTable:
    """获取环境信息的 PrettyTable 表格对象。

    Args:
        env_infos_dict (dict): 环境信息字典。
    """
    env_num = env_infos_dict["env_num"]
    valid_env_num = env_infos_dict["valid_env_num"]
    disk_usage = env_infos_dict["disk_usage"]
    total_apparent_size = env_infos_dict["total_apparent_size"]
    env_namelist = env_infos_dict["env_namelist"]
    env_lastmodified_timelist = env_infos_dict["env_lastmodified_timelist"]
    env_installation_time_list = env_infos_dict["env_installation_time_list"]
    env_pyverlist = env_infos_dict["env_pyverlist"]
    env_realusage_list = env_infos_dict["env_realusage_list"]
    env_totalsize_list = env_infos_dict["env_totalsize_list"]

    _max_name_length = max((len_to_print(i) for i in env_namelist), default=0)
    _max_name_length = max(_max_name_length, len("Env Name") + 7)  # 让length过短时也能正常显示

    table = PrettyTable()
    fieldstr_Number = "No."
    fieldstr_EnvName = (
        "Env Name" + " " * (_max_name_length + 11 - (len("Env Name" + "(Python Version)"))) + "(Python Version)"
    )
    if main_display_mode == 1:
        fieldstr_LastUpdated_Installation = "Last Updated"
    elif main_display_mode == 2:
        fieldstr_LastUpdated_Installation = "Installation"
    else:
        fieldstr_LastUpdated_Installation = "Last Updated/Installation"

    fieldstr_Usage = ("+Usage" if main_display_mode == 3 else "+  Usage") + " " * 2 + "(%)"
    fieldstr_Size = "Size" + " " * 2 + "(%)"

    field_names = [
        fieldstr_Number,
        fieldstr_EnvName,
        fieldstr_LastUpdated_Installation,
    ]
    if main_display_mode == 1:
        field_names.append(fieldstr_Usage)
    elif main_display_mode == 2:
        field_names.append(fieldstr_Size)
    else:
        field_names.extend([fieldstr_Usage, fieldstr_Size])

    table.field_names = field_names
    table.align = "l"
    table.align[fieldstr_LastUpdated_Installation] = "c"  # type: ignore
    if fieldstr_Usage in table.field_names:
        table.align[fieldstr_Usage] = "r"  # type: ignore
    if fieldstr_Size in table.field_names:
        table.align[fieldstr_Size] = "r"  # type: ignore
    table.border = False
    table.padding_width = 1
    # table.hrules = HEADER

    def _format_pyver(pyver: str):
        try:
            major, minor, patch = pyver.split(".")
            return f"{major}.{minor:>2}.{patch:>2}"
        except:
            return pyver

    def _format_size_info(size: int, total_size: int):
        if main_display_mode == 3:
            return (
                f"{format_size(size,sig_digits=2,B_suffix=False):>5} ({size/total_size*100:>2.0f})"
                if size > 0
                else f"{'-':^10}"
            )
        else:
            return (
                f"{format_size(size,B_suffix=False):>6} ({size/total_size*100:>2.0f})"
                if size > 0
                else f"{'-':^11}"
            )

    for i in range(env_num):
        boundarys = ["", ""] if valid_env_num > 9 else ["[", "]"]
        row = [
            f"{boundarys[0]}{str(i + 1)}{boundarys[1]}",
            env_namelist[i]
            + " " * (_max_name_length - len_to_print(env_namelist[i]) + 2)
            + f"({_format_pyver(env_pyverlist[i]):^7s})",
        ]
        if main_display_mode == 1:
            row.extend(
                [
                    f"{env_lastmodified_timelist[i]}",
                    "+ " + _format_size_info(env_realusage_list[i], disk_usage),
                ]
            )
        elif main_display_mode == 2:
            row.extend(
                [
                    f"{env_installation_time_list[i]}",
                    _format_size_info(env_totalsize_list[i], total_apparent_size),
                ]
            )
        else:
            row.extend(
                [
                    f"{env_lastmodified_timelist[i]:^10} / {env_installation_time_list[i]:^10}",
                    "+" + _format_size_info(env_realusage_list[i], disk_usage),
                    _format_size_info(env_totalsize_list[i], total_apparent_size),
                ]
            )
        table.add_row(row)

    return table


def _print_header(table_rstrip_width: int, env_infos_dict: EnvInfosDict):
    """打印主界面的标题信息。"""

    def _get_header_str():
        header_str = " ("
        if IS_MAMBA:
            header_str += "mamba "
            if MAMBA_VERSION:
                header_str += f"{LIGHT_GREEN(MAMBA_VERSION)}"
            else:
                header_str += LIGHT_GREEN("supported".upper())
            header_str += ", "
        header_str += "conda "
        if CONDA_VERSION and Version(CONDA_VERSION) >= Version("23.10"):
            header_str += f'{LIGHT_GREEN(f"{CONDA_VERSION}")}'
        elif CONDA_VERSION and Version(CONDA_VERSION) >= Version("22.12"):
            header_str += f'{LIGHT_YELLOW(f"{CONDA_VERSION}")}'
        elif CONDA_VERSION:
            header_str += f'{YELLOW(f"{CONDA_VERSION}")}'
        else:
            header_str += LIGHT_RED("NO")
        if not IS_MAMBA:
            header_str += ", lib-mamba "
            if LIBMAMBA_SOLVER_VERSION and Version(LIBMAMBA_SOLVER_VERSION) >= Version("23.9"):
                header_str += f'{LIGHT_GREEN(f"{LIBMAMBA_SOLVER_VERSION}")}'
            elif LIBMAMBA_SOLVER_VERSION:
                header_str += f'{YELLOW(f"{LIBMAMBA_SOLVER_VERSION}")}'
            else:
                header_str += LIGHT_RED("NO")
            if LIBMAMBA_SOLVER_VERSION:
                header_str += " "
                if detect_conda_libmamba_solver_enabled():
                    header_str += LIGHT_GREEN("Used")
                else:
                    header_str += LIGHT_RED("Not Used")
                header_str += ""
        header_str += ")"
        return header_str

    print_str = "# " + BOLD(os.path.split(CONDA_HOME)[1].capitalize()) + _get_header_str()
    print_sizeinfo = (
        BOLD(f"[Apparent Size: {format_size(env_infos_dict['total_apparent_size'])}]")
        if main_display_mode == 2
        else BOLD(f"[Disk Usage: {format_size(env_infos_dict['disk_usage'])}]")
    )
    print(
        print_str
        + " " * (table_rstrip_width - len_to_print(print_str) - len_to_print(print_sizeinfo))
        + print_sizeinfo
    )


def _print_envs_table(table: PrettyTable, env_infos_dict: EnvInfosDict):
    """打印环境表格。"""

    def colorstr_interval(s, i):
        return LIGHT_YELLOW(s) if i % 2 == 0 else LIGHT_CYAN(s)

    table_width = get_prettytable_width(table)
    env_pathlist = env_infos_dict["env_pathlist"]
    env_validity_list = env_infos_dict["env_validity_list"]

    last_envpath_prefix = ""
    passed_first_invalid_env = False
    for i, line in enumerate(table.get_string().splitlines()):
        if i == 0:
            print(BOLD(line))
            continue

        if not env_validity_list[i - 1] and not passed_first_invalid_env:
            print(LIGHT_RED((DIM(f"{' * Invalid * ':-^{table_width}}"))))
            passed_first_invalid_env = True
        if not env_pathlist[i - 1].startswith(CONDA_HOME) and not passed_first_invalid_env:
            envpath_prefix = os.path.split(env_pathlist[i - 1])[0]
            if envpath_prefix != last_envpath_prefix:
                last_envpath_prefix = envpath_prefix
                prompt_str = f" {replace_user_path(envpath_prefix)} "
                print(DIM(f"{prompt_str:-^{table_width}}"))

        if env_validity_list[i - 1]:
            print(colorstr_interval(line, i))
        else:
            print(LIGHT_RED(line))


def _print_other_envs(others_env_pathlist: list[str]):
    """可能地打印其他不受支持的环境。"""
    show_others, available_conda_homes = should_show_other_envs(others_env_pathlist)
    if show_others:
        print(LIGHT_YELLOW("*" * 10), end="")
        print(LIGHT_YELLOW(f" 目前管理的 Conda 发行版是 {CONDA_HOME} "), end="")
        print(LIGHT_YELLOW("*" * 10))
        if len(available_conda_homes) > 1:
            print(YELLOW("[提示] 检测到多个发行版安装："))
            for i, condapath in enumerate(available_conda_homes, 1):
                if condapath == CONDA_HOME:
                    print(LIGHT_GREEN(f"[{i}]\t{os.path.split(condapath)[1]}\t{condapath} (当前)"))
                else:
                    print(f"[{i}]\t{os.path.split(condapath)[1]}\t{condapath}")
        if others_env_pathlist:
            print(YELLOW("[提示] 检测到如下其它发行版的环境，或未安装在规范目录下的环境，将不会被显示与管理："))
            for i, path in enumerate(others_env_pathlist, 1):
                for condapath in available_conda_homes:
                    if path.startswith(condapath):
                        print(f"[{i}]\t{os.path.split(condapath)[1]}\t{path}")
                        break
                else:
                    print(f"[{i}]\t         \t{path}")
        print(LIGHT_YELLOW(f"{' 以上信息仅在不受支持的环境有变化时显示 ':*^55}"))
        print()


def _get_main_prompt_str(valid_env_num: int) -> str:
    """打印主界面的用户输入提示。"""

    main_prompt_str = f"""
允许的操作指令如下 (按{BOLD(YELLOW("[Q]"))}以退出, 按{BOLD("[Tab]")}切换当前显示模式 {BOLD(LIGHT_CYAN(main_display_mode))}):"""

    boundarys = ["<", ">"] if valid_env_num > 9 else ["[", "]"]
    _s = "输入" if valid_env_num > 9 else "请按"
    main_prompt_str += f"""
  - 激活环境对应命令行{_s}编号{boundarys[0]}{BOLD(LIGHT_YELLOW(f"1-{valid_env_num}"))}{boundarys[1]};浏览环境主目录输入<{BOLD(LIGHT_GREEN("@编号"))}>;"""

    main_prompt_str += f"""
  - 删除环境按{BOLD(RED("[-]"))};新建环境按{BOLD(LIGHT_GREEN("[+]"))};重命名环境按{BOLD(LIGHT_BLUE("[R]"))};复制环境按{BOLD(LIGHT_CYAN("[P]"))};
  - 显示并回退至环境的历史版本按{BOLD(LIGHT_MAGENTA("[V]"))};
  - 更新环境的所有 Conda 包按{BOLD(GREEN("[U]"))};
  - 查看及清空 Conda/pip 缓存按{BOLD(LIGHT_RED("[C]"))};
  - 注册 Jupyter 内核按{BOLD(CYAN("[I]"))};显示、管理及清理 Jupyter 内核按{BOLD(LIGHT_BLUE("[J]"))};
  - 检查环境完整性并显示健康报告按{BOLD(LIGHT_GREEN("[H]"))};
  - 搜索 Conda 软件包按{BOLD(LIGHT_YELLOW("[S]"))};"""

    # a. Extras
    if env_size_recalc_need_confirm:
        calc_cost_time = data_manager.get_data("envs_size_data").get("calc_cost_time", 0)
        cost_prompt = f"(约 {calc_cost_time:.0f} 秒)" if calc_cost_time > 0 else ""
        main_prompt_str += f"\n  * {cost_prompt} 统计环境大小及磁盘占用情况按{BOLD(LIGHT_GREEN('[D]'))};"

    main_prompt_str += "\n"

    return main_prompt_str


def _prompt_and_validate_command(allowed_inputs: list[str], immediately_returned_chars: Iterable[str]) -> str:
    """提示并放回通过验证的用户输入的字符串，或者立即返回由 immediately_returned_chars 指定的字符。

    此函数用于提示用户输入，并根据给定的允许输入列表验证输入是否合法，不合法则重新提示用户输入。
    内部get_command函数使用get_char()获取输入，最多支持获取{_MAX_WIDTH-len(prompt)}个字符。

    Args:
        allowed_inputs (list[str]): 允许的输入列表。
        immediately_returned_chars (list[str]): 立即返回的字符列表。

    Notes:
        用户输入界面：    "请按下指令键，或输入命令并回车："
                        "$ {user_inp}"
    """

    def refresh_line(prompt: str, user_inp: str, cursor_pos: int):
        """刷新当前输入行，并自动恢复光标的正确位置。"""
        print("\r\033[K", end="", flush=True)  # 清除当前行
        print(prompt + user_inp, end="", flush=True)
        print("\b" * len_to_print(user_inp[cursor_pos:]), end="", flush=True)

    def get_valid_command() -> str:
        """简易的自定义input函数。

        支持特定字符立即返回；仅在输入合法时提示符变绿后才可回车；
        输入必须在一行内；及光标左右移动、退格删除、Esc清空、Ctrl+C退出。
        """
        _MAX_WIDTH = min(25, fast_get_terminal_size().columns - 2)  # 让输入不超过一行
        is_correct_input = False
        prompt = BOLD("$ ")
        user_inp = ""
        cursor_pos = 0
        print(prompt, end="", flush=True)
        while char := get_char():
            if char in immediately_returned_chars and not user_inp:  # 按下立即返回的字符且输入为空
                user_inp = char
                break
            elif char == "\r" and user_inp in allowed_inputs:  # 按下回车键且输入合法则返回
                break
            elif char == "\x03":  # 按下Ctrl+C
                user_inp = "Q"
                break

            if char in ("\x1b[D", "àK"):  # 按下左箭头
                if cursor_pos > 0:
                    left_len = len_to_print(user_inp[cursor_pos - 1])
                    cursor_pos -= 1
                    print("\b" * left_len, end="", flush=True)
            elif char in ("\x1b[C", "àM"):  # 按下右箭头
                if cursor_pos < len(user_inp):
                    right_len = len_to_print(user_inp[cursor_pos])
                    cursor_pos += 1
                    print("\033[C" * right_len, end="", flush=True)
            elif len(char) == 1 and char.isprintable():  # 输入可打印字符
                if len_to_print(f"{prompt}{user_inp}") < _MAX_WIDTH:
                    user_inp = user_inp[:cursor_pos] + char + user_inp[cursor_pos:]
                    cursor_pos += 1
                    if cursor_pos == len(user_inp):
                        print(char, end="", flush=True)
                    else:
                        refresh_line(prompt, user_inp, cursor_pos)
            elif char in ("\x08", "\x7f"):  # 按下退格键
                if cursor_pos > 0:
                    del_len = len_to_print(user_inp[cursor_pos - 1])
                    user_inp = user_inp[: cursor_pos - 1] + user_inp[cursor_pos:]
                    cursor_pos -= 1
                    if cursor_pos == len(user_inp):
                        print("\b" * del_len + " " * del_len + "\b" * del_len, end="", flush=True)
                    else:
                        refresh_line(prompt, user_inp, cursor_pos)
            elif char == "\x1b":  # 按下ESC键，清空输入
                user_inp = ""
                cursor_pos = 0
                refresh_line(prompt, user_inp, cursor_pos)

            if user_inp in allowed_inputs:  # 对于合法的输入，提示符变为绿色
                refresh_line(LIGHT_GREEN(prompt), user_inp, cursor_pos)
                is_correct_input = True
            elif is_correct_input:
                refresh_line(prompt, user_inp, cursor_pos)
                is_correct_input = False

        return user_inp.strip(" ")

    allowed_inputs.extend(immediately_returned_chars)

    first_prompt_str = "请按下指令键，或输入命令并回车："

    print(first_prompt_str)
    inp = get_valid_command()
    clear_lines_above(get_printed_line_count(first_prompt_str))

    return inp


def show_info_and_get_input(env_infos_dict: EnvInfosDict) -> str:
    """显示主界面信息并获取用户的操作指令以供 do_action 函数执行相应操作。

    Attention:
        * * * * * 注意 * * * * *
        此函数是整个脚本的三个主函数其二，负责主循环中 “显示主界面信息和获取用户指令” 功能。
    """
    global main_display_mode

    env_num = env_infos_dict["env_num"]
    valid_env_num = env_infos_dict["valid_env_num"]
    others_env_pathlist = env_infos_dict["others_env_pathlist"]

    # 1.1 输出<可能的>其他发行版与不受支持的环境
    _print_other_envs(others_env_pathlist)

    def printRegularTransactionSet(cls=False):
        table = get_envs_prettytable(env_infos_dict)
        if cls:
            clear_screen(hard=CFG_FULL_TERMINAL_CLEAR)
        # 1.2 输出抬头
        table_rstrip_width = len_to_print(table.get_string().splitlines()[0].rstrip())
        _print_header(table_rstrip_width, env_infos_dict)
        # 1.3 输出表格
        _print_envs_table(table, env_infos_dict)

        # 2. 输出主界面提示信息
        main_prompt_str = _get_main_prompt_str(valid_env_num)
        print(main_prompt_str)

    printRegularTransactionSet()

    # 3. 提示用户按下或输入对应指令
    _CYCLE_DISP = "\t"
    allowed_commands = ["-", "_", "+", "=", "I", "R", "J", "C", "V", "U", "S", "Q", "P", "H", _CYCLE_DISP]
    if env_size_recalc_need_confirm:
        allowed_commands.append("D")
    allowed_commands += [char.lower() for char in allowed_commands if char.isupper()]
    allowed_inputs = [f"@{str(i)}" for i in range(1, env_num + 1)]
    valid_env_numbers = [str(i) for i in range(1, valid_env_num + 1)]
    if valid_env_num > 9:  # 仅允许激活有效的环境
        allowed_inputs += valid_env_numbers
    else:
        allowed_commands += valid_env_numbers

    while True:  # 设置了immediately_returned_chars后，inp最多只能接受一行内的字符
        inp = _prompt_and_validate_command(allowed_inputs, allowed_commands)
        if inp == _CYCLE_DISP:
            main_display_mode = main_display_mode % 3 + 1
            printRegularTransactionSet(cls=True)
        else:
            clear_lines_above(get_printed_line_count(_get_main_prompt_str(valid_env_num)))
            return inp


def do_action(inp, env_infos_dict: EnvInfosDict):
    """根据用户按下或输入的值执行相应的操作，并生成状态码。

    Args:
        inp (str): 用户按下或输入的指令。
        env_infos_dict (dict): 环境信息字典。

    Note:
        通过修改全局变量 action_status 来存储状态码:
            - 1 表示需要继续显示环境列表 (即继续脚本主循环);
            - 0 表示正常进入环境 (即进入命令行，退出主循环)。

    Attention:
        * * * * * 注意 * * * * *
        此函数是整个脚本的三个主函数其三，负责主循环中 “根据用户输入执行相应的操作” 功能。
    """
    env_num = env_infos_dict["env_num"]
    valid_env_num = env_infos_dict["valid_env_num"]
    env_namelist = env_infos_dict["env_namelist"]
    env_pathlist = env_infos_dict["env_pathlist"]
    env_validity_list = env_infos_dict["env_validity_list"]
    env_lastmodified_timelist = env_infos_dict["env_lastmodified_timelist"]
    env_installation_time_list = env_infos_dict["env_installation_time_list"]
    env_pyverlist = env_infos_dict["env_pyverlist"]
    env_totalsize_list = env_infos_dict["env_totalsize_list"]

    def _print_table(env_names: list[str], field_name_env="Env Name", body_color: ColorType = None) -> bool:
        """验证 env_names 环境名称列表是否为空；若为空则返回 False；否则打印表格并返回 True。"""
        if not env_names:
            print(LIGHT_RED("[错误] 未检测到有效的环境编号！"))
            return False
        table = PrettyTable([field_name_env, "PyVer", "Last Updated/Installation"])
        table.align = "l"
        table.border = False
        for name in env_names:
            table.add_row(
                [
                    name,
                    env_pyverlist[env_namelist.index(name)],
                    env_lastmodified_timelist[env_namelist.index(name)]
                    + " / "
                    + env_installation_time_list[env_namelist.index(name)],
                ]
            )
        print(three_line_table(table, body_color=body_color))
        return True

    global action_status
    # 如果按下的是[-]或[_]，则删除环境
    if inp in ("-", "_"):
        if not all(env_validity_list):
            invalid_env_names = [env_namelist[i] for i in range(env_num) if not env_validity_list[i]]
            invalid_env_paths = [env_pathlist[i] for i in range(env_num) if not env_validity_list[i]]
            invalid_env_sizes = [env_totalsize_list[i] for i in range(env_num) if not env_validity_list[i]]
            if all(x == 0 for x in invalid_env_sizes):  # 当大小并未被计算时(仅可能在Windows下发生)
                invalid_env_sizes = get_paths_totalsize_list(invalid_env_paths)
            invalid_env_timelist = [os.path.getmtime(i) for i in invalid_env_paths]
            table = PrettyTable(["Name", "Path", "Size", "Timestamp"])
            table.align = "l"
            table.align["Size"] = "r"  # type: ignore
            table.border = False
            for i in range(len(invalid_env_names)):
                table.add_row(
                    [
                        invalid_env_names[i],
                        replace_user_path(invalid_env_paths[i]),
                        format_size(invalid_env_sizes[i], B_suffix=False),
                        time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(invalid_env_timelist[i])),
                    ]
                )
            _s = f" Invalid Environments ({format_size(sum(invalid_env_sizes))}) "
            print(LIGHT_RED(three_line_table(table, title=_s)))
            print(LIGHT_YELLOW("(i) 检测到以上无效环境，是否删除？"))
            inp = input_strip("[(Y)/n] >>> ")
            if ResponseChecker(inp, default="yes").is_yes():
                for i in range(env_num - valid_env_num):
                    command = get_cmd([f'mamba remove -n "{invalid_env_names[i]}" --all --yes --quiet'])
                    subprocess.run(command, shell=True)
                    if os.path.exists(invalid_env_paths[i]):
                        rmtree(invalid_env_paths[i])
                print(LIGHT_GREEN("[提示] 所有无效环境均已被删除！"))
                return

        print(f"(1) 请输入想要{BOLD(RED('删除'))}的环境的编号（或all=全部），多个以空格隔开：")
        inp = input_strip(f"[2-{env_num} | all] >>> ")
        if inp.lower() == "all":
            env_delete_names = [i for i in env_namelist if i not in illegal_env_namelist]
        else:
            env_delete_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
            env_delete_names = [
                env_namelist[i] for i in env_delete_nums if env_namelist[i] not in illegal_env_namelist
            ]
        if not _print_table(env_delete_names, field_name_env="Env to Delete", body_color="LIGHT_RED"):
            return
        print("(2) 确认删除以上环境吗？")
        inp = input_strip("[(Y)/n] >>> ")
        if not ResponseChecker(inp, default="yes").is_yes():
            return
        for name in env_delete_names:
            command = get_cmd([f'mamba remove -n "{name}" --all --yes --quiet'])
            subprocess.run(command, shell=True)
            command = get_cmd([f"jupyter kernelspec list --json"])
            result_text = subprocess.run(command, shell=True, stdout=subprocess.PIPE, text=True).stdout
            # 清除可能的Jupyter注册
            try:
                result_json_dic = json.loads(result_text)
            except:
                print(
                    LIGHT_YELLOW(
                        "[警告] base 环境未安装 Jupyter ，无法管理相关环境的 Jupyter 内核注册，请在主界面按[J]以安装"
                    )
                )
                return
            _this_env_pypath = (
                result_json_dic.get("kernelspecs", {}).get(name, {}).get("spec", {}).get("argv", [""])[0]
            )
            if _this_env_pypath and not os.path.exists(_this_env_pypath):
                command = get_cmd([f'jupyter kernelspec uninstall "{name}" -f'])
                subprocess.run(command, shell=True)
                print(LIGHT_GREEN(f"[提示] 已清除卸载的环境 {LIGHT_CYAN(name)} 的 Jupyter 内核注册"))

    # 如果按下的是[+]或[=]，则新建环境
    elif inp in ("+", "="):
        print(f"(1) 请输入想要{BOLD(LIGHT_GREEN('新建'))}的环境的名称：")
        new_name = get_valid_input(
            ">>> ",
            condition_func=lambda x: is_legal_envname(x, env_namelist),
            error_msg_func=lambda input_str: f"新环境名称 {LIGHT_CYAN(input_str)} "
            + f"{LIGHT_RED('已存在或不符合规范')}，请重新输入：",
        )
        py_pattern = r"(?:py|python)[_.-]?(\d)\.?(\d{1,2})"
        py_match = re.search(py_pattern, new_name, re.IGNORECASE)
        if py_match and (
            (int(py_match[1]) == 1 and int(py_match[2]) in (0, 2, 3, 4, 5, 6))
            or (int(py_match[1]) == 2 and int(py_match[2]) in (0, 6, 7))
            or (int(py_match[1]) == 3 and 3 <= int(py_match[2]) <= 15)
        ):
            py_version = py_match.group(1) + "." + py_match.group(2)
            print(
                f"(2) [提示] 根据环境名称 {LIGHT_CYAN(new_name)} 已自动确定 Python 版本为 {LIGHT_GREEN(py_version)}"
            )
        else:
            print("(2) 请指定 Python 版本（为空默认最新版）：")
            py_version = get_valid_input(
                "[x.y] >>> ",
                condition_func=lambda x: re.match(r"\d\.\d", x) or x == "",
            )
        print(
            f"(3) 请指定预安装参数（如{LIGHT_YELLOW('spyder')}包等，{LIGHT_GREEN('-c nvidia')}源等，以空格隔开）："
        )
        print(
            LIGHT_YELLOW("[提示]")
            + f" 若输入\"{LIGHT_GREEN('--+')}\"，则等效于预安装\"{LIGHT_YELLOW(CFG_CMD_TRIGGERED_PKGS)}\"包"
            + "（并注册 Jupyter 内核）"
            if "ipykernel" in CFG_CMD_TRIGGERED_PKGS
            else ""
        )
        install_opts = input_strip(">>> ")
        is_register_jupyter = False
        if install_opts.find("--+") != -1:
            install_opts = install_opts.replace("--+", CFG_CMD_TRIGGERED_PKGS)
            is_register_jupyter = True if "ipykernel" in CFG_CMD_TRIGGERED_PKGS else False

        py_version = f"={py_version}" if py_version else ""
        command = get_cmd([f'mamba create -n "{new_name}" python{py_version} {install_opts}'])
        cmd_res = subprocess.run(command, shell=True).returncode
        # 如果安装不成功则尝试使用更多的源
        if cmd_res != 0:
            print(LIGHT_YELLOW(f"(3a) {LIGHT_RED('安装失败！')}是否启用更多的源重新安装？"))
            inp = input_strip("[(Y)/n] >>> ")
            if not ResponseChecker(inp, default="yes").is_yes():
                return
            else:
                print(
                    LIGHT_YELLOW("[提示]") + " 常用第三方源有：" + LIGHT_GREEN("pytorch nvidia intel Paddle ...")
                )
                print("(3b) 请输入更多的源，以空格隔开：")
                inp_sources = input_strip(">>> ")
                inp_source_str = " ".join(f"-c {i}" for i in inp_sources.split())
                command = get_cmd(
                    [f'mamba create -n "{new_name}" python{py_version} {install_opts} {inp_source_str}']
                )
                subprocess.run(command, shell=True)
                # 将启用的源添加为当前新环境的默认源
                if new_name in _get_env_basic_infos()[0]:
                    inp_source_str = " ".join(f"--add channels {i}" for i in inp_sources.split()[::-1])
                    command = get_cmd(
                        [
                            f'conda activate "{new_name}"',
                            f"conda config --env {inp_source_str}",
                        ]
                    )
                    subprocess.run(command, shell=True)
                    print(f"(3c) 已将 {LIGHT_GREEN(inp_sources)} 添加为新环境 {LIGHT_CYAN(new_name)} 的默认源。")

        if is_register_jupyter and new_name in _get_env_basic_infos()[0]:
            if not re.match(r"^[A-Za-z0-9._-]+$", new_name):
                print(
                    LIGHT_YELLOW(
                        f"(i) 检测到环境名 {LIGHT_CYAN(new_name)} 存在非规范字符，请重新取 Jupyter 内核的注册名（非显示名称）："
                    )
                )
                jup_name = get_valid_input(
                    ">>> ",
                    condition_func=lambda x: re.match(r"^[A-Za-z0-9._-]+$", x),
                    error_msg_func=lambda input_str: f"Jupyter 注册名称 {LIGHT_YELLOW(input_str)} "
                    + LIGHT_RED("不全符合[A-Za-z0-9._-]规则")
                    + f"，请重新为 {LIGHT_CYAN(new_name)} 的 Jupyter 内核取注册名：",
                )
            else:
                jup_name = new_name
            print(f"(4) 请输入此环境注册的 Jupyter 内核的显示名称（为空使用默认值）：")
            jup_disp_name = input_strip(f"[{new_name}] >>> ")
            if jup_disp_name == "":
                jup_disp_name = new_name
            command = get_cmd(
                [
                    f'conda activate "{new_name}"',
                    f'python -m ipykernel install --user --name "{jup_name}" --display-name "{jup_disp_name}"',
                ]
            )
            subprocess.run(command, shell=True)

    # 如果按下的是[I]，则将指定环境注册到Jupyter
    elif inp.upper() == "I":
        print(f"(1) 请输入想要将 Jupyter 内核{BOLD(CYAN('注册'))}到用户的环境编号（或all=全部），多个以空格隔开：")
        inp = input_strip(f"[2-{valid_env_num} | all] >>> ")
        if inp.lower() == "all":
            env_reg_names = [i for i in env_namelist if i not in illegal_env_namelist]
        else:
            env_reg_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= valid_env_num]
            env_reg_names = [env_namelist[i] for i in env_reg_nums if env_namelist[i] not in illegal_env_namelist]
        if not _print_table(env_reg_names, field_name_env="Env to Register", body_color="LIGHT_CYAN"):
            return
        print("(2) 确认注册以上环境的 Jupyter 内核到用户吗？")
        inp = input_strip("[(Y)/n] >>> ")
        if not ResponseChecker(inp, default="yes").is_yes():
            return
        for idx, name in enumerate(env_reg_names, 1):
            if not re.match(r"^[A-Za-z0-9._-]+$", name):
                print(
                    LIGHT_YELLOW(
                        f"(i) 检测到环境名 {LIGHT_CYAN(name)} 存在非规范字符，请重新取 Jupyter 内核的注册名（非显示名称）："
                    )
                )
                jup_name = get_valid_input(
                    ">>> ",
                    condition_func=lambda x: re.match(r"^[A-Za-z0-9._-]+$", x),
                    error_msg_func=lambda input_str: f"Jupyter 注册名称 {LIGHT_YELLOW(input_str)} "
                    + LIGHT_RED("不全符合[A-Za-z0-9._-]规则")
                    + f"，请重新为 {LIGHT_CYAN(name)} 的 Jupyter 内核取注册名：",
                )
            else:
                jup_name = name
            print(f"(3.{idx}) 请输入环境 {LIGHT_CYAN(name)} 注册的 Jupyter 内核的显示名称（为空使用默认值）：")
            jup_disp_name = input_strip(f"[{name}] >>> ")
            if jup_disp_name == "":
                jup_disp_name = name
            command = [CONDA_EXE_PATH, "list", "-n", name, "--json"]
            result_text = subprocess.run(command, stdout=subprocess.PIPE, text=True).stdout

            _command = [f'conda activate "{name}"']
            if result_text.find("ipykernel") == -1:
                print(LIGHT_YELLOW("[提示] 该环境中未检测到 ipykernel 包，正在为环境安装 ipykernel 包..."))
                _command.append("mamba install ipykernel --no-update-deps --yes --quiet")
            _command.append(
                f'python -m ipykernel install --user --name "{jup_name}" --display-name "{jup_disp_name}"'
            )
            command = get_cmd(_command)
            subprocess.run(command, shell=True)

    # 如果按下的是[R]，则重命名环境
    elif inp.upper() == "R":
        print(f"(1) 请输入想要{BOLD(LIGHT_BLUE('重命名'))}的环境的编号，多个以空格隔开：")
        inp = input_strip(f"[2-{valid_env_num}] >>> ")
        env_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= valid_env_num]
        env_names = [env_namelist[i] for i in env_nums if env_namelist[i] not in illegal_env_namelist]
        if not _print_table(env_names, field_name_env="Env to Rename", body_color="LIGHT_CYAN"):
            return
        print("(2) 确认重命名以上环境吗？")
        inp = input_strip("[(Y)/n] >>> ")
        if not ResponseChecker(inp, default="yes").is_yes():
            return
        for idx, name in enumerate(env_names, 1):
            print(f"(3.{idx}) 请输入环境 {LIGHT_CYAN(name)} 重命名后的环境名称：")
            new_name = get_valid_input(
                ">>> ",
                condition_func=lambda x: is_legal_envname(x, env_namelist) and x != name,
                error_msg_func=lambda input_str: f"新环境名称 {LIGHT_CYAN(input_str)} "
                + f"{LIGHT_RED('已存在或不符合规范')}，请重新为 {LIGHT_CYAN(name)} 重命名：",
            )
            command = get_cmd(
                [
                    f'mamba create -n "{new_name}" --clone "{name}"',
                    f'mamba remove -n "{name}" --all --yes --quiet',
                ]
            )
            subprocess.run(command, shell=True)
            command = get_cmd(
                [
                    f"jupyter kernelspec list --json",
                ]
            )
            result_text = subprocess.run(command, shell=True, stdout=subprocess.PIPE, text=True).stdout
            # 重新可能的Jupyter注册
            try:
                result_json_dic = json.loads(result_text)
            except:
                print(
                    LIGHT_YELLOW(
                        "[警告] base 环境未安装 Jupyter，无法管理相关环境的 Jupyter 内核注册，请在主界面按[J]以安装"
                    )
                )
                return
            _this_env_pypath = (
                result_json_dic.get("kernelspecs", {}).get(name, {}).get("spec", {}).get("argv", [""])[0]
            )
            if _this_env_pypath and not os.path.exists(_this_env_pypath):
                print(
                    LIGHT_YELLOW("[提示] 检测到原环境的 Jupyter 注册已失效，正在为新环境重新注册 Jupyter 内核...")
                )
                if not re.match(r"^[A-Za-z0-9._-]+$", new_name):
                    print(
                        LIGHT_YELLOW(
                            f"(i) 检测到新环境名 {LIGHT_CYAN(new_name)} 存在非规范字符，请重新取 Jupyter 内核的注册名（非显示名称）："
                        )
                    )
                    jup_name = get_valid_input(
                        ">>> ",
                        condition_func=lambda x: re.match(r"^[A-Za-z0-9._-]+$", x),
                        error_msg_func=lambda input_str: f"Jupyter 内核注册名称 {LIGHT_YELLOW(input_str)} "
                        + LIGHT_RED("不全符合[A-Za-z0-9._-]规则")
                        + f"，请重新为 {LIGHT_CYAN(new_name)} 的 Jupyter 内核取注册名：",
                    )
                else:
                    jup_name = new_name
                print("(4) 请输入注册的 Jupyter 内核的显示名称（为空使用默认值）：")
                jup_disp_name = input_strip(f"[{new_name}] >>> ")
                if jup_disp_name == "":
                    jup_disp_name = new_name
                command = get_cmd(
                    [
                        f'jupyter kernelspec uninstall "{name}" -f',
                        f'conda activate "{new_name}"',
                        f'python -m ipykernel install --user --name "{jup_name}" --display-name "{jup_disp_name}"',
                    ]
                )
                subprocess.run(command, shell=True)
                print(LIGHT_GREEN(f"[提示] 已重新注册新环境 {LIGHT_CYAN(new_name)} 的 Jupyter 内核！"))

    # 如果按下的是[P]，则复制环境
    elif inp.upper() == "P":
        print(f"(1) 请输入想要{BOLD(LIGHT_CYAN('复制'))}的环境的编号，多个以空格隔开：")
        inp = input_strip(f"[1-{valid_env_num}] >>> ")
        env_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= valid_env_num]
        env_names = [env_namelist[i] for i in env_nums]
        if not _print_table(env_names, field_name_env="Env to Copy"):
            return
        print("(2) 确认复制以上环境吗？")
        inp = input_strip("[(Y)/n] >>> ")
        if not ResponseChecker(inp, default="yes").is_yes():
            return
        for idx, name in enumerate(env_names, 1):
            print(f"(3.{idx}) 请输入环境 {LIGHT_CYAN(name)} 复制后的环境名称（为空使用默认值）：")
            default_name = name + "_copy"
            copy_idx = 1
            while default_name in env_namelist:
                copy_idx += 1
                default_name = name + "_copy" + "_" + str(copy_idx)
            new_name = get_valid_input(
                f"[{default_name}] >>> ",
                condition_func=lambda x: is_legal_envname(x, env_namelist) or x == "",
                error_msg_func=lambda input_str: f"新环境名称 {LIGHT_CYAN(input_str)} "
                + f"{LIGHT_RED('已存在或不符合规范')}，请重新为 {LIGHT_CYAN(name)} 命名：",
            )
            if new_name == "":
                new_name = default_name
            command = get_cmd([f'mamba create -n "{new_name}" --clone "{name}" --quiet'])
            subprocess.run(command, shell=True)

    # 如果按下的是[J]，则显示、管理所有已注册的Jupyter环境及清理弃用项
    elif inp.upper() == "J":
        jupyter_exe_path = re.sub(r"conda(?=($|\.exe$))", "jupyter", CONDA_EXE_PATH)
        if not os.path.isfile(jupyter_exe_path):
            print(LIGHT_YELLOW("[提示] 未检测到 Jupyter 命令，正尝试向 base 环境安装 ipykernel..."))
            command = get_cmd(["mamba install ipykernel -y"])
            if subprocess.run(command, shell=True).returncode:
                print(LIGHT_RED("[提示] 安装失败，请在 base 环境中手动安装 ipykernel 后重试！"))
                return
            else:
                print(LIGHT_GREEN(f"[提示] {LIGHT_CYAN('base')} 环境中 ipykernel 安装成功！"))
        print(f"当前用户{BOLD(LIGHT_BLUE('已注册'))}的 {BOLD('Jupyter')} 内核如下：")
        command = get_cmd(["jupyter kernelspec list --json"])
        kernel_output = subprocess.run(command, shell=True, stdout=subprocess.PIPE, text=True).stdout
        kernel_dict = json.loads(kernel_output).get("kernelspecs", {})
        # 创建 Prettytable 表格对象
        kernel_names = []
        is_valid_kernels = []
        display_names = []
        py_pathlist = []
        py_versions = []
        install_timestamps = []
        kernel_dirs = []

        value = kernel_dict.pop("python3", None)
        if value:
            kernel_dict = {"python3": value, **kernel_dict}

        for k_name, k_info in kernel_dict.items():
            kernel_names.append(k_name)
            display_names.append(k_info["spec"]["display_name"])
            py_pathlist.append(k_info["spec"]["argv"][0])
            install_timestamps.append(
                time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(k_info["resource_dir"])))
            )
            kernel_dirs.append(replace_user_path(k_info["resource_dir"]))
        py_versions = get_pyvers_from_paths(py_pathlist)
        is_valid_kernels = [bool(i) for i in py_versions]

        dir_col_max_width = max(len_to_print(i) for i in kernel_dirs)
        table = PrettyTable(
            [
                "No.",
                "Display Name",
                "Py Ver.",
                "Install Time",
                f"Resource Dir{' ':{dir_col_max_width-25}}{LIGHT_YELLOW('(Kernel Name)')}",
            ]
        )
        table.align = "l"
        table.border = False
        table.padding_width = 1
        for i in range(len(kernel_names)):
            if kernel_names[i] == "python3":
                table.add_row(
                    [
                        LIGHT_CYAN(f"{i+1}"),
                        LIGHT_CYAN(display_names[i]),
                        LIGHT_CYAN(py_versions[i]),
                        LIGHT_CYAN(install_timestamps[i]),
                        LIGHT_CYAN(
                            os.sep.join((lambda p: (p[0], LIGHT_YELLOW(p[1])))(os.path.split(kernel_dirs[i])))
                        ),
                    ]
                )
                continue
            if is_valid_kernels[i]:
                table.add_row(
                    [
                        f"{i+1}",
                        display_names[i],
                        py_versions[i],
                        install_timestamps[i],
                        os.sep.join((lambda p: (p[0], LIGHT_YELLOW(p[1])))(os.path.split(kernel_dirs[i]))),
                    ]
                )
            else:
                table.add_row(
                    [
                        LIGHT_RED(f"{i+1}"),
                        LIGHT_RED(display_names[i] + " (已失效)"),
                        LIGHT_RED("-"),
                        LIGHT_RED(install_timestamps[i]),
                        LIGHT_RED(
                            os.sep.join((lambda p: (p[0], LIGHT_YELLOW(p[1])))(os.path.split(kernel_dirs[i])))
                        ),
                    ]
                )

        if not table._rows:
            print(LIGHT_YELLOW("[提示] 未检测到任何 Jupyter 内核注册！"))
            return
        else:
            print(three_line_table(table))  # 打印表格
        print()

        # 询问清理失效项
        if not all(is_valid_kernels):
            print(LIGHT_YELLOW("(0a) 确认清理以上失效项吗？"))
            inp = input_strip("[(Y)/n] >>> ")
            if ResponseChecker(inp, default="yes").is_yes():
                for kernel in [i for i in kernel_names if not is_valid_kernels[kernel_names.index(i)]]:
                    command = get_cmd([f'jupyter kernelspec uninstall "{kernel}" -f'])
                    subprocess.run(command, shell=True)

        # 删除对应Jupyter环境
        print(f"(1) 请输入想要{BOLD(RED('删除'))}的 Jupyter 内核的编号（或all=全部），多个以空格隔开：")
        inp = input_strip(f"[2-{len(kernel_names)} | all] >>> ")
        if inp.lower() == "all":
            kernel_nums_todelete = range(len(kernel_names))
        else:
            kernel_nums_todelete = [
                int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= len(kernel_names)
            ]
        kernel_names_todelete = [kernel_names[i] for i in kernel_nums_todelete if kernel_names[i] != "python3"]
        if kernel_names_todelete:
            table = PrettyTable(["Display Name", "Location"], border=False, padding_width=1, align="l")
            for kernel in kernel_names_todelete:
                table.add_row([display_names[kernel_names.index(kernel)], kernel_dirs[kernel_names.index(kernel)]])
            print(three_line_table(table, body_color="LIGHT_RED"))
        else:
            print("[错误] 未检测到有效的 Jupyter 内核编号！")
            return
        print("(2) 确认删除以上 Jupyter 内核注册吗？")
        inp = input_strip("[(Y)/n] >>> ")
        if not ResponseChecker(inp, default="yes").is_yes():
            return
        for kernel in kernel_names_todelete:
            command = get_cmd([f'jupyter kernelspec uninstall "{kernel}" -f'])
            subprocess.run(command, shell=True)

    # 对应环境查看并回退至历史版本按[V]
    elif inp.upper() == "V":
        print(f"(1) 请输入需要查看及回退{BOLD(LIGHT_MAGENTA('历史版本'))}的环境编号：")
        inp = get_valid_input(
            f"[1-{valid_env_num}] >>> ",
            condition_func=lambda x: x.isdigit() and 1 <= int(x) <= valid_env_num,
            error_msg_func=lambda input_str: f"输入的环境编号 {LIGHT_YELLOW(input_str)} 无效，请重新输入：",
        )
        name = env_namelist[int(inp) - 1]
        print(f"环境 {LIGHT_CYAN(name)} 的历史版本如下：")
        command = [CONDA_EXE_PATH, "list", "-n", name, "--revisions"]
        result_text = subprocess.run(command, stdout=subprocess.PIPE, text=True).stdout
        print(result_text)
        raw_src_set = set(
            source.rsplit("/", 1)[0]
            for source in re.findall(r"\(([^()]+)\)", result_text)
            if "/" in source and " " not in source.rsplit("/", 1)[0]
        )
        sourceslist = filter_and_sort_sources_by_priority(raw_src_set, keep_url=True, enable_default_src=False)
        valid_rev_nums = [i for i in re.findall((r"(?i)\(rev\s+(\d+)\)"), result_text)]
        if not valid_rev_nums:
            print(LIGHT_YELLOW("[提示] 未检测到 Conda 环境的历史版本，无法回退！"))
            return
        print(f"(2) 请输入环境 {LIGHT_CYAN(name)} 的历史版本编号 ({LIGHT_YELLOW(f'0-{valid_rev_nums[-1]}')}): ")
        rev_num = get_valid_input(
            "[rev后的数字] >>> ",
            condition_func=lambda x: x in valid_rev_nums or x == "",
        )
        if rev_num != "" and rev_num != valid_rev_nums[-1]:  # 确认不是当前rev版本
            formatted_sources = " ".join(["-c " + source for source in sourceslist])
            if formatted_sources:
                print(LIGHT_YELLOW("[提示] 根据历史记录已自动启用附加源：") + LIGHT_GREEN(formatted_sources))
            command = get_cmd(
                [f'conda install -n "{name}" --revision {rev_num} {formatted_sources}'],
            )
            subprocess.run(command, shell=True)

    # 如果按下的是[C]，则运行pip cache purge和mamba clean --all -y来清空所有pip与conda缓存
    elif inp.upper() == "C":
        print(LIGHT_YELLOW("[提示] 加载缓存信息中，请稍等..."))
        command = get_cmd(["mamba clean --all --dry-run --json --quiet", "pip cache dir"])
        result_text = subprocess.run(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        ).stdout
        clear_lines_above(1)
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
                "1",
                "Conda Index Caches",
                format_size(index_cache_size),
                os.path.join("$CONDA_HOME", "pkgs", "cache", "*.json"),
            ]
            tarballs_cache_row = [
                "2",
                "Conda Unused Tarballs",
                format_size(tarballs_cache_size := result_json_dic["tarballs"]["total_size"]),
                os.path.join("$CONDA_HOME", "pkgs", "(*.tar.bz2|*.conda)"),
            ]
            pkgs_cache_row = [
                "3",
                "Conda Unused Packages",
                format_size(pkgs_cache_size := result_json_dic["packages"]["total_size"]),
                os.path.join("$CONDA_HOME", "pkgs", "(包文件夹)"),
            ]
            logs_and_temps_size = 0
            for _path in result_json_dic["logfiles"] + result_json_dic["tempfiles"]:
                if os.path.isdir(_path):
                    logs_and_temps_size += get_folder_size(_path)
                elif os.path.isfile(_path):
                    logs_and_temps_size += os.path.getsize(_path)
            logs_and_temps_row = [
                "4",
                "Conda Logs & Temps",
                format_size(logs_and_temps_size),
                "Conda logfiles & tempfiles",
            ]
            if os.path.isdir(result_text_pip):
                pip_cache_size = get_folder_size(result_text_pip)
                pip_cache_Description = "Pip index cache & local built wheels"
            else:
                pip_cache_size = 0
                pip_cache_Description = "* DISABLED *"
            pip_cache_row = [
                "5",
                "Pip Cache",
                format_size(pip_cache_size),
                pip_cache_Description,
            ]
            total_size = (
                index_cache_size + tarballs_cache_size + pkgs_cache_size + logs_and_temps_size + pip_cache_size
            )
            table = PrettyTable(["No.", "Items to Clean", "Size", "Description"])
            table.add_row(index_cache_row)
            table.add_row(tarballs_cache_row)
            table.add_row(pkgs_cache_row)
            table.add_row(logs_and_temps_row)
            table.add_row(pip_cache_row)
            table.align = "l"
            table.border = False
            print(
                three_line_table(
                    table,
                    title=f" {'Mamba' if IS_MAMBA else 'Conda'} 及 Pip 缓存情况 ",
                    footer=f" 总缓存大小：{format_size(total_size)} ",
                    top_bottom_line_char="=",
                )
            )
            print()
            print(f"(1) 请输入Y(回车:全部清理)/N，或想要{BOLD(LIGHT_RED('清理'))}的缓存项编号，多个以空格隔开：")

            def _valid_input_condition(x: str):
                if x in ["Y", "y", "N", "n", "\r", "\n", ""]:
                    return True
                for i in x.split():
                    if not (i.isdigit() and 1 <= int(i) <= 5):
                        return False
                return True

            inp = get_valid_input(
                "[(Y:All)/n | 1-5] >>> ",
                condition_func=_valid_input_condition,
                error_msg_func=lambda x: f"输入 {LIGHT_YELLOW(x)} "
                + "应为空或Y或N或数字 (1-5) 的以空格隔开的组合，请重新输入：",
            )
            if ResponseChecker(inp, default="yes").is_no():
                return
            elif ResponseChecker(inp, default="yes").is_yes():
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
                        command_list.append("mamba clean --logfiles --tempfiles -y")
                    elif i == "5":
                        command_list.append("pip cache purge")
                command = get_cmd(command_list)
            subprocess.run(command, shell=True)
        except Exception as e:
            print(
                LIGHT_RED(LIGHT_RED("[错误] ") + str(e)),
                LIGHT_RED("[错误] mamba clean --all --dry-run --json 命令输出有误！无法解析，输出如下："),
                result_text,
                LIGHT_YELLOW("[提示] 已启动默认清理程序"),
                sep="\n",
            )
            print("(1) 确认清空所有 Conda/pip 缓存吗？")
            inp = input_strip("[(Y)/n] >>> ")
            if not ResponseChecker(inp, default="yes").is_yes():
                return
            command = get_cmd(["mamba clean --all -y", "pip cache purge"])
            subprocess.run(command, shell=True)

    # 如果按下的是[U]，则更新指定环境的所有包
    elif inp.upper() == "U":

        def get_pinned_pkgs(env_name: str) -> dict[str, str]:
            env_path = env_pathlist[env_namelist.index(env_name)]
            pinned_file = os.path.join(env_path, "conda-meta", "pinned")
            pinned_pkgs = {}
            if os.path.exists(pinned_file):
                with open(pinned_file, "r") as f:
                    for line in f.readlines():
                        if line.startswith("#") or not line.strip():
                            continue
                        line = line.strip().replace("=", " ")
                        if len(line.split()) == 2:
                            pkg, version = line.split()
                            pinned_pkgs[pkg] = version
                        else:
                            pinned_pkgs[line.split()[0]] = ""
            return pinned_pkgs

        def write_pinned_pkgs(env_name: str, pinned_pkgs: dict[str, str]):
            env_path = env_pathlist[env_namelist.index(env_name)]
            pinned_file = os.path.join(env_path, "conda-meta", "pinned")
            if not pinned_pkgs:
                if os.path.exists(pinned_file):
                    os.remove(pinned_file)
                return
            with open(pinned_file, "w") as f:
                for pkg, version in pinned_pkgs.items():
                    if version:
                        f.write(f"{pkg}=={version}\n")
                    else:
                        f.write(f"{pkg}\n")

        print(DIM("[提示] 慎用，请仔细检查更新前后的包对应源的变化！"))
        print(f"(1) 请输入想要{BOLD(GREEN('更新'))}的环境的编号（或all=全部），多个以空格隔开：")
        inp = input_strip(f"[1-{valid_env_num} | all] >>> ")
        if inp.lower() == "all":
            env_names = env_namelist
        else:
            env_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= valid_env_num]
            env_names = [env_namelist[i] for i in env_nums]
        if not _print_table(env_names, field_name_env="Env to Update", body_color="LIGHT_CYAN"):
            return
        print("(2) 确认更新以上环境吗？")
        inp = input_strip("[(Y)/n] >>> ")
        if not ResponseChecker(inp, default="yes").is_yes():
            return
        for idx, name in enumerate(env_names, 1):
            print(DIM("-" * fast_get_terminal_size().columns))
            if name == "base":
                strict_channel_priority = False
            else:
                strict_channel_priority = True
                print(f'(i) 是否为 {LIGHT_CYAN(name)} 启用 "strict-channel-priority" 规则？')
                inp = input_strip("[(Y)/n] >>> ")
                if ResponseChecker(inp, default="yes").is_no():
                    strict_channel_priority = False
                clear_lines_above(2)
            print(
                f"[{idx}/{len(env_names)}] 正在更新环境 {LIGHT_CYAN(name)} 的所有包...",
                " (strict-channel-priority:",
                (LIGHT_GREEN("True") + ")" if strict_channel_priority else LIGHT_RED("False") + ")"),
            )

            command = [CONDA_EXE_PATH, "list", "-n", name, "--json"]
            result_text = subprocess.run(command, capture_output=True, text=True).stdout
            result_json_list: list[dict] = json.loads(result_text)

            pinned_pkgs = get_pinned_pkgs(name)
            if pinned_pkgs:
                print(LIGHT_YELLOW(f"[提示] 检测到如下已固定版本的 Conda 包，将不会被更新："))
                table = PrettyTable(["No.", "Pinned Pkg", "Pinned Ver"])
                table.align = "l"
                table.border = False
                for idx, (pkg, version) in enumerate(pinned_pkgs.items(), 1):
                    table.add_row([idx, pkg, version])
                print(three_line_table(table))
            print(f"(i) 是否为该环境 添加(A){'/删除(D)' if pinned_pkgs else ''} Conda 包的固定版本信息？")
            inp = input_strip(f"[A{'/D' if pinned_pkgs else ''}/(NO)] >>> ")
            clear_lines_above(2)
            if inp.upper() == "D" and pinned_pkgs:
                print("(i) 请输入要删除固定版本信息的 Conda 包的编号，多个以空格隔开：")
                inp = get_valid_input(
                    ">>> ",
                    lambda x: not x or all(i.isdigit() and 1 <= int(i) <= idx for i in x.split()),
                )
                if inp:
                    pinned_pkg_names = list(pinned_pkgs.keys())
                    for pkg_idx in inp.split():
                        pkg_idx = int(pkg_idx) - 1
                        del pinned_pkgs[pinned_pkg_names[pkg_idx]]
                    write_pinned_pkgs(name, pinned_pkgs)
                    print(LIGHT_GREEN("[提示] 已删除指定 Conda 包的版本固定信息！"))
            elif inp.upper() == "A":
                table = PrettyTable(["No.", "Package", "Version"])
                table.align = "l"
                table.border = False
                idx = 0
                pkg_rows = []
                for pkginfo_dict in result_json_list:
                    if pkginfo_dict["channel"] != "pypi":
                        idx += 1
                        pkg_rows.append([idx, pkginfo_dict["name"], pkginfo_dict["version"]])
                table.add_rows(pkg_rows)
                print(three_line_table(table, title=" 当前环境的所有 Conda 包 "))
                print("(i) 请输入要固定于当前版本的 Conda 包的编号，多个以空格隔开：")
                print(
                    LIGHT_YELLOW(
                        f'[提示] 默认仅固定主次版本号 (X.Y.*)，若需固定完整版本，请在对应序号前加"{LIGHT_CYAN("=")}"号'
                    )
                )
                inp = get_valid_input(
                    ">>> ",
                    lambda x: not x
                    or all((match := re.match(r"^=*(\d+)$", i)) and 1 <= int(match[1]) <= idx for i in x.split()),
                )
                if inp:
                    for pkg_idx in inp.split():
                        is_full_version = pkg_idx.startswith("=")
                        pkg_idx = int(pkg_idx.replace("=", "")) - 1
                        pkg_name = pkg_rows[pkg_idx][1]
                        pkg_version = pkg_rows[pkg_idx][2]
                        if not is_full_version:
                            ver = version_parse(pkg_version)
                            pkg_version = f"{ver.major}.{ver.minor}.*"
                        pinned_pkgs[pkg_name] = pkg_version
                    write_pinned_pkgs(name, pinned_pkgs)
                    print(LIGHT_GREEN("[提示] 已添加指定 Conda 包的版本固定信息！"))
            raw_src_set = set()
            for pkginfo_dict in result_json_list:
                if source_str := pkginfo_dict.get("channel"):
                    raw_src_set.add(source_str.rsplit("/", 1)[-1])
            if "pypi" in raw_src_set:
                print(LIGHT_YELLOW(f"{LIGHT_RED('[警告]')} 检测到如下由 Pip 安装的包，将不会被更新："))
                table = PrettyTable(["Package from Pip", "Version"])
                table.align = "l"
                table.border = False
                for pkginfo_dict in result_json_list:
                    if pkginfo_dict.get("channel") == "pypi":
                        table.add_row([pkginfo_dict["name"], pkginfo_dict["version"]])
                print(three_line_table(table))
                print(f"(i) 更新环境 {LIGHT_CYAN(name)} 可能不再保证正确的包依赖关系，是否继续？")
                inp1 = input_strip("[y/(N)] >>> ")
                if not ResponseChecker(inp1, default="no").is_yes():
                    continue
            sourceslist = filter_and_sort_sources_by_priority(raw_src_set, enable_default_src=False)
            formatted_sources = " ".join(["-c " + source for source in sourceslist])
            if formatted_sources:
                print(LIGHT_YELLOW("[提示] 已自动启用附加源：") + LIGHT_GREEN(formatted_sources))
            command_str = f'mamba update -n "{name}" {formatted_sources} --all'
            if strict_channel_priority:
                command_str += " --strict-channel-priority"
            command = get_cmd([command_str])
            subprocess.run(command, shell=True)

    # 如果按下的是[S]，则搜索指定Python版本下的包
    elif inp.upper() == "S":
        is_legacy_solver = False
        if not IS_MAMBA and (not LIBMAMBA_SOLVER_VERSION or Version(LIBMAMBA_SOLVER_VERSION) < Version("23.9")):
            is_legacy_solver = True
            print(DIM("[提示] 您的 conda 版本过低，无法加速搜索，请升级到 23.10 及以上。"))

        print(f"(1) 请输入要{BOLD(LIGHT_YELLOW('搜索'))}的包关联的 Python 版本（为空默认全版本）：")
        target_py_version = get_valid_input(
            "[x.y] >>> ",
            condition_func=lambda x: re.match(r"\d\.\d", x) or x == "",
        )

        def _get_pyversion_from_build(build_str: str):
            """从build字符串中提取Python版本号(x.y)，若无则返回None"""
            py_pattern = r"(?<![A-Za-z])(?:py|pypy|python)(2|3)\.?(\d{1,2})(?!\d)"
            if py_match := re.search(py_pattern, build_str):
                return py_match.group(1) + "." + py_match.group(2)
            else:
                return None

        def _get_cuda_version_from_build(build_str: str):
            """从build字符串中提取CUDA版本号(x.y)，若无则返回None"""
            cuda_pattern = r"(?<![A-Za-z])(?:cuda|cu)(\d{1,2})\.?(\d)(?!\d)"
            if cuda_match := re.search(cuda_pattern, build_str):
                if cuda_match.group(1) == "0" or cuda_match.group(1) == "1":
                    return None
                return cuda_match.group(1) + "." + cuda_match.group(2)
            else:
                return None

        def _get_channel_from_url(url_str: str):
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

        def format_major_minor(match: re.Match):
            major, minor = match.groups()
            return f"{major}.{minor}"

        def _preprocess_cuda_version_string(version_str: str):
            version_pattern = re.compile(r"(\d{1,2})\.([a-zA-Z\d*]{1,3})(?:\.[a-zA-Z\d.*]+)?")
            version_gtlt_pattern = re.compile(r">=(\d{1,2}\.[\da]+),<(\d{1,2}\.[\da]+)")
            new_version_str = version_pattern.sub(format_major_minor, version_str)

            if new_version_str.endswith(".0a0"):
                # 在比较版本号时，如果用户输入预览版版本号，结果可能会有歧义，但不重要，因为没人会用预览版
                new_version_str = new_version_str[:-4]

            if res := new_version_str.split("|"):
                if len(res) == 2 and res[0] == res[1]:
                    new_version_str = res[0]

            if match := version_gtlt_pattern.match(new_version_str):
                first_version_1, first_version_2 = match[1].split(".")
                second_version_1, second_version_2 = match[2].split(".")
                if first_version_1 == second_version_1 and int(first_version_2) + 1 == int(second_version_2):
                    new_version_str = match[1]
                elif match[1] == "11.8" and second_version_1 == "12":
                    new_version_str = match[1]

            return new_version_str

        def _preprocess_python_version_string(version_str: str):
            version_str = version_str.replace(" ", "")

            notequal_3vers_pattern = re.compile(r"(,?!=\d+\.\d+\.\d+)(?=,|$)")
            if len(res := notequal_3vers_pattern.sub("", version_str)) > 1:
                version_str = res

            version_pattern = re.compile(r"(2|3|4)\.([a-zA-Z\d*]{1,5})(?:\.[a-zA-Z\d.*]+)?")
            new_version_str = version_pattern.sub(format_major_minor, version_str)

            # 由于比较式"python>3.6"允许3.6.x进行安装，所以需要将>转换为>=
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

        def filter_pkg_info(raw_pkginfo_dict: dict[str, Any]):
            """过滤、处理并原地更新原始包信息字典 raw_pkginfo_dict。

            Notes:
                处理步骤:
                1. 提取并确定构建前缀 (build_prefix)。
                2. 提取并确定包的渠道 (channel)。
                3. 提取并判断是否包含 CUDA (is_cuda)。
                4. 从依赖项和约束条件中提取 Python 版本和 CUDA 版本。
                5. 根据提取的信息更新原始包信息字典。
            """
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
                    and build_rsplit_list[-1][-build_number_length:] == str(raw_pkginfo_dict["build_number"])
                ):
                    build_prefix = "_".join(build_rsplit_list[:-1])
                else:
                    build_prefix = raw_pkginfo_dict["build"]

            channel = _get_channel_from_url(raw_pkginfo_dict["url"])

            is_cuda = False

            python_version = None
            cuda_version = None
            TIMESTAMP_20160220 = 1455955200  # utc 8:00am 2016-02-20

            py_pattern = re.compile(r"python\s+(\S+)")
            py_equal_pattern = re.compile(r"python\s+(?:~=)?((?:2|3|4)\.[\d.*]+)(?!.*[|>=~<])")
            py_gtlt_pattern = re.compile(
                r"python\s+>=((?:2|3|4)\.\d{1,2})(?:\.[\d*a-z]+)?,<((?:2|3|4)\.\d{1,2})(?:\.[\d*a-z]+)?"
            )
            py_abi_pattern = re.compile(r"python_abi\s+((?:2|3|4)\.\d{1,2})")
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
                        python_version = python_version_split[0] + "." + python_version_split[1].replace("*", "")
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

            if not python_version and (python_version := _get_pyversion_from_build(raw_pkginfo_dict["build"])):
                if (python_version == "3.1" or python_version == "3.2") and raw_pkginfo_dict[
                    "timestamp"
                ] > TIMESTAMP_20160220:
                    python_version = None

            if not is_cuda and gpu_pattern.search(raw_pkginfo_dict["build"]):
                is_cuda = True
            if is_cuda and not cuda_version and cpu_pattern.search(raw_pkginfo_dict["build"]):
                is_cuda = False

            if cuda_version:
                cuda_version = _preprocess_cuda_version_string(cuda_version)

            if not python_version and python_version_tmp:
                python_version = _preprocess_python_version_string(python_version_tmp)

            raw_pkginfo_dict["build_prefix"] = build_prefix
            raw_pkginfo_dict["channel"] = channel
            raw_pkginfo_dict["is_cuda"] = is_cuda
            raw_pkginfo_dict["python_version"] = python_version
            raw_pkginfo_dict["cuda_version"] = cuda_version

        def find_python_version_range(python_version_str: str):
            """根据输入的 Python 版本字符串，返回支持的最小和最大 Python 版本。

            Returns:
                tuple: 包含两个元素的元组:
                    - 最小支持的 Python 版本 (str 或 None): 如果存在最小版本限制，则返回该版本字符串；否则返回 None。
                    - 最大支持的 Python 版本 (str 或 None): 如果存在最大版本限制，则返回该版本字符串；否则返回 None。
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

            if min_version == Version("99999.9") or is_version_within_constraints("0.0", python_version_str):
                min_version_str = None
            else:
                min_version_str = str(min_version)
            if max_version == Version("0.0") or is_version_within_constraints("99999.9", python_version_str):
                max_version_str = None
            else:
                max_version_str = str(max_version)

            return min_version_str, max_version_str

        def get_min_supported_cuda_version_11_or_later(cuda_version_str: str) -> Union[str, None]:
            """获取支持的最小 CUDA 版本(11.0及以后), 若无则返回 None"""
            match = re.fullmatch(r"(\d{2})(?:\.[\d*]{1,2})?", cuda_version_str)
            if match:
                major_version = int(match[1])
                if "*" in cuda_version_str:
                    if major_version == 11:
                        return "11.8"
                    elif major_version >= 12:
                        return str(major_version)
                elif major_version >= 11:
                    return cuda_version_str
                return None

            match = re.search(r"(<=|<)(\d{2}(?:\.\d{1,2})?)", cuda_version_str)
            if match:
                operator, version = match.groups()
                major_str, _, minor_str = version.partition(".")
                if operator == "<=":
                    if int(major_str) >= 11:
                        return version
                    return None
                elif operator == "<":
                    if int(major_str) >= 11:
                        if minor_str and int(minor_str) > 0:
                            return f"{major_str}.{int(minor_str)-1}"

            if is_version_within_constraints(cuda_version_str, ">=12"):
                matches = re.findall(r"(12\.\d{1,2})", cuda_version_str)
                for match in reversed(matches):
                    if match != "12.0" and is_version_within_constraints(cuda_version_str, match):
                        return match
                return "12"

            if is_version_within_constraints(cuda_version_str, ">=11.8"):
                return "11.8"

            match = re.search(r">=(11\.\d{1,2})", cuda_version_str)
            if match:
                return match.group(1)

            return None

        class MergePkgInfos:
            """合并包信息列表。

            Notes:
                1. ref提供初筛结果，key为(name,version)，供后续为无Python版本的包提供最大最小Python版本的参考
                2. 第一遍合并需考虑build_prefix一样，按build_number大小合并
                3. 第二遍合并只考虑name, version, channel，并注明支持的最大Python版本，与是否存在CUDA包
            """

            def __init__(self, pkginfos_list_raw: list[dict[str, Any]]):
                self.pkginfo_ref_dict = {}
                for pkginfo_dict in pkginfos_list_raw:
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
                            elif max_py_ver != self.pkginfo_ref_dict[key]["max_py_ver"] and version_parse(
                                max_py_ver
                            ) > version_parse(self.pkginfo_ref_dict[key]["max_py_ver"]):
                                self.pkginfo_ref_dict[key]["max_py_ver"] = max_py_ver
                        if min_py_ver:
                            if not self.pkginfo_ref_dict[key]["min_py_ver"]:
                                self.pkginfo_ref_dict[key]["min_py_ver"] = min_py_ver
                            elif min_py_ver != self.pkginfo_ref_dict[key]["min_py_ver"] and version_parse(
                                min_py_ver
                            ) < version_parse(self.pkginfo_ref_dict[key]["min_py_ver"]):
                                self.pkginfo_ref_dict[key]["min_py_ver"] = min_py_ver
                    else:
                        self.pkginfo_ref_dict[key] = {
                            "max_py_ver": max_py_ver,
                            "min_py_ver": min_py_ver,
                        }

            def get_ref_dict(self):
                """第0遍提供初筛结果，key为(name,version)，供后续为无Python版本的包提供最大最小Python版本的参考"""
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

            def merge_1st(self, pkginfo_dicts_list: list[dict[str, Any]]):
                """第一遍合并需考虑build_prefix一样，按build_number大小合并"""
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

            def merge_2nd(self, pkginfo_dicts_list: list[dict[str, Any]]):
                """第二遍合并只考虑name, version, channel，并注明支持的最大Python版本，与是否存在CUDA包

                Notes:
                    注意！这不是在 merge_1st 的基础上再合并，而是重新从 pkginfos_list_raw 开始合并
                """
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
                        cuda11_or_later_support = get_min_supported_cuda_version_11_or_later(cuda_version)
                    else:
                        cuda11_or_later_support = None

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
                        if cuda11_or_later_support:
                            if not merged_pkginfos_dict[key]["cuda11_or_later"]:
                                merged_pkginfos_dict[key]["cuda11_or_later"] = cuda11_or_later_support
                            elif cuda11_or_later_support != merged_pkginfos_dict[key][
                                "cuda11_or_later"
                            ] and version_parse(cuda11_or_later_support) > version_parse(
                                merged_pkginfos_dict[key]["cuda11_or_later"]
                            ):
                                merged_pkginfos_dict[key]["cuda11_or_later"] = cuda11_or_later_support
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
                            "cuda11_or_later": cuda11_or_later_support,
                            "timestamp": current_timestamp,
                            "build_count": pkginfo_dict.get("build_count", 1),
                        }
                return list(merged_pkginfos_dict.values())

            def merge_3rd(self, pkginfo_dicts_list: list[dict[str, Any]]):
                """第三遍合并只考虑name, channel, 并注明支持的最大Python版本，与是否存在CUDA包"""
                merged_pkginfos_dict = {}
                for pkginfo_dict in pkginfo_dicts_list:
                    name = pkginfo_dict["name"]
                    version = pkginfo_dict["version"]
                    is_cuda = pkginfo_dict["is_cuda"]
                    channel = pkginfo_dict["channel"]
                    current_timestamp = pkginfo_dict["timestamp"]
                    max_py_ver = pkginfo_dict["max_py_ver"]
                    min_py_ver = pkginfo_dict["min_py_ver"]
                    cuda11_or_later_support = pkginfo_dict["cuda11_or_later"]

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
                        if cuda11_or_later_support:
                            if not merged_pkginfos_dict[key]["cuda11_or_later"]:
                                merged_pkginfos_dict[key]["cuda11_or_later"] = cuda11_or_later_support
                            elif version_parse(cuda11_or_later_support) > version_parse(
                                merged_pkginfos_dict[key]["cuda11_or_later"]
                            ):
                                merged_pkginfos_dict[key]["cuda11_or_later"] = cuda11_or_later_support
                        if current_timestamp > merged_pkginfos_dict[key]["timestamp"]:
                            merged_pkginfos_dict[key]["timestamp"] = current_timestamp
                    else:
                        merged_pkginfos_dict[key] = {
                            "name": pkginfo_dict["name"],
                            "version": version,
                            "channel": pkginfo_dict["channel"],
                            "max_py_ver": max_py_ver,
                            "min_py_ver": min_py_ver,
                            "cuda11_or_later": cuda11_or_later_support,
                            "is_cuda": is_cuda,
                            "timestamp": current_timestamp,
                            "build_count": pkginfo_dict["build_count"],
                        }
                return list(merged_pkginfos_dict.values())

        def get_pkginfos_list_raw(
            use_cache: bool, search_pkg_info: str, total_channels: list
        ) -> list[dict[str, Any]]:
            """根据指定是否使用缓存和查询字符串，获取原始的包信息列表。

            该函数将根据 is_legacy_solver: bool 决定是否使用 repoquery 命令以加速搜索。

            Args:
                use_cache (bool): 是否使用缓存。如果为 True，则使用缓存的索引数据。
                search_pkg_info (str): 需要搜索的包信息字符串。
                total_channels (list[str]): 需要搜索的源列表。

            Returns:
                list[dict[str, Any]]: 原始包信息列表。如果解析失败，或结果为空，则返回空列表。
            """
            if is_legacy_solver:
                head_cmd = "conda search"
            else:
                head_cmd = "mamba repoquery search"

            query_option = f'"{search_pkg_info}" {" ".join(["-c "+i for i in total_channels])}'
            cmd_str = f'{head_cmd} {query_option} --json --quiet {"--use-index-cache" if use_cache else ""}'

            command = get_cmd([cmd_str])

            if "mamba repoquery search" in command:  # 解决win下的mamba输出强制utf-8编码问题
                result_text = subprocess.run(
                    command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True
                ).stdout.decode("utf-8")
            else:
                result_text = subprocess.run(
                    command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True, text=True
                ).stdout

            is_error = False
            pkginfos_list_raw = []

            try:
                result_json = json.loads(result_text)
            except json.JSONDecodeError:
                is_error = True
                result_json = {}

            if is_legacy_solver:
                if "error" in result_json:
                    if "PackagesNotFoundError" not in result_json["error"]:
                        is_error = True
                elif result_json and "error" not in result_json:
                    search_pkg_name = search_pkg_info.split("=", 1)[0]
                    name_pattern = re.compile("^" + search_pkg_name.replace("*", ".*") + "$")
                    pkginfos_list_raw = [
                        item
                        for sublist in result_json.values()
                        for item in sublist
                        if name_pattern.match(item["name"])
                    ]
                    for pkginfo_dict in pkginfos_list_raw:
                        if "timestamp" not in pkginfo_dict:
                            pkginfo_dict["timestamp"] = 0
                        else:
                            pkginfo_dict["timestamp"] = int(pkginfo_dict["timestamp"] / 1000)
            else:  # mamba 或 conda >= 23.9
                if not result_json.get("result"):
                    is_error = True
                pkginfos_list_raw = result_json.get("result", {}).get("pkgs", [])

            if is_error:
                print(LIGHT_RED("[错误] 搜索结果解析失败！原始结果如下："))
                print("-" * 10 + "\n" + result_text + "\n" + "-" * 10)
                return []

            return pkginfos_list_raw

        def search_pkgs_main(target_py_version: str):
            """搜索Conda包任务的主函数"""
            print("-" * min(100, fast_get_terminal_size().columns))
            print(
                "[提示1] 搜索默认启用的源为 "
                + LIGHT_GREEN(CFG_DEFAULT_SEARCH_CHANNELS)
                + LIGHT_YELLOW("，如需额外源请在末尾添加 -c 参数")
            )
            print("[提示2] 可用 mamba repoquery depends/whoneeds 命令列出包的依赖项/列出需要给定包的程序包")
            print(
                "[提示3] 搜索语法为 Name=Version=Build，后两项可选（示例: numpy>1.17,<1.19.2 *numpy*=1.17.*=py38*）"
            )
            print(
                "      （详见https://github.com/conda/conda/blob/main/docs/source/user-guide/concepts/pkg-search.rst）"
            )
            print("-" * min(100, fast_get_terminal_size().columns))
            if target_py_version:
                print(f"(2) 请输入要搜索的包名（支持通配符 *；适用于 Python {target_py_version}）：")
            else:
                print("(2) 请输入要搜索的包名（支持通配符 *；适用所有 Python 版本）：")
            inp = get_valid_input(
                ">>> ",
                condition_func=lambda x: x,
                error_msg_func=lambda x: f"输入{LIGHT_RED('不能为空')}，请重新输入：",
            )
            if inp.find(" -c ") != -1:
                add_channels = [i for i in inp[inp.find(" -c ") :].split(" -c ") if i != ""]
                print(
                    LIGHT_YELLOW(
                        "[提示] 检测到 -c 参数，已自动添加相应源：" + LIGHT_GREEN(", ".join(add_channels))
                    )
                )
                search_pkg_info = inp[: inp.find(" -c ")]
            else:
                add_channels = []
                search_pkg_info = inp

            print(f"正在搜索 ({LIGHT_CYAN(search_pkg_info)})...")
            t0_search = time.time()

            total_channels = add_channels + CFG_DEFAULT_SEARCH_CHANNELS.split()
            total_channels = ordered_unique(total_channels)

            search_meta_data = data_manager.get_data("search_meta_data")
            if search_meta_data.get("last_update_time", 0) >= (
                time.time() - CFG_SEARCH_CACHE_EXPIRE_MINUTES * 60
            ) and set(total_channels).issubset(search_meta_data.get("total_channels", [])):
                use_cache = True
                search_meta_data["total_channels"] = list(
                    set(total_channels) | set(search_meta_data.get("total_channels", []))
                )
            else:
                use_cache = False
                search_meta_data["total_channels"] = total_channels
            search_meta_data["last_update_time"] = time.time()
            data_manager.update_data("search_meta_data", search_meta_data)

            pkginfos_list_raw = get_pkginfos_list_raw(use_cache, search_pkg_info, total_channels)

            if not pkginfos_list_raw:
                print(LIGHT_YELLOW(f"[警告] 未搜索到任何相关包 ({round(time.time() - t0_search, 2)} s)！"))
                return

            # pkginfos_list_* :list[dict[str, Any]]每一dict是一个包的信息，list是不同的包组成的列表
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
                                    elif version_parse(matching_ref["max_py_ver"]) > version_parse(max_py_ver):
                                        max_py_ver = matching_ref["max_py_ver"]
                                if matching_ref["min_py_ver"]:
                                    if not min_py_ver:
                                        min_py_ver = matching_ref["min_py_ver"]
                                    elif version_parse(matching_ref["min_py_ver"]) < version_parse(min_py_ver):
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
                            not pkg_min_py_ver or version_parse(pkg_min_py_ver) <= version_parse(target_py_version)
                        ) and (
                            not pkg_max_py_ver or version_parse(pkg_max_py_ver) >= version_parse(target_py_version)
                        ):
                            pkginfos_list_0.append(pkg)
                    else:
                        pkginfos_list_0.append(pkg)

                pkginfos_list_raw = pkginfos_list_0

            class ReverseStr(str):
                def __lt__(self, other):
                    return self > other

            search_name = search_pkg_info.split("=", 1)[0].replace("*", "")

            def _sort_by_name(name_str: str):  # 第二版
                if search_name:
                    forward, _, backward = name_str.partition(search_name)
                    return ReverseStr(forward), ReverseStr(backward)
                else:
                    return name_str

            def _sort_by_channel(channel_str: str):
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

            def _hidden_columns(row: list[str], hidden_field_indexes: Iterable[int]):
                return [row[i] for i in range(len(row)) if i not in hidden_field_indexes]

            def _get_overview_table(
                pkg_overviews_list: list[dict[str, Any]], user_options
            ) -> tuple[PrettyTable, bool]:
                """适用于user_options["ui_mode"]等于1的情况。

                Returns:
                    tuple[PrettyTable, bool]: 同 _get_pkgs_table 函数

                Note:
                    table会尽量显示完整name字段(保证name字段长度>=min_name_width)，为此可能会：
                        省略build_count字段->省略timestamp字段->省略channel字段
                """

                terminal_width = fast_get_terminal_size().columns
                ver_len_maxlim = 15

                _hidden_fields = []
                is_display_omitted = False

                number_field = "No."
                name_field = "Name"
                version_field = f"{LIGHT_GREEN('Latest')} Version" if user_options["merge_version"] else "Version"
                channel_field = "Channel"
                python_version_field = "MinMax PyVer"
                cuda_field = "CUDA" + f" ( ≥ 11 )"
                timestamp_field = "Last Update"
                build_count_field = "Total Builds"

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
                    table_fields.insert(0, number_field)

                table_padding_width = 1
                f_number_width = (
                    max(len(number_field), len(f"{len(pkg_overviews_list)}")) if user_options["select_mode"] else 0
                )
                f_version_width = max(
                    len_to_print(version_field),
                    min(ver_len_maxlim, max(map(lambda x: len(x["version"]), pkg_overviews_list))),
                )
                f_channel_width = max(
                    len_to_print(channel_field), max(map(lambda x: len(x["channel"]), pkg_overviews_list))
                )
                f_python_version_width = len_to_print(python_version_field)
                f_cuda_width = len_to_print(cuda_field)
                f_timestamp_width = len_to_print(timestamp_field)
                f_build_count_width = len_to_print(build_count_field)

                max_name_len = max(map(lambda x: len(x["name"]), pkg_overviews_list))
                name_len_maxlim = (
                    terminal_width
                    - f_number_width
                    - f_version_width
                    - f_channel_width
                    - f_python_version_width
                    - f_cuda_width
                    - f_timestamp_width
                    - f_build_count_width
                    - table_padding_width * 2 * (8 if user_options["select_mode"] else 7)
                )
                min_name_width = min(15, max_name_len)  # 定义name字段最小宽度
                if name_len_maxlim < min_name_width:
                    _hidden_fields.append(build_count_field)
                    name_len_maxlim += f_build_count_width + table_padding_width * 2
                if name_len_maxlim < min_name_width:
                    _hidden_fields.append(timestamp_field)
                    name_len_maxlim += f_timestamp_width + table_padding_width * 2
                if name_len_maxlim < min_name_width:
                    _hidden_fields.append(channel_field)
                    name_len_maxlim += f_channel_width + table_padding_width * 2
                name_len_maxlim = max(name_len_maxlim, min_name_width)

                hidden_field_indexes = {table_fields.index(field) for field in _hidden_fields}

                if hidden_field_indexes:
                    is_display_omitted = True
                    table_fields = _hidden_columns(table_fields, hidden_field_indexes)
                table = PrettyTable(table_fields)
                if user_options["select_mode"]:
                    table.align[number_field] = "l"
                table.align[name_field] = "l"
                table.align[version_field] = "c"
                table.align[channel_field] = "r"
                table.align[python_version_field] = "c"
                table.align[cuda_field] = "r"
                table.align[timestamp_field] = "r"
                table.align[build_count_field] = "r"
                table.padding_width = table_padding_width
                table.border = False

                if len(pkg_overviews_list) == 0:
                    table.add_row(["-" for _ in range(len(table_fields))])
                    table.align = "c"
                    return table, is_display_omitted

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
                        cuda_support = LIGHT_GREEN("Y")
                    else:
                        cuda_support = LIGHT_RED("N")

                    if cuda11_or_later := pkg_overview["cuda11_or_later"]:
                        if version_parse(cuda11_or_later) >= version_parse("12"):
                            cuda11_or_later = f'({LIGHT_GREEN(f"{cuda11_or_later:^6}")})'
                        elif version_parse(cuda11_or_later) >= version_parse("11.8"):
                            cuda11_or_later = f'({LIGHT_CYAN(f"{cuda11_or_later:^6}")})'
                        else:
                            cuda11_or_later = f"({cuda11_or_later:^6})"

                        cuda_support += f"{'':2}{cuda11_or_later}"
                    else:
                        cuda_support += f"{'':10}"
                    if len(pkg_overview["name"]) > name_len_maxlim:
                        name_str = (
                            pkg_overview["name"][: name_len_maxlim - 8]
                            + LIGHT_YELLOW("...")
                            + pkg_overview["name"][-5:]
                        )
                        is_display_omitted = True
                    else:
                        name_str = pkg_overview["name"]
                    if len(pkg_overview["version"]) > ver_len_maxlim:
                        version_str = pkg_overview["version"][: ver_len_maxlim - 3] + LIGHT_YELLOW("...")
                    else:
                        version_str = pkg_overview["version"]

                    channel_str = pkg_overview["channel"]
                    if pkg_overview["name"] in name_maxversion_dict:
                        max_version = name_maxversion_dict[pkg_overview["name"]]
                        if max_version == pkg_overview["version"]:
                            version_str = LIGHT_GREEN(version_str)

                    row = [
                        name_str,
                        version_str,
                        channel_str,
                        python_version_range,
                        cuda_support,
                        (
                            time.strftime("%Y-%m-%d", time.gmtime(pkg_overview["timestamp"]))
                            if pkg_overview["timestamp"]
                            else ""
                        ),
                        f"{pkg_overview['build_count']} builds",
                    ]
                    if user_options["select_mode"]:
                        row.insert(0, f"{i}")
                    if hidden_field_indexes:
                        row = _hidden_columns(row, hidden_field_indexes)
                    table.add_row(row)

                return table, is_display_omitted

            def beautify_version_constraints(constraints_str: str):
                """美化版本约束字符串，通过合并和简化约束来简化输出。"""
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
                    start_version = end_version = f"{only_version_units[0][0]}.{only_version_units[0][1]}"

                    for i, unit in enumerate(only_version_units):
                        if i == 0:
                            continue
                        if unit[0] == only_version_units[i - 1][0] and unit[1] == only_version_units[i - 1][1] + 1:
                            end_version = f"{unit[0]}.{unit[1]}"
                        else:
                            if start_version == end_version and start_version not in merged_constraint_units:
                                merged_constraint_units.append(start_version)
                            else:
                                merged_constraint_units.append(f"{start_version}~{end_version}")
                            start_version = end_version = f"{unit[0]}.{unit[1]}"
                    if start_version == end_version and start_version not in merged_constraint_units:
                        merged_constraint_units.append(start_version)
                    else:
                        merged_constraint_units.append(f"{start_version}~{end_version}")

                def _sort_version(version_str: str):
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

            def merge_not_equal_constraints(constraints_str: str):
                """简化并合并版本约束字符串中不等于!=的约束， 例如："!=1.0,!=1.1,!=1.2" -> "!=1.0~1.2"。"""

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
                    if current_parts[0] == prev_parts[0] and int(current_parts[1]) == int(prev_parts[1]) + 1:
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

            def _get_pkgs_table(pkginfos_list: list[dict[str, Any]], user_options) -> tuple[PrettyTable, bool]:
                """适用于user_options["ui_mode"]等于2或3的情况。

                Returns:
                    tuple[PrettyTable, bool]: 包含以下内容：
                        table: PrettyTable
                        is_display_omitted: 是否有内容(因为终端宽度太小)被省略而未被显示

                Note:
                    table会尽量显示完整name字段(保证name字段长度>=min_name_width)，为此可能会：
                        减少build字段长度->省略build字段->省略size字段->省略timestamp字段
                """
                if user_options["ui_mode"] == 1:
                    return _get_overview_table(pkginfos_list, user_options)

                terminal_width = fast_get_terminal_size().columns
                ver_len_maxlim = 15

                is_display_omitted = False
                _hidden_fields = []

                if user_options["sort_by"][1]:
                    sort_flag = LIGHT_GREEN("▼")
                else:
                    sort_flag = LIGHT_GREEN("▲")

                max_cuda_len = 6
                max_build_count = 1

                if len(pkginfos_list):
                    # 计算build字段的90%分位数
                    build_lengths = list(map(lambda x: len(x["build"]), pkginfos_list))
                    build_lengths.sort()
                    build_len_maxlim = build_lengths[max(0, int(0.9 * len(build_lengths)) - 1)]
                    if build_lengths[-1] - build_len_maxlim < 3:
                        build_len_maxlim = build_lengths[-1]

                    max_name_len = max(map(lambda x: len(x["name"]), pkginfos_list))
                    max_version_len = min(ver_len_maxlim, max(map(lambda x: len(x["version"]), pkginfos_list)))
                    max_channel_len = max(map(lambda x: len(x["channel"]), pkginfos_list))
                    max_python_version_len = max(
                        map(lambda x: len(beautify_version_constraints(x["python_version"] or "")), pkginfos_list)
                    )
                    max_cuda_len = max(map(lambda x: len(x["cuda_version"] or ""), pkginfos_list))
                    max_size_len = 6
                    max_timestamp_len = 10
                    max_build_count = max(map(lambda x: x.get("build_count", 1), pkginfos_list))
                    bcount_width = max(len(str(max_build_count)), 2)

                def add_sort_flag(sort_by_str):
                    return sort_flag if user_options["sort_by"][0] == sort_by_str else ""

                def get_build_fieldstr():
                    if max_build_count > 1:
                        build_field = (
                            "Build"
                            + " "
                            * (
                                build_len_maxlim
                                + len(f" (+{1:{bcount_width}d} builds)")
                                - len("Build")
                                - len("(similar builds)")
                            )
                            + "(similar builds)"
                        )
                    else:
                        build_field = "Build"
                    return build_field

                number_field = "No."
                name_field = "Name" + add_sort_flag("name/version")
                version_field = "Version" + add_sort_flag("name/version")
                build_field = get_build_fieldstr() + add_sort_flag("build")
                channel_field = "Channel" + add_sort_flag("channel")
                python_version_field = "Python" + add_sort_flag("python_version")
                cuda_version_field = " CUDA " + add_sort_flag("cuda_version")
                size_field = (" " * 3 if max_cuda_len < 6 + 2 else "") + "Size" + add_sort_flag("size")
                timestamp_field = "UTC_Time" + add_sort_flag("timestamp")

                table_padding_width = 1
                f_number_width = (
                    max(len(number_field), len(f"{len(pkginfos_list)}")) if user_options["select_mode"] else 0
                )
                f_version_width = len_to_print(version_field)
                f_build_width = len_to_print(build_field)
                f_channel_width = len_to_print(channel_field)
                f_python_version_width = len_to_print(python_version_field)
                f_cuda_version_width = len_to_print(cuda_version_field)
                f_size_width = len_to_print(size_field)
                f_timestamp_width = len_to_print(timestamp_field)
                if len(pkginfos_list):
                    f_version_width = max(f_version_width, max_version_len)
                    f_channel_width = max(f_channel_width, max_channel_len)
                    f_build_width = max(f_build_width, build_len_maxlim)
                    f_python_version_width = max(f_python_version_width, max_python_version_len)
                    f_cuda_version_width = max(f_cuda_version_width, max_cuda_len)
                    f_size_width = max(f_size_width, max_size_len)
                    f_timestamp_width = max(f_timestamp_width, max_timestamp_len)

                if user_options["ui_mode"] != 3 and len(pkginfos_list):
                    name_len_maxlim = (
                        terminal_width
                        - f_number_width
                        - f_version_width
                        - f_build_width
                        - f_channel_width
                        - f_python_version_width
                        - f_cuda_version_width
                        - f_size_width
                        - f_timestamp_width
                        - table_padding_width * 2 * (9 if user_options["select_mode"] else 8)
                    )
                    while name_len_maxlim < max_name_len:
                        is_display_omitted = True
                        if build_len_maxlim > 9:  # 当name长度不够时，逐渐减小build长度来尽量优先name长度
                            build_len_maxlim -= 1
                            name_len_maxlim += 1
                        else:
                            break
                    build_field = get_build_fieldstr() + add_sort_flag("build")
                    f_build_width = max(len_to_print(build_field), build_len_maxlim)

                    min_name_width = min(15, max_name_len)  # 定义name字段最小宽度
                    if name_len_maxlim < min_name_width:
                        _hidden_fields.append(build_field)
                        name_len_maxlim += f_build_width + table_padding_width * 2
                    if name_len_maxlim < min_name_width:
                        _hidden_fields.append(size_field)
                        name_len_maxlim += f_size_width + table_padding_width * 2
                    if name_len_maxlim < min_name_width:
                        _hidden_fields.append(timestamp_field)
                        name_len_maxlim += f_timestamp_width + table_padding_width * 2
                    name_len_maxlim = max(name_len_maxlim, min_name_width)

                elif len(pkginfos_list):  # user_options["ui_mode"] == 3 且有包时
                    name_len_maxlim = max_name_len
                    build_len_maxlim = build_lengths[-1]

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
                    table_fields.insert(0, number_field)

                hidden_field_indexes = {table_fields.index(field) for field in _hidden_fields}

                if hidden_field_indexes:
                    is_display_omitted = True
                    table_fields = _hidden_columns(table_fields, hidden_field_indexes)
                table = PrettyTable(table_fields)
                if user_options["select_mode"]:
                    table.align[number_field] = "l"
                table.align[name_field] = "l"
                table.align[version_field] = "l"
                table.align[build_field] = "l"
                table.align[channel_field] = "r"
                table.align[python_version_field] = "c"
                table.align[cuda_version_field] = "c"
                table.align[size_field] = "r"
                table.align[timestamp_field] = "r"
                table.padding_width = table_padding_width
                table.border = False

                if len(pkginfos_list) == 0:
                    table.add_row(["-" for _ in range(len(table_fields))])
                    table.align = "c"
                    return table, is_display_omitted

                for i, pkginfo_dict in enumerate(pkginfos_list, 1):
                    python_version = pkginfo_dict["python_version"] or "-"
                    python_version = beautify_version_constraints(python_version)

                    if pkginfo_dict["cuda_version"]:
                        cuda_info = pkginfo_dict["cuda_version"]
                    elif pkginfo_dict["is_cuda"]:
                        cuda_info = "UNSURE"
                    else:
                        cuda_info = ""
                    build_count = pkginfo_dict.get("build_count", 1)
                    if build_count > 1:
                        build_count_str = f" (+{build_count-1:{bcount_width}d} builds)"
                    else:
                        build_count_str = ""
                    build_length = len(pkginfo_dict["build"])
                    if build_length <= build_len_maxlim:
                        build_str = "{:<{build_width}}".format(pkginfo_dict["build"], build_width=build_len_maxlim)
                    else:
                        build_str = "{:<{build_width}}".format(
                            pkginfo_dict["build"][: build_len_maxlim - 6]
                            + LIGHT_YELLOW("...")
                            + pkginfo_dict["build"][-3:],
                            build_width=build_len_maxlim,
                        )
                    build_show_str = build_str + build_count_str
                    if user_options["ui_mode"] != 3 and len(pkginfo_dict["name"]) > name_len_maxlim:
                        name_str = (
                            pkginfo_dict["name"][: name_len_maxlim - 8]
                            + LIGHT_YELLOW("...")
                            + pkginfo_dict["name"][-5:]
                        )
                    else:
                        name_str = pkginfo_dict["name"]
                    if user_options["ui_mode"] != 3 and len(pkginfo_dict["version"]) > ver_len_maxlim:
                        version_str = pkginfo_dict["version"][: ver_len_maxlim - 3] + LIGHT_YELLOW("...")
                    else:
                        version_str = pkginfo_dict["version"]
                    row = [
                        name_str,
                        version_str,
                        build_show_str,
                        pkginfo_dict["channel"],
                        python_version,
                        cuda_info,
                        format_size(pkginfo_dict["size"], B_suffix=False),
                        (
                            time.strftime("%Y-%m-%d", time.gmtime(pkginfo_dict["timestamp"]))
                            if pkginfo_dict["timestamp"]
                            else ""
                        ),
                    ]
                    if user_options["select_mode"]:
                        row.insert(0, f"{i}")
                    if hidden_field_indexes:
                        row = _hidden_columns(row, hidden_field_indexes)
                    table.add_row(row)

                return table, is_display_omitted

            def data_processing_transaction(user_options) -> list[dict[str, Any]]:
                """根据用户选项（user_options）处理相应的包信息列表：

                - pkginfos_list_raw (若 ui_mode == 3)
                - pkginfos_list_iter1 (若 ui_mode == 2)
                - pkginfos_list_iter2 (若 ui_mode == 1 且 merge_version == False)
                - pkginfos_list_iter3 (若 ui_mode == 1 且 merge_version == True)

                并返回处理后的包信息列表交由 _print_transcation 显示。

                Attention:
                    * * * 注意 * * *
                    这是 search_pkgs_main 内的 3 个主事务函数其一，实现 “数据处理事务”。
                """

                def _get_only_one_version(version_str: str, pattern: re.Pattern):
                    if version_str:
                        findall_list = re.findall(pattern, version_str)
                        if findall_list and (index := version_str.find(findall_list[-1])) > 0:
                            op = ""
                            while version_str[index - 1] in ["<", ">", "=", "!"]:
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
                        return version_str
                    return None

                python_versionstr_pattern = re.compile(r"(?:2|3|4)(?:\.[a-zA-Z\d]{1,3})?")

                def parse_one_python_version(version_str: str):
                    one_version = _get_only_one_version(version_str, python_versionstr_pattern)
                    return one_version or "0.0"

                cuda_versionstr_pattern = re.compile(r"\d{1,2}(?:\.[a-zA-Z\d]{1,3})?")

                def get_cuda_versionstr_from_pkgdict(pkginfo_dict: dict[str, Any], filter_to_pure_version=True):
                    if filter_to_pure_version:
                        if one_version := _get_only_one_version(
                            pkginfo_dict["cuda_version"], cuda_versionstr_pattern
                        ):
                            version_str = one_version
                        else:
                            version_str = "UNSURE" if pkginfo_dict["is_cuda"] else ""
                    else:
                        if pkginfo_dict["cuda_version"]:
                            version_str = pkginfo_dict["cuda_version"]
                        else:
                            version_str = "UNSURE" if pkginfo_dict["is_cuda"] else ""

                    return version_str

                def parse_cuda_version(version_str: str):
                    if version_str == "":
                        return version_parse("0.0.0")
                    elif version_str == "UNSURE":
                        return version_parse("0.0.1")
                    else:
                        return version_parse(version_str)

                ui_mode = user_options["ui_mode"]
                sort_by = user_options["sort_by"]
                filters = user_options["filters"]

                if ui_mode == 1 and user_options["merge_version"]:
                    pkginfos_list = pkginfos_list_iter3
                elif ui_mode == 1 and not user_options["merge_version"]:
                    pkginfos_list = pkginfos_list_iter2
                elif ui_mode == 2:
                    pkginfos_list = pkginfos_list_iter1
                else:  # ui_mode == 3
                    pkginfos_list = pkginfos_list_raw
                pkginfos_list = pkginfos_list.copy()

                if ui_mode != 1:
                    for filter_name, filter_value in filters.items():
                        if filter_value:
                            if filter_name == "is_cuda_only":
                                pkginfos_list = [
                                    pkginfo_dict for pkginfo_dict in pkginfos_list if pkginfo_dict["is_cuda"]
                                ]
                            elif filter_name == "version":
                                pkginfos_list = [
                                    pkginfo_dict
                                    for pkginfo_dict in pkginfos_list
                                    if is_version_within_constraints(pkginfo_dict[filter_name], filter_value)
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
                                        if is_version_within_constraints(py_ver_constraint_str, filter_value):
                                            pkginfos_list_processed.append(pkginfo_dict)
                                    else:
                                        pkginfos_list_processed.append(pkginfo_dict)
                                pkginfos_list = pkginfos_list_processed

                            elif filter_name == "cuda_version":
                                pkginfos_list = [
                                    pkginfo_dict
                                    for pkginfo_dict in pkginfos_list
                                    if is_version_within_constraints(
                                        get_cuda_versionstr_from_pkgdict(
                                            pkginfo_dict, filter_to_pure_version=False
                                        ),
                                        filter_value,
                                        always_true_strs=["UNSURE"],
                                        always_false_strs=[""],
                                    )
                                ]
                            else:
                                pattern = re.compile("^" + filter_value.replace("*", ".*") + "$")
                                pkginfos_list = [
                                    pkginfo_dict
                                    for pkginfo_dict in pkginfos_list
                                    if pattern.match(pkginfo_dict[filter_name])
                                ]

                    if sort_by[0] == "name/version":  # 就是按名称/版本排序
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
                            key=lambda x: version_parse(parse_one_python_version(x[sort_by[0]])),
                            reverse=sort_by[1],
                        )
                    elif sort_by[0] == "cuda_version":
                        pkginfos_list.sort(
                            key=lambda x: parse_cuda_version(get_cuda_versionstr_from_pkgdict(x)),
                            reverse=sort_by[1],
                        )
                    elif sort_by[0] == "channel":
                        pkginfos_list.sort(key=lambda x: _sort_by_channel(x[sort_by[0]]), reverse=sort_by[1])

                    elif sort_by[0]:
                        pkginfos_list.sort(
                            key=lambda x: x[sort_by[0]],
                            reverse=sort_by[1],
                        )
                elif ui_mode == 1 and user_options["reversed_display"]:
                    pkginfos_list = pkginfos_list[::-1]

                return pkginfos_list

            def print_transcation(pkginfos_list: list[dict[str, Any]], first_print=False):
                """根据已由 data_processing_transaction 处理的包信息列表，

                调用 _get_pkgs_table 生成 PrettyTable 对象并智能地打印表格到终端。

                Attention:
                    * * * 注意 * * *
                    这是 search_pkgs_main 内的 3 个主事务函数其二，实现 “打印事务”。
                """
                table, is_display_omitted = _get_pkgs_table(pkginfos_list, user_options)
                table_header, table_body = table.get_string().split("\n", 1)
                print(BOLD(table_header))
                print("-" * len_to_print(table_header))
                print(table_body)
                if first_print:
                    print("-" * len_to_print(table_header))
                    print(
                        LIGHT_GREEN(f"搜索完成 ({round(time.time() - t0_search, 2)} s)！"),
                        f"对于 {LIGHT_CYAN(search_pkg_info)}，共找到 {LIGHT_CYAN(len(pkginfos_list_raw))} 个相关包，搜索结果如上",
                    )
                if is_display_omitted:
                    prompt_str = DIM(" * 请增加终端宽度以显示更多内容 * ")
                    prompt_width = len_to_print(prompt_str)
                    hyphens_half_width = (len_to_print(table_header) - prompt_width) // 2
                    print("-" * hyphens_half_width, end="")
                    print(prompt_str, end="")
                    print("-" * (len_to_print(table_header) - prompt_width - hyphens_half_width))
                else:
                    print("-" * len_to_print(table_header))

            def _BOLD_keyboard_keys(print_str: str):
                return re.sub(
                    r"((?:\x1b\[\d+m)?)(\[\w{1,5}\])",
                    r"\1" + BOLD(r"\2") + r"\1",
                    print_str,
                )

            def get_user_options(user_options, pkginfos_list: list[dict[str, Any]]) -> int:
                """根据现有的用户选项和处理后的包信息列表：
                    1. 打印用户选项菜单
                    2. 获取用户输入
                        2.1 显示一些信息
                        2.2 更新用户选项
                    3. 返回已打印到终端的实际行数 num_lines

                Attention:
                    * * * 注意 * * *
                    这是search_pkgs_main内的3个主事务函数其三，实现 “人机交互事务”。

                """

                def count_and_print(s: str) -> int:
                    print(s)
                    return get_printed_line_count(s)

                user_options["need_reprint"] = True

                num_lines = 0

                filters = user_options["filters"]
                sort_by = user_options["sort_by"]

                is_filtered = any(filter_value for filter_value in filters.values())

                if user_options["select_mode"]:
                    if user_options["ui_mode"] != 1:
                        while user_options["select_mode"]:
                            num_lines_to_prompt = count_and_print(
                                f"(i) 请输入要查看详细信息的包对应编号（带{LIGHT_CYAN('@')}号则显示安装命令行并拷贝到剪贴板）："
                            )
                            key = input_strip(">>> ")
                            num_lines += num_lines_to_prompt + 1
                            if key == "":
                                user_options["select_mode"] = False
                                return num_lines
                            elif key.isdigit() and 1 <= int(key) <= len(pkginfos_list):
                                clear_lines_above(num_lines)
                                num_lines = 0
                                pkginfo_dict = pkginfos_list[int(key) - 1].copy()
                                pkginfo_dict["size"] = format_size(pkginfo_dict["size"])
                                pkginfo_dict["timestamp"] = (
                                    time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(pkginfo_dict["timestamp"]))
                                    if pkginfo_dict["timestamp"]
                                    else ""
                                )
                                prompt_str = f" [{key}]包{LIGHT_CYAN(pkginfo_dict['name'])} {LIGHT_GREEN(pkginfo_dict['version'])}的详细信息如下 "
                                print_str = (
                                    "="
                                    * min(35, (fast_get_terminal_size().columns - len_to_print(prompt_str)) // 2)
                                    + prompt_str
                                    + "="
                                    * min(35, (fast_get_terminal_size().columns - len_to_print(prompt_str)) // 2)
                                )
                                num_lines += count_and_print(print_str)
                                pkginfo_dict_copy = pkginfo_dict.copy()
                                pkginfo_dict_copy.pop("build_count", None)
                                pkginfo_dict_copy.pop("build_prefix", None)
                                pkginfo_dict_copy.pop("build_string", None)
                                pkginfo_dict_copy.pop("python_version", None)
                                pkginfo_dict_copy.pop("cuda_version", None)
                                pkginfo_dict_copy.pop("is_cuda", None)
                                if not pkginfo_dict_copy.get("track_features"):
                                    pkginfo_dict_copy.pop("track_features", None)
                                if not pkginfo_dict_copy.get("constrains"):
                                    pkginfo_dict_copy.pop("constrains", None)
                                print_str = json.dumps(pkginfo_dict_copy, indent=4, skipkeys=True)
                                num_lines += count_and_print(print_str)
                            elif (
                                key.startswith("@")
                                and (key := key.replace("@", "")).isdigit()
                                and 1 <= int(key) <= len(pkginfos_list)
                            ):
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
                                num_lines += count_and_print(print_str)
                                if os.name == "nt":
                                    command = ["clip"]
                                else:  # os.name == "posix"
                                    command = ["xclip", "-selection", "clipboard"]
                                if subprocess.run(command, input=print_str, text=True).returncode == 0:
                                    num_lines += count_and_print(LIGHT_GREEN("[提示] 安装命令已拷贝到剪贴板！"))
                            else:
                                clear_lines_above(num_lines_to_prompt + 1)
                                num_lines -= num_lines_to_prompt + 1
                    else:  # ui_mode == 1
                        num_lines += count_and_print("(i) 请输入要跳转到原始显示模式并过滤的包版本对应编号：")
                        key = input_strip(">>> ")
                        num_lines += 1
                        if key.isdigit() and 1 <= int(key) <= len(pkginfos_list):
                            pkginfo_dict = pkginfos_list[int(key) - 1].copy()
                            filters["name"] = pkginfo_dict["name"]
                            if not user_options["merge_version"]:
                                filters["version"] = pkginfo_dict["version"]
                            filters["channel"] = pkginfo_dict["channel"]
                            user_options["ui_mode"] = 3
                            user_options["select_mode"] = False
                            return num_lines
                        else:
                            user_options["select_mode"] = False
                            clear_lines_above(num_lines)
                            num_lines = 0

                if user_options["ui_mode"] == 1:
                    print_str = LIGHT_CYAN("[1] 概览") + "\t" + "[2] 精简显示" + "\t" + "[3] 原始显示"
                elif user_options["ui_mode"] == 2:
                    print_str = "[1] 概览" + "\t" + LIGHT_CYAN("[2] 精简显示") + "\t" + "[3] 原始显示"
                else:  # ui_mode == 3
                    print_str = "[1] 概览" + "\t" + "[2] 精简显示" + "\t" + LIGHT_CYAN("[3] 原始显示")
                print_str += "\t"
                if user_options["ui_mode"] != 1:
                    if is_filtered:
                        print_str += LIGHT_GREEN("[F] 过滤器")
                    else:
                        print_str += "[F] 过滤器"
                    print_str += "\t"
                    if sort_by[0]:
                        print_str += LIGHT_GREEN("[S] 排序")
                    else:
                        print_str += "[S] 排序"
                    print_str += "\t"
                    print_str += "[V] 查看包详情"
                else:
                    print_str += "[V] 选择以过滤原始显示"
                    print_str += "\t"
                    if user_options["merge_version"]:
                        print_str += LIGHT_GREEN("[M] 合并版本号")
                    else:
                        print_str += "[M] 合并版本号"
                    print_str += "\t"
                    if user_options["reversed_display"]:
                        print_str += LIGHT_CYAN("[R] 倒序显示")
                    else:
                        print_str += "[R] 倒序显示"
                print_str += "\t" + LIGHT_YELLOW("[Esc] 退出")
                print_str = _BOLD_keyboard_keys(print_str)
                num_lines += count_and_print(print_str)

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
                    print_str += LIGHT_GREEN(f'{sort_by[0]}{("▼" if sort_by[1] else "▲")}')
                    print_str += "  (按↑ |↓ 键切换为升序|降序)"
                if filter_enable_list:
                    if sort_by[0]:
                        print_str += "  ;  [过滤器] "
                    else:
                        print_str = " " * 8 + "[过滤器] "
                    for i, (filter_name, filter_value) in enumerate(filter_enable_list):
                        if i:
                            print_str += ", "
                        print_str += f"{LIGHT_CYAN(filter_name)}({LIGHT_GREEN(filter_value)})"
                if sort_by[0] or filter_enable_list:
                    num_lines += count_and_print(print_str)

                key = get_char()

                if key == "1":
                    user_options["ui_mode"] = 1
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
                    user_options["ui_mode"] = int(key)
                elif key in ("S", "s") and user_options["ui_mode"] != 1:
                    if sort_by[0]:
                        sort_by[0] = ""
                    else:
                        clear_lines_above(num_lines)
                        num_lines = 0
                        num_lines += count_and_print("(i) 请按下排序依据对应的序号：")
                        # (名称/版本/Channel/Python版本/大小/时间戳)
                        print_strs = [
                            (LIGHT_GREEN("[1] 名称/版本") if sort_by[0] == "name/version" else "[1] 名称/版本"),
                            (LIGHT_GREEN("[2] Channel") if sort_by[0] == "channel" else "[2] Channel"),
                            (
                                LIGHT_GREEN("[3] Python版本")
                                if sort_by[0] == "python_version"
                                else "[3] Python版本"
                            ),
                            (LIGHT_GREEN("[4] CUDA版本") if sort_by[0] == "cuda_version" else "[4] CUDA版本"),
                            LIGHT_GREEN("[5] 大小") if sort_by[0] == "size" else "[5] 大小",
                            (LIGHT_GREEN("[6] 时间戳") if sort_by[0] == "timestamp" else "[6] 时间戳"),
                        ]
                        print_str = _BOLD_keyboard_keys("\t".join(print_strs))
                        num_lines += count_and_print(print_str)

                        key1 = get_char()
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
                elif key in ("\x1b[A", "\x1b[B", "àH", "àP") and sort_by[0] and user_options["ui_mode"] != 1:
                    if key in ("\x1b[A", "àH") and sort_by[1]:
                        sort_by[1] = False
                    elif key in ("\x1b[B", "àP") and not sort_by[1]:
                        sort_by[1] = True
                    else:
                        user_options["need_reprint"] = False

                elif key in ("F", "f") and user_options["ui_mode"] != 1:
                    clear_lines_above(num_lines)
                    num_lines = 0
                    num_lines += count_and_print("(i) 请按下过滤目标对应的序号：")
                    print_strs = [
                        LIGHT_GREEN("[1] 名称") if filters["name"] else "[1] 名称",
                        LIGHT_GREEN("[2] 版本") if filters["version"] else "[2] 版本",
                        LIGHT_GREEN("[3] Channel") if filters["channel"] else "[3] Channel",
                        (LIGHT_GREEN("[4] Python版本") if filters["python_version"] else "[4] Python版本"),
                        (LIGHT_GREEN("[5] CUDA版本") if filters["cuda_version"] else "[5] CUDA版本"),
                        (LIGHT_GREEN("[6] 只显示CUDA") if filters["is_cuda_only"] else "[6] 只显示CUDA"),
                    ]
                    print_str = _BOLD_keyboard_keys("\t".join(print_strs))
                    num_lines += count_and_print(print_str)
                    key1 = get_char()
                    if key1 == "1":
                        if filters["name"]:
                            filters["name"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += count_and_print("(ii) 请输入名称过滤器（支持通配符*）：")
                            filters["name"] = input_strip(">>> ")
                            num_lines += 1
                    elif key1 == "2":
                        if filters["version"]:
                            filters["version"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += count_and_print(
                                "(ii) 请输入版本过滤器（支持比较式 [示例: 1.19|<2|>=2.6,<2.10.0a0,!=2.9.*]）："
                            )
                            filters["version"] = input_strip(">>> ")
                            num_lines += 1
                    elif key1 == "3":
                        if filters["channel"]:
                            filters["channel"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += count_and_print("(ii) 请输入 Channel 过滤器（支持通配符*）：")
                            filters["channel"] = input_strip(">>> ")
                            num_lines += 1
                    elif key1 == "4":
                        if filters["python_version"]:
                            filters["python_version"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += count_and_print(
                                "(ii) 请输入 Python 版本过滤器（支持主次版本号比较式 [示例: >=3.11|3.7|!=2.*,<3.10a0,!=3.8]）："
                            )
                            filters["python_version"] = input_strip(">>> ")
                            num_lines += 1
                    elif key1 == "5":
                        if filters["cuda_version"]:
                            filters["cuda_version"] = None
                            filters["is_cuda_only"] = False
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += count_and_print(
                                "(ii) 请输入 CUDA 版本过滤器（支持主次版本号比较式 [示例: !=12.2,<=12.3|>=9,<13.0a0,!=10.*]）："
                            )
                            filters["cuda_version"] = input_strip(">>> ")
                            filters["is_cuda_only"] = True
                            num_lines += 1
                    elif key1 == "6":
                        filters["is_cuda_only"] = not filters["is_cuda_only"]
                elif key == "V" or key == "v":
                    user_options["select_mode"] = True
                elif key == "M" or key == "m" and user_options["ui_mode"] == 1:
                    user_options["merge_version"] = not user_options["merge_version"]
                elif key == "R" or key == "r" and user_options["ui_mode"] == 1:
                    user_options["reversed_display"] = not user_options["reversed_display"]
                elif key == "\x1b" or key == "\x03":
                    user_options["exit"] = True
                else:
                    user_options["need_reprint"] = False

                return num_lines

            user_options = {
                # 显示模式(按键[1],[2],[3]) 1对应pkginfos_list_iter2，2对应pkginfos_list_iter1，3对应pkginfos_list_raw
                "ui_mode": 1,
                "sort_by": ["", True],  # 排序依据，按键[S]
                "filters": {  # 过滤器字典，按键[F]
                    "name": None,  # 名称过滤器，取值为字符串或None
                    "version": None,  # 版本过滤器，取值为字符串或None
                    "channel": None,  # Channel过滤器，取值为字符串或None
                    "python_version": None,  # Python 版本过滤器，取值为字符串或None
                    "cuda_version": None,  # CUDA 版本过滤器，取值为字符串或None
                    "is_cuda_only": False,  # 是否 CUDA 过滤器，取值为布尔值
                },
                "select_mode": False,  # 是否进入选择模式，按键[V]
                "merge_version": False,  # 是否合并版本号相同的包，dipslay_mode为1时有效
                "reversed_display": False,  # 倒序显示，ui_mode为1时有效
                "exit": False,  # 退出标志，按键Esc或Ctrl+C为其赋值
                "need_reprint": True,
            }

            def extract_major_minor_only(version_str: str):
                """过滤版本字符串，仅保留主版本号和次版本号。"""
                pattern = re.compile(r"([\d*]{1,3})\.([\d*]{1,3})(?:\.[a-zA-Z\d.*]+)*")
                return pattern.sub(format_major_minor, version_str)

            # ----- * 搜索功能之展示 Conda 包表格的主事件循环 * -----
            clear_screen(CFG_FULL_TERMINAL_CLEAR)
            pkginfos_list = data_processing_transaction(user_options)
            print_transcation(pkginfos_list, first_print=True)
            num_lines_2 = get_user_options(user_options, pkginfos_list)
            while not user_options["exit"]:
                if filter_value := user_options["filters"]["python_version"]:
                    user_options["filters"]["python_version"] = extract_major_minor_only(filter_value)
                if filter_value := user_options["filters"]["cuda_version"]:
                    user_options["filters"]["cuda_version"] = extract_major_minor_only(filter_value)
                if user_options["need_reprint"]:
                    clear_screen(CFG_FULL_TERMINAL_CLEAR)
                    pkginfos_list = data_processing_transaction(user_options)
                    print_transcation(pkginfos_list)
                else:
                    clear_lines_above(num_lines_2)
                    pkginfos_list = []
                num_lines_2 = get_user_options(user_options, pkginfos_list)

        while True:
            search_pkgs_main(target_py_version)
            print()
            if target_py_version:
                print(f"(i) 是否继续为 Python {target_py_version} 查找包? ")
            else:
                print("(i) 是否继续为所有 Python 版本查找包? ")
            inp = input_strip("[(Y)/n] >>> ")
            if not ResponseChecker(inp, default="yes").is_yes():
                break

    # 如果按下的是[H]，则显示由"conda doctor"命令出具的Conda环境健康报告
    elif inp.upper() == "H":
        if not CONDA_VERSION or Version(CONDA_VERSION) < Version("23.5.0"):
            print(LIGHT_YELLOW("[警告] conda doctor 子命令需要 23.5 及以上版本支持，请在 base 环境升级后重试！"))
            print(" * 升级 conda 命令: conda update -n base -c defaults conda")
        print(f"(1) 请输入想要{BOLD(LIGHT_GREEN('检查完整性'))}的环境的编号（默认为全部），多个以空格隔开：")
        inp = input_strip(f"[(ALL) | 1-{env_num}] >>> ")
        if inp.lower() in ["all", ""]:
            env_check_names = [i for i in env_namelist]
        else:
            env_check_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
            env_check_names = [env_namelist[i] for i in env_check_nums]
        if os.name == "nt":  # 因为win下运行conda doctor时任何方式捕获输出，都会有未知编码错误，这是conda自身的bug
            print("-" * (fast_get_terminal_size().columns - 5))
            for i, name in enumerate(env_check_names, 1):
                print(f"[{i}/{len(env_check_names)}] 正在检查环境 {LIGHT_CYAN(name)} 的健康情况...")
                print(DIM(f"{' * Conda Doctor * ':-^{fast_get_terminal_size().columns - 5}}"))
                command = get_cmd([f'conda doctor -n "{name}"'])
                subprocess.run(command, shell=True)
                command = get_cmd([f'conda activate "{name}"', "pip check"])
                print(DIM(f"{' * Pip Check * ':-^{fast_get_terminal_size().columns - 5}}"))
                subprocess.run(command, shell=True)
                print("-" * (fast_get_terminal_size().columns - 5))
        else:

            async def check_environment_health(name: str):
                try:
                    command1 = get_cmd([f'conda doctor -n "{name}"'])
                    proc1 = await asyncio.create_subprocess_shell(
                        command1,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                    )
                    command2 = get_cmd([f'conda activate "{name}"', "pip check"])
                    proc2 = await asyncio.create_subprocess_shell(
                        command2,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                    )
                    conda_res, _ = await proc1.communicate()
                    pip_res, _ = await proc2.communicate()
                    return conda_res.decode("utf-8"), pip_res.decode("utf-8")
                except Exception as e:
                    return RED(str(e)), RED(str(e))

            async def async_check_main():
                tasks = []
                for name in env_check_names:
                    tasks.append(asyncio.create_task(check_environment_health(name), name=name))

                print("-" * (fast_get_terminal_size().columns - 5))
                for i, task in enumerate(tasks, 1):
                    print(f"[{i}/{len(env_check_names)}] 正在检查环境 {LIGHT_CYAN(task.get_name())} 的健康情况...")
                    conda_doctor_res, pip_check_res = await task
                    print(DIM(f"{' * Conda Doctor * ':-^{fast_get_terminal_size().columns - 5}}"))
                    print(conda_doctor_res)
                    print(DIM(f"{' * Pip Check * ':-^{fast_get_terminal_size().columns - 5}}"))
                    print(pip_check_res)
                    print("-" * (fast_get_terminal_size().columns - 5))

            asyncio.run(async_check_main())

        input_strip(f"{LIGHT_GREEN('[完成]')} 检查完毕，请按<回车键>继续...")

    # 如果按下的是[D]，则计算所有环境的大小及真实磁盘占有量
    elif inp.upper() == "D":
        global env_size_recalc_force_enable
        env_size_recalc_force_enable = True
        clear_screen(hard=CFG_FULL_TERMINAL_CLEAR)

    # 如果输入的是[=编号]，则浏览环境主目录
    elif inp.find("@") != -1:
        inp = int(inp[1:])
        name = env_namelist[inp - 1]
        print(LIGHT_GREEN(f"[提示] 已在文件资源管理器中打开环境 {LIGHT_CYAN(name)} 的主目录："))
        env_path = env_pathlist[inp - 1]
        print(env_path)
        if os.name == "nt":
            subprocess.run(["explorer", env_path])
        else:
            subprocess.run(["xdg-open", env_path])

    # 如果按下的是[Q]，则退出
    elif inp.upper() == "Q":
        action_status = 0

    # 如果输入的是数字[编号]，则激活对应的环境，然后进入命令行
    else:
        action_status = 0
        name = env_namelist[int(inp) - 1]
        if os.name == "nt":
            conda_hook_path = os.path.join(CONDA_HOME, "shell", "condabin", "conda-hook.ps1")
            command = [
                "powershell",
                "-ExecutionPolicy",
                "ByPass",
                "-NoExit",
                "-Command",
                f'& "{conda_hook_path}" ; conda activate "{name}"',
            ]
        else:
            cmd_str = get_linux_activation_shell_cmd() + f" && conda activate '{name}'"
            command = ["bash", "-c", f'bash --init-file <(echo ". $HOME/.bashrc; {cmd_str}")']

        os.environ["PYTHONNOUSERSITE"] = "True"  # 防止用户site-packages影响环境
        subprocess.run(command)


def main(workdir):
    os.chdir(workdir)
    while action_status:
        env_infolist_dict = get_env_infos()
        inp = show_info_and_get_input(env_infolist_dict)
        print()
        try:
            do_action(inp, env_infolist_dict)
        except KeyboardInterrupt:  # 捕获Ctrl+C中断信号,自定义其功能为中断当前事务，重启主循环
            if action_status:
                cancel_msg = " * CANCLED BY USER * "
                half_width = (fast_get_terminal_size().columns - len(cancel_msg)) // 2
                print("\n" + DIM(LIGHT_YELLOW(">" * half_width + cancel_msg + "<" * half_width)))
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Conda/Mamba 发行版环境管理工具 v{PROGRAM_VERSION}")
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
        help="Conda/Mamba 发行版的安装路径，如 C:\\Users\\USER_NAME\\miniforge3, /home/USER_NAME/miniconda3",
    )
    group.add_argument(
        "-n",
        "-N",
        "--distribution-name",
        type=str,
        required=False,
        help="发行版的名称，支持miniforge3, anaconda3, miniconda3, mambaforge, miniforge-pypy3, mambaforge-pypy3，默认顺序如前",
    )
    parser.add_argument(
        "--detect-distribution",
        action="store_true",
        help="探测并列出计算机中所有受支持的 Conda/Mamba 发行版",
    )
    parser.add_argument(
        "--delete-data-files",
        action="store_true",
        help=f"删除程序数据文件夹 ({LIGHT_CYAN(data_manager.program_data_home)})",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="仅打印 Conda 环境信息，不进入交互界面",
    )
    args = parser.parse_args()
    if args.delete_data_files:
        if os.path.exists(data_manager.program_data_home):
            rmtree(data_manager.program_data_home)
            print(LIGHT_GREEN(f"[提示] 程序数据文件夹 ({LIGHT_CYAN(data_manager.program_data_home)}) 已删除！"))
        else:
            print(LIGHT_YELLOW("[错误] 程序数据文件夹不存在！"))
        sys.exit(0)
    if args.detect_distribution:
        print("计算机中所有受支持的 Conda/Mamba 发行版如下：")
        available_conda_homes = get_conda_homes(detect_mode=True)
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
        for i in range(len(available_conda_homes)):
            table.add_row(
                [
                    i + 1,
                    os.path.split(available_conda_homes[i])[1],
                    "*" if i == 0 else "",
                    available_conda_homes[i],
                    (
                        LIGHT_GREEN(detect_conda_mamba_infos(available_conda_homes[i])[-1])
                        if detect_conda_mamba_infos(available_conda_homes[i])[-1]
                        else LIGHT_RED("NO")
                    ),
                    (
                        LIGHT_GREEN(detect_conda_mamba_infos(available_conda_homes[i])[2])
                        if detect_conda_mamba_infos(available_conda_homes[i])[2]
                        else LIGHT_RED("NOT supported".upper())
                    ),
                    (
                        LIGHT_GREEN(detect_conda_mamba_infos(available_conda_homes[i])[3])
                        if detect_conda_mamba_infos(available_conda_homes[i])[3]
                        else "-"
                    ),
                ]
            )
        table.align = "l"
        table.border = False
        print(three_line_table(table))
        sys.exit(0)
    if args.prefix is not None:
        if is_valid_env(args.prefix):
            CONDA_HOME = os.path.realpath(args.prefix)
            CONDA_EXE_PATH, IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = (
                detect_conda_mamba_infos(CONDA_HOME)
            )
        else:
            print(YELLOW(f'[提示] 未在指定路径"{args.prefix}"检测到对应发行版，将使用默认发行版'))
    elif args.distribution_name is not None:
        CONDA_HOME, CONDA_EXE_PATH, IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = (
            detect_conda_installation(args.distribution_name)
        )
        if os.path.split(CONDA_HOME)[1].lower() != args.distribution_name.lower():
            print(YELLOW(f"[提示] 未检测到指定的发行版 ({args.distribution_name})，将使用默认发行版"))
    if args.print_only:
        env_size_recalc_force_enable = True
        main_display_mode = 3
        env_infolist_dict = get_env_infos()
        table = get_envs_prettytable(env_infolist_dict)
        table_rstrip_width = len_to_print(table.get_string().splitlines()[0].rstrip())
        _print_header(table_rstrip_width, env_infolist_dict)
        _print_envs_table(table, env_infolist_dict)
        sys.exit(0)

    workdir = args.workdir if args.workdir is not None else USER_HOME
    if os.path.isdir(workdir):
        if CONDA_HOME == "error":
            if os.name == "nt":
                print("请输入 Conda/Mamba 发行版的安装路径，如 C:\\Users\\USER_NAME\\anaconda3: ")
            else:
                print("请输入 Conda/Mamba 发行版的安装路径，如 /home/USER_NAME/anaconda3: ")
            conda_prefix = input_strip(">>> ")
            if is_valid_env(conda_prefix):
                CONDA_HOME = os.path.realpath(conda_prefix)
                CONDA_EXE_PATH, IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = (
                    detect_conda_mamba_infos(CONDA_HOME)
                )
            else:
                sys.exit(1)
        main(workdir)
    else:
        raise ValueError(LIGHT_RED("[错误] 传入的参数不是一个目录！"))
