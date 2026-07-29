from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def status(ok: bool, label: str, detail: str = "") -> None:
    marker = "OK" if ok else "—"
    suffix = f": {detail}" if detail else ""
    print(f"[{marker}] {label}{suffix}")


def main() -> int:
    load_env(ROOT / ".env")

    status((ROOT / "planner_app.py").exists(), "planner_app.py")
    status((ROOT / "planner_config.json").exists(), "planner_config.json")
    status((ROOT / "routines.json").exists(), "routines.json")
    status((ROOT / "diction_exercises.json").exists(), "diction_exercises.json")
    status((ROOT / "frontend" / "dist" / "morning-summary.js").exists(), "frontend build")
    status(bool(os.environ.get("TELEGRAM_BOT_TOKEN")), "Telegram token")
    status(bool(os.environ.get("TELEGRAM_CHAT_ID")), "Telegram chat ID")

    notion_token = bool(os.environ.get("NOTION_TOKEN"))
    notion_ids = [
        os.environ.get("NOTION_TASKS_DATA_SOURCE_ID"),
        os.environ.get("NOTION_ROUTINES_DATA_SOURCE_ID"),
        os.environ.get("NOTION_EXERCISES_DATA_SOURCE_ID"),
        os.environ.get("NOTION_DAYS_DATA_SOURCE_ID"),
    ]
    status(notion_token, "Notion token")
    status(all(notion_ids), "Notion data sources")

    try:
        config = json.loads((ROOT / "planner_config.json").read_text(encoding="utf-8"))
        status(isinstance(config, dict), "Planner config JSON")
    except Exception as error:
        status(False, "Planner config JSON", str(error))
        return 1

    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    probe = data_dir / ".write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        status(True, "Database directory is writable")
    except OSError as error:
        status(False, "Database directory is writable", str(error))
        return 1

    print("")
    if notion_token and all(notion_ids):
        print("Проект готов к полной синхронизации с Notion.")
    else:
        print("Проект готов в локальном режиме. Для полной синхронизации запусти setup_notion.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
