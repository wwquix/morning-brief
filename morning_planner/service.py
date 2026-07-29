from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .local_sources import (
    deduplicate_items,
    normalize_text,
    read_exercises,
    read_markdown_tasks,
    read_routines,
)
from .models import DailyPlan, SourceItem
from .notion import (
    NotionClient,
    NotionError,
    day_plan_markdown,
    sync_plan_from_markdown,
)
from .storage import PlannerStorage


DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "tasks_source": "both",
    "routines_source": "both",
    "exercises_source": "both",
    "create_notion_day_page": True,
    "diction_categories": [
        "warmup",
        "syllables",
        "words",
        "tongue_twister",
        "reading",
        "free_speech",
    ],
    "diction_items_per_category": 1,
    "similarity_threshold": 94,
    "database_path": "data/morning_brief.db",
    "routines_path": "routines.json",
    "exercises_path": "diction_exercises.json",
}


def load_planner_config(path: Path) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return config
    if isinstance(value, dict):
        config.update(value)
    return config


def _merge_unique(*groups: list[SourceItem]) -> list[SourceItem]:
    result: list[SourceItem] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            key = normalize_text(f"{item.kind} {item.title}")
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)
    return result


class PlannerService:
    def __init__(
        self,
        base_dir: Path,
        planner_config: dict[str, Any] | None = None,
        notion: NotionClient | None = None,
    ):
        self.base_dir = base_dir
        self.config = planner_config or load_planner_config(
            base_dir / "planner_config.json"
        )
        database_path = base_dir / str(
            self.config.get("database_path") or "data/morning_brief.db"
        )
        self.storage = PlannerStorage(database_path)
        self.notion = notion or NotionClient()

    def prepare_day(self, today: date) -> DailyPlan:
        plan_date = today.isoformat()
        warnings: list[str] = []

        self._sync_previous_day(today, warnings)

        existing = self.storage.load_plan(plan_date)
        if existing is not None:
            existing.warnings.extend(
                message
                for message in warnings
                if message not in existing.warnings
            )
            self._ensure_notion_page(existing, warnings)
            existing.warnings.extend(
                message
                for message in warnings
                if message not in existing.warnings
            )
            self.storage.save_plan(existing)
            return existing

        tasks = self._load_tasks(today, warnings)
        routines = self._load_routines(today, warnings)
        exercises = self._load_exercises(warnings)
        diction = self._choose_diction(exercises, today)

        previous_completed, previous_total = self.storage.previous_day_summary(
            plan_date
        )
        plan = DailyPlan(
            date=plan_date,
            tasks=[item.to_plan_item() for item in tasks],
            routines=[item.to_plan_item() for item in routines],
            diction=[item.to_plan_item() for item in diction],
            previous_completed=previous_completed,
            previous_total=previous_total,
            warnings=warnings,
        )
        self.storage.save_plan(plan)
        for item in diction:
            self.storage.record_exercise_usage(item.id, plan_date)

        self._ensure_notion_page(plan, warnings)
        self.storage.save_plan(plan)
        return plan

    def _source_enabled(self, setting: str, source: str) -> bool:
        value = str(self.config.get(setting) or "both").lower()
        return value == "both" or value == source

    def _load_tasks(
        self,
        today: date,
        warnings: list[str],
    ) -> list[SourceItem]:
        local: list[SourceItem] = []
        notion: list[SourceItem] = []
        if self._source_enabled("tasks_source", "local"):
            local = read_markdown_tasks(self.base_dir / "tasks.md", today)
        if self._source_enabled("tasks_source", "notion") and self.notion.enabled:
            try:
                notion = self.notion.load_tasks(today)
            except NotionError as error:
                warnings.append(f"Notion-задачи недоступны: {error}")
        return _merge_unique(notion, local)

    def _load_routines(
        self,
        today: date,
        warnings: list[str],
    ) -> list[SourceItem]:
        local: list[SourceItem] = []
        notion: list[SourceItem] = []
        if self._source_enabled("routines_source", "local"):
            local = read_routines(
                self.base_dir
                / str(self.config.get("routines_path") or "routines.json"),
                today,
            )
        if self._source_enabled("routines_source", "notion") and self.notion.enabled:
            try:
                notion = self.notion.load_routines(today)
            except NotionError as error:
                warnings.append(f"Notion-привычки недоступны: {error}")
        return _merge_unique(notion, local)

    def _load_exercises(self, warnings: list[str]) -> list[SourceItem]:
        local: list[SourceItem] = []
        notion: list[SourceItem] = []
        if self._source_enabled("exercises_source", "local"):
            local = read_exercises(
                self.base_dir
                / str(
                    self.config.get("exercises_path")
                    or "diction_exercises.json"
                )
            )
        if (
            self._source_enabled("exercises_source", "notion")
            and self.notion.enabled
        ):
            try:
                notion = self.notion.load_exercises()
            except NotionError as error:
                warnings.append(f"Notion-упражнения недоступны: {error}")
        return deduplicate_items(
            _merge_unique(notion, local),
            threshold=float(self.config.get("similarity_threshold") or 94),
        )

    def _choose_diction(
        self,
        exercises: list[SourceItem],
        today: date,
    ) -> list[SourceItem]:
        categories = [
            str(item) for item in self.config.get("diction_categories", [])
        ]
        per_category = max(
            1,
            int(self.config.get("diction_items_per_category") or 1),
        )
        rng = random.Random(f"morning-brief:{today.isoformat()}")
        result: list[SourceItem] = []

        for category in categories:
            candidates = [
                item
                for item in exercises
                if normalize_text(item.category) == normalize_text(category)
            ]
            eligible: list[SourceItem] = []
            deferred: list[tuple[str, SourceItem]] = []
            for item in candidates:
                last_used = self.storage.get_exercise_last_used(item.id)
                if not last_used:
                    eligible.append(item)
                    continue
                try:
                    days_since = (
                        today - date.fromisoformat(last_used)
                    ).days
                except ValueError:
                    days_since = item.cooldown_days
                if days_since >= max(0, item.cooldown_days):
                    eligible.append(item)
                else:
                    deferred.append((last_used, item))

            rng.shuffle(eligible)
            selected = eligible[:per_category]
            if len(selected) < per_category:
                deferred.sort(key=lambda pair: pair[0])
                selected.extend(
                    item
                    for _last, item in deferred[
                        : per_category - len(selected)
                    ]
                )
            result.extend(selected)

        if not result and exercises:
            shuffled = list(exercises)
            rng.shuffle(shuffled)
            result = shuffled[: min(6, len(shuffled))]
        return result

    def _sync_previous_day(
        self,
        today: date,
        warnings: list[str],
    ) -> None:
        previous_date = (today - timedelta(days=1)).isoformat()
        previous = self.storage.load_plan(previous_date)
        if (
            previous is None
            or not previous.notion_page_id
            or not self.notion.enabled
        ):
            return
        try:
            markdown = self.notion.retrieve_page_markdown(
                previous.notion_page_id
            )
            sync_plan_from_markdown(previous, markdown)
            for item in previous.all_items():
                self.storage.set_completion(
                    previous.date,
                    item.id,
                    item.completed,
                    source="notion",
                )
            self.storage.save_plan(previous)
            self.notion.update_day_progress(
                previous.notion_page_id,
                previous,
            )
        except NotionError as error:
            warnings.append(
                f"Не удалось считать вчерашние отметки Notion: {error}"
            )

    def _ensure_notion_page(
        self,
        plan: DailyPlan,
        warnings: list[str],
    ) -> None:
        if not self.notion.enabled or not bool(
            self.config.get("create_notion_day_page", True)
        ):
            return
        try:
            page = self.notion.find_day_page(plan.date)
            if page is None:
                page = self.notion.create_day_page(
                    plan,
                    day_plan_markdown(plan),
                )
            else:
                markdown = self.notion.retrieve_page_markdown(
                    str(page.get("id") or "")
                )
                sync_plan_from_markdown(plan, markdown)
                for item in plan.all_items():
                    self.storage.set_completion(
                        plan.date,
                        item.id,
                        item.completed,
                        source="notion",
                    )
            plan.notion_page_id = str(page.get("id") or "")
            plan.notion_url = str(page.get("url") or "")
            self.storage.update_notion_page(
                plan.date,
                plan.notion_page_id,
                plan.notion_url,
            )
        except NotionError as error:
            message = f"Страница дня Notion не создана: {error}"
            if message not in warnings:
                warnings.append(message)

    def frontend_payload(self, plan: DailyPlan) -> dict[str, Any]:
        payload = plan.to_dict()
        payload["notion_enabled"] = self.notion.enabled
        payload["completion_mode"] = (
            "notion" if self.notion.enabled else "browser"
        )
        payload["sources"] = {
            "tasks": str(self.config.get("tasks_source") or "both"),
            "routines": str(self.config.get("routines_source") or "both"),
            "exercises": str(self.config.get("exercises_source") or "both"),
        }
        return payload

    def markdown_section(self, plan: DailyPlan) -> str:
        lines = ["", "## План дня", ""]
        for heading, items in [
            ("Одноразовые задачи", plan.tasks),
            ("Ежедневные действия", plan.routines),
            ("Дикция", plan.diction),
        ]:
            lines.extend([f"### {heading}", ""])
            if not items:
                lines.append("- нет")
            for item in items:
                suffix = f" — {item.details}" if item.details else ""
                lines.append(f"- [ ] {item.title}{suffix}")
            lines.append("")
        if plan.notion_url:
            lines.extend(
                [f"Страница дня в Notion: {plan.notion_url}", ""]
            )
        return "\n".join(lines)
