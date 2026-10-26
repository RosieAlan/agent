# D06：文件工具与路径限制；授课串联。日期：10/26

原4.3.1/4.3.2逐项：query_requirement读业务JSON并JSON.parse；read_file读UTF8标准；write_file创建目录并写制品；名称/描述/Schema+绑定+执行字典+ToolMessage均沿用。工作目录workspace，文件路径和内容是工具参数。原safePath使用字符串startsWith有同前缀兄弟目录风险，Python改resolve+is_relative_to；这是应用内路径校验，OS沙箱/权限和并发符号链接替换风险在D26完整处理。

以下独立文件服务教学代码，完整可复制；本轮不要求新增HTTP入口。@tool封装沿已学模式，读写异常须在调用边界处理；FileNotFoundError/PermissionError/FileExistsError分别表示不存在/权限不足/拒绝覆盖。当前库存/广告为只读成功缓存，写工具应按允许的工具名限定缓存范围，跨请求幂等与审批D20。D07日志/制品入库对照与D26越权联调继续验收。

```python
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent / "workspace"


def safe_path(relative_path: str) -> Path:
    root = WORKSPACE_ROOT.resolve()  # 得到工作目录的完整路径。
    if Path(relative_path).is_absolute():
        raise ValueError("请使用工作目录内的相对路径")
    target = (root / relative_path).resolve()  # 合并路径，展开..和已有符号链接。
    if not target.is_relative_to(root):  # 按目录层级判断目标归属。
        raise ValueError("路径超出允许的工作目录")
    return target


def read_workspace_file(relative_path: str) -> str:
    target = safe_path(relative_path)  # 先验证，再读取。
    return target.read_text(encoding="utf-8")


def write_workspace_file(relative_path: str, content: str) -> dict:
    target = safe_path(relative_path)  # 先验证，再创建目录和写入。
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as output:  # 新建文件；已有文件时拒绝覆盖。
        output.write(content)
    return {"path": relative_path, "saved": True}

```

对应TS：path.resolve→Path.resolve；fs.readFileSync→read_text；fs.mkdirSync recursive→mkdir parents；fs.writeFileSync覆盖→本例open x拒绝覆盖；JSON.parse→json.loads。生产用户隔离依服务端身份与所属数据查验，路径位于工作目录不能自动证明当前用户有读取权限。

必背：模型产生文件路径和内容参数，后端验证路径/权限后读写并返回实际结果；读取用于给模型事实或规范，写入用于保存报告制品。输入Schema验证结构，目录限制与权限验证可执行范围。

本轮独立临时目录验证读写、../越界、同前缀兄弟目录、绝对路径和覆盖拒绝通过，临时目录自动清理；未修改学生业务文件。学生独立文件读写/越界、库存25、三失败例、缓存命中/跨轮日志待补。D06授课完成，验收待收尾；用户明确请求加速进入D07，按授权推进，完整独立通过1/32。

D01模型调用与结构校验→D02历史和状态→D03Prompt与HTTP结构化接口→D04超时/取消/重试/SSE/日志→D05投放迁移与Python主线→D06工具参数/绑定/后端执行/结果回传/有限循环/缓存/失败/库存迁移/文件边界。独立已交运行证据与未交检查分别记录。
