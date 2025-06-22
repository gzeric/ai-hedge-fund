"""LLM (大语言模型) 相关的辅助函数"""

import json # JSON 处理库
from pydantic import BaseModel # Pydantic 用于数据模型验证
from src.llm.models import get_model, get_model_info, ModelProvider # 从模型模块导入相关函数和枚举
from src.utils.progress import progress # 进度更新工具
from src.graph.state import AgentState # 代理状态定义


def call_llm(
    prompt: any, # 发送给 LLM 的提示 (可以是字符串、消息列表等)
    pydantic_model: type[BaseModel], # 用于结构化 LLM 输出的 Pydantic 模型类
    agent_name: str | None = None, # 可选的代理名称，用于进度更新和模型配置提取
    state: AgentState | None = None, # 可选的状态对象，用于提取特定于代理的模型配置
    max_retries: int = 3, # 最大重试次数 (默认: 3)
    default_factory: callable | None = None, # 可选的工厂函数，用于在失败时创建默认响应
) -> BaseModel:
    """
    执行 LLM 调用，并带有重试逻辑。
    能够处理支持 JSON 模式和不支持 JSON 模式的模型。

    参数:
        prompt: 发送给 LLM 的提示。
        pydantic_model: 用于结构化输出的 Pydantic 模型类。
        agent_name: (可选) 代理名称，用于进度更新和模型配置提取。
        state: (可选) 状态对象，用于提取特定于代理的模型配置。
        max_retries: (可选) 最大重试次数，默认为3。
        default_factory: (可选) 在多次尝试失败后，用于创建默认响应的工厂函数。

    返回:
        指定 Pydantic 模型的一个实例。如果所有尝试都失败，则返回默认响应。
    """
    
    model_name: str | None = None
    model_provider: ModelProvider | str | None = None

    # 如果提供了 state 和 agent_name，则提取模型配置
    if state and agent_name:
        model_name, model_provider_val = get_agent_model_config(state, agent_name)
        # 尝试将 model_provider_val 转换为 ModelProvider 枚举
        try:
            model_provider = ModelProvider(model_provider_val)
        except ValueError:
            print(f"警告: 无效的 model_provider 值 '{model_provider_val}'。将回退到默认值。")
            model_provider = None # 或者抛出错误，取决于期望行为
    
    # 如果模型名称或提供商仍未提供，则回退到默认值
    if not model_name:
        model_name = "gpt-4o" # 默认模型
    if not model_provider:
        model_provider = ModelProvider.OPENAI # 默认提供商

    # 获取模型信息和 LangChain 模型实例
    model_info = get_model_info(model_name, model_provider.value if isinstance(model_provider, ModelProvider) else model_provider)
    llm = get_model(model_name, model_provider if isinstance(model_provider, ModelProvider) else ModelProvider(str(model_provider)))

    if not llm: # 如果 get_model 返回 None (例如，提供商无效)
        print(f"错误: 无法为模型 '{model_name}' (提供商: {model_provider}) 获取 LLM 实例。")
        return default_factory() if default_factory else create_default_response(pydantic_model)

    # 对于支持原生 JSON 模式的模型，配置结构化输出
    # 注意：model_info.has_json_mode() 的逻辑是：如果 *不* 是 (model_info 存在 且 model_info.has_json_mode() 为 False)
    # 换句话说，如果 model_info 不存在，或者 model_info.has_json_mode() 为 True，则使用 json_mode
    if not (model_info and not model_info.has_json_mode()):
        llm = llm.with_structured_output(
            pydantic_model,
            method="json_mode", # LangChain 的 JSON 模式方法
        )

    # 带重试逻辑调用 LLM
    for attempt in range(max_retries):
        try:
            # 调用 LLM
            result = llm.invoke(prompt)

            # 对于不支持原生 JSON 模式的模型 (例如某些 Gemini 或 DeepSeek 模型通过 LangChain 的当前集成方式)，
            # 需要从其内容中手动提取和解析 JSON。
            if model_info and not model_info.has_json_mode():
                if hasattr(result, 'content') and isinstance(result.content, str):
                    parsed_result_dict = extract_json_from_response(result.content)
                    if parsed_result_dict:
                        return pydantic_model(**parsed_result_dict) # 将解析的字典转换为 Pydantic 模型
                    else:
                        # 如果无法从内容中提取 JSON，则认为是一次失败的尝试
                        raise ValueError("无法从 LLM 响应中提取有效的 JSON。")
                else:
                    # 如果响应没有 .content 属性或不是字符串，则无法处理
                    raise TypeError(f"LLM 响应格式不符合预期 (期望有 content 字符串): {type(result)}")
            else:
                # 对于支持 JSON 模式的模型，结果应该已经是 Pydantic 模型实例
                return result

        except Exception as e:
            if agent_name:
                progress.update_status(agent_name, None, f"错误 - 重试 {attempt + 1}/{max_retries}")

            if attempt == max_retries - 1: # 如果达到最大重试次数
                print(f"LLM 调用在 {max_retries} 次尝试后失败: {e}")
                # 如果提供了 default_factory，则使用它创建默认响应
                if default_factory:
                    return default_factory()
                # 否则，创建一个通用的默认响应
                return create_default_response(pydantic_model)

    # 此处理论上不应到达，因为上面的重试逻辑会处理所有情况
    # 但为确保函数总有返回值，返回一个默认响应
    return create_default_response(pydantic_model)


