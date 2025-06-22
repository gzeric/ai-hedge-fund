import asyncio
import json
from langchain_core.messages import HumanMessage # LangChain 核心消息类型
from langgraph.graph import END, StateGraph # LangGraph 用于构建状态图

from src.agents.portfolio_manager import portfolio_management_agent # 投资组合管理代理
from src.agents.risk_manager import risk_management_agent # 风险管理代理
from src.main import start # 图的起始节点函数
from src.utils.analysts import ANALYST_CONFIG # 分析师配置
from src.graph.state import AgentState # 图的状态定义


# 辅助函数，用于创建代理图 (agent graph)
def create_graph(selected_agents: list[str]) -> StateGraph:
    """根据选定的代理创建工作流程图。"""
    graph = StateGraph(AgentState) # 初始化状态图，使用 AgentState 作为状态定义
    graph.add_node("start_node", start) # 添加起始节点

    # 过滤掉不在 analyst.py 配置中的代理
    selected_agents = [agent for agent in selected_agents if agent in ANALYST_CONFIG]

    # 从配置中获取分析师节点信息
    # analyst_nodes 是一个字典，键是代理名称，值是 (节点名称, 节点处理函数)
    analyst_nodes = {key: (f"{key}_agent", config["agent_func"]) for key, config in ANALYST_CONFIG.items()}

    # 添加选定的分析师节点到图中
    for agent_name in selected_agents:
        node_name, node_func = analyst_nodes[agent_name]
        graph.add_node(node_name, node_func) # 添加节点
        graph.add_edge("start_node", node_name) #添加入口边：从起始节点连接到该分析师节点

    # 目前总是添加风险管理和投资组合管理代理
    graph.add_node("risk_management_agent", risk_management_agent)
    graph.add_node("portfolio_manager", portfolio_management_agent)

    # 将选定的分析师节点连接到风险管理节点
    for agent_name in selected_agents:
        node_name = analyst_nodes[agent_name][0]
        graph.add_edge(node_name, "risk_management_agent")

    # 将风险管理代理连接到投资组合管理代理
    graph.add_edge("risk_management_agent", "portfolio_manager")

    # 将投资组合管理代理连接到结束节点 (END)
    graph.add_edge("portfolio_manager", END)

    # 设置图的入口点为 "start_node"
    graph.set_entry_point("start_node")
    return graph


async def run_graph_async(graph, portfolio, tickers, start_date, end_date, model_name, model_provider, request=None):
    """run_graph 的异步包装器，以便与 asyncio 一起工作。"""
    # 使用 run_in_executor 在单独的线程中运行同步函数，
    # 这样它就不会阻塞事件循环。
    loop = asyncio.get_running_loop() # 获取当前事件循环
    # loop.run_in_executor(executor, func, *args)
    # None 表示使用默认的线程池执行器 (ThreadPoolExecutor)
    result = await loop.run_in_executor(
        None,
        lambda: run_graph(graph, portfolio, tickers, start_date, end_date, model_name, model_provider, request)
    )
    return result


def run_graph(
    graph: StateGraph,
    portfolio: dict, # 投资组合数据
    tickers: list[str], # 股票代码列表
    start_date: str, # 开始日期
    end_date: str, # 结束日期
    model_name: str, # 模型名称
    model_provider: str, # 模型提供者
    request=None, # 完整的请求对象，可选
) -> dict:
    """
    使用给定的投资组合、股票代码、开始日期、结束日期、
    模型名称和模型提供者来运行图。
    """
    #调用图的 invoke 方法来执行
    return graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content="根据提供的数据做出交易决策。", # 给大模型的初始指令
                )
            ],
            "data": { # 业务相关数据
                "tickers": tickers,
                "portfolio": portfolio,
                "start_date": start_date,
                "end_date": end_date,
                "analyst_signals": {}, # 初始化分析师信号为空字典
            },
            "metadata": { # 元数据，控制行为或传递额外信息
                "show_reasoning": False, # 是否显示推理过程 (当前未使用)
                "model_name": model_name,
                "model_provider": model_provider,
                "request": request,  # 传递请求对象，以便代理可以访问特定于代理的模型配置
            },
        },
    )


def parse_hedge_fund_response(response: str) -> dict | None:
    """解析 JSON 字符串并返回一个字典。如果解析失败则返回 None。"""
    try:
        # 尝试将响应字符串解析为 JSON 对象 (字典)
        return json.loads(response)
    except json.JSONDecodeError as e:
        # 如果发生 JSON 解码错误 (例如，字符串不是有效的 JSON)
        print(f"JSON 解码错误: {e}\n响应内容: {repr(response)}")
        return None
    except TypeError as e:
        # 如果响应类型不是字符串 (json.loads 需要字符串输入)
        print(f"无效的响应类型 (期望字符串，得到 {type(response).__name__}): {e}")
        return None
    except Exception as e:
        # 捕获其他所有在解析过程中可能发生的未知错误
        print(f"解析响应时发生意外错误: {e}\n响应内容: {repr(response)}")
        return None
