from __future__ import annotations

import base64
import html
import json
import mimetypes
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests


REQUEST_TIMEOUT_SECONDS = 10
TELEGRAM_UPLOAD_TIMEOUT_SECONDS = 30
NOTIFICATION_STARTUP_TIMEOUT_SECONDS = 5
NOTIFICATION_WORKER_TIMEOUT_SECONDS = 120
DATA_ERROR = "не удалось получить данные"
CATS_ERROR = "не удалось получить котов"
WEEKDAYS_RU = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]
TOAST_XML = """
<toast activationType="foreground" launch="open-summary" scenario="{scenario}">
    <visual>
        <binding template='ToastGeneric'></binding>
    </visual>
</toast>
"""


@dataclass
class WeatherReport:
    markdown: str
    temperature: str
    description: str


@dataclass
class HolidayReport:
    markdown: str
    summary: str


@dataclass
class CatImage:
    url: str
    src: str
    local_path: Path | None = None


@dataclass
class SummaryData:
    date_text: str
    markdown: str
    html: str
    weather: WeatherReport
    holidays: HolidayReport
    cats: list[CatImage] | str
    pending_tasks: list[str]


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_env_file(env_path: Path) -> None:
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        if stripped.lower().startswith("export "):
            stripped = stripped[7:].strip()

        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ[key] = value


def today_for_config_timezone(config: dict[str, Any]):
    timezone_name = str(config.get("timezone") or "UTC")
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception:
        return datetime.now().date()

    return datetime.now(timezone).date()


def get_json(url: str, params: dict[str, Any] | None = None) -> Any | None:
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def weather_code_to_russian(weather_code: Any) -> str:
    try:
        code = int(weather_code)
    except (TypeError, ValueError):
        return "неизвестно"

    if code == 0:
        return "ясно"
    if code in {1, 2}:
        return "переменная облачность"
    if code == 3:
        return "облачно"
    if code in {45, 48}:
        return "туман"
    if code in {51, 53, 55, 56, 57}:
        return "морось"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "дождь"
    if code in {71, 73, 75, 77, 85, 86}:
        return "снег"
    if code in {95, 96, 99}:
        return "гроза"

    return "неизвестно"


def format_value(value: Any, unit: str = "") -> str:
    if value is None:
        return DATA_ERROR
    if isinstance(value, float):
        value = f"{value:g}"

    return f"{value} {unit}".strip()


def fetch_weather(config: dict[str, Any]) -> WeatherReport:
    params = {
        "latitude": config.get("latitude"),
        "longitude": config.get("longitude"),
        "current": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "precipitation",
                "rain",
                "weather_code",
                "wind_speed_10m",
            ]
        ),
        "timezone": config.get("timezone", "UTC"),
        "forecast_days": 1,
    }
    data = get_json("https://api.open-meteo.com/v1/forecast", params=params)
    if not isinstance(data, dict) or not isinstance(data.get("current"), dict):
        return WeatherReport(DATA_ERROR, DATA_ERROR, DATA_ERROR)

    current = data["current"]
    units = data.get("current_units") if isinstance(data.get("current_units"), dict) else {}
    temperature = format_value(current.get("temperature_2m"), units.get("temperature_2m", ""))
    description = weather_code_to_russian(current.get("weather_code"))

    lines = [
        f"- Город: {config.get('city_name', DATA_ERROR)}",
        f"- Температура: {temperature}",
    ]

    if current.get("apparent_temperature") is not None:
        lines.append(
            f"- Ощущается как: {format_value(current.get('apparent_temperature'), units.get('apparent_temperature', ''))}"
        )

    if current.get("precipitation") is not None:
        lines.append(
            f"- Осадки: {format_value(current.get('precipitation'), units.get('precipitation', ''))}"
        )

    if current.get("rain") is not None:
        lines.append(f"- Дождь: {format_value(current.get('rain'), units.get('rain', ''))}")

    lines.extend(
        [
            f"- Ветер: {format_value(current.get('wind_speed_10m'), units.get('wind_speed_10m', ''))}",
            f"- Описание: {description}",
        ]
    )

    return WeatherReport("\n".join(lines), temperature, description)


