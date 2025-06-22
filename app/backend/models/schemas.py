from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import List, Optional
from src.llm.models import ModelProvider # 导入模型提供者枚举


# 定义代理的模型配置
class AgentModelConfig(BaseModel):
    agent_id: str  # 代理ID
    model_name: Optional[str] = None  # 模型名称 (可选)
    model_provider: Optional[ModelProvider] = None  # 模型提供者 (可选)


# 定义对冲基金API的响应结构
class HedgeFundResponse(BaseModel):
    decisions: dict  # 投资决策
    analyst_signals: dict  # 分析师信号


# 定义错误响应结构
class ErrorResponse(BaseModel):
    message: str  # 错误信息
    error: str | None = None  # 详细错误内容 (可选)


# 定义对冲基金API的请求结构
class HedgeFundRequest(BaseModel):
    tickers: List[str]  # 股票代码列表
    selected_agents: List[str]  # 选定的代理列表
    agent_models: Optional[List[AgentModelConfig]] = None  # 各代理的模型配置 (可选)
    # 结束日期，默认为当前日期，格式为 "YYYY-MM-DD"
    end_date: Optional[str] = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    start_date: Optional[str] = None  # 开始日期 (可选)，格式为 "YYYY-MM-DD"
    model_name: str = "gpt-4o"  # 默认使用的模型名称
    model_provider: ModelProvider = ModelProvider.OPENAI  # 默认模型提供者
    initial_cash: float = 100000.0  # 初始现金金额
    margin_requirement: float = 0.0  # 保证金要求

    def get_start_date(self) -> str:
        """如果未提供开始日期，则计算开始日期"""
        if self.start_date:
            return self.start_date
        # 如果未提供 start_date，则默认从 end_date 往前回溯90天
        return (datetime.strptime(self.end_date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")

    def get_agent_model_config(self, agent_id: str) -> tuple[str, ModelProvider]:
        """获取特定代理的模型配置"""
        if self.agent_models:
            for config in self.agent_models:
                if config.agent_id == agent_id:
                    # 如果代理有特定配置，则使用该配置；否则使用全局配置
                    return (
                        config.model_name or self.model_name, # 如果 config.model_name 为 None，则使用 self.model_name
                        config.model_provider or self.model_provider # 如果 config.model_provider 为 None，则使用 self.model_provider
                    )
        # 如果没有找到特定代理的配置，则回退到全局模型设置
        return self.model_name, self.model_provider
