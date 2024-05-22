# This code is authored by azhan.

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
from typing import Literal, Union
from prettytable import PrettyTable
from ColorStr import *
from MyTools import *

if os.name == "posix":
    import readline  # 使Linux下的input()函数支持上下左右键

PROGRAME_NAME = "Conda-Environment-Manager"
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


class ProgramDataManager:
    """用于管理程序数据的类"""

    if os.name == "nt":
        localappdata_home = os.environ.get("LOCALAPPDATA", os.path.join(USER_HOME, "AppData", "Local"))
    else:  # os.name == "posix":
        localappdata_home = os.environ.get("XDG_DATA_HOME", os.path.join(USER_HOME, ".local", "share"))
    if os.path.exists(localappdata_home):
        program_data_home = os.path.join(localappdata_home, PROGRAME_NAME)
    else:
        program_data_home = os.path.join(USER_HOME, "." + PROGRAME_NAME.lower())
    data_file = os.path.join(program_data_home, "data.json")

    def __init__(self):
        self._all_data = self._load_data()
        self.env_info_data = self._all_data.get(CONDA_HOME, {})

    def _load_data(self):
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            os.remove(self.data_file)
            return {}
        except:
            return {}

    def _write_data(self):
        self._all_data[CONDA_HOME] = self.env_info_data
        if not os.path.exists(self.program_data_home):
            os.mkdir(self.program_data_home)
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self._all_data, f)

    def get_data(self, key) -> dict:
        """
        key: str, 形如*_data，描述一个数据的字典
        return: 仅返回字典格式的data，若key不存在则返回空字典
        """
        return self.env_info_data.get(key, {})

    def update_data(self, key, value: dict):
        """value: dict, 更新的单个data数据的字典"""
        self.env_info_data[key] = value
        self._write_data()


def filter_and_sort_sources_by_priority(
    sources: Union[list[str], set[str], tuple[str]], keep_url=False, enable_default_src=True
) -> list[str]:
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
        error_msg_func = lambda input_str: f"输入错误{LIGHT_RED(error_count)}次，请重新输入: "
    inp = input_strip(prompt)
    while not condition_func(inp):
        error_count += 1
        if error_count == 1:
            clear_lines_above(prompt.count("\n") + 1)
        else:
            clear_lines_above(prompt.count("\n") + 1 + error_msg_func(inp).count("\n") + 1)
        print(error_msg_func(inp))
        if error_count > max_errors:
            print(f"输入错误达到最大次数({LIGHT_RED(max_errors)})，程序退出")
            sys.exit(1)
        inp = input_strip(prompt)
    if error_count > 0:
        clear_lines_above(prompt.count("\n") + 1 + error_msg_func(inp).count("\n") + 1)
        print(prompt + inp)
    return inp


def get_pyvers_from_paths(pypathlist: list[str]) -> list[str | None]:
    """通过python路径list获取python版本号list，并支持异步并行获取"""
    sem = asyncio.Semaphore(5)
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

    async def get_pyver(pypath):
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
                for i in glob_res:
                    if match := re.search(r"python-(\d\.\d{1,2}\.\d{1,2})", i):
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
    """获取受支持的conda发行版的安装路径列表，默认仅返回第1个找到项，若detect_mode为True则返回所有找到项。"""
    available_conda_homes = []
    if os.name == "nt":
        # 获取ProgramData路径
        progradata_path = os.environ["ProgramData"]
        for i in allowed_release_names:
            if i == "CONDA_PREFIX" and "CONDA_PREFIX" in os.environ:
                available_conda_homes.append(os.environ["CONDA_PREFIX"])
                if not detect_mode:
                    break
            elif os.path.exists(os.path.join(USER_HOME, i, "conda-meta")):
                available_conda_homes.append(os.path.join(USER_HOME, i))
                if not detect_mode:
                    break
            elif os.path.exists(os.path.join(progradata_path, i, "conda-meta")):
                available_conda_homes.append(os.path.join(progradata_path, i))
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
                                        available_conda_homes.append(arguments.split()[-1])
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
                                            available_conda_homes.append(arguments.split()[-1])
                                            is_find = True
                                            if not detect_mode:
                                                break
                                if is_find and not detect_mode:
                                    break
    else:
        for i in allowed_release_names:
            if i == "CONDA_PREFIX" and "CONDA_PREFIX" in os.environ:
                available_conda_homes.append(os.environ["CONDA_PREFIX"])
                if not detect_mode:
                    break
            elif os.path.exists(os.path.join(USER_HOME, i, "conda-meta")):
                available_conda_homes.append(os.path.join(USER_HOME, i))
                if not detect_mode:
                    break
            elif os.path.exists(os.path.join("root", i, "conda-meta")):
                available_conda_homes.append(os.path.join("root", i))
                if not detect_mode:
                    break

    if len(available_conda_homes) > 1:
        available_conda_homes_raw = available_conda_homes.copy()
        available_conda_homes = list(set(available_conda_homes_raw))
        available_conda_homes.sort(key=available_conda_homes_raw.index)

    return available_conda_homes


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


def should_show_other_envs(other_envs: list[str]):
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
    global allowed_release_names
    if prior_release_name != "" and prior_release_name in allowed_release_names:
        allowed_release_names.insert(0, prior_release_name)

    available_conda_homes = get_conda_homes()
    # 判断是否安装了Conda/Mamba
    if len(available_conda_homes) == 0:
        print(LIGHT_RED("[错误] 未检测到Conda/Mamba发行版的安装，请先安装相关发行版后再运行此脚本！"))
        return "error", False, None, None, None
    else:
        conda_home = available_conda_homes[0]

    is_mamba, mamba_version, libmamba_solver_version, conda_version = detect_conda_mamba_infos(conda_home)
    return conda_home, is_mamba, mamba_version, libmamba_solver_version, conda_version


CONDA_HOME, IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = detect_conda_installation()
CONDA_EXE_PATH = (
    os.path.join(CONDA_HOME, "Scripts", "conda.exe")
    if os.name == "nt"
    else os.path.join(CONDA_HOME, "bin", "conda")
)

data_manager = ProgramDataManager()


def detect_conda_libmamba_solver_enabled():
    """检测是否启用了libmamba求解器"""
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


def get_cmd(cmdlist: list):
    if not IS_MAMBA:
        cmdlist = [i.replace("mamba", "conda", 1) if i.startswith("mamba") else i for i in cmdlist]

    if os.name == "nt":
        cmd = f'"{os.path.join(CONDA_HOME,"Scripts","activate.bat")}"'
        for i in cmdlist:
            cmd += f" && {i}"
        if not "".join(cmdlist).isascii():
            output = subprocess.run("chcp", capture_output=True, shell=True, text=True).stdout
            now_codepage = re.search(r"\d+", output).group(0)  # type: ignore
            echo_lines = f"({'&'.join(['echo.']*30)})"  # Only work for Windows Terminal
            cmd = f"{echo_lines} && chcp 65001 && " + cmd + f" && {echo_lines} && chcp {now_codepage}"

    else:
        LINUX_ACTIVATION_CMD = get_linux_activation_shell_cmd()
        cmd = LINUX_ACTIVATION_CMD + " && conda activate"
        for i in cmdlist:
            cmd += f" && {i}"

    return cmd


def _get_envpath_last_modified_time(name: str, path: str, pyver: str):
    """获取环境的最后修改时间(conda , pip)，用于判断是否需要重新计算环境大小"""
    conda_meta_path = os.path.join(path, "conda-meta")
    if os.name == "nt":
        site_packages_path = os.path.join(path, "Lib", "site-packages")
    else:  # os.name == "posix":
        site_packages_path = os.path.join(path, "lib", f"python{'.'.join(pyver.split('.')[:2])}", "site-packages")
    if name == "base":
        pkgs_path = os.path.join(path, "pkgs")
        pkgs_mtime = os.path.getmtime(pkgs_path) if os.path.exists(pkgs_path) else 0
    else:
        pkgs_mtime = os.path.getmtime(path) if os.path.exists(path) else 0

    conda_meta_mtime = os.path.getmtime(conda_meta_path) if os.path.exists(conda_meta_path) else 0
    site_packages_mtime = os.path.getmtime(site_packages_path) if os.path.exists(site_packages_path) else 0
    return max(pkgs_mtime, conda_meta_mtime), site_packages_mtime


def _get_env_totalsize_list(pathlist: list[str]):
    sem = asyncio.Semaphore(8)

    async def get_folder_size_with_semaphore(path):
        async with sem:
            return await asyncio.to_thread(get_folder_size, path)

    async def get_sizes_async():
        tasks = [get_folder_size_with_semaphore(path) for path in pathlist]
        return await asyncio.gather(*tasks)

    return asyncio.run(get_sizes_async())


def _get_envsizes_linux(pathlist):
    disk_usage = 0
    real_usage_list = [0] * len(pathlist)

    dirs = []
    for direntry in os.scandir(CONDA_HOME):
        if direntry.is_dir() and direntry.name != "envs":
            dirs.append(direntry.path)
        elif direntry.is_file():
            disk_usage += direntry.stat().st_size
    for direntry in os.scandir(os.path.join(CONDA_HOME, "envs")):
        if direntry.is_dir():
            dirs.append(direntry.path)
        elif direntry.is_file():
            disk_usage += direntry.stat().st_size

    command = ["du", "-cd", "0", *dirs]
    du_result = subprocess.run(command, capture_output=True, text=True).stdout
    lines = du_result.splitlines()
    disk_usage = int(lines[-1].strip().split("\t")[0]) * 1024

    conda_envs_path = os.path.join(CONDA_HOME, "envs")
    for line in lines[:-1]:
        size, path = line.strip().split("\t")
        size = int(size) * 1024

        if path.startswith(conda_envs_path):
            if path in pathlist:
                real_usage_list[pathlist.index(path)] = size

    base_index = pathlist.index(CONDA_HOME)
    real_usage_list[base_index] = disk_usage - sum(real_usage_list)

    total_size_list = _get_env_totalsize_list(pathlist[:base_index] + pathlist[base_index + 1 :])
    total_size_list.insert(base_index, real_usage_list[base_index])

    return real_usage_list, total_size_list, disk_usage


ENV_SIZE_CALC_ENABLED_WIN = False
ENV_SIZE_NEED_RECALC_WIN = False


