from fastapi import APIRouter

# router收集这一组接口，app.main负责将它装配到应用。
router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    # 保留已验收的健康检查，迁移目录后返回内容保持一致。
    return {"status": "ok", "project": "运营提效助手"}
