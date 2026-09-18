# CODEBASE.md: spotiflac-bot Semantic Digest

> **Notice**: AI-optimized semantic index. No narrative prose. Keep token density high.

## 1. System Topology & Data Flow

```text
Telegram Update ──► handlers.py (_guard → handle_message)
                         │
                    resolver.py (resolve_query_to_track_url → SpotifyMetadataClient)
                         │
                    downloader.py (download_track → SpotiFLAC in executor)
                         │
                    audio_meta.py (collect_metadata, detect_duration, extract_and_create_thumbnail)
                         │
                    Telegram (reply_audio with thumbnail, tags, duration) ──► cleanup_session()
```

## 2. Global Constraints & Architecture Patterns

- **Language**: Python 3.12, uv-managed
- **Paradigm**: Role-based — `models/`, `services/`, `bot/`
- **Hard Limits**: <300 lines/file, <45 lines/fn, max 4 params, max 3 nesting depth
- **Tooling**: ruff (lint+format), mypy strict, python-telegram-bot v22, SpotiFLAC v4, Pillow
- **SpotiFLAC**: sync-only library — always wrapped in `loop.run_in_executor`
- **Metadata**: Native Spotify metadata & 1500x1500px artwork prioritized; external enrichment disabled by default.

## 3. Module & Interface Skeleton

### `src/spotiflac_bot/exceptions.py` (Role: domain, Lines: 15)
- **Responsibility**: Typed exception hierarchy — no logic.
- **Types**:
  ```python
  class SpotiFlacBotError(Exception)
  class UnauthorizedUserError(SpotiFlacBotError)
  class DownloadFailedError(SpotiFlacBotError)
  class FileTooLargeError(SpotiFlacBotError)
  class InvalidInputError(SpotiFlacBotError)
  ```

### `src/spotiflac_bot/config.py` (Role: infra, Lines: 143)
- **Responsibility**: Load `config.toml` + `.env` → frozen `Settings` dataclass singleton.
- **Imports**: `os`, `tomllib`, `dataclasses`, `pathlib`, `dotenv`
- **Types**:
  ```python
  @dataclass(frozen=True)
  class DownloadConfig:
      download_dir: Path
      max_file_bytes: int
      services: list[str]
      quality: str
      allow_fallback: bool
      enrich_metadata: bool = False


  @dataclass(frozen=True)
  class Settings:
      bot_token: str
      allowed_user_ids: list[int]
      download: DownloadConfig
      registries: list[str]
  ```
- **Public Properties**: `download_dir`, `max_file_bytes`, `services`, `quality`, `allow_fallback`, `enrich_metadata`
- **Side Effects**: reads `config.toml` and `.env`, calls `load_dotenv()`

### `src/spotiflac_bot/models/download.py` (Role: domain, Lines: 32)
- **Responsibility**: Pure immutable DTOs — no I/O.
- **Types**:
  ```python
  @dataclass(frozen=True)
  class DownloadRequest:
      user_id: int
      query: str
      is_url: bool
      expected_title: str = ""
      expected_artist: str = ""


  @dataclass(frozen=True)
  class DownloadResult:
      file_path: Path
      title: str
      artist: str
      file_size_bytes: int
      resolution: str = ""
      duration_seconds: int = 0
      thumbnail_path: Path | None = None


  @dataclass(frozen=True)
  class ProgressUpdate:
      elapsed_seconds: int
      downloaded_bytes: int
      total_bytes: int | None
      speed_mbps: float
      percent: float | None
  ```

### `src/spotiflac_bot/services/resolver.py` (Role: domain, Lines: 63)
- **Responsibility**: Spotify URL detection and native Spotify metadata resolution.
- **Imports**: `logging`, `re`, `SpotiFLAC.core.spotify_metadata.SpotifyMetadataClient`
- **Public**:
  ```python
  def is_spotify_url(text: str) -> bool
  def extract_spotify_url(text: str) -> str | None
  async def resolve_query_to_track_url(query: str) -> tuple[str, str, str] | None
  ```

