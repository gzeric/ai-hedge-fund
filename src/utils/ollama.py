"""处理 Ollama 模型的实用工具。"""

import platform # 获取操作系统信息
import subprocess # 运行子进程
import requests # 发送 HTTP 请求
import time # 时间相关操作
from typing import List # 类型提示
import questionary # 创建交互式命令行提示
from colorama import Fore, Style # 在终端输出彩色文本
import os # 操作系统相关功能，例如环境变量
from . import docker # 导入同目录下的 docker.py 模块 (如果存在)

# 常量定义
OLLAMA_SERVER_URL = "http://localhost:11434" # Ollama 服务器的默认 URL
OLLAMA_API_MODELS_ENDPOINT = f"{OLLAMA_SERVER_URL}/api/tags" # 获取已下载模型列表的 API 端点
# 不同操作系统的 Ollama 下载链接
OLLAMA_DOWNLOAD_URL = {
    "darwin": "https://ollama.com/download/darwin",  # macOS
    "windows": "https://ollama.com/download/windows", # Windows
    "linux": "https://ollama.com/download/linux"      # Linux
}
# 不同操作系统的 Ollama 安装指令 (主要用于 Linux 和 macOS 的命令行安装)
INSTALLATION_INSTRUCTIONS = {
    "darwin": "curl -fsSL https://ollama.com/install.sh | sh",
    "windows": "# 请从 https://ollama.com/download/windows 下载并运行安装程序",
    "linux": "curl -fsSL https://ollama.com/install.sh | sh"
}


