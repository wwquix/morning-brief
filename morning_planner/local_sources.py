from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from .models import SourceItem

try:
    from rapidfuzz.fuzz import ratio as rapid_ratio
except ImportError:  # pragma: no cover - fallback keeps the project usable
    rapid_ratio = None


DAY_ALIASES = {
    0: {"mon", "monday", "пн", "понедельник"},
    1: {"tue", "tuesday", "вт", "вторник"},
    2: {"wed", "wednesday", "ср", "среда"},
    3: {"thu", "thursday", "чт", "четверг"},
    4: {"fri", "friday", "пт", "пятница"},
    5: {"sat", "saturday", "сб", "суббота"},
    6: {"sun", "sunday", "вс", "воскресенье"},
}


def normalize_text(value: str) -> str:
    value = value.lower().replace("ё", "е")
    value = re.sub(r"[^\w\s]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def similarity(left: str, right: str) -> float:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm and not right_norm:
        return 100.0
    if rapid_ratio is not None:
        return float(rapid_ratio(left_norm, right_norm))
    return SequenceMatcher(None, left_norm, right_norm).ratio() * 100


def deduplicate_items(
    items: Iterable[SourceItem],
    threshold: float = 94.0,
) -> list[SourceItem]:
    result: list[SourceItem] = []
    for item in items:
        if any(similarity(item.details or item.title, current.details or current.title) >= threshold for current in result):
            continue
        result.append(item)
    return result


def _metadata_value(parts: list[str], key: str, default: str = "") -> str:
    prefix = f"{key.lower()}:"
    for part in parts:
        if part.strip().lower().startswith(prefix):
            return part.split(":", 1)[1].strip()
    return default


def read_markdown_tasks(path: Path, today: date) -> list[SourceItem]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    result: list[SourceItem] = []
    for line in lines:
        stripped = line.strip()
        if not (stripped.startswith("- [ ]") or stripped.startswith("* [ ]")):
            continue
        raw = stripped[5:].strip()
        if not raw:
            continue
        parts = [part.strip() for part in raw.split("|")]
        title = parts[0]
        scheduled_date = _metadata_value(parts[1:], "date")
        include = _metadata_value(parts[1:], "include", "yes").lower()
        if scheduled_date:
            try:
                task_date = date.fromisoformat(scheduled_date)
            except ValueError:
                task_date = today
            if task_date > today:
                continue
        if include in {"no", "false", "0", "off"}:
            continue
        duration = _metadata_value(parts[1:], "duration", "0")
        try:
            duration_minutes = int(duration)
        except ValueError:
            duration_minutes = 0
        result.append(
            SourceItem(
                id=stable_id("task", title),
                title=title,
                kind="task",
                category=_metadata_value(parts[1:], "category", "Личное"),
                priority=_metadata_value(parts[1:], "priority", "medium"),
                duration_minutes=duration_minutes,
                scheduled_date=scheduled_date,
                source="tasks.md",
            )
        )
    return result


def load_json_list(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return value if isinstance(value, list) else []


def routine_is_due(days: list[str], weekday: int) -> bool:
    if not days:
        return True
    normalized = {normalize_text(day) for day in days}
    if normalized & {"daily", "everyday", "ежедневно", "каждый день"}:
        return True
    return bool(normalized & DAY_ALIASES[weekday])


def read_routines(path: Path, today: date) -> list[SourceItem]:
    result: list[SourceItem] = []
    for row in load_json_list(path):
        title = str(row.get("title") or row.get("name") or "").strip()
        if not title or not bool(row.get("active", True)):
            continue
        days = [str(item) for item in row.get("days", [])]
        if not routine_is_due(days, today.weekday()):
            continue
        result.append(
            SourceItem(
                id=str(row.get("id") or stable_id("routine", title)),
                title=title,
                kind="routine",
                details=str(row.get("details") or row.get("notes") or ""),
                category=str(row.get("category") or "Регулярное"),
                duration_minutes=int(row.get("duration_minutes") or 0),
                active=True,
                days=days,
                source="routines.json",
            )
        )
    return result


def read_exercises(path: Path) -> list[SourceItem]:
    result: list[SourceItem] = []
    for row in load_json_list(path):
        title = str(row.get("title") or row.get("name") or "").strip()
        text = str(row.get("text") or row.get("details") or "").strip()
        if not title or not bool(row.get("active", True)):
            continue
        result.append(
            SourceItem(
                id=str(row.get("id") or stable_id("exercise", f"{title} {text}")),
                title=title,
                kind="diction",
                details=text,
                category=str(row.get("type") or row.get("category") or "other"),
                difficulty=str(row.get("difficulty") or "medium"),
                duration_minutes=int(row.get("duration_minutes") or 0),
                repetitions=int(row.get("repetitions") or 0),
                cooldown_days=int(row.get("cooldown_days") or 3),
                tags=[str(item) for item in row.get("tags", [])],
                source="diction_exercises.json",
            )
        )
    return deduplicate_items(result)
