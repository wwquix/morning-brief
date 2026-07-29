from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator

from .models import DailyPlan


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS daily_plans (
    plan_date TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    notion_page_id TEXT NOT NULL DEFAULT '',
    notion_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS completions (
    plan_date TEXT NOT NULL,
    item_id TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'local',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (plan_date, item_id)
);

CREATE TABLE IF NOT EXISTS exercise_history (
    exercise_id TEXT PRIMARY KEY,
    last_used_date TEXT NOT NULL,
    use_count INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sync_state (
    state_key TEXT PRIMARY KEY,
    state_value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class PlannerStorage:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def load_plan(self, plan_date: str) -> DailyPlan | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json, notion_page_id, notion_url FROM daily_plans WHERE plan_date = ?",
                (plan_date,),
            ).fetchone()
            if row is None:
                return None
            plan = DailyPlan.from_dict(json.loads(row["payload_json"]))
            plan.notion_page_id = row["notion_page_id"] or plan.notion_page_id
            plan.notion_url = row["notion_url"] or plan.notion_url
            self.apply_completions(connection, plan)
            return plan

    def save_plan(self, plan: DailyPlan) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        payload = json.dumps(plan.to_dict(), ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO daily_plans (
                    plan_date, payload_json, notion_page_id, notion_url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_date) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    notion_page_id = excluded.notion_page_id,
                    notion_url = excluded.notion_url,
                    updated_at = excluded.updated_at
                """,
                (
                    plan.date,
                    payload,
                    plan.notion_page_id,
                    plan.notion_url,
                    now,
                    now,
                ),
            )
            for item in plan.all_items():
                connection.execute(
                    """
                    INSERT INTO completions (plan_date, item_id, completed, source, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(plan_date, item_id) DO NOTHING
                    """,
                    (
                        plan.date,
                        item.id,
                        1 if item.completed else 0,
                        "plan",
                        now,
                    ),
                )

    def update_notion_page(self, plan_date: str, page_id: str, url: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE daily_plans
                SET notion_page_id = ?, notion_url = ?, updated_at = ?
                WHERE plan_date = ?
                """,
                (page_id, url, now, plan_date),
            )

    def set_completion(
        self,
        plan_date: str,
        item_id: str,
        completed: bool,
        source: str = "local",
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO completions (plan_date, item_id, completed, source, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(plan_date, item_id) DO UPDATE SET
                    completed = excluded.completed,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (plan_date, item_id, 1 if completed else 0, source, now),
            )

    def apply_completions(
        self,
        connection: sqlite3.Connection,
        plan: DailyPlan,
    ) -> None:
        rows = connection.execute(
            "SELECT item_id, completed FROM completions WHERE plan_date = ?",
            (plan.date,),
        ).fetchall()
        values = {row["item_id"]: bool(row["completed"]) for row in rows}
        for item in plan.all_items():
            if item.id in values:
                item.completed = values[item.id]

    def completion_summary(self, plan_date: str) -> tuple[int, int]:
        plan = self.load_plan(plan_date)
        if plan is None:
            return 0, 0
        return plan.completed_items, plan.total_items

    def previous_day_summary(self, plan_date: str) -> tuple[int, int]:
        previous = date.fromisoformat(plan_date) - timedelta(days=1)
        return self.completion_summary(previous.isoformat())

    def get_exercise_last_used(self, exercise_id: str) -> str:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT last_used_date FROM exercise_history WHERE exercise_id = ?",
                (exercise_id,),
            ).fetchone()
            return str(row["last_used_date"]) if row else ""

    def record_exercise_usage(self, exercise_id: str, used_date: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO exercise_history (exercise_id, last_used_date, use_count)
                VALUES (?, ?, 1)
                ON CONFLICT(exercise_id) DO UPDATE SET
                    last_used_date = excluded.last_used_date,
                    use_count = exercise_history.use_count + 1
                """,
                (exercise_id, used_date),
            )

    def delete_plan(self, plan_date: str) -> bool:
        plan = self.load_plan(plan_date)
        if plan is None:
            return False
        exercise_ids = [item.id for item in plan.diction]
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM completions WHERE plan_date = ?",
                (plan_date,),
            )
            connection.execute(
                "DELETE FROM daily_plans WHERE plan_date = ?",
                (plan_date,),
            )
            if exercise_ids:
                placeholders = ",".join("?" for _ in exercise_ids)
                connection.execute(
                    f"DELETE FROM exercise_history "
                    f"WHERE last_used_date = ? AND exercise_id IN ({placeholders})",
                    (plan_date, *exercise_ids),
                )
        return True

    def get_sync_state(self, key: str, default: str = "") -> str:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT state_value FROM sync_state WHERE state_key = ?",
                (key,),
            ).fetchone()
            return str(row["state_value"]) if row else default

    def set_sync_state(self, key: str, value: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sync_state (state_key, state_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(state_key) DO UPDATE SET
                    state_value = excluded.state_value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
