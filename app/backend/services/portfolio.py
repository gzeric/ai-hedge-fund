

def create_portfolio(initial_cash: float, margin_requirement: float, tickers: list[str]) -> dict:
  """
  创建一个新的投资组合字典。

  参数:
    initial_cash (float): 初始现金金额。
    margin_requirement (float): 初始保证金要求 (例如 0.5 表示 50%)。
    tickers (list[str]): 投资组合中将要跟踪的股票代码列表。

  返回:
    dict: 表示投资组合的字典，包含现金、保证金信息、持仓和已实现收益。
  """
  return {
        "cash": initial_cash,  # 初始现金金额
        "margin_requirement": margin_requirement,  # 初始保证金要求 (例如，做空100美元股票，保证金要求0.5，则需要50美元保证金)
        "margin_used": 0.0,  # 所有空头头寸占用的总保证金
        "positions": { # 持仓详情
            ticker: { # 每只股票的持仓信息
                "long": 0,  # 持有的多头股数
                "short": 0,  # 持有的空头股数 (做空的股数)
                "long_cost_basis": 0.0,  # 多头头寸的平均成本基础 (买入均价)
                "short_cost_basis": 0.0,  # 空头头寸的平均成本基础 (卖空均价)
                "short_margin_used": 0.0,  # 该股票空头头寸占用的保证金金额
            }
            for ticker in tickers # 为列表中的每只股票初始化持仓信息
        },
        "realized_gains": { # 已实现收益/亏损
            ticker: { # 每只股票的已实现收益信息
                "long": 0.0,  # 来自多头头寸的已实现收益/亏损
                "short": 0.0,  # 来自空头头寸的已实现收益/亏损
            }
            for ticker in tickers # 为列表中的每只股票初始化已实现收益信息
        },
    }