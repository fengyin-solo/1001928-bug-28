"""变桨系统接口：维护变桨系统，覆盖提交调试、登记角度偏差、锁定变桨等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.pitch import PitchService

router = APIRouter(prefix="/api/pitch", tags=["变桨系统"])

service = PitchService()

LIST_FIELDS = ["系统编号", "所属机组", "变桨方式", "桨距角范围", "蓄电池电压", "上次调试日", "调试人员", "变桨状态"]
STATUSES = ["待调试", "调试正常", "角度偏差", "已锁定"]
READONLY_ROLE = "readonly"


def require_writable(x_operator_role: str | None = Header(default=None)) -> None:
    """只读账号只能查看，写操作一律 403 拦下。"""
    if (x_operator_role or "").strip().lower() == READONLY_ROLE:
        raise HTTPException(status_code=403, detail="当前为只读账号，不能登记或变更变桨系统")


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出变桨系统清单：返回去重、按系统编号排序后的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "pitch", "total": total, "items": items}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按系统编号或桨距角范围检索"),
    mode: str | None = Query(default=None, description="按变桨方式收窄，如电动变桨、液压变桨"),
    status: str | None = Query(default=None, description="待调试、调试正常、角度偏差、已锁定"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按变桨方式与变桨状态过滤变桨系统列表；重复系统编号折叠后只给命中的几条。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, mode=mode, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条变桨系统明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"变桨系统 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(
    payload: EntryPayload,
    x_operator_role: str | None = Header(default=None),
) -> ActionResult:
    """登记一条变桨系统，缺字段时说明原因而不是静默丢弃；同一系统编号重复提交只记一次。"""
    require_writable(x_operator_role)
    entry, missing, duplicated = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if duplicated:
        return ActionResult(ok=True, message=f"系统编号已存在，已复用原记录：{entry.get('系统编号')}", entry=entry)
    return ActionResult(ok=True, message="变桨系统已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    x_operator_role: str | None = Header(default=None),
) -> ActionResult:
    """对单条变桨系统执行提交调试、登记角度偏差、锁定变桨；不允许的动作会被拦下并说明原因。"""
    require_writable(x_operator_role)
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
