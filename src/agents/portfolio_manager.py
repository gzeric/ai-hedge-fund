import json
from langchain_core.messages import HumanMessage # LangChain 核心消息类型
from langchain_core.prompts import ChatPromptTemplate # LangChain 聊天提示模板

from src.graph.state import AgentState, show_agent_reasoning # 代理状态和显示推理的辅助函数
from pydantic import BaseModel, Field # Pydantic 用于数据验证和模型定义
from typing_extensions import Literal # 用于定义字面量类型
from src.utils.progress import progress # 进度更新工具
from src.utils.llm import call_llm # 调用大语言模型的辅助函数


# 定义单个投资组合决策的数据模型
class PortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "short", "cover", "hold"] # 交易动作：买入、卖出、做空、回补、持有
    quantity: int = Field(description="要交易的股票数量")
    confidence: float = Field(description="决策的置信度，介于 0.0 和 100.0 之间")
    reasoning: str = Field(description="做出此决策的理由")


# 定义投资组合管理器输出的数据模型，包含多个股票的决策
class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision] = Field(description="股票代码到交易决策的字典")


##### 投资组合管理代理 (Portfolio Management Agent) #####
def portfolio_management_agent(state: AgentState):
    """针对多个股票代码做出最终交易决策并生成订单。"""

    # 从状态中获取投资组合、分析师信号和股票代码列表
    portfolio = state["data"]["portfolio"]
    analyst_signals = state["data"]["analyst_signals"]
    tickers = state["data"]["tickers"]

    # 初始化用于存储每个股票代码数据的字典
    position_limits = {} # 头寸限制
    current_prices = {}  # 当前价格
    max_shares = {}      # 基于头寸限制和价格计算的最大可交易股数
    signals_by_ticker = {} # 按股票代码组织的信号

    # 遍历每个股票代码，收集所需信息
    for ticker in tickers:
        progress.update_status("portfolio_manager", ticker, "处理分析师信号") # 更新进度状态

        # 从风险管理代理的信号中获取该股票的头寸限制和当前价格
        risk_data = analyst_signals.get("risk_management_agent", {}).get(ticker, {})
        position_limits[ticker] = risk_data.get("remaining_position_limit", 0) # 剩余头寸限制
        current_prices[ticker] = risk_data.get("current_price", 0) # 当前市场价格

        # 根据头寸限制和当前价格计算最大允许购买/做空的股数
        if current_prices[ticker] > 0:
            max_shares[ticker] = int(position_limits[ticker] / current_prices[ticker])
        else:
            max_shares[ticker] = 0 # 如果价格为0或无效，则最大股数为0

        # 收集该股票来自其他分析师的信号
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            # 排除风险管理代理自身，并确保信号中包含当前股票代码
            if agent != "risk_management_agent" and ticker in signals:
                ticker_signals[agent] = {"signal": signals[ticker]["signal"], "confidence": signals[ticker]["confidence"]}
        signals_by_ticker[ticker] = ticker_signals

    progress.update_status("portfolio_manager", None, "生成交易决策") # 更新总体进度

    # 调用大语言模型生成交易决策
    result = generate_trading_decision(
        tickers=tickers,
        signals_by_ticker=signals_by_ticker,
        current_prices=current_prices,
        max_shares=max_shares,
        portfolio=portfolio,
        state=state,
    )

    # 将决策结果构造成 HumanMessage，以便在 LangGraph 中传递
    message = HumanMessage(
        content=json.dumps({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}), # 将决策对象序列化为 JSON 字符串
        name="portfolio_manager", # 消息发送者名称
    )

    # 如果设置了显示推理的标志，则打印决策过程
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}, "Portfolio Manager")

    progress.update_status("portfolio_manager", None, "完成") # 更新最终进度

    # 返回更新后的状态，包含新的消息和原始数据
    return {
        "messages": state["messages"] + [message], # 将新消息追加到消息列表
        "data": state["data"], # 数据部分保持不变
    }


