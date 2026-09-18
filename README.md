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

1. **Set secrets in `.env`**:
   ```bash
   cp .env.example .env
   ```
   Add your Telegram bot token:
   ```env
   BOT_TOKEN=your_telegram_bot_token_here
   ```

2. **Customize settings in `config.toml`**:
   ```toml
   [bot]
   allowed_user_ids = [123456789] # Your Telegram user ID

   [download]
   download_dir = "/tmp/spotiflac"
   max_file_mb = 49
   services = [
       "tidal-web",
       "qobuz-web",
       "deezer",
       "amazon",
   ]

   [extensions]
   registries = [
       "https://raw.githubusercontent.com/zarzet/SpotiFLAC-Extension/main/registry.json",
   ]
   ```

### 3. Run

```bash
uv run python -m spotiflac_bot
```

---

## ⚙️ Configuration Reference

### Secrets (`.env`)
| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | **Yes** | Telegram Bot token from @BotFather |

### Application Settings (`config.toml`)
| Section | Key | Default | Description |
|---|---|---|---|
| `[bot]` | `allowed_user_ids` | `[]` *(all allowed)* | List of authorized Telegram user IDs |
| `[download]` | `download_dir` | `"/tmp/spotiflac"` | Staging directory for audio files |
| `[download]` | `max_file_mb` | `49` | Max size before Telegram limit rejection |
| `[download]` | `services` | `["tidal-web", ...]` | Lossless FLAC providers in priority order |
| `[extensions]` | `registries` | `["https://..."]` | Extension registry repository URLs |

---

## 📜 License

MIT © [Your Name](https://github.com/youruser)
