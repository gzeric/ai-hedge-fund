from typing import Dict, Optional, Any, Literal
from pydantic import BaseModel


class BaseEvent(BaseModel):
    """所有服务器发送事件 (SSE) 的基类"""

    type: str  # 事件类型

    def to_sse(self) -> str:
        """转换为服务器发送事件 (SSE) 格式"""
        event_type = self.type.lower()
        # 格式:
        # event: 事件类型
        # data: JSON 格式的事件数据
        # \n\n (表示事件结束)
        return f"event: {event_type}\ndata: {self.model_dump_json()}\n\n"


class StartEvent(BaseEvent):
    """表示处理开始的事件"""

    type: Literal["start"] = "start"  # 事件类型固定为 "start"
    timestamp: Optional[str] = None  # 事件发生的时间戳 (可选)

class ProgressUpdateEvent(BaseEvent):
    """包含代理进度更新的事件"""

    type: Literal["progress"] = "progress"  # 事件类型固定为 "progress"
    agent: str  # 产生此事件的代理名称
    ticker: Optional[str] = None  # 相关的股票代码 (可选)
    status: str  # 当前状态描述
    timestamp: Optional[str] = None  # 事件发生的时间戳 (可选)
    analysis: Optional[str] = None  # 分析结果或中间信息 (可选)

class ErrorEvent(BaseEvent):
    """表示发生错误的事件"""

    type: Literal["error"] = "error"  # 事件类型固定为 "error"
    message: str  # 错误信息
    timestamp: Optional[str] = None  # 事件发生的时间戳 (可选)


class CompleteEvent(BaseEvent):
    """表示成功完成并附带结果的事件"""

    type: Literal["complete"] = "complete"  # 事件类型固定为 "complete"
    data: Dict[str, Any]  # 处理结果数据，以字典形式存储
    timestamp: Optional[str] = None  # 事件发生的时间戳 (可选)
