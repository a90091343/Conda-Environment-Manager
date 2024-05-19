# v1.0.1
import re
from ColorStr import *


def translate_script(input_file, output_file, translation_dict):
    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    replacements = {}

    for chinese, english in translation_dict.items():
        replaced_content, count = re.subn(re.escape(chinese), english, content)
        replacements[chinese] = count
        content = replaced_content

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    return replacements


# Thanks to GitHub Copilot for providing the original version of the translation_dict.
translation_dict = {
    "无法读取快捷方式文件：": "Unable to read shortcut file: ",
    "[错误] 未检测到Conda/Mamba发行版的安装，请先安装相关发行版后再运行此脚本！": "[Error] No Conda/Mamba distribution installation detected, please install the relevant distribution before running this script!",
    ",以回车结束:": ", press <Enter> to end: ",
    "请输入": "Please input ",
    "输入错误次数({error_count})过多，已退出！": "Too many input errors ({error_count}), exited!",
    "对应指令": "corresponding instructions",
    "[错误] 未检测到有效的环境编号！": "[Error] No valid environment number detected!",
    "(1) 请输入想要删除的环境的编号(或all=全部),多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to delete (or all for all envs), separated by spaces, and press <Enter> to end: ",
    "(2) 确认删除以上环境吗？[y(回车)/n]": "(2) Are you sure you want to delete the above environment(s)? [y(Enter)/n]",
    "[警告] base环境未安装Jupyter,无法管理相关环境的jupyter注册,请在主界面按[J]以安装": "[Warning] The base environment is NOT installed with Jupyter, and cannot manage the Jupyter registration of related environments. Please press [J] on the main interface to install",
    "(1) 请输入想要新建的环境的名称,以回车结束: ": "(1) Please enter the name of the environment you want to create, and press <Enter> to end: ",
    "新环境名称": "New environment name ",
    "已存在或不符合规范": " Already exists or does not meet the specifications",
    "，请重新输入: ": ", please re-enter: ",
    "已自动指定python版本={inp2}": " Python version has been automatically specified={inp2}",
    "(2) 请指定python版本(为空默认最新版)，以回车结束:": "(2) Please specify the python version (leave blank for the latest version), and press <Enter> to end:",
    "[提示]": "[Tip]",
    "安装失败！": "Installation failed!",
    "(3a) 是否启用更多的源重新安装[(Y)/n] >>> ": "(3a) Do you want to enable more sources to reinstall [(Y)/n] >>> ",
    " 常用第三方源有:": " Common third-party sources include:",
    "(3b) 请输入更多的源,以空格隔开: ": "(3b) Please enter more sources, separated by spaces: ",
    "[提示] 该环境中未检测到ipykernel包，正在为环境安装ipykernel包...": "[Tip] The ipykernel package is NOT detected in the environment, and the ipykernel package is being installed for the environment...",
    "(1) 请输入想要重命名的环境的编号,多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to rename, separated by spaces, and press <Enter> to end: ",
    "(2) 确认重命名以上环境吗？[y(回车)/n]": "(2) Are you sure you want to rename the above environment(s)? [y(Enter)/n]",
    "[提示] 检测到原环境的Jupyter注册已失效，正在为新环境重新注册Jupyter": "[Tip] The Jupyter registration of the original environment has Expired, and Jupyter is being re-registered for the new environment",
    "已重新注册新环境{ii}的Jupyter": "Jupyter of the new environment {ii} has been re-registered",
    "(1) 请输入想要复制的环境的编号,多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to copy, separated by spaces, and press <Enter> to end: ",
    "(2) 确认复制以上环境吗？[y(回车)/n]": "(2) Are you sure you want to copy the above environment(s)? [y(Enter)/n]",
    "[提示] 未检测到jupyter命令，正尝试向base环境安装ipykernel...": "[Tip] The jupyter command is NOT detected, and an attempt is being made to install ipykernel to the base environment...",
    "[提示] {LIGHT_CYAN('base')}环境中ipykernel安装成功！": "[Tip] ipykernel is successfully installed in the {LIGHT_CYAN('base')} environment!",
    " (已失效)": " (Expired)",
    "(0a) 确认清理以上失效项吗？[y(回车)/n]": "(0a) Are you sure you want to clear the above Expired registrations? [y(Enter)/n]",
    "需要查看及回退历史版本的环境编号": "the number of environment to view and roll back to historical version",
    "],以回车结束: ": "], and press <Enter> to end: ",
    "[rev后的数字] >>> ": "[Number after rev] >>> ",
    "[提示] 根据历史记录已自动启用附加源:": "[Tip] Additional sources have been automatically enabled based on the history:",
    "(包文件夹)": "(Package folder)",
    " 及 Pip 缓存情况": " and Pip cache situation",
    "总缓存大小: ": "Total cache size: ",
    "(1) 请输入Y(回车:全部清理)/N,或想要清理的缓存项编号,多个以空格隔开: ": "(1) Please enter Y(<Enter>: clean all)/N, or the number(s) of the cache item(s) you want to clean, separated by spaces: ",
    "输入": "Input ",
    "应为空或Y或N或数字[1-5]的以空格隔开的组合,请重新输入: ": " should be a combination of empty, Y, N, or numbers [1-5] separated by spaces, please re-enter: ",
    "[错误] ": "[Error] ",
    "[错误] mamba clean --all --dry-run --json命令输出有误！无法解析,输出如下:": "[Error] The mamba clean --all --dry-run --json command output is incorrect! Unable to parse, the output is as follows:",
    "[提示] 已启动默认清理程序": "[Tip] The default cleaning program has been started",
    "(1) 确认清空所有Conda/pip缓存吗？[y(回车)/n]": "(1) Are you sure you want to clear all Conda/pip caches? [y(Enter)/n]",
    "[提示] 慎用，请仔细检查更新前后的包对应源的变化！": "[Tip] Use with caution, please carefully check the changes in the corresponding sources of the package before and after the update!",
    "(1) 请输入想要更新的环境的编号(或all=全部),多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to update (or all for all envs), separated by spaces, and press <Enter> to end: ",
    "(2) 确认更新以上环境吗？[y(回车)/n]": "(2) Are you sure you want to update the above environment(s)? [y(Enter)/n]",
    "[警告] 检测到如下由Pip管理的包，更新可能会出现问题！": "[Warning] The following packages managed by Pip are detected, and problems may occur during the update!",
    "[提示] 已自动启用附加源: ": "[Tip] Additional sources have been automatically enabled: ",
    "[提示] 您的conda-libmamba-solver未安装或版本过低，无法使用搜索功能，请将conda-libmamba-solver升级到23.9及以上版本": "[Tip] Your conda-libmamba-solver is NOT installed or the version is too low, and the search function cannot be used. Please upgrade conda-libmamba-solver to version 23.9 or higher",
    "[提示] 您的conda版本过低，建议先升级conda到23.10及以上版本": "[Tip] Your conda version is too low, it is recommended to upgrade conda to version 23.10 or higher first",
    "升级conda命令: ": "Upgrade conda command: ",
    "升级libmamba命令: ": "Upgrade libmamba command: ",
    "安装libmamba命令: ": "Install libmamba command: ",
    "请在base环境下执行以上命令。": "Please execute the above commands in the base environment.",
    "(1) 请指定python版本(为空默认全版本)，以回车结束:": "(1) Please specify the python version (leave blank for all versions), and press <Enter> to end:",
    "[提示1] 搜索默认启用的源为": "[Tip1] The default enabled source for search is ",
    "如需额外源请在末尾添加 -c 参数": " If you need additional sources, please add the -c parameter at the end",
    "[提示2] 可用mamba repoquery depends/whoneeds命令列出包的依赖项/列出需要给定包的程序包": "[Tip2] The mamba repoquery depends/whoneeds command can be used to list the dependencies of the package/list the packages that need the given package",
    "[提示3] 搜索语法为Name=Version=Build,后两项可选 (示例:numpy>1.17,<1.19.2 *numpy*=1.17.*=py38*)": "[Tip3] The search syntax is Name=Version=Build, the last two items are optional (example: numpy>1.17,<1.19.2 *numpy*=1.17.*=py38*)",
    "        (详见https://github.com/conda/conda/blob/main/docs/source/user-guide/concepts/pkg-search.rst)": "        (For details, see https://github.com/conda/conda/blob/main/docs/source/user-guide/concepts/pkg-search.rst)",
    "(2) 请输入想要搜索的包 (适用于Python {target_py_version}),以回车结束:": "(2) Please enter the package you want to search (for Python {target_py_version}), and press <Enter> to end:",
    "(2) 请输入想要搜索的包 (适用于全部Python版本),以回车结束:": "(2) Please enter the package you want to search (for all Python versions), and press <Enter> to end:",
    "[提示] 检测到-c参数，已自动添加相应源: ": "[Tip] The -c parameter is detected, and the corresponding source has been automatically added: ",
    "[错误] 搜索结果解析失败!原始结果如下:": "[Error] Search result parsing failed! The original result is as follows:",
    "[警告] 未搜索到任何相关包({round(time.time() - t0_search, 2)} s)！": "[Warning] No relevant packages found ({round(time.time() - t0_search, 2)} s)!",
    "[提示] 安装命令已拷贝到剪贴板！": "[Tip] The installation command has been copied to the clipboard!",
    "(i) 请输入要跳转到原始显示模式并过滤的包版本对应编号:": "(i) Please enter the corresponding number of the specific package version to jump to Original display mode and filter:",
    "[1] 概览": "[1] Overview",
    "[2] 精简显示": "[2] Simplified",
    "[3] 原始显示": "[3] Original",
    "[F] 过滤器": "[F] Filter",
    "[S] 排序": "[S] Sort",
    "[V] 查看包详情": "[V] View package details",
    "[V] 选择以过滤原始显示": "[V] Filter the Original",
    "[M] 合并版本号": "[M] Merge versions",
    "[R] 倒序显示": "[R] Reverse",
    "[Esc] 退出": "[Esc] Exit",
    "[排序] 依据为 ": "[Sort] Based on ",
    "(按↑ |↓ 键切换为升序|降序)": "(Press ↑ |↓ to switch order)",
    "  ;  [过滤器] ": "  ;  [Filter] ",
    "[过滤器] ": "[Filter] ",
    "(i) 请按下排序依据对应的序号: ": "(i) Please press the corresponding number of the sorting basis: ",
    "[1] 名称/版本": "[1] Name/Version",
    "[3] Python版本": "[3] Python version",
    "[4] CUDA版本": "[4] CUDA version",
    "[5] 大小": "[5] Size",
    "[6] 时间戳": "[6] Timestamp",
    "(i) 请按下过滤目标对应的序号: ": "(i) Please press the corresponding number of the filter target: ",
    "[1] 名称": "[1] Name",
    "[2] 版本": "[2] Version",
    "[4] Python版本": "[4] Python version",
    "[5] CUDA版本": "[5] CUDA version",
    "[6] 只显示CUDA": "[6] Show only CUDA",
    "(ii) 请输入名称过滤器(支持通配符*): ": "(ii) Please enter the name filter (supports wildcard *): ",
    "(ii) 请输入版本过滤器(支持比较式[示例: 1.19|<2|>=2.6,<2.10.0a0,!=2.9.*]): ": "(ii) Please enter the version filter (supports comparison expression [example: 1.19|<2|>=2.6,<2.10.0a0,!=2.9.*]): ",
    "(ii) 请输入Channel过滤器(支持通配符*): ": "(ii) Please enter the Channel filter (supports wildcard *): ",
    "(ii) 请输入Python版本过滤器(支持主次版本号比较式[示例: >=3.11|3.7|!=2.*,<3.10a0,!=3.8]): ": "(ii) Please enter the Python version filter (supports major and minor version comparison expressions [example: >=3.11|3.7|!=2.*,<3.10a0,!=3.8]): ",
    "(ii) 请输入CUDA版本过滤器(支持主次版本号比较式[示例: !=12.2,<=12.3|>=9,<13.0a0,!=10.*]): ": "(ii) Please enter the CUDA version filter (supports major and minor version comparison expressions [example: !=12.2,<=12.3|>=9,<13.0a0,!=10.*]): ",
    "搜索完成({round(time.time() - t0_search, 2)} s)！": "Search completed ({round(time.time() - t0_search, 2)} s)!",
    "(i) 是否继续为 Python {target_py_version} 查找包? [Y(回车)/n]": "(i) Do you want to continue searching for packages for Python {target_py_version}? [Y(Enter)/n]",
    "(i) 是否继续为所有 Python 版本查找包? [Y(回车)/n]": "(i) Do you want to continue searching for packages for all Python versions? [Y(Enter)/n]",
    "[错误] conda doctor命令需要conda 23.5.0及以上版本支持,请在base环境升级conda后重试!": "[Error] The conda doctor command requires conda 23.5.0 and above to support, please upgrade conda in the base environment and try again!",
    "(1) 请输入想要检查完整性的环境的编号(默认为全部),多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to check the integrity (default is all), separated by spaces, and press <Enter> to end: ",
    "请输入Conda/Mamba发行版的安装路径,如C:\\\\Users\\\\USER_NAME\\\\anaconda3: ": "Please enter the installation path of the Conda/Mamba distribution, such as C:\\\\\\\\Users\\\\\\\\USER_NAME\\\\\\\\anaconda3: ",
    "请输入Conda/Mamba发行版的安装路径,如/home/USER_NAME/anaconda3: ": "Please enter the installation path of the Conda/Mamba distribution, such as /home/USER_NAME/anaconda3: ",
    "Conda/Mamba发行版环境管理工具": "Conda/Mamba distribution environment management tool",
    "打开的路径，默认为当前路径": "The opened path, default is the current path",
    "Conda/Mamba发行版的安装路径,如C:\\\\Users\\\\USER_NAME\\\\miniforge3,/home/USER_NAME/miniconda3": "Installation path of the Conda/Mamba distribution, such as C:\\\\\\\\Users\\\\\\\\USER_NAME\\\\\\\\miniforge3,/home/USER_NAME/miniconda3",
    "发行版的名称,支持miniforge3,anaconda3,miniconda3,mambaforge,miniforge-pypy3,mambaforge-pypy3,默认顺序如前": "The name of the distribution, supports miniforge3,anaconda3,miniconda3,mambaforge,miniforge-pypy3,mambaforge-pypy3, the default order is as before",
    "探测并列出计算机中所有受支持的Conda/Mamba发行版": "Detect and list all supported Conda/Mamba distributions on the computer",
    "计算机中所有受支持的Conda/Mamba发行版如下:": "All supported Conda/Mamba distributions on the computer are as follows:",
    '[提示] 未在指定路径"{args.prefix}"检测到对应发行版，将使用默认发行版': '[Tip] The corresponding distribution was NOT detected in the specified path "{args.prefix}", and the default distribution will be used',
    "[提示] 未检测到指定的发行版({args.distribution_name})，将使用默认发行版": "[Tip] The specified distribution ({args.distribution_name}) was NOT detected, and the default distribution will be used",
    "[错误] 传入的参数不是一个目录！": "[Error] The passed parameter is NOT a directory!",
    "输入错误{LIGHT_RED(error_count)}次，请重新输入: ": "Input error {LIGHT_RED(error_count)} times, please re-enter: ",
    '"输入错误达到最大次数({LIGHT_RED(max_errors)})，程序退出"': '"The maximum number of input errors ({LIGHT_RED(max_errors)}) has been reached, and the program exits"',
    "{LIGHT_YELLOW('[提示]')} 正在计算环境大小及磁盘占用情况，请稍等...": "{LIGHT_YELLOW('[Tip]')} Calculating the environment size and disk usage, please wait...",
    "{prefix_str}输入错误({RED(error_count)})次!请重新输入{askstr}": "{prefix_str}Input error ({RED(error_count)}) times! Please re-enter{askstr}",
    " 目前管理的 Conda 发行版是 {CONDA_HOME} ": " The Conda distribution currently managed is {CONDA_HOME} ",
    "[提示] 检测到多个发行版安装:": "[Tip] Multiple distributions are detected:",
    "[{i}]\\t{os.path.split(condapath)[1]}\\t{condapath} (当前)": "[{i}]\\\\t{os.path.split(condapath)[1]}\\\\t{condapath} (Current)",
    "[提示] 检测到如下其它发行版的环境,或未安装在规范目录(envs)下的环境,将不会被显示与管理:": "[Tip] The environments of the following other distributions are detected, or the environments that are NOT installed in the standard directory (envs) will NOT be displayed and managed:",
    "{' 以上信息仅在不受支持的环境有变化时显示 ':*^55}": "{' The above information is displayed only when there are changes in unsupported environments ':*^55}",
    '允许的操作指令如下 (按{BOLD(YELLOW("[Q]"))}以退出, {BOLD(LIGHT_WHITE("<Tab>"))}切换当前显示模式 {BOLD(LIGHT_CYAN(display_mode))}):': 'Allowed commands (press {BOLD(YELLOW("[Q]"))} to quit, {BOLD(LIGHT_WHITE("<Tab>"))} to switch display mode {BOLD(LIGHT_CYAN(display_mode))}):',
    '激活环境对应命令行输入编号{BOLD(LIGHT_YELLOW(f"[1-{env_num}]"))};浏览环境主目录输入{BOLD(LIGHT_GREEN("[=编号]"))};': 'Activate environment by {BOLD(LIGHT_YELLOW(f"[1-{env_num}]"))}; Browse environment directory by {BOLD(LIGHT_GREEN("[=Number]"))};',
    '删除环境按{BOLD(RED("[-]"))};新建环境按{BOLD(LIGHT_GREEN("[+]"))};重命名环境按{BOLD(LIGHT_BLUE("[R]"))};复制环境按{BOLD(LIGHT_CYAN("[P]"))};': '{BOLD("For env(s)")}: Delete by {BOLD(RED("[-]"))}; Create new by {BOLD(LIGHT_GREEN("[+]"))}; Rename by {BOLD(LIGHT_BLUE("[R]"))}; Copy by {BOLD(LIGHT_CYAN("[P]"))};',
    '显示并回退至环境的历史版本按{BOLD(LIGHT_MAGENTA("[V]"))};': 'View and roll back to historical version of the environment by {BOLD(LIGHT_MAGENTA("[V]"))};',
    '更新环境的所有 Conda 包按{BOLD(GREEN("[U]"))};': 'Update all Conda packages of environment(s) by {BOLD(GREEN("[U]"))};',
    '查看及清空 Conda/pip 缓存按{BOLD(LIGHT_RED("[C]"))};': 'Clean or view Conda/pip cache by {BOLD(LIGHT_RED("[C]"))};',
    '注册 Jupyter 内核按{BOLD(CYAN("[I]"))};显示、管理及清理 Jupyter 内核按{BOLD(LIGHT_BLUE("[J]"))};': '{BOLD("For Jupyter kernel(s)")}: Register by {BOLD(CYAN("[I]"))}; Display, manage, and clean by {BOLD(LIGHT_BLUE("[J]"))};',
    '检查环境完整性并显示健康报告按{BOLD(LIGHT_GREEN("[H]"))};': 'Check the integrity of env(s) and display health report by {BOLD(LIGHT_GREEN("[H]"))};',
    '搜索 Conda 软件包按{BOLD(LIGHT_CYAN("[S]"))};': 'Search for Conda packages by {BOLD(LIGHT_CYAN("[S]"))};',
    "(仅限Windows) 显示环境大小及磁盘占用情况按{LIGHT_GREEN('[D]')};": "(Windows only) Display the size and disk usage of envs by {LIGHT_GREEN('[D]')};",
    "[警告] base环境未安装Jupyter,无法管理相关环境的jupyter内核注册,请在主界面按[J]以安装": "[Warning] The base environment is NOT installed with Jupyter, and cannot manage the Jupyter kernel registration of related environments. Please press [J] on the main interface to install",
    "[提示] 已清除卸载的环境 {LIGHT_CYAN(i)} 的Jupyter内核注册": "[Tip] The Jupyter kernel registration of the uninstalled environment {LIGHT_CYAN(i)} has been cleared",
    "(2)[提示] 检测到环境名称{LIGHT_CYAN(inp1)}符合python环境命名规范,": "(2)[Tip] The environment name {LIGHT_CYAN(inp1)} meets the naming specifications of Python environments,",
    "(3) 请指定预安装参数(如{LIGHT_YELLOW('spyder')}包等,{LIGHT_GREEN('-c nvidia')}源等,以空格隔开)，以回车结束:": "(3) Please specify the pre-installed parameters (such as the {LIGHT_YELLOW('spyder')} package, {LIGHT_GREEN('-c nvidia')} source, etc., separated by spaces), and press <Enter> to end:",
    ' 若输入\\"{LIGHT_GREEN(\'--+\')}\\",则等效于预安装\\"{LIGHT_YELLOW(pre_install_pkgs)}\\"包(并将该环境的Jupyter内核注册到用户)': ' If \\\\"{LIGHT_GREEN(\'--+\')}\\\\" is entered, it is equivalent to pre-installing the \\\\"{LIGHT_YELLOW(pre_install_pkgs)}\\\\" package (and registering the Jupyter kernel of the environment to the user)',
    "(3c) 已将{LIGHT_GREEN(inp_sources)}添加为新环境{inp1}的默认源": "(3c) {LIGHT_GREEN(inp_sources)} has been added as the default source for the new environment {inp1}",
    "(i) 检测到环境名{LIGHT_CYAN(inp1)}存在非规范字符,请重新取Jupyter内核的注册名(非显示名称):": "(i) Non-standard characters are detected in the environment name {LIGHT_CYAN(inp1)}, please re-enter the registration name of the Jupyter kernel (not the display name):",
    "jupyter注册名称{LIGHT_YELLOW(input_str)}": "Jupyter registration name {LIGHT_YELLOW(input_str)}",
    "不全符合[A-Za-z0-9._-]": "Does NOT fully meet [A-Za-z0-9._-]",
    ",请重新为{LIGHT_CYAN(inp1)}的jupyter内核取注册名: ": ", please re-enter the registration name of the Jupyter kernel for {LIGHT_CYAN(inp1)}: ",
    "(4) 请输入此环境注册的Jupyter内核的显示名称(为空使用默认值):": "(4) Please enter the display name of the Jupyter kernel registered for this environment (leave blank to use the default value):",
    "(1) 请输入想要将Jupyter内核注册到用户的环境编号(或all=全部),多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to register the Jupyter kernel to the user (or all for all envs), separated by spaces, and press <Enter> to end: ",
    "(2) 确认注册以上环境的Jupyter内核到用户吗？[y(回车)/n]": "(2) Are you sure you want to register the Jupyter kernel of the above environment to the user? [y(Enter)/n]",
    "(i) 检测到环境名{LIGHT_CYAN(env_name)}存在非规范字符,请重新取Jupyter内核的注册名(非显示名称):": "(i) Non-standard characters are detected in the environment name {LIGHT_CYAN(env_name)}, please re-enter the registration name of the Jupyter kernel (not the display name):",
    ",请重新为{LIGHT_CYAN(env_name)}的jupyter内核取注册名: ": ", please re-enter the registration name of the Jupyter kernel for {LIGHT_CYAN(env_name)}: ",
    "(3.{idx}) 请输入环境{LIGHT_CYAN(env_name)}注册的Jupyter内核的显示名称(为空使用默认值):": "(3.{idx}) Please enter the display name of the Jupyter kernel registered for the environment {LIGHT_CYAN(env_name)} (leave blank to use the default value):",
    "(3.{idx}) 请输入环境{LIGHT_CYAN(env_name)}重命名后的环境名称:": "(3.{idx}) Please enter the name of the environment after renaming the environment {LIGHT_CYAN(env_name)}:",
    ",请重新为{LIGHT_CYAN(env_name)}重命名: ": ", please re-enter the renaming for {LIGHT_CYAN(env_name)}: ",
    "(i) 检测到新环境名{LIGHT_CYAN(ii)}存在非规范字符,请重新取Jupyter内核的注册名(非显示名称):": "(i) Non-standard characters are detected in the new environment name {LIGHT_CYAN(ii)}, please re-enter the registration name of the Jupyter kernel (not the display name):",
    ",请重新为{LIGHT_CYAN(ii)}的jupyter内核取注册名: ": ", please re-enter the registration name of the Jupyter kernel for {LIGHT_CYAN(ii)}: ",
    "(4) 请输入注册的Jupyter内核的显示名称(为空使用默认值):": "(4) Please enter the display name of the registered Jupyter kernel (leave blank to use the default value):",
    "(3.{idx}) 请输入环境{LIGHT_CYAN(env_name)}复制后的环境名称(为空使用默认值):": "(3.{idx}) Please enter the name of the environment after copying the environment {LIGHT_CYAN(env_name)} (leave blank to use the default value):",
    ",请重新为{LIGHT_CYAN(env_name)}命名: ": ", please re-enter the renaming for {LIGHT_CYAN(env_name)}: ",
    "[提示] 安装失败，请在 base 环境中手动安装ipykernel后重试！": "[Tip] Installation failed, please manually install ipykernel in the base environment and try again!",
    "当前用户已注册的Jupyter内核如下:": "The Jupyter kernels registered by the current user are as follows:",
    "[提示] 未检测到任何Jupyter内核注册！": "[Tip] No Jupyter kernel registration detected!",
    "(1) 请输入想要删除的Jupyter内核的编号(或all=全部),多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of Jupyter kernel(s) you want to delete (or all for all kernels), separated by spaces, and press <Enter> to end: ",
    "[错误] 未检测到有效的Jupyter内核编号！": "[Error] No valid Jupyter kernel number detected!",
    "(2) 确认删除以上Jupyter内核注册吗？[y(回车)/n]": "(2) Are you sure you want to delete the above Jupyter kernel registration? [y(Enter)/n]",
    "环境{LIGHT_CYAN(env_name)}的历史版本如下:": "The historical versions of the environment {LIGHT_CYAN(env_name)} are as follows:",
    "(2) 请输入环境{LIGHT_CYAN(env_name)}的历史版本编号[": "(2) Please enter the historical version number of the environment {LIGHT_CYAN(env_name)} [",
    "[{idx}/{len(env_names)}] 正在更新环境{LIGHT_CYAN(env_name)}的所有包...": "[{idx}/{len(env_names)}] Updating all packages of the environment {LIGHT_CYAN(env_name)}...",
    "(i) 是否继续更新环境{LIGHT_CYAN(env_name)}？[y/n(回车)]": "(i) Do you want to continue updating the environment {LIGHT_CYAN(env_name)}? [y/n(Enter)]",
    '"输入" + LIGHT_RED("不能为空") + ",请重新输入: "': '"Input" + LIGHT_RED(" cannot be empty") + ", please re-enter: "',
    "正在搜索({LIGHT_CYAN(inp)})...": "Searching ({LIGHT_CYAN(inp)})...",
    "(i) 请输入要查看详细信息的包对应编号(带{LIGHT_CYAN('=')}号则显示安装命令行并拷贝到剪贴板): ": "(i) Please enter the corresponding number of the package to view detailed information (with {LIGHT_CYAN('=')} to display the installation command line and copy to the clipboard): ",
    "[{key}]包{LIGHT_CYAN(pkginfo_dict['name'])} {LIGHT_GREEN(pkginfo_dict['version'])}的详细信息如下": "[{key}] The detailed information of the package {LIGHT_CYAN(pkginfo_dict['name'])} {LIGHT_GREEN(pkginfo_dict['version'])} is as follows",
    "对于{LIGHT_CYAN(inp)},共找到{LIGHT_CYAN(len(pkginfos_list_raw))}个相关包,搜索结果如上": "For {LIGHT_CYAN(inp)}, a total of {LIGHT_CYAN(len(pkginfos_list_raw))} relevant packages were found, and the search results are as above",
    "[{i}/{len(env_check_names)}] 正在检查环境{LIGHT_CYAN(env_name)}的健康情况...": "[{i}/{len(env_check_names)}] Checking the health of the environment {LIGHT_CYAN(env_name)}...",
    "[{i}/{len(env_check_names)}] 正在检查环境{LIGHT_CYAN(task.get_name())}的健康情况...": "[{i}/{len(env_check_names)}] Checking the health of the environment {LIGHT_CYAN(task.get_name())}...",
    "{LIGHT_GREEN('[完成]')} 检查完毕,请按<回车键>继续...": "{LIGHT_GREEN('[Done]')} Check completed, please press <Enter> to continue...",
    "[提示] 已在文件资源管理器中打开环境{LIGHT_CYAN(env_name)}的主目录:": "[Tip] The main directory of the environment {LIGHT_CYAN(env_name)} has been opened in the file explorer:",
    '"删除程序数据文件夹({LIGHT_CYAN(data_manager.program_data_home)})"': '"Delete the program data folder ({LIGHT_CYAN(data_manager.program_data_home)})"',
    "[提示] 程序数据文件夹({LIGHT_CYAN(data_manager.program_data_home)})已删除！": "[Tip] The program data folder ({LIGHT_CYAN(data_manager.program_data_home)}) has been deleted!",
    "[错误] 程序数据文件夹不存在！": "[Error] The program data folder does NOT exist!",
    " * 请增加终端宽度以显示更多内容 * ": " * Please widen terminal for more content * ",
}
sorted_keys = sorted(translation_dict.keys(), key=lambda x: len(x), reverse=True)
sorted_dict = {key: translation_dict[key] for key in sorted_keys}
translation_dict = sorted_dict

if __name__ == "__main__":
    input_file = output_file = "conda_env_manager.py"
    # input_file = "conda_env_manager.py"
    # output_file = "translated_script.py"

    replacements = translate_script(input_file, output_file, translation_dict)

    succeed = True
    for _, count in replacements.items():
        if count == 0:
            succeed = False
            break
    if succeed:
        print(LIGHT_GREEN("All translations are placed successfully!"))
    else:
        print(LIGHT_RED("Some translations failed to be placed!"))
        idx = 0
        for key, count in replacements.items():
            if count == 0:
                idx += 1
                print(f"{LIGHT_YELLOW(f'[{idx}] Failed to place:')} {key}")
