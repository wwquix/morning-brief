# Morning Brief Planner — завершение настройки

## Что изменилось

Исходный дизайн Morning Brief не заменяется. Старые разделы с погодой, праздниками, котами и задачами остаются без изменений. Новый блок «Личный план» монтируется после существующей страницы.

Основная цепочка:

```text
tasks.md / routines.json / diction_exercises.json
                     │
                     ├── локальный резервный режим
                     │
Notion databases ────┤
                     ▼
              morning_planner
                     │
                     ├── SQLite: стабильный план и история
                     ├── HTML: исходный дизайн + новый блок
                     ├── Telegram: самостоятельный HTML
                     └── Notion: страница дня с чекбоксами
```

## Где записывать данные

### После подключения Notion

Это основной режим.

- **Morning Brief — Задачи**: одноразовые задачи.
- **Morning Brief — Регулярные действия**: ежедневные и недельные действия.
- **Morning Brief — Дикция**: библиотека упражнений.
- **Morning Brief — Дни**: автоматически создаваемые страницы каждого дня.

Не редактируй базу `Morning Brief — Дни` вручную, кроме отметок и заметок на странице конкретного дня.

### До подключения Notion или при сбое

- `tasks.md` — одноразовые задачи.
- `routines.json` — регулярные действия.
- `diction_exercises.json` — упражнения.
- `data/morning_brief.db` — внутренняя история; вручную не редактируется.

Пример задачи в `tasks.md`:

```markdown
- [ ] Закончить API | date:2026-07-30 | priority:high | category:IT | duration:45
```

Все поля после `|` необязательны.

## Быстрая локальная установка Windows