def fetch_holidays(config: dict[str, Any], today) -> HolidayReport:
    country_code = str(config.get("country_code", "")).upper()
    if not country_code:
        return HolidayReport(DATA_ERROR, DATA_ERROR)

    url = f"https://date.nager.at/api/v3/PublicHolidays/{today.year}/{country_code}"
    data = get_json(url)
    if not isinstance(data, list):
        return HolidayReport(DATA_ERROR, DATA_ERROR)

    todays_holidays = [
        holiday
        for holiday in data
        if isinstance(holiday, dict) and holiday.get("date") == today.isoformat()
    ]
    if not todays_holidays:
        return HolidayReport("официальных праздников сегодня нет", "праздников нет")

    names = []
    for holiday in todays_holidays:
        local_name = holiday.get("localName")
        english_name = holiday.get("name")
        if local_name and english_name and local_name != english_name:
            names.append(f"{local_name} ({english_name})")
        elif local_name or english_name:
            names.append(str(local_name or english_name))

    if not names:
        return HolidayReport(DATA_ERROR, DATA_ERROR)

    return HolidayReport("\n".join(f"- {name}" for name in names), ", ".join(names))


def fetch_cat_image_urls(config: dict[str, Any]) -> list[str] | str:
    count = int(config.get("cat_images_count", 2))
    data = get_json(
        "https://api.thecatapi.com/v1/images/search",
        params={"limit": count, "order": "RANDOM"},
    )
    if not isinstance(data, list):
        return CATS_ERROR

    urls = [
        item.get("url")
        for item in data
        if isinstance(item, dict) and isinstance(item.get("url"), str)
    ]
    if len(urls) < count:
        return CATS_ERROR

    return urls[:count]


def image_extension_from_response(response: requests.Response, url: str) -> str:
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
    if content_type in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    if content_type == "image/gif":
        return ".gif"
    if content_type == "image/webp":
        return ".webp"

    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix

    return ".jpg"


def download_cat_image(url: str, cats_dir: Path, date_text: str, index: int) -> CatImage:
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"Cache-Control": "no-cache"},
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if not content_type.startswith("image/"):
            raise ValueError("ответ не является изображением")

        cats_dir.mkdir(parents=True, exist_ok=True)
        extension = image_extension_from_response(response, url)
        filename = f"{date_text}-{index}-{int(time.time() * 1000)}{extension}"
        local_path = cats_dir / filename
        local_path.write_bytes(response.content)

        return CatImage(url=url, src=f"cats/{filename}", local_path=local_path)
    except Exception:
        return CatImage(url=url, src=url, local_path=None)


def fetch_cat_images(config: dict[str, Any], output_dir: Path, date_text: str) -> list[CatImage] | str:
    urls = fetch_cat_image_urls(config)
    if isinstance(urls, str):
        return urls

    cats_dir = output_dir / "cats"
    return [
        download_cat_image(url, cats_dir, date_text, index)
        for index, url in enumerate(urls, start=1)
    ]


def read_pending_tasks(tasks_path: Path) -> list[str]:
    try:
        lines = tasks_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    tasks = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("* [ ]"):
            task_text = stripped[5:].strip()
            if task_text:
                tasks.append(f"- {task_text}")

    return tasks


def render_cats_section(cats: list[CatImage] | str) -> str:
    if isinstance(cats, str):
        return cats

    return "\n".join(
        f"{index}. ![Кот {index}]({cat.src})"
        for index, cat in enumerate(cats, start=1)
    )


def render_tasks_section(tasks: list[str]) -> str:
    if not tasks:
        return "незавершённых задач нет"

    return "\n".join(tasks)


