# v1.0.1
import re


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
    "输入错误{ColorStr.LIGHT_RED(error_count)}次，请重新输入: ": "Input error {ColorStr.LIGHT_RED(error_count)} times, please try again: ",
    "输入错误达到最大次数({ColorStr.LIGHT_RED(max_errors)})，程序退出": "Maximum number of input errors ({ColorStr.LIGHT_RED(max_errors)}) reached, program exits.",
    "无法读取快捷方式文件：": "Unable to read shortcut file: ",
    "未检测到conda/mamba的安装，请先安装conda/mamba后再运行此脚本！": "Conda/mamba is NOT detected, please install conda/mamba before running this script!",
    "[提示] 检测到多个发行版安装,目前默认管理的是{os.path.split(CONDA_HOME)[1]},其他发行版的环境{others_env_namelist}将不会被显示！": "[Tip] Multiple distributions are detected, currently managing {os.path.split(CONDA_HOME)[1]} by default, other distributions {others_env_namelist} will NOT be displayed!",
    ",以回车结束:": ", press Enter to end: ",
    "请输入": "Please input ",
    "输入错误次数({error_count})过多，已退出！": "Too many input errors ({error_count}), exited!",
    "{prefix_str}输入错误({ColorStr.RED(error_count)})次!请重新输入{askstr}": "{prefix_str}Input error ({ColorStr.RED(error_count)}) times! Please re-enter {askstr}",
    "允许的操作指令如下:": "The allowed operation instructions are as follows:",
    '激活环境对应命令行输入编号{ColorStr.LIGHT_YELLOW(f"[1-{env_num}]")};浏览环境主目录输入{ColorStr.LIGHT_GREEN("[=编号]")};': 'Activate environment by {ColorStr.LIGHT_YELLOW(f"[1-{env_num}]")}; Browse environment directory by {ColorStr.LIGHT_GREEN("[=number]")};',
    '删除环境按{ColorStr.RED("[-]")};新建环境按{ColorStr.LIGHT_GREEN("[+]")};重命名环境按{ColorStr.LIGHT_BLUE("[R]")};复制环境按{ColorStr.LIGHT_CYAN("[P]")};': 'Delete env(s) by {ColorStr.RED("[-]")}; Create a new env by {ColorStr.LIGHT_GREEN("[+]")}; Rename env(s) by {ColorStr.LIGHT_BLUE("[R]")}; Copy env(s) by {ColorStr.LIGHT_CYAN("[P]")};',
    '对应环境查看并回退至历史版本按{ColorStr.LIGHT_MAGENTA("[V]")};': 'View and roll back to the historical version of the corresponding environment by {ColorStr.LIGHT_MAGENTA("[V]")};',
    '更新指定环境的所有包按{ColorStr.GREEN("[U]")};': 'Update all packages of the specified environment(s) by {ColorStr.GREEN("[U]")};',
    '查看及清空 pip/mamba/conda 缓存按{ColorStr.LIGHT_RED("[C]")};': 'Clean or view pip/mamba/conda cache by {ColorStr.LIGHT_RED("[C]")};',
    '将指定环境注册到 Jupyter 按{ColorStr.LIGHT_CYAN("[I]")};': 'Register the specified environment to Jupyter by {ColorStr.LIGHT_CYAN("[I]")};',
    '显示、管理所有已注册的 Jupyter 环境及清理弃用项按{ColorStr.LIGHT_BLUE("[J]")};': 'Display, manage all registered Jupyter environments and clean up obsolete items by {ColorStr.LIGHT_BLUE("[J]")};',
    '检查环境完整性并显示健康报告按{ColorStr.LIGHT_GREEN("[H]")};': 'Check the integrity of the environment and display the health report by {ColorStr.LIGHT_GREEN("[H]")};',
    '搜索 Conda 软件包按{ColorStr.LIGHT_CYAN("[S]")};': 'Search Conda packages by {ColorStr.LIGHT_CYAN("[S]")};',
    '退出按{ColorStr.YELLOW("[Q]")};': 'Exit by {ColorStr.YELLOW("[Q]")};',
    "对应指令": "Corresponding instructions",
    "[错误] 未检测到有效的环境编号！": "[Error] No valid environment number detected!",
    "(1) 请输入想要删除的环境的编号(或all=全部),多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to delete (or all for all envs), separated by spaces, and press Enter to end: ",
    "(2) 确认删除以上环境吗？[y(回车)/n]": "(2) Are you sure you want to delete the above environment(s)? [y(Enter)/n]",
    "[警告] base环境未安装Jupyter,无法管理相关环境的jupyter注册,请在主界面按[J]以安装": "[Warning] The base environment is NOT installed with Jupyter, and cannot manage the Jupyter registration of related environments. Please press [J] on the main interface to install",
    "[提示] 已清除需卸载环境{i}的Jupyter注册": "[Tip] The Jupyter registration of the environment to be uninstalled {i} has been cleared",
    "(1) 请输入想要新建的环境的名称,以回车结束: ": "(1) Please enter the name of the environment you want to create, and press Enter to end: ",
    "新环境名称": "New environment name ",
    "已存在或不符合规范": " Already exists or does not meet the specifications",
    "，请重新输入: ": ", please re-enter: ",
    "(2)[提示] 检测到环境名称{ColorStr.LIGHT_CYAN(inp1)}符合python环境命名规范,": "(2)[Tip] The environment name {ColorStr.LIGHT_CYAN(inp1)} meets the naming specifications of the python environment,",
    "已自动指定python版本={inp2}": " Python version has been automatically specified={inp2}",
    "(2) 请指定python版本(为空默认最新版)，以回车结束:": "(2) Please specify the python version (leave blank for the latest version), and press Enter to end:",
    "(3) 请指定预安装参数(如{ColorStr.LIGHT_YELLOW('spyder')}包等,{ColorStr.LIGHT_GREEN('-c nvidia')}源等,以空格隔开)，以回车结束:": "(3) Please specify the pre-installation parameters (such as {ColorStr.LIGHT_YELLOW('spyder')} package(s), {ColorStr.LIGHT_GREEN('-c nvidia')} source(s), etc., separated by spaces), and press Enter to end:",
    "[提示]": "[Tip]",
    r" 如输入了独立的\"{ColorStr.LIGHT_GREEN('--+')}\",则等效于预安装\"{ColorStr.LIGHT_YELLOW(pre_install_pkgs)}\"包(并将该环境注册到用户Jupyter)": r" If an independent \"{ColorStr.LIGHT_GREEN('--+')}\" is entered, it is equivalent to pre-installing the \"{ColorStr.LIGHT_YELLOW(pre_install_pkgs)}\" packages (and registering to the user's Jupyter)",
    "安装失败！": "Installation failed!",
    "(3a) 是否启用更多的源重新安装[(Y)/n] >>> ": "(3a) Do you want to enable more sources to reinstall [(Y)/n] >>> ",
    "[提示]": "[Tip]",
    " 常用第三方源有:": " Common third-party sources include:",
    "(3b) 请输入更多的源,以空格隔开: ": "(3b) Please enter more sources, separated by spaces: ",
    "(3c) 已将{ColorStr.LIGHT_GREEN(inp_sources)}添加为新环境{inp1}的默认源": "(3c) {ColorStr.LIGHT_GREEN(inp_sources)} has been added as the default source for the new environment {inp1}",
    "(4) 请输入此环境注册到Jupyter的显示名称(为空使用默认值):": "(4) Please enter the display name of this environment registered to Jupyter (leave blank to use the default value):",
    "(1) 请输入想要注册到用户级Jupyter的环境的编号(或all=全部),多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to register to the user-level Jupyter (or all for all envs), separated by spaces, and press Enter to end: ",
    "(2) 确认注册以上环境的Jupyter到用户吗？[y(回车)/n]": "(2) Are you sure you want to register the Jupyter of the above environment(s) to the user? [y(Enter)/n]",
    "(3.{j}) 请输入环境{ColorStr.LIGHT_CYAN(i)}注册到Jupyter的显示名称(为空使用默认值):": "(3.{j}) Please enter the display name of the environment {ColorStr.LIGHT_CYAN(i)} registered to Jupyter (leave blank to use the default value):",
    "[提示] 该环境中未检测到ipykernel包，正在为环境安装ipykernel包...": "[Tip] The ipykernel package is NOT detected in the environment, and the ipykernel package is being installed for the environment...",
    "(1) 请输入想要重命名的环境的编号,多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to rename, separated by spaces, and press Enter to end: ",
    "(2) 确认重命名以上环境吗？[y(回车)/n]": "(2) Are you sure you want to rename the above environment(s)? [y(Enter)/n]",
    "(3.{j}) 请输入环境{ColorStr.LIGHT_CYAN(i)}重命名后的环境名称:": "(3.{j}) Please enter the new name of the environment {ColorStr.LIGHT_CYAN(i)} after renaming:",
    "新环境名称": "New environment name ",
    "已存在或不符合规范": " Already exists or does not meet the specifications",
    ",请重新为{ColorStr.LIGHT_CYAN(i)}重命名: ": ", please rename {ColorStr.LIGHT_CYAN(i)}: ",
    "[警告] base环境未安装Jupyter,无法管理相关环境的jupyter注册,请在主界面按[J]以安装": "[Warning] The base environment is NOT installed with Jupyter, and cannot manage the Jupyter registration of related environments. Please press [J] on the main interface to install",
    "[提示] 检测到原环境的Jupyter注册已失效，正在为新环境重新注册Jupyter": "[Tip] The Jupyter registration of the original environment has Expired, and Jupyter is being re-registered for the new environment",
    "(4) 请输入注册到Jupyter的显示名称(为空使用默认值):": "(4) Please enter the display name registered to Jupyter (leave blank to use the default value):",
    "已重新注册新环境{ii}的Jupyter": "Jupyter of the new environment {ii} has been re-registered",
    "(1) 请输入想要复制的环境的编号,多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to copy, separated by spaces, and press Enter to end: ",
    "(2) 确认复制以上环境吗？[y(回车)/n]": "(2) Are you sure you want to copy the above environment(s)? [y(Enter)/n]",
    "(3.{j}) 请输入环境{ColorStr.LIGHT_CYAN(i)}复制后的环境名称(为空使用默认值):": "(3.{j}) Please enter the new name of the environment {ColorStr.LIGHT_CYAN(i)} after copying (leave blank to use the default value):",
    "新环境名称": "New environment name ",
    "已存在或不符合规范": " Already exists or does not meet the specifications",
    ",请重新为{ColorStr.LIGHT_CYAN(i)}命名: ": ", please rename {ColorStr.LIGHT_CYAN(i)}: ",
    "当前用户已注册的Jupyter环境如下:": "The Jupyter environments registered by the current user are as follows:",
    "[提示] 未检测到jupyter命令，正尝试向base环境安装ipykernel...": "[Tip] The jupyter command is NOT detected, and an attempt is being made to install ipykernel to the base environment...",
    "安装失败，请手动安装ipykernel后重试！": "Installation failed, please install ipykernel manually and try again!",
    "[提示] 已打开base环境的powershell": "[Tip] The powershell of the base environment has been opened",
    "base环境中ipykernel安装成功！": "ipykernel installation in the base environment was successful!",
    " (已失效)": " (Expired)",
    "未检测到任何Jupyter环境": "No Jupyter environment detected",
    "(0a) 确认清理以上失效项吗？[y(回车)/n]": "(0a) Are you sure you want to clear the above Expired registrations? [y(Enter)/n]",
    "(1) 请输入想要删除的Jupyter环境的编号(或all=全部),多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of the Jupyter environment(s) you want to delete (or all for all envs), separated by spaces, and press Enter to end: ",
    "[错误] 未检测到有效的Jupyter环境编号！": "[Error] No valid Jupyter environment number detected!",
    "(2) 确认删除以上Jupyter环境吗？[y(回车)/n]": "(2) Are you sure you want to delete the above Jupyter environment? [y(Enter)/n]",
    "需要查看及回退历史版本的环境编号": "the number of environment to view and roll back to historical version",
    "环境{ColorStr.LIGHT_CYAN(env_name)}的历史版本如下:": "The historical versions of the environment {ColorStr.LIGHT_CYAN(env_name)} are as follows:",
    "(2) 请输入环境{ColorStr.LIGHT_CYAN(env_name)}的历史版本编号[": "(2) Please enter the historical version number of the environment {ColorStr.LIGHT_CYAN(env_name)} [",
    "],以回车结束: ": "], and press Enter to end: ",
    "[rev后的数字] >>> ": "[Number after rev] >>> ",
    "[提示] 根据历史记录已自动启用附加源:": "[Tip] Additional sources have been automatically enabled based on the history:",
    "(包文件夹)": "(Package folder)",
    " 及 Pip 缓存情况": " and Pip cache situation",
    "总缓存大小: ": "Total cache size: ",
    "(1) 请输入Y(回车:全部清理)/N,或想要清理的缓存项编号,多个以空格隔开: ": "(1) Please enter Y(Enter: clean all)/N, or the number of the cache item you want to clean, separated by spaces: ",
    "输入": "Input ",
    "应为空或Y或N或数字[1-5]的以空格隔开的组合,请重新输入: ": " should be a combination of empty, Y, N, or numbers [1-5] separated by spaces, please re-enter: ",
    "[错误] ": "[Error] ",
    "[错误] mamba clean --all --dry-run --json命令输出有误！无法解析,输出如下:": "[Error] The mamba clean --all --dry-run --json command output is incorrect! Unable to parse, the output is as follows:",
    "[提示] 已启动默认清理程序": "[Tip] The default cleaning program has been started",
    "(1) 确认清空所有pip/mamba/conda缓存吗？[y(回车)/n]": "(1) Are you sure you want to clear all pip/mamba/conda caches? [y(Enter)/n]",
    "[提示] 慎用，请仔细检查更新前后的包对应源的变化！": "[Tip] Use with caution, please carefully check the changes in the corresponding sources of the package before and after the update!",
    "(1) 请输入想要更新的环境的编号(或all=全部),多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to update (or all for all envs), separated by spaces, and press Enter to end: ",
    "(2) 确认更新以上环境吗？[y(回车)/n]": "(2) Are you sure you want to update the above environment(s)? [y(Enter)/n]",
    "[{j}/{len(env_names)}] 正在更新环境{ColorStr.LIGHT_CYAN(i)}的所有包...": "[{j}/{len(env_names)}] Updating all packages of the environment {ColorStr.LIGHT_CYAN(i)}...",
    "[警告] 检测到如下由Pip管理的包，更新可能会出现问题！": "[Warning] The following packages managed by Pip are detected, and problems may occur during the update!",
    "(i) 是否继续更新环境{ColorStr.LIGHT_CYAN(i)}？[y/n(回车)]": "(i) Do you want to continue updating the environment {ColorStr.LIGHT_CYAN(i)}? [y/n(Enter)]",
    "[提示] 已自动启用附加源: ": "[Tip] Additional sources have been automatically enabled: ",
    "[提示] 您的conda-libmamba-solver未安装或版本过低，无法使用搜索功能，请将conda-libmamba-solver升级到23.9及以上版本": "[Tip] Your conda-libmamba-solver is NOT installed or the version is too low, and the search function cannot be used. Please upgrade conda-libmamba-solver to version 23.9 or higher",
    "[提示] 您的conda版本过低，建议先升级conda到23.10及以上版本": "[Tip] Your conda version is too low, it is recommended to upgrade conda to version 23.10 or higher first",
    "升级conda命令: ": "Upgrade conda command: ",
    "升级libmamba命令: ": "Upgrade libmamba command: ",
    "安装libmamba命令: ": "Install libmamba command: ",
    "请在base环境下执行以上命令。": "Please execute the above commands in the base environment.",
    "(1) 请指定python版本(为空默认全版本)，以回车结束:": "(1) Please specify the python version (leave blank for all versions), and press Enter to end:",
    "[提示1] 搜索默认启用的源为": "[Tip1] The default enabled source for search is ",
    "如需额外源请在末尾添加 -c 参数": " If you need additional sources, please add the -c parameter at the end",
    "[提示2] 可用mamba repoquery depends/whoneeds命令列出包的依赖项/列出需要给定包的程序包": "[Tip2] The mamba repoquery depends/whoneeds command can be used to list the dependencies of the package/list the packages that need the given package",
    "[提示3] 搜索语法为Name=Version=Build,后两项可选 (示例:numpy>1.17,<1.19.2 *numpy*=1.17.*=py38*)": "[Tip3] The search syntax is Name=Version=Build, the last two items are optional (example: numpy>1.17,<1.19.2 *numpy*=1.17.*=py38*)",
    "        (详见https://github.com/conda/conda/blob/main/docs/source/user-guide/concepts/pkg-search.rst)": "        (For details, see https://github.com/conda/conda/blob/main/docs/source/user-guide/concepts/pkg-search.rst)",
    "(2) 请输入想要搜索的包 (适用于Python {target_py_version}),以回车结束:": "(2) Please enter the package you want to search (for Python {target_py_version}), and press Enter to end:",
    "(2) 请输入想要搜索的包 (适用于全部Python版本),以回车结束:": "(2) Please enter the package you want to search (for all Python versions), and press Enter to end:",
    '"输入" + ColorStr.LIGHT_RED("不能为空") + ",请重新输入: "': '"Input" + ColorStr.LIGHT_RED("cannot be empty") + ", please re-enter: "',
    "[提示] 检测到-c参数，已自动添加相应源: ": "[Tip] The -c parameter is detected, and the corresponding source has been automatically added: ",
    "正在搜索({ColorStr.LIGHT_CYAN(inp)})...": "Searching ({ColorStr.LIGHT_CYAN(inp)})...",
    "搜索结果解析失败!原始结果如下:": "Search result parsing failed! The original result is as follows:",
    "[警告] 未搜索到任何相关包({round(time.time() - t0_search, 2)} s)！": "[Warning] No relevant packages found ({round(time.time() - t0_search, 2)} s)!",
    "(i) 请输入要查看详细信息的包对应编号(带{ColorStr.LIGHT_CYAN('=')}号则显示安装命令行并拷贝到剪贴板): ": "(i) Please enter the corresponding number of package to view details (with {ColorStr.LIGHT_CYAN('=')} to display the installation command line and copy it to the clipboard): ",
    "[{key}]包{ColorStr.LIGHT_CYAN(pkginfo_dict['name'])} {ColorStr.LIGHT_GREEN(pkginfo_dict['version'])}的详细信息如下": "[{key}] The detailed information of package {ColorStr.LIGHT_CYAN(pkginfo_dict['name'])} {ColorStr.LIGHT_GREEN(pkginfo_dict['version'])} is as follows",
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
    "对于{ColorStr.LIGHT_CYAN(inp)},共找到{ColorStr.LIGHT_CYAN(len(pkginfos_list_raw))}个相关包,搜索结果如上": "For {ColorStr.LIGHT_CYAN(inp)}, {ColorStr.LIGHT_CYAN(len(pkginfos_list_raw))} related packages found, search results as above.",
    "(i) 是否继续为 Python {target_py_version} 查找包? [Y(回车)/n]": "(i) Do you want to continue searching for packages for Python {target_py_version}? [Y(Enter)/n]",
    "(i) 是否继续为所有 Python 版本查找包? [Y(回车)/n]": "(i) Do you want to continue searching for packages for all Python versions? [Y(Enter)/n]",
    "[错误] conda doctor命令需要conda 23.5.0及以上版本支持,请在base环境升级conda后重试!": "[Error] The conda doctor command requires conda 23.5.0 and above to support, please upgrade conda in the base environment and try again!",
    "升级conda命令: ": "Upgrade conda command: ",
    "(1) 请输入想要检查完整性的环境的编号(默认为全部),多个以空格隔开,以回车结束: ": "(1) Please enter the number(s) of environment(s) you want to check the integrity (default is all), separated by spaces, and press Enter to end: ",
    "[{i}/{len(env_check_names)}] 正在检查环境{ColorStr.LIGHT_CYAN(env_name)}的健康情况...": "[{i}/{len(env_check_names)}] Checking the health of the environment {ColorStr.LIGHT_CYAN(env_name)}...",
    "[提示] 已在文件资源管理器中打开环境{ColorStr.LIGHT_CYAN(env_name)}的主目录:": "[Tip] The main directory of the environment {ColorStr.LIGHT_CYAN(env_name)} has been opened in the file explorer:",
    "请输入conda/mamba发行版的安装路径,如C:\\\\Users\\\\USER_NAME\\\\anaconda3: ": "Please enter the installation path of the conda/mamba distribution, such as C:\\\\\\\\Users\\\\\\\\USER_NAME\\\\\\\\anaconda3: ",
    "请输入conda/mamba发行版的安装路径,如/home/USER_NAME/anaconda3: ": "Please enter the installation path of the conda/mamba distribution, such as /home/USER_NAME/anaconda3: ",
    "conda/mamba发行版环境管理工具": "Conda/mamba distribution environment management tool",
    "打开的路径，默认为当前路径": "The opened path, default is the current path",
    "conda/mamba发行版的安装路径,如C:\\\\Users\\\\USER_NAME\\\\miniforge3,/home/USER_NAME/miniconda3": "Installation path of the conda/mamba distribution, such as C:\\\\\\\\Users\\\\\\\\USER_NAME\\\\\\\\miniforge3,/home/USER_NAME/miniconda3",
    "发行版的名称,支持miniforge3,anaconda3,miniconda3,mambaforge,miniforge-pypy3,mambaforge-pypy3,默认顺序如前": "The name of the distribution, supports miniforge3,anaconda3,miniconda3,mambaforge,miniforge-pypy3,mambaforge-pypy3, the default order is as before",
    "探测并列出计算机中所有受支持的conda/mamba发行版": "Detect and list all supported conda/mamba distributions on the computer",
    "计算机中所有受支持的conda/mamba发行版如下:": "All supported conda/mamba distributions on the computer are as follows:",
    '未在指定路径"{args.prefix}"检测到对应发行版，将使用默认发行版': 'No corresponding distribution was detected in the specified path "{args.prefix}", and the default distribution will be used',
    "未检测到指定的发行版({args.distribution_name})，将使用默认发行版": "The specified distribution ({args.distribution_name}) was NOT detected, and the default distribution will be used",
    "传入的参数不是一个目录！": "The passed parameter is NOT a directory!",
}
sorted_keys = sorted(translation_dict.keys(), key=lambda x: len(x), reverse=True)
sorted_dict = {key: translation_dict[key] for key in sorted_keys}
translation_dict = sorted_dict

if __name__ == "__main__":
    input_file = output_file = "manage_conda_envs.py"
    # input_file = "manage_conda_envs.py"
    # output_file = "translated_script.py"

    replacements = translate_script(input_file, output_file, translation_dict)

    succeed = True
    for _, count in replacements.items():
        if count == 0:
            succeed = False
            break
    if succeed:
        print("All translations are placed successfully!")
    else:
        print("Some translations failed to be placed!")
        for key, count in replacements.items():
            if count == 0:
                print(f"Failed to place: {key}")