def generate_trading_decision(
    tickers: list[str], # 股票代码列表
    signals_by_ticker: dict[str, dict], # 按股票代码组织的信号
    current_prices: dict[str, float], # 各股票的当前价格
    max_shares: dict[str, int], # 各股票的最大可交易股数
    portfolio: dict[str, float], # 当前投资组合信息
    state: AgentState, # 当前代理状态
) -> PortfolioManagerOutput:
    """尝试从大语言模型获取决策，并带有重试逻辑 (通过 call_llm 实现)。"""
    # 创建聊天提示模板
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system", # 系统消息，定义角色和规则
                """您是一位投资组合经理，需要根据多个股票代码的信息做出最终的交易决策。

              交易规则:
              - 多头头寸:
                * 只有在有可用现金时才能买入。
                * 只有在当前持有多头股票时才能卖出。
                * 卖出数量必须 ≤ 当前多头持股数量。
                * 买入数量必须 ≤ 该股票的 max_shares。
              
              - 空头头寸:
                * 只有在有可用保证金 (头寸价值 × 保证金要求) 时才能做空。
                * 只有在当前持有空头股票时才能回补。
                * 回补数量必须 ≤ 当前空头持股数量。
                * 做空数量必须遵守保证金要求。
              
              - max_shares 值是预先计算好的，以遵守头寸限制。
              - 根据信号同时考虑多头和空头机会。
              - 通过多头和空头敞口来维持适当的风险管理。

              可用操作:
              - "buy": 开仓或增加多头头寸
              - "sell": 平仓或减少多头头寸
              - "short": 开仓或增加空头头寸
              - "cover": 平仓或减少空头头寸
              - "hold": 无操作

              输入信息:
              - signals_by_ticker: 股票代码 → 信号的字典
              - max_shares: 每个股票代码允许的最大股数
              - portfolio_cash: 投资组合中的当前现金
              - portfolio_positions: 当前持仓 (包括多头和空头)
              - current_prices: 每个股票代码的当前价格
              - margin_requirement: 当前空头头寸的保证金要求 (例如，0.5 表示 50%)
              - total_margin_used: 当前已使用的总保证金
              """,
            ),
            (
                "human", # 用户消息，提供具体数据并要求输出
                """根据团队的分析，请为每个股票代码做出您的交易决策。

              以下是按股票代码分类的信号:
              {signals_by_ticker}

              当前价格:
              {current_prices}

              允许购买的最大股数:
              {max_shares}

              投资组合现金: {portfolio_cash}
              当前持仓: {portfolio_positions}
              当前保证金要求: {margin_requirement}
              已用总保证金: {total_margin_used}

              请严格按照以下 JSON 结构输出:
              {{
                "decisions": {{
                  "TICKER1": {{
                    "action": "buy/sell/short/cover/hold",
                    "quantity": 整数,
                    "confidence": 0到100之间的浮点数,
                    "reasoning": "字符串"
                  }},
                  "TICKER2": {{
                    ...
                  }},
                  ...
                }}
              }}
              """,
            ),
        ]
    )

    # 使用具体数据填充提示模板
    prompt = template.invoke(
        {
            "signals_by_ticker": json.dumps(signals_by_ticker, indent=2), # 将信号字典转换为格式化的 JSON 字符串
            "current_prices": json.dumps(current_prices, indent=2),
            "max_shares": json.dumps(max_shares, indent=2),
            "portfolio_cash": f"{portfolio.get('cash', 0):.2f}", # 格式化现金为两位小数的字符串
            "portfolio_positions": json.dumps(portfolio.get("positions", {}), indent=2),
            "margin_requirement": f"{portfolio.get('margin_requirement', 0):.2f}",
            "total_margin_used": f"{portfolio.get('margin_used', 0):.2f}",
        }
    )

    # 为 PortfolioManagerOutput 创建默认工厂函数，用于在 LLM 调用失败时返回默认值
    def create_default_portfolio_output():
        # 如果LLM处理出错，默认对所有股票都执行 "hold" 操作
        return PortfolioManagerOutput(
            decisions={
                ticker: PortfolioDecision(
                    action="hold",
                    quantity=0,
                    confidence=0.0,
                    reasoning="投资组合管理出错，默认为持有"
                ) for ticker in tickers
            }
        )

    # 调用大语言模型处理填充好的提示，并期望得到 PortfolioManagerOutput 类型的结构化输出
    return call_llm(
        prompt=prompt, # 完整的提示内容
        pydantic_model=PortfolioManagerOutput, # 期望的 Pydantic 输出模型
        agent_name="portfolio_manager", # 当前代理名称，用于日志和跟踪
        state=state, # 当前代理状态，可能包含模型配置等信息
        default_factory=create_default_portfolio_output, # LLM 调用失败时的默认返回值工厂
    )
