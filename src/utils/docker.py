"""用于在 Docker 环境中处理 Ollama 模型的实用工具。"""

import requests # HTTP 请求库
import time # 时间相关操作
from colorama import Fore, Style # 用于在终端输出彩色文本
import questionary # 用于创建交互式命令行提示

def ensure_ollama_and_model(model_name: str, ollama_url: str) -> bool:
    """确保 Ollama 模型在 Docker 环境中可用。"""
    print(f"{Fore.CYAN}检测到 Docker 环境。{Style.RESET_ALL}")
    
    # 步骤 1: 检查 Ollama 服务是否可用
    if not is_ollama_available(ollama_url):
        return False # 如果服务不可用，则无法继续
        
    # 步骤 2: 检查模型是否已存在
    available_models = get_available_models(ollama_url)
    if model_name in available_models:
        print(f"{Fore.GREEN}模型 {model_name} 在 Docker Ollama 容器中可用。{Style.RESET_ALL}")
        return True # 模型已存在
        
    # 步骤 3: 模型不存在 - 询问用户是否要下载
    print(f"{Fore.YELLOW}模型 {model_name} 在 Docker Ollama 容器中不可用。{Style.RESET_ALL}")
    
    # 使用 questionary 库向用户确认是否下载
    if not questionary.confirm(f"您想下载模型 {model_name} 吗？").ask():
        print(f"{Fore.RED}没有该模型无法继续。{Style.RESET_ALL}")
        return False # 用户拒绝下载
        
    # 步骤 4: 下载模型
    return download_model(model_name, ollama_url)


def is_ollama_available(ollama_url: str) -> bool:
    """检查 Docker 环境中的 Ollama 服务是否可用。"""
    try:
        # 尝试向 Ollama 的版本 API 端点发送 GET 请求
        response = requests.get(f"{ollama_url}/api/version", timeout=5) # 设置5秒超时
        if response.status_code == 200: # HTTP 200 OK 表示成功
            return True
            
        # 如果状态码不是200，则打印错误信息
        print(f"{Fore.RED}无法连接到位于 {ollama_url} 的 Ollama 服务。{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}请确保 Ollama 服务正在您的 Docker 环境中运行。{Style.RESET_ALL}")
        return False
    except requests.RequestException as e: # 捕获请求相关的异常 (例如网络错误)
        print(f"{Fore.RED}连接 Ollama 服务时出错: {e}{Style.RESET_ALL}")
        return False


def get_available_models(ollama_url: str) -> list[str]:
    """获取 Docker 环境中可用的模型列表。"""
    try:
        # 向 Ollama 的标签 API 端点发送 GET 请求以获取模型列表
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models_data = response.json().get("models", []) # 解析 JSON 响应并获取 "models" 列表
            return [m["name"] for m in models_data] # 提取每个模型的名称
            
        print(f"{Fore.RED}从 Ollama 服务获取可用模型列表失败。状态码: {response.status_code}{Style.RESET_ALL}")
        return []
    except requests.RequestException as e:
        print(f"{Fore.RED}获取可用模型时出错: {e}{Style.RESET_ALL}")
        return []


def download_model(model_name: str, ollama_url: str) -> bool:
    """在 Docker 环境中下载模型。"""
    print(f"{Fore.YELLOW}正在将模型 {model_name} 下载到 Docker Ollama 容器中...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}这可能需要一些时间。请耐心等待。{Style.RESET_ALL}")
    
    # 步骤 1: 发起下载请求
    try:
        # 向 Ollama 的拉取 API 端点发送 POST 请求以下载模型
        response = requests.post(f"{ollama_url}/api/pull", json={"name": model_name}, timeout=10) # 设置10秒超时用于发起请求
        if response.status_code != 200: # 如果发起下载失败
            print(f"{Fore.RED}发起模型下载失败。状态码: {response.status_code}{Style.RESET_ALL}")
            if response.text: # 如果响应体中有错误信息，则打印出来
                print(f"{Fore.RED}错误: {response.text}{Style.RESET_ALL}")
            return False
    except requests.RequestException as e:
        print(f"{Fore.RED}发起下载请求时出错: {e}{Style.RESET_ALL}")
        return False
    
    # 步骤 2: 监控下载进度
    print(f"{Fore.CYAN}下载已发起。正在定期检查完成情况...{Style.RESET_ALL}")
    
    total_wait_time = 0 # 已等待总时间
    max_wait_time = 1800  # 最大等待时间30分钟 (1800秒)
    check_interval = 10  # 每10秒检查一次
    
    # 循环检查，直到超过最大等待时间
    while total_wait_time < max_wait_time:
        # 检查模型是否已下载完成
        available_models = get_available_models(ollama_url)
        if model_name in available_models:
            print(f"{Fore.GREEN}模型 {model_name} 下载成功。{Style.RESET_ALL}")
            return True # 下载完成
            
        # 等待一段时间再检查
        time.sleep(check_interval)
        total_wait_time += check_interval
        
        # 每分钟打印一次状态消息
        if total_wait_time % 60 == 0:
            minutes = total_wait_time // 60
            print(f"{Fore.CYAN}下载进行中... (已过 {minutes} 分钟){Style.RESET_ALL}")
    
    # 如果循环结束仍未下载完成，则视为超时
    print(f"{Fore.RED}等待模型下载超时 ({max_wait_time // 60} 分钟)。{Style.RESET_ALL}")
    return False


def delete_model(model_name: str, ollama_url: str) -> bool:
    """在 Docker 环境中删除模型。"""
    print(f"{Fore.YELLOW}正在从 Docker 容器中删除模型 {model_name}...{Style.RESET_ALL}")
    
    try:
        # 向 Ollama 的删除 API 端点发送 DELETE 请求
        response = requests.delete(f"{ollama_url}/api/delete", json={"name": model_name}, timeout=10)
        if response.status_code == 200:
            print(f"{Fore.GREEN}模型 {model_name} 删除成功。{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}删除模型失败。状态码: {response.status_code}{Style.RESET_ALL}")
            if response.text:
                print(f"{Fore.RED}错误: {response.text}{Style.RESET_ALL}")
            return False
    except requests.RequestException as e:
        print(f"{Fore.RED}删除模型时出错: {e}{Style.RESET_ALL}")
        return False