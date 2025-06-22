import sys # 系统相关功能

from dotenv import load_dotenv # 用于从 .env 文件加载环境变量
from langchain_core.messages import HumanMessage # LangChain 核心消息类型
from langgraph.graph import END, StateGraph # LangGraph 用于构建和运行状态图
from colorama import Fore, Style, init # 用于在终端输出彩色文本
import questionary # 用于创建交互式命令行界面
from src.agents.portfolio_manager import portfolio_management_agent # 投资组合管理代理
from src.agents.risk_manager import risk_management_agent # 风险管理代理
from src.graph.state import AgentState # 代理状态定义
from src.utils.display import print_trading_output # 显示交易输出的工具
from src.utils.analysts import ANALYST_ORDER, get_analyst_nodes # 分析师配置和获取节点工具
from src.utils.progress import progress # 进度跟踪工具
from src.llm.models import LLM_ORDER, OLLAMA_LLM_ORDER, get_model_info, ModelProvider # LLM 模型相关
from src.utils.ollama import ensure_ollama_and_model # Ollama 相关工具

import argparse # 用于解析命令行参数
from datetime import datetime # 日期和时间操作
from dateutil.relativedelta import relativedelta # 更灵活的日期偏移计算
from src.utils.visualize import save_graph_as_png # 可视化图并保存为图片
import json # JSON 操作库

# 从 .env 文件加载环境变量 (例如 API 密钥)
load_dotenv()

# 初始化 colorama，使其在 Windows 等终端中也能正确显示颜色，并自动重置颜色
init(autoreset=True)


def parse_hedge_fund_response(response: str) -> dict | None:
    """解析包含对冲基金响应的 JSON 字符串，并返回一个字典。"""
    try:
        return json.loads(response) # 尝试解析 JSON
    except json.JSONDecodeError as e: # 如果 JSON 格式无效
        print(f"JSON 解码错误: {e}\n响应: {repr(response)}")
        return None
    except TypeError as e: # 如果响应不是字符串类型
        print(f"无效的响应类型 (期望字符串，得到 {type(response).__name__}): {e}")
        return None
    except Exception as e: # 其他未知错误
        print(f"解析响应时发生意外错误: {e}\n响应: {repr(response)}")
        return None


##### 运行对冲基金 (Run the Hedge Fund) #####
def run_hedge_fund(
    tickers: list[str], # 要分析的股票代码列表
    start_date: str, # 数据分析的开始日期
    end_date: str, # 数据分析的结束日期
    portfolio: dict, # 当前的投资组合状态
    show_reasoning: bool = False, # 是否显示每个代理的推理过程
    selected_analysts: list[str] = [], # 用户选择的分析师列表
    model_name: str = "gpt-4o", # 使用的 LLM 模型名称
    model_provider: str = "OpenAI", # LLM 提供商
) -> dict:
    """
    运行对冲基金的模拟。
    它会根据选定的分析师构建一个工作流程 (agent graph)，
    然后调用该工作流程处理输入数据并返回交易决策和分析师信号。
    """
    progress.start() # 开始进度跟踪

    try:
        # 如果用户自定义了分析师，则创建一个新的工作流程
        if selected_analysts:
            workflow = create_workflow(selected_analysts)
            agent = workflow.compile() # 编译工作流程图
        else:
            # 否则，使用预定义的或默认的 'app' (假设 'app' 是一个已编译的工作流程)
            # 注意：这里的 'app' 变量在当前上下文中未定义，如果 selected_analysts 为空，
            # 并且没有全局的 'app'，这里会引发 NameError。
            # 通常应该总是基于 selected_analysts (即使为空，也应创建默认工作流) 来创建 agent。
            # 为了安全，可以修改为：
            # workflow = create_workflow(selected_analysts if selected_analysts else None)
            # agent = workflow.compile()
            # 或者确保 'app' 变量在调用此函数前已定义为默认工作流。
            # 鉴于 create_workflow 的设计，更合理的做法是总是调用它。
            workflow = create_workflow(selected_analysts) # 即使为空，create_workflow 也会处理
            agent = workflow.compile()


        # 调用编译好的代理 (LangGraph 工作流程)
        final_state = agent.invoke(
            {
                "messages": [ # 初始消息，通常是给 LLM 的指令
                    HumanMessage(
                        content="根据提供的数据做出交易决策。",
                    )
                ],
                "data": { # 业务逻辑所需的数据
                    "tickers": tickers,
                    "portfolio": portfolio,
                    "start_date": start_date,
                    "end_date": end_date,
                    "analyst_signals": {}, # 初始化分析师信号为空字典
                },
                "metadata": { # 元数据，用于控制流程或传递额外信息
                    "show_reasoning": show_reasoning,
                    "model_name": model_name,
                    "model_provider": model_provider,
                },
            },
        )

        # 从最终状态中提取决策和分析师信号
        return {
            "decisions": parse_hedge_fund_response(final_state["messages"][-1].content), # 解析最后一个消息的内容作为决策
            "analyst_signals": final_state["data"]["analyst_signals"], # 获取所有分析师的信号
        }
    finally:
        progress.stop() # 停止进度跟踪


