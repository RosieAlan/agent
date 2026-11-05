class AuthenticationFailed(Exception):
    """公司会话无效或登录失败。"""


class AccessDenied(Exception):
    """当前用户缺少目标店铺权限。"""


class DependencyUnavailable(Exception):
    """公司接口或数据库暂时不可用。"""
