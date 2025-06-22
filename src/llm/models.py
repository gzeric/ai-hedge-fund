import os # 操作系统相关功能，例如读取环境变量
import json # JSON 文件处理
from langchain_anthropic import ChatAnthropic # Anthropic 聊天模型
from langchain_deepseek import ChatDeepSeek # DeepSeek 聊天模型
from langchain_google_genai import ChatGoogleGenerativeAI # Google Gemini 聊天模型
from langchain_groq import ChatGroq # Groq 聊天模型
from langchain_openai import ChatOpenAI # OpenAI 聊天模型
from langchain_ollama import ChatOllama # Ollama 本地聊天模型
from enum import Enum # 枚举类型
from pydantic import BaseModel # Pydantic 数据模型
from typing import Tuple, List # 类型提示
from pathlib import Path # 路径操作


# 定义支持的 LLM 提供商枚举
class ModelProvider(str, Enum):
    """支持的 LLM 提供商枚举"""

    ANTHROPIC = "Anthropic"
    DEEPSEEK = "DeepSeek"
    GEMINI = "Gemini"
    GROQ = "Groq"
    OPENAI = "OpenAI"
    OLLAMA = "Ollama"


# 定义 LLM 模型配置的数据类
class LLMModel(BaseModel):
    """代表一个 LLM 模型的配置"""

    display_name: str  # 在UI中显示的名称
    model_name: str    # 实际的模型名称 (API 调用时使用)
    provider: ModelProvider # 模型提供商

    def to_choice_tuple(self) -> Tuple[str, str, str]:
        """转换为 questionary 选项所需的元组格式 (显示名称, 模型名称, 提供商值)"""
        return (self.display_name, self.model_name, self.provider.value)

    def is_custom(self) -> bool:
        """检查模型是否为自定义模型 (标志为 "-")"""
        return self.model_name == "-"

    def has_json_mode(self) -> bool:
        """检查模型是否支持 JSON 模式。"""
        # DeepSeek 和 Gemini 目前在 LangChain 中可能没有直接的 JSON 模式支持或配置方式
        if self.is_deepseek() or self.is_gemini():
            return False
        # 只有特定的 Ollama 模型支持 JSON 模式
        if self.is_ollama():
            # 这是一个示例，实际支持情况取决于具体的 Ollama 模型和 LangChain Ollama 集成
            return "llama3" in self.model_name or "neural-chat" in self.model_name
        return True # 假设其他提供商 (OpenAI, Anthropic, Groq) 支持 JSON 模式

    def is_deepseek(self) -> bool:
        """检查模型是否为 DeepSeek 模型"""
        return self.model_name.startswith("deepseek")

    def is_gemini(self) -> bool:
        """检查模型是否为 Gemini 模型"""
        return self.model_name.startswith("gemini")

    def is_ollama(self) -> bool:
        """检查模型是否为 Ollama 模型"""
        return self.provider == ModelProvider.OLLAMA


# 从 JSON 文件加载模型列表
def load_models_from_json(json_path: str) -> List[LLMModel]:
    """从 JSON 文件加载模型配置列表"""
    with open(json_path, 'r', encoding='utf-8') as f: # 指定 utf-8 编码
        models_data = json.load(f)
    
    models = []
    for model_data in models_data:
        # 将字符串类型的 provider 转换为 ModelProvider 枚举成员
        try:
            provider_enum = ModelProvider(model_data["provider"])
        except ValueError:
            print(f"警告: 在 {json_path} 中找到未知的提供商 '{model_data['provider']}'。跳过此模型。")
            continue # 如果提供商无效，则跳过此模型

        models.append(
            LLMModel(
                display_name=model_data["display_name"],
                model_name=model_data["model_name"],
                provider=provider_enum
            )
        )
    return models


# 获取 JSON 文件的路径
current_dir = Path(__file__).parent # 当前文件所在目录
models_json_path = current_dir / "api_models.json" # API 模型配置文件路径
ollama_models_json_path = current_dir / "ollama_models.json" # Ollama 模型配置文件路径

# 从 JSON 加载可用的 API 模型
AVAILABLE_MODELS = load_models_from_json(str(models_json_path))

