"""变桨系统接口：维护变桨系统，覆盖提交调试、登记角度偏差、锁定变桨等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import require_writable
from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.pitch import STATUS_ORDER, PitchService

router = APIRouter(prefix="/api/pitch", tags=["变桨系统"])

service = PitchService()

LIST_FIELDS = ["系统编号", "所属机组", "变桨方式", "桨距角范围", "蓄电池电压", "上次调试日", "调试人员", "变桨状态"]
STATUSES = STATUS_ORDER


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按系统编号检索"),
    mode: str | None = Query(default=None, description="按变桨方式筛选"),
    angle: str | None = Query(default=None, description="按桨距角读数/范围检索"),
    status: str | None = Query(default=None, description="待调试、调试正常、角度偏差、已锁定"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按系统编号、变桨方式、桨距角与状态过滤；结果按系统编号去重并稳定排序。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if status and status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"变桨状态「{status}」不在可筛选范围内")
    items, total = service.list_entries(
        keyword=keyword, mode=mode, angle=angle, status=status, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出变桨系统清单：去重后按系统编号排序的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "pitch", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条变桨系统明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"变桨系统 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult, dependencies=[Depends(require_writable)])
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条变桨系统，缺字段或编号重复时说明原因而不是静默丢弃。"""
    entry, message = service.create_entry(payload.values)
    if message:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message="变桨系统已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult, dependencies=[Depends(require_writable)])
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条变桨系统执行提交调试、登记角度偏差、锁定变桨；重复提交只生效一次。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
