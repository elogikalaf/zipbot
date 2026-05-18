from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.enums import ChatAction
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, Message

from .compressor import compress_session
from .config import Settings, load_settings
from .models import BotSession, QueueItem, clean_filename, human_size
from .ui import (
    home_keyboard,
    home_text,
    item_keyboard,
    item_text,
    mode_keyboard,
    password_keyboard,
    queue_keyboard,
    queue_text,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("zipbot")

settings: Settings = load_settings()
settings.work_dir.mkdir(parents=True, exist_ok=True)
session = BotSession(
    owner_id=settings.primary_owner_id,
    work_root=settings.work_dir / str(settings.primary_owner_id),
    compression_format=settings.default_format,
    compression_level=settings.default_level,
)
app = Client(
    "zipbot",
    api_id=settings.api_id,
    api_hash=settings.api_hash,
    bot_token=settings.bot_token,
    workdir=str(settings.work_dir),
)


def ensure_dirs() -> None:
    (session.work_root / "incoming").mkdir(parents=True, exist_ok=True)
    (session.work_root / "out").mkdir(parents=True, exist_ok=True)


def is_owner(message: Message | CallbackQuery) -> bool:
    user = message.from_user
    return bool(user and user.id in settings.owner_ids)


async def reject_if_not_owner(message: Message | CallbackQuery) -> bool:
    if is_owner(message):
        return False
    if isinstance(message, CallbackQuery):
        await message.answer("This bot is private.", show_alert=True)
    else:
        await message.reply_text("This bot is private.")
    return True


async def show_home(target: Message | CallbackQuery, text: str | None = None) -> None:
    body = text or home_text(session, settings.max_total_bytes)
    keyboard = home_keyboard(session)
    try:
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(body, reply_markup=keyboard)
        else:
            await target.reply_text(body, reply_markup=keyboard)
    except MessageNotModified:
        pass


def media_payload(message: Message):
    for name in (
        "document",
        "video",
        "audio",
        "voice",
        "photo",
        "animation",
        "sticker",
        "video_note",
    ):
        value = getattr(message, name, None)
        if value:
            return name, value
    return None, None


def payload_size(payload) -> int:
    return int(getattr(payload, "file_size", 0) or 0)


def payload_name(kind: str, payload, message: Message) -> str:
    if getattr(payload, "file_name", None):
        return payload.file_name
    extension = {
        "photo": ".jpg",
        "voice": ".ogg",
        "video_note": ".mp4",
        "sticker": ".webp" if not getattr(payload, "is_animated", False) else ".tgs",
    }.get(kind, "")
    return f"{kind}_{message.id}{extension}"


async def update_progress(current: int, total: int, message: Message, prefix: str) -> None:
    now = asyncio.get_running_loop().time()
    last = getattr(update_progress, "last", 0.0)
    if now - last < 2 and current != total:
        return
    update_progress.last = now
    total = total or current
    pct = (current / total * 100) if total else 0
    try:
        await message.edit_text(f"{prefix}\n{human_size(current)} / {human_size(total)} ({pct:.1f}%)")
    except MessageNotModified:
        pass


@app.on_message(filters.command(["start", "help"]))
async def start_handler(_: Client, message: Message) -> None:
    if await reject_if_not_owner(message):
        return
    ensure_dirs()
    await show_home(message)


@app.on_message(filters.command("queue"))
async def queue_command(_: Client, message: Message) -> None:
    if await reject_if_not_owner(message):
        return
    await message.reply_text(
        queue_text(session, settings.max_total_bytes),
        reply_markup=queue_keyboard(session),
    )


@app.on_message(filters.command("cancel"))
async def cancel_handler(_: Client, message: Message) -> None:
    if await reject_if_not_owner(message):
        return
    session.expecting = None
    session.expecting_item_id = None
    await show_home(message, "Input cancelled.\n\n" + home_text(session, settings.max_total_bytes))


@app.on_message(filters.text & ~filters.command(["start", "help", "queue", "cancel"]))
async def text_handler(_: Client, message: Message) -> None:
    if await reject_if_not_owner(message):
        return
    if not session.expecting:
        await show_home(message)
        return

    value = (message.text or "").strip()
    expecting = session.expecting
    item_id = session.expecting_item_id
    session.expecting = None
    session.expecting_item_id = None

    if expecting == "archive_name":
        session.archive_name = clean_filename(value, "archive")
        await show_home(message, "Archive name updated.\n\n" + home_text(session, settings.max_total_bytes))
        return
    if expecting == "password":
        session.password = value or None
        try:
            await message.delete()
        except Exception:
            log.debug("could not delete password message", exc_info=True)
        await app.send_message(
            message.chat.id,
            "Password updated.\n\n" + home_text(session, settings.max_total_bytes),
            reply_markup=home_keyboard(session),
        )
        return
    if expecting == "rename" and item_id:
        item = session.get_item(item_id)
        if item:
            item.archive_name = clean_filename(value, item.archive_name)
            await message.reply_text(item_text(item), reply_markup=item_keyboard(item))
            return
    await show_home(message)


@app.on_message(filters.media)
async def media_handler(client: Client, message: Message) -> None:
    if await reject_if_not_owner(message):
        return
    ensure_dirs()
    if session.busy:
        await message.reply_text("Compression is running. Wait for it to finish before adding files.")
        return

    kind, payload = media_payload(message)
    if not payload:
        await message.reply_text("I could not read that media type.")
        return
    size = payload_size(payload)
    if session.total_size + size > settings.max_total_bytes:
        await message.reply_text(
            "That would exceed the queue limit.\n"
            f"Current: {human_size(session.total_size)}\n"
            f"Incoming: {human_size(size)}\n"
            f"Limit: {human_size(settings.max_total_bytes)}"
        )
        return

    item_id = session.new_item_id()
    original_name = clean_filename(payload_name(kind, payload, message), f"{kind}_{message.id}")
    download_dir = session.work_root / "incoming" / item_id
    download_dir.mkdir(parents=True, exist_ok=True)
    status = await message.reply_text(f"Downloading {original_name}...")

    await client.send_chat_action(message.chat.id, ChatAction.UPLOAD_DOCUMENT)
    downloaded = await message.download(
        file_name=str(download_dir / original_name),
        progress=update_progress,
        progress_args=(status, f"Downloading {original_name}"),
    )
    if not downloaded:
        await status.edit_text("Download failed.")
        return

    path = Path(downloaded)
    item = QueueItem(
        id=item_id,
        message_id=message.id,
        media_kind=kind,
        original_name=original_name,
        archive_name=original_name,
        size=path.stat().st_size,
        path=path,
    )
    if session.total_size + item.size > settings.max_total_bytes:
        shutil.rmtree(download_dir, ignore_errors=True)
        await status.edit_text("Downloaded file exceeds the queue limit after size verification.")
        return
    session.add_item(item)
    await status.edit_text(
        f"Added to queue: {item.archive_name}\n"
        f"Queue: {len(session.items)} files, {human_size(session.total_size)}",
        reply_markup=home_keyboard(session),
    )


@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery) -> None:
    if await reject_if_not_owner(query):
        return
    data = query.data or ""
    await query.answer()

    if data == "noop":
        return
    if session.busy and data != "home":
        await query.answer("Compression is running.", show_alert=True)
        return
    if data == "home":
        await show_home(query)
        return
    if data == "queue":
        await query.message.edit_text(
            queue_text(session, settings.max_total_bytes),
            reply_markup=queue_keyboard(session),
        )
        return
    if data == "clear":
        session.clear()
        await show_home(query, "Queue cleared.\n\n" + home_text(session, settings.max_total_bytes))
        return
    if data == "set_name":
        session.expecting = "archive_name"
        await query.message.edit_text("Send the archive name. Use /cancel to stop.")
        return
    if data == "set_password":
        session.expecting = "password"
        await query.message.edit_text(
            "Send the password. The bot will try to delete that message after saving it.",
            reply_markup=password_keyboard(session.has_password),
        )
        return
    if data == "clear_password":
        session.password = None
        await show_home(query, "Password cleared.\n\n" + home_text(session, settings.max_total_bytes))
        return
    if data == "mode":
        await query.message.edit_text(
            f"Choose compression mode.\nCurrent: {session.compression_format}",
            reply_markup=mode_keyboard(session.compression_format),
        )
        return
    if data.startswith("mode_set:"):
        session.compression_format = data.split(":", 1)[1]
        await show_home(query, "Compression mode updated.\n\n" + home_text(session, settings.max_total_bytes))
        return
    if data.startswith("item:"):
        item = session.get_item(data.split(":", 1)[1])
        if item:
            await query.message.edit_text(item_text(item), reply_markup=item_keyboard(item))
        return
    if data.startswith("remove:"):
        session.remove_item(data.split(":", 1)[1])
        await query.message.edit_text(
            queue_text(session, settings.max_total_bytes),
            reply_markup=queue_keyboard(session),
        )
        return
    if data.startswith("rename:"):
        session.expecting = "rename"
        session.expecting_item_id = data.split(":", 1)[1]
        await query.message.edit_text("Send the new file name inside the archive. Use /cancel to stop.")
        return
    if data.startswith("move:"):
        _, item_id, offset = data.split(":", 2)
        session.move_item(item_id, int(offset))
        item = session.get_item(item_id)
        if item:
            await query.message.edit_text(item_text(item), reply_markup=item_keyboard(item))
        return
    if data == "compress":
        await run_compression(client, query)


