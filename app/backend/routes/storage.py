from fastapi import APIRouter, HTTPException
import json
from pathlib import Path # 用于处理文件路径
from pydantic import BaseModel # 用于数据验证和模型定义

from app.backend.models.schemas import ErrorResponse # 导入错误响应模型

# 创建一个 FastAPI APIRouter 实例，所有此文件中的路由都将以 "/storage" 为前缀
router = APIRouter(prefix="/storage")

# 定义保存 JSON 请求的数据模型
class SaveJsonRequest(BaseModel):
    filename: str  # 要保存的文件名
    data: dict    # 要保存的 JSON 数据 (以字典形式)

# 定义 "/save-json" 路径的 POST 请求处理函数
@router.post(
    path="/save-json",
    responses={ # 定义可能的响应状态码和描述
        200: {"description": "文件成功保存"},
        400: {"model": ErrorResponse, "description": "无效的请求参数"},
        500: {"model": ErrorResponse, "description": "内部服务器错误"},
    },
)
async def save_json_file(request: SaveJsonRequest):
    """将 JSON 数据保存到项目的 /outputs 目录中。"""
    try:
        # 1. 确定项目根目录并创建 outputs 目录 (如果不存在)
        # Path(__file__) 获取当前文件的路径
        # .parent.parent.parent.parent 向上导航四级以到达项目根目录
        # (app/backend/routes/storage.py -> app/backend/routes -> app/backend -> app -> project_root)
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        outputs_dir = project_root / "outputs" # 构建 outputs 目录的路径
        outputs_dir.mkdir(exist_ok=True) # 创建目录，如果目录已存在则不报错
        
        # 2. 构建完整的文件路径
        # Ensure the filename is safe and does not contain path traversal characters
        # (虽然这里没有显式检查，但在生产环境中应该添加文件名清理和验证)
        file_path = outputs_dir / request.filename
        
        # 3. 将 JSON 数据写入文件
        # 使用 'w'模式打开文件 (写入模式，如果文件存在则覆盖)
        # encoding='utf-8'确保正确处理各种字符
        # ensure_ascii=False 允许在 JSON 中使用非 ASCII 字符 (例如中文)
        # indent=2 使 JSON 文件具有良好的可读性 (缩进2个空格)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(request.data, f, indent=2, ensure_ascii=False)
        
        # 4. 返回成功响应
        return {
            "success": True,
            "message": f"文件成功保存至 {file_path}",
            "filename": request.filename
        }
        
    except Exception as e: # 捕获所有可能的异常
        # 如果发生错误，则抛出 HTTP 500 错误
        raise HTTPException(status_code=500, detail=f"保存文件失败: {str(e)}")