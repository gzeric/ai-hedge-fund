import sys # 系统相关功能

from datetime import datetime, timedelta # 日期和时间操作
from dateutil.relativedelta import relativedelta # 更灵活的日期偏移计算
import questionary # 用于创建交互式命令行界面

import matplotlib.pyplot as plt # 用于绘图
import pandas as pd # 数据分析库
from colorama import Fore, Style, init # 用于在终端输出彩色文本
import numpy as np # 数值计算库
import itertools # 用于创建迭代器

from src.llm.models import LLM_ORDER, OLLAMA_LLM_ORDER, get_model_info, ModelProvider # 大语言模型相关
from src.utils.analysts import ANALYST_ORDER # 分析师顺序定义
from src.main import run_hedge_fund # 主要的对冲基金运行逻辑
from src.tools.api import ( # API工具，用于获取数据
    get_company_news,
    get_price_data,
    get_prices,
    get_financial_metrics,
    get_insider_trades,
)
from src.utils.display import print_backtest_results, format_backtest_row # 显示回测结果的工具
from typing_extensions import Callable # 可调用类型提示
from src.utils.ollama import ensure_ollama_and_model # Ollama 相关工具

init(autoreset=True) # 初始化 colorama，自动重置颜色


class Backtester:
    """回测器类，用于模拟交易策略并评估其性能。"""
    def __init__(
        self,
        agent: Callable, # 交易代理 (一个可调用对象，例如函数)
        tickers: list[str], # 要回测的股票代码列表
        start_date: str, # 开始日期字符串 (YYYY-MM-DD)
        end_date: str, # 结束日期字符串 (YYYY-MM-DD)
        initial_capital: float, # 初始资金
        model_name: str = "gpt-4o", # 使用的LLM模型名称
        model_provider: str = "OpenAI", # LLM提供商 (OpenAI等)
        selected_analysts: list[str] = [], # 要纳入的分析师名称或ID列表
        initial_margin_requirement: float = 0.0, # 初始保证金要求 (例如0.5表示50%)
    ):
        """
        初始化回测器。
        :param agent: 交易代理 (Callable)。
        :param tickers: 要回测的股票代码列表。
        :param start_date: 开始日期字符串 (YYYY-MM-DD)。
        :param end_date: 结束日期字符串 (YYYY-MM-DD)。
        :param initial_capital: 初始投资组合现金。
        :param model_name: 要使用的LLM模型名称 (gpt-4o等)。
        :param model_provider: LLM提供商 (OpenAI等)。
        :param selected_analysts: 要整合的分析师名称或ID列表。
        :param initial_margin_requirement: 保证金比例 (例如0.5 = 50%)。
        """
        self.agent = agent
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.model_name = model_name
        self.model_provider = model_provider
        self.selected_analysts = selected_analysts

        # 初始化投资组合，支持多头和空头头寸
        self.portfolio_values = [] # 存储每日投资组合价值
        self.portfolio = {
            "cash": initial_capital, # 初始现金
            "margin_used": 0.0,  # 所有空头头寸使用的总保证金
            "margin_requirement": initial_margin_requirement,  # 空头所需的保证金比例
            "positions": { # 各股票的头寸信息
                ticker: {
                    "long": 0,  # 持有的多头股数
                    "short": 0,  # 持有的空头股数
                    "long_cost_basis": 0.0,  # 多头头寸的平均成本基础 (每股)
                    "short_cost_basis": 0.0,  # 空头头寸的平均成本基础 (每股)
                    "short_margin_used": 0.0  # 该股票空头头寸使用的保证金金额
                } for ticker in tickers
            },
            "realized_gains": { # 各股票的已实现收益/亏损
                ticker: {
                    "long": 0.0,  # 来自多头头寸的已实现收益
                    "short": 0.0,  # 来自空头头寸的已实现收益
                }
                for ticker in tickers
            },
        }

    def execute_trade(self, ticker: str, action: str, quantity: float, current_price: float):
        """
        执行交易，支持多头和空头头寸。
        `quantity` 是代理希望买入/卖出/做空/回补的股数。
        为简单起见，我们只交易整数股。
        返回实际执行的股数。
        """
        if quantity <= 0: # 如果期望数量无效，则不执行交易
            return 0

        quantity = int(quantity)  # 强制为整数股
        position = self.portfolio["positions"][ticker] # 获取该股票的当前头寸信息

        if action == "buy": # 买入操作
            cost = quantity * current_price # 计算所需成本
            if cost <= self.portfolio["cash"]: # 如果现金充足
                # 计算新的加权平均成本基础
                old_shares = position["long"]
                old_cost_basis = position["long_cost_basis"]
                new_shares = quantity
                total_shares = old_shares + new_shares

                if total_shares > 0:
                    total_old_cost = old_cost_basis * old_shares
                    total_new_cost = cost
                    position["long_cost_basis"] = (total_old_cost + total_new_cost) / total_shares

                position["long"] += quantity # 增加多头持股
                self.portfolio["cash"] -= cost # 减少现金
                return quantity # 返回实际买入数量
            else: # 如果现金不足，则尝试买入最大可负担数量
                max_quantity = int(self.portfolio["cash"] / current_price)
                if max_quantity > 0:
                    cost = max_quantity * current_price
                    old_shares = position["long"]
                    old_cost_basis = position["long_cost_basis"]
                    total_shares = old_shares + max_quantity

                    if total_shares > 0:
                        total_old_cost = old_cost_basis * old_shares
                        total_new_cost = cost
                        position["long_cost_basis"] = (total_old_cost + total_new_cost) / total_shares

                    position["long"] += max_quantity
                    self.portfolio["cash"] -= cost
                    return max_quantity # 返回实际买入数量
                return 0 # 无法买入

        elif action == "sell": # 卖出操作
            # 只能卖出持有的股数
            quantity = min(quantity, position["long"])
            if quantity > 0:
                # 使用平均成本基础计算已实现收益/亏损
                avg_cost_per_share = position["long_cost_basis"] if position["long"] > 0 else 0
                realized_gain = (current_price - avg_cost_per_share) * quantity
                self.portfolio["realized_gains"][ticker]["long"] += realized_gain # 累加到已实现收益

                position["long"] -= quantity # 减少多头持股
                self.portfolio["cash"] += quantity * current_price # 增加现金

                if position["long"] == 0: # 如果清仓
                    position["long_cost_basis"] = 0.0 # 重置成本基础

                return quantity # 返回实际卖出数量

        elif action == "short": # 做空操作
            """
            典型的卖空流程:
              1) 收到款项 = 当前价格 * 数量
              2) 缴纳保证金 = 款项 * 保证金比例
              3) 对现金的净影响 = +款项 - 保证金
            """
            proceeds = current_price * quantity # 做空获得的款项
            margin_required = proceeds * self.portfolio["margin_requirement"] # 需要的保证金
            if margin_required <= self.portfolio["cash"]: # 如果现金足够支付保证金
                # 计算新的加权平均空头成本基础
                old_short_shares = position["short"]
                old_cost_basis = position["short_cost_basis"]
                new_shares = quantity
                total_shares = old_short_shares + new_shares

                if total_shares > 0:
                    total_old_cost = old_cost_basis * old_short_shares
                    total_new_cost = current_price * new_shares # 做空成本是当前价格
                    position["short_cost_basis"] = (total_old_cost + total_new_cost) / total_shares

                position["short"] += quantity # 增加空头持股

                # 更新保证金使用情况
                position["short_margin_used"] += margin_required
                self.portfolio["margin_used"] += margin_required

                # 现金增加卖空所得，然后减去所需保证金
                self.portfolio["cash"] += proceeds
                self.portfolio["cash"] -= margin_required
                return quantity # 返回实际做空数量
            else: # 如果现金不足以支付保证金，尝试做空最大可负担数量
                margin_ratio = self.portfolio["margin_requirement"]
                if margin_ratio > 0:
                    max_quantity = int(self.portfolio["cash"] / (current_price * margin_ratio))
                else: # 如果保证金要求为0（理论上不应发生，但作为保护）
                    max_quantity = 0 # 无法做空

                if max_quantity > 0:
                    proceeds = current_price * max_quantity
                    margin_required = proceeds * margin_ratio

                    old_short_shares = position["short"]
                    old_cost_basis = position["short_cost_basis"]
                    total_shares = old_short_shares + max_quantity

                    if total_shares > 0:
                        total_old_cost = old_cost_basis * old_short_shares
                        total_new_cost = current_price * max_quantity
                        position["short_cost_basis"] = (total_old_cost + total_new_cost) / total_shares

                    position["short"] += max_quantity
                    position["short_margin_used"] += margin_required
                    self.portfolio["margin_used"] += margin_required

                    self.portfolio["cash"] += proceeds
                    self.portfolio["cash"] -= margin_required
                    return max_quantity # 返回实际做空数量
                return 0 # 无法做空

        elif action == "cover": # 回补操作 (买入以平掉空头仓位)
            """
            回补股票时:
              1) 支付回补成本 = 当前价格 * 数量
              2) 释放相应比例的保证金
              3) 对现金的净影响 = -回补成本 + 释放的保证金
            """
            quantity = min(quantity, position["short"]) # 只能回补持有的空头股数
            if quantity > 0:
                cover_cost = quantity * current_price # 回补所需成本
                avg_short_price = position["short_cost_basis"] if position["short"] > 0 else 0 # 做空时的平均价格
                realized_gain = (avg_short_price - current_price) * quantity # 计算已实现收益/亏损 (做空是价格下跌盈利)
                self.portfolio["realized_gains"][ticker]["short"] += realized_gain # 累加到已实现收益

                # 计算要释放的保证金
                if position["short"] > 0: # 防止除以零
                    portion_covered = quantity / position["short"] # 回补的比例
                else:
                    portion_covered = 1.0 # 如果空头已为0（理论上不应到这里），则释放全部（安全起见）

                margin_to_release = portion_covered * position["short_margin_used"]

                position["short"] -= quantity # 减少空头持股
                position["short_margin_used"] -= margin_to_release # 减少该股票占用的保证金
                self.portfolio["margin_used"] -= margin_to_release # 减少总占用保证金

                # 现金增加释放的保证金，然后减去回补成本
                self.portfolio["cash"] += margin_to_release
                self.portfolio["cash"] -= cover_cost

                if position["short"] == 0: # 如果空头仓位已平
                    position["short_cost_basis"] = 0.0 # 重置空头成本基础
                    position["short_margin_used"] = 0.0 # 重置该股票占用的保证金

                return quantity # 返回实际回补数量

        return 0 # 如果操作未被识别或数量无效

    def calculate_portfolio_value(self, current_prices: dict[str, float]) -> float:
        """
        计算总投资组合价值，包括：
          - 现金
          - 多头头寸的市值
          - 空头头寸的未实现收益/亏损（从总价值中减去空头市值，因为它们代表负债）
        """
        total_value = self.portfolio["cash"] # 从现金开始

        for ticker in self.tickers:
            position = self.portfolio["positions"][ticker]
            price = current_prices[ticker] # 获取当前价格

            # 多头头寸价值
            long_value = position["long"] * price
            total_value += long_value

            # 空头头寸代表负债，其当前市值应从总资产中扣除。
            # (或者可以理解为：未实现盈亏 = 空头股数 * (做空成本 - 当前价格) )
            # 这里采用更直接的方式：总资产 = 现金 + 多头市值 - 空头市值
            if position["short"] > 0:
                total_value -= position["short"] * price # 减去空头头寸的当前市值

        return total_value

    def prefetch_data(self):
        """预取回测期间所需的所有数据。"""
        print("\n正在为整个回测期间预取数据...")

        # 将结束日期字符串转换为datetime对象，获取最多提前一年的数据
        end_date_dt = datetime.strptime(self.end_date, "%Y-%m-%d")
        start_date_dt = end_date_dt - relativedelta(years=1) #  获取一年前的日期
        start_date_str = start_date_dt.strftime("%Y-%m-%d")

        for ticker in self.tickers:
            # 获取整个期间的价格数据，外加一年
            get_prices(ticker, start_date_str, self.end_date)

            # 获取财务指标
            get_financial_metrics(ticker, self.end_date, limit=10) # 获取最近10条

            # 获取内部交易数据
            get_insider_trades(ticker, self.end_date, start_date=self.start_date, limit=1000)

            # 获取公司新闻
            get_company_news(ticker, self.end_date, start_date=self.start_date, limit=1000)

        print("数据预取完成。")

    def run_backtest(self):
        """运行回测过程。"""
        # 在开始时预取所有数据
        self.prefetch_data()

        # 生成回测期间的交易日期 (B代表工作日)
        dates = pd.date_range(self.start_date, self.end_date, freq="B")
        table_rows = [] # 用于存储每日回测结果表格的行
        # 初始化性能指标字典
        performance_metrics = {
            "sharpe_ratio": None, "sortino_ratio": None, "max_drawdown": None,
            "long_short_ratio": None, "gross_exposure": None, "net_exposure": None
        }

        print("\n开始回测...")

        # 初始化投资组合价值列表，包含初始资金
        if len(dates) > 0:
            # 假设回测的第一天（或开始日期前一天）的价值是初始资本
            self.portfolio_values = [{"Date": dates[0] - pd.Timedelta(days=1) if dates[0] > datetime.strptime(self.start_date, "%Y-%m-%d") else dates[0], "Portfolio Value": self.initial_capital}]
        else:
            self.portfolio_values = []

        # 遍历每个交易日
        for current_date in dates:
            # 定义数据回溯期开始日期 (例如向前看30天)
            lookback_start = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
            current_date_str = current_date.strftime("%Y-%m-%d")
            # 获取前一个交易日的价格，用于当日决策和交易执行
            # 注意：这里假设 get_price_data 使用的是闭区间，或者能正确处理单个日期查询
            previous_date_str = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")


            # 如果回溯开始日期与当前日期相同（通常是回测范围的第一个有效日期），则跳过
            # 因为我们需要至少一天的数据来进行价格获取和决策
            if pd.to_datetime(lookback_start) >= current_date:
                # 记录初始投资组合价值（如果尚未记录）
                if not any(pv['Date'] == current_date for pv in self.portfolio_values):
                     self.portfolio_values.append({"Date": current_date, "Portfolio Value": self.initial_capital})
                continue

            # 获取所有股票代码的当前价格 (使用前一天的收盘价作为当天的开盘价或决策价)
            try:
                current_prices = {}
                missing_data = False
                for ticker in self.tickers:
                    try:
                        # 尝试获取从 previous_date_str 到 current_date_str 的价格数据
                        # 我们通常关心的是 current_date_str 这一天的价格，但API可能需要一个范围
                        # 或者，如果API支持，直接获取 current_date_str 的价格
                        # 为了简化，这里假设 get_price_data(ticker, prev, curr) 返回 curr 日期的价格
                        price_data = get_price_data(ticker, previous_date_str, current_date_str)
                        if price_data.empty:
                            print(f"警告: {ticker} 在 {current_date_str} 没有价格数据")
                            missing_data = True
                            break
                        current_prices[ticker] = price_data.iloc[-1]["close"] # 取最后一行的收盘价
                    except Exception as e:
                        print(f"获取 {ticker} 在 {previous_date_str} 到 {current_date_str} 之间的价格时出错: {e}")
                        missing_data = True
                        break

                if missing_data:
                    print(f"由于缺少价格数据，跳过交易日 {current_date_str}")
                    # 记录当日投资组合价值（无交易发生，价值不变）
                    if self.portfolio_values and self.portfolio_values[-1]['Date'] != current_date :
                         self.portfolio_values.append({"Date": current_date, "Portfolio Value": self.portfolio_values[-1]["Portfolio Value"]})
                    elif not self.portfolio_values:
                         self.portfolio_values.append({"Date": current_date, "Portfolio Value": self.initial_capital})
                    continue
            except Exception as e:
                # 如果获取价格时发生通用API错误，记录并跳过这一天
                print(f"获取 {current_date_str} 的价格时出错: {e}")
                if self.portfolio_values and self.portfolio_values[-1]['Date'] != current_date :
                    self.portfolio_values.append({"Date": current_date, "Portfolio Value": self.portfolio_values[-1]["Portfolio Value"]})
                elif not self.portfolio_values:
                    self.portfolio_values.append({"Date": current_date, "Portfolio Value": self.initial_capital})
                continue

            # ---------------------------------------------------------------
            # 1) 执行代理的交易决策
            # ---------------------------------------------------------------
            output = self.agent( # 调用交易代理函数
                tickers=self.tickers,
                start_date=lookback_start, # 数据回溯开始日期
                end_date=current_date_str, # 当前决策日期
                portfolio=self.portfolio, # 当前投资组合状态
                model_name=self.model_name,
                model_provider=self.model_provider,
                selected_analysts=self.selected_analysts,
            )
            decisions = output["decisions"] # 获取交易决策
            analyst_signals = output["analyst_signals"] # 获取分析师信号

            # 为每个股票代码执行交易
            executed_trades = {} # 记录实际执行的交易
            for ticker in self.tickers:
                decision = decisions.get(ticker, {"action": "hold", "quantity": 0}) # 获取该股票的决策，默认为持有
                action, quantity = decision.get("action", "hold"), decision.get("quantity", 0)

                # 使用当天的价格执行交易
                executed_quantity = self.execute_trade(ticker, action, quantity, current_prices[ticker])
                executed_trades[ticker] = executed_quantity

            # ---------------------------------------------------------------
            # 2) 交易执行后，重新计算当日最终的投资组合价值
            # ---------------------------------------------------------------
            total_value = self.calculate_portfolio_value(current_prices)

            # 同时计算交易后的多空敞口
            long_exposure = sum(self.portfolio["positions"][t]["long"] * current_prices[t] for t in self.tickers)
            short_exposure = sum(self.portfolio["positions"][t]["short"] * current_prices[t] for t in self.tickers)

            # 计算总敞口和净敞口
            gross_exposure = long_exposure + short_exposure # 总敞口 = 多头市值 + 空头市值 (绝对值)
            net_exposure = long_exposure - short_exposure   # 净敞口 = 多头市值 - 空头市值
            long_short_ratio = long_exposure / short_exposure if short_exposure > 1e-9 else float("inf") # 多空比

            # 跟踪每日的投资组合价值及敞口信息
            self.portfolio_values.append({
                "Date": current_date, "Portfolio Value": total_value,
                "Long Exposure": long_exposure, "Short Exposure": short_exposure,
                "Gross Exposure": gross_exposure, "Net Exposure": net_exposure,
                "Long/Short Ratio": long_short_ratio
            })

            # ---------------------------------------------------------------
            # 3) 构建用于显示的表格行
            # ---------------------------------------------------------------
            date_rows = [] # 当日所有股票的表格行

            # 为每个股票代码记录信号和交易
            for ticker in self.tickers:
                ticker_signals = {} # 该股票收到的所有分析师信号
                for agent_name, signals in analyst_signals.items():
                    if ticker in signals:
                        ticker_signals[agent_name] = signals[ticker]

                # 统计看涨、看跌、中性信号的数量
                bullish_count = len([s for s in ticker_signals.values() if s.get("signal", "").lower() == "bullish"])
                bearish_count = len([s for s in ticker_signals.values() if s.get("signal", "").lower() == "bearish"])
                neutral_count = len([s for s in ticker_signals.values() if s.get("signal", "").lower() == "neutral"])

                # 计算净头寸价值
                pos = self.portfolio["positions"][ticker]
                long_val = pos["long"] * current_prices[ticker]
                short_val = pos["short"] * current_prices[ticker]
                net_position_value = long_val - short_val # 净头寸价值

                # 从决策中获取操作和（实际执行的）数量
                action = decisions.get(ticker, {}).get("action", "hold")
                quantity = executed_trades.get(ticker, 0)

                # 将代理操作追加到表格行
                date_rows.append(
                    format_backtest_row(
                        date=current_date_str,
                        ticker=ticker,
                        action=action,
                        quantity=quantity,
                        price=current_prices[ticker],
                        shares_owned=pos["long"] - pos["short"],  # 净持股数
                        position_value=net_position_value,
                        bullish_count=bullish_count,
                        bearish_count=bearish_count,
                        neutral_count=neutral_count,
                    )
                )
            # ---------------------------------------------------------------
            # 4) 计算性能摘要指标
            # ---------------------------------------------------------------
            # 计算投资组合相对于初始资本的回报率
            # 已实现收益已反映在现金余额中，因此不单独添加
            portfolio_return = (total_value / self.initial_capital - 1) * 100

            # 为当日添加摘要行
            date_rows.append(
                format_backtest_row(
                    date=current_date_str,
                    ticker="", # 摘要行不针对特定股票
                    action="",
                    quantity=0,
                    price=0,
                    shares_owned=0,
                    position_value=0,
                    bullish_count=0,
                    bearish_count=0,
                    neutral_count=0,
                    is_summary=True, # 标记为摘要行
                    total_value=total_value, # 当日总价值
                    return_pct=portfolio_return, # 当日回报率
                    cash_balance=self.portfolio["cash"], # 现金余额
                    total_position_value=total_value - self.portfolio["cash"], # 总头寸价值
                    sharpe_ratio=performance_metrics["sharpe_ratio"], # 夏普比率 (可能是截至昨日的)
                    sortino_ratio=performance_metrics["sortino_ratio"], # 索提诺比率 (可能是截至昨日的)
                    max_drawdown=performance_metrics["max_drawdown"], # 最大回撤 (可能是截至昨日的)
                ),
            )

            table_rows.extend(date_rows) # 将当日所有行添加到总表
            print_backtest_results(table_rows) # 打印当前回测结果

            # 如果有足够的数据，则更新性能指标
            if len(self.portfolio_values) > 3: # 需要至少几天的数据来计算有意义的指标
                self._update_performance_metrics(performance_metrics)

        # 存储最终的性能指标，供 analyze_performance 参考
        self.performance_metrics = performance_metrics
        return performance_metrics

    def _update_performance_metrics(self, performance_metrics: dict):
        """使用每日回报率更新性能指标的辅助方法。"""
        values_df = pd.DataFrame(self.portfolio_values).set_index("Date") # 将投资组合价值列表转换为DataFrame
        values_df["Daily Return"] = values_df["Portfolio Value"].pct_change() # 计算每日回报率
        clean_returns = values_df["Daily Return"].dropna() # 去除NaN值 (通常是第一天)

        if len(clean_returns) < 2: # 数据点不足
            return

        # 假设每年252个交易日
        daily_risk_free_rate = 0.0434 / 252 # 每日无风险利率 (示例值，应根据实际情况调整)
        excess_returns = clean_returns - daily_risk_free_rate # 计算超额回报率
        mean_excess_return = excess_returns.mean() # 平均超额回报
        std_excess_return = excess_returns.std() # 超额回报的标准差

        # 夏普比率
        if std_excess_return > 1e-12: # 防止除以零
            performance_metrics["sharpe_ratio"] = np.sqrt(252) * (mean_excess_return / std_excess_return)
        else:
            performance_metrics["sharpe_ratio"] = 0.0

        # 索提诺比率
        negative_returns = excess_returns[excess_returns < 0] # 只考虑负的超额回报（下行风险）
        if len(negative_returns) > 0:
            downside_std = negative_returns.std() # 下行标准差
            if downside_std > 1e-12: # 防止除以零
                performance_metrics["sortino_ratio"] = np.sqrt(252) * (mean_excess_return / downside_std)
            else: # 如果下行标准差为0（即没有负回报）
                performance_metrics["sortino_ratio"] = float("inf") if mean_excess_return > 0 else 0
        else: # 如果没有负回报
            performance_metrics["sortino_ratio"] = float("inf") if mean_excess_return > 0 else 0

        # 最大回撤 (确保以负百分比形式存储)
        rolling_max = values_df["Portfolio Value"].cummax() # 计算滚动最大值
        drawdown = (values_df["Portfolio Value"] - rolling_max) / rolling_max # 计算回撤比例

        if len(drawdown) > 0:
            min_drawdown = drawdown.min() # 找到最大回撤（最小的回撤比例值）
            performance_metrics["max_drawdown"] = min_drawdown * 100 # 以百分比存储

            # 存储最大回撤的日期以供参考
            if min_drawdown < 0:
                performance_metrics["max_drawdown_date"] = drawdown.idxmin().strftime("%Y-%m-%d")
            else:
                performance_metrics["max_drawdown_date"] = None
        else:
            performance_metrics["max_drawdown"] = 0.0
            performance_metrics["max_drawdown_date"] = None

    def analyze_performance(self):
        """创建性能DataFrame，打印摘要统计信息，并绘制资产净值曲线。"""
        if not self.portfolio_values: #如果没有投资组合数据
            print("未找到投资组合数据。请先运行回测。")
            return pd.DataFrame()

        performance_df = pd.DataFrame(self.portfolio_values).set_index("Date") # 转换为DataFrame
        if performance_df.empty:
            print("没有有效的性能数据可供分析。")
            return performance_df

        final_portfolio_value = performance_df["Portfolio Value"].iloc[-1] # 最终投资组合价值
        total_return = ((final_portfolio_value - self.initial_capital) / self.initial_capital) * 100 # 总回报率

        print(f"\n{Fore.WHITE}{Style.BRIGHT}投资组合性能摘要:{Style.RESET_ALL}")
        print(f"总回报率: {Fore.GREEN if total_return >= 0 else Fore.RED}{total_return:.2f}%{Style.RESET_ALL}")

        # 打印已实现盈亏，仅供参考
        total_realized_gains = sum(
            self.portfolio["realized_gains"][ticker]["long"] + self.portfolio["realized_gains"][ticker]["short"]
            for ticker in self.tickers
        )
        print(f"总已实现收益/亏损: {Fore.GREEN if total_realized_gains >= 0 else Fore.RED}${total_realized_gains:,.2f}{Style.RESET_ALL}")

        # 绘制投资组合价值随时间变化的曲线
        plt.figure(figsize=(12, 6))
        plt.plot(performance_df.index, performance_df["Portfolio Value"], color="blue")
        plt.title("投资组合价值随时间变化")
        plt.ylabel("投资组合价值 ($)")
        plt.xlabel("日期")
        plt.grid(True)
        plt.show() # 显示图表

        # 计算每日回报率
        performance_df["Daily Return"] = performance_df["Portfolio Value"].pct_change().fillna(0)
        daily_rf = 0.0434 / 252  # 每日无风险利率 (示例)
        mean_daily_return = performance_df["Daily Return"].mean() # 平均每日回报率
        std_daily_return = performance_df["Daily Return"].std() # 每日回报率标准差

        # 年化夏普比率
        if std_daily_return != 0:
            annualized_sharpe = np.sqrt(252) * ((mean_daily_return - daily_rf) / std_daily_return)
        else:
            annualized_sharpe = 0
        print(f"\n夏普比率: {Fore.YELLOW}{annualized_sharpe:.2f}{Style.RESET_ALL}")

        # 使用回测期间计算的最大回撤值（如果可用）
        max_drawdown = getattr(self, "performance_metrics", {}).get("max_drawdown")
        max_drawdown_date = getattr(self, "performance_metrics", {}).get("max_drawdown_date")

        # 如果尚无值，则计算它
        if max_drawdown is None:
            rolling_max = performance_df["Portfolio Value"].cummax()
            drawdown = (performance_df["Portfolio Value"] - rolling_max) / rolling_max
            max_drawdown = drawdown.min() * 100 # 转换为百分比
            max_drawdown_date = drawdown.idxmin().strftime("%Y-%m-%d") if pd.notnull(drawdown.idxmin()) else None

        if max_drawdown_date:
            print(f"最大回撤: {Fore.RED}{abs(max_drawdown):.2f}%{Style.RESET_ALL} (发生于 {max_drawdown_date})")
        else:
            print(f"最大回撤: {Fore.RED}{abs(max_drawdown):.2f}%{Style.RESET_ALL}")

        # 胜率 (盈利天数比例)
        winning_days = len(performance_df[performance_df["Daily Return"] > 0]) # 盈利天数
        total_days = max(len(performance_df) - 1, 1) # 总交易天数 (减去第一天，至少为1)
        win_rate = (winning_days / total_days) * 100
        print(f"胜率: {Fore.GREEN}{win_rate:.2f}%{Style.RESET_ALL}")

        # 平均盈亏比
        positive_returns = performance_df[performance_df["Daily Return"] > 0]["Daily Return"] # 所有正回报
        negative_returns = performance_df[performance_df["Daily Return"] < 0]["Daily Return"] # 所有负回报
        avg_win = positive_returns.mean() if not positive_returns.empty else 0 # 平均盈利
        avg_loss = abs(negative_returns.mean()) if not negative_returns.empty else 0 # 平均亏损 (取绝对值)
        if avg_loss != 0:
            win_loss_ratio = avg_win / avg_loss
        else: # 如果没有亏损日
            win_loss_ratio = float("inf") if avg_win > 0 else 0
        print(f"盈亏比: {Fore.GREEN}{win_loss_ratio:.2f}{Style.RESET_ALL}")

        # 最大连续盈利/亏损天数
        returns_binary = (performance_df["Daily Return"] > 0).astype(int) # 将回报转换为1 (盈利) 或 0 (亏损/持平)
        if len(returns_binary) > 0:
            max_consecutive_wins = max((len(list(g)) for k, g in itertools.groupby(returns_binary) if k == 1), default=0)
            max_consecutive_losses = max((len(list(g)) for k, g in itertools.groupby(returns_binary) if k == 0), default=0) # 注意：这里k==0包括了持平的日子
        else:
            max_consecutive_wins = 0
            max_consecutive_losses = 0

        print(f"最大连续盈利天数: {Fore.GREEN}{max_consecutive_wins}{Style.RESET_ALL}")
        print(f"最大连续亏损/持平天数: {Fore.RED}{max_consecutive_losses}{Style.RESET_ALL}")

        return performance_df


