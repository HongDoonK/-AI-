"""신청 진행 데이터 저장소 (user_data.db).

정책 데이터(youth_policy.db, 읽기 전용)와 분리된 사용자 런타임 DB에
applications / application_items 테이블을 관리한다.
상태머신 전이는 이 모듈에서만 검증한다.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from backend.db import get_user_connection

# 상태머신: docs/AGENT_APPLY_DESIGN.md §3
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"preparing", "expired"},
    "preparing": {"ready", "expired"},
    "ready": {"preparing", "submitted", "expired"},
    "submitted": {"done"},
    "done": set(),
    "expired": set(),
}

ACTIVE_STATUSES = ("draft", "preparing", "ready", "submitted")


def _ensure_tables(cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            application_id    TEXT PRIMARY KEY,
            user_id           TEXT,
            doc_id            TEXT NOT NULL,
            source_table      TEXT,
            source_id         TEXT,
            policy_name       TEXT,
            status            TEXT NOT NULL DEFAULT 'preparing',
            eligibility       TEXT,
            eligibility_notes TEXT,
            apply_channel     TEXT,
            apply_url         TEXT,
            apply_deadline    TEXT,
            draft_answers     TEXT,
            created_at        TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at        TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS application_items (
            item_id        TEXT PRIMARY KEY,
            application_id TEXT NOT NULL,
            kind           TEXT NOT NULL,
            label          TEXT NOT NULL,
            help_label     TEXT,
            help_url       TEXT,
            checked        INTEGER NOT NULL DEFAULT 0,
            sort_order     INTEGER NOT NULL DEFAULT 0
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_applications_user ON applications(user_id, status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_application_items_app ON application_items(application_id)"
    )


def _connect():
    conn = get_user_connection()
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_tables(conn.cursor())
    return conn


def _row_to_application(row, items: list[dict] | None = None) -> dict[str, Any]:
    data = dict(row)
    try:
        data["eligibility_notes"] = json.loads(data.get("eligibility_notes") or "[]")
    except (TypeError, ValueError):
        data["eligibility_notes"] = []
    try:
        data["draft_answers"] = json.loads(data["draft_answers"]) if data.get("draft_answers") else None
    except (TypeError, ValueError):
        data["draft_answers"] = None
    if items is not None:
        data["checklist"] = items
        total = len(items)
        done = sum(1 for item in items if item.get("checked"))
        data["progress"] = {"total": total, "completed": done}
    return data


def find_active_application(user_id: str | None, doc_id: str) -> dict[str, Any] | None:
    """멱등 생성용: 동일 사용자+정책의 진행 중 신청 건을 찾는다."""
    conn = _connect()
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        if user_id:
            cursor.execute(
                f"SELECT * FROM applications WHERE user_id = ? AND doc_id = ? "
                f"AND status IN ({placeholders}) ORDER BY created_at DESC LIMIT 1",
                (user_id, doc_id, *ACTIVE_STATUSES),
            )
        else:
            cursor.execute(
                f"SELECT * FROM applications WHERE user_id IS NULL AND doc_id = ? "
                f"AND status IN ({placeholders}) ORDER BY created_at DESC LIMIT 1",
                (doc_id, *ACTIVE_STATUSES),
            )
        row = cursor.fetchone()
        if not row:
            return None
        return get_application(row["application_id"])
    finally:
        conn.close()


def create_application(plan: dict[str, Any], checklist: list[dict[str, Any]]) -> dict[str, Any]:
    application_id = str(uuid.uuid4())
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO applications (
                application_id, user_id, doc_id, source_table, source_id,
                policy_name, status, eligibility, eligibility_notes,
                apply_channel, apply_url, apply_deadline, draft_answers
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                plan.get("user_id"),
                plan["doc_id"],
                plan.get("source_table"),
                plan.get("source_id"),
                plan.get("policy_name"),
                "preparing",
                plan.get("eligibility"),
                json.dumps(plan.get("eligibility_notes") or [], ensure_ascii=False),
                plan.get("apply_channel"),
                plan.get("apply_url"),
                plan.get("apply_deadline"),
                json.dumps(plan["draft_answers"], ensure_ascii=False) if plan.get("draft_answers") else None,
            ),
        )
        for order, item in enumerate(checklist):
            cursor.execute(
                """
                INSERT INTO application_items (
                    item_id, application_id, kind, label, help_label, help_url, checked, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    str(uuid.uuid4()),
                    application_id,
                    item.get("kind", "action"),
                    item.get("label", ""),
                    item.get("help_label"),
                    item.get("help_url"),
                    order,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return get_application(application_id)


def get_application(application_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM applications WHERE application_id = ?", (application_id,))
        row = cursor.fetchone()
        if not row:
            return None
        cursor.execute(
            "SELECT * FROM application_items WHERE application_id = ? ORDER BY sort_order",
            (application_id,),
        )
        items = [dict(item) for item in cursor.fetchall()]
        for item in items:
            item["checked"] = bool(item["checked"])
        return _row_to_application(row, items)
    finally:
        conn.close()


def list_applications(user_id: str) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM applications WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            cursor.execute(
                "SELECT COUNT(*) AS total, SUM(checked) AS done FROM application_items WHERE application_id = ?",
                (row["application_id"],),
            )
            stats = cursor.fetchone()
            data = _row_to_application(row)
            data["progress"] = {
                "total": stats["total"] or 0,
                "completed": stats["done"] or 0,
            }
            result.append(data)
        return result
    finally:
        conn.close()


class InvalidTransition(ValueError):
    pass


def update_status(application_id: str, new_status: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM applications WHERE application_id = ?", (application_id,))
        row = cursor.fetchone()
        if not row:
            return None
        current = row["status"]
        if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
            raise InvalidTransition(f"'{current}' 상태에서 '{new_status}'(으)로 전이할 수 없습니다.")
        cursor.execute(
            "UPDATE applications SET status = ?, updated_at = datetime('now', 'localtime') "
            "WHERE application_id = ?",
            (new_status, application_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_application(application_id)


def set_item_checked(application_id: str, item_id: str, checked: bool) -> dict[str, Any] | None:
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM applications WHERE application_id = ?", (application_id,))
        row = cursor.fetchone()
        if not row:
            return None
        if row["status"] in {"submitted", "done", "expired"}:
            raise InvalidTransition("제출 이후에는 체크리스트를 변경할 수 없습니다.")
        cursor.execute(
            "UPDATE application_items SET checked = ? WHERE item_id = ? AND application_id = ?",
            (1 if checked else 0, item_id, application_id),
        )
        if cursor.rowcount == 0:
            return None
        cursor.execute(
            "UPDATE applications SET updated_at = datetime('now', 'localtime') WHERE application_id = ?",
            (application_id,),
        )
        conn.commit()
    finally:
        conn.close()
    return get_application(application_id)
