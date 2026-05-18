from __future__ import annotations

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .models import BotSession, QueueItem, human_size

STYLE_PRIMARY = "primary"
STYLE_POSITIVE = "positive"
STYLE_DESTRUCTIVE = "destructive"
STYLE_SECONDARY = "secondary"


def button(
    text: str,
    callback_data: str,
    style: str | None = None,
    icon_custom_emoji_id: str | None = None,
) -> InlineKeyboardButton:
    kwargs = {"text": text, "callback_data": callback_data}
    if style:
        kwargs["style"] = style
    if icon_custom_emoji_id:
        kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id
    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs.pop("style", None)
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(**kwargs)


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
            button("Queue", callback_data="queue", style=STYLE_PRIMARY),
            button("Name", callback_data="set_name", style=STYLE_SECONDARY),
        ],
        [
            button("Password", callback_data="set_password", style=STYLE_SECONDARY),
            button("Mode", callback_data="mode", style=STYLE_SECONDARY),
        ],
        [
            button("Clear", callback_data="clear", style=STYLE_DESTRUCTIVE),
            button(
                "Compress",
                callback_data="compress" if can_compress else "noop",
                style=STYLE_POSITIVE if can_compress else STYLE_SECONDARY,
            ),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def queue_keyboard(session: BotSession) -> InlineKeyboardMarkup:
    rows = []
    for index, item in enumerate(session.items, start=1):
        label = f"{index}. {item.archive_name[:28]}"
        rows.append([button(label, callback_data=f"item:{item.id}", style=STYLE_PRIMARY)])
    rows.append(
        [
            button("Back", callback_data="home", style=STYLE_SECONDARY),
            button("Clear", callback_data="clear", style=STYLE_DESTRUCTIVE),
            button(
                "Compress",
                callback_data="compress" if session.items else "noop",
                style=STYLE_POSITIVE if session.items else STYLE_SECONDARY,
            ),
        ]
    )
    return InlineKeyboardMarkup(rows)


def item_keyboard(item: QueueItem) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                button("Up", callback_data=f"move:{item.id}:-1", style=STYLE_SECONDARY),
                button("Down", callback_data=f"move:{item.id}:1", style=STYLE_SECONDARY),
            ],
            [
                button("Rename", callback_data=f"rename:{item.id}", style=STYLE_PRIMARY),
                button("Remove", callback_data=f"remove:{item.id}", style=STYLE_DESTRUCTIVE),
            ],
            [button("Back", callback_data="queue", style=STYLE_SECONDARY)],
        ]
    )


def mode_keyboard(current: str) -> InlineKeyboardMarkup:
    def label(value: str) -> str:
        return f"* {value}" if value == current else value

    return InlineKeyboardMarkup(
        [
            [
                button(label("auto"), callback_data="mode_set:auto", style=STYLE_PRIMARY),
                button(label("7z"), callback_data="mode_set:7z", style=STYLE_PRIMARY),
            ],
            [
                button(label("zip"), callback_data="mode_set:zip", style=STYLE_PRIMARY),
                button(label("tar.gz"), callback_data="mode_set:tar.gz", style=STYLE_PRIMARY),
            ],
            [button("Back", callback_data="home", style=STYLE_SECONDARY)],
        ]
    )


def password_keyboard(has_password: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_password:
        rows.append(
            [
                button(
                    "Clear password",
                    callback_data="clear_password",
                    style=STYLE_DESTRUCTIVE,
                )
            ]
        )
    rows.append([button("Back", callback_data="home", style=STYLE_SECONDARY)])
    return InlineKeyboardMarkup(rows)
