from colorama import Fore, Style # 用于在终端输出带颜色的文本
from tabulate import tabulate # 用于将数据格式化为表格
from .analysts import ANALYST_ORDER # 从 analysts 模块导入分析师顺序配置
import os # 操作系统相关功能，例如清屏
import json # JSON 处理


def sort_agent_signals(signals: list) -> list:
    """按照预定义的顺序对代理(分析师)信号进行排序。"""
    # 从 ANALYST_ORDER 创建顺序映射 (显示名称 -> 索引)
    # ANALYST_ORDER 是一个元组列表，格式为 [(display_name, key), ...]
    analyst_display_to_order_idx = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}

    # 为风险管理代理添加一个特定的顺序，通常放在最后
    # 注意：这里的 "Risk Management" 是硬编码的，需要与代理名称匹配
    # 如果代理名称是 "risk_management_agent"，那么在提取 agent_name 时会被处理成 "Risk Management"
    analyst_display_to_order_idx["Risk Management"] = len(ANALYST_ORDER)

    # 对信号列表进行排序
    # 排序的键 (key) 是一个 lambda 函数，它尝试从 analyst_display_to_order_idx 中获取代理名称的顺序索引
    # 代理名称 (x[0]) 需要去除颜色代码才能正确匹配
    # 如果代理名称不在映射中 (例如，新的或未配置的代理)，则赋予一个较大的默认顺序值 (999)，使其排在最后
    return sorted(signals, key=lambda x: analyst_display_to_order_idx.get(x[0].replace(Fore.CYAN, "").replace(Style.RESET_ALL, ""), 999))


