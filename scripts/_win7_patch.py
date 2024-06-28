import re
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ColorStr import *


def patch_script(source_file, patched_file, patch_dict):
    with open(source_file, "r", encoding="utf-8") as f:
        file_content = f.read()

    patch_counts = {}

    for original, replacement in patch_dict.items():
        patched_content, count = re.subn(re.escape(original), replacement, file_content)
        patch_counts[original] = count
        file_content = patched_content

    with open(patched_file, "w", encoding="utf-8") as f:
        f.write(file_content)

    return patch_counts


patch_MyTools_dict = {
    'top_bottom_line_char: Optional[str] = "─",': 'top_bottom_line_char: Optional[str] = "-",',  # 解决Win7终端 ─ 占2格
    "def get_printed_line_count(text: str) -> int:": r"""def get_printed_line_count(text: str) -> int:
    return text.count("\\n") + 1""",  # 解决Win7终端一行显示不全，导致行数计算错误
    "line_length = min(table_width, terminal_width)": "line_length = table_width",
    "return input(prompt).strip()": """print(prompt, end="")
    return input().strip()""",  # 解决Win7终端input()无法显示带颜色的提示信息
}
patch_conda_env_manager_dict = {
    r'''if not "".join(cmdlist).isascii():
            output = subprocess.run("chcp", capture_output=True, shell=True, text=True).stdout
            now_codepage = re.search(r"\d+", output).group(0)  # type: ignore
            echo_lines = f"({'&'.join(['echo.']*30)})"  # Only work for Windows Terminal
            cmd = f"{echo_lines} && chcp 65001 && " + cmd + f" && {echo_lines} && chcp {now_codepage}"''': "",  # 解决Win7终端chcp无效和莫名异常
    """and "#" not in env_name""": """and "#" not in env_name
        and re.match(r"^[a-zA-Z0-9_-]+$", env_name)""",  # 环境名称只能包含字母、数字、下划线和短横线
}

sorted_keys = sorted(patch_MyTools_dict.keys(), key=lambda x: len(x), reverse=True)
sorted_dict = {key: patch_MyTools_dict[key] for key in sorted_keys}
patch_MyTools_dict = sorted_dict

sorted_keys = sorted(patch_conda_env_manager_dict.keys(), key=lambda x: len(x), reverse=True)
sorted_dict = {key: patch_conda_env_manager_dict[key] for key in sorted_keys}
patch_conda_env_manager_dict = sorted_dict

if __name__ == "__main__":
    # 1. Patch MyTools.py
    input_file = output_file = "MyTools.py"
    replacements = patch_script(input_file, output_file, patch_MyTools_dict)
    succeed = True
    for _, count in replacements.items():
        if count == 0:
            succeed = False
            break
    if succeed:
        print(LIGHT_GREEN("All patches were applied successfully to MyTools.py!"))
    else:
        print(LIGHT_RED("Some patches failed to apply to MyTools.py!"))
        idx = 0
        for key, count in replacements.items():
            if count == 0:
                idx += 1
                print(LIGHT_YELLOW(f"[{idx}] Failed to patch:"), key)

    # 2. Patch conda_env_manager.py
    input_file = output_file = "conda_env_manager.py"
    replacements = patch_script(input_file, output_file, patch_conda_env_manager_dict)
    succeed = True
    for _, count in replacements.items():
        if count == 0:
            succeed = False
            break
    if succeed:
        print(LIGHT_GREEN("All patches were applied successfully to conda_env_manager.py!"))
    else:
        print(LIGHT_RED("Some patches failed to apply to conda_env_manager.py!"))
        idx = 0
        for key, count in replacements.items():
            if count == 0:
                idx += 1
                print(LIGHT_YELLOW(f"[{idx}] Failed to patch:"), key)
