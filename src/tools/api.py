import datetime # 日期时间模块
import os       # 操作系统模块，用于访问环境变量
import pandas as pd # Pandas库，用于数据处理和分析
import requests   # HTTP请求库
import time       # 时间模块，用于处理延迟

from src.data.cache import get_cache # 从缓存模块导入获取缓存实例的函数
from src.data.models import ( # 从数据模型模块导入各种Pydantic模型
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyFactsResponse,
)

# 全局缓存实例
_cache = get_cache()


def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: dict = None, max_retries: int = 3) -> requests.Response:
    """
    执行API请求，并处理速率限制和适度的退避重试机制。
    
    参数:
        url: 请求的URL
        headers: 请求中包含的头部信息
        method: HTTP方法 (GET 或 POST)
        json_data: POST请求的JSON数据
        max_retries: 最大重试次数 (默认: 3)
    
    返回:
        requests.Response: 响应对象
    
    异常:
        Exception: 如果请求失败且错误非429 (速率限制)
    """
    for attempt in range(max_retries + 1):  # +1 是因为第一次尝试也算在内
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.get(url, headers=headers)
        
        # 如果遇到速率限制 (状态码 429) 并且尚未达到最大重试次数
        if response.status_code == 429 and attempt < max_retries:
            # 线性退避策略: 60秒, 90秒, 120秒, 150秒...
            delay = 60 + (30 * attempt)
            print(f"遇到速率限制 (429)。尝试 {attempt + 1}/{max_retries + 1}。等待 {delay}秒 后重试...")
            time.sleep(delay) # 等待一段时间
            continue # 继续下一次尝试
        
        # 返回响应 (无论是成功、其他错误，还是最终的429错误)
        return response


def get_prices(ticker: str, start_date: str, end_date: str) -> list[Price]:
    """从缓存或API获取价格数据。"""
    # 创建一个包含所有参数的缓存键，以确保精确匹配
    cache_key = f"{ticker}_{start_date}_{end_date}"
    
    # 首先检查缓存 - 进行简单的精确匹配
    cached_data = _cache.get_prices(cache_key)
    if cached_data:
        return [Price(**price) for price in cached_data] # 将字典转换为Price对象

    # 如果不在缓存中，则从API获取
    headers = {}
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY") # 从环境变量获取API密钥
    if api_key:
        headers["X-API-KEY"] = api_key

    url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    response = _make_api_request(url, headers)
    if response.status_code != 200: # 如果API请求不成功
        raise Exception(f"获取数据时出错: {ticker} - {response.status_code} - {response.text}")

    # 使用Pydantic模型解析响应
    price_response = PriceResponse(**response.json())
    prices = price_response.prices

    if not prices: # 如果没有价格数据
        return []

    # 使用综合缓存键缓存结果
    _cache.set_prices(cache_key, [p.model_dump() for p in prices]) # 将Price对象转换为字典进行缓存
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm", # 默认为 "ttm" (最近十二个月)
    limit: int = 10,     # 默认限制10条记录
) -> list[FinancialMetrics]:
    """从缓存或API获取财务指标。"""
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    
    cached_data = _cache.get_financial_metrics(cache_key)
    if cached_data:
        return [FinancialMetrics(**metric) for metric in cached_data]

    headers = {}
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if api_key:
        headers["X-API-KEY"] = api_key

    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    response = _make_api_request(url, headers)
    if response.status_code != 200:
        raise Exception(f"获取数据时出错: {ticker} - {response.status_code} - {response.text}")

    metrics_response = FinancialMetricsResponse(**response.json())
    financial_metrics = metrics_response.financial_metrics

    if not financial_metrics:
        return []

    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
    return financial_metrics


