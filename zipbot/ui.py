from __future__ import annotations

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .models import BotSession, QueueItem, human_size


def home_text(session: BotSession, max_total_bytes: int) -> str:
    percent = (session.total_size / max_total_bytes * 100) if max_total_bytes else 0
    password = "set" if session.has_password else "none"
    lines = [
        "ZipBot",
        "",
        f"Files: {len(session.items)}",
        f"Queued size: {human_size(session.total_size)} / {human_size(max_total_bytes)} ({percent:.1f}%)",
        f"Archive name: {session.archive_name}",
        f"Password: {password}",
        f"Mode: {session.compression_format}",
        "",
        "Send or forward files here to add them to the queue.",
    ]
    return "\n".join(lines)


def queue_text(session: BotSession, max_total_bytes: int) -> str:
    if not session.items:
        return home_text(session, max_total_bytes) + "\n\nQueue is empty."
    lines = [home_text(session, max_total_bytes), "", "Queue:"]
    for index, item in enumerate(session.items, start=1):
        lines.append(f"{index}. {item.archive_name} - {human_size(item.size)}")
    return "\n".join(lines)


def item_text(item: QueueItem) -> str:
    return "\n".join(
        [
            "Queued file",
            "",
            f"Name: {item.archive_name}",
            f"Original: {item.original_name}",
            f"Type: {item.media_kind}",
            f"Size: {human_size(item.size)}",
        ]
    )


def home_keyboard(session: BotSession) -> InlineKeyboardMarkup:
    can_compress = bool(session.items) and not session.busy
    rows = [
        [
            InlineKeyboardButton("Queue", callback_data="queue"),
            InlineKeyboardButton("Name", callback_data="set_name"),
        ],
        [
            InlineKeyboardButton("Password", callback_data="set_password"),
            InlineKeyboardButton("Mode", callback_data="mode"),
        ],
        [
            InlineKeyboardButton("Clear", callback_data="clear"),
            InlineKeyboardButton("Compress", callback_data="compress" if can_compress else "noop"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def queue_keyboard(session: BotSession) -> InlineKeyboardMarkup:
    rows = []
    for index, item in enumerate(session.items, start=1):
        label = f"{index}. {item.archive_name[:28]}"
        rows.append([InlineKeyboardButton(label, callback_data=f"item:{item.id}")])
    rows.append(
        [
            InlineKeyboardButton("Back", callback_data="home"),
            InlineKeyboardButton("Clear", callback_data="clear"),
            InlineKeyboardButton("Compress", callback_data="compress" if session.items else "noop"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def item_keyboard(item: QueueItem) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Up", callback_data=f"move:{item.id}:-1"),
                InlineKeyboardButton("Down", callback_data=f"move:{item.id}:1"),
            ],
            [
                InlineKeyboardButton("Rename", callback_data=f"rename:{item.id}"),
                InlineKeyboardButton("Remove", callback_data=f"remove:{item.id}"),
            ],
            [InlineKeyboardButton("Back", callback_data="queue")],
        ]
    )


def mode_keyboard(current: str) -> InlineKeyboardMarkup:
    def label(value: str) -> str:
        return f"* {value}" if value == current else value

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(label("auto"), callback_data="mode_set:auto"),
                InlineKeyboardButton(label("7z"), callback_data="mode_set:7z"),
            ],
            [
                InlineKeyboardButton(label("zip"), callback_data="mode_set:zip"),
                InlineKeyboardButton(label("tar.gz"), callback_data="mode_set:tar.gz"),
            ],
            [InlineKeyboardButton("Back", callback_data="home")],
        ]
    )


def password_keyboard(has_password: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_password:
        rows.append([InlineKeyboardButton("Clear password", callback_data="clear_password")])
    rows.append([InlineKeyboardButton("Back", callback_data="home")])
    return InlineKeyboardMarkup(rows)
