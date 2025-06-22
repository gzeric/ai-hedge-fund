from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio

from app.backend.models.schemas import ErrorResponse, HedgeFundRequest
from app.backend.models.events import StartEvent, ProgressUpdateEvent, ErrorEvent, CompleteEvent
from app.backend.services.graph import create_graph, parse_hedge_fund_response, run_graph_async
from app.backend.services.portfolio import create_portfolio
from src.utils.progress import progress # 导入进度跟踪模块
from src.utils.analysts import get_agents_list # 导入获取代理列表的函数
from src.llm.models import get_models_list # 导入获取模型列表的函数

# 创建一个 FastAPI APIRouter 实例，所有此文件中的路由都将以 "/hedge-fund" 为前缀
router = APIRouter(prefix="/hedge-fund")

# 定义 "/run" 路径的 POST 请求处理函数
@router.post(
    path="/run",
    responses={ # 定义可能的响应状态码和描述
        200: {"description": "成功响应并带有流式更新"},
        400: {"model": ErrorResponse, "description": "无效的请求参数"},
        500: {"model": ErrorResponse, "description": "内部服务器错误"},
    },
)
async def run_hedge_fund(request: HedgeFundRequest):
    """
    异步处理运行对冲基金模拟的请求。
    它会创建一个投资组合，构建并运行一个代理图，并通过 SSE 流式传输进度和结果。
    """
    try:
        # 1. 创建投资组合实例
        portfolio = create_portfolio(request.initial_cash, request.margin_requirement, request.tickers)

        # 2. 构建代理图 (Agent Graph)
        graph = create_graph(request.selected_agents) # 根据选定的代理创建图
        graph = graph.compile() # 编译图，准备执行

        # 记录一条测试进度更新，用于调试
        progress.update_status("system", None, "准备运行对冲基金模拟")

        # 如果 model_provider 是枚举类型，则转换为字符串值
        model_provider = request.model_provider
        if hasattr(model_provider, "value"):
            model_provider = model_provider.value

        # 3. 设置流式响应 (SSE)
        async def event_generator():
            """异步生成器，用于产生 SSE 事件流。"""
            # 用于存储进度更新的队列
            progress_queue = asyncio.Queue()

            # 定义一个简单的处理函数，将进度更新添加到队列中
            def progress_handler(agent_name, ticker, status, analysis, timestamp):
                event = ProgressUpdateEvent(agent=agent_name, ticker=ticker, status=status, timestamp=timestamp, analysis=analysis)
                progress_queue.put_nowait(event) # 非阻塞方式放入队列

            # 注册进度处理函数到全局进度跟踪器
            progress.register_handler(progress_handler)

            try:
                # 4. 在后台任务中开始执行代理图
                run_task = asyncio.create_task(
                    run_graph_async(
                        graph=graph,
                        portfolio=portfolio,
                        tickers=request.tickers,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        model_name=request.model_name,
                        model_provider=model_provider,
                        request=request,  # 传递完整的请求对象，以便代理可以访问特定模型的配置
                    )
                )
                # 发送初始的 "start" 事件
                yield StartEvent().to_sse()

                # 5. 流式传输进度更新，直到 run_task 完成
                while not run_task.done():
                    try:
                        # 尝试从队列中获取进度更新，超时时间为1秒
                        event = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                        yield event.to_sse() # 发送进度事件
                    except asyncio.TimeoutError:
                        # 超时则继续循环，检查 run_task 是否完成
                        pass

                # 6. 获取最终结果
                result = run_task.result() # 等待并获取 run_graph_async 的返回结果

                # 如果结果为空或没有消息，则发送错误事件
                if not result or not result.get("messages"):
                    yield ErrorEvent(message="未能生成对冲基金决策").to_sse()
                    return

                # 7. 发送最终的 "complete" 事件和结果数据
                final_data = CompleteEvent(
                    data={
                        "decisions": parse_hedge_fund_response(result.get("messages", [])[-1].content), # 解析最后一个消息的内容作为决策
                        "analyst_signals": result.get("data", {}).get("analyst_signals", {}), # 获取分析师信号
                    }
                )
                yield final_data.to_sse()

            finally:
                # 8. 清理操作
                progress.unregister_handler(progress_handler) # 注销进度处理函数
                # 如果任务仍在运行（例如，如果生成器被外部关闭），则取消任务
                if "run_task" in locals() and not run_task.done():
                    run_task.cancel()

        # 返回一个 StreamingResponse，它会持续发送 event_generator() 生成的事件
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except HTTPException as e: # 捕获 FastAPI 的 HTTP 异常并重新抛出
        raise e
    except Exception as e: # 捕获其他所有异常，并返回 500 错误
        raise HTTPException(status_code=500, detail=f"处理请求时发生错误: {str(e)}")

# 定义 "/agents" 路径的 GET 请求处理函数
@router.get(
    path="/agents",
    responses={
        200: {"description": "可用代理列表"},
        500: {"model": ErrorResponse, "description": "内部服务器错误"},
    },
)
async def get_agents():
    """获取可用的代理列表。"""
    try:
        return {"agents": get_agents_list()} # 调用 src.utils.analysts 中的函数获取列表
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"未能检索到代理列表: {str(e)}")


# 定义 "/language-models" 路径的 GET 请求处理函数
@router.get(
    path="/language-models",
    responses={
        200: {"description": "可用的语言模型列表"},
        500: {"model": ErrorResponse, "description": "内部服务器错误"},
    },
)
async def get_language_models():
    """获取可用的语言模型列表。"""
    try:
        return {"models": get_models_list()} # 调用 src.llm.models 中的函数获取列表
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"未能检索到模型列表: {str(e)}")

