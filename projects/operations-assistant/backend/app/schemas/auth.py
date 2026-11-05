from pydantic import BaseModel, ConfigDict, Field, SecretStr


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")  # 拒绝额外传入user_id或权限字段。
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=256)  # 避免对象日志显示密码。


class CurrentUser(BaseModel):
    id: str
    username: str
    display_name: str


class LoginOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: CurrentUser


class AuthContext(BaseModel):
    user: CurrentUser
    account_codes: list[str]  # 仅来自公司当前用户数据权限接口。
