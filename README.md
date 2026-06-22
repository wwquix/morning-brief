 /># Утренняя сводка <img width="1902" height="944" alt="image" src="https://github.com/user-attachments/assets/09d81e12-1bdc-440c-b3ea-65962bb6483e" />


Локальный Python-проект для создания Markdown-файла с утренней сводкой и отправки уведомлений.

Каждый запуск `app.py`:

- создает файл `output\YYYY-MM-DD.md`;
- создает HTML-версию `output\YYYY-MM-DD.html`;
- HTML-версия использует Vite + React frontend из папки `frontend` и данные `window.BRIEF_DATA`;
- HTML-файл самодостаточный: CSS, JS, hero-изображение и локальные картинки котов встраиваются внутрь файла;
- добавляет дату, праздник, погоду, картинки котов и незавершенные задачи из `tasks.md`;
- скачивает котов в `output\cats` и вставляет их в HTML как галерею;
- показывает Windows-уведомление, если `send_windows_notification=true`;
- отправляет HTML-файл документом в Telegram, если `send_telegram=true`.

Токен Telegram не хранится в коде, `config.json`, README или логах. Он читается из переменной окружения `TELEGRAM_BOT_TOKEN` или из локального файла `.env`.

## Требования

- Python 3.11+
- Node.js 20+ для сборки React frontend
- интернет-доступ для API погоды, праздников, котов и Telegram
- Windows для локального toast-уведомления

## Первый запуск на Windows

