from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import app as legacy_app

from morning_planner.service import PlannerService, load_planner_config


def build_planner_summary() -> tuple[
    legacy_app.SummaryData,
    dict[str, Any],
    Path,
    Path,
]:
    base_dir = Path(__file__).resolve().parent
    legacy_app.load_env_file(base_dir / ".env")
    config = legacy_app.load_config(base_dir / "config.json")
    planner_config = load_planner_config(base_dir / "planner_config.json")

    if not legacy_app.config_enabled(
        planner_config.get("enabled"),
        default=True,
    ):
        output_dir = base_dir / str(config.get("output_dir", "output"))
        output_dir.mkdir(parents=True, exist_ok=True)
        return (
            legacy_app.build_summary(base_dir, output_dir, config),
            config,
            base_dir,
            output_dir,
        )

    service = PlannerService(base_dir, planner_config=planner_config)
    today = legacy_app.today_for_config_timezone(config)
    plan = service.prepare_day(today)

    original_build_brief_data = legacy_app.build_brief_data

    def enhanced_build_brief_data(
        summary: legacy_app.SummaryData,
        brief_config: dict[str, Any],
        render_base_dir: Path | None = None,
    ) -> dict[str, Any]:
        data = original_build_brief_data(
            summary,
            brief_config,
            render_base_dir,
        )
        data["planner"] = service.frontend_payload(plan)
        return data

    legacy_app.build_brief_data = enhanced_build_brief_data

    original_caption = legacy_app.build_telegram_caption

    def enhanced_caption(
        caption_config: dict[str, Any],
        caption_summary: legacy_app.SummaryData,
    ) -> str:
        caption = original_caption(caption_config, caption_summary)
        diction_minutes = sum(
            item.duration_minutes for item in plan.diction
        )
        caption += (
            f" · план: {plan.total_items}"
            f" · дикция: {diction_minutes} мин"
        )
        if plan.notion_url:
            caption += f" · {plan.notion_url}"
        return caption[:1024]

    legacy_app.build_telegram_caption = enhanced_caption

    output_dir = base_dir / str(config.get("output_dir", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = legacy_app.build_summary(base_dir, output_dir, config)
    summary.markdown = (
        summary.markdown.rstrip()
        + "\n"
        + service.markdown_section(plan)
    )
    summary.html = legacy_app.render_summary_html(summary, config, base_dir)
    return summary, config, base_dir, output_dir


def main() -> None:
    summary, config, base_dir, output_dir = build_planner_summary()
    output_path = output_dir / f"{summary.date_text}.md"
    html_output_path = output_dir / f"{summary.date_text}.html"
    output_path.write_text(summary.markdown, encoding="utf-8")
    html_output_path.write_text(summary.html, encoding="utf-8")

    print(f"Создан файл: {output_path}")
    print(f"Создан файл: {html_output_path}")
    print(f"Открывайте локальную версию: {html_output_path.resolve()}")
    print(
        "Morning Planner: задачи, регулярные действия и дикция "
        "добавлены в сводку."
    )

    warning = legacy_app.frontend_build_warning(base_dir)
    if warning:
        print(warning)

    legacy_app.send_telegram_summary(
        config,
        summary,
        output_path.resolve(),
    )
    if legacy_app.config_enabled(
        config.get("send_windows_notification"),
        default=True,
    ):
        legacy_app.send_clickable_notification(
            legacy_app.select_full_summary_file(output_path).resolve()
        )


if __name__ == "__main__":
    if len(sys.argv) in {3, 4} and sys.argv[1] == "--toast-worker":
        status_path = Path(sys.argv[3]) if len(sys.argv) == 4 else None
        legacy_app.show_clickable_notification(sys.argv[2], status_path)
    else:
        main()