def start(state: AgentState) -> AgentState:
    """工作流程的起始节点。简单地返回初始状态。"""
    return state


def create_workflow(selected_analysts: list[str] | None = None) -> StateGraph:
    """
    根据选定的分析师创建 LangGraph 工作流程。
    如果 selected_analysts 为 None 或空，则使用所有默认分析师。
    """
    workflow = StateGraph(AgentState) # 初始化状态图
    workflow.add_node("start_node", start) # 添加起始节点

    # 从配置中获取所有可用的分析师节点
    analyst_nodes = get_analyst_nodes()

    # 如果未选择分析师，则默认为使用所有已配置的分析师
    if not selected_analysts: # 处理 None 或空列表的情况
        selected_analysts = list(analyst_nodes.keys()) # 获取所有分析师的键 (ID)

    # 添加选定的分析师节点到工作流程中
    for analyst_key in selected_analysts:
        if analyst_key in analyst_nodes: # 确保选定的分析师在配置中存在
            node_name, node_func = analyst_nodes[analyst_key]
            workflow.add_node(node_name, node_func) # 添加分析师节点
            workflow.add_edge("start_node", node_name) # 从起始节点连接到每个分析师节点
        else:
            print(f"警告: 未找到分析师 '{analyst_key}' 的配置，将跳过此分析师。")


    # 总是添加风险管理和投资组合管理代理
    workflow.add_node("risk_management_agent", risk_management_agent)
    workflow.add_node("portfolio_manager", portfolio_management_agent)

    # 将选定的（且有效的）分析师节点连接到风险管理节点
    for analyst_key in selected_analysts:
        if analyst_key in analyst_nodes:
            node_name = analyst_nodes[analyst_key][0]
            workflow.add_edge(node_name, "risk_management_agent") # 分析师 -> 风险管理

    # 连接风险管理代理到投资组合管理代理
    workflow.add_edge("risk_management_agent", "portfolio_manager")
    # 连接投资组合管理代理到结束节点 (END)
    workflow.add_edge("portfolio_manager", END)

    # 设置工作流程的入口点
    workflow.set_entry_point("start_node")
    return workflow


