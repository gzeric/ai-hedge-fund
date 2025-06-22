from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend.routes import api_router

# 创建 FastAPI 应用实例
# title: API 标题
# description: API 描述
# version: API 版本
app = FastAPI(title="AI Hedge Fund API", description="Backend API for AI Hedge Fund", version="0.1.0")

# 配置 CORS (跨源资源共享)
# 允许前端应用 (例如 http://localhost:5173) 访问后端 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # 允许的前端 URL 列表
    allow_credentials=True,  # 允许携带凭证 (例如 cookies)
    allow_methods=["*"],  # 允许所有 HTTP 方法 (GET, POST, etc.)
    allow_headers=["*"],  # 允许所有 HTTP 请求头
)

# 包含所有 API 路由
# api_router 定义在 app.backend.routes 中
app.include_router(api_router)
