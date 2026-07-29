from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as legacy_app

from morning_planner.local_sources import load_json_list, read_exercises
from morning_planner.notion import NotionClient, NotionError, NotionResources


def extract_notion_id(value: str) -> str:
    matches = re.findall(
        r"(?i)([0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        value,
    )
    if not matches:
        raise ValueError("Не удалось найти ID страницы Notion в ссылке или строке")
    raw = matches[-1].replace("-", "").lower()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def update_env_file(path: Path, values: dict[str, str]) -> None:
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    output: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith("#"):
            output.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)
    if output and output[-1].strip():
        output.append("")
    output.extend(f"{key}={value}" for key, value in remaining.items())
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def select_options(names: list[str]) -> dict[str, Any]:
    colors = ["gray", "blue", "green", "yellow", "orange", "red", "purple", "pink", "brown"]
    return {
        "options": [
            {"name": name, "color": colors[index % len(colors)]}
            for index, name in enumerate(names)
        ]
    }


def schemas() -> dict[str, tuple[str, str, dict[str, Any]]]:
    return {
        "tasks": (
            "Morning Brief — Задачи",
            "✅",
            {
                "Название": {"title": {}},
                "Статус": {"select": select_options(["Входящие", "Запланировано", "Выполнено", "Пропущено"])},
                "Дата": {"date": {}},
                "Приоритет": {"select": select_options(["Низкий", "Средний", "Высокий"])},
                "Категория": {"select": select_options(["IT", "Учёба", "Личное", "Здоровье", "Другое"])},
                "Минуты": {"number": {"format": "number"}},
                "В ближайший план": {"checkbox": {}},
                "Заметки": {"rich_text": {}},
            },
        ),
        "routines": (
            "Morning Brief — Регулярные действия",
            "🔁",
            {
                "Название": {"title": {}},
                "Активно": {"checkbox": {}},
                "Дни": {
                    "multi_select": select_options(
                        ["Ежедневно", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
                    )
                },
                "Категория": {"select": select_options(["Здоровье", "IT", "Учёба", "Отдых", "Личное"])},
                "Минуты": {"number": {"format": "number"}},
                "Обязательно": {"checkbox": {}},
                "Заметки": {"rich_text": {}},
            },
        ),
        "exercises": (
            "Morning Brief — Дикция",
            "🎙️",
            {
                "Название": {"title": {}},
                "Активно": {"checkbox": {}},
                "Тип": {
                    "select": select_options(
                        ["warmup", "syllables", "words", "tongue_twister", "reading", "free_speech"]
                    )
                },
                "Сложность": {"select": select_options(["easy", "medium", "hard"])},
                "Текст": {"rich_text": {}},
                "Повторения": {"number": {"format": "number"}},
                "Минуты": {"number": {"format": "number"}},
                "Пауза дней": {"number": {"format": "number"}},
                "Теги": {"multi_select": {"options": []}},
                "Заметки": {"rich_text": {}},
            },
        ),
        "days": (
            "Morning Brief — Дни",
            "☀️",
            {
                "Название": {"title": {}},
                "Дата": {"date": {}},
                "Статус": {"select": select_options(["Запланирован", "В процессе", "Выполнен"])},
                "Выполнено": {"number": {"format": "number"}},
                "Всего": {"number": {"format": "number"}},
                "Процент": {"number": {"format": "number"}},
                "Заметки": {"rich_text": {}},
            },
        ),
    }


def rich_text(value: str) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": value[:1900]}}]} if value else {"rich_text": []}


def existing_titles(client: NotionClient, data_source_id: str) -> set[str]:
    result: set[str] = set()
    for page in client.query_data_source(data_source_id):
        props = page.get("properties") if isinstance(page.get("properties"), dict) else {}
        title_prop = props.get("Название") or props.get("Name") or {}
        title_parts = title_prop.get("title") if isinstance(title_prop, dict) else []
        text = "".join(str(item.get("plain_text") or "") for item in title_parts or [] if isinstance(item, dict))
        if text:
            result.add(text.strip().lower())
    return result


def seed_local_data(client: NotionClient, resources: NotionResources) -> None:
    routines = load_json_list(ROOT / "routines.json")
    exercises = read_exercises(ROOT / "diction_exercises.json")

    routine_titles = existing_titles(client, resources.routines)
    for item in routines:
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title or title.lower() in routine_titles:
            continue
        days = [str(value) for value in item.get("days", [])] or ["Ежедневно"]
        client.request(
            "POST",
            "/pages",
            payload={
                "parent": {"data_source_id": resources.routines},
                "properties": {
                    "Название": {"title": [{"text": {"content": title}}]},
                    "Активно": {"checkbox": bool(item.get("active", True))},
                    "Дни": {"multi_select": [{"name": value} for value in days]},
                    "Категория": {"select": {"name": str(item.get("category") or "Личное")}},
                    "Минуты": {"number": int(item.get("duration_minutes") or 0)},
                    "Обязательно": {"checkbox": bool(item.get("mandatory", False))},
                    "Заметки": rich_text(str(item.get("details") or item.get("notes") or "")),
                },
            },
        )

    exercise_titles = existing_titles(client, resources.exercises)
    for item in exercises:
        if item.title.lower() in exercise_titles:
            continue
        client.request(
            "POST",
            "/pages",
            payload={
                "parent": {"data_source_id": resources.exercises},
                "properties": {
                    "Название": {"title": [{"text": {"content": item.title}}]},
                    "Активно": {"checkbox": True},
                    "Тип": {"select": {"name": item.category or "other"}},
                    "Сложность": {"select": {"name": item.difficulty or "medium"}},
                    "Текст": rich_text(item.details),
                    "Повторения": {"number": item.repetitions},
                    "Минуты": {"number": item.duration_minutes},
                    "Пауза дней": {"number": item.cooldown_days},
                    "Теги": {"multi_select": [{"name": tag} for tag in item.tags]},
                    "Заметки": rich_text(""),
                },
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Настройка Notion для Morning Brief")
    parser.add_argument("--parent", help="Ссылка или ID родительской страницы Notion")
    parser.add_argument("--no-seed", action="store_true", help="Не переносить локальные привычки и упражнения")
    args = parser.parse_args()

    legacy_app.load_env_file(ROOT / ".env")
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        print("Ошибка: добавь NOTION_TOKEN в .env и запусти скрипт снова.")
        return 1

    parent_value = (args.parent or os.environ.get("NOTION_PARENT_PAGE_ID") or "").strip()
    if not parent_value:
        parent_value = input("Вставь ссылку на пустую родительскую страницу Notion: ").strip()
    try:
        parent_page_id = extract_notion_id(parent_value)
    except ValueError as error:
        print(f"Ошибка: {error}")
        return 1

    client = NotionClient(token=token, resources=NotionResources())
    created: dict[str, str] = {}
    try:
        for key, (title, emoji, properties) in schemas().items():
            print(f"Создаю: {title}")
            _database_id, data_source_id = client.create_database(
                parent_page_id,
                title,
                properties,
                emoji,
            )
            created[key] = data_source_id
    except NotionError as error:
        print(f"Ошибка Notion: {error}")
        print("Проверь, что родительская страница расшарена интеграции и разрешены Read/Insert/Update content.")
        return 1

    env_values = {
        "NOTION_PARENT_PAGE_ID": parent_page_id,
        "NOTION_TASKS_DATA_SOURCE_ID": created["tasks"],
        "NOTION_ROUTINES_DATA_SOURCE_ID": created["routines"],
        "NOTION_EXERCISES_DATA_SOURCE_ID": created["exercises"],
        "NOTION_DAYS_DATA_SOURCE_ID": created["days"],
    }
    update_env_file(ROOT / ".env", env_values)

    resources = NotionResources(
        tasks=created["tasks"],
        routines=created["routines"],
        exercises=created["exercises"],
        days=created["days"],
    )
    if not args.no_seed:
        try:
            seed_local_data(NotionClient(token=token, resources=resources), resources)
            print("Локальные регулярные действия и упражнения перенесены в Notion.")
        except NotionError as error:
            print(f"Предупреждение: базы созданы, но начальные данные не перенесены: {error}")

    print("")
    print("Готово. ID источников данных записаны в .env.")
    print("Теперь запусти: .\\.venv\\Scripts\\python.exe planner_app.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