def _get_envsizes_windows(pathlist):
    global ENV_SIZE_CALC_ENABLED_WIN, ENV_SIZE_NEED_RECALC_WIN
    if not ENV_SIZE_CALC_ENABLED_WIN:
        ENV_SIZE_NEED_RECALC_WIN = True
        return [0] * len(pathlist), [0] * len(pathlist), 0

    from threading import Event, Lock, Thread
    from concurrent.futures import ThreadPoolExecutor

    class ProgressBar(Thread):
        """进度条线程类，用于Windows下显示计算conda环境磁盘占用大小的进度信息。"""

        def __init__(self, num_files: Union[None, int] = None):
            super().__init__(daemon=True)
            self.is_running = Event()
            self.is_running.clear()  # 默认处于非运行状态
            self.lock = Lock()
            self.num_files = num_files
            self.bar_length = 10

        def run(self):
            print()
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
            self._show_process()

        def _show_process(self):
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

            size_str = " - Apparent Size: " + print_fsize_smart(self.size)

            num_files_str = " - Files: " + f"{self.count:,}"

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

            clear_lines_above(1)
            print(bar + size_str + num_files_str + " " + extra_info, flush=True)

    ENV_SIZE_CALC_ENABLED_WIN = False
    ENV_SIZE_NEED_RECALC_WIN = False

    num_files = 0
    real_usage_list = [0] * len(pathlist)
    total_size_list = [0] * len(pathlist)
    path_corresponding_index = {path: idx for idx, path in enumerate(pathlist)}
    seen_inodes = set()
    walker = os.walk(CONDA_HOME, followlinks=True)  # followlinks=True为了避免islink()判断，提高速度
    root, dirs, nondirs = next(walker)
    dirs.append(dirs.pop(dirs.index("envs")))

    lock = Lock()
    conda_envs_path = os.path.join(CONDA_HOME, "envs")
    cluster_size = get_cluster_size_windows(CONDA_HOME)

    last_num_files = data_manager.get_data("num_files_data").get("num_files")
    progress_bar = ProgressBar(num_files=last_num_files)
    progress_bar.start()

    def get_disk_usage(root, nondirs):
        for f in nondirs:
            nonlocal num_files
            with lock:
                num_files += 1

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

            if root.startswith(conda_envs_path) and len(root) > len(conda_envs_path):
                suffix = root[len(conda_envs_path) + 1 :]
                env_name = suffix.split(os.sep)[0]
                env_path = conda_envs_path + os.sep + env_name
                with lock:
                    total_size_list[path_corresponding_index[env_path]] += size
                    if inode not in seen_inodes:
                        seen_inodes.add(inode)
                        real_usage_list[path_corresponding_index[env_path]] += usage
            else:
                with lock:
                    total_size_list[path_corresponding_index[CONDA_HOME]] += size
                    if inode not in seen_inodes:
                        seen_inodes.add(inode)
                        real_usage_list[path_corresponding_index[CONDA_HOME]] += usage

    get_disk_usage(root, nondirs)
    with ThreadPoolExecutor(max_workers=8) as executor:
        for root, _, nondirs in walker:
            executor.submit(get_disk_usage, root, nondirs)

    progress_bar.stop()
    print("\n")
    data_manager.update_data("num_files_data", {"num_files": num_files})

    disk_usage = sum(real_usage_list)

    return real_usage_list, total_size_list, disk_usage


def get_home_sizes(namelist: list[str], pathlist: list[str], pyverlist: list[str]):
    # 因为同一conda包的多次安装只会在pkgs目录下创建一次，其余环境均为硬链接，故实际磁盘占用会远小于表观大小；Win下默认不计算，需用户手动开启
    envs_size_data = data_manager.get_data("envs_size_data")
    last_env_sizes = envs_size_data.get("env_sizes", {})
    disk_usage = envs_size_data.get("disk_usage", 0)

    name_sizes_dict = {}

    namelist_changed = []
    namelist_deleted = set(last_env_sizes.keys()) - set(namelist)
    pathlist_changed = []
    timestamplist_changed = []
    re_calc_all = False
    for name, path, pyver in zip(namelist, pathlist, pyverlist):
        c_conda_mtime, c_pip_mtime = _get_envpath_last_modified_time(name, path, pyver)
        if name not in last_env_sizes or c_conda_mtime != last_env_sizes[name]["conda_mtime"]:
            namelist_changed.append(name)
            pathlist_changed.append(path)
            timestamplist_changed.append({"conda_mtime": c_conda_mtime, "pip_mtime": c_pip_mtime})
            re_calc_all = True
            break
        elif c_pip_mtime != last_env_sizes[name]["pip_mtime"]:
            namelist_changed.append(name)
            pathlist_changed.append(path)
            timestamplist_changed.append({"conda_mtime": c_conda_mtime, "pip_mtime": c_pip_mtime})
            if name == "base":
                re_calc_all = True
                break
        else:
            name_sizes_dict[name] = {
                "real_usage": last_env_sizes[name]["real_usage"],
                "total_size": last_env_sizes[name]["total_size"],
                "conda_mtime": c_conda_mtime,
                "pip_mtime": c_pip_mtime,
            }

    if not namelist_changed and not namelist_deleted and not re_calc_all:
        return name_sizes_dict, disk_usage

    print(f"{LIGHT_YELLOW('[提示]')} 正在计算环境大小及磁盘占用情况，请稍等...")

    if re_calc_all:
        name_sizes_dict.clear()
        if os.name == "posix":
            real_usage_list, total_size_list, disk_usage = _get_envsizes_linux(pathlist)
        else:  # os.name == "nt":
            real_usage_list, total_size_list, disk_usage = _get_envsizes_windows(pathlist)

        if disk_usage:
            for name, real_usage, total_size in zip(namelist, real_usage_list, total_size_list):
                c_conda_mtime, c_pip_mtime = _get_envpath_last_modified_time(
                    name, pathlist[namelist.index(name)], pyverlist[namelist.index(name)]
                )
                name_sizes_dict[name] = {
                    "real_usage": real_usage,
                    "total_size": total_size,
                    "conda_mtime": c_conda_mtime,
                    "pip_mtime": c_pip_mtime,
                }
        else:  # (此情况应仅限Windows)未获取磁盘使用量，重置所有环境的大小
            for name in namelist:
                name_sizes_dict[name] = {
                    "real_usage": 0,
                    "total_size": 0,
                    "conda_mtime": 0,
                    "pip_mtime": 0,
                }
    else:  # 此分支仅在删除环境或环境的pip包时执行
        total_size_list = _get_env_totalsize_list(pathlist_changed)

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

    envs_size_data = {"env_sizes": name_sizes_dict, "disk_usage": disk_usage}
    data_manager.update_data("envs_size_data", envs_size_data)

    clear_lines_above(1)
    return name_sizes_dict, disk_usage


def get_env_last_updated_time(path: str, pyver: str):
    """获取环境的最后更新时间，检查conda及pip的安装行为，用于env_lastmodified_timelist"""
    meta_history_path = os.path.join(path, "conda-meta", "history")
    if os.name == "nt":
        site_packages_path = os.path.join(path, "Lib", "site-packages")
    else:  # os.name == "posix":
        site_packages_path = os.path.join(path, "lib", f"python{'.'.join(pyver.split('.')[:2])}", "site-packages")
    t1 = os.path.getmtime(meta_history_path) if os.path.exists(meta_history_path) else 0
    t2 = os.path.getmtime(site_packages_path) if os.path.exists(site_packages_path) else 0
    return max(t1, t2)


def _get_env_basic_infos():
    env_output = subprocess.run([CONDA_EXE_PATH, "env", "list", "--json"], capture_output=True, text=True).stdout
    env_list_raw = json.loads(env_output).get("envs", [])

    env_namelist = []
    env_pathlist = []
    others_env_pathlist = []

    for env_path in env_list_raw:
        if env_path == CONDA_HOME:
            env_namelist.append("base")
            env_pathlist.append(CONDA_HOME)
        elif env_path.startswith(os.path.join(CONDA_HOME, "envs")):
            env_namelist.append(os.path.split(env_path)[1])
            env_pathlist.append(env_path)
        else:
            others_env_pathlist.append(env_path)

    return env_namelist, env_pathlist, others_env_pathlist


def get_env_infos():
    # 获取所有环境的基本信息
    env_namelist, env_pathlist, others_env_pathlist = _get_env_basic_infos()
    env_num = len(env_namelist)
    # 获取所有环境的Python版本并存入env_pyverlist
    env_pypathlist = [
        os.path.join(i, "python.exe") if os.name == "nt" else os.path.join(i, "bin", "python")
        for i in env_pathlist
    ]
    env_pyverlist = [i if i else "-" for i in get_pyvers_from_paths(env_pypathlist)]
    env_lastmodified_timelist = [
        time.strftime(
            "%Y-%m-%d",
            time.gmtime(get_env_last_updated_time(path, pyver)),
        )
        for path, pyver in zip(env_pathlist, env_pyverlist)
    ]
    env_installation_time_list = []
    for i in env_pathlist:
        with open(os.path.join(i, "conda-meta", "history"), "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("==>"):
                    if match := re.search(r"\d{4}-\d{2}-\d{2}", line):
                        env_installation_time_list.append(match.group(0))
                        break
            else:
                env_installation_time_list.append("Unknown")

    name_sizes_dict, disk_usage = get_home_sizes(env_namelist, env_pathlist, env_pyverlist)
    env_realusage_list = [name_sizes_dict[i]["real_usage"] for i in env_namelist]
    env_totalsize_list = [name_sizes_dict[i]["total_size"] for i in env_namelist]
    total_apparent_size = sum(env_totalsize_list)

    assert (
        len(env_namelist)
        == len(env_pyverlist)
        == len(env_lastmodified_timelist)
        == len(env_installation_time_list)
        == len(env_pathlist)
        == len(env_realusage_list)
        == len(env_totalsize_list)
    )

    env_infos_dict = {
        "env_num": env_num,  # int
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
    }
    return env_infos_dict


def prompt_and_validate_input(prefix_str, askstr, allow_input=None, immediately_returned_chars=[]):
    def _to_print(print_str, is_clear_lines_above=False):
        if is_clear_lines_above:
            clear_lines_above(2)
        print(print_str + ",以回车结束:")

    def _to_get_input():
        if immediately_returned_chars:
            print(">>> ", end="", flush=True)
            inp = ""
            while char := get_char():
                if char in immediately_returned_chars:
                    inp = char
                    break
                if char == "\r":
                    print(flush=True)
                    break
                elif char == "\x03":
                    print()
                    sys.exit(0)
                if len(char) == 1 and char.isprintable() and len_to_print(inp) < 30:  # 让输入不超过一行
                    print(char, end="", flush=True)
                    inp += char
                elif char in ("\x08", "\x7f") and inp:
                    inp = inp[:-1]
                    print("\r\033[K" + ">>> " + inp, end="", flush=True)
        else:
            inp = input_strip(">>> ")
        return inp.strip()

    _to_print(prefix_str + "请输入" + askstr)
    inp = _to_get_input()
    # 判断输入是否合法，不合法则重新输入
    if allow_input is not None:
        allow_input.extend(immediately_returned_chars)
        error_count = 0
        while inp not in allow_input:
            error_count += 1
            if error_count > 5:
                clear_lines_above(2)
                print(RED(f"输入错误次数({error_count})过多，已退出！"))
                sys.exit(1)
            _to_print(
                f"{prefix_str}输入错误({RED(error_count)})次!请重新输入{askstr}",
                True,
            )
            inp = _to_get_input()

    return inp


def get_envs_prettytable(env_infos_dict, display_mode=3):
    """display_mode:
    1: 显示环境的Last Updated时间，和磁盘实际使用量；
    2: 显示环境的Installation时间，和磁盘总大小；
    3: 同时显示Last Updated和Installation时间，以及磁盘实际使用量和总大小；
    """

    env_num = env_infos_dict["env_num"]
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
    if display_mode == 1:
        fieldstr_LastUpdated_Installation = "Last Updated"
    elif display_mode == 2:
        fieldstr_LastUpdated_Installation = "Installation"
    else:
        fieldstr_LastUpdated_Installation = "Last Updated/Installation"

    fieldstr_Usage = ("+Usage" if display_mode == 3 else "+  Usage") + " " * 2 + "(%)"
    fieldstr_Size = "Size" + " " * 2 + "(%)"

    field_names = [
        fieldstr_Number,
        fieldstr_EnvName,
        fieldstr_LastUpdated_Installation,
    ]
    if display_mode == 1:
        field_names.append(fieldstr_Usage)
    elif display_mode == 2:
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
        if display_mode == 3:
            return (
                f"{print_fsize_smart(size,precision=2,B_suffix=False):>5} ({size/total_size*100:>2.0f})"
                if size > 0
                else f"{'-':^10}"
            )
        else:
            return (
                f"{print_fsize_smart(size,B_suffix=False):>6} ({size/total_size*100:>2.0f})"
                if size > 0
                else f"{'-':^11}"
            )

    for i in range(env_num):
        row = [
            f"[{str(i + 1)}]",
            env_namelist[i]
            + " " * (_max_name_length - len_to_print(env_namelist[i]) + 2)
            + f"({_format_pyver(env_pyverlist[i]):^7s})",
        ]
        if display_mode == 1:
            row.extend(
                [
                    f"{env_lastmodified_timelist[i]}",
                    "+ " + _format_size_info(env_realusage_list[i], disk_usage),
                ]
            )
        elif display_mode == 2:
            row.extend(
                [
                    f"{env_installation_time_list[i]}",
                    _format_size_info(env_totalsize_list[i], total_apparent_size),
                ]
            )
        else:
            row.extend(
                [
                    f"{env_lastmodified_timelist[i]} / {env_installation_time_list[i]}",
                    "+" + _format_size_info(env_realusage_list[i], disk_usage),
                    _format_size_info(env_totalsize_list[i], total_apparent_size),
                ]
            )
        table.add_row(row)

    return table


def _print_header(table_width, env_infos_dict, display_mode):
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
        BOLD(f"[Apparent Size: {print_fsize_smart(env_infos_dict['total_apparent_size'])}]")
        if display_mode == 2
        else BOLD(f"[Disk Usage: {print_fsize_smart(env_infos_dict['disk_usage'])}]")
    )
    print(
        print_str + " " * (table_width - len_to_print(print_str) - len_to_print(print_sizeinfo)) + print_sizeinfo
    )


