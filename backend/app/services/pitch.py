"""变桨系统业务规则：状态流转、字段校验与筛选口径都收在这里。

列表口径（与详情/导出保持一致）：
1. 同一「系统编号」只保留最早登记的一条（id 最小），重复记录折叠掉；
2. 再按变桨方式 / 变桨状态 / 关键词收窄；
3. 最后按系统编号稳定排序后分页，total 与去重后的条数一致。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "pitch"
REQUIRED_FIELDS = ["系统编号", "所属机组", "变桨方式"]
OPTIONAL_FIELDS = ["桨距角范围", "蓄电池电压", "上次调试日", "调试人员"]
STATUS_ORDER = ["待调试", "调试正常", "角度偏差", "已锁定"]
ACTION_RULES = {"提交调试": "调试正常", "登记角度偏差": "角度偏差", "锁定变桨": "已锁定"}
NEGATIVE_ACTIONS = ["登记角度偏差"]
SORT_FIELD = "系统编号"
ANGLE_FIELD = "桨距角范围"
MODE_FIELD = "变桨方式"
DISPLAY_STATUS_FIELD = "变桨状态"


def _code(row: dict[str, Any]) -> str:
    return str(row.get(SORT_FIELD) or "").strip()


def _state(row: dict[str, Any]) -> str:
    return str(row.get("status") or "").strip()


def _row_id(row: dict[str, Any]) -> int:
    try:
        return int(row.get("id", 0))
    except (TypeError, ValueError):
        return 0


def _canonical_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按系统编号去重并稳定排序：同一系统保留 id 最小的一条，空编号各自保留。"""
    unique: dict[str, dict[str, Any]] = {}
    no_code: list[dict[str, Any]] = []
    for row in rows:
        code = _code(row)
        if not code:
            no_code.append(row)
            continue
        current = unique.get(code)
        if current is None or _row_id(row) < _row_id(current):
            unique[code] = row
    deduped = sorted(unique.values(), key=lambda row: (_code(row), _row_id(row)))
    deduped.extend(sorted(no_code, key=_row_id))
    return deduped


class PitchService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        mode: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = _canonical_rows(store.rows(MODULE))
        if mode and mode.strip():
            needle = mode.strip().lower()
            rows = [row for row in rows if needle in str(row.get(MODE_FIELD, "")).lower()]
        if status and status.strip():
            wanted = status.strip()
            rows = [row for row in rows if _state(row) == wanted]
        if keyword and keyword.strip():
            needle = keyword.strip().lower()

            def hit(row: dict[str, Any]) -> bool:
                return needle in _code(row).lower() or needle in str(row.get(ANGLE_FIELD, "")).lower()

            rows = [row for row in rows if hit(row)]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None or not self._is_canonical(entry):
            return None
        return entry

    @staticmethod
    def _is_canonical(entry: dict[str, Any]) -> bool:
        """列表/导出只保留每个系统编号最早登记的一条，其余重复记录视为已合并归档。"""
        code = _code(entry)
        if not code:
            return True
        canonical = {
            _code(row): row for row in _canonical_rows(store.rows(MODULE)) if _code(row)
        }
        return canonical.get(code) is entry

    def find_by_code(self, code: str) -> dict[str, Any] | None:
        """按系统编号取去重后的唯一记录，用于登记前去重判断。"""
        wanted = code.strip()
        for row in _canonical_rows(store.rows(MODULE)):
            if _code(row) == wanted:
                return row
        return None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], bool]:
        """登记一条变桨系统。

        返回 (记录, 缺失字段, 是否命中已有系统编号)。同一系统编号重复提交时直接回吐
        已有记录、不再新增，保证「重复提交只记一次」。
        """
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, False
        code = str(values.get("系统编号") or "").strip()
        existing = self.find_by_code(code)
        if existing is not None:
            return existing, [], True
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((_row_id(row) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip() != "":
                entry[field] = str(value).strip()
        entry["status"] = STATUS_ORDER[0]
        entry[DISPLAY_STATUS_FIELD] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, [], False

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None or not self._is_canonical(entry):
            return None, f"变桨系统 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于变桨系统可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        if _state(entry) == target:
            # 已经是目标状态：重复点击不重复记录、不反复翻转状态。
            return entry, f"当前已是「{target}」，未重复{action}"
        entry["status"] = target
        entry[DISPLAY_STATUS_FIELD] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"变桨系统已{action}"