### 4. 运行回测 (Run the Backtest) #####
if __name__ == "__main__":
    import argparse # 用于解析命令行参数

    parser = argparse.ArgumentParser(description="运行回测模拟")
    parser.add_argument(
        "--tickers",
        type=str,
        required=False, # 设置为 False，因为后面会有交互式选择
        help="以逗号分隔的股票代码列表 (例如, AAPL,MSFT,GOOGL)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"), # 默认为当前日期
        help="结束日期，格式 YYYY-MM-DD",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=(datetime.now() - relativedelta(months=1)).strftime("%Y-%m-%d"), # 默认为一个月前
        help="开始日期，格式 YYYY-MM-DD",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=100000, # 默认初始资金
        help="初始资金数额 (默认: 100000)",
    )
    parser.add_argument(
        "--margin-requirement",
        type=float,
        default=0.0, # 默认无保证金要求 (即不允许做空或需要100%现金覆盖)
        help="空头头寸的保证金比例，例如0.5代表50% (默认: 0.0)",
    )
    parser.add_argument(
        "--analysts",
        type=str,
        required=False,
        help="以逗号分隔的要使用的分析师列表 (例如, michael_burry,other_analyst)",
    )
    parser.add_argument(
        "--analysts-all",
        action="store_true", # 如果出现此参数，则其值为True
        help="使用所有可用的分析师 (覆盖 --analysts)",
    )
    parser.add_argument("--ollama", action="store_true", help="使用 Ollama进行本地LLM推理")

    args = parser.parse_args() # 解析传入的参数

    # 从逗号分隔的字符串解析股票代码
    tickers = [ticker.strip().upper() for ticker in args.tickers.split(",")] if args.tickers else []
    if not tickers: # 如果命令行没有提供 tickers
        tickers_input = questionary.text(
            "请输入要回测的股票代码 (以逗号分隔, 例如 AAPL,MSFT):",
            validate=lambda text: True if text.strip() else "至少需要一个股票代码"
        ).ask()
        if not tickers_input:
            print("未提供股票代码，退出。")
            sys.exit(0)
        tickers = [ticker.strip().upper() for ticker in tickers_input.split(",")]


    # 从命令行标志解析分析师
    selected_analysts = None
    if args.analysts_all: # 如果指定了 --analysts-all
        selected_analysts = [a[1] for a in ANALYST_ORDER] #选择所有分析师
    elif args.analysts: # 如果通过 --analysts 指定了分析师
        selected_analysts = [a.strip() for a in args.analysts.split(",") if a.strip()]
    else: # 否则，进行交互式选择
        choices = questionary.checkbox(
            "请使用空格键选择/取消选择分析师。",
            choices=[questionary.Choice(display, value=value) for display, value in ANALYST_ORDER],
            instruction="\n\n按 'a' 键全选/全不选。\n完成后按 Enter 键运行对冲基金。",
            validate=lambda x: len(x) > 0 or "您必须至少选择一位分析师。",
            style=questionary.Style( # 定义样式
                [
                    ("checkbox-selected", "fg:green"),
                    ("selected", "fg:green noinherit"),
                    ("highlighted", "noinherit"),
                    ("pointer", "noinherit"),
                ]
            ),
        ).ask()
        if not choices: # 如果用户中断选择
            print("\n\n收到中断信号。正在退出...")
            sys.exit(0)
        else:
            selected_analysts = choices
            print(f"\n已选分析师: " f"{', '.join(Fore.GREEN + choice.title().replace('_', ' ') + Style.RESET_ALL for choice in choices)}")

    # 根据是否使用Ollama选择LLM模型
    model_name = ""
    model_provider = None

    if args.ollama: # 如果使用 Ollama
        print(f"{Fore.CYAN}正在使用 Ollama 进行本地 LLM 推理。{Style.RESET_ALL}")

        # 从Ollama特定模型中选择
        model_name = questionary.select(
            "请选择您的 Ollama 模型:",
            choices=[questionary.Choice(display, value=value) for display, value, _ in OLLAMA_LLM_ORDER], # OLLAMA_LLM_ORDER 包含 (显示名称, 模型值, 描述)
            style=questionary.Style(
                [
                    ("selected", "fg:green bold"),
                    ("pointer", "fg:green bold"),
                    ("highlighted", "fg:green"),
                    ("answer", "fg:green bold"),
                ]
            ),
        ).ask()

        if not model_name: # 用户中断
            print("\n\n收到中断信号。正在退出...")
            sys.exit(0)

        if model_name == "-": # 如果选择自定义模型
            model_name = questionary.text("请输入自定义模型名称:").ask()
            if not model_name:
                print("\n\n收到中断信号。正在退出...")
                sys.exit(0)

        # 确保Ollama已安装、正在运行且模型可用
        if not ensure_ollama_and_model(model_name):
            print(f"{Fore.RED}无法在没有 Ollama 和所选模型的情况下继续。{Style.RESET_ALL}")
            sys.exit(1)

        model_provider = ModelProvider.OLLAMA.value # 设置模型提供商为 Ollama
        print(f"\n已选 {Fore.CYAN}Ollama{Style.RESET_ALL} 模型: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}\n")
    else: # 使用标准的基于云的LLM选择
        model_choice = questionary.select(
            "请选择您的 LLM 模型:",
            choices=[questionary.Choice(display, value=(name, provider)) for display, name, provider in LLM_ORDER], # LLM_ORDER 包含 (显示名称, 模型名称, 提供商)
            style=questionary.Style(
                [
                    ("selected", "fg:green bold"),
                    ("pointer", "fg:green bold"),
                    ("highlighted", "fg:green"),
                    ("answer", "fg:green bold"),
                ]
            ),
        ).ask()

        if not model_choice: # 用户中断
            print("\n\n收到中断信号。正在退出...")
            sys.exit(0)
        
        model_name, model_provider_str = model_choice # 解包选择结果
        model_provider = ModelProvider(model_provider_str) # 将字符串转换为枚举成员


        model_info = get_model_info(model_name, model_provider.value) # 获取模型信息
        if model_info:
            if model_info.is_custom(): # 如果是自定义模型
                model_name = questionary.text("请输入自定义模型名称:").ask()
                if not model_name:
                    print("\n\n收到中断信号。正在退出...")
                    sys.exit(0)

            print(f"\n已选 {Fore.CYAN}{model_provider.value}{Style.RESET_ALL} 模型: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}\n")
        else: # 如果模型信息未找到 (理论上不应发生，因为是从列表中选择的)
            # model_provider = "Unknown" # 这行会导致类型错误，因为 model_provider 期望 ModelProvider 枚举
            print(f"\n已选模型: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL} (提供商: {model_provider.value})\n")


    # 创建并运行回测器
    backtester = Backtester(
        agent=run_hedge_fund, # 使用 run_hedge_fund 作为交易代理
        tickers=tickers,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        model_name=model_name,
        model_provider=model_provider.value, # 传递枚举的值 (字符串)
        selected_analysts=selected_analysts,
        initial_margin_requirement=args.margin_requirement,
    )

    performance_metrics = backtester.run_backtest() # 运行回测
    performance_df = backtester.analyze_performance() # 分析性能