def _print_envs_table(table):
    # 格式化输出环境名称:路径、最后修改时间，并且左对齐,去网格
    def _print_colorstr_interval(s, i):
        return LIGHT_YELLOW(s) if i % 2 == 0 else LIGHT_CYAN(s)

    # 输出表格
    for i, line in enumerate(table.get_string().splitlines()):
        if i == 0:
            print(BOLD(line))
            continue
        print(_print_colorstr_interval(line, i))


def _print_other_envs(others_env_pathlist):
    show_others, available_conda_homes = should_show_other_envs(others_env_pathlist)
    if show_others:
        print(LIGHT_YELLOW("*" * 10), end="")
        print(LIGHT_YELLOW(f" 目前管理的 Conda 发行版是 {CONDA_HOME} "), end="")
        print(LIGHT_YELLOW("*" * 10))
        if len(available_conda_homes) > 1:
            print(YELLOW("[提示] 检测到多个发行版安装:"))
            for i, condapath in enumerate(available_conda_homes, 1):
                if condapath == CONDA_HOME:
                    print(LIGHT_GREEN(f"[{i}]\t{os.path.split(condapath)[1]}\t{condapath} (当前)"))
                else:
                    print(f"[{i}]\t{os.path.split(condapath)[1]}\t{condapath}")
        if others_env_pathlist:
            print(YELLOW("[提示] 检测到如下其它发行版的环境,或未安装在规范目录(envs)下的环境,将不会被显示与管理:"))
            for i, path in enumerate(others_env_pathlist, 1):
                for condapath in available_conda_homes:
                    if path.startswith(condapath):
                        print(f"[{i}]\t{os.path.split(condapath)[1]}\t{path}")
                        break
                else:
                    print(f"[{i}]\t         \t{path}")

        print(LIGHT_YELLOW(f"{' 以上信息仅在不受支持的环境有变化时显示 ':*^55}"))
        print()


def _print_main_prompt_str(env_num, display_mode):
    main_prompt_str = f"""
允许的操作指令如下 (按{BOLD(YELLOW("[Q]"))}以退出, {BOLD(LIGHT_WHITE("<Tab>"))}切换当前显示模式 {BOLD(LIGHT_CYAN(display_mode))}):
  - 激活环境对应命令行输入编号{BOLD(LIGHT_YELLOW(f"[1-{env_num}]"))};浏览环境主目录输入{BOLD(LIGHT_GREEN("[=编号]"))};
  - 删除环境按{BOLD(RED("[-]"))};新建环境按{BOLD(LIGHT_GREEN("[+]"))};重命名环境按{BOLD(LIGHT_BLUE("[R]"))};复制环境按{BOLD(LIGHT_CYAN("[P]"))};
  - 显示并回退至环境的历史版本按{BOLD(LIGHT_MAGENTA("[V]"))};
  - 更新环境的所有 Conda 包按{BOLD(GREEN("[U]"))};
  - 查看及清空 Conda/pip 缓存按{BOLD(LIGHT_RED("[C]"))};
  - 注册 Jupyter 内核按{BOLD(CYAN("[I]"))};显示、管理及清理 Jupyter 内核按{BOLD(LIGHT_BLUE("[J]"))};
  - 检查环境完整性并显示健康报告按{BOLD(LIGHT_GREEN("[H]"))};
  - 搜索 Conda 软件包按{BOLD(LIGHT_CYAN("[S]"))};"""

    # a. Windows Only
    if os.name == "nt" and ENV_SIZE_NEED_RECALC_WIN:
        main_prompt_str += f"\n  - (仅限Windows) 显示环境大小及磁盘占用情况按{LIGHT_GREEN('[D]')};"  # Windows Only

    print(main_prompt_str)
    print()


def show_info_and_get_input(env_infos_dict):
    display_mode = 1

    env_num = env_infos_dict["env_num"]
    others_env_pathlist = env_infos_dict["others_env_pathlist"]

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
    allow_input.extend(str(i) for i in range(1, env_num + 1))
    allow_input.extend(f"={str(i)}" for i in range(1, env_num + 1))
    if os.name == "nt" and ENV_SIZE_NEED_RECALC_WIN:
        allow_input.extend(["d", "D"])

    # 1.1 输出<可能的>其他发行版与不受支持的环境
    _print_other_envs(others_env_pathlist)

    def __printRegularTransactionSet(cls=False):
        table = get_envs_prettytable(env_infos_dict, display_mode)
        if cls:
            clear_screen()
        # 1.2 输出抬头
        table_width = len_to_print(table.get_string().splitlines()[0].rstrip())
        _print_header(table_width, env_infos_dict, display_mode)
        # 1.3 输出表格
        _print_envs_table(table)

        # 2. 输出主界面提示信息
        _print_main_prompt_str(env_num, display_mode)

    __printRegularTransactionSet()

    # 3. 提示用户输入对应指令
    while True:
        # 设置了immediately_returned_chars后，inp最多只能接受30个字符
        inp = prompt_and_validate_input(
            prefix_str="", askstr="对应指令", allow_input=allow_input, immediately_returned_chars=["\t"]
        )
        if inp == "\t":
            display_mode = display_mode % 3 + 1
            __printRegularTransactionSet(cls=True)

        else:
            return inp