async def run_compression(client: Client, query: CallbackQuery) -> None:
    if not session.items:
        await query.answer("Queue is empty.", show_alert=True)
        return
    session.busy = True
    out_dir = session.work_root / "out"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        await query.message.edit_text(
            "Compressing...\n"
            f"Files: {len(session.items)}\n"
            f"Input size: {human_size(session.total_size)}"
        )
        result = await compress_session(session, out_dir)
        output_size = result.path.stat().st_size
        if output_size > settings.max_total_bytes:
            await query.message.edit_text(
                "Archive created but is larger than the configured upload limit.\n"
                f"Output: {human_size(output_size)}\n"
                f"Limit: {human_size(settings.max_total_bytes)}"
            )
            return
        await query.message.edit_text(
            f"Uploading {result.path.name}...\n"
            f"Output: {human_size(output_size)}\n"
            f"Format: {result.format}"
        )
        await client.send_chat_action(query.message.chat.id, ChatAction.UPLOAD_DOCUMENT)
        await client.send_document(
            query.message.chat.id,
            document=str(result.path),
            caption=(
                f"{result.path.name}\n"
                f"{len(session.items)} files\n"
                f"{human_size(session.total_size)} -> {human_size(output_size)}"
            ),
            progress=update_progress,
            progress_args=(query.message, f"Uploading {result.path.name}"),
        )
        session.clear()
        result.path.unlink(missing_ok=True)
        await show_home(query, "Done. Queue cleared.\n\n" + home_text(session, settings.max_total_bytes))
    except Exception as exc:
        log.exception("compression failed")
        await query.message.edit_text(f"Compression failed: {exc}")
    finally:
        session.busy = False


def main() -> None:
    ensure_dirs()
    log.info("Starting ZipBot for owners %s", ", ".join(str(owner) for owner in settings.owner_ids))
    app.run()