# 当此脚本作为主程序执行时:
if __name__ == "__main__":
    # 设置命令行参数解析器
    parser = argparse.ArgumentParser(description="运行对冲基金交易系统")
    parser.add_argument("--initial-cash", type=float, default=100000.0, help="初始现金头寸。默认为 100000.0")
    parser.add_argument("--margin-requirement", type=float, default=0.0, help="初始保证金要求。默认为 0.0")
    parser.add_argument("--tickers", type=str, required=True, help="以逗号分隔的股票代码列表")
    parser.add_argument(
        "--start-date",
        type=str,
        help="开始日期 (YYYY-MM-DD)。默认为结束日期前3个月",
    )
    parser.add_argument("--end-date", type=str, help="结束日期 (YYYY-MM-DD)。默认为今天")
    parser.add_argument("--show-reasoning", action="store_true", help="显示每个代理的推理过程")
    parser.add_argument("--show-agent-graph", action="store_true", help="显示代理图并保存为图片")
    parser.add_argument("--ollama", action="store_true", help="使用 Ollama 进行本地 LLM 推理")

    args = parser.parse_args() # 解析命令行参数

    # 从逗号分隔的字符串解析股票代码
    tickers = [ticker.strip().upper() for ticker in args.tickers.split(",")] #去除空格并转为大写

    # 选择分析师 (交互式)
    selected_analysts = None
    choices = questionary.checkbox(
        "选择您的 AI 分析师。",
        choices=[questionary.Choice(display, value=value) for display, value in ANALYST_ORDER], # 从配置中获取分析师选项
        instruction="\n\n说明: \n1. 按空格键选择/取消选择分析师。\n2. 按 'a' 键全选/全不选。\n3. 完成后按 Enter 键运行对冲基金。\n",
        validate=lambda x: len(x) > 0 or "您必须至少选择一位分析师。", # 验证至少选择一个
        style=questionary.Style( # 定义交互界面样式
            [
                ("checkbox-selected", "fg:green"),
                ("selected", "fg:green noinherit"),
                ("highlighted", "noinherit"),
                ("pointer", "noinherit"),
            ]
        ),
    ).ask() # 弹出选择提示

    if not choices: # 如果用户未选择 (例如按 Ctrl+C)
        print("\n\n收到中断信号。正在退出...")
        sys.exit(0)
    else:
        selected_analysts = choices
        print(f"\n已选分析师: {', '.join(Fore.GREEN + choice.title().replace('_', ' ') + Style.RESET_ALL for choice in choices)}\n")

    # 根据是否使用 Ollama 选择 LLM 模型
    model_name = ""
    model_provider = ""

    if args.ollama: # 如果命令行指定了 --ollama
        print(f"{Fore.CYAN}正在使用 Ollama 进行本地 LLM 推理。{Style.RESET_ALL}")

        # 从 Ollama 特定模型中选择
        model_name_str: str | None = questionary.select( # 类型注解确保清晰
            "选择您的 Ollama 模型:",
            choices=[questionary.Choice(display, value=value) for display, value, _ in OLLAMA_LLM_ORDER],
            style=questionary.Style(
                [
                    ("selected", "fg:green bold"),
                    ("pointer", "fg:green bold"),
                    ("highlighted", "fg:green"),
                    ("answer", "fg:green bold"),
                ]
            ),
        ).ask()
        model_name = model_name_str if model_name_str is not None else ""


        if not model_name: # 用户中断
            print("\n\n收到中断信号。正在退出...")
            sys.exit(0)

        if model_name == "-": # 如果选择 "自定义"
            custom_model_name: str | None = questionary.text("请输入自定义模型名称:").ask()
            model_name = custom_model_name if custom_model_name is not None else ""
            if not model_name:
                print("\n\n收到中断信号。正在退出...")
                sys.exit(0)

        # 确保 Ollama 已安装、正在运行且模型可用
        if not ensure_ollama_and_model(model_name):
            print(f"{Fore.RED}无法在没有 Ollama 和所选模型的情况下继续。{Style.RESET_ALL}")
            sys.exit(1)

        model_provider = ModelProvider.OLLAMA.value # 设置模型提供商为 Ollama
        print(f"\n已选 {Fore.CYAN}Ollama{Style.RESET_ALL} 模型: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}\n")
    else: # 使用标准的基于云的 LLM 选择
        model_choice_tuple: tuple[str, str] | None = questionary.select(
            "选择您的 LLM 模型:",
            choices=[questionary.Choice(display, value=(name, provider)) for display, name, provider in LLM_ORDER],
            style=questionary.Style(
                [
                    ("selected", "fg:green bold"),
                    ("pointer", "fg:green bold"),
                    ("highlighted", "fg:green"),
                    ("answer", "fg:green bold"),
                ]
            ),
        ).ask()


        if not model_choice_tuple: # 用户中断
            print("\n\n收到中断信号。正在退出...")
            sys.exit(0)

        model_name, model_provider_str_val = model_choice_tuple
        model_provider = model_provider_str_val # model_provider 现在是字符串形式的提供商名称


        # 使用辅助函数获取模型信息
        model_info = get_model_info(model_name, model_provider)
        if model_info:
            if model_info.is_custom(): # 如果是自定义模型
                custom_model_name_cloud: str | None = questionary.text("请输入自定义模型名称:").ask()
                model_name = custom_model_name_cloud if custom_model_name_cloud is not None else ""
                if not model_name:
                    print("\n\n收到中断信号。正在退出...")
                    sys.exit(0)

            print(f"\n已选 {Fore.CYAN}{model_provider}{Style.RESET_ALL} 模型: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}\n")
        else: # 理论上不应发生，因为是从列表中选择的
            model_provider = "Unknown" # 或者保留 model_provider_str_val
            print(f"\n已选模型: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL} (提供商未知或配置错误)\n")


    # 根据选定的分析师创建工作流程
    # 注意：这里的 'app' 变量在 run_hedge_fund 函数中可能未定义。
    # 应该在 run_hedge_fund 内部或此处确保工作流总是被创建和编译。
    # 为了清晰，直接在 run_hedge_fund 中处理工作流创建。
    # app = create_workflow(selected_analysts).compile() # 这行可以移到 run_hedge_fund 或在此处保留给全局 app (如果需要)

    if args.show_agent_graph: # 如果用户要求显示代理图
        # 编译一个临时的图用于可视化 (如果 'app' 不是全局的)
        temp_workflow_for_graph = create_workflow(selected_analysts)
        temp_app_for_graph = temp_workflow_for_graph.compile()
        file_path = "agent_graph.png" # 默认文件名
        if selected_analysts: # 如果选择了分析师，可以创建更具体的文件名
            file_path = "_".join(selected_analysts) + "_graph.png"
        save_graph_as_png(temp_app_for_graph, file_path) # 保存图为 PNG
        print(f"代理图已保存至: {file_path}")

    # 验证提供的日期格式是否正确
    if args.start_date:
        try:
            datetime.strptime(args.start_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("开始日期必须为 YYYY-MM-DD 格式")

    if args.end_date:
        try:
            datetime.strptime(args.end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("结束日期必须为 YYYY-MM-DD 格式")

    # 设置开始和结束日期
    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d") # 如果未提供，默认为今天
    if not args.start_date:
        # 如果未提供开始日期，则计算为结束日期前3个月
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = (end_date_obj - relativedelta(months=3)).strftime("%Y-%m-%d")
    else:
        start_date = args.start_date

    # 初始化投资组合，包含现金和股票头寸
    portfolio = {
        "cash": args.initial_cash,  # 初始现金金额
        "margin_requirement": args.margin_requirement,  # 初始保证金要求
        "margin_used": 0.0,  # 所有空头头寸使用的总保证金
        "positions": { # 各股票的头寸信息
            ticker: {
                "long": 0,  # 持有的多头股数
                "short": 0,  # 持有的空头股数
                "long_cost_basis": 0.0,  # 多头头寸的平均成本基础
                "short_cost_basis": 0.0,  # 空头头寸的平均卖出价格
                "short_margin_used": 0.0,  # 该股票空头头寸使用的保证金
            }
            for ticker in tickers
        },
        "realized_gains": { # 已实现收益/亏损
            ticker: {
                "long": 0.0,  # 来自多头头寸的已实现收益
                "short": 0.0,  # 来自空头头寸的已实现收益
            }
            for ticker in tickers
        },
    }

    # 运行对冲基金模拟
    result = run_hedge_fund(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        portfolio=portfolio,
        show_reasoning=args.show_reasoning, # 是否显示推理过程
        selected_analysts=selected_analysts, # 选定的分析师
        model_name=model_name, # LLM 模型名称
        model_provider=model_provider, # LLM 提供商 (字符串形式)
    )
    print_trading_output(result) # 打印最终的交易输出
