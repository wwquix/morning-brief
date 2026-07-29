from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class SourceItem:
    id: str
    title: str
    kind: str
    details: str = ""
    category: str = ""
    difficulty: str = ""
    duration_minutes: int = 0
    repetitions: int = 0
    cooldown_days: int = 0
    active: bool = True
    scheduled_date: str = ""
    priority: str = ""
    days: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: str = "local"
    source_page_id: str = ""

    def to_plan_item(self) -> "PlanItem":
        return PlanItem(
            id=self.id,
            title=self.title,
            kind=self.kind,
            details=self.details,
            category=self.category,
            difficulty=self.difficulty,
            duration_minutes=self.duration_minutes,
            repetitions=self.repetitions,
            priority=self.priority,
            source=self.source,
            source_id=self.source_page_id or self.id,
        )


@dataclass(slots=True)
class PlanItem:
    id: str
    title: str
    kind: str
    details: str = ""
    category: str = ""
    difficulty: str = ""
    duration_minutes: int = 0
    repetitions: int = 0
    priority: str = ""
    source: str = "local"
    source_id: str = ""
    completed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PlanItem":
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: value[key] for key in allowed if key in value})


@dataclass(slots=True)
class DailyPlan:
    date: str
    tasks: list[PlanItem] = field(default_factory=list)
    routines: list[PlanItem] = field(default_factory=list)
    diction: list[PlanItem] = field(default_factory=list)
    notion_page_id: str = ""
    notion_url: str = ""
    previous_completed: int = 0
    previous_total: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        return len(self.tasks) + len(self.routines) + len(self.diction)

    @property
    def completed_items(self) -> int:
        return sum(
            item.completed
            for item in [*self.tasks, *self.routines, *self.diction]
        )

    @property
    def duration_minutes(self) -> int:
        return sum(
            max(0, int(item.duration_minutes or 0))
            for item in [*self.tasks, *self.routines, *self.diction]
        )

    def all_items(self) -> list[PlanItem]:
        return [*self.tasks, *self.routines, *self.diction]

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "tasks": [item.to_dict() for item in self.tasks],
            "routines": [item.to_dict() for item in self.routines],
            "diction": [item.to_dict() for item in self.diction],
            "notion_page_id": self.notion_page_id,
            "notion_url": self.notion_url,
            "previous_completed": self.previous_completed,
            "previous_total": self.previous_total,
            "warnings": list(self.warnings),
            "stats": {
                "total": self.total_items,
                "completed": self.completed_items,
                "duration_minutes": self.duration_minutes,
            },
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DailyPlan":
        return cls(
            date=str(value.get("date") or date.today().isoformat()),
            tasks=[PlanItem.from_dict(item) for item in value.get("tasks", [])],
            routines=[PlanItem.from_dict(item) for item in value.get("routines", [])],
            diction=[PlanItem.from_dict(item) for item in value.get("diction", [])],
            notion_page_id=str(value.get("notion_page_id") or ""),
            notion_url=str(value.get("notion_url") or ""),
            previous_completed=int(value.get("previous_completed") or 0),
            previous_total=int(value.get("previous_total") or 0),
            warnings=[str(item) for item in value.get("warnings", [])],
        )
