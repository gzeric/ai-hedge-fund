from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import json

# 创建一个 FastAPI APIRouter 实例，用于定义相关路由
router = APIRouter()


# 定义根路径 ("/") 的 GET 请求处理函数
@router.get("/")
async def root():
    """当访问 API 根路径时，返回欢迎信息。"""
    return {"message": "Welcome to AI Hedge Fund API"}  # 返回一个包含欢迎信息的 JSON 对象


# 定义 "/ping" 路径的 GET 请求处理函数
@router.get("/ping")
async def ping():
    """
    一个异步生成器函数，用于模拟服务器发送事件 (SSE)。
    它会每秒发送一个 "ping" 事件，共发送5次。
    """
    async def event_generator():
        for i in range(5):
            # 为每个 ping 创建一个 JSON 对象
            data = {"ping": f"ping {i+1}/5", "timestamp": i + 1} # 数据包含 ping 的次数和时间戳

            # 格式化为 SSE (Server-Sent Event)
            # SSE 格式要求 "data: " 开头，并以 "\n\n" 结尾
            yield f"data: {json.dumps(data)}\n\n"

            # 等待1秒
            await asyncio.sleep(1)

    # 返回一个 StreamingResponse，它会持续发送 event_generator() 生成的事件
    # media_type 设置为 "text/event-stream"，这是 SSE 的标准 MIME 类型
    return StreamingResponse(event_generator(), media_type="text/event-stream")