def strip_markdown_list_marker(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("- "):
        return stripped[2:].strip()

    return stripped


def render_text_or_list_html(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return "<p>не удалось получить данные</p>"

    if all(line.strip().startswith("- ") for line in lines):
        items = "\n".join(
            f"<li>{html.escape(strip_markdown_list_marker(line))}</li>"
            for line in lines
        )
        return f"<ul>\n{items}\n</ul>"

    paragraphs = "\n".join(f"<p>{html.escape(line.strip())}</p>" for line in lines)
    return paragraphs


def render_tasks_html(tasks: list[str]) -> str:
    if not tasks:
        return "<p>незавершённых задач нет</p>"

    items = "\n".join(
        f"<li>{html.escape(strip_markdown_list_marker(task))}</li>"
        for task in tasks
    )
    return f"<ul>\n{items}\n</ul>"


def render_cats_html(cats: list[CatImage] | str) -> str:
    if isinstance(cats, str):
        return f"<p>{html.escape(cats)}</p>"

    figures = []
    for index, cat in enumerate(cats, start=1):
        src = html.escape(cat.src, quote=True)
        source_text = "локальное изображение" if cat.local_path else "прямая ссылка"
        figures.append(
            f"""<figure class="cat-card">
    <img src="{src}" alt="Кот {index}" loading="lazy">
    <figcaption>Кот {index} · {source_text}</figcaption>
</figure>"""
        )

    return f"""<div class="cat-gallery">
{chr(10).join(figures)}
</div>"""


def markdown_list_to_plain_items(text: str) -> list[str]:
    return [
        strip_markdown_list_marker(line)
        for line in text.splitlines()
        if line.strip()
    ]


def markdown_list_to_label_items(text: str) -> list[dict[str, str]]:
    items = []
    for line in markdown_list_to_plain_items(text):
        if ":" in line:
            label, value = line.split(":", 1)
            items.append({"label": label.strip(), "value": value.strip()})
        else:
            items.append({"label": line, "value": ""})

    return items


def mime_type_for_path(path: Path) -> str:
    guessed_type, _encoding = mimetypes.guess_type(path.name)
    if guessed_type:
        return guessed_type

    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".css":
        return "text/css"
    if suffix == ".js":
        return "text/javascript"

    return "application/octet-stream"


def file_to_data_url(path: Path) -> str | None:
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return None

    return f"data:{mime_type_for_path(path)};base64,{encoded}"


def hero_image_data_url(base_dir: Path | None) -> str | None:
    if base_dir is None:
        return None

    for path in [
        base_dir / "frontend" / "public" / "hero-bg.jpg",
        base_dir / "frontend" / "dist" / "hero-bg.jpg",
    ]:
        if path.exists():
            return file_to_data_url(path)

    return None


def build_brief_data(
    summary: SummaryData,
    config: dict[str, Any],
    base_dir: Path | None = None,
) -> dict[str, Any]:
    country_name = str(config.get("country_name") or config.get("country_code") or "")
    hero_data_url = hero_image_data_url(base_dir)

    cats = []
    if isinstance(summary.cats, list):
        for index, cat in enumerate(summary.cats, start=1):
            cat_src = cat.src
            if cat.local_path is not None and cat.local_path.exists():
                cat_src = file_to_data_url(cat.local_path) or cat.src

            cats.append(
                {
                    "src": cat_src,
                    "url": cat.url,
                    "local": cat.local_path is not None,
                    "alt": f"Кот {index}",
                }
            )

    return {
        "date": summary.date_text,
        "city": str(config.get("city_name") or DATA_ERROR),
        "country": country_name,
        "weather": {
            "temperature": summary.weather.temperature,
            "description": summary.weather.description,
            "items": markdown_list_to_label_items(summary.weather.markdown),
        },
        "holidays": {
            "summary": summary.holidays.summary,
            "items": []
            if summary.holidays.summary == "праздников нет"
            else markdown_list_to_plain_items(summary.holidays.markdown),
        },
        "cats": cats,
        "tasks": [
            strip_markdown_list_marker(task)
            for task in summary.pending_tasks
        ],
        "assets": {
            "heroImage": hero_data_url or "",
        },
    }


def frontend_asset_paths(base_dir: Path) -> dict[str, Any] | None:
    dist_dir = base_dir / "frontend" / "dist"
    script_path = dist_dir / "morning-summary.js"
    style_path = dist_dir / "morning-summary-frontend.css"

    if not script_path.exists() or not style_path.exists():
        return None

    return {
        "script": "../frontend/dist/morning-summary.js",
        "style": "../frontend/dist/morning-summary-frontend.css",
        "script_path": script_path,
        "style_path": style_path,
        "script_mtime_ns": script_path.stat().st_mtime_ns,
        "style_mtime_ns": style_path.stat().st_mtime_ns,
    }


def frontend_build_warning(base_dir: Path) -> str | None:
    assets = frontend_asset_paths(base_dir)
    if assets is None:
        return (
            "Предупреждение: frontend/dist не найден или не содержит актуальные файлы "
            "morning-summary.js и morning-summary-frontend.css. Выполните: cd frontend; npm run build"
        )

    src_dir = base_dir / "frontend" / "src"
    if not src_dir.exists():
        return None

    source_mtimes = [
        path.stat().st_mtime_ns
        for path in src_dir.rglob("*")
        if path.is_file()
    ]
    if not source_mtimes:
        return None

    latest_source_mtime = max(source_mtimes)
    oldest_build_mtime = min(assets["script_mtime_ns"], assets["style_mtime_ns"])
    if latest_source_mtime > oldest_build_mtime:
        return (
            "Предупреждение: frontend/src новее, чем frontend/dist. "
            "Чтобы увидеть последние изменения дизайна, выполните: cd frontend; npm run build"
        )

    return None


def json_for_script(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def inline_style_text(style_text: str) -> str:
    return style_text.replace("</style", "<\\/style")


def inline_script_text(script_text: str) -> str:
    return script_text.replace("</script", "<\\/script")


def render_summary_html(summary: SummaryData, config: dict[str, Any], base_dir: Path | None = None) -> str:
    if base_dir is not None:
        assets = frontend_asset_paths(base_dir)
        if assets is not None:
            date_text = html.escape(summary.date_text)
            brief_data = json_for_script(build_brief_data(summary, config, base_dir))
            build_version = max(assets["script_mtime_ns"], assets["style_mtime_ns"])
            style_text = inline_style_text(assets["style_path"].read_text(encoding="utf-8"))
            script_text = inline_script_text(assets["script_path"].read_text(encoding="utf-8"))

            return f"""<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Утренняя сводка — {date_text}</title>
    <style>
{style_text}
    </style>
</head>
<body>
    <div id="root"></div>
    <!-- frontend build: {build_version} -->
    <script>
        window.BRIEF_DATA = {brief_data};
    </script>
    <script>
{script_text}
    </script>
</body>
</html>
"""

    city_name = html.escape(str(config.get("city_name") or DATA_ERROR))
    date_text = html.escape(summary.date_text)

    return f"""<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Утренняя сводка — {date_text}</title>
    <style>
        :root {{
            color-scheme: light;
            --bg: #f6f7f9;
            --surface: #ffffff;
            --text: #1f2933;
            --muted: #65758b;
            --line: #d9e2ec;
            --accent: #1d7f6e;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: var(--bg);
            color: var(--text);
            font-family: "Segoe UI", Arial, sans-serif;
            line-height: 1.55;
        }}

        main {{
            width: min(920px, calc(100% - 32px));
            margin: 0 auto;
            padding: 32px 0 48px;
        }}

        header {{
            margin-bottom: 28px;
        }}

        h1 {{
            margin: 0 0 8px;
            font-size: 32px;
            font-weight: 700;
        }}

        .meta {{
            margin: 0;
            color: var(--muted);
        }}

        section {{
            padding: 22px 0;
            border-top: 1px solid var(--line);
        }}

        h2 {{
            margin: 0 0 14px;
            font-size: 22px;
        }}

        ul {{
            margin: 0;
            padding-left: 22px;
        }}

        .cat-gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
        }}

        .cat-card {{
            margin: 0;
            overflow: hidden;
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 8px;
        }}

        .cat-card img {{
            display: block;
            width: 100%;
            height: clamp(220px, 34vw, 360px);
            object-fit: cover;
            background: #eef2f6;
        }}

        .cat-card figcaption {{
            padding: 10px 12px;
            color: var(--muted);
            font-size: 14px;
        }}

        @media (max-width: 560px) {{
            main {{
                width: min(100% - 24px, 920px);
                padding-top: 22px;
            }}

            h1 {{
                font-size: 26px;
            }}
        }}
    </style>
</head>
<body>
<main>
    <header>
        <h1>Утренняя сводка — {date_text}</h1>
        <p class="meta">{city_name}</p>
    </header>

    <section>
        <h2>Праздники</h2>
        {render_text_or_list_html(summary.holidays.markdown)}
    </section>

    <section>
        <h2>Погода</h2>
        {render_text_or_list_html(summary.weather.markdown)}
    </section>

    <section>
        <h2>Коты</h2>
        {render_cats_html(summary.cats)}
    </section>

    <section>
        <h2>Задачи</h2>
        {render_tasks_html(summary.pending_tasks)}
    </section>
</main>
</body>
</html>
"""


def send_clickable_notification(output_file_path: str | Path) -> None:
    absolute_path = Path(output_file_path).resolve()
    status_path = (
        Path(tempfile.gettempdir())
        / f"morning-summary-toast-{os.getpid()}-{int(time.time() * 1000)}.txt"
    )

    try:
        worker = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--toast-worker",
                str(absolute_path),
                str(status_path),
            ],
            cwd=str(Path(__file__).resolve().parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as error:
        print(f"Предупреждение: не удалось показать уведомление: {error}")
        return


    deadline = time.monotonic() + NOTIFICATION_STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if status_path.exists():
            try:
                status = status_path.read_text(encoding="utf-8")
                status_path.unlink(missing_ok=True)
            except OSError:
                status = "shown"

            if status.startswith("error:"):
                print(f"Предупреждение: не удалось показать уведомление: {status[6:].strip()}")
            return

        if worker.poll() is not None:
            print("Предупреждение: не удалось показать уведомление: процесс уведомления завершился раньше времени")
            return

        time.sleep(0.05)

    print("Предупреждение: не удалось подтвердить показ уведомления")


def write_notification_status(status_path: Path | None, status: str) -> None:
    if status_path is None:
        return

    try:
        status_path.write_text(status, encoding="utf-8")
    except OSError:
        pass


def show_clickable_notification(output_file_path: str | Path, status_path: Path | None = None) -> None:
    absolute_path = Path(output_file_path).resolve()
    done = threading.Event()

    def open_summary(_event_args: Any = None) -> None:
        try:
            os.startfile(str(absolute_path))
        except Exception as error:
            print(f"Предупреждение: не удалось открыть файл из уведомления: {error}")
        finally:
            done.set()

    def mark_done(*_args: Any) -> None:
        done.set()

    try:
        from win11toast import notify

        notification = notify(
            "Сводка на день",
            "Нажми, чтобы открыть полную версию",
            button={
                "activationType": "foreground",
                "arguments": "open-summary",
                "content": "Открыть",
            },
            duration="long",
            xml=TOAST_XML,
        )
        write_notification_status(status_path, "shown")

        activated_token = notification.add_activated(lambda *_args: open_summary())
        dismissed_token = notification.add_dismissed(mark_done)
        failed_token = notification.add_failed(mark_done)

        try:
            done.wait(NOTIFICATION_WORKER_TIMEOUT_SECONDS)
        finally:
            notification.remove_activated(activated_token)
            notification.remove_dismissed(dismissed_token)
            notification.remove_failed(failed_token)
    except Exception as error:
        write_notification_status(status_path, f"error: {error}")
        print(f"Предупреждение: не удалось показать уведомление: {error}")


def config_enabled(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}

    return bool(value)


def telegram_api_post(
    bot_token: str,
    method: str,
    data: dict[str, Any],
    files: dict[str, Any] | None = None,
) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    timeout = TELEGRAM_UPLOAD_TIMEOUT_SECONDS if files else REQUEST_TIMEOUT_SECONDS

    try:
        response = requests.post(url, data=data, files=files, timeout=timeout)
    except requests.RequestException:
        print(f"Предупреждение: Telegram {method}: не удалось выполнить запрос")
        return False

    if response.ok:
        return True

    description = ""
    try:
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("description"), str):
            description = f": {payload['description']}"
    except ValueError:
        pass

    print(f"Предупреждение: Telegram {method}: HTTP {response.status_code}{description}")
    return False


def weekday_for_date_text(date_text: str) -> str:
    try:
        date_value = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        return ""

    return WEEKDAYS_RU[date_value.weekday()]


def build_telegram_caption(
    config: dict[str, Any],
    summary: SummaryData,
) -> str:
    city_name = str(config.get("city_name") or DATA_ERROR)
    weekday = weekday_for_date_text(summary.date_text)
    date_line = summary.date_text
    if weekday:
        date_line = f"{weekday}, {summary.date_text}"

    return (
        f"Утренняя сводка готова · {city_name} · {date_line} · "
        f"{summary.weather.temperature} · задач: {len(summary.pending_tasks)}"
    )


def select_full_summary_file(markdown_file_path: str | Path) -> Path:
    markdown_path = Path(markdown_file_path)
    html_path = markdown_path.with_suffix(".html")
    if html_path.exists():
        return html_path

    return markdown_path


def send_telegram_summary(
    config: dict[str, Any],
    summary: SummaryData,
    markdown_file_path: str | Path,
) -> None:
    if not config_enabled(config.get("send_telegram"), default=False):
        print("Telegram: пропущено — send_telegram=false.")
        return

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    missing_variables = [
        name
        for name, value in {
            "TELEGRAM_BOT_TOKEN": bot_token,
            "TELEGRAM_CHAT_ID": chat_id,
        }.items()
        if not value
    ]
    if missing_variables:
        print(
            "Telegram: пропущено — не заданы переменные окружения: "
            + ", ".join(missing_variables)
        )
        return

    summary_file_path = select_full_summary_file(markdown_file_path).resolve()
    if not summary_file_path.exists():
        print(f"Telegram: не удалось отправить HTML-файл — файл не найден: {summary_file_path}")
        return

    print("Telegram: переменные найдены, отправляю HTML-файл...")
    with summary_file_path.open("rb") as summary_file:
        sent = telegram_api_post(
            bot_token,
            "sendDocument",
            {
                "chat_id": chat_id,
                "caption": build_telegram_caption(config, summary),
            },
            files={
                "document": (
                    summary_file_path.name,
                    summary_file,
                    "text/html",
                ),
            },
        )

    if sent:
        print("Telegram: HTML-файл отправлен.")
    else:
        print("Telegram: не удалось отправить HTML-файл.")


def build_summary(base_dir: Path, output_dir: Path, config: dict[str, Any]) -> SummaryData:
    today = today_for_config_timezone(config)
    date_text = today.isoformat()

    holidays = fetch_holidays(config, today)
    weather = fetch_weather(config)
    cats = fetch_cat_images(config, output_dir, date_text)
    tasks = read_pending_tasks(base_dir / "tasks.md")

    markdown = f"""# Утренняя сводка — {date_text}

## Праздники

{holidays.markdown}

## Погода

{weather.markdown}

## Коты

{render_cats_section(cats)}

## Задачи

{render_tasks_section(tasks)}
"""

    summary = SummaryData(
        date_text=date_text,
        markdown=markdown,
        html="",
        weather=weather,
        holidays=holidays,
        cats=cats,
        pending_tasks=tasks,
    )
    summary.html = render_summary_html(summary, config, base_dir)

    return summary


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    load_env_file(base_dir / ".env")
    config = load_config(base_dir / "config.json")
    output_dir = base_dir / str(config.get("output_dir", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = build_summary(base_dir, output_dir, config)

    output_path = output_dir / f"{summary.date_text}.md"
    html_output_path = output_dir / f"{summary.date_text}.html"
    output_path.write_text(summary.markdown, encoding="utf-8")
    html_output_path.write_text(summary.html, encoding="utf-8")

    print(f"Создан файл: {output_path}")
    print(f"Создан файл: {html_output_path}")
    print(f"Открывайте локальную версию: {html_output_path.resolve()}")
    print("HTML самодостаточный: CSS, JS и локальные изображения встроены в файл.")
    print("Telegram отправляет HTML-файл документом, если заданы переменные TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID.")
    print("Обновление страницы в браузере не пересоздаёт данные и не отправляет уведомления повторно.")
    warning = frontend_build_warning(base_dir)
    if warning:
        print(warning)

    send_telegram_summary(config, summary, output_path.resolve())

    if config_enabled(config.get("send_windows_notification"), default=True):
        send_clickable_notification(select_full_summary_file(output_path).resolve())


if __name__ == "__main__":
    if len(sys.argv) in {3, 4} and sys.argv[1] == "--toast-worker":
        notification_status_path = Path(sys.argv[3]) if len(sys.argv) == 4 else None
        show_clickable_notification(sys.argv[2], notification_status_path)
    else:
        main()
