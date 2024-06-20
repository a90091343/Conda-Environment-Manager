import platform
import subprocess
import sys

# Common Dependencies
common_dependencies = ["colorama", "prettytable", "packaging"]

# Windows Only Dependencies
windows_dependencies = ["pywin32"]

# Linux Only Dependencies
linux_dependencies = []


if platform.system() == "Windows":
    dependencies = common_dependencies + windows_dependencies
elif platform.system() == "Linux":
    dependencies = common_dependencies + linux_dependencies
else:
    dependencies = common_dependencies


try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", *dependencies])
except subprocess.CalledProcessError:
    print("\033[0;91m[ERROR] An error occurred while installing dependencies.\033[0m")
else:
    print("\033[0;92m[SUCCESS] All dependencies for this project have been installed.\033[0m")