def search_line_items(
    ticker: str,
    line_items: list[str], # 要搜索的财务报表科目列表
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[LineItem]:
    """从API获取财务报表细项。(此函数目前不使用缓存，直接调用API)"""
    headers = {}
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if api_key:
        headers["X-API-KEY"] = api_key

    url = "https://api.financialdatasets.ai/financials/search/line-items" # POST请求URL

    body = { # POST请求体
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    response = _make_api_request(url, headers, method="POST", json_data=body) # 发起POST请求
    if response.status_code != 200:
        raise Exception(f"获取数据时出错: {ticker} - {response.status_code} - {response.text}")

    data = response.json()
    response_model = LineItemResponse(**data) # 使用Pydantic模型解析
    search_results = response_model.search_results
    if not search_results:
        return []

    # 注意：这里没有将结果存入缓存的逻辑，如果需要可以添加
    return search_results[:limit] # 返回指定数量的结果


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None, # 开始日期可选
    limit: int = 1000, # 默认限制1000条
) -> list[InsiderTrade]:
    """从缓存或API获取内部交易数据，并处理分页。"""
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}" # 'none' 用于区分 None 和空字符串
    
    cached_data = _cache.get_insider_trades(cache_key)
    if cached_data:
        return [InsiderTrade(**trade) for trade in cached_data]

    headers = {}
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if api_key:
        headers["X-API-KEY"] = api_key

    all_trades = [] # 用于存储所有获取到的交易数据
    current_end_date = end_date # 用于分页的当前结束日期，初始为用户指定的结束日期

    while True: # 循环直到没有更多数据或满足停止条件
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        url += f"&limit={limit}" # API限制每页返回的数量

        response = _make_api_request(url, headers)
        if response.status_code != 200:
            raise Exception(f"获取数据时出错: {ticker} - {response.status_code} - {response.text}")

        data = response.json()
        response_model = InsiderTradeResponse(**data)
        insider_trades = response_model.insider_trades

        if not insider_trades: # 如果当前页没有数据，则停止
            break

        all_trades.extend(insider_trades) # 将当前页数据添加到总列表

        # 只有在提供了 start_date 并且当前页返回了完整数量的数据时，才继续分页
        if not start_date or len(insider_trades) < limit:
            break

        # 更新 current_end_date 为当前批次中最旧的申报日期，用于下一次迭代
        # .split("T")[0] 是为了去掉时间部分，只保留日期
        current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]

        # 如果我们已经达到或超过了 start_date，就可以停止了
        if current_end_date <= start_date:
            break

    if not all_trades:
        return []

    _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in all_trades])
    return all_trades


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[CompanyNews]:
    """从缓存或API获取公司新闻，并处理分页。"""
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    cached_data = _cache.get_company_news(cache_key)
    if cached_data:
        return [CompanyNews(**news) for news in cached_data]

    headers = {}
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if api_key:
        headers["X-API-KEY"] = api_key

    all_news = []
    current_end_date = end_date # 用于分页的当前结束日期

    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
        if start_date:
            url += f"&start_date={start_date}"
        url += f"&limit={limit}"

        response = _make_api_request(url, headers)
        if response.status_code != 200:
            raise Exception(f"获取数据时出错: {ticker} - {response.status_code} - {response.text}")

        data = response.json()
        response_model = CompanyNewsResponse(**data)
        company_news = response_model.news

        if not company_news:
            break

        all_news.extend(company_news)

        if not start_date or len(company_news) < limit:
            break

        # 更新 current_end_date 为当前批次中最旧的新闻日期
        current_end_date = min(news.date for news in company_news).split("T")[0]

        if current_end_date <= start_date:
            break

    if not all_news:
        return []

    _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
    return all_news


def get_market_cap(
    ticker: str,
    end_date: str, # 通常是分析的“当前”日期
) -> float | None:
    """从API获取市值。"""
    # 检查 end_date 是否为今天
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        # 如果是今天，尝试从公司基本信息API获取实时市值
        headers = {}
        api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if api_key:
            headers["X-API-KEY"] = api_key

        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            print(f"获取公司基本信息时出错: {ticker} - {response.status_code}")
            # 如果获取实时市值失败，可以尝试回退到财务指标中的市值
        else:
            data = response.json()
            response_model = CompanyFactsResponse(**data)
            if response_model.company_facts and response_model.company_facts.market_cap is not None:
                 return response_model.company_facts.market_cap

    # 如果 end_date 不是今天，或者从 company facts 获取失败，则从财务指标中获取最近的市值
    # 注意：财务指标中的市值可能是基于报告期末的，可能不是 end_date 当天的实时市值
    financial_metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=1) # 获取最近的TTM数据
    if not financial_metrics:
        financial_metrics = get_financial_metrics(ticker, end_date, period="quarterly", limit=1) # 尝试季度数据
        if not financial_metrics:
            return None # 如果两种都找不到，则返回None

    market_cap = financial_metrics[0].market_cap # 取第一条（最新的）记录

    if not market_cap: # 再次检查确保 market_cap 不是 None
        return None

    return market_cap


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """将价格对象列表转换为Pandas DataFrame。"""
    df = pd.DataFrame([p.model_dump() for p in prices]) # 将Pydantic模型列表转换为字典列表，然后创建DataFrame
    df["Date"] = pd.to_datetime(df["time"]) # 将 "time" 列转换为日期时间对象，并命名为 "Date"
    df.set_index("Date", inplace=True) # 将 "Date" 列设为索引
    numeric_cols = ["open", "close", "high", "low", "volume"] # 需要转换为数值类型的列
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce") # 转换为数值，无法转换的设为NaN
    df.sort_index(inplace=True) # 按日期索引排序
    return df


# 更新 get_price_data 函数以使用新的辅助函数
def get_price_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取价格数据并将其转换为DataFrame。"""
    prices = get_prices(ticker, start_date, end_date) # 调用新的 get_prices 函数
    return prices_to_df(prices) # 将结果转换为DataFrame
