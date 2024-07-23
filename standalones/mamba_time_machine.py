"""
Conda/Mamba Time Machine

This script filters all repodata.json files in the pkgs/cache directory of conda/mamba distributions, 
retaining only the packages with timestamps earlier than the specified date.

Usage:
1. Ensure all the repodata files in the pkgs/cache directory are the latest synchronized from online sources.
2. Modify the custom configuration (maximum date threshold and pkgs/cache directory path) and run this script.
3. Use the `conda/mamba install/create ... -C` command to enforce using the local index cache, as if installing on the specified date.
"""

import json
import os
import re
from datetime import datetime


def find_matching_files(directory):
    """查找指定目录下的所有形如 cb90b959.json 的文件名。"""
    pattern = re.compile(r"^[a-f0-9]{8}\.json$")
    files = os.listdir(directory)
    matching_files = [f for f in files if pattern.match(f)]

    return matching_files


def filter_repodata(repodata_file, timestamp_str):
    """
    根据时间戳过滤 repodata.json 文件，仅保留时间戳早于指定时间戳的包。

    参数:
    - json_file: repodata.json 文件路径
    - timestamp_str: 时间戳阈值，格式为 "YYYY-MM-DD"
    """
    # 将时间戳阈值转换为 ms 级时间戳
    timestamp_threshold = datetime.strptime(timestamp_str, "%Y-%m-%d").timestamp() * 1000

    with open(repodata_file, "r") as file:
        data = json.load(file)

    num_original_packages = len(data.get("packages", {}))
    # 过滤 packages 部分
    filtered_packages = {
        pkg: info
        for pkg, info in data.get("packages", {}).items()
        if info.get("timestamp", 0) <= timestamp_threshold
    }
    num_original_packages_conda = len(data.get("packages.conda", {}))
    # 过滤 packages.conda 部分
    filtered_packages_conda = {
        pkg: info
        for pkg, info in data.get("packages.conda", {}).items()
        if info.get("timestamp", 0) <= timestamp_threshold
    }

    data["packages"] = filtered_packages
    data["packages.conda"] = filtered_packages_conda

    with open(repodata_file, "w") as file:
        json.dump(data, file)

    print(
        f"Filtered {repodata_file} created with {len(filtered_packages)} packages ({num_original_packages} original) and {len(filtered_packages_conda)} .conda packages ({num_original_packages_conda} original)."
    )


def update_state_json(repodata_file):
    """更新 repodata.json 文件一一对应的 *.state.json 文件的 mtime_ns 和 size 字段。"""
    state_file = repodata_file.replace(".json", ".state.json")

    mtime_ns = os.stat(repodata_file).st_mtime_ns
    repodata_size = os.path.getsize(repodata_file)

    if os.path.exists(state_file):
        with open(state_file, "r") as file:
            state_data = json.load(file)

        if state_data["mtime_ns"] < 0:  # 修复Linux下可能的负数时间戳
            fixed_mtime_ns = mtime_ns - 6437664000000000000
        else:
            fixed_mtime_ns = mtime_ns

        state_data["mtime_ns"] = fixed_mtime_ns
        state_data["size"] = repodata_size

        with open(state_file, "w") as file:
            json.dump(state_data, file, indent=4)

        print(f"Updated {state_file} with mtime_ns={fixed_mtime_ns} and size={repodata_size}.")


def main():
    repodata_files = [os.path.join(pkgs_cache_dir, f) for f in find_matching_files(pkgs_cache_dir)]

    print(
        f"1. Processing {len(repodata_files)} repodata.json files in '{pkgs_cache_dir}' with a maximum date threshold of '{date_max_threshold}'..."
    )
    for idx, repodata_file in enumerate(repodata_files, 1):
        print(f"  [{idx}/{len(repodata_files)}] ", end="")
        filter_repodata(repodata_file, date_max_threshold)

    print("2. Cleaning up .solv files...")
    # 2. 删除 pkgs/cache 目录下的所有 .solv 文件
    solv_files = [os.path.join(pkgs_cache_dir, f) for f in os.listdir(pkgs_cache_dir) if f.endswith(".solv")]
    for solv_file in solv_files:
        os.remove(solv_file)

    print("3. Updating .state.json files with new mtime_ns and size...")
    # 3. 更改 .state.json 文件
    for idx, repodata_file in enumerate(repodata_files, 1):
        print(f"  [{idx}/{len(repodata_files)}] ", end="")
        update_state_json(repodata_file)

    print("All done!")


# ----- 以下为自定义配置 -----
date_max_threshold = "2023-05-06"
pkgs_cache_dir = "/home/username/miniforge3/pkgs/cache"

if __name__ == "__main__":
    main()
