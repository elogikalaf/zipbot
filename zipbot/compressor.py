from __future__ import annotations

import asyncio
import mimetypes
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import py7zr

from .models import BotSession, clean_filename


ARCHIVE_EXTENSIONS = {
    ".7z",
    ".zip",
    ".rar",
    ".gz",
    ".bz2",
    ".xz",
    ".zst",
    ".tar",
    ".tgz",
    ".tbz2",
    ".txz",
    ".apk",
    ".ipa",
    ".jar",
    ".war",
    ".whl",
}

MEDIA_PREFIXES = ("audio/", "image/", "video/")


@dataclass(frozen=True)
class CompressionResult:
    path: Path
    format: str


def looks_already_compressed(path: Path) -> bool:
    suffixes = {suffix.lower() for suffix in path.suffixes}
    if suffixes & ARCHIVE_EXTENSIONS:
        return True
    mime_type, _ = mimetypes.guess_type(path.name)
    return bool(mime_type and mime_type.startswith(MEDIA_PREFIXES))


def choose_format(session: BotSession) -> str:
    requested = session.compression_format
    if session.password:
        return "7z"
    if requested in {"7z", "zip", "tar.gz"}:
        return requested
    if session.items and all(looks_already_compressed(item.path) for item in session.items):
        return "zip"
    return "7z"


def archive_path(output_dir: Path, archive_name: str, archive_format: str) -> Path:
    name = clean_filename(archive_name, "archive")
    suffix = ".tar.gz" if archive_format == "tar.gz" else f".{archive_format}"
    lowered = name.lower()
    for existing_suffix in (".tar.gz", ".7z", ".zip"):
        if lowered.endswith(existing_suffix):
            name = name[: -len(existing_suffix)]
            break
    return output_dir / f"{name}{suffix}"


def _write_zip(session: BotSession, output_path: Path) -> None:
    compression = zipfile.ZIP_DEFLATED
    compresslevel = session.compression_level
    if all(looks_already_compressed(item.path) for item in session.items):
        compression = zipfile.ZIP_STORED
        compresslevel = None
    with zipfile.ZipFile(output_path, "w", compression=compression, compresslevel=compresslevel) as archive:
        for item in session.items:
            archive.write(item.path, arcname=item.archive_name)


def _write_tar_gz(session: BotSession, output_path: Path) -> None:
    with tarfile.open(output_path, "w:gz", compresslevel=session.compression_level) as archive:
        for item in session.items:
            archive.add(item.path, arcname=item.archive_name, recursive=False)


def _write_7z(session: BotSession, output_path: Path) -> None:
    filters = [{"id": py7zr.FILTER_LZMA2, "preset": session.compression_level}]
    with py7zr.SevenZipFile(
        output_path,
        "w",
        filters=filters,
        password=session.password,
        header_encryption=bool(session.password),
    ) as archive:
        for item in session.items:
            archive.write(item.path, arcname=item.archive_name)


async def compress_session(session: BotSession, output_dir: Path) -> CompressionResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_format = choose_format(session)
    output_path = archive_path(output_dir, session.archive_name, archive_format)
    if output_path.exists():
        output_path.unlink()

    def run() -> None:
        if archive_format == "zip":
            _write_zip(session, output_path)
        elif archive_format == "tar.gz":
            _write_tar_gz(session, output_path)
        else:
            _write_7z(session, output_path)

    await asyncio.to_thread(run)
    return CompressionResult(path=output_path, format=archive_format)
