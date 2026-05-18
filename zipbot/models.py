from __future__ import annotations

import re
import secrets
import shutil
from dataclasses import dataclass, field
from pathlib import Path


SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._() -]+")


def clean_filename(name: str, fallback: str = "file") -> str:
    name = name.strip().replace("/", "_").replace("\\", "_")
    name = SAFE_NAME_RE.sub("_", name)
    name = name.strip(" .")
    return name or fallback


def human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


@dataclass
class QueueItem:
    id: str
    message_id: int
    media_kind: str
    original_name: str
    archive_name: str
    size: int
    path: Path


@dataclass
class BotSession:
    owner_id: int
    work_root: Path
    archive_name: str = "archive"
    password: str | None = None
    compression_format: str = "auto"
    compression_level: int = 9
    items: list[QueueItem] = field(default_factory=list)
    expecting: str | None = None
    expecting_item_id: str | None = None
    busy: bool = False

    @property
    def total_size(self) -> int:
        return sum(item.size for item in self.items)

    @property
    def has_password(self) -> bool:
        return bool(self.password)

    def new_item_id(self) -> str:
        return secrets.token_hex(4)

    def add_item(self, item: QueueItem) -> None:
        existing_names = {queued.archive_name for queued in self.items}
        base = clean_filename(item.archive_name)
        candidate = base
        stem = Path(base).stem
        suffix = Path(base).suffix
        index = 2
        while candidate in existing_names:
            candidate = f"{stem} ({index}){suffix}"
            index += 1
        item.archive_name = candidate
        self.items.append(item)

    def remove_item(self, item_id: str) -> QueueItem | None:
        for index, item in enumerate(self.items):
            if item.id == item_id:
                removed = self.items.pop(index)
                removed.path.unlink(missing_ok=True)
                return removed
        return None

    def get_item(self, item_id: str) -> QueueItem | None:
        return next((item for item in self.items if item.id == item_id), None)

    def move_item(self, item_id: str, offset: int) -> bool:
        for index, item in enumerate(self.items):
            if item.id != item_id:
                continue
            new_index = max(0, min(len(self.items) - 1, index + offset))
            if new_index == index:
                return False
            self.items.pop(index)
            self.items.insert(new_index, item)
            return True
        return False

    def clear(self) -> None:
        for item in self.items:
            item.path.unlink(missing_ok=True)
        self.items.clear()

    def cleanup_all(self) -> None:
        if self.work_root.exists():
            shutil.rmtree(self.work_root, ignore_errors=True)
