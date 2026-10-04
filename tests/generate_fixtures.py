"""Generate deterministic standalone HTML for browser tests; never notify services."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app  # noqa: E402


def main():
    output = ROOT / "output" / "test-fixtures"
    output.mkdir(parents=True, exist_ok=True)
    config = app.load_config(ROOT / "config.json")
    config.update(send_telegram=False, send_windows_notification=False)
    with patch.object(app, "get_json", return_value=None):
        offline = app.build_summary(ROOT, output, config)
    (output / "offline.html").write_text(offline.html, encoding="utf-8")

    image = ROOT / "frontend/public/hero-bg.jpg"
    cats = [app.CatImage("", "", image) for _ in range(3)]
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        (base / "tasks.md").write_text(
            "- [ ] Проверить сводку\n- [x] Уже выполнено\n- [ ] " + "ДлиннаяЗадача" * 40
            + '\n- [ ] </script><script>window.__injected=true</script>\n', encoding="utf-8"
        )
        with patch.object(app, "fetch_holidays", return_value=app.HolidayReport("- Тестовый праздник", "Тестовый праздник")), patch.object(app, "fetch_weather", return_value=app.WeatherReport("- Ветер: 9 km/h", "24 °C", "ясно")), patch.object(app, "fetch_cat_images", return_value=cats):
            summary = app.build_summary(base, output, config)
        summary.html = app.render_summary_html(summary, config, ROOT)
        (output / "populated.html").write_text(summary.html, encoding="utf-8")
        (output / "fallback.html").write_text(app.render_summary_html(summary, config), encoding="utf-8")
        (base / "tasks.md").unlink()
        with patch.object(app, "get_json", return_value=None):
            missing = app.build_summary(base, output, config)
        (output / "missing-tasks.html").write_text(app.render_summary_html(missing, config, ROOT), encoding="utf-8")
    (output / "data.json").write_text(json.dumps(app.build_brief_data(summary, config, ROOT), ensure_ascii=False), encoding="utf-8")
    print(f"Fixtures: {output}")


if __name__ == "__main__":
    main()
