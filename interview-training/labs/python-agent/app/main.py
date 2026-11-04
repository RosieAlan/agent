from fastapi import FastAPI
from app.api import ads, health, inventory, requirements

app = FastAPI(title="电商Agent学习接口")  # 创建HTTP应用。
app.include_router(health.router)  # 登记健康检查接口。
app.include_router(requirements.router)  # 登记预览、需求抽取接口。
app.include_router(ads.router)  # 登记报表和Agent接口。
app.include_router(inventory.router)  # 登记库存查询、更新接口。
