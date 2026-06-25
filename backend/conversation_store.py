"""대화 상태 저장소 (user_data.db).

멀티턴 신청 대화의 휘발성 컨텍스트(선택 정책, 최근 추천, 직전 의도)와
턴 기록을 관리한다. 영속 신청 진행 상태(applications)와는 분리한다
(설계: docs/ADR-001-conversational-apply-flow.md §대화 상태 모델).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from backend.db import get_user_connection


def _ensure_tables(cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            session_id           TEXT PRIMARY KEY,
            user_id              TEXT,
            selected_policy      TEXT,
            last_recommendations TEXT,
            last_intent          TEXT,
            created_at           TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at           TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_turns (
            turn_id     TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL,
            intent      TEXT,
            content     TEXT NOT NULL,
            payload     TEXT,
            created_at  TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_turns_session "
        "ON conversation_turns(session_id, created_at)"
    )


def _connect():
    conn = get_user_connection()
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_tables(conn.cursor())
    return conn


def _loads(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


def _row_to_session(row) -> dict[str, Any]:
    data = dict(row)
    data["selected_policy"] = _loads(data.get("selected_policy"), None)
    data["last_recommendations"] = _loads(data.get("last_recommendations"), [])
    return data


def get_session(session_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversations WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        return _row_to_session(row) if row else None
    finally:
        conn.close()


def cleanup_old_sessions(days: int = 7) -> int:
    """days일 이상 갱신되지 않은 세션과 관련 턴을 삭제한다. 삭제 건수를 반환."""
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id FROM conversations "
            "WHERE updated_at < datetime('now', 'localtime', ? || ' days')",
            (f"-{days}",),
        )
        old_ids = [row["session_id"] for row in cursor.fetchall()]
        if not old_ids:
            return 0
        placeholders = ",".join("?" * len(old_ids))
        conn.execute(f"DELETE FROM conversation_turns WHERE session_id IN ({placeholders})", old_ids)
        conn.execute(f"DELETE FROM conversations WHERE session_id IN ({placeholders})", old_ids)
        conn.commit()
        return len(old_ids)
    finally:
        conn.close()


def get_or_create_session(session_id: str | None, user_id: str | None) -> dict[str, Any]:
    """session_id가 있고 존재하면 복원, 없으면 새로 만든다. 호출 시 오래된 세션을 정리한다."""
    cleanup_old_sessions(days=7)
    if session_id:
        existing = get_session(session_id)
        if existing:
            return existing
    new_id = session_id or str(uuid.uuid4())
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO conversations (session_id, user_id) VALUES (?, ?)",
            (new_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_session(new_id)


def update_session(
    session_id: str,
    *,
    selected_policy: dict[str, Any] | None = None,
    last_recommendations: list[dict[str, Any]] | None = None,
    last_intent: str | None = None,
    clear_selection: bool = False,
) -> dict[str, Any] | None:
    """전달된 필드만 갱신한다. clear_selection=True면 선택 정책을 비운다."""
    sets, params = [], []
    if clear_selection:
        sets.append("selected_policy = NULL")
    elif selected_policy is not None:
        sets.append("selected_policy = ?")
        params.append(json.dumps(selected_policy, ensure_ascii=False))
    if last_recommendations is not None:
        sets.append("last_recommendations = ?")
        params.append(json.dumps(last_recommendations, ensure_ascii=False))
    if last_intent is not None:
        sets.append("last_intent = ?")
        params.append(last_intent)
    sets.append("updated_at = datetime('now', 'localtime')")
    params.append(session_id)
    conn = _connect()
    try:
        conn.execute(f"UPDATE conversations SET {', '.join(sets)} WHERE session_id = ?", params)
        conn.commit()
    finally:
        conn.close()
    return get_session(session_id)


def add_turn(
    session_id: str,
    role: str,
    content: str,
    *,
    intent: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO conversation_turns (turn_id, session_id, role, intent, content, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                session_id,
                role,
                intent,
                content,
                json.dumps(payload, ensure_ascii=False) if payload else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_turns(session_id: str) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        cursor = conn.cursor()
        # 삽입 순서 보장: created_at은 초 단위라 같은 초에 들어온 턴 순서가 뒤섞이고
        # turn_id는 무작위 UUID라 정렬 기준이 못 된다. SQLite rowid는 삽입마다 단조 증가하므로
        # rowid로 정렬해야 user/assistant 턴 순서가 항상 삽입 순서와 일치한다.
        cursor.execute(
            "SELECT * FROM conversation_turns WHERE session_id = ? ORDER BY rowid",
            (session_id,),
        )
        turns = []
        for row in cursor.fetchall():
            data = dict(row)
            data["payload"] = _loads(data.get("payload"), None)
            turns.append(data)
        return turns
    finally:
        conn.close()
