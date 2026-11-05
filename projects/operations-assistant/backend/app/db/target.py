from sqlalchemy.engine import URL, make_url


def local_project_url(value: str) -> URL:
    """本阶段仅连接本机项目库；部署时单独审核目标配置。"""
    url = make_url(value)
    if (url.drivername != "mysql+pymysql"
        or url.database != "operations_assistant"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.query):
        # 拒绝query中的host/service覆盖URL主机，避免指向其他库。
        raise ValueError("数据库连接必须指向本机MySQL operations_assistant项目库，且不含URL查询参数")
    return url