Из корня проекта:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_project.ps1
```

Скрипт:

1. создаст `.venv`, если её нет;
2. установит Python-зависимости;
3. установит frontend-зависимости;
4. соберёт React/Vite;
5. проверит конфигурацию.

Тестовый запуск:

```powershell
.\.venv\Scripts\python.exe planner_app.py
Start-Process (Get-ChildItem ".\output\*.html" | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
```

Классический `app.py` оставлен и может использоваться отдельно. Основной запуск новой версии — `planner_app.py`.

## Подключение Notion

### 1. Создай родительскую страницу

В Notion создай пустую страницу, например:

```text
Morning Brief
```

Базы вручную создавать не требуется.

### 2. Создай внутреннюю интеграцию

В Notion Developer Portal создай internal integration/connection.

Разрешения:

- Read content;
- Insert content;
- Update content.

Скопируй installation access token.

### 3. Дай интеграции доступ к странице

Открой созданную страницу `Morning Brief`.

Меню `•••` → `Add connections` → выбери созданную интеграцию.

Без этого API вернёт ошибку доступа.

### 4. Добавь токен в `.env`

Не отправляй токен в GitHub или сообщения.

```env
NOTION_TOKEN=...
```

Существующие `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` оставь без изменений.

### 5. Запусти автоматическую настройку

```powershell
.\.venv\Scripts\python.exe scripts\setup_notion.py
```

Скрипт попросит ссылку на пустую родительскую страницу и автоматически:

- создаст четыре базы;
- запишет data source ID в `.env`;
- перенесёт начальные регулярные действия;
- перенесёт библиотеку дикции.

Повторно не запускай его без необходимости: повторный запуск создаст ещё один набор баз.

### 6. Проверь

```powershell
.\.venv\Scripts\python.exe scripts\check_setup.py
.\.venv\Scripts\python.exe planner_app.py
```

После запуска в базе `Morning Brief — Дни` появится страница текущей даты.

## Как пользоваться каждый день

### Одноразовая задача

Добавь строку в `Morning Brief — Задачи`.

Рекомендуемые поля:

- `Название`;
- `Дата`;
- `Статус` — `Входящие` или `Запланировано`;
- `В ближайший план` — включи для задачи без даты;
- `Приоритет`;
- `Категория`;
- `Минуты`.

В план попадут:

- задачи на сегодня;
- просроченные незавершённые задачи;
- задачи без даты с включённым `В ближайший план`.

### Регулярное действие

Добавь строку в `Morning Brief — Регулярные действия`.

- `Активно` — включено;
- `Дни` — `Ежедневно` либо нужные дни недели;
- `Минуты`;
- `Категория`.

### Упражнение дикции

Добавь строку в `Morning Brief — Дикция`.

Тип должен быть одним из:

- `warmup`;
- `syllables`;
- `words`;
- `tongue_twister`;
- `reading`;
- `free_speech`.

`Пауза дней` определяет, сколько дней упражнение не должно повторяться.

### Выполнение плана

Утром программа создаёт страницу в `Morning Brief — Дни`. Ставь галочки на этой странице.

На следующем запуске программа:

1. прочитает страницу предыдущего дня;
2. сохранит отметки в SQLite;
3. обновит процент выполнения;
4. покажет вчерашний результат в новом HTML;
5. сформирует новый набор упражнений.

Галочки в HTML сохраняются только локально в браузере. При подключённом Notion главным источником считаются галочки Notion.

## Автоматический запуск Windows

Установить задачу на 07:00:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_task.ps1 -Time "07:00"
```

Проверить:

```powershell
Get-ScheduledTask -TaskName "Morning Brief"
```

Удалить:

```powershell
Unregister-ScheduledTask -TaskName "Morning Brief" -Confirm:$false
```

## Автоматический запуск Ubuntu VPS

Файлы:

- `deploy/morning-brief.service`;
- `deploy/morning-brief.timer`.

Пример:

```bash
sudo cp deploy/morning-brief.service /etc/systemd/system/
sudo cp deploy/morning-brief.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now morning-brief.timer
systemctl list-timers morning-brief.timer
```

Секреты хранятся в:

```text
/etc/morning-brief.env
```

Пример:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
NOTION_TOKEN=...
NOTION_PARENT_PAGE_ID=...
NOTION_TASKS_DATA_SOURCE_ID=...
NOTION_ROUTINES_DATA_SOURCE_ID=...
NOTION_EXERCISES_DATA_SOURCE_ID=...
NOTION_DAYS_DATA_SOURCE_ID=...
```

Права:

```bash
sudo chmod 600 /etc/morning-brief.env
```

## Локальное добавление без Notion

```powershell
.\.venv\Scripts\python.exe planner_cli.py add-task "Закончить API" --date 2026-07-30 --category IT --duration 45
```

```powershell
.\.venv\Scripts\python.exe planner_cli.py add-routine "Зарядка" --days "Ежедневно" --category "Здоровье" --duration 10
```

```powershell
.\.venv\Scripts\python.exe planner_cli.py add-exercise "Новая скороговорка" --type tongue_twister --difficulty medium --text "Текст упражнения"
```

## Проверки проекта

```powershell
.\.venv\Scripts\python.exe -m pytest
cd frontend
npm run build
```

GitHub Actions запускает те же базовые проверки для pull request.

## Просмотр и сброс сегодняшнего плана

План фиксируется на день, чтобы повторный запуск не менял упражнения.

Посмотреть сохранённый план:

```powershell
.\.venv\Scripts\python.exe planner_cli.py show-day
```

Безопасно пересоздать сегодняшний план:

```powershell
.\.venv\Scripts\python.exe planner_cli.py reset-day
.\.venv\Scripts\python.exe planner_app.py
```

Перед удалением CLI запросит подтверждение. Базу SQLite вручную редактировать не требуется.

## Безопасность

- `.env` не отправляется в Git;
- `data/*.db` не отправляется в Git;
- токены не печатаются в лог;
- при недоступном Notion используется локальный режим;
- `app.py` и исходный интерфейс сохранены;
- OBS и настройка микрофона в этот проект не входят.
