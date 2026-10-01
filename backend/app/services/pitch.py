"""变桨系统业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "pitch"
REQUIRED_FIELDS = ["系统编号", "所属机组", "变桨方式"]
STATUS_ORDER = ["待调试", "调试正常", "角度偏差", "已锁定"]
ACTION_RULES = {"提交调试": "调试正常", "登记角度偏差": "角度偏差", "锁定变桨": "已锁定"}
NEGATIVE_ACTIONS = []

CODE_FIELD = "系统编号"
MODE_FIELD = "变桨方式"
ANGLE_FIELD = "桨距角范围"
DISPLAY_STATUS_FIELD = "变桨状态"


class PitchService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        mode: str | None = None,
        status: str | None = None,
        angle: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        # 同一套系统只保留一条：按系统编号去重，多条重复时取 id 最小（最早登记）的那条。
        chosen: dict[str, dict[str, Any]] = {}
        for row in store.rows(MODULE):
            code = str(row.get(CODE_FIELD, "")).strip()
            current = chosen.get(code)
            if current is None or int(row.get("id", 0)) < int(current.get("id", 0)):
                chosen[code] = row
        rows = list(chosen.values())

        keyword = (keyword or "").strip()
        mode = (mode or "").strip()
        angle = (angle or "").strip()
        status = (status or "").strip()

        if keyword:
            rows = [row for row in rows if keyword in str(row.get(CODE_FIELD, ""))]
        if mode:
            rows = [row for row in rows if mode in str(row.get(MODE_FIELD, ""))]
        if angle:
            rows = [row for row in rows if angle in str(row.get(ANGLE_FIELD, ""))]
        if status:
            rows = [row for row in rows if str(row.get("status", "")) == status]

        # 按系统编号稳定排序，编号相同时用 id 兜底，保证每次看到的顺序一致。
        rows.sort(key=lambda row: (str(row.get(CODE_FIELD, "")), int(row.get("id", 0))))

        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = [self._present(row) for row in rows[start:start + size]]
        return page_rows, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._present(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        rows = store.rows(MODULE)
        code = str(values.get(CODE_FIELD) or "").strip()
        # 重复提交只记一次：同一系统编号已存在时直接拦下，不再新增记录。
        if any(str(row.get(CODE_FIELD, "")).strip() == code for row in rows):
            return None, f"系统编号 {code} 已登记，重复提交不会重复记录"
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, None

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"变桨系统 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于变桨系统可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        # 幂等：已经处于目标状态时不再重复记录，直接返回当前记录。
        if entry.get("status") == target:
            return entry, f"变桨系统当前已是「{target}」，无需重复{action}"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"变桨系统已{action}"

    @staticmethod
    def _present(row: dict[str, Any]) -> dict[str, Any]:
        """对外展示时让「变桨状态」列与内部真实状态保持一致，列表/详情口径统一。"""
        presented = dict(row)
        presented[DISPLAY_STATUS_FIELD] = row.get("status")
        return presented
