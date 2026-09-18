<div align="center">

# 🎵 音波 · SpotiFLAC Bot

### High-Fidelity Lossless FLAC Music Delivery Bot for Telegram

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Telegram](https://img.shields.io/badge/Telegram-Bot%20API-24A1DE?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![SpotiFLAC](https://img.shields.io/badge/SpotiFLAC-v4.2+-7b97ed?style=for-the-badge)](https://github.com/BartolomeoRusso9/SpotiFLAC-Module-Version)
[![License](https://img.shields.io/badge/License-MIT-a6e3a1?style=for-the-badge)](LICENSE)

[⚡ Quickstart](#-quickstart) • [✨ Features](#-key-features) • [🔄 Architecture](#-system-architecture) • [🚀 Running Guide](#-running-the-bot) • [⚙️ Configuration](#%EF%B8%8F-configuration-reference)

---

</div>

> [!TIP]
> **Pure Lossless Fidelity Guaranteed**  
> Probes 24-bit Hi-Res studio masters (up to 192kHz) across **Qobuz**, **Tidal**, and **Amazon Music** before cascading gracefully to bit-perfect 16-bit / 44.1kHz CD FLAC. Zero lossy compression.

---

## ✨ Key Features

- **🎧 True Studio Lossless (24-bit & 16-bit)**: Cascades across Qobuz, Tidal, Amazon Music, and Deezer to fetch the highest available resolution master.
- **🔍 Universal Input Resolution**: Accepts Spotify links (including localized `open.spotify.com/intl-.../track/...`) or plain track titles (e.g. `Kiseki`) with automatic Spotify metadata matching.
- **📊 Real-Time Rich Progress Tickers**: Animated Unicode block gauges (`[████████░░░░]`) updating live every 3.5s with transferred MB, line speed, and ETA calculations.
- **📤 Streaming Upload Progress**: Tracks active HTTP transmission bytes as files stream directly to Telegram.
- **🏷️ Automated Metadata & Resolution Tags**: Inspects audio headers via `mutagen` to stamp real bit-depth and sample rates (`24-bit / 96.0 kHz FLAC`) directly on chat audio cards.
- **🛡️ Secure Whitelist Access Guard**: Restricts bot usage to authorized Telegram user IDs.
- **🧹 Instant Atomic Cleanup**: Temporary session directories are wiped immediately upon delivery, keeping VPS disk footprint minimal.
- **⚙️ Clean TOML Configuration**: Structured application settings separated into `config.toml` via native `tomllib`, keeping `.env` strictly for secrets.

---

## 🔄 System Architecture

```text
               ┌───────────────────────────────┐
               │    Telegram User Message      │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │      Auth Whitelist Guard     │
               └───────────────┬───────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            │                                     │
   [Spotify Link]                         [Track / Artist Name]
            │                                     │
            ▼                                     ▼
┌───────────────────────┐             ┌───────────────────────┐
│ Clean URL Normalizer  │             │ Spotify Search Client │
└───────────┬───────────┘             └───────────┬───────────┘
            │                                     │
            └──────────────────┬──────────────────┘
                               │
                               ▼
        ┌─────────────────────────────────────────────┐
        │       Multi-Pass Quality Cascading          │
        │                                             │
        │  Pass 1: 24-bit Hi-Res (Qobuz / Tidal / AM) │
        │  Pass 2: 16-bit CD FLAC (Lossless Fallback) │
        └──────────────────────┬──────────────────────┘
                               │
                               ▼
        ┌─────────────────────────────────────────────┐
        │        Real-Time Progress Ticker            │
        │   [██████████░░░░] 70% · 3.8 MB/s · ETA     │
        └──────────────────────┬──────────────────────┘
                               │
                               ▼
        ┌─────────────────────────────────────────────┐
        │       Streaming Telegram Audio Delivery     │
        │        + Tag Inspection (Mutagen)           │
        └──────────────────────┬──────────────────────┘
                               │
                               ▼
        ┌─────────────────────────────────────────────┐
        │          Atomic Session Cleanup             │
        └─────────────────────────────────────────────┘
```

---

## ⚡ Quickstart

### 1. Clone & Install Dependencies

Managed exclusively with [`uv`](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/Praveensenpai/spotiflac-bot.git
cd spotiflac-bot
uv sync
```

### 2. Configure Credentials & Settings

```bash
# Copy templates
cp .env.example .env
cp config.example.toml config.toml
```

1. Add your Telegram Bot token in `.env`:
   ```env
   BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
   ```

2. Add your Telegram User ID in `config.toml`:
   ```toml
   [bot]
   allowed_user_ids = [12345678888]
   ```

---

## 🚀 Running the Bot

### Option A: Run Interactively in Terminal

To start the bot directly in your active shell:

```bash
cd /home/paisen/Projects/spotiflac-bot
uv run python -m spotiflac_bot
```

---

### Option B: Headless Linux VPS / 24/7 Background Service

On headless Linux servers, Cloudflare Turnstile challenges block standard headless browsers. SpotiFLAC solves this autonomously by detecting headless environments, automatically launching a virtual display via **Xvfb** (`:99`), and driving Chromium offscreen without needing a physical monitor.

#### 1. Install VPS System Dependencies

```bash
# Ubuntu / Debian VPS
sudo apt-get update && sudo apt-get install -y \
  curl \
  git \
  ffmpeg \
  nodejs \
  npm \
  xvfb \
  chromium-browser

# If your distro lacks the chromium-browser apt package:
# wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
# sudo apt-get install -y ./google-chrome-stable_current_amd64.deb
```

#### 2. Deploy Systemd Service

A production-ready unit file is included at [`spotiflac-bot.service`](spotiflac-bot.service):

```bash
# 1. Copy unit file to systemd directory
sudo cp spotiflac-bot.service /etc/systemd/system/

# 2. Adjust User and WorkingDirectory to match your server path
sudo nano /etc/systemd/system/spotiflac-bot.service

# 3. Reload systemd & start bot
sudo systemctl daemon-reload
sudo systemctl enable --now spotiflac-bot

# 4. Monitor live service logs
journalctl -u spotiflac-bot -f
```

#### 3. Managing the Service
```bash
sudo systemctl restart spotiflac-bot   # Restart bot
sudo systemctl stop spotiflac-bot      # Stop bot
sudo systemctl status spotiflac-bot    # View status
```

---

## ⚙️ Configuration Reference

### Secrets: [`.env`](.env)

| Variable | Type | Description |
| :--- | :--- | :--- |
| `BOT_TOKEN` | `string` | **Required**. Telegram Bot token obtained from [@BotFather](https://t.me/BotFather). |

---

### Application Settings: [`config.toml`](config.toml)

```toml
[bot]
# Whitelist of Telegram user IDs permitted to interact with the bot.
# Leave empty ([]) to allow all users.
allowed_user_ids = [8703708885]

[download]
# Temporary directory where downloads are staged prior to Telegram upload.
download_dir = "/tmp/spotiflac"

# Telegram max file size threshold in MB (Telegram hard limit is 50 MB).
max_file_mb = 49

# Target quality tier:
# - "HI_RES_LOSSLESS": 24-bit Hi-Res master (up to 192kHz) -> cascades to 16-bit FLAC
# - "DOLBY_ATMOS": Dolby Atmos spatial audio -> cascades to 24-bit -> 16-bit FLAC
# - "LOSSLESS": Standard 16-bit / 44.1kHz CD quality FLAC
quality = "HI_RES_LOSSLESS"

# Automatically step down quality tier if highest resolution is unavailable.
allow_fallback = true

# Priority-ordered list of pure lossless FLAC providers.
services = [
    "qobuz-web",
    "tidal-web",
    "amazon",
    "deezer",
]

[extensions]
# Remote community registries used to bootstrap SpotiFLAC download extensions.
registries = [
    "https://raw.githubusercontent.com/zarzet/SpotiFLAC-Extension/main/registry.json",
]
```

---

## 🛠️ Tech Stack & Engineering Standards

- **Runtime**: Python 3.12+ (100% type annotated, `mypy --strict` compliant)
- **Tooling**: Managed exclusively via [`uv`](https://docs.astral.sh/uv/) and [`ruff`](https://docs.astral.sh/ruff/)
- **Libraries**: `python-telegram-bot[job-queue]`, `SpotiFLAC`, `mutagen`, `aiofiles`, `tomllib`
- **Design Philosophy**: Role-based domain architecture (`models/`, `services/`, `bot/`) adhering strictly to clean code boundaries (<300 lines/file, <45 lines/function).

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.