def is_ollama_installed() -> bool:
    """检查系统中是否安装了 Ollama。"""
    system = platform.system().lower() # 获取当前操作系统名称并转为小写

    if system == "darwin" or system == "linux":  # macOS 或 Linux
        try:
            # 使用 'which' 命令检查 'ollama' 是否在 PATH 中
            result = subprocess.run(["which", "ollama"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            return result.returncode == 0 # 返回码为0表示命令成功执行且找到
        except Exception:
            return False # 发生异常则认为未安装
    elif system == "windows":  # Windows
        try:
            # 使用 'where' 命令检查 'ollama' 是否在 PATH 中
            result = subprocess.run(["where", "ollama"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True, check=False)
            return result.returncode == 0
        except Exception:
            return False
    else:
        return False  # 不支持的操作系统


def is_ollama_server_running() -> bool:
    """检查 Ollama 服务器是否正在运行。"""
    try:
        # 尝试向 Ollama API 发送一个简单的 GET 请求
        response = requests.get(OLLAMA_API_MODELS_ENDPOINT, timeout=2) # 设置2秒超时
        return response.status_code == 200 # HTTP 200 OK 表示服务器正在运行且可访问
    except requests.RequestException:
        return False # 任何请求异常都意味着服务器未运行或不可达


def get_locally_available_models() -> List[str]:
    """获取本地已下载的模型列表。"""
    if not is_ollama_server_running(): # 如果服务器未运行，则无法获取列表
        return []

    try:
        response = requests.get(OLLAMA_API_MODELS_ENDPOINT, timeout=5) # 设置5秒超时
        if response.status_code == 200:
            data = response.json()
            # 从 JSON 响应中提取模型名称列表
            return [model["name"] for model in data["models"]] if "models" in data and isinstance(data["models"], list) else []
        return []
    except requests.RequestException:
        return []


def start_ollama_server() -> bool:
    """如果 Ollama 服务器未运行，则启动它。"""
    if is_ollama_server_running():
        print(f"{Fore.GREEN}Ollama 服务器已在运行。{Style.RESET_ALL}")
        return True

    system = platform.system().lower()

    try:
        if system == "darwin" or system == "linux":  # macOS 或 Linux
            # 在后台启动 Ollama 服务
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        elif system == "windows":  # Windows
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        else:
            print(f"{Fore.RED}不支持的操作系统: {system}{Style.RESET_ALL}")
            return False

        # 等待服务器启动
        print(f"{Fore.YELLOW}正在启动 Ollama 服务器...{Style.RESET_ALL}")
        for _ in range(10):  # 尝试等待10秒
            if is_ollama_server_running():
                print(f"{Fore.GREEN}Ollama 服务器启动成功。{Style.RESET_ALL}")
                return True
            time.sleep(1) # 每秒检查一次

        print(f"{Fore.RED}启动 Ollama 服务器失败。等待服务器可用超时。{Style.RESET_ALL}")
        return False
    except Exception as e:
        print(f"{Fore.RED}启动 Ollama 服务器时出错: {e}{Style.RESET_ALL}")
        return False


def install_ollama() -> bool:
    """在系统上安装 Ollama。"""
    system = platform.system().lower()
    if system not in OLLAMA_DOWNLOAD_URL: # 检查是否为支持自动安装的系统
        print(f"{Fore.RED}不支持的操作系统进行自动安装: {system}{Style.RESET_ALL}")
        print(f"请访问 https://ollama.com/download 手动安装 Ollama。")
        return False

    if system == "darwin":  # macOS
        print(f"{Fore.YELLOW}Mac 版 Ollama 可通过应用程序下载。{Style.RESET_ALL}")

        # 优先为 macOS 用户提供应用程序下载选项
        if questionary.confirm("您想下载 Ollama 应用程序吗？", default=True).ask():
            try:
                import webbrowser # 用于打开网页浏览器
                webbrowser.open(OLLAMA_DOWNLOAD_URL["darwin"])
                print(f"{Fore.YELLOW}请下载并安装该应用程序，然后重新启动此程序。{Style.RESET_ALL}")
                print(f"{Fore.CYAN}安装后，您可能需要先打开一次 Ollama 应用才能继续。{Style.RESET_ALL}")

                # 询问用户是否已完成安装并尝试继续
                if questionary.confirm("您是否已安装 Ollama 应用并至少打开过一次？", default=False).ask():
                    if is_ollama_installed() and start_ollama_server():
                        print(f"{Fore.GREEN}Ollama 现在已正确安装并运行！{Style.RESET_ALL}")
                        return True
                    else:
                        print(f"{Fore.RED}未检测到 Ollama 安装。请在安装 Ollama 后重新启动此应用程序。{Style.RESET_ALL}")
                        return False
                return False # 如果用户选择不立即继续
            except Exception as e:
                print(f"{Fore.RED}打开浏览器失败: {e}{Style.RESET_ALL}")
                return False
        else: # 如果用户不选择下载应用程序
            # 仅为高级用户提供命令行安装作为后备方案
            if questionary.confirm("您想尝试命令行安装吗？（适用于高级用户）", default=False).ask():
                print(f"{Fore.YELLOW}正在尝试命令行安装...{Style.RESET_ALL}")
                try:
                    # 执行安装脚本
                    install_process = subprocess.run(
                        ["bash", "-c", INSTALLATION_INSTRUCTIONS["darwin"]],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
                    )
                    if install_process.returncode == 0:
                        print(f"{Fore.GREEN}通过命令行成功安装 Ollama。{Style.RESET_ALL}")
                        return True
                    else:
                        print(f"{Fore.RED}命令行安装失败。请改用应用程序下载方法。错误: {install_process.stderr}{Style.RESET_ALL}")
                        return False
                except Exception as e:
                    print(f"{Fore.RED}命令行安装期间出错: {e}{Style.RESET_ALL}")
                    return False
            return False # 如果用户也不选择命令行安装
    elif system == "linux":  # Linux
        print(f"{Fore.YELLOW}正在安装 Ollama...{Style.RESET_ALL}")
        try:
            install_process = subprocess.run(
                ["bash", "-c", INSTALLATION_INSTRUCTIONS["linux"]],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
            )
            if install_process.returncode == 0:
                print(f"{Fore.GREEN}Ollama 安装成功。{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}安装 Ollama 失败。错误: {install_process.stderr}{Style.RESET_ALL}")
                return False
        except Exception as e:
            print(f"{Fore.RED}Ollama 安装期间出错: {e}{Style.RESET_ALL}")
            return False
    elif system == "windows":  # Windows
        print(f"{Fore.YELLOW}Windows 尚不支持自动安装。{Style.RESET_ALL}")
        print(f"请从以下地址下载并安装 Ollama: {OLLAMA_DOWNLOAD_URL['windows']}")

        if questionary.confirm("您想在浏览器中打开 Ollama 下载页面吗？").ask():
            try:
                import webbrowser
                webbrowser.open(OLLAMA_DOWNLOAD_URL["windows"])
                print(f"{Fore.YELLOW}安装后，请重新启动此应用程序。{Style.RESET_ALL}")
                if questionary.confirm("您是否已安装 Ollama？", default=False).ask():
                    if is_ollama_installed() and start_ollama_server():
                        print(f"{Fore.GREEN}Ollama 现在已正确安装并运行！{Style.RESET_ALL}")
                        return True
                    else:
                        print(f"{Fore.RED}未检测到 Ollama 安装。请在安装 Ollama 后重新启动此应用程序。{Style.RESET_ALL}")
                        return False
            except Exception as e:
                print(f"{Fore.RED}打开浏览器失败: {e}{Style.RESET_ALL}")
        return False # Windows 下总是返回 False，因为需要手动操作

    return False # 默认返回 False


def download_model(model_name: str) -> bool:
    """下载一个 Ollama 模型。"""
    if not is_ollama_server_running(): # 确保服务器正在运行
        if not start_ollama_server(): # 如果未运行，则尝试启动
            return False

    print(f"{Fore.YELLOW}正在下载模型 {model_name}...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}这可能需要一些时间，具体取决于您的网络速度和模型大小。{Style.RESET_ALL}")
    print(f"{Fore.CYAN}下载正在后台进行。请耐心等待...{Style.RESET_ALL}")

    try:
        # 使用 Ollama CLI 下载模型
        # subprocess.Popen 用于在后台运行命令
        process = subprocess.Popen(
            ["ollama", "pull", model_name], # 命令和参数
            stdout=subprocess.PIPE,  # 捕获标准输出
            stderr=subprocess.STDOUT, # 将标准错误重定向到标准输出，以捕获所有输出
            text=True, # 以文本模式处理输出
            bufsize=1,  # 行缓冲，以便逐行读取输出
            encoding='utf-8',  # 显式使用 UTF-8 编码
            errors='replace'   # 替换无法解码的字符
        )
        
        print(f"{Fore.CYAN}下载进度:{Style.RESET_ALL}")

        # 用于跟踪进度
        last_percentage = 0.0
        last_phase = ""
        bar_length = 40 # 进度条长度

        while True: # 循环读取输出直到进程结束
            output_line = process.stdout.readline() if process.stdout else "" # 读取一行输出
            if output_line == "" and process.poll() is not None: # 如果没有输出且进程已结束
                break
            if output_line:
                output_line = output_line.strip()
                percentage = None
                current_phase = None

                # Ollama 输出示例:
                # "downloading: 23.45 MB / 42.19 MB [================>-------------] 55.59%"
                # "downloading model: 76%"
                # "pulling manifest: 100%"

                # 尝试从输出中提取百分比
                import re
                percentage_match = re.search(r"(\d+(\.\d+)?)%", output_line)
                if percentage_match:
                    try:
                        percentage = float(percentage_match.group(1))
                    except ValueError:
                        pass # 无法转换则忽略

                # 尝试确定当前阶段 (downloading, extracting 等)
                phase_match = re.search(r"^([a-zA-Z\s]+):", output_line)
                if phase_match:
                    current_phase = phase_match.group(1).strip()

                # 如果找到百分比，则显示进度条
                if percentage is not None:
                    # 仅当百分比有显著变化或阶段改变时更新，以避免闪烁
                    if abs(percentage - last_percentage) >= 1 or (current_phase and current_phase != last_phase):
                        last_percentage = percentage
                        if current_phase:
                            last_phase = current_phase

                        filled_length = int(bar_length * percentage / 100)
                        bar = "█" * filled_length + "░" * (bar_length - filled_length)
                        phase_display = f"{Fore.CYAN}{last_phase.capitalize()}{Style.RESET_ALL}: " if last_phase else ""
                        status_line = f"\r{phase_display}{Fore.GREEN}{bar}{Style.RESET_ALL} {Fore.YELLOW}{percentage:.1f}%{Style.RESET_ALL}"
                        print(status_line, end="", flush=True) # 不换行打印，实现原地更新
                else: # 如果没有百分比但有可识别的输出
                    if "download" in output_line.lower() or "extract" in output_line.lower() or "pulling" in output_line.lower():
                        if "%" in output_line: # 如果行内有百分号，也尝试原地更新
                            print(f"\r{Fore.GREEN}{output_line}{Style.RESET_ALL}", end="", flush=True)
                        else: # 否则正常打印
                            print(f"{Fore.GREEN}{output_line}{Style.RESET_ALL}")

        return_code = process.wait() # 等待下载进程结束
        print() # 确保在进度条后换行

        if return_code == 0:
            print(f"{Fore.GREEN}模型 {model_name} 下载成功！{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}下载模型 {model_name} 失败。请检查您的网络连接并重试。{Style.RESET_ALL}")
            return False
    except Exception as e:
        print(f"\n{Fore.RED}下载模型 {model_name} 时出错: {e}{Style.RESET_ALL}")
        return False


def ensure_ollama_and_model(model_name: str) -> bool:
    """确保 Ollama 已安装、正在运行，并且请求的模型可用。"""
    # 检查是否在 Docker 环境中运行
    # 通过检查 OLLAMA_BASE_URL 环境变量是否以特定 Docker 主机名开头来判断
    in_docker = os.environ.get("OLLAMA_BASE_URL", "").startswith("http://ollama:") or \
                os.environ.get("OLLAMA_BASE_URL", "").startswith("http://host.docker.internal:")
    
    if in_docker: # 如果在 Docker 环境中
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434") # 获取 Docker 内的 Ollama URL
        return docker.ensure_ollama_and_model(model_name, ollama_url) # 调用 docker 模块的相应函数
    
    # 非 Docker 环境的常规流程
    if not is_ollama_installed(): # 检查 Ollama 是否已安装
        print(f"{Fore.YELLOW}您的系统中未安装 Ollama。{Style.RESET_ALL}")
        if questionary.confirm("您想安装 Ollama 吗？").ask():
            if not install_ollama(): # 尝试安装
                return False # 安装失败
        else:
            print(f"{Fore.RED}使用本地模型需要 Ollama。{Style.RESET_ALL}")
            return False # 用户拒绝安装
    
    if not is_ollama_server_running(): # 确保服务器正在运行
        print(f"{Fore.YELLOW}正在启动 Ollama 服务器...{Style.RESET_ALL}")
        if not start_ollama_server(): # 尝试启动服务器
            return False # 启动失败
    
    available_models = get_locally_available_models() # 获取本地可用模型列表
    if model_name not in available_models: # 如果请求的模型不在列表中
        print(f"{Fore.YELLOW}模型 {model_name} 在本地不可用。{Style.RESET_ALL}")
        
        model_size_info = "" # 模型大小提示信息
        if "70b" in model_name.lower():
            model_size_info = " 这是一个大模型 (可能高达几十GB)，下载可能需要较长时间。"
        elif "34b" in model_name.lower() or "8x7b" in model_name.lower():
            model_size_info = " 这是一个中等大小的模型 (数GB到十几GB)，下载可能需要几分钟。"
        
        if questionary.confirm(f"您想下载模型 {model_name} 吗？{model_size_info} 下载将在后台进行。").ask():
            return download_model(model_name) # 下载模型
        else:
            print(f"{Fore.RED}需要该模型才能继续。{Style.RESET_ALL}")
            return False # 用户拒绝下载
    
    return True # Ollama 已安装，服务器已运行，模型也可用


def delete_model(model_name: str) -> bool:
    """删除本地下载的 Ollama 模型。"""
    in_docker = os.environ.get("OLLAMA_BASE_URL", "").startswith("http://ollama:") or \
                os.environ.get("OLLAMA_BASE_URL", "").startswith("http://host.docker.internal:")
    
    if in_docker: # Docker 环境
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
        return docker.delete_model(model_name, ollama_url) # 调用 docker 模块的删除函数
        
    # 非 Docker 环境
    if not is_ollama_server_running(): # 确保服务器运行
        if not start_ollama_server():
            return False
    
    print(f"{Fore.YELLOW}正在删除模型 {model_name}...{Style.RESET_ALL}")
    
    try:
        # 使用 Ollama CLI 删除模型
        process = subprocess.run(["ollama", "rm", model_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        
        if process.returncode == 0:
            print(f"{Fore.GREEN}模型 {model_name} 删除成功。{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}删除模型 {model_name} 失败。错误: {process.stderr}{Style.RESET_ALL}")
            return False
    except Exception as e:
        print(f"{Fore.RED}删除模型 {model_name} 时出错: {e}{Style.RESET_ALL}")
        return False


# 添加此部分以便在文件末尾通过命令行使用
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Ollama 模型管理器")
    parser.add_argument("--check-model", help="检查模型是否存在，如果不存在则下载")
    args = parser.parse_args()

    if args.check_model:
        print(f"正在确保 Ollama 已安装且模型 {args.check_model} 可用...")
        result = ensure_ollama_and_model(args.check_model)
        sys.exit(0 if result else 1) # 成功则退出码为0，否则为1
    else:
        print("未指定操作。请使用 --check-model <模型名称> 来检查模型。")
        sys.exit(1)
