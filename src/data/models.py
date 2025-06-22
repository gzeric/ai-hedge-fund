from pydantic import BaseModel # 导入 Pydantic 的 BaseModel，用于数据验证和模型定义

# 定义价格数据模型
class Price(BaseModel):
    open: float  # 开盘价
    close: float  # 收盘价
    high: float  # 最高价
    low: float  # 最低价
    volume: int  # 成交量
    time: str  # 时间戳 (通常为日期或日期时间字符串)

# 定义价格API响应的数据模型
class PriceResponse(BaseModel):
    ticker: str  # 股票代码
    prices: list[Price]  # 价格数据列表

# 定义财务指标数据模型
class FinancialMetrics(BaseModel):
    ticker: str  # 股票代码
    report_period: str  # 报告期 (例如 "2023-12-31")
    period: str  # 期间类型 (例如 "annual", "quarterly")
    currency: str  # 货币单位 (例如 "USD")
    market_cap: float | None  # 市值 (可选)
    enterprise_value: float | None  # 企业价值 (可选)
    price_to_earnings_ratio: float | None  # 市盈率 (可选)
    price_to_book_ratio: float | None  # 市净率 (可选)
    price_to_sales_ratio: float | None  # 市销率 (可选)
    enterprise_value_to_ebitda_ratio: float | None  # 企业价值/EBITDA比率 (可选)
    enterprise_value_to_revenue_ratio: float | None  # 企业价值/收入比率 (可选)
    free_cash_flow_yield: float | None  # 自由现金流收益率 (可选)
    peg_ratio: float | None  # 市盈率相对盈利增长比率 (可选)
    gross_margin: float | None  # 毛利率 (可选)
    operating_margin: float | None  # 营业利润率 (可选)
    net_margin: float | None  # 净利率 (可选)
    return_on_equity: float | None  # 净资产收益率 (ROE) (可选)
    return_on_assets: float | None  # 总资产收益率 (ROA) (可选)
    return_on_invested_capital: float | None  # 投入资本回报率 (ROIC) (可选)
    asset_turnover: float | None  # 资产周转率 (可选)
    inventory_turnover: float | None  # 库存周转率 (可选)
    receivables_turnover: float | None  # 应收账款周转率 (可选)
    days_sales_outstanding: float | None  # 应收账款周转天数 (可选)
    operating_cycle: float | None  # 营业周期 (可选)
    working_capital_turnover: float | None  # 营运资本周转率 (可选)
    current_ratio: float | None  # 流动比率 (可选)
    quick_ratio: float | None  # 速动比率 (可选)
    cash_ratio: float | None  # 现金比率 (可选)
    operating_cash_flow_ratio: float | None  # 经营现金流量比率 (可选)
    debt_to_equity: float | None  # 负债权益比 (可选)
    debt_to_assets: float | None  # 资产负债率 (可选)
    interest_coverage: float | None  # 利息保障倍数 (可选)
    revenue_growth: float | None  # 收入增长率 (可选)
    earnings_growth: float | None  # 收益增长率 (可选)
    book_value_growth: float | None  # 账面价值增长率 (可选)
    earnings_per_share_growth: float | None  # 每股收益增长率 (可选)
    free_cash_flow_growth: float | None  # 自由现金流增长率 (可选)
    operating_income_growth: float | None  # 营业收入增长率 (可选)
    ebitda_growth: float | None  # EBITDA增长率 (可选)
    payout_ratio: float | None  # 股息支付率 (可选)
    earnings_per_share: float | None  # 每股收益 (EPS) (可选)
    book_value_per_share: float | None  # 每股账面价值 (可选)
    free_cash_flow_per_share: float | None  # 每股自由现金流 (可选)

# 定义财务指标API响应的数据模型
class FinancialMetricsResponse(BaseModel):
    financial_metrics: list[FinancialMetrics]  # 财务指标列表

# 定义财务报表细项数据模型
class LineItem(BaseModel):
    ticker: str  # 股票代码
    report_period: str  # 报告期
    period: str  # 期间类型
    currency: str  # 货币

    # 允许动态添加额外字段 (例如，不同的财务报表科目)
    model_config = {"extra": "allow"}

# 定义财务报表细项API响应的数据模型
class LineItemResponse(BaseModel):
    search_results: list[LineItem]  # 搜索结果列表，每个结果是一个细项

