from fastapi import FastAPI
from app.api import ads, health, inventory, requirements
from app.api import conversations  # 导入会话路由定义。
from app.api import ui  # 导入新路由。

app = FastAPI(title="电商Agent学习接口")  # 创建HTTP应用。
app.include_router(health.router)  # 登记健康检查接口。
app.include_router(requirements.router)  # 登记预览、需求抽取接口。
app.include_router(ads.router)  # 登记报表和Agent接口。
app.include_router(inventory.router)  # 登记库存查询、更新接口。
app.include_router(conversations.router)  # 登记这一组接口。
app.include_router(ui.router)  # 将新路由登记到应用。