def print_trading_output(result: dict) -> None:
    """
    以带颜色的表格格式打印多个股票代码的交易结果。

    参数:
        result (dict): 包含多个股票代码的决策和分析师信号的字典。
                       结构示例:
                       {
                           "decisions": {"AAPL": {"action": "BUY", ...}, "MSFT": {...}},
                           "analyst_signals": {"tech_analyst": {"AAPL": {"signal": "BULLISH", ...}}, ...}
                       }
    """
    decisions = result.get("decisions") # 获取所有股票的交易决策
    if not decisions:
        print(f"{Fore.RED}没有可用的交易决策{Style.RESET_ALL}")
        return

    # 遍历每个股票代码的决策
    for ticker, decision in decisions.items():
        print(f"\n{Fore.WHITE}{Style.BRIGHT}{ticker} 的分析结果{Style.RESET_ALL}") # 打印股票代码标题
        print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}") # 打印分隔线

        # 准备该股票代码的分析师信号表格数据
        table_data = []
        # 遍历所有分析师的信号 (result.get("analyst_signals", {}) 确保如果信号不存在则返回空字典)
        for agent_key, ticker_signals_map in result.get("analyst_signals", {}).items():
            if ticker not in ticker_signals_map: # 如果当前分析师没有对这个股票的信号，则跳过
                continue
                
            # 在“代理分析”部分跳过风险管理代理的信号（它通常不提供直接的买卖信号）
            if agent_key == "risk_management_agent":
                continue

            signal_details = ticker_signals_map[ticker] # 获取该股票的具体信号内容
            # 将代理键名转换为更易读的显示名称 (例如 "technical_analyst_agent" -> "Technical Analyst")
            agent_display_name = agent_key.replace("_agent", "").replace("_", " ").title()
            signal_type = signal_details.get("signal", "").upper() # 获取信号类型 (BULLISH, BEARISH, NEUTRAL)，转为大写
            confidence = signal_details.get("confidence", 0) # 获取置信度，默认为0

            # 根据信号类型设置颜色
            signal_color = {
                "BULLISH": Fore.GREEN, # 看涨为绿色
                "BEARISH": Fore.RED,   # 看跌为红色
                "NEUTRAL": Fore.YELLOW, # 中性为黄色
            }.get(signal_type, Fore.WHITE) # 默认为白色
            
            # 获取并格式化推理过程（如果存在）
            reasoning_str = ""
            if "reasoning" in signal_details and signal_details["reasoning"]:
                reasoning_content = signal_details["reasoning"]
                
                # 处理不同类型的推理内容 (字符串、字典等)
                if isinstance(reasoning_content, str):
                    reasoning_str = reasoning_content
                elif isinstance(reasoning_content, dict):
                    # 将字典转换为格式化的 JSON 字符串
                    reasoning_str = json.dumps(reasoning_content, indent=2, ensure_ascii=False) # ensure_ascii=False 支持中文
                else:
                    # 将其他类型转换为字符串
                    reasoning_str = str(reasoning_content)
                
                # 对过长的推理文本进行换行处理，使其更易读
                wrapped_reasoning = ""
                current_line = ""
                max_line_length = 60 # 表格列的固定宽度
                for word in reasoning_str.split():
                    if len(current_line) + len(word) + 1 > max_line_length:
                        wrapped_reasoning += current_line + "\n"
                        current_line = word
                    else:
                        if current_line:
                            current_line += " " + word
                        else:
                            current_line = word
                if current_line: # 添加最后一行
                    wrapped_reasoning += current_line
                reasoning_str = wrapped_reasoning

            table_data.append( # 添加一行到表格数据
                [
                    f"{Fore.CYAN}{agent_display_name}{Style.RESET_ALL}", # 代理名称
                    f"{signal_color}{signal_type}{Style.RESET_ALL}",    # 信号类型 (带颜色)
                    f"{Fore.WHITE}{confidence}%{Style.RESET_ALL}",     # 置信度
                    f"{Fore.WHITE}{reasoning_str}{Style.RESET_ALL}",    # 推理过程
                ]
            )

        # 根据预定义的顺序对信号进行排序
        table_data = sort_agent_signals(table_data)

        print(f"\n{Fore.WHITE}{Style.BRIGHT}代理分析:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        # 使用 tabulate 打印分析师信号表格
        print(
            tabulate(
                table_data,
                headers=[f"{Fore.WHITE}代理", "信号", "置信度", "推理"], # 表头
                tablefmt="grid", # 表格格式
                colalign=("left", "center", "right", "left"), # 列对齐方式
            )
        )

        # 打印交易决策表格
        action = decision.get("action", "").upper() # 获取交易动作，转为大写
        # 根据交易动作设置颜色
        action_color = {
            "BUY": Fore.GREEN,   # 买入为绿色
            "SELL": Fore.RED,    # 卖出为红色
            "HOLD": Fore.YELLOW, # 持有为黄色
            "COVER": Fore.GREEN, # 回补为绿色 (平空仓)
            "SHORT": Fore.RED,   # 做空为红色
        }.get(action, Fore.WHITE) # 默认为白色

        # 获取并格式化决策的推理过程
        reasoning_decision = decision.get("reasoning", "")
        wrapped_reasoning_decision = ""
        if reasoning_decision: # 与上面分析师信号的推理过程格式化逻辑相同
            current_line = ""
            max_line_length = 60
            for word in reasoning_decision.split():
                if len(current_line) + len(word) + 1 > max_line_length:
                    wrapped_reasoning_decision += current_line + "\n"
                    current_line = word
                else:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
            if current_line:
                wrapped_reasoning_decision += current_line

        # 准备交易决策表格数据
        decision_data = [
            ["操作", f"{action_color}{action}{Style.RESET_ALL}"],
            ["数量", f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}"],
            ["置信度", f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}"], # 保留一位小数
            ["推理", f"{Fore.WHITE}{wrapped_reasoning_decision}{Style.RESET_ALL}"],
        ]
        
        print(f"\n{Fore.WHITE}{Style.BRIGHT}交易决策:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        # 使用 tabulate 打印交易决策表格
        print(tabulate(decision_data, tablefmt="grid", colalign=("left", "left")))

    # 打印投资组合摘要
    print(f"\n{Fore.WHITE}{Style.BRIGHT}投资组合摘要:{Style.RESET_ALL}")
    portfolio_data = [] # 用于存储摘要表格数据
    
    # 提取投资组合经理的推理 (假设对所有股票是相同的，取第一个非空的)
    portfolio_manager_reasoning = None
    for ticker, decision in decisions.items(): # 再次遍历决策以构建摘要表
        if decision.get("reasoning"): # 这个推理实际上是 PortfolioManager 对单个股票的决策推理
                                      # 如果需要一个总体的投资组合策略推理，它应该来自 PortfolioManager 的一个独立输出
            portfolio_manager_reasoning = decision.get("reasoning") # 这里可能需要调整逻辑以获取“总体策略”
            break
            
    # 填充投资组合摘要表格数据
    for ticker, decision in decisions.items():
        action = decision.get("action", "").upper()
        action_color = {
            "BUY": Fore.GREEN, "SELL": Fore.RED, "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN, "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)
        portfolio_data.append(
            [
                f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
                f"{action_color}{action}{Style.RESET_ALL}",
                f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}",
                f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
            ]
        )

    headers = [f"{Fore.WHITE}股票代码", "操作", "数量", "置信度"] # 摘要表头
    
    # 打印投资组合摘要表格
    print(
        tabulate(
            portfolio_data,
            headers=headers,
            tablefmt="grid",
            colalign=("left", "center", "right", "right"),
        )
    )
    
    # 打印投资组合经理的（总体）策略推理（如果可用）
    # 注意：当前的 portfolio_manager_reasoning 是从单个股票决策中提取的，可能不是真正的总体策略。
    # 一个更好的方法是让 PortfolioManager agent 输出一个专门的总体策略描述。
    if portfolio_manager_reasoning:
        reasoning_str_pm = ""
        if isinstance(portfolio_manager_reasoning, str):
            reasoning_str_pm = portfolio_manager_reasoning
        elif isinstance(portfolio_manager_reasoning, dict):
            reasoning_str_pm = json.dumps(portfolio_manager_reasoning, indent=2, ensure_ascii=False)
        else:
            reasoning_str_pm = str(portfolio_manager_reasoning)
            
        wrapped_reasoning_pm = "" # 格式化换行
        current_line_pm = ""
        max_line_length_pm = 80 # 总体策略可以宽一些
        for word in reasoning_str_pm.split():
            if len(current_line_pm) + len(word) + 1 > max_line_length_pm:
                wrapped_reasoning_pm += current_line_pm + "\n"
                current_line_pm = word
            else:
                if current_line_pm:
                    current_line_pm += " " + word
                else:
                    current_line_pm = word
        if current_line_pm:
            wrapped_reasoning_pm += current_line_pm
            
        print(f"\n{Fore.WHITE}{Style.BRIGHT}投资组合策略:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{wrapped_reasoning_pm}{Style.RESET_ALL}")


def print_backtest_results(table_rows: list) -> None:
    """以美观的表格格式打印回测结果。"""
    # 清屏 (Windows 使用 "cls",其他系统使用 "clear")
    os.system("cls" if os.name == "nt" else "clear")

    # 将行分为股票行和摘要行
    ticker_rows = []
    summary_rows = []

    for row_data in table_rows: # row_data 是 format_backtest_row 返回的列表
        # 检查是否为摘要行：摘要行的第二个元素 (索引1) 是一个包含 "PORTFOLIO SUMMARY" 的格式化字符串
        # 需要去除颜色代码进行判断
        if isinstance(row_data[1], str) and "PORTFOLIO SUMMARY" in row_data[1].replace(Fore.WHITE, "").replace(Style.BRIGHT, "").replace(Style.RESET_ALL, ""):
            summary_rows.append(row_data)
        else:
            ticker_rows.append(row_data)

    
    # 显示最新的投资组合摘要
    if summary_rows:
        latest_summary = summary_rows[-1] # 取最后一条摘要记录
        print(f"\n{Fore.WHITE}{Style.BRIGHT}投资组合摘要:{Style.RESET_ALL}")

        # 从格式化的字符串中提取数值并移除逗号以便转换为浮点数
        # 索引可能需要根据 format_backtest_row 的实际输出调整
        # 假设 format_backtest_row 返回的摘要行格式如下：
        # [date, "PORTFOLIO SUMMARY", "", "", "", "", total_pos_val_str, cash_bal_str, total_val_str, return_str, sharpe_str, sortino_str, drawdown_str]

        # 现金余额 (假设在索引7)
        cash_str_formatted = latest_summary[7]
        cash_str = cash_str_formatted.split("$")[1].split(Style.RESET_ALL)[0].replace(",", "") if "$" in cash_str_formatted else "0"
        # 总头寸价值 (假设在索引6)
        position_str_formatted = latest_summary[6]
        position_str = position_str_formatted.split("$")[1].split(Style.RESET_ALL)[0].replace(",", "") if "$" in position_str_formatted else "0"
        # 总价值 (假设在索引8)
        total_str_formatted = latest_summary[8]
        total_str = total_str_formatted.split("$")[1].split(Style.RESET_ALL)[0].replace(",", "") if "$" in total_str_formatted else "0"

        print(f"现金余额: {Fore.CYAN}${float(cash_str):,.2f}{Style.RESET_ALL}")
        print(f"总头寸价值: {Fore.YELLOW}${float(position_str):,.2f}{Style.RESET_ALL}")
        print(f"总价值: {Fore.WHITE}${float(total_str):,.2f}{Style.RESET_ALL}")
        print(f"回报率: {latest_summary[9]}") # 回报率字符串 (已带颜色)
        
        # 显示性能指标 (如果可用)
        if latest_summary[10]:  # 夏普比率
            print(f"夏普比率: {latest_summary[10]}")
        if latest_summary[11]:  # 索提诺比率
            print(f"索提诺比率: {latest_summary[11]}")
        if latest_summary[12]:  # 最大回撤
            print(f"最大回撤: {latest_summary[12]}")

    # 添加垂直间距
    print("\n" * 2)

    # 打印仅包含股票代码行的表格
    print(
        tabulate(
            ticker_rows,
            headers=[ # 表头
                "日期", "股票代码", "操作", "数量", "价格",
                "持股数", "头寸价值", "看涨数", "看跌数", "中性数",
            ],
            tablefmt="grid", # 表格格式
            colalign=( # 列对齐方式
                "left",   # 日期
                "left",   # 股票代码
                "center", # 操作
                "right",  # 数量
                "right",  # 价格
                "right",  # 持股数
                "right",  # 头寸价值
                "right",  # 看涨数
                "right",  # 看跌数
                "right",  # 中性数
            ),
        )
    )

    # 添加垂直间距
    print("\n" * 4)


def format_backtest_row(
    date: str, # 日期
    ticker: str, # 股票代码
    action: str, # 操作 (BUY, SELL, HOLD, SHORT, COVER)
    quantity: float, # 数量
    price: float, # 价格
    shares_owned: float, # 持有股数 (净值)
    position_value: float, # 头寸价值
    bullish_count: int, # 看涨信号数
    bearish_count: int, # 看跌信号数
    neutral_count: int, # 中性信号数
    is_summary: bool = False, # 是否为摘要行
    total_value: float | None = None, # 总价值 (摘要行用)
    return_pct: float | None = None, # 回报率 (摘要行用)
    cash_balance: float | None = None, # 现金余额 (摘要行用)
    total_position_value: float | None = None, # 总头寸价值 (摘要行用)
    sharpe_ratio: float | None = None, # 夏普比率 (摘要行用)
    sortino_ratio: float | None = None, # 索提诺比率 (摘要行用)
    max_drawdown: float | None = None, # 最大回撤 (摘要行用)
) -> list[any]:
    """格式化回测结果表格的一行。"""
    # 根据操作类型设置颜色
    action_color = {
        "BUY": Fore.GREEN, "COVER": Fore.GREEN,
        "SELL": Fore.RED, "SHORT": Fore.RED,
        "HOLD": Fore.WHITE, # 持有为白色
    }.get(action.upper(), Fore.WHITE) # 默认为白色

    if is_summary: # 如果是摘要行
        # 根据回报率正负设置颜色
        return_color = Fore.GREEN if return_pct is not None and return_pct >= 0 else Fore.RED
        # 返回摘要行的数据列表
        return [
            date,
            f"{Fore.WHITE}{Style.BRIGHT}投资组合摘要{Style.RESET_ALL}",
            "",  # 操作列为空
            "",  # 数量列为空
            "",  # 价格列为空
            "",  # 持股数列为空
            f"{Fore.YELLOW}${total_position_value:,.2f}{Style.RESET_ALL}" if total_position_value is not None else "",  # 总头寸价值
            f"{Fore.CYAN}${cash_balance:,.2f}{Style.RESET_ALL}" if cash_balance is not None else "",  # 现金余额
            f"{Fore.WHITE}${total_value:,.2f}{Style.RESET_ALL}" if total_value is not None else "",  # 总价值
            f"{return_color}{return_pct:+.2f}%{Style.RESET_ALL}" if return_pct is not None else "",  # 回报率 (带正负号，保留两位小数)
            f"{Fore.YELLOW}{sharpe_ratio:.2f}{Style.RESET_ALL}" if sharpe_ratio is not None else "",  # 夏普比率
            f"{Fore.YELLOW}{sortino_ratio:.2f}{Style.RESET_ALL}" if sortino_ratio is not None else "",  # 索提诺比率
            f"{Fore.RED}{abs(max_drawdown):.2f}%{Style.RESET_ALL}" if max_drawdown is not None else "",  # 最大回撤 (取绝对值)
        ]
    else: # 如果是普通股票行
        # 返回股票行的数据列表
        return [
            date, # 日期
            f"{Fore.CYAN}{ticker}{Style.RESET_ALL}", # 股票代码 (蓝色)
            f"{action_color}{action.upper()}{Style.RESET_ALL}", # 操作 (带颜色)
            f"{action_color}{quantity:,.0f}{Style.RESET_ALL}", # 数量 (带颜色，千位分隔，无小数)
            f"{Fore.WHITE}{price:,.2f}{Style.RESET_ALL}", # 价格 (白色，千位分隔，两位小数)
            f"{Fore.WHITE}{shares_owned:,.0f}{Style.RESET_ALL}", # 持股数 (白色，千位分隔，无小数)
            f"{Fore.YELLOW}{position_value:,.2f}{Style.RESET_ALL}", # 头寸价值 (黄色，千位分隔，两位小数)
            f"{Fore.GREEN}{bullish_count}{Style.RESET_ALL}", # 看涨数 (绿色)
            f"{Fore.RED}{bearish_count}{Style.RESET_ALL}", # 看跌数 (红色)
            f"{Fore.BLUE}{neutral_count}{Style.RESET_ALL}", # 中性数 (蓝色，之前是BLUE，可以保持或改为YELLOW/WHITE)
        ]
