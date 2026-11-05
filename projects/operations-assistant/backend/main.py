from fastapi import FastAPI  # 导入创建HTTP服务的工具。

# 创建当前项目的应用，下面的接口都注册到这个app上。
app = FastAPI(title="运营提效助手")


# 浏览器请求 GET /health 时，FastAPI执行下面的函数。
@app.get("/health")
def health():
    # Python字典会被FastAPI转换成JSON，返回给浏览器。
    return {
        "status": "ok",
        "project": "运营提效助手",
    }