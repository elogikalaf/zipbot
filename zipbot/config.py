from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    bot_token: str
    owner_id: int
    work_dir: Path
    max_total_bytes: int
    default_format: str
    default_level: int


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    load_dotenv()
    work_dir = Path(os.getenv("WORK_DIR", "./data")).resolve()
    return Settings(
        api_id=int(_required("API_ID")),
        api_hash=_required("API_HASH"),
        bot_token=_required("BOT_TOKEN"),
        owner_id=int(_required("OWNER_ID")),
        work_dir=work_dir,
        max_total_bytes=int(os.getenv("MAX_TOTAL_BYTES", "2147483648")),
        default_format=os.getenv("DEFAULT_FORMAT", "auto").lower(),
        default_level=int(os.getenv("DEFAULT_LEVEL", "9")),
    )
