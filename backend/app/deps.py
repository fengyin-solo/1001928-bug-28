"""接口公共依赖：识别当前账号是否只读。

前端在请求头里带 X-Operator-Role: readonly | readwrite；
不带时按可读写处理，保证导出与脚本调用不受影响。
"""
from __future__ import annotations

from fastapi import Header, HTTPException

READONLY_ROLE = "readonly"


def require_writable(x_operator_role: str | None = Header(default=None)) -> None:
    """写操作（登记、动作）前校验：只读账号一律拒绝，由前端按钮置灰做前置拦截。"""
    if (x_operator_role or "").strip().lower() == READONLY_ROLE:
        raise HTTPException(status_code=403, detail="当前为只读账号，无权变更变桨系统数据")
