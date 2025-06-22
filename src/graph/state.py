from typing_extensions import Annotated, Sequence, TypedDict # 类型提示工具
import operator # 用于操作符，例如 operator.add
from langchain_core.messages import BaseMessage # LangChain 核心消息基类
import json # JSON 操作库


def merge_dicts(a: dict[str, any], b: dict[str, any]) -> dict[str, any]:
    """
    合并两个字典。如果键冲突，字典 b 中的值将覆盖字典 a 中的值。
    这是 LangGraph 中状态更新的常用方法。
    """
    return {**a, **b} # 使用字典解包和合并


# 定义代理状态 (AgentState)
# AgentState 是一个 TypedDict，它定义了在 LangGraph 中流动的状态的结构。
# 每个字段都使用 Annotated 进行了类型注解，并指定了当多个节点更新同一字段时如何合并这些更新。
class AgentState(TypedDict):
    # 'messages' 字段存储一系列 BaseMessage 对象。
    # 当多个节点向 'messages' 添加消息时，使用 operator.add (列表连接) 来合并它们。
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # 'data' 字段是一个字典，用于存储各种业务逻辑数据。
    # 当多个节点更新 'data' 时，使用上面定义的 merge_dicts 函数来合并字典。
    data: Annotated[dict[str, any], merge_dicts]

    # 'metadata' 字段是一个字典，用于存储元数据或控制信息。
    # 当多个节点更新 'metadata' 时，也使用 merge_dicts 函数来合并。
    metadata: Annotated[dict[str, any], merge_dicts]


def show_agent_reasoning(output: any, agent_name: str):
    """
    以易于阅读的格式打印代理的输出/推理过程。
    主要用于调试和演示。

    参数:
      output (any): 代理产生的输出，可以是字符串、字典或列表。
      agent_name (str): 产生此输出的代理的名称。
    """
    print(f"\n{'=' * 10} {agent_name.center(28)} {'=' * 10}") # 打印带代理名称的标题

    def convert_to_serializable(obj: any) -> any:
        """
        递归地将对象转换为 JSON 可序列化的格式。
        处理常见的不可序列化类型，如 Pandas 对象或自定义对象。
        """
        if hasattr(obj, "to_dict"):  # 处理 Pandas Series/DataFrame
            return obj.to_dict()
        elif hasattr(obj, "__dict__"):  # 处理具有 __dict__ 属性的自定义对象
            return obj.__dict__
        elif isinstance(obj, (int, float, bool, str, type(None))): # 基本可序列化类型
            return obj
        elif isinstance(obj, (list, tuple)): # 列表和元组
            return [convert_to_serializable(item) for item in obj]
        elif isinstance(obj, dict): # 字典
            return {key: convert_to_serializable(value) for key, value in obj.items()}
        else: # 其他所有类型，回退到其字符串表示形式
            return str(obj)

    if isinstance(output, (dict, list)):
        # 如果输出本身是字典或列表，先尝试将其转换为完全可序列化的格式
        serializable_output = convert_to_serializable(output)
        print(json.dumps(serializable_output, indent=2, ensure_ascii=False)) # ensure_ascii=False 支持中文字符
    else: # 如果输出不是字典或列表 (可能是字符串)
        try:
            # 尝试将字符串解析为 JSON 并进行格式化打印
            parsed_output = json.loads(str(output)) # 先确保是字符串
            print(json.dumps(parsed_output, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            # 如果不是有效的 JSON 字符串，则直接打印原始输出
            print(output)
        except Exception:
            # 其他可能的转换错误，直接打印原始输出
            print(output)


    print("=" * 48) # 打印页脚分隔符
