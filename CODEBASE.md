# CODEBASE.md: spotiflac-bot Semantic Digest

> **Notice**: AI-optimized semantic index. No narrative prose. Keep token density high.

## 1. System Topology & Data Flow

```text
Telegram Update ──► handlers.py (_guard → handle_message)
                         │
                    resolver.py (is_spotify_url / extract_spotify_url)
                         │
                    downloader.py (download_track → SpotiFLAC[sync] in executor)
                         │
                    Telegram (reply_audio) ──► cleanup_session()
```

## 2. Global Constraints & Architecture Patterns

- **Language**: Python 3.12, uv-managed
- **Paradigm**: Role-based — `models/`, `services/`, `bot/`
- **Hard Limits**: <300 lines/file, <45 lines/fn, max 4 params, max 3 nesting depth
- **Tooling**: ruff (lint+format), mypy strict, python-telegram-bot v22, SpotiFLAC v4
- **SpotiFLAC**: sync-only library — always wrapped in `loop.run_in_executor`

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

### `src/spotiflac_bot/config.py` (Role: infra, Lines: 48)
- **Responsibility**: Load `.env` → frozen `Settings` dataclass singleton.
- **Imports**: `os`, `dataclasses`, `pathlib`, `dotenv`
- **Types**:
  ```python
  @dataclass(frozen=True)
  class Settings:
      bot_token: str
      allowed_user_ids: list[int]
      download_dir: Path
      services: list[str]
      max_file_bytes: int
  ```
- **Public**: `Settings.from_env() -> Settings`, module-level `settings: Settings`
- **Side Effects**: reads env vars, calls `load_dotenv()`

### `src/spotiflac_bot/models/download.py` (Role: domain, Lines: 18)
- **Responsibility**: Pure immutable DTOs — no I/O.
- **Types**:
  ```python
  @dataclass(frozen=True)
  class DownloadRequest:
      user_id: int; query: str; is_url: bool

  @dataclass(frozen=True)
  class DownloadResult:
      file_path: Path; title: str; artist: str; file_size_bytes: int
  ```

### `src/spotiflac_bot/services/resolver.py` (Role: domain, Lines: 14)
- **Responsibility**: Spotify URL detection via regex — no I/O.
- **Public**:
  ```python
  def is_spotify_url(text: str) -> bool
  def extract_spotify_url(text: str) -> str | None
  ```

### `src/spotiflac_bot/services/downloader.py` (Role: infra, Lines: 58)
- **Responsibility**: Wraps sync SpotiFLAC in async executor; manages session dirs.
- **Imports**: `asyncio`, `shutil`, `uuid`, `SpotiFLAC`, `settings`, exceptions, models
- **Public**:
  ```python
  async def download_track(request: DownloadRequest) -> DownloadResult
  def cleanup_session(result: DownloadResult) -> None
  ```
- **Side Effects**: creates/deletes `settings.download_dir/<uuid>/`, calls SpotiFLAC sync

### `src/spotiflac_bot/bot/keyboards.py` (Role: api, Lines: 22)
- **Responsibility**: Inline keyboard factory functions.
- **Public**:
  ```python
  def provider_keyboard() -> InlineKeyboardMarkup
  def cancel_keyboard() -> InlineKeyboardMarkup
  ```

### `src/spotiflac_bot/bot/handlers.py` (Role: api, Lines: 131)
- **Responsibility**: All Telegram update handlers — auth guard, download flow, upload.
- **Public**:
  ```python
  async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None
  async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None
  async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None
  ```
- **Private**: `_guard(update) -> tuple[Message, int]`, `_esc(text: str) -> str`
- **Side Effects**: Telegram API calls (reply_text, reply_audio, edit_text, delete)

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

## 4. Execution Lifecycle

1. `__main__.py` → `run()`
2. `run()` configures logging, ensures `download_dir` exists, calls `build_app().run_polling()`
3. Telegram update → `handle_message` → `_guard()` checks whitelist
4. `resolver.py` detects URL vs search term
5. `download_track()` spawns SpotiFLAC in thread executor → writes FLAC to session dir
6. Bot sends audio file via `reply_audio`, then `cleanup_session()` removes temp dir

## 5. Verification Commands

```bash
uv run ruff check --fix src/ && uv run ruff format src/
uv run mypy src/
uv run python -m spotiflac_bot
```

## 6. Recent Changes

- **2026-09-18**: Added `spotiflac-bot.service` unit template for systemd VPS deployment. Verified live token connection to Telegram API (@spotiflacdesubot).
- **2026-09-18**: Initial project scaffold — all modules written, ruff+mypy green.
