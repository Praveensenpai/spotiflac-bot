# 🎵 SpotiFLAC Bot

> **Send a Spotify link or a song name — get lossless FLAC delivered straight to Telegram.**

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![SpotiFLAC](https://img.shields.io/badge/SpotiFLAC-4.2+-7b97ed?style=for-the-badge)](https://pypi.org/project/SpotiFLAC/)
[![License](https://img.shields.io/badge/License-MIT-a6e3a1?style=for-the-badge)](LICENSE)

---

> [!TIP]
> Supports **Tidal · Qobuz · Amazon Music · Deezer** — priority-ordered, auto-fallback.

## ✨ Features

- **🔗 URL or Name** — paste a Spotify track/album/playlist URL, or just type a song name
- **🎧 True Lossless** — downloads FLAC via your configured provider extensions
- **📤 Auto-Upload** — sends the file directly to you in Telegram
- **🛡️ Whitelist Auth** — restrict access to specific Telegram user IDs
- **♻️ Auto-Cleanup** — temp files deleted immediately after upload
- **⚡ Async Core** — non-blocking; SpotiFLAC runs in a thread executor

---

## 🗂️ Architecture

```text
Telegram Update
      │
  handlers.py  ←── auth guard (_guard)
      │
  resolver.py  ←── URL or search term?
      │
  downloader.py ←── SpotiFLAC (sync → executor)
      │
  reply_audio  ──► cleanup temp dir
```

---

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone https://github.com/youruser/spotiflac-bot.git
cd spotiflac-bot
uv sync
```

### 2. Configure

```bash
cp .env.example .env
$EDITOR .env
```

Fill in your values:

```env
BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_USER_IDS=123456789        # your Telegram user ID (leave empty = allow all)
SERVICES=tidal,qobuz,amazon,deezer
DOWNLOAD_DIR=/tmp/spotiflac
MAX_FILE_MB=49
```

> [!IMPORTANT]
> You need SpotiFLAC provider extensions configured separately.
> Join [t.me/SpotiFLAC_Chat](https://t.me/SpotiFLAC_Chat) for extension setup guides.

### 3. Run

```bash
uv run python -m spotiflac_bot
```

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | **required** | BotFather token |
| `ALLOWED_USER_IDS` | *(empty = all)* | Comma-separated Telegram user IDs |
| `SERVICES` | `tidal,qobuz,amazon,deezer` | Provider priority order |
| `DOWNLOAD_DIR` | `/tmp/spotiflac` | Temp dir for downloads |
| `MAX_FILE_MB` | `49` | Reject files larger than this (Telegram cap = 50 MB) |

---

## 📜 License

MIT © [Your Name](https://github.com/youruser)