def do_correct_action(inp, env_infos_dict) -> Literal[0, 1]:
    """根据用户输入的值执行相应的操作,并返回两种状态码，1表示需要继续显示环境列表，0表示正常进入环境"""
    env_num = env_infos_dict["env_num"]
    env_namelist = env_infos_dict["env_namelist"]
    env_pathlist = env_infos_dict["env_pathlist"]
    env_lastmodified_timelist = env_infos_dict["env_lastmodified_timelist"]
    env_installation_time_list = env_infos_dict["env_installation_time_list"]
    env_pyverlist = env_infos_dict["env_pyverlist"]

    def _print_table(envnames, field_name_env="Env Name", color_func=lambda x: x):
        if not envnames:
            print(LIGHT_RED("[错误] 未检测到有效的环境编号！"))
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
    # 如果输入的是[-]，则删除环境
    if inp == "-":
        print("(1) 请输入想要删除的环境的编号(或all=全部),多个以空格隔开,以回车结束: ")
        inp = input_strip(f"[2-{env_num} | all] >>> ")
        if inp.lower() == "all":
            env_delete_names = [i for i in env_namelist if i not in illegal_env_namelist]
        else:
            env_delete_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
            env_delete_names = [
                env_namelist[i] for i in env_delete_nums if env_namelist[i] not in illegal_env_namelist
            ]
        if not _print_table(env_delete_names, field_name_env="Env to Delete", color_func=LIGHT_RED):
            return 1
        print("(2) 确认删除以上环境吗？[y(回车)/n]")

        inp = input_strip("[(Y)/n] >>> ")
        if inp not in ("y", "Y", ""):
            return 1
        for i in env_delete_names:
            command = get_cmd([f'mamba remove -n "{i}" --all --yes --quiet'])
            subprocess.run(command, shell=True)
            command = get_cmd([f"jupyter kernelspec list --json"])
            result_text = subprocess.run(command, shell=True, stdout=subprocess.PIPE, text=True).stdout
            # 清除可能的Jupyter注册
            try:
                result_json_dic = json.loads(result_text)
            except:
                print(
                    LIGHT_YELLOW(
                        "[警告] base环境未安装Jupyter,无法管理相关环境的jupyter内核注册,请在主界面按[J]以安装"
                    )
                )
                return 1
            _this_env_pypath = (
                result_json_dic.get("kernelspecs", {}).get(i, {}).get("spec", {}).get("argv", [""])[0]
            )
            if _this_env_pypath and not os.path.exists(_this_env_pypath):
                command = get_cmd([f'jupyter kernelspec uninstall "{i}" -y'])
                subprocess.run(command, shell=True)
                print(LIGHT_GREEN(f"[提示] 已清除卸载的环境 {LIGHT_CYAN(i)} 的Jupyter内核注册"))

        res = 1
    # 如果输入的是[+]，则新建环境
    elif inp == "+":
        print("(1) 请输入想要新建的环境的名称,以回车结束: ")
        inp1 = get_valid_input(
            ">>> ",
            lambda x: is_legal_envname(x, env_namelist),
            lambda input_str: f"新环境名称{LIGHT_CYAN(input_str)}"
            + LIGHT_RED("已存在或不符合规范")
            + "，请重新输入: ",
        )
        py_pattern = r"(?:py|pypy|python)[^A-Za-z0-9]{0,2}(\d)\.?(\d{1,2})"
        py_match = re.search(py_pattern, inp1)
        if py_match:
            inp2 = py_match.group(1) + "." + py_match.group(2)
            print(
                f"(2)[提示] 检测到环境名称{LIGHT_CYAN(inp1)}符合python环境命名规范,"
                + LIGHT_GREEN(f"已自动指定python版本={inp2}")
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
            f"(3) 请指定预安装参数(如{LIGHT_YELLOW('spyder')}包等,{LIGHT_GREEN('-c nvidia')}源等,以空格隔开)，以回车结束:"
        )
        print(
            LIGHT_YELLOW("[提示]")
            + f" 若输入\"{LIGHT_GREEN('--+')}\",则等效于预安装\"{LIGHT_YELLOW(pre_install_pkgs)}\"包(并将该环境的Jupyter内核注册到用户)"
        )
        inp3 = input_strip(">>> ")
        is_register_jupyter = False
        if inp3.find("--+") != -1:
            inp3 = inp3.replace("--+", pre_install_pkgs)
            is_register_jupyter = True
        command = get_cmd([f'mamba create -n "{inp1}" python{inp2} {inp3}'])

        cmd_res = subprocess.run(command, shell=True).returncode
        # 如果安装不成功则尝试使用更多的源
        if cmd_res != 0:
            print(LIGHT_RED("安装失败！"))
            inp = input_strip(LIGHT_YELLOW("(3a) 是否启用更多的源重新安装[(Y)/n] >>> "))
            if inp not in ("y", "Y", ""):
                return 1
            else:
                print(LIGHT_YELLOW("[提示]") + " 常用第三方源有:" + LIGHT_GREEN("pytorch nvidia intel Paddle ..."))
                print("(3b) 请输入更多的源,以空格隔开: ")
                inp_sources = input_strip(">>> ")
                inp_source_str = " ".join(f"-c {i}" for i in inp_sources.split())
                command = get_cmd([f'mamba create -n "{inp1}" python{inp2} {inp3} {inp_source_str}'])
                subprocess.run(command, shell=True)
                # 将启用的源添加为当前新环境的默认源
                if inp1 in _get_env_basic_infos()[0]:
                    inp_source_str = " ".join(f"--add channels {i}" for i in inp_sources.split()[::-1])
                    command = get_cmd(
                        [
                            f'conda activate "{inp1}"',
                            f"conda config --env {inp_source_str}",
                        ]
                    )
                    subprocess.run(command, shell=True)
                    print(f"(3c) 已将{LIGHT_GREEN(inp_sources)}添加为新环境{inp1}的默认源")

        if is_register_jupyter and inp1 in _get_env_basic_infos()[0]:
            if not inp1.isascii():
                print(
                    LIGHT_YELLOW(
                        f"(i) 检测到环境名{LIGHT_CYAN(inp1)}存在非规范字符,请重新取Jupyter内核的注册名(非显示名称):"
                    )
                )
                ipy_name = get_valid_input(
                    ">>> ",
                    lambda x: re.match(r"^[A-Za-z0-9._-]+$", x),
                    lambda input_str: f"jupyter注册名称{LIGHT_YELLOW(input_str)}"
                    + LIGHT_RED("不全符合[A-Za-z0-9._-]")
                    + f",请重新为{LIGHT_CYAN(inp1)}的jupyter内核取注册名: ",
                )
            else:
                ipy_name = inp1
            print(f"(4) 请输入此环境注册的Jupyter内核的显示名称(为空使用默认值):")
            inp11 = input_strip(f"[{inp1}] >>> ")
            if inp11 == "":
                inp11 = inp1
            command = get_cmd(
                [
                    f'conda activate "{inp1}"',
                    f'python -m ipykernel install --user --name "{ipy_name}" --display-name "{inp11}"',
                ]
            )
            subprocess.run(command, shell=True)
        res = 1
    # 如果输入的是[I]，则将指定环境注册到Jupyter
    elif inp in ["I", "i"]:
        print("(1) 请输入想要将Jupyter内核注册到用户的环境编号(或all=全部),多个以空格隔开,以回车结束: ")
        inp = input_strip(f"[2-{env_num} | all] >>> ")
        if inp.lower() == "all":
            env_reg_names = [i for i in env_namelist if i not in illegal_env_namelist]
        else:
            env_reg_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
            env_reg_names = [env_namelist[i] for i in env_reg_nums if env_namelist[i] not in illegal_env_namelist]
        if not _print_table(env_reg_names, field_name_env="Env to Register", color_func=LIGHT_CYAN):
            return 1
        print("(2) 确认注册以上环境的Jupyter内核到用户吗？[y(回车)/n]")
        inp = input_strip("[(Y)/n] >>> ")
        if inp not in ("y", "Y", ""):
            return 1
        for idx, env_name in enumerate(env_reg_names, 1):
            if not env_name.isascii():
                print(
                    LIGHT_YELLOW(
                        f"(i) 检测到环境名{LIGHT_CYAN(env_name)}存在非规范字符,请重新取Jupyter内核的注册名(非显示名称):"
                    )
                )
                ipy_name = get_valid_input(
                    ">>> ",
                    lambda x: re.match(r"^[A-Za-z0-9._-]+$", x),
                    lambda input_str: f"jupyter注册名称{LIGHT_YELLOW(input_str)}"
                    + LIGHT_RED("不全符合[A-Za-z0-9._-]")
                    + f",请重新为{LIGHT_CYAN(env_name)}的jupyter内核取注册名: ",
                )
            else:
                ipy_name = env_name
            print(f"(3.{idx}) 请输入环境{LIGHT_CYAN(env_name)}注册的Jupyter内核的显示名称(为空使用默认值):")
            ii = input_strip(f"[{env_name}] >>> ")
            if ii == "":
                ii = env_name
            command = [CONDA_EXE_PATH, "list", "-n", env_name, "--json"]
            result_text = subprocess.run(command, stdout=subprocess.PIPE, text=True).stdout
            if result_text.find("ipykernel") == -1:
                print(LIGHT_YELLOW("[提示] 该环境中未检测到ipykernel包，正在为环境安装ipykernel包..."))
                command = get_cmd(
                    [
                        f'conda activate "{env_name}"',
                        f"mamba install ipykernel --no-update-deps --yes --quiet",
                        f'python -m ipykernel install --user --name "{ipy_name}" --display-name "{ii}"',
                    ]
                )
            else:
                command = get_cmd(
                    [
                        f'conda activate "{env_name}"',
                        f'python -m ipykernel install --user --name "{ipy_name}" --display-name "{ii}"',
                    ]
                )
            subprocess.run(command, shell=True)
        res = 1
    # 如果输入的是[R]，则重命名环境
    elif inp in ["R", "r"]:
        print("(1) 请输入想要重命名的环境的编号,多个以空格隔开,以回车结束: ")
        inp = input_strip(f"[2-{env_num}] >>> ")
        env_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
        env_names = [env_namelist[i] for i in env_nums if env_namelist[i] not in illegal_env_namelist]
        if not _print_table(env_names, field_name_env="Env to Rename", color_func=LIGHT_CYAN):
            return 1
        print("(2) 确认重命名以上环境吗？[y(回车)/n]")
        inp = input_strip("[(Y)/n] >>> ")
        if inp not in ("y", "Y", ""):
            return 1
        for idx, env_name in enumerate(env_names, 1):
            print(f"(3.{idx}) 请输入环境{LIGHT_CYAN(env_name)}重命名后的环境名称:")
            ii = get_valid_input(
                ">>> ",
                lambda x: is_legal_envname(x, env_namelist) and x != env_name,
                lambda input_str: f"新环境名称{LIGHT_YELLOW(input_str)}"
                + LIGHT_RED("已存在或不符合规范")
                + f",请重新为{LIGHT_CYAN(env_name)}重命名: ",
            )
            command = get_cmd(
                [
                    f'mamba create -n "{ii}" --clone "{env_name}"',
                    f'mamba remove -n "{env_name}" --all --yes --quiet',
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
                        "[警告] base环境未安装Jupyter,无法管理相关环境的jupyter注册,请在主界面按[J]以安装"
                    )
                )
                return 1
            _this_env_pypath = (
                result_json_dic.get("kernelspecs", {}).get(env_name, {}).get("spec", {}).get("argv", [""])[0]
            )
            if _this_env_pypath and not os.path.exists(_this_env_pypath):
                print(LIGHT_YELLOW("[提示] 检测到原环境的Jupyter注册已失效，正在为新环境重新注册Jupyter"))
                if not ii.isascii():
                    print(
                        LIGHT_YELLOW(
                            f"(i) 检测到新环境名{LIGHT_CYAN(ii)}存在非规范字符,请重新取Jupyter内核的注册名(非显示名称):"
                        )
                    )
                    ipy_name = get_valid_input(
                        ">>> ",
                        lambda x: re.match(r"^[A-Za-z0-9._-]+$", x),
                        lambda input_str: f"jupyter内核注册名称{LIGHT_YELLOW(input_str)}"
                        + LIGHT_RED("不全符合[A-Za-z0-9._-]")
                        + f",请重新为{LIGHT_CYAN(ii)}的jupyter内核取注册名: ",
                    )
                else:
                    ipy_name = ii
                print("(4) 请输入注册的Jupyter内核的显示名称(为空使用默认值):")
                iii = input_strip(f"[{ii}] >>> ")
                if iii == "":
                    iii = ii
                command = get_cmd(
                    [
                        f'jupyter kernelspec uninstall "{env_name}" -y',
                        f'conda activate "{ii}"',
                        f'python -m ipykernel install --user --name "{ipy_name}" --display-name "{iii}"',
                    ]
                )
                subprocess.run(command, shell=True)
                print(LIGHT_GREEN(f"已重新注册新环境{ii}的Jupyter"))
        res = 1
    # 如果输入的是[P]，则复制环境
    elif inp in ["P", "p"]:
        print("(1) 请输入想要复制的环境的编号,多个以空格隔开,以回车结束: ")
        inp = input_strip(f"[1-{env_num}] >>> ")
        env_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
        env_names = [env_namelist[i] for i in env_nums]
        if not _print_table(env_names, field_name_env="Env to Copy"):
            return 1
        print("(2) 确认复制以上环境吗？[y(回车)/n]")
        inp = input_strip("[(Y)/n] >>> ")
        if inp not in ("y", "Y", ""):
            return 1
        for idx, env_name in enumerate(env_names, 1):
            print(f"(3.{idx}) 请输入环境{LIGHT_CYAN(env_name)}复制后的环境名称(为空使用默认值):")
            default_envname = env_name + "_copy"
            iii = 1
            while default_envname in env_namelist:
                iii += 1
                default_envname = env_name + "_copy" + "_" + str(iii)
            ii = get_valid_input(
                f"[{default_envname}] >>> ",
                lambda x: is_legal_envname(x, env_namelist) or x == "",
                lambda input_str: f"新环境名称{LIGHT_YELLOW(input_str)}"
                + LIGHT_RED("已存在或不符合规范")
                + f",请重新为{LIGHT_CYAN(env_name)}命名: ",
            )
            if ii == "":
                ii = default_envname
            command = get_cmd([f'mamba create -n "{ii}" --clone "{env_name}" --quiet'])
            subprocess.run(command, shell=True)
        res = 1
    # 如果输入的是[J]，则显示、管理所有已注册的Jupyter环境及清理弃用项
    elif inp in ["J", "j"]:
        command = [CONDA_EXE_PATH, "list", "--json"]
        if subprocess.run(command, capture_output=True, text=True).stdout.find("ipykernel") == -1:
            print(LIGHT_YELLOW("[提示] 未检测到jupyter命令，正尝试向base环境安装ipykernel..."))
            command = get_cmd(["mamba install ipykernel -y"])
            if subprocess.run(command, shell=True).returncode:
                print(LIGHT_RED("[提示] 安装失败，请在 base 环境中手动安装ipykernel后重试！"))
                return 1
            else:
                print(LIGHT_GREEN(f"[提示] {LIGHT_CYAN('base')}环境中ipykernel安装成功！"))
        print("当前用户已注册的Jupyter内核如下:")
        command = get_cmd(["jupyter kernelspec list --json"])
        kernel_output = subprocess.run(command, shell=True, stdout=subprocess.PIPE, text=True).stdout
        kernel_dict = json.loads(kernel_output).get("kernelspecs", {})
        # 创建表格对象
        kernel_names = []
        is_valid_kernels = []
        display_names = []
        py_pathlist = []
        py_versions = []
        install_timestamps = []
        kernel_dirs = []
        try:
            value = kernel_dict.pop("python3")
            kernel_dict = {"python3": value, **kernel_dict}
        except:
            pass

        for k_name, k_info in kernel_dict.items():
            kernel_names.append(k_name)
            display_names.append(k_info["spec"]["display_name"])
            py_pathlist.append(k_info["spec"]["argv"][0])
            install_timestamps.append(
                time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(k_info["resource_dir"])))
            )
            kernel_dirs.append(replace_user_path(k_info["resource_dir"]))
        py_versions = get_pyvers_from_paths(py_pathlist)
        is_valid_kernels = [bool(i) for i in py_versions]

        dir_col_max_width = max(len(i) for i in kernel_dirs)
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
                        LIGHT_CYAN(f"[{i+1}]"),
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
                        f"[{i+1}]",
                        display_names[i],
                        py_versions[i],
                        install_timestamps[i],
                        os.sep.join((lambda p: (p[0], LIGHT_YELLOW(p[1])))(os.path.split(kernel_dirs[i]))),
                    ]
                )
            else:
                table.add_row(
                    [
                        LIGHT_RED(f"[{i+1}]"),
                        LIGHT_RED(display_names[i] + " (已失效)"),
                        LIGHT_RED("-"),
                        LIGHT_RED(install_timestamps[i]),
                        LIGHT_RED(
                            os.sep.join((lambda p: (p[0], LIGHT_YELLOW(p[1])))(os.path.split(kernel_dirs[i])))
                        ),
                    ]
                )

        # 打印表格
        print(table)
        if not table._rows:
            print(LIGHT_YELLOW("[提示] 未检测到任何Jupyter内核注册！"))
            return 1
        print()
        # 询问清理失效项
        if not all(is_valid_kernels):
            print(LIGHT_YELLOW("(0a) 确认清理以上失效项吗？[y(回车)/n]"))
            inp = input_strip("[(Y)/n] >>> ")
            if inp in ("y", "Y", ""):
                for i in [i for i in kernel_names if not is_valid_kernels[kernel_names.index(i)]]:
                    command = get_cmd([f'jupyter kernelspec uninstall "{i}" -y'])
                    subprocess.run(command, shell=True)

        # 删除对应Jupyter环境
        print("(1) 请输入想要删除的Jupyter内核的编号(或all=全部),多个以空格隔开,以回车结束: ")
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
            for i in kernel_names_todelete:
                table.add_row([display_names[kernel_names.index(i)], kernel_dirs[kernel_names.index(i)]])
            print(table.get_string().splitlines()[0])
            print("-" * len(table.get_string().splitlines()[0]))
            for i in table.get_string().splitlines()[1:]:
                print(LIGHT_RED(i))
            print("-" * len(table.get_string().splitlines()[0]))
        else:
            print("[错误] 未检测到有效的Jupyter内核编号！")
            return 1
        print("(2) 确认删除以上Jupyter内核注册吗？[y(回车)/n]")
        inp = input_strip("[(Y)/n] >>> ")
        if inp not in ("y", "Y", ""):
            return 1
        for i in kernel_names_todelete:
            command = get_cmd([f'jupyter kernelspec uninstall "{i}" -y'])
            subprocess.run(command, shell=True)
        res = 1
    # 对应环境查看并回退至历史版本按[V]
    elif inp in ["V", "v"]:
        inp = prompt_and_validate_input(
            prefix_str="(1) ",
            askstr="需要查看及回退历史版本的环境编号",
            allow_input=[str(i) for i in range(1, env_num + 1)],
        )
        env_name = env_namelist[int(inp) - 1]
        print(f"环境{LIGHT_CYAN(env_name)}的历史版本如下:")
        command = [CONDA_EXE_PATH, "list", "-n", env_name, "--revisions"]
        result_text = subprocess.run(command, stdout=subprocess.PIPE, text=True).stdout
        print(result_text)
        raw_src_set = set(
            source.rsplit("/", 1)[0]
            for source in re.findall(r"\(([^()]+)\)", result_text)
            if "/" in source and " " not in source.rsplit("/", 1)[0]
        )
        sourceslist = filter_and_sort_sources_by_priority(raw_src_set, keep_url=True, enable_default_src=False)
        valid_rev_nums = [i for i in re.findall((r"(?i)\(rev\s+(\d+)\)"), result_text)]
        print(
            f"(2) 请输入环境{LIGHT_CYAN(env_name)}的历史版本编号["
            + LIGHT_YELLOW(f"0-{max(int(i) for i in valid_rev_nums)}")
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
                    LIGHT_YELLOW("[提示] 根据历史记录已自动启用附加源:"),
                    LIGHT_GREEN(formatted_sources),
                )
            command = get_cmd(
                [f'conda install -n "{env_name}" --revision {inp} {formatted_sources}'],
            )
            subprocess.run(command, shell=True)

        res = 1
    # 如果输入的是[C]，则运行pip cache purge和mamba clean --all -y来清空所有pip与conda缓存
    elif inp in ["C", "c"]:
        command = get_cmd(["mamba clean --all --dry-run --json --quiet", "pip cache dir"])
        result_text = subprocess.run(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        ).stdout
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
                index_cache_size + tarballs_cache_size + pkgs_cache_size + logfiles_and_locks_size + pip_cache_size
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
                lambda x: "输入" + LIGHT_RED(x) + "应为空或Y或N或数字[1-5]的以空格隔开的组合,请重新输入: ",
            )
            if inp in ("N", "n"):
                return 1
            elif inp in ("y", "Y", ""):
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
            subprocess.run(command, shell=True)
        except Exception as e:
            print(
                LIGHT_RED(LIGHT_RED("[错误] ") + str(e)),
                LIGHT_RED("[错误] mamba clean --all --dry-run --json命令输出有误！无法解析,输出如下:"),
                result_text,
                LIGHT_YELLOW("[提示] 已启动默认清理程序"),
                sep="\n",
            )
            print("(1) 确认清空所有Conda/pip缓存吗？[y(回车)/n]")
            inp = input_strip("[(Y)/n] >>> ")
            if inp not in ("y", "Y", ""):
                return 1
            command = get_cmd(["mamba clean --all -y", "pip cache purge"])
            subprocess.run(command, shell=True)

        res = 1
    # 如果输入的是[U]，则更新指定环境的所有包
    elif inp in ["U", "u"]:
        print(LIGHT_YELLOW("[提示] 慎用，请仔细检查更新前后的包对应源的变化！"))
        print("(1) 请输入想要更新的环境的编号(或all=全部),多个以空格隔开,以回车结束: ")
        inp = input_strip(f"[1-{env_num} | all] >>> ")
        if inp.lower() == "all":
            env_names = env_namelist
        else:
            env_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
            env_names = [env_namelist[i] for i in env_nums]
        if not _print_table(env_names, field_name_env="Env to Update", color_func=LIGHT_CYAN):
            return 1
        print("(2) 确认更新以上环境吗？[y(回车)/n]")
        inp = input_strip("[(Y)/n] >>> ")
        if inp not in ("y", "Y", ""):
            return 1
        for idx, env_name in enumerate(env_names, 1):
            if env_name == "base":
                strict_channel_priority = False
            else:
                strict_channel_priority = True
            print(
                f"[{idx}/{len(env_names)}] 正在更新环境{LIGHT_CYAN(env_name)}的所有包...",
                "(strict-channel-priority:",
                (LIGHT_GREEN("True") + ")" if strict_channel_priority else LIGHT_RED("False") + ")"),
            )
            command = [CONDA_EXE_PATH, "list", "-n", env_name, "--json"]
            result_text = subprocess.run(command, capture_output=True, text=True).stdout
            result_json_list = json.loads(result_text)
            raw_src_set = set()
            for pkginfo_dict in result_json_list:
                if source_str := pkginfo_dict.get("channel"):
                    raw_src_set.add(source_str.rsplit("/", 1)[-1])
            if "pypi" in raw_src_set:
                print(LIGHT_RED("[警告] 检测到如下由Pip管理的包，更新可能会出现问题！"))
                table = PrettyTable(["Package from Pip", "Version"])
                table.align = "l"
                table.border = False
                for pkginfo_dict in result_json_list:
                    if pkginfo_dict.get("channel") == "pypi":
                        table.add_row([pkginfo_dict["name"], pkginfo_dict["version"]])
                print(table.get_string().splitlines()[0])
                print("-" * len_to_print(table.get_string().splitlines()[0]))
                print(*(i for i in table.get_string().splitlines()[1:]), sep="\n")
                print("-" * len_to_print(table.get_string().splitlines()[0]))
                print(f"(i) 是否继续更新环境{LIGHT_CYAN(env_name)}？[y/n(回车)]")
                inp1 = input_strip("[y/(N)] >>> ")
                if inp1 not in ("y", "Y"):
                    continue
            sourceslist = filter_and_sort_sources_by_priority(raw_src_set, enable_default_src=False)
            formatted_sources = " ".join(["-c " + source for source in sourceslist])
            if formatted_sources:
                print(LIGHT_YELLOW("[提示] 已自动启用附加源: ") + LIGHT_GREEN(formatted_sources))
            if strict_channel_priority:
                command_str = f'mamba update -n "{env_name}" {formatted_sources} --all --strict-channel-priority'
            else:
                command_str = f"mamba update --all {formatted_sources}"
            command = get_cmd([command_str])
            subprocess.run(command, shell=True)
        res = 1
    # 如果输入的是[S]，则搜索指定Python版本下的包
    elif inp in ["S", "s"]:
        if not IS_MAMBA and (not LIBMAMBA_SOLVER_VERSION or Version(LIBMAMBA_SOLVER_VERSION) < Version("23.9")):
            print(
                LIGHT_YELLOW(
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
            print(LIGHT_YELLOW("请在base环境下执行以上命令。"))
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

        def _pure_python_version(version_str):
            version_str = version_str.replace(" ", "")

            notequal_3vers_pattern = re.compile(r"(,?!=\d+\.\d+\.\d+)(?=,|$)")
            if len(res := notequal_3vers_pattern.sub("", version_str)) > 1:
                version_str = res

            version_pattern = re.compile(r"(2|3|4)\.([a-zA-Z\d*]{1,5})(?:\.[a-zA-Z\d.*]+)?")
            new_version_str = version_pattern.sub(shorten_version, version_str)

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
                cuda_version = _pure_cuda_version(cuda_version)

            if not python_version and python_version_tmp:
                python_version = _pure_python_version(python_version_tmp)

            raw_pkginfo_dict["build_prefix"] = build_prefix
            raw_pkginfo_dict["python_version"] = python_version
            raw_pkginfo_dict["cuda_version"] = cuda_version
            raw_pkginfo_dict["is_cuda"] = is_cuda
            raw_pkginfo_dict["channel"] = channel

        def find_python_version_range(python_version_str):
            """Return: 最小支持Python版本: str|None，最大支持Python版本: str|None"""
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

            def merge_2nd(self, pkginfo_dicts_list):
                """第二遍合并只考虑name, version, channel，并注明支持的最大Python版本，与是否存在CUDA包"""
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

        def search_pkgs_main(target_py_version):
            INDEX_CHECK_INTERVAL = 30  # 30分钟检查一次，搜索功能的索引文件在这期间内使用缓存搜索

            print("-" * min(100, fast_get_terminal_size().columns))
            print(
                "[提示1] 搜索默认启用的源为"
                + LIGHT_GREEN("pytorch,nvidia,intel,conda-forge,defaults")
                + ","
                + LIGHT_YELLOW("如需额外源请在末尾添加 -c 参数")
            )
            print("[提示2] 可用mamba repoquery depends/whoneeds命令列出包的依赖项/列出需要给定包的程序包")
            print("[提示3] 搜索语法为Name=Version=Build,后两项可选 (示例:numpy>1.17,<1.19.2 *numpy*=1.17.*=py38*)")
            print(
                "        (详见https://github.com/conda/conda/blob/main/docs/source/user-guide/concepts/pkg-search.rst)"
            )
            print("-" * min(100, fast_get_terminal_size().columns))
            if target_py_version:
                print(f"(2) 请输入想要搜索的包 (适用于Python {target_py_version}),以回车结束:")
            else:
                print("(2) 请输入想要搜索的包 (适用于全部Python版本),以回车结束:")
            inp = get_valid_input(
                ">>> ",
                lambda x: x,
                lambda x: "输入" + LIGHT_RED("不能为空") + ",请重新输入: ",
            )
            if inp.find(" -c ") != -1:
                add_channels = [i for i in inp[inp.find(" -c ") :].split(" -c ") if i != ""]
                print(
                    LIGHT_YELLOW("[提示] 检测到-c参数，已自动添加相应源: " + LIGHT_GREEN(", ".join(add_channels)))
                )
                inp = inp[: inp.find(" -c ")]
            else:
                add_channels = []

            total_channels = add_channels + ["pytorch", "nvidia", "intel", "conda-forge", "defaults"]
            total_channels = ordered_unique(total_channels)
            search_meta_data = data_manager.get_data("search_meta_data")
            if search_meta_data.get("last_update_time", 0) >= (time.time() - INDEX_CHECK_INTERVAL * 60) and set(
                total_channels
            ).issubset(search_meta_data.get("total_channels", [])):
                command_str = f'mamba repoquery search "{inp}" {" ".join(["-c "+i for i in total_channels])} --json --quiet --use-index-cache'
                search_meta_data["total_channels"] = list(
                    set(total_channels) | set(search_meta_data.get("total_channels", []))
                )
            else:
                command_str = (
                    f'mamba repoquery search "{inp}" {" ".join(["-c "+i for i in total_channels])} --json --quiet'
                )
                search_meta_data["total_channels"] = total_channels
            search_meta_data["last_update_time"] = time.time()
            data_manager.update_data("search_meta_data", search_meta_data)

            command = get_cmd([command_str])

            print(f"正在搜索({LIGHT_CYAN(inp)})...")
            t0_search = time.time()
            if "mamba repoquery search" in command:
                result_text = subprocess.run(
                    command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True
                ).stdout.decode(
                    "utf-8"
                )  # win下的mamba输出强制utf-8编码问题
            else:
                result_text = subprocess.run(
                    command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True, text=True
                ).stdout
            clear_lines_above(1)
            pkg_name_to_search = inp.split("=", 1)[0]
            try:
                result_json = json.loads(result_text)
            except json.JSONDecodeError:
                print(LIGHT_RED("[错误] 搜索结果解析失败!原始结果如下:"))
                print(result_text)
                exit(1)

            if not result_json.get("result", {}).get("pkgs"):
                if not result_json.get("result"):
                    print(json.dumps(result_json, indent=4))
                print(LIGHT_YELLOW(f"[警告] 未搜索到任何相关包({round(time.time() - t0_search, 2)} s)！"))
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

            def _hidden_columns(row, hidden_field_indexes):
                return [row[i] for i in range(len(row)) if i not in hidden_field_indexes]

            def _get_overview_table(pkg_overviews_list, user_options) -> tuple[PrettyTable, bool]:
                """
                适用于user_options["display_mode"]等于1的情况。
                <Returns>: (table, is_display_omitted) -- 同 _get_pkgs_table 函数
                <Note>:
                    table会尽量显示完整name字段(保证name字段长度>=_NAME_MIN_WIDTH),为此可能会：
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

                table_padding_width = 2
                f_number_width = len(f"[{len(pkg_overviews_list)}]") if user_options["select_mode"] else 0
                f_version_width = len_to_print(version_field)
                f_channel_width = len_to_print(channel_field)
                f_python_version_width = len_to_print(python_version_field)
                f_cuda_width = len_to_print(cuda_field)
                f_timestamp_width = len_to_print(timestamp_field)
                f_build_count_width = len_to_print(build_count_field)
                if len(pkg_overviews_list):
                    f_version_width = max(
                        f_version_width,
                        min(ver_len_maxlim, max(map(lambda x: len(x["version"]), pkg_overviews_list))),
                    )
                    f_channel_width = max(
                        f_channel_width, max(map(lambda x: len(x["channel"]), pkg_overviews_list))
                    )

                name_len_maxlim = (
                    terminal_width
                    - f_number_width
                    - f_version_width
                    - f_channel_width
                    - f_python_version_width
                    - f_cuda_width
                    - f_timestamp_width
                    - f_build_count_width
                    - table_padding_width * (8 if user_options["select_mode"] else 7)
                )
                _NAME_MIN_WIDTH = 20
                if name_len_maxlim < _NAME_MIN_WIDTH:
                    _hidden_fields.append(build_count_field)
                    name_len_maxlim += f_build_count_width + table_padding_width
                if name_len_maxlim < _NAME_MIN_WIDTH:
                    _hidden_fields.append(timestamp_field)
                    name_len_maxlim += f_timestamp_width + table_padding_width
                if name_len_maxlim < _NAME_MIN_WIDTH:
                    _hidden_fields.append(channel_field)
                    name_len_maxlim += f_channel_width + table_padding_width
                name_len_maxlim = max(name_len_maxlim, _NAME_MIN_WIDTH)

                hidden_field_indexes = {table_fields.index(field) for field in _hidden_fields}

                if hidden_field_indexes:
                    is_display_omitted = True
                    table_fields = _hidden_columns(table_fields, hidden_field_indexes)
                table = PrettyTable(table_fields)
                table.align[name_field] = "l"
                table.align[version_field] = "c"
                table.align[channel_field] = "r"
                table.align[python_version_field] = "c"
                table.align[cuda_field] = "r"
                table.align[timestamp_field] = "r"
                table.align[build_count_field] = "r"
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

                    if cuda110_12 := pkg_overview["cuda110_12"]:
                        if version_parse(cuda110_12) >= version_parse("12"):
                            cuda110_12 = f'({LIGHT_GREEN(f"{cuda110_12:^6}")})'
                        elif version_parse(cuda110_12) >= version_parse("11.8"):
                            cuda110_12 = f'({LIGHT_CYAN(f"{cuda110_12:^6}")})'
                        else:
                            cuda110_12 = f"({cuda110_12:^6})"

                        cuda_support += f"{'':2}{cuda110_12}"
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
                        time.strftime("%Y-%m-%d", time.gmtime(pkg_overview["timestamp"])),
                        f"{pkg_overview['build_count']} builds",
                    ]
                    if user_options["select_mode"]:
                        row.insert(0, f"[{i}]")
                    if hidden_field_indexes:
                        row = _hidden_columns(row, hidden_field_indexes)
                    table.add_row(row)

                return table, is_display_omitted

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

            def _get_pkgs_table(pkginfos_list, user_options) -> tuple[PrettyTable, bool]:
                """
                适用于user_options["display_mode"]等于2或3的情况。
                <Returns>: (table, is_display_omitted)
                    table: PrettyTable
                    is_display_omitted：是否有内容(因为终端宽度太小)被省略而未被显示
                <Note>:
                    table会尽量显示完整name字段(保证name字段长度>=_NAME_MIN_WIDTH),为此可能会：
                        减少build字段长度->省略build字段->省略size字段->省略timestamp字段
                """
                if user_options["display_mode"] == 1:
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

                def __add_sort_flag(sort_by_str):
                    return sort_flag if user_options["sort_by"][0] == sort_by_str else ""

                def __get_build_fieldstr():
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
                name_field = "Name" + __add_sort_flag("name/version")
                version_field = "Version" + __add_sort_flag("name/version")
                build_field = __get_build_fieldstr() + __add_sort_flag("build")
                channel_field = "Channel" + __add_sort_flag("channel")
                python_version_field = "Python" + __add_sort_flag("python_version")
                cuda_version_field = " CUDA " + __add_sort_flag("cuda_version")
                size_field = (" " * 3 if max_cuda_len < 6 + 2 else "") + "Size" + __add_sort_flag("size")
                timestamp_field = "Timestamp" + __add_sort_flag("timestamp")

                table_padding_width = 2
                f_number_width = len(f"[{len(pkginfos_list)}]") if user_options["select_mode"] else 0
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

                if user_options["display_mode"] != 3 and len(pkginfos_list):
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
                        - table_padding_width * (9 if user_options["select_mode"] else 8)
                    )
                    while name_len_maxlim < max_name_len:
                        is_display_omitted = True
                        if build_len_maxlim > 9:  # 当name长度不够时，逐渐减小build长度来尽量优先name长度
                            build_len_maxlim -= 1
                            name_len_maxlim += 1
                        else:
                            break
                    build_field = __get_build_fieldstr() + __add_sort_flag("build")
                    f_build_width = max(len_to_print(build_field), build_len_maxlim)

                    _NAME_MIN_WIDTH = 15
                    if name_len_maxlim < _NAME_MIN_WIDTH:
                        _hidden_fields.append(build_field)
                        name_len_maxlim += f_build_width + table_padding_width
                    if name_len_maxlim < _NAME_MIN_WIDTH:
                        _hidden_fields.append(size_field)
                        name_len_maxlim += f_size_width + table_padding_width
                    if name_len_maxlim < _NAME_MIN_WIDTH:
                        _hidden_fields.append(timestamp_field)
                        name_len_maxlim += f_timestamp_width + table_padding_width
                    name_len_maxlim = max(name_len_maxlim, _NAME_MIN_WIDTH)

                elif len(pkginfos_list):  # user_options["display_mode"] == 3 且有包时
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
                table.align[name_field] = "l"
                table.align[version_field] = "l"
                table.align[build_field] = "l"
                table.align[channel_field] = "r"
                table.align[python_version_field] = "c"
                table.align[cuda_version_field] = "c"
                table.align[size_field] = "r"
                table.align[timestamp_field] = "r"
                # table.padding_width = table_padding_width
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
                        cuda_info = "  "
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
                    if user_options["display_mode"] != 3 and len(pkginfo_dict["name"]) > name_len_maxlim:
                        name_str = (
                            pkginfo_dict["name"][: name_len_maxlim - 8]
                            + LIGHT_YELLOW("...")
                            + pkginfo_dict["name"][-5:]
                        )
                    else:
                        name_str = pkginfo_dict["name"]
                    if user_options["display_mode"] != 3 and len(pkginfo_dict["version"]) > ver_len_maxlim:
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
                        print_fsize_smart(pkginfo_dict["size"], B_suffix=False),
                        time.strftime("%Y-%m-%d", time.gmtime(pkginfo_dict["timestamp"])),
                    ]
                    if user_options["select_mode"]:
                        row.insert(0, f"[{i}]")
                    if hidden_field_indexes:
                        row = _hidden_columns(row, hidden_field_indexes)
                    table.add_row(row)

                return table, is_display_omitted

            def _data_processing_transaction(user_options) -> list[dict]:
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
                            version_str = "UNSURE"
                        else:
                            version_str = "  "
                    else:
                        if pkginfo_dict["cuda_version"]:
                            version_str = pkginfo_dict["cuda_version"]
                        elif pkginfo_dict["is_cuda"]:
                            version_str = "UNSURE"
                        else:
                            version_str = "  "
                    return version_str

                def _parse_cuda_version(version_str):
                    if version_str == "  ":
                        return version_parse("0.0.0")
                    elif version_str == "UNSURE":
                        return version_parse("0.0.1")
                    else:
                        return version_parse(version_str)

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
                                        _get_cuda_versionstr_from_pkgdict(
                                            pkginfo_dict, filter_to_pure_version=False
                                        ),
                                        filter_value,
                                        always_true_strs=["UNSURE"],
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
                        pkginfos_list.sort(key=lambda x: _sort_by_channel(x[sort_by[0]]), reverse=sort_by[1])

                    elif sort_by[0]:
                        pkginfos_list.sort(
                            key=lambda x: x[sort_by[0]],
                            reverse=sort_by[1],
                        )
                elif display_mode == 1 and user_options["reversed_display"]:
                    pkginfos_list = pkginfos_list[::-1]

                return pkginfos_list

            def _print_transcation(pkginfos_list, first_print=False):
                table, is_display_omitted = _get_pkgs_table(pkginfos_list, user_options)
                table_header, table_body = table.get_string().split("\n", 1)
                print(BOLD(table_header))
                print("-" * len_to_print(table_header))
                print(table_body)
                if first_print:
                    print("-" * len_to_print(table_header))
                    print(
                        LIGHT_GREEN(f"搜索完成({round(time.time() - t0_search, 2)} s)！"),
                        f"对于{LIGHT_CYAN(inp)},共找到{LIGHT_CYAN(len(pkginfos_list_raw))}个相关包,搜索结果如上",
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

            def _BOLD_keyboard_keys(print_str):
                return re.sub(
                    r"((?:\x1b\[\d+m)?)(\[\w{1,5}\])",
                    r"\1" + BOLD(r"\2") + r"\1",
                    print_str,
                )

            def _get_user_options(user_options, pkginfos_list) -> int:
                """返回已打印到终端的实际行数 num_lines"""

                def __count_and_print(s) -> int:
                    print(s)
                    return get_printed_line_count(s)

                user_options["need_reprint"] = True

                num_lines = 0

                filters = user_options["filters"]
                sort_by = user_options["sort_by"]

                is_filtered = any(filter_value for filter_value in filters.values())

                if user_options["select_mode"]:
                    if user_options["display_mode"] != 1:
                        while user_options["select_mode"]:
                            num_lines += __count_and_print(
                                f"(i) 请输入要查看详细信息的包对应编号(带{LIGHT_CYAN('=')}号则显示安装命令行并拷贝到剪贴板): "
                            )
                            key = input_strip(">>> ")
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
                                    prompt_str = f" [{key}]包{LIGHT_CYAN(pkginfo_dict['name'])} {LIGHT_GREEN(pkginfo_dict['version'])}的详细信息如下 "
                                    print_str = (
                                        "="
                                        * min(
                                            35, (fast_get_terminal_size().columns - len_to_print(prompt_str)) // 2
                                        )
                                        + prompt_str
                                        + "="
                                        * min(
                                            35, (fast_get_terminal_size().columns - len_to_print(prompt_str)) // 2
                                        )
                                    )
                                    num_lines += __count_and_print(print_str)
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
                                    num_lines += __count_and_print(print_str)
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
                                    num_lines += __count_and_print(print_str)
                                    if os.name == "posix":
                                        if os.system(f'echo "{print_str}" | xclip -selection clipboard') == 0:
                                            num_lines += __count_and_print(
                                                LIGHT_GREEN("[提示] 安装命令已拷贝到剪贴板！")
                                            )
                                    elif os.name == "nt":
                                        if os.system(f'echo "{print_str}" | clip') == 0:
                                            num_lines += __count_and_print(
                                                LIGHT_GREEN("[提示] 安装命令已拷贝到剪贴板！")
                                            )

                            else:
                                clear_lines_above(2)
                                num_lines -= 2
                    else:  # display_mode == 1
                        num_lines += __count_and_print("(i) 请输入要跳转到原始显示模式并过滤的包版本对应编号:")
                        key = input_strip(">>> ")
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
                    print_str = LIGHT_CYAN("[1] 概览") + "\t" + "[2] 精简显示" + "\t" + "[3] 原始显示"
                elif user_options["display_mode"] == 2:
                    print_str = "[1] 概览" + "\t" + LIGHT_CYAN("[2] 精简显示") + "\t" + "[3] 原始显示"
                else:  # display_mode == 3
                    print_str = "[1] 概览" + "\t" + "[2] 精简显示" + "\t" + LIGHT_CYAN("[3] 原始显示")
                print_str += "\t"
                if user_options["display_mode"] != 1:
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
                num_lines += __count_and_print(print_str)

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
                        print_str += f"{LIGHT_CYAN(filter_name)}({LIGHT_GREEN(filter_value)})"
                if sort_by[0] or filter_enable_list:
                    num_lines += __count_and_print(print_str)

                key = get_char()

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
                        num_lines += __count_and_print("(i) 请按下排序依据对应的序号: ")
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
                        num_lines += __count_and_print(print_str)

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
                elif key in ("\x1b[A", "\x1b[B", "àH", "àP") and sort_by[0] and user_options["display_mode"] != 1:
                    if key in ("\x1b[A", "àH") and sort_by[1]:
                        sort_by[1] = False
                    elif key in ("\x1b[B", "àP") and not sort_by[1]:
                        sort_by[1] = True
                    else:
                        user_options["need_reprint"] = False

                elif key in ("F", "f") and user_options["display_mode"] != 1:
                    clear_lines_above(num_lines)
                    num_lines = 0
                    num_lines += __count_and_print("(i) 请按下过滤目标对应的序号: ")
                    print_strs = [
                        LIGHT_GREEN("[1] 名称") if filters["name"] else "[1] 名称",
                        LIGHT_GREEN("[2] 版本") if filters["version"] else "[2] 版本",
                        LIGHT_GREEN("[3] Channel") if filters["channel"] else "[3] Channel",
                        (LIGHT_GREEN("[4] Python版本") if filters["python_version"] else "[4] Python版本"),
                        (LIGHT_GREEN("[5] CUDA版本") if filters["cuda_version"] else "[5] CUDA版本"),
                        (LIGHT_GREEN("[6] 只显示CUDA") if filters["is_cuda_only"] else "[6] 只显示CUDA"),
                    ]
                    print_str = _BOLD_keyboard_keys("\t".join(print_strs))
                    num_lines += __count_and_print(print_str)
                    key1 = get_char()
                    if key1 == "1":
                        if filters["name"]:
                            filters["name"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += __count_and_print("(ii) 请输入名称过滤器(支持通配符*): ")
                            filters["name"] = input_strip(">>> ")
                            num_lines += 1
                    elif key1 == "2":
                        if filters["version"]:
                            filters["version"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += __count_and_print(
                                "(ii) 请输入版本过滤器(支持比较式[示例: 1.19|<2|>=2.6,<2.10.0a0,!=2.9.*]): "
                            )
                            filters["version"] = input_strip(">>> ")
                            num_lines += 1
                    elif key1 == "3":
                        if filters["channel"]:
                            filters["channel"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += __count_and_print("(ii) 请输入Channel过滤器(支持通配符*): ")
                            filters["channel"] = input_strip(">>> ")
                            num_lines += 1
                    elif key1 == "4":
                        if filters["python_version"]:
                            filters["python_version"] = None
                        else:
                            clear_lines_above(num_lines)
                            num_lines = 0
                            num_lines += __count_and_print(
                                "(ii) 请输入Python版本过滤器(支持主次版本号比较式[示例: >=3.11|3.7|!=2.*,<3.10a0,!=3.8]): "
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
                            num_lines += __count_and_print(
                                "(ii) 请输入CUDA版本过滤器(支持主次版本号比较式[示例: !=12.2,<=12.3|>=9,<13.0a0,!=10.*]): "
                            )
                            filters["cuda_version"] = input_strip(">>> ")
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
            }

            def filter_version_major_minor(version_str):
                pattern = re.compile(r"([\d*]{1,3})\.([\d*]{1,3})(?:\.[a-zA-Z\d.*]+)*")
                return pattern.sub(shorten_version, version_str)

            clear_screen()
            pkginfos_list = _data_processing_transaction(user_options)
            _print_transcation(pkginfos_list, first_print=True)
            num_lines_2 = _get_user_options(user_options, pkginfos_list)
            while not user_options["exit"]:
                if filter_value := user_options["filters"]["python_version"]:
                    user_options["filters"]["python_version"] = filter_version_major_minor(filter_value)
                if filter_value := user_options["filters"]["cuda_version"]:
                    user_options["filters"]["cuda_version"] = filter_version_major_minor(filter_value)
                if user_options["need_reprint"]:
                    clear_screen()
                    pkginfos_list = _data_processing_transaction(user_options)
                    _print_transcation(pkginfos_list)
                else:
                    clear_lines_above(num_lines_2)
                    pkginfos_list = []
                num_lines_2 = _get_user_options(user_options, pkginfos_list)

        while True:
            search_pkgs_main(target_py_version)
            print()
            if target_py_version:
                print(f"(i) 是否继续为 Python {target_py_version} 查找包? [Y(回车)/n]")
            else:
                print("(i) 是否继续为所有 Python 版本查找包? [Y(回车)/n]")
            inp = input_strip("[(Y)/n] >>> ")
            if inp not in ("y", "Y", ""):
                break
        res = 1
    # 如果输入的是[H],则显示由"conda doctor"命令出具的Conda环境健康报告
    elif inp in ["H", "h"]:
        if not CONDA_VERSION or Version(CONDA_VERSION) < Version("23.5.0"):
            print(LIGHT_RED("[错误] conda doctor命令需要conda 23.5.0及以上版本支持,请在base环境升级conda后重试!"))
            print("升级conda命令: conda update -n base -c defaults conda")
            return 1
        print("(1) 请输入想要检查完整性的环境的编号(默认为全部),多个以空格隔开,以回车结束: ")
        inp = input_strip(f"[(ALL) | 1-{env_num}] >>> ")
        if inp.lower() in ["all", ""]:
            env_check_names = [i for i in env_namelist]
        else:
            env_check_nums = [int(i) - 1 for i in inp.split() if i.isdigit() and 1 <= int(i) <= env_num]
            env_check_names = [env_namelist[i] for i in env_check_nums]
        if os.name == "nt":  # 因为win下运行conda doctor时任何方式捕获输出，都会有未知编码错误，这是conda自身的bug
            for i, env_name in enumerate(env_check_names, 1):
                print(f"[{i}/{len(env_check_names)}] 正在检查环境{LIGHT_CYAN(env_name)}的健康情况...")
                command = get_cmd([f'conda doctor -n "{env_name}"'])
                print("-" * (fast_get_terminal_size().columns - 5))
                subprocess.run(command, shell=True)
                print("-" * (fast_get_terminal_size().columns - 5))
        else:

            async def check_environment_health(env_name):
                command = get_cmd([f'conda doctor -n "{env_name}"'])
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                stdout, _ = await proc.communicate()
                return stdout.decode("utf-8")

            async def async_check_main():
                tasks = []
                for env_name in env_check_names:
                    tasks.append(asyncio.create_task(check_environment_health(env_name), name=env_name))

                for i, task in enumerate(tasks, 1):
                    print(f"[{i}/{len(env_check_names)}] 正在检查环境{LIGHT_CYAN(task.get_name())}的健康情况...")
                    result = await task
                    print("-" * (fast_get_terminal_size().columns - 5))
                    print(result)
                    print("-" * (fast_get_terminal_size().columns - 5))

            asyncio.run(async_check_main())

        input_strip(f"{LIGHT_GREEN('[完成]')} 检查完毕,请按<回车键>继续...")
        res = 1
    # 如果输入的是[D],且为Windows，则计算所有环境的大小及真实磁盘占有量
    elif inp in ["D", "d"]:
        global ENV_SIZE_CALC_ENABLED_WIN
        ENV_SIZE_CALC_ENABLED_WIN = True
        clear_screen(hard=False)
        res = 1
    # 如果输入的是[=编号]，则浏览环境主目录
    elif inp.find("=") != -1:
        inp = int(inp[1:])
        env_name = env_namelist[inp - 1]
        print(LIGHT_GREEN(f"[提示] 已在文件资源管理器中打开环境{LIGHT_CYAN(env_name)}的主目录:"))
        env_path = env_pathlist[inp - 1]
        print(env_path)
        if os.name == "nt":
            subprocess.run(["explorer", env_path])
        else:
            subprocess.run(["xdg-open", env_path])
        res = 1
    # 如果输入的是[Q]，则退出
    elif inp in ["Q", "q", "\x03"]:
        res = 0
    # 如果输入的是数字[编号]，则进入对应的环境
    else:
        # 通过列表的索引值获取对应的环境名称
        env_name = env_namelist[int(inp) - 1]
        # 激活环境，然后进入命令行
        clear_screen()
        if os.name == "nt":
            conda_hook_path = os.path.join(CONDA_HOME, "shell", "condabin", "conda-hook.ps1")
            command = [
                "powershell",
                "-ExecutionPolicy",
                "ByPass",
                "-NoExit",
                "-Command",
                f'& "{conda_hook_path}" ; conda activate "{env_name}"',
            ]
            subprocess.run(command)
        else:
            LINUX_ACTIVATION_CMD = get_linux_activation_shell_cmd()
            cmd_str = (
                LINUX_ACTIVATION_CMD.replace("$", "\\$").replace('"', '\\"') + f' && conda activate "{env_name}"'
            )
            command = rf"""bash -c 'bash --init-file <(echo ". $HOME/.bashrc; {cmd_str}")' """
            subprocess.run(command, shell=True)

    return res


def main(workdir):
    global CONDA_HOME, IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION
    if CONDA_HOME == "error":
        if os.name == "nt":
            print("请输入Conda/Mamba发行版的安装路径,如C:\\Users\\USER_NAME\\anaconda3: ")
        else:
            print("请输入Conda/Mamba发行版的安装路径,如/home/USER_NAME/anaconda3: ")
        conda_prefix = input_strip(">>> ")
        if os.path.isdir(conda_prefix) and os.path.exists(os.path.join(conda_prefix, "conda-meta")):
            CONDA_HOME = conda_prefix
            IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = detect_conda_mamba_infos(CONDA_HOME)
        else:
            sys.exit(1)

    os.chdir(workdir)
    env_infolist_dict = get_env_infos()
    inp = show_info_and_get_input(env_infolist_dict)
    while do_correct_action(inp, env_infolist_dict):
        print()
        env_infolist_dict = get_env_infos()
        inp = show_info_and_get_input(env_infolist_dict)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Conda/Mamba发行版环境管理工具")
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
        help="Conda/Mamba发行版的安装路径,如C:\\Users\\USER_NAME\\miniforge3,/home/USER_NAME/miniconda3",
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
        help="探测并列出计算机中所有受支持的Conda/Mamba发行版",
    )
    parser.add_argument(
        "--delete-data-files",
        action="store_true",
        help=f"删除程序数据文件夹({LIGHT_CYAN(data_manager.program_data_home)})",
    )
    args = parser.parse_args()
    if args.delete_data_files:
        if os.path.exists(data_manager.program_data_home):
            rmtree(data_manager.program_data_home)
            print(LIGHT_GREEN(f"[提示] 程序数据文件夹({LIGHT_CYAN(data_manager.program_data_home)})已删除！"))
        else:
            print(LIGHT_YELLOW("[错误] 程序数据文件夹不存在！"))
        sys.exit(0)
    if args.detect_distribution:
        print("计算机中所有受支持的Conda/Mamba发行版如下:")
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
                        LIGHT_GREEN(detect_conda_mamba_infos(available_conda_homes[i])[1])
                        if detect_conda_mamba_infos(available_conda_homes[i])[1]
                        else LIGHT_RED("NOT supported".upper())
                    ),
                    (
                        LIGHT_GREEN(detect_conda_mamba_infos(available_conda_homes[i])[2])
                        if detect_conda_mamba_infos(available_conda_homes[i])[2]
                        else "-"
                    ),
                ]
            )
        table.align = "l"
        table.border = False
        print(table)
        sys.exit(0)
    if args.prefix is not None:
        if os.path.isdir(args.prefix) and os.path.exists(os.path.join(args.prefix, "conda-meta")):
            CONDA_HOME = args.prefix
            IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = detect_conda_mamba_infos(CONDA_HOME)
        else:
            print(YELLOW(f'[提示] 未在指定路径"{args.prefix}"检测到对应发行版，将使用默认发行版'))

    elif args.distribution_name is not None:
        CONDA_HOME, IS_MAMBA, MAMBA_VERSION, LIBMAMBA_SOLVER_VERSION, CONDA_VERSION = detect_conda_installation(
            args.distribution_name
        )
        if os.path.split(CONDA_HOME)[1] != args.distribution_name:
            print(YELLOW(f"[提示] 未检测到指定的发行版({args.distribution_name})，将使用默认发行版"))
    workdir = args.workdir if args.workdir is not None else USER_HOME
    if os.path.isdir(workdir):
        main(workdir)
    else:
        raise ValueError(LIGHT_RED("[错误] 传入的参数不是一个目录！"))

# ***** 版本更新日志 *****
# 2023-9-26 v0.1 稳定版
# 2023-9-27 v0.2 稳定版,增加了对Linux系统的全面适配
# 2023-9-27 23:29 v0.2.10 完全版,优化了一些细节
# 2023-9-28 v0.2.100 完全版,增加了探测所有可用发行版的功能，修复了一些错误
# 2023-9-28 16:19--20:08 v0.3 稳定完全版,优化显示模块,优化逻辑，修复小错误，全面完善功能
# 2023-9-28 22:50 v0.3.100 发行版,增加搜索包功能，增加退出功能
# 2023-9-29 中秋 验收完毕
# 2023-10-12 v0.5.0 大大增强了发行版的识别成功率
# 2024-3-16 v1.0.rc0 改善代码逻辑，修复若干问题，添加复制环境功能[P]，打开环境主目录功能[=编号]；优化使用体验
# 2024-4-1 v1.0 (Release) 全新的[S]搜索功能，臻品打造，全面重构了代码，完善了相应功能，优化了用户体验
# 2024-4-2 v1.0.1 fix bugs ; 2024-4-3 fix; 2024-4-4 增加健康报告[H]功能，优化主界面显示，fix; 2024-4-5 v1.0.6 (Release) fix bugs
# 2024-4-23 v1.7.beta 显示大量代码重构，函数逻辑优化；主界面显示优化，增加磁盘占用列显示 (支持统计所有环境的表观大小与实际磁盘占用)
# 2024-5-12 v1.7.rc1 优化界面显示，更加友好化的操作逻辑；优化环境大小统计功能；修复了一些bug
# 2024-5-15 v1.7.rc2 修复了一些bug；优化了一些显示与操作逻辑；
# 2024-5-16 ~ 2024-5-19 v1.7 (Release) 优化了搜索结果界面的显示，增加了适应终端宽度的功能; fix bugs; 正式发布版
# **********************
# 致谢：OpenAI ChatGPT，Github Copilot
