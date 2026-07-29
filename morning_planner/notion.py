from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import requests

from .local_sources import normalize_text, routine_is_due, stable_id
from .models import DailyPlan, SourceItem


NOTION_API_VERSION = "2026-03-11"
NOTION_BASE_URL = "https://api.notion.com/v1"


class NotionError(RuntimeError):
    pass


def _plain_text(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(
        str(item.get("plain_text") or item.get("text", {}).get("content") or "")
        for item in items
        if isinstance(item, dict)
    ).strip()


def _property(properties: dict[str, Any], *names: str) -> dict[str, Any]:
    lowered = {str(key).lower(): value for key, value in properties.items()}
    for name in names:
        if name.lower() in lowered and isinstance(lowered[name.lower()], dict):
            return lowered[name.lower()]
    return {}


def prop_title(properties: dict[str, Any], *names: str) -> str:
    return _plain_text(_property(properties, *names).get("title"))


def prop_text(properties: dict[str, Any], *names: str) -> str:
    return _plain_text(_property(properties, *names).get("rich_text"))


def prop_select(properties: dict[str, Any], *names: str) -> str:
    value = _property(properties, *names).get("select")
    return str(value.get("name") or "") if isinstance(value, dict) else ""


def prop_multi_select(properties: dict[str, Any], *names: str) -> list[str]:
    value = _property(properties, *names).get("multi_select")
    if not isinstance(value, list):
        return []
    return [
        str(item.get("name") or "")
        for item in value
        if isinstance(item, dict) and item.get("name")
    ]


def prop_checkbox(
    properties: dict[str, Any],
    *names: str,
    default: bool = False,
) -> bool:
    value = _property(properties, *names)
    if "checkbox" not in value:
        return default
    return bool(value.get("checkbox"))


def prop_number(
    properties: dict[str, Any],
    *names: str,
    default: int = 0,
) -> int:
    value = _property(properties, *names).get("number")
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def prop_date(properties: dict[str, Any], *names: str) -> str:
    value = _property(properties, *names).get("date")
    return str(value.get("start") or "") if isinstance(value, dict) else ""


@dataclass(slots=True)
class NotionResources:
    tasks: str = ""
    routines: str = ""
    exercises: str = ""
    days: str = ""

    @property
    def complete(self) -> bool:
        return all([self.tasks, self.routines, self.exercises, self.days])


class NotionClient:
    def __init__(
        self,
        token: str | None = None,
        resources: NotionResources | None = None,
        timeout_seconds: int = 20,
    ):
        self.token = token or os.environ.get("NOTION_TOKEN", "")
        self.resources = resources or NotionResources(
            tasks=os.environ.get("NOTION_TASKS_DATA_SOURCE_ID", ""),
            routines=os.environ.get("NOTION_ROUTINES_DATA_SOURCE_ID", ""),
            exercises=os.environ.get("NOTION_EXERCISES_DATA_SOURCE_ID", ""),
            days=os.environ.get("NOTION_DAYS_DATA_SOURCE_ID", ""),
        )
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.resources.complete)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        retries: int = 3,
    ) -> dict[str, Any]:
        if not self.token:
            raise NotionError("NOTION_TOKEN не задан")
        url = f"{NOTION_BASE_URL}{path}"
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < retries:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                if not response.ok:
                    try:
                        message = response.json().get("message") or response.text
                    except ValueError:
                        message = response.text
                    raise NotionError(f"Notion API {response.status_code}: {message}")
                if not response.content:
                    return {}
                value = response.json()
                return value if isinstance(value, dict) else {}
            except (requests.RequestException, ValueError, NotionError) as error:
                last_error = error
                if isinstance(error, NotionError) or attempt + 1 >= retries:
                    break
                time.sleep(1.5 * (attempt + 1))
        raise NotionError(str(last_error or "Неизвестная ошибка Notion API"))

    def query_data_source(self, data_source_id: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor = ""
        while True:
            payload: dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            response = self.request(
                "POST",
                f"/data_sources/{data_source_id}/query",
                payload=payload,
            )
            results.extend(
                item
                for item in response.get("results", [])
                if isinstance(item, dict)
            )
            if not response.get("has_more"):
                return results
            cursor = str(response.get("next_cursor") or "")
            if not cursor:
                return results

    def load_tasks(self, today: date) -> list[SourceItem]:
        result: list[SourceItem] = []
        done_statuses = {
            "done",
            "completed",
            "готово",
            "выполнено",
            "пропущено",
            "skipped",
        }
        for page in self.query_data_source(self.resources.tasks):
            props = (
                page.get("properties")
                if isinstance(page.get("properties"), dict)
                else {}
            )
            title = prop_title(props, "Название", "Name")
            if not title:
                continue
            status = prop_select(props, "Статус", "Status").lower()
            if status in done_statuses:
                continue
            scheduled = prop_date(props, "Дата", "Date")
            include = prop_checkbox(
                props,
                "В ближайший план",
                "Include",
                default=not scheduled,
            )
            if scheduled:
                try:
                    if date.fromisoformat(scheduled[:10]) > today:
                        continue
                except ValueError:
                    pass
            elif not include:
                continue
            result.append(
                SourceItem(
                    id=stable_id(
                        "notion-task",
                        str(page.get("id") or title),
                    ),
                    title=title,
                    kind="task",
                    details=prop_text(props, "Заметки", "Notes"),
                    category=prop_select(props, "Категория", "Category")
                    or "Личное",
                    priority=prop_select(props, "Приоритет", "Priority")
                    or "medium",
                    duration_minutes=prop_number(props, "Минуты", "Duration"),
                    scheduled_date=scheduled,
                    source="notion",
                    source_page_id=str(page.get("id") or ""),
                )
            )
        return result

    def load_routines(self, today: date) -> list[SourceItem]:
        result: list[SourceItem] = []
        for page in self.query_data_source(self.resources.routines):
            props = (
                page.get("properties")
                if isinstance(page.get("properties"), dict)
                else {}
            )
            title = prop_title(props, "Название", "Name")
            if not title or not prop_checkbox(
                props,
                "Активно",
                "Active",
                default=True,
            ):
                continue
            days = prop_multi_select(props, "Дни", "Days")
            if not routine_is_due(days, today.weekday()):
                continue
            result.append(
                SourceItem(
                    id=stable_id(
                        "notion-routine",
                        str(page.get("id") or title),
                    ),
                    title=title,
                    kind="routine",
                    details=prop_text(props, "Заметки", "Notes"),
                    category=prop_select(props, "Категория", "Category")
                    or "Регулярное",
                    duration_minutes=prop_number(props, "Минуты", "Duration"),
                    days=days,
                    source="notion",
                    source_page_id=str(page.get("id") or ""),
                )
            )
        return result

    def load_exercises(self) -> list[SourceItem]:
        result: list[SourceItem] = []
        for page in self.query_data_source(self.resources.exercises):
            props = (
                page.get("properties")
                if isinstance(page.get("properties"), dict)
                else {}
            )
            title = prop_title(props, "Название", "Name")
            if not title or not prop_checkbox(
                props,
                "Активно",
                "Active",
                default=True,
            ):
                continue
            result.append(
                SourceItem(
                    id=stable_id(
                        "notion-exercise",
                        str(page.get("id") or title),
                    ),
                    title=title,
                    kind="diction",
                    details=prop_text(props, "Текст", "Text"),
                    category=prop_select(props, "Тип", "Type") or "other",
                    difficulty=prop_select(
                        props,
                        "Сложность",
                        "Difficulty",
                    )
                    or "medium",
                    duration_minutes=prop_number(props, "Минуты", "Duration"),
                    repetitions=prop_number(
                        props,
                        "Повторения",
                        "Repetitions",
                    ),
                    cooldown_days=prop_number(
                        props,
                        "Пауза дней",
                        "Cooldown",
                        default=3,
                    ),
                    tags=prop_multi_select(props, "Теги", "Tags"),
                    source="notion",
                    source_page_id=str(page.get("id") or ""),
                )
            )
        return result

    def find_day_page(self, plan_date: str) -> dict[str, Any] | None:
        for page in self.query_data_source(self.resources.days):
            props = (
                page.get("properties")
                if isinstance(page.get("properties"), dict)
                else {}
            )
            if prop_date(props, "Дата", "Date")[:10] == plan_date:
                return page
            if prop_title(props, "Название", "Name").endswith(plan_date):
                return page
        return None

    def create_day_page(self, plan: DailyPlan, markdown: str) -> dict[str, Any]:
        return self.request(
            "POST",
            "/pages",
            payload={
                "parent": {"data_source_id": self.resources.days},
                "properties": {
                    "Название": {
                        "title": [
                            {"text": {"content": f"План на {plan.date}"}}
                        ]
                    },
                    "Дата": {"date": {"start": plan.date}},
                    "Статус": {"select": {"name": "Запланирован"}},
                    "Выполнено": {"number": plan.completed_items},
                    "Всего": {"number": plan.total_items},
                    "Процент": {
                        "number": round(
                            plan.completed_items * 100 / plan.total_items,
                            1,
                        )
                        if plan.total_items
                        else 0
                    },
                },
                "markdown": markdown,
                "icon": {"type": "emoji", "emoji": "☀️"},
            },
        )

    def update_day_progress(self, page_id: str, plan: DailyPlan) -> None:
        self.request(
            "PATCH",
            f"/pages/{page_id}",
            payload={
                "properties": {
                    "Статус": {
                        "select": {
                            "name": "Выполнен"
                            if plan.completed_items == plan.total_items
                            and plan.total_items
                            else "В процессе"
                        }
                    },
                    "Выполнено": {"number": plan.completed_items},
                    "Всего": {"number": plan.total_items},
                    "Процент": {
                        "number": round(
                            plan.completed_items * 100 / plan.total_items,
                            1,
                        )
                        if plan.total_items
                        else 0
                    },
                }
            },
        )

    def retrieve_page_markdown(self, page_id: str) -> str:
        response = self.request("GET", f"/pages/{page_id}/markdown")
        return str(response.get("markdown") or "")

    def replace_page_markdown(self, page_id: str, markdown: str) -> None:
        self.request(
            "PATCH",
            f"/pages/{page_id}/markdown",
            payload={
                "type": "replace_content",
                "replace_content": {
                    "new_str": markdown,
                    "allow_deleting_content": False,
                },
            },
        )

    def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties: dict[str, Any],
        emoji: str,
    ) -> tuple[str, str]:
        database = self.request(
            "POST",
            "/databases",
            payload={
                "parent": {
                    "type": "page_id",
                    "page_id": parent_page_id,
                },
                "title": [
                    {
                        "type": "text",
                        "text": {"content": title},
                    }
                ],
                "is_inline": False,
                "icon": {"type": "emoji", "emoji": emoji},
                "initial_data_source": {"properties": properties},
            },
        )
        database_id = str(database.get("id") or "")
        if not database_id:
            raise NotionError(f"Notion не вернул ID базы «{title}»")
        details = self.request("GET", f"/databases/{database_id}")
        data_sources = details.get("data_sources")
        if not isinstance(data_sources, list) or not data_sources:
            raise NotionError(f"У базы «{title}» не найден источник данных")
        data_source_id = str(data_sources[0].get("id") or "")
        if not data_source_id:
            raise NotionError(
                f"Notion не вернул data source ID для «{title}»"
            )
        return database_id, data_source_id


