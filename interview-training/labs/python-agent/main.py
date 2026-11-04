"""兼容原uvicorn main:app命令；实际应用入口为app/main.py。"""
from app.main import app  # 复用同一个应用，保留原启动命令。
