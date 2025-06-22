class Cache:
    """用于 API 响应的内存缓存。"""

    def __init__(self):
        # 缓存结构：字典，键为股票代码 (ticker)，值为包含字典的列表。
        # 每个内部字典代表一条数据记录 (例如，一个时间点的价格，一份财报等)。
        self._prices_cache: dict[str, list[dict[str, any]]] = {}  # 价格数据缓存
        self._financial_metrics_cache: dict[str, list[dict[str, any]]] = {}  # 财务指标缓存
        self._line_items_cache: dict[str, list[dict[str, any]]] = {}  # 财务报表细项缓存
        self._insider_trades_cache: dict[str, list[dict[str, any]]] = {}  # 内部交易缓存
        self._company_news_cache: dict[str, list[dict[str, any]]] = {}  # 公司新闻缓存

    def _merge_data(self, existing: list[dict] | None, new_data: list[dict], key_field: str) -> list[dict]:
        """
        合并现有数据和新数据，基于一个关键字段避免重复。

        参数:
          existing (list[dict] | None): 已缓存的数据列表，如果不存在则为 None。
          new_data (list[dict]): 要添加的新数据列表。
          key_field (str): 用于检查重复项的字典键名 (例如 "time", "report_period")。

        返回:
          list[dict]: 合并后的数据列表，不含重复项。
        """
        if not existing: # 如果缓存中没有现有数据
            return new_data # 直接返回新数据

        # 创建一个现有键的集合，以便进行 O(1) 复杂度的查找
        existing_keys = {item[key_field] for item in existing}

        # 只添加尚不存在的项目
        merged = existing.copy() # 复制现有数据以避免修改原始列表
        # 遍历新数据，如果其关键字段的值不在 existing_keys 中，则添加到 merged 列表
        merged.extend([item for item in new_data if item[key_field] not in existing_keys])
        return merged

    def get_prices(self, ticker: str) -> list[dict[str, any]] | None:
        """如果可用，获取缓存的价格数据。"""
        return self._prices_cache.get(ticker)

    def set_prices(self, ticker: str, data: list[dict[str, any]]):
        """将新的价格数据追加到缓存。使用 "time" 字段去重。"""
        self._prices_cache[ticker] = self._merge_data(self._prices_cache.get(ticker), data, key_field="time")

    def get_financial_metrics(self, ticker: str) -> list[dict[str, any]] | None:
        """如果可用，获取缓存的财务指标。"""
        return self._financial_metrics_cache.get(ticker)

    def set_financial_metrics(self, ticker: str, data: list[dict[str, any]]):
        """将新的财务指标追加到缓存。使用 "report_period" 字段去重。"""
        self._financial_metrics_cache[ticker] = self._merge_data(self._financial_metrics_cache.get(ticker), data, key_field="report_period")

    def get_line_items(self, ticker: str) -> list[dict[str, any]] | None:
        """如果可用，获取缓存的财务报表细项。"""
        return self._line_items_cache.get(ticker)

    def set_line_items(self, ticker: str, data: list[dict[str, any]]):
        """将新的财务报表细项追加到缓存。使用 "report_period" 字段去重。"""
        self._line_items_cache[ticker] = self._merge_data(self._line_items_cache.get(ticker), data, key_field="report_period")

    def get_insider_trades(self, ticker: str) -> list[dict[str, any]] | None:
        """如果可用，获取缓存的内部交易数据。"""
        return self._insider_trades_cache.get(ticker)

    def set_insider_trades(self, ticker: str, data: list[dict[str, any]]):
        """将新的内部交易数据追加到缓存。使用 "filing_date" 字段去重 (也可以根据需要使用 "transaction_date")。"""
        self._insider_trades_cache[ticker] = self._merge_data(self._insider_trades_cache.get(ticker), data, key_field="filing_date")

    def get_company_news(self, ticker: str) -> list[dict[str, any]] | None:
        """如果可用，获取缓存的公司新闻。"""
        return self._company_news_cache.get(ticker)

    def set_company_news(self, ticker: str, data: list[dict[str, any]]):
        """将新的公司新闻追加到缓存。使用 "date" 字段去重。"""
        self._company_news_cache[ticker] = self._merge_data(self._company_news_cache.get(ticker), data, key_field="date")


# 全局缓存实例
_cache = Cache()


def get_cache() -> Cache:
    """获取全局缓存实例。"""
    return _cache