def checked_titles_from_markdown(markdown: str) -> set[str]:
    result: set[str] = set()
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("- [x]"):
            title = stripped[5:].strip()
            if title:
                result.add(normalize_text(title))
    return result


def sync_plan_from_markdown(plan: DailyPlan, markdown: str) -> DailyPlan:
    checked = checked_titles_from_markdown(markdown)
    for item in plan.all_items():
        item.completed = normalize_text(item.title) in checked
    return plan


def day_plan_markdown(plan: DailyPlan) -> str:
    lines = [
        f"# План на {plan.date}",
        "",
        "Отмечай выполненные пункты прямо здесь. На следующем запуске Morning Brief сохранит результат.",
        "",
        "## Одноразовые задачи",
        "",
    ]
    if plan.tasks:
        lines.extend(
            f"- [{'x' if item.completed else ' '}] {item.title}"
            for item in plan.tasks
        )
    else:
        lines.append("Одноразовых задач нет.")
    lines.extend(["", "## Ежедневные действия", ""])
    if plan.routines:
        lines.extend(
            f"- [{'x' if item.completed else ' '}] {item.title}"
            for item in plan.routines
        )
    else:
        lines.append("Регулярных действий на сегодня нет.")
    lines.extend(["", "## Дикция", ""])
    for item in plan.diction:
        lines.append(f"- [{'x' if item.completed else ' '}] {item.title}")
        if item.details:
            lines.append(f"  - {item.details}")
    if not plan.diction:
        lines.append("Упражнения не подобраны.")
    lines.extend(
        [
            "",
            "---",
            "",
            f"Плановая длительность: {plan.duration_minutes} мин.",
            "Источник истины для галочек: эта страница Notion.",
        ]
    )
    return "\n".join(lines)
