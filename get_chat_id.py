from __future__ import annotations

import os
from typing import Any

import requests


REQUEST_TIMEOUT_SECONDS = 10


def get_chat_from_update(update: dict[str, Any]) -> dict[str, Any] | None:
    for field_name in ("message", "edited_message", "channel_post", "edited_channel_post"):
        event = update.get(field_name)
        if isinstance(event, dict) and isinstance(event.get("chat"), dict):
            return event["chat"]

    callback_query = update.get("callback_query")
    if isinstance(callback_query, dict):
        message = callback_query.get("message")
        if isinstance(message, dict) and isinstance(message.get("chat"), dict):
            return message["chat"]

    return None


def format_chat_name(chat: dict[str, Any]) -> str:
    title = chat.get("title")
    if title:
        return str(title)

    parts = [chat.get("first_name"), chat.get("last_name")]
    name = " ".join(str(part) for part in parts if part)
    if name:
        return name

    username = chat.get("username")
    if username:
        return f"@{username}"

    return "без имени"


def main() -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("Не задана переменная окружения TELEGRAM_BOT_TOKEN.")
        print("Перед запуском создайте бота, задайте TELEGRAM_BOT_TOKEN и напишите боту любое сообщение.")
        return

    print("Перед запуском нужно написать своему боту любое сообщение в Telegram.")
    print("Проверяю последние обновления...")

    try:
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getUpdates",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        print("Не удалось выполнить запрос к Telegram getUpdates.")
        return

    if not response.ok:
        print(f"Telegram getUpdates вернул HTTP {response.status_code}. Проверьте токен бота.")
        return

    try:
        payload = response.json()
    except ValueError:
        print("Telegram вернул ответ, который не удалось прочитать как JSON.")
        return

    updates = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(updates, list) or not updates:
        print("chat_id не найдены.")
        print("Откройте чат со своим ботом, отправьте любое сообщение и запустите скрипт еще раз.")
        return

    seen_chat_ids = set()
    found = False
    for update in updates:
        if not isinstance(update, dict):
            continue

        chat = get_chat_from_update(update)
        if not chat or "id" not in chat:
            continue

        chat_id = chat["id"]
        if chat_id in seen_chat_ids:
            continue

        seen_chat_ids.add(chat_id)
        found = True
        chat_type = chat.get("type", "unknown")
        chat_name = format_chat_name(chat)

        print(f"chat_id: {chat_id}")
        print(f"тип: {chat_type}")
        print(f"имя: {chat_name}")
        print()

    if not found:
        print("chat_id не найдены в последних обновлениях.")
        print("Напишите боту любое сообщение и запустите скрипт еще раз.")


if __name__ == "__main__":
    main()
