# Утренняя сводка

Личная сводка погоды, праздников, котов и незавершённых задач. Python создаёт
`output/YYYY-MM-DD.md` и `output/YYYY-MM-DD.html`; React оформляет HTML.
По настройкам файл отправляется в Telegram и показывается Windows-уведомление.

Готовый HTML можно перенести и открыть без сети: стили, JavaScript, шрифты
и успешно загруженные картинки встроены внутрь. Обновление страницы не обновляет
данные и не отправляет сообщения. Для новой сводки снова запустите Python.
Задачи редактируются в `tasks.md`; это статический отчёт, не менеджер задач.

![Пример сводки](image.png)

## Требования

- Python 3.11+.
- Node.js 22.12+ в ветке 22, Node 24 или 26+ для сборки и тестов интерфейса.
- Интернет для установки и получения свежих данных. Сбои API отображаются в сводке.
- Windows 10/11 для toast; генератор также работает на Linux.

## Первый запуск на Windows

```powershell
git clone https://github.com/wwquix/morning-brief.git
cd morning-brief
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe app.py --local-only
Start-Process (Get-ChildItem .\output\*.html | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
```

Если `py` отсутствует, используйте `python -m venv .venv`. Активация окружения
не обязательна: команды используют его Python напрямую.

`--local-only` отключает обе отправки независимо от config, но получает свежие
данные из публичных API. Это удобный первый запуск без Telegram-ключей.
Без frontend/dist создаётся простая HTML-версия с предупреждением.
После изменения интерфейса повторите сборку и запуск Python.

## Настройки

`config.json` читается относительно проекта, независимо от текущего каталога.

| Поле | Значение и ограничения |
|---|---|
| `city_name`, `country_name` | Подписи в сводке |
| `latitude`, `longitude` | Числа от -90 до 90 / от -180 до 180 |
| `country_code` | Двухбуквенный код страны Nager.Date, например `BY` |
| `timezone` | Часовой пояс IANA, например `Europe/Minsk`; определяет дату сводки |
| `output_dir` | Каталог результатов; относительный путь считается от проекта |
| `cat_images_count` | Целое 0–10; 0 отключает запрос котов |
| `send_telegram` | JSON `true` / `false`; отправлять HTML-документ |
| `send_windows_notification` | JSON `true` / `false`; Windows toast |
| `language` | Зарезервировано; текущий интерфейс и описания погоды — на русском |

В исходном config оба уведомления включены. `--local-only` имеет приоритет.
Ошибка JSON, координат, timezone или прав записи завершает команду кодом 1.

В `tasks.md` добавляйте `- [ ] Задача`; строки `- [x] Выполнено` пропускаются.
Поддерживаются маркеры `-` и `*`, UTF-8 с BOM или без него. Пустой файл означает
отсутствие задач; отсутствующий/нечитаемый файл отображается как ошибка.

## Telegram и окружение

1. Создайте бота через `@BotFather` (`/newbot`).
2. Создайте `.env` по `.env.example`, укажите токен и напишите своему боту сообщение.
3. Запустите `.\.venv\Scripts\python.exe get_chat_id.py`, скопируйте нужный chat_id в `.env`.
4. Включите `send_telegram=true`; запустите `.\.venv\Scripts\python.exe app.py`.

| Переменная | Назначение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Секретный токен BotFather |
| `TELEGRAM_CHAT_ID` | Получатель HTML: личный чат, группа или канал с нужными правами |

Обе команды читают `.env` из корня проекта. Уже заданное окружение имеет приоритет
над файлом, включая PowerShell-запуск. Поддерживаются кавычки и префикс `export`.
`.env*` исключены из Git, кроме `.env.example`. Замените значения `PASTE_...`.

Без токена/chat_id отправка пропускается, файлы создаются. Ошибка Telegram не
удаляет локальную сводку. Код 0 означает создание файлов, а не гарантию доставки.
Telegram-клиент может требовать скачать HTML и открыть внешним браузером.
Сводка содержит ваши задачи — выбирайте получателя внимательно.

## Повторный и скрытый Windows-запуск

```powershell
.\run_morning_brief.ps1 -LocalOnly  # без уведомлений
.\run_morning_brief.ps1             # по config.json
```

Лог: `logs/morning-brief.log`. Скрипт использует `.venv\Scripts\python.exe` и
передаёт код завершения. `run_morning_brief_hidden.vbs` запускает его без окна
из собственной папки. Если необязательный компонент VBScript отключён,
используйте PowerShell. Для toast нужна интерактивная сессия Windows с разрешёнными уведомлениями.

## Linux и cron

После клонирования из корня проекта:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python app.py --local-only
```

Windows toast на Linux пропускается. Для Telegram настройте `.env`, ограничьте
доступ `chmod 600 .env` и уберите `--local-only`.
Пример cron (замените путь своим):

```cron
0 7 * * * cd /opt/morning-brief && .venv/bin/python app.py >> cron.log 2>&1
```

Время запуска задаёт timezone cron/сервера; настройка timezone проекта управляет
датой данных. Каждый запуск может отправить сообщение. Дедупликации и блокировки
одновременных запусков нет.

## Разработка и проверки

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip_audit
cd frontend
npm ci
npm run lint
npm test
npm run build
npm audit
npx playwright install chromium
cd ..
.\.venv\Scripts\python.exe tests/generate_fixtures.py
cd frontend
npm run test:e2e
```

На Linux используйте `.venv/bin/python` и `npx playwright install --with-deps chromium`.
Тесты не отправляют уведомления. Браузерные fixtures детерминированы и проверяют
длинные задачи, экранирование HTML, отсутствие сети, ошибки данных и 3 ширины экрана.
GitHub Actions запускает проверки на Linux/Python 3.11/Node 22 и Windows/Python 3.13/Node 24.

`npm run dev` показывает пример из `frontend/index.html`, а не Python-сводку.
Vite собирает библиотеку JS/CSS; production-результат проверяйте открытием HTML
из `output`. Vite preview для такой сборки не поддерживается.

## Сервисы и ограничения

- Open-Meteo: текущая погода. Nager.Date: официальные праздники, покрытие зависит от страны.
- The Cat API: случайные изображения; при частичном ответе показываются доступные.
- Картинки принимаются только с HTTPS CDN The Cat API или его конкретного S3-bucket,
  без перенаправлений, до 8 МБ каждая; SVG исключён. При ошибках нет внешних fallback-запросов.
- Шрифты Barlow/Cormorant Garamond встроены через Fontsource (SIL OFL).
- Файлы за одну дату перезаписываются. Картинки в `output/cats` накапливаются;
  политики автоматического удаления нет.
- Полного lock-файла Python нет: используйте чистое окружение и `pip_audit`.

Подробности и оставшиеся ограничения: [аудит](docs/AUDIT.md).