def create_default_response(model_class: type[BaseModel]) -> BaseModel:
    """根据模型的字段创建一个安全的默认响应。"""
    default_values = {}
    for field_name, field_info in model_class.model_fields.items():
        # Pydantic v2 中，字段信息在 field_info.annotation
        annotation = field_info.annotation
        if annotation == str:
            default_values[field_name] = "分析出错，使用默认值"
        elif annotation == float:
            default_values[field_name] = 0.0
        elif annotation == int:
            default_values[field_name] = 0
        elif hasattr(annotation, "__origin__") and annotation.__origin__ == dict: # 检查是否为字典类型
            default_values[field_name] = {}
        elif hasattr(annotation, "__origin__") and annotation.__origin__ == list: # 检查是否为列表类型
            default_values[field_name] = []
        else:
            # 对于其他类型 (例如 Literal)，尝试使用第一个允许的值
            # Literal 的参数在 __args__ 中
            if hasattr(annotation, "__args__") and annotation.__args__:
                default_values[field_name] = annotation.__args__[0]
            else: # 其他未知类型或没有默认值的 Literal
                default_values[field_name] = None # 或者可以根据字段是否可选来决定

    return model_class(**default_values)


def extract_json_from_response(content: str) -> dict | None:
    """从 Markdown 格式的响应中提取 JSON。"""
    try:
        # 查找被 ```json ... ``` 包围的 JSON 块
        json_start_tag = "```json"
        json_end_tag = "```"

        start_index = content.find(json_start_tag)
        if start_index != -1:
            # 跳过 ```json 标签本身
            json_text_block = content[start_index + len(json_start_tag):]
            end_index = json_text_block.find(json_end_tag)
            if end_index != -1:
                # 提取 JSON 文本并去除首尾空格
                json_text = json_text_block[:end_index].strip()
                return json.loads(json_text) # 解析 JSON 字符串
        else: # 如果没有找到 ```json 标签，尝试直接解析整个内容
            return json.loads(content)

    except json.JSONDecodeError as e: # JSON 解析错误
        print(f"从响应中提取 JSON 时出错 (JSONDecodeError): {e}")
    except Exception as e: # 其他潜在错误
        print(f"从响应中提取 JSON 时发生意外错误: {e}")
    return None # 如果提取或解析失败，返回 None


def get_agent_model_config(state: AgentState, agent_name: str) -> tuple[str, str]:
    """
    从状态中获取特定代理的模型配置。
    如果特定于代理的配置不可用，则回退到全局模型配置。
    """
    # 尝试从 state['metadata']['request'] 获取请求对象
    # 这个 request 对象被期望有一个 get_agent_model_config 方法
    request_obj = state.get("metadata", {}).get("request")

    # 特殊处理 portfolio_manager，它可能直接从 metadata 获取配置
    if agent_name == 'portfolio_manager':
        model_name_pm = state.get("metadata", {}).get("model_name", "gpt-4o")
        model_provider_pm = state.get("metadata", {}).get("model_provider", "OPENAI") # 默认为 OpenAI
        return model_name_pm, str(model_provider_pm) # 确保提供商是字符串
    
    # 如果存在 request 对象并且它有 get_agent_model_config 方法
    if request_obj and hasattr(request_obj, 'get_agent_model_config'):
        # 获取特定于代理的模型配置
        model_name_agent, model_provider_agent = request_obj.get_agent_model_config(agent_name)
        # 如果 model_provider_agent 是枚举类型，则取其值；否则转换为字符串
        return model_name_agent, model_provider_agent.value if hasattr(model_provider_agent, 'value') else str(model_provider_agent)
    
    # 如果上述条件都不满足，则回退到全局配置
    # 从 state['metadata'] 获取全局模型名称和提供商
    model_name_global = state.get("metadata", {}).get("model_name", "gpt-4o") # 默认模型
    model_provider_global = state.get("metadata", {}).get("model_provider", "OPENAI") # 默认提供商
    
    # 如果 model_provider_global 是枚举类型，则取其值
    if hasattr(model_provider_global, 'value'):
        model_provider_global_str = model_provider_global.value
    else:
        model_provider_global_str = str(model_provider_global)
    
    return model_name_global, model_provider_global_str