```powershell
cd "D:\yura\Сайты и код\проекты\Бот уведомление - Сводка с утра"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Если команда `python` не найдена, используйте `py`:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

## Frontend

React-часть находится в папке `frontend`.

Установка и сборка:

```powershell
cd "D:\yura\Сайты и код\проекты\Бот уведомление - Сводка с утра\frontend"
npm install
npm run build
```

После сборки `app.py` создает `output\YYYY-MM-DD.html`, который читает `window.BRIEF_DATA` и показывает:

- hero;
- погоду;
- праздники;
- котов картинками;
- задачи.
<img width="1895" height="937" alt="image" src="https://github.com/user-attachments/assets/6adc8291-9805-4298-83bb-e76c95b4d728" />

React Bits сейчас не используется.

После любых изменений в `frontend` сначала обновите сборку, а потом запускайте Python:

```powershell
cd "D:\yura\Сайты и код\проекты\Бот уведомление - Сводка с утра"
cd frontend
npm run build
cd ..
.\.venv\Scripts\python.exe app.py
Start-Process ".\output\2026-06-21.html"
```

Открыть самый свежий HTML-файл можно одной командой:

```powershell
Start-Process (Get-ChildItem ".\output\*.html" | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
```

## Настройки

Все обычные настройки находятся в `config.json`.

По умолчанию сводка настроена на Светлогорск, Беларусь:

- `city_name`: `Светлогорск`;
- `country_code`: `BY`;
- `timezone`: `Europe/Minsk`;
- `latitude`: `52.6329`;
- `longitude`: `29.7389`.

Важные переключатели:

- `send_telegram` - отправлять сводку в Telegram;
- `send_windows_notification` - показывать локальное Windows-уведомление.

Если `send_telegram=true`, но `TELEGRAM_BOT_TOKEN` или `TELEGRAM_CHAT_ID` не заданы, скрипт выведет предупреждение и продолжит работу локально.

## Telegram
<img width="1899" height="937" alt="image" src="https://github.com/user-attachments/assets/6487c089-609c-4086-9d21-ef889909fb08" />

### Создать бота

1. Откройте Telegram и найдите `@BotFather`.
2. Отправьте команду `/newbot`.
3. Задайте имя и username бота.
4. BotFather выдаст токен. Не вставляйте его в код, `config.json`, README или публичные сообщения.

### Написать боту первое сообщение

Откройте созданного бота в Telegram и отправьте ему любое сообщение, например `привет`.

Без первого сообщения Telegram Bot API обычно не вернет ваш `chat_id`.

### Узнать TELEGRAM_CHAT_ID

В PowerShell временно задайте токен только для текущего окна:

```powershell
$env:TELEGRAM_BOT_TOKEN="PASTE_BOT_TOKEN_HERE"
python get_chat_id.py
```

Скрипт покажет найденные `chat_id`. Скопируйте нужный ID.

### Проверить отправку на Windows

В том же окне PowerShell задайте `chat_id` и запустите проект:

```powershell
$env:TELEGRAM_BOT_TOKEN="PASTE_BOT_TOKEN_HERE"
$env:TELEGRAM_CHAT_ID="PASTE_CHAT_ID_HERE"
python app.py
```

Можно также создать локальный `.env` в корне проекта по примеру `.env.example`:

```env
TELEGRAM_BOT_TOKEN=PASTE_BOT_TOKEN_HERE
TELEGRAM_CHAT_ID=PASTE_CHAT_ID_HERE
```

Файл `.env` добавлен в `.gitignore`; не отправляйте его в репозиторий.

Ожидаемый результат:

- в папке `output` появился файл `YYYY-MM-DD.md`;
- в папке `output` появился файл `YYYY-MM-DD.html`;
- в папке `output\cats` появились скачанные картинки котов;
- на компьютере появилось Windows-уведомление;
- в Telegram пришел HTML-файл документом с короткой подписью.

HTML самодостаточный, поэтому его можно открыть и из локальной папки `output`, и после скачивания из Telegram.

## Повторный локальный запуск

```powershell
cd "D:\yura\Сайты и код\проекты\Бот уведомление - Сводка с утра"
.\.venv\Scripts\Activate.ps1
python app.py
```

Если Telegram-переменные не заданы, будет создана локальная сводка и показано Windows-уведомление.

Полную HTML-версию можно открыть вручную:

```powershell
start .\output\YYYY-MM-DD.html
```

Или открыть самый свежий HTML:

```powershell
Start-Process (Get-ChildItem ".\output\*.html" | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
```

## Перенос на сервер
<img width="1896" height="938" alt="image" src="https://github.com/user-attachments/assets/0712b333-1a01-4d83-b97f-77654ab3184c" />

На Linux-сервере Windows-уведомления не нужны, поэтому в `config.json` обычно ставят:

```json
"send_windows_notification": false
```

Базовый порядок:

```bash
cd /opt
git clone <repo-url> morning-summary
cd /opt/morning-summary
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Если проекта нет в Git, перенесите папку проекта на сервер любым удобным способом и выполните команды из нее.

Секреты удобно хранить в отдельном env-файле на сервере, например `/etc/morning-summary.env`:

```bash
export TELEGRAM_BOT_TOKEN='PASTE_BOT_TOKEN_HERE'
export TELEGRAM_CHAT_ID='PASTE_CHAT_ID_HERE'
```

Ограничьте доступ к файлу:

```bash
sudo chmod 600 /etc/morning-summary.env
```

Проверка на сервере:

```bash
. /etc/morning-summary.env
cd /opt/morning-summary
. .venv/bin/activate
python app.py
```

## Cron на Linux

Откройте cron:

```bash
crontab -e
```

Пример запуска каждый день в 7:00:

```cron
0 7 * * * . /etc/morning-summary.env; cd /opt/morning-summary && /opt/morning-summary/.venv/bin/python app.py >> /opt/morning-summary/cron.log 2>&1
```

Проверьте, что путь `/opt/morning-summary` совпадает с реальным путем к проекту.

## Задачи

Незавершенные задачи хранятся в `tasks.md`.

Скрипт добавляет в сводку только задачи с пустым чекбоксом:

```markdown
- [ ] Пример незавершенной задачи
```

Выполненные задачи вида `- [x] ...` в сводку не попадают.