### `src/spotiflac_bot/services/audio_meta.py` (Role: infra, Lines: 146)
- **Responsibility**: Audio header inspection, duration extraction, Vorbis/ID3 tag reading, and 320x320 JPEG thumbnail generation for Telegram.
- **Imports**: `contextlib`, `io`, `logging`, `pathlib`, `mutagen.flac.FLAC`, `mutagen.mp3.MP3`, `mutagen.easyid3.EasyID3`, `PIL.Image`
- **Public**:
  ```python
  def detect_resolution(file_path: Path) -> str
  def detect_duration_seconds(file_path: Path) -> int
  def collect_metadata(file_path: Path, expected_title: str = "", expected_artist: str = "") -> tuple[str, str]
  def extract_and_create_thumbnail(file_path: Path) -> Path | None
  ```

### `src/spotiflac_bot/services/downloader.py` (Role: infra, Lines: 212)
- **Responsibility**: Wraps sync SpotiFLAC in async executor; multi-tier quality probing, progress monitoring, and session dirs.
- **Imports**: `asyncio`, `shutil`, `uuid`, `SpotiFLAC`, `audio_meta`, `settings`, exceptions, models
- **Public**:
  ```python
  def ensure_extensions() -> None
  async def download_track(request: DownloadRequest, on_progress: Callable | None = None) -> DownloadResult
  def cleanup_session(result: DownloadResult) -> None
  ```
- **Side Effects**: creates/deletes `settings.download_dir/<uuid>/`, spawns SpotiFLAC with `enrich_metadata` setting

### `src/spotiflac_bot/bot/keyboards.py` (Role: api, Lines: 22)
- **Responsibility**: Inline keyboard factory functions.
- **Public**:
  ```python
  def provider_keyboard() -> InlineKeyboardMarkup
  def cancel_keyboard() -> InlineKeyboardMarkup
  ```

### `src/spotiflac_bot/bot/handlers.py` (Role: api, Lines: 255)
- **Responsibility**: Telegram update handlers — auth guard, download dispatch, upload with audio thumbnail and player metadata.
- **Public**:
  ```python
  async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None
  async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None
  async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None
  ```
- **Private**: `_guard(update) -> tuple[Message, int]`, `_send_audio_result(...)`
- **Side Effects**: Telegram API calls (reply_text, reply_audio, edit_text, delete)

### `src/spotiflac_bot/bot/progress.py` (Role: api, Lines: 98)
- **Responsibility**: Rich Unicode progress card rendering and upload stream byte tracking.
- **Types**: `ProgressCardData`, `TrackedFileReader`
- **Public**: `format_size`, `format_time`, `render_bar`, `esc_md`, `render_progress_card`

### `src/spotiflac_bot/bot/app.py` (Role: api, Lines: 26)
- **Responsibility**: Application factory + run() entry point.
- **Public**:
  ```python
  def build_app() -> Application
  def run() -> None
  ```

### `src/spotiflac_bot/__main__.py` (Role: cli, Lines: 4)
- **Responsibility**: `python -m spotiflac_bot` entrypoint.
- **Calls**: `bot.app.run()`

### `install.sh` (Role: cli/infra, Lines: 230)
- **Responsibility**: Production-grade automated installer & systemd setup script (`set -euo pipefail`).
- **Functionality**: Auto-installs system packages (`xvfb`, `ffmpeg`, `chromium`, `curl`, `git`), installs `uv`, runs `uv sync`, interactively prompts for `BOT_TOKEN` and whitelist `allowed_user_ids` into `.env` and `config.toml`, and configures & enables `/etc/systemd/system/spotiflac-bot.service` with `DISPLAY=:99`.
- **Side Effects**: Installs system packages via `apt`, modifies systemd unit files, enables service.

## 4. Execution Lifecycle