# 从 JSON 加载可用的 Ollama 模型
OLLAMA_MODELS = load_models_from_json(str(ollama_models_json_path))

# 创建 LLM_ORDER 列表，格式为 UI (questionary) 所期望的
LLM_ORDER = [model.to_choice_tuple() for model in AVAILABLE_MODELS]

# 单独创建 Ollama 模型的 LLM_ORDER 列表
OLLAMA_LLM_ORDER = [model.to_choice_tuple() for model in OLLAMA_MODELS]


def get_model_info(model_name: str, model_provider: str) -> LLMModel | None:
    """根据模型名称和提供商获取模型信息"""
    all_models = AVAILABLE_MODELS + OLLAMA_MODELS # 合并所有模型列表进行搜索
    # 使用 next 和生成器表达式查找匹配的模型，如果找不到则返回 None
    return next((model for model in all_models if model.model_name == model_name and model.provider.value == model_provider), None)


def get_models_list() -> list[dict]:
    """获取用于 API 响应的模型列表。"""
    return [
        {
            "display_name": model.display_name,
            "model_name": model.model_name,
            "provider": model.provider.value # 返回枚举的值 (字符串)
        }
        for model in AVAILABLE_MODELS # 通常只暴露 API 模型给外部 API
    ]


# 根据模型名称和提供商获取相应的 LangChain聊天模型实例
def get_model(model_name: str, model_provider: ModelProvider) -> ChatOpenAI | ChatGroq | ChatOllama | ChatAnthropic | ChatDeepSeek | ChatGoogleGenerativeAI | None:
    """
    根据提供的模型名称和提供商，返回相应的 LangChain 聊天模型实例。
    会自动从环境变量中读取 API 密钥。
    """
    if model_provider == ModelProvider.GROQ:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print(f"API 密钥错误: 请确保 GROQ_API_KEY 已在您的 .env 文件中设置。")
            raise ValueError("未找到 Groq API 密钥。请确保 GROQ_API_KEY 已在您的 .env 文件中设置。")
        return ChatGroq(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.OPENAI:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE") # 可选的 OpenAI API 基础 URL
        if not api_key:
            print(f"API 密钥错误: 请确保 OPENAI_API_KEY 已在您的 .env 文件中设置。")
            raise ValueError("未找到 OpenAI API 密钥。请确保 OPENAI_API_KEY 已在您的 .env 文件中设置。")
        return ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url if base_url else None)
    elif model_provider == ModelProvider.ANTHROPIC:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print(f"API 密钥错误: 请确保 ANTHROPIC_API_KEY 已在您的 .env 文件中设置。")
            raise ValueError("未找到 Anthropic API 密钥。请确保 ANTHROPIC_API_KEY 已在您的 .env 文件中设置。")
        return ChatAnthropic(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.DEEPSEEK:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            print(f"API 密钥错误: 请确保 DEEPSEEK_API_KEY 已在您的 .env 文件中设置。")
            raise ValueError("未找到 DeepSeek API 密钥。请确保 DEEPSEEK_API_KEY 已在您的 .env 文件中设置。")
        return ChatDeepSeek(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.GEMINI:
        api_key = os.getenv("GOOGLE_API_KEY") # Gemini 使用 Google API Key
        if not api_key:
            print(f"API 密钥错误: 请确保 GOOGLE_API_KEY 已在您的 .env 文件中设置。")
            raise ValueError("未找到 Google API 密钥。请确保 GOOGLE_API_KEY 已在您的 .env 文件中设置。")
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key) # 注意参数名为 google_api_key
    elif model_provider == ModelProvider.OLLAMA:
        # Ollama 使用基础 URL 而不是 API 密钥
        # 检查是否设置了 OLLAMA_HOST (用于 macOS 上的 Docker)
        ollama_host = os.getenv("OLLAMA_HOST", "localhost") # 默认为 localhost
        base_url = os.getenv("OLLAMA_BASE_URL", f"http://{ollama_host}:11434") # 默认Ollama URL
        return ChatOllama(
            model=model_name,
            base_url=base_url,
        )
    return None # 如果提供商不受支持
