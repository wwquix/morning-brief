from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from morning_planner.local_sources import (
    deduplicate_items,
    normalize_text,
    read_markdown_tasks,
    routine_is_due,
    similarity,
)
from morning_planner.models import SourceItem
from morning_planner.service import PlannerService
from morning_planner.storage import PlannerStorage


def write_config(root: Path) -> dict:
    config = {
        "enabled": True,
        "tasks_source": "local",
        "routines_source": "local",
        "exercises_source": "local",
        "create_notion_day_page": False,
        "diction_categories": ["warmup", "words"],
        "diction_items_per_category": 1,
        "database_path": "data/test.db",
        "routines_path": "routines.json",
        "exercises_path": "diction_exercises.json",
    }
    (root / "planner_config.json").write_text(json.dumps(config), encoding="utf-8")
    return config


def test_normalize_and_similarity() -> None:
    assert normalize_text("Интервьюер, интервьюера!") == "интервьюер интервьюера"
    assert similarity("Прочитай текст медленно", "Медленно прочитай текст") > 60


def test_deduplicate_items() -> None:
    items = [
        SourceItem(id="1", title="A", kind="diction", details="Интервьюер интервьюировал"),
        SourceItem(id="2", title="B", kind="diction", details="интервьюер, интервьюировал!"),
    ]
    assert len(deduplicate_items(items, threshold=90)) == 1


def test_markdown_tasks_support_metadata(tmp_path: Path) -> None:
    path = tmp_path / "tasks.md"
    path.write_text(
        "- [ ] Сделать API | date:2026-07-29 | priority:high | category:IT | duration:45\n"
        "- [x] Уже готово\n"
        "- [ ] Будущее | date:2099-01-01\n",
        encoding="utf-8",
    )
    tasks = read_markdown_tasks(path, date(2026, 7, 29))
    assert [task.title for task in tasks] == ["Сделать API"]
    assert tasks[0].duration_minutes == 45


def test_routine_days() -> None:
    assert routine_is_due(["Ежедневно"], 0)
    assert routine_is_due(["Пн", "Ср"], 2)
    assert not routine_is_due(["Пн"], 1)


def test_storage_persists_plan(tmp_path: Path) -> None:
    storage = PlannerStorage(tmp_path / "planner.db")
    from morning_planner.models import DailyPlan, PlanItem

    plan = DailyPlan(
        date="2026-07-29",
        tasks=[PlanItem(id="task-1", title="Задача", kind="task")],
    )
    storage.save_plan(plan)
    storage.set_completion(plan.date, "task-1", True)
    loaded = storage.load_plan(plan.date)
    assert loaded is not None
    assert loaded.tasks[0].completed is True
    assert storage.delete_plan(plan.date) is True
    assert storage.load_plan(plan.date) is None


def test_daily_plan_is_stable_and_respects_cooldown(tmp_path: Path) -> None:
    config = write_config(tmp_path)
    (tmp_path / "tasks.md").write_text("- [ ] Задача\n", encoding="utf-8")
    (tmp_path / "routines.json").write_text(
        json.dumps(
            [{"id": "r1", "title": "Зарядка", "active": True, "days": ["Ежедневно"]}]
        ),
        encoding="utf-8",
    )
    (tmp_path / "diction_exercises.json").write_text(
        json.dumps(
            [
                {
                    "id": "w1",
                    "title": "Разминка 1",
                    "type": "warmup",
                    "active": True,
                    "cooldown_days": 10,
                },
                {
                    "id": "w2",
                    "title": "Разминка 2",
                    "type": "warmup",
                    "active": True,
                    "cooldown_days": 10,
                },
                {
                    "id": "word1",
                    "title": "Слова 1",
                    "type": "words",
                    "active": True,
                    "cooldown_days": 10,
                },
            ]
        ),
        encoding="utf-8",
    )

    service = PlannerService(tmp_path, planner_config=config)
    first = service.prepare_day(date(2026, 7, 29))
    second = service.prepare_day(date(2026, 7, 29))
    assert [item.id for item in first.diction] == [item.id for item in second.diction]
    assert len(first.tasks) == 1
    assert len(first.routines) == 1
    assert len(first.diction) == 2

    next_day = service.prepare_day(date(2026, 7, 30))
    assert next_day.diction
    assert next_day.date == "2026-07-30"
