# ZipBot

A single-user Telegram bot for collecting files into a queue, reviewing the queue, and producing a compressed archive. It uses Pyrofork for Telegram media handling and `py7zr`/standard library archivers for compression.

## Features

- Accepts forwarded or directly uploaded Telegram media: documents, videos, audio, voice notes, photos, animations, stickers, and video notes.
- Queue UI with Telegram inline buttons: view files, remove files, rename queued files, move files up/down, clear queue, set archive name, set/clear password, choose compression mode, and start compression.
- Tracks total queued source size and blocks queues above the configured 2 GB limit.
- Automatic compression choice:
  - Uses encrypted `.7z` when a password is set.
  - Uses fast stored `.zip` for already-compressed media when no password is set.
  - Uses high-compression `.7z` for mixed or compressible input.
- Owner-only access through `OWNER_ID`.

## Setup

1. Create a bot with BotFather and get the bot token.
2. Create Telegram API credentials at `my.telegram.org` and get `API_ID` and `API_HASH`.
3. Copy `.env.example` to `.env` and fill in the values.
4. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

5. Run the bot:

```bash
python -m zipbot
```

## Notes

- Telegram’s public Bot API documents a 2000 MB upload limit when using a local Bot API server. Pyrofork uses Telegram’s MTProto client API path, but keeping the queue below 2 GB is still the practical target for bot uploads.
- Telegram Bot API 9.4 added button `style` and `icon_custom_emoji_id` fields. Pyrofork inline keyboards may not expose those Bot API-only fields everywhere yet, so this bot uses strong labels and layout for a polished UI while staying compatible.
- Password-protected archives are created as `.7z` archives with encrypted headers.