# 定义内部交易数据模型
class InsiderTrade(BaseModel):
    ticker: str  # 股票代码
    issuer: str | None  # 发行公司名称 (可选)
    name: str | None  # 交易人姓名 (可选)
    title: str | None  # 交易人头衔 (可选)
    is_board_director: bool | None  # 是否为董事会成员 (可选)
    transaction_date: str | None  # 交易日期 (可选)
    transaction_shares: float | None  # 交易股数 (可选)
    transaction_price_per_share: float | None  # 每股交易价格 (可选)
    transaction_value: float | None  # 交易总价值 (可选)
    shares_owned_before_transaction: float | None  # 交易前持股数 (可选)
    shares_owned_after_transaction: float | None  # 交易后持股数 (可选)
    security_title: str | None  # 证券名称 (可选)
    filing_date: str  # 申报日期

# 定义内部交易API响应的数据模型
class InsiderTradeResponse(BaseModel):
    insider_trades: list[InsiderTrade]  # 内部交易列表

# 定义公司新闻数据模型
class CompanyNews(BaseModel):
    ticker: str  # 股票代码
    title: str  # 新闻标题
    author: str  # 作者
    source: str  # 新闻来源
    date: str  # 发布日期
    url: str  # 新闻链接
    sentiment: str | None = None  # 新闻情感分析结果 (可选，例如 "positive", "negative", "neutral")

# 定义公司新闻API响应的数据模型
class CompanyNewsResponse(BaseModel):
    news: list[CompanyNews]  # 新闻列表

# 定义公司基本信息数据模型
class CompanyFacts(BaseModel):
    ticker: str  # 股票代码
    name: str  # 公司名称
    cik: str | None = None  # CIK码 (SEC中央索引码) (可选)
    industry: str | None = None  # 行业 (可选)
    sector: str | None = None  # 板块 (可选)
    category: str | None = None  # 类别 (可选)
    exchange: str | None = None  # 交易所 (可选)
    is_active: bool | None = None  # 是否活跃 (可选)
    listing_date: str | None = None  # 上市日期 (可选)
    location: str | None = None  # 公司所在地 (可选)
    market_cap: float | None = None  # 市值 (可选)
    number_of_employees: int | None = None  # 员工数量 (可选)
    sec_filings_url: str | None = None  # SEC文件链接 (可选)
    sic_code: str | None = None  # SIC码 (标准行业分类码) (可选)
    sic_industry: str | None = None  # SIC行业 (可选)
    sic_sector: str | None = None  # SIC板块 (可选)
    website_url: str | None = None  # 公司网站链接 (可选)
    weighted_average_shares: int | None = None  # 加权平均股数 (可选)

# 定义公司基本信息API响应的数据模型
class CompanyFactsResponse(BaseModel):
    company_facts: CompanyFacts  # 公司基本信息

# 定义单个头寸的数据模型 (用于投资组合)
class Position(BaseModel):
    cash: float = 0.0  # 与此头寸相关的现金 (通常不用，现金在Portfolio层面管理)
    shares: int = 0  # 持有股数 (对于多头是正数，空头可以是负数或单独字段表示)
    ticker: str  # 股票代码

# 定义投资组合数据模型
class Portfolio(BaseModel):
    positions: dict[str, Position]  # 股票代码 -> 头寸对象的映射
    total_cash: float = 0.0  # 投资组合总现金

# 定义分析师信号数据模型
class AnalystSignal(BaseModel):
    signal: str | None = None  # 信号类型 (例如 "buy", "sell", "hold", "bullish", "bearish") (可选)
    confidence: float | None = None  # 置信度 (可选)
    reasoning: dict | str | None = None  # 做出此信号的理由 (可以是字典或字符串) (可选)
    max_position_size: float | None = None  # 最大头寸规模 (用于风险管理信号) (可选)

# 定义单个股票的分析结果数据模型
class TickerAnalysis(BaseModel):
    ticker: str  # 股票代码
    analyst_signals: dict[str, AnalystSignal]  # 代理名称 -> 分析师信号的映射

# 定义代理状态中的数据部分模型 (用于LangGraph)
class AgentStateData(BaseModel):
    tickers: list[str]  # 股票代码列表
    portfolio: Portfolio  # 投资组合状态
    start_date: str  # 分析开始日期
    end_date: str  # 分析结束日期
    ticker_analyses: dict[str, TickerAnalysis]  # 股票代码 -> 分析结果的映射

# 定义代理状态中的元数据部分模型 (用于LangGraph)
class AgentStateMetadata(BaseModel):
    show_reasoning: bool = False  # 是否显示推理过程，默认为False
    model_config = {"extra": "allow"}  # 允许在元数据中存在未明确定义的额外字段
