from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_list(path: Path) -> list[dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return value if isinstance(value, list) else []


def save_list(path: Path, value: list[dict]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_task(args: argparse.Namespace) -> None:
    metadata = []
    if args.date:
        metadata.append(f"date:{args.date}")
    if args.priority:
        metadata.append(f"priority:{args.priority}")
    if args.category:
        metadata.append(f"category:{args.category}")
    if args.duration:
        metadata.append(f"duration:{args.duration}")
    suffix = f" | {' | '.join(metadata)}" if metadata else ""
    with (ROOT / "tasks.md").open("a", encoding="utf-8") as file:
        file.write(f"\n- [ ] {args.title}{suffix}\n")
    print("Задача добавлена в tasks.md")


def add_routine(args: argparse.Namespace) -> None:
    path = ROOT / "routines.json"
    values = load_list(path)
    values.append(
        {
            "title": args.title,
            "active": True,
            "days": [item.strip() for item in args.days.split(",") if item.strip()],
            "category": args.category,
            "duration_minutes": args.duration,
            "details": args.details,
        }
    )
    save_list(path, values)
    print("Регулярное действие добавлено в routines.json")


def add_exercise(args: argparse.Namespace) -> None:
    path = ROOT / "diction_exercises.json"
    values = load_list(path)
    values.append(
        {
            "title": args.title,
            "active": True,
            "type": args.type,
            "difficulty": args.difficulty,
            "text": args.text,
            "repetitions": args.repetitions,
            "duration_minutes": args.duration,
            "cooldown_days": args.cooldown,
            "tags": [item.strip() for item in args.tags.split(",") if item.strip()],
        }
    )
    save_list(path, values)
    print("Упражнение добавлено в diction_exercises.json")


def planner_storage():
    from morning_planner.service import load_planner_config
    from morning_planner.storage import PlannerStorage

    config = load_planner_config(ROOT / "planner_config.json")
    return PlannerStorage(ROOT / str(config.get("database_path") or "data/morning_brief.db"))


def show_day(args: argparse.Namespace) -> None:
    day = args.date or date.today().isoformat()
    plan = planner_storage().load_plan(day)
    if plan is None:
        print(f"План на {day} ещё не создан.")
        return
    print(f"План на {day}: {plan.completed_items}/{plan.total_items}, {plan.duration_minutes} мин")
    for heading, items in [("Задачи", plan.tasks), ("Регулярные", plan.routines), ("Дикция", plan.diction)]:
        print(f"\n{heading}:")
        if not items:
            print("  — нет")
        for item in items:
            marker = "x" if item.completed else " "
            print(f"  [{marker}] {item.title}")
    if plan.notion_url:
        print(f"\nNotion: {plan.notion_url}")


def reset_day(args: argparse.Namespace) -> None:
    day = args.date or date.today().isoformat()
    if not args.yes:
        confirmation = input(f"Удалить сохранённый план на {day} и пересоздать его при следующем запуске? [y/N] ").strip().lower()
        if confirmation not in {"y", "yes", "д", "да"}:
            print("Отменено.")
            return
    deleted = planner_storage().delete_plan(day)
    print("План удалён." if deleted else "План на эту дату не найден.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Локальное управление Morning Brief")
    subparsers = parser.add_subparsers(dest="command", required=True)

    task = subparsers.add_parser("add-task")
    task.add_argument("title")
    task.add_argument("--date", default="")
    task.add_argument("--priority", default="medium")
    task.add_argument("--category", default="Личное")
    task.add_argument("--duration", type=int, default=0)
    task.set_defaults(handler=add_task)

    routine = subparsers.add_parser("add-routine")
    routine.add_argument("title")
    routine.add_argument("--days", default="Ежедневно")
    routine.add_argument("--category", default="Личное")
    routine.add_argument("--duration", type=int, default=0)
    routine.add_argument("--details", default="")
    routine.set_defaults(handler=add_routine)

    exercise = subparsers.add_parser("add-exercise")
    exercise.add_argument("title")
    exercise.add_argument("--type", default="words")
    exercise.add_argument("--difficulty", default="medium")
    exercise.add_argument("--text", default="")
    exercise.add_argument("--repetitions", type=int, default=3)
    exercise.add_argument("--duration", type=int, default=3)
    exercise.add_argument("--cooldown", type=int, default=4)
    exercise.add_argument("--tags", default="")
    exercise.set_defaults(handler=add_exercise)

    show = subparsers.add_parser("show-day")
    show.add_argument("--date", default="")
    show.set_defaults(handler=show_day)

    reset = subparsers.add_parser("reset-day")
    reset.add_argument("--date", default="")
    reset.add_argument("--yes", action="store_true")
    reset.set_defaults(handler=reset_day)

    args = parser.parse_args()
    args.handler(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