1. `__main__.py` → `run()`
2. `run()` configures logging, ensures `download_dir` exists, calls `build_app().run_polling()`
3. Telegram update → `handle_message` → `_guard()` checks whitelist
4. `resolver.py` detects URL vs search term; queries `SpotifyMetadataClient` for native title and artist
5. `download_track()` spawns SpotiFLAC with native Spotify tagging (`enrich_metadata=false`)
6. `audio_meta.py` reads duration, verifies Vorbis/ID3 tags, and extracts/resizes front cover to 320x320 JPEG
7. Bot sends audio file via `reply_audio(thumbnail=thumb, title=title, performer=artist, duration=dur)`
8. `cleanup_session()` cleans up temp session folder

## 5. Verification Commands

```bash
uv run ruff check --fix && uv run ruff check --select I --fix && uv run ruff format
uv run mypy .
uv run python -m spotiflac_bot
```

## 6. Recent Changes

- **2026-09-18**: Created production-grade `install.sh` and modernized `README.md`:
  - Added fully automated installer script `install.sh` adhering to `bash-clean-code` (`set -euo pipefail`, cleanup traps, TTY awareness).
  - Automatically installs system dependencies (`xvfb`, `ffmpeg`, `chromium-browser`), `uv`, synchronizes project virtualenv, prompts for `BOT_TOKEN`, and deploys & enables `/etc/systemd/system/spotiflac-bot.service` with `DISPLAY=:99`.
  - Added `🪄 One-Liner Magic` quickstart snippet to `README.md` and updated `spotiflac-bot.service` template.
- **2026-09-18**: Fixed inaccurate cover art and metadata:
  - Extracted audio metadata and thumbnail logic into dedicated `services/audio_meta.py` module (<150 lines).
  - Added native Spotify metadata resolution for direct Spotify URLs in `services/resolver.py`.
  - Added configurable `enrich_metadata = false` in `config.toml` and `config.py` to prevent Deezer/Apple Music from overwriting Spotify's native cover art and tags.
  - Added automatic front cover extraction and 320x320 JPEG thumbnail generation via Pillow in `audio_meta.py`.
  - Updated `reply_audio` in `bot/handlers.py` to explicitly supply `thumbnail`, `title`, `performer`, and `duration` so Telegram clients display the cover artwork and player metadata.
  - Extended `DownloadRequest` (`expected_title`, `expected_artist`) and `DownloadResult` (`duration_seconds`, `thumbnail_path`).
- **2026-09-18**: Documented headless Linux VPS deployment and autonomous Cloudflare challenge bypass via Xvfb (`:99`) and off-screen Chromium in `README.md` and `spotiflac-bot.service`.
- **2026-09-18**: Added rich Unicode block progress bar (`[████████░░░░]`) and real-time streaming upload tracking via `bot/progress.py` (`TrackedFileReader`, `render_progress_card`) with transfer rate and ETA estimates.
- **2026-09-18**: Implemented multi-pass quality probing across providers (`_attempt_tier_download`, `_run_download`) to guarantee highest resolution is found first before stepping down. Added `_detect_resolution` via mutagen FLAC header inspection to show real-time bit-depth and sample rate in Telegram audio messages.
- **2026-09-18**: Added configurable audio quality tier (`quality = "HI_RES_LOSSLESS"` or `"DOLBY_ATMOS"`) and automatic cascading fallback (`allow_fallback = true`) in `config.toml`, `config.py`, and `downloader.py`.
- **2026-09-18**: Migrated structured configuration to `config.toml` via native `tomllib` (bot whitelist, download settings, lossless services, and extension registries), keeping `.env` strictly for secrets (`BOT_TOKEN`).
- **2026-09-18**: Added real-time progress ticker (`ProgressUpdate`, `_monitor_progress`) with visual ASCII progress bar, byte transfer rate, and elapsed time updated every 3.5s in Telegram.
- **2026-09-18**: Integrated SpotiFLAC extension registry (`SPOTIFLAC_REGISTRIES`) and auto-bootstrap in `app.py`. Added Spotify metadata search to `resolver.py` so song titles automatically resolve to track URLs. Expanded URL regex for regional paths (`intl-...`).
- **2026-09-18**: Added `spotiflac-bot.service` unit template for systemd VPS deployment. Verified live token connection to Telegram API (@spotiflacdesubot).
- **2026-09-18**: Initial project scaffold — all modules written, ruff+mypy green.
