from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import time
from collections.abc import Callable

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from spotiflac_bot.bot.progress import (
    ProgressCardData,
    TrackedFileReader,
    esc_md,
    render_progress_card,
)
from spotiflac_bot.config import settings
from spotiflac_bot.exceptions import (
    DownloadFailedError,
    FileTooLargeError,
    UnauthorizedUserError,
)
from spotiflac_bot.models.download import (
    DownloadRequest,
    DownloadResult,
    ProgressUpdate,
)
from spotiflac_bot.services.downloader import cleanup_session, download_track
from spotiflac_bot.services.resolver import resolve_query_to_track_url

log = logging.getLogger(__name__)

_WELCOME = (
    "🎵 *SpotiFLAC Bot*\n\n"
    "Send me:\n"
    "• A Spotify track / album / playlist URL\n"
    "• Or a song name — I'll find it for you\n\n"
    "I'll download the lossless FLAC and send it right here. 🎧"
)

_SEARCHING = "🔍 Searching Spotify for match…"
_DOWNLOADING = "⏳ Probing providers for highest resolution FLAC…"


def _is_authorized(user_id: int) -> bool:
    if not settings.allowed_user_ids:
        return True
    return user_id in settings.allowed_user_ids


def _guard(update: Update) -> tuple[Message, int]:
    if update.message is None or update.effective_user is None:
        raise ValueError("Update has no message or user")
    user_id = update.effective_user.id
    if not _is_authorized(user_id):
        raise UnauthorizedUserError(f"User {user_id} not in whitelist")
    return update.message, user_id


async def _run_upload_ticker(
    status: Message,
    result: DownloadResult,
    get_bytes: Callable[[], int],
    stop_event: asyncio.Event,
) -> None:
    start_time = time.time()
    last_b = 0
    last_t = start_time
    total = result.file_size_bytes

    while not stop_event.is_set():
        try:
            await asyncio.sleep(3.5)
            if stop_event.is_set():
                break
            now = time.time()
            cur_b = get_bytes()
            dt = now - last_t
            spd = ((cur_b - last_b) / (1024 * 1024)) / dt if dt > 0 else 0.0
            last_b = cur_b
            last_t = now

            card = render_progress_card(
                ProgressCardData(
                    stage_icon="📤",
                    stage_name="Uploading to Telegram",
                    title=result.title,
                    artist=result.artist,
                    resolution=result.resolution,
                    bytes_done=cur_b,
                    total_bytes=total,
                    speed_mbps=round(spd, 2),
                    elapsed_seconds=int(now - start_time),
                )
            )
            with contextlib.suppress(Exception):
                await status.edit_text(card, parse_mode=ParseMode.MARKDOWN_V2)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


async def _send_audio_result(
    message: Message,
    status: Message,
    result: DownloadResult,
) -> None:
    total_bytes = result.file_size_bytes
    uploaded_bytes = 0

    def _on_chunk(count: int) -> None:
        nonlocal uploaded_bytes
        uploaded_bytes = count

    stop_event = asyncio.Event()
    ticker = asyncio.create_task(
        _run_upload_ticker(status, result, lambda: uploaded_bytes, stop_event)
    )

    try:
        with io.FileIO(str(result.file_path), "rb") as raw_f:
            tracked_io = TrackedFileReader(raw_f, total_bytes, _on_chunk)
            res_badge = (
                f"\n✨ `{esc_md(result.resolution)}`" if result.resolution else ""
            )
            caption = (
                f"🎵 *{esc_md(result.title)}*\n"
                f"👤 {_esc(result.artist)}"
                f"{res_badge}\n"
                f"💾 `{total_bytes // (1024 * 1024)} MB`"
            )
            await message.reply_audio(
                audio=tracked_io,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN_V2,
                filename=result.file_path.name,
            )
    finally:
        stop_event.set()
        ticker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ticker


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        message, _ = _guard(update)
    except UnauthorizedUserError:
        if update.message:
            await update.message.reply_text(
                "⛔ You are not authorized to use this bot."
            )
        return
    await message.reply_text(_WELCOME, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        message, user_id = _guard(update)
    except UnauthorizedUserError:
        if update.message:
            await update.message.reply_text(
                "⛔ You are not authorized to use this bot."
            )
        return

    text = (message.text or "").strip()
    if not text:
        return

    status = await message.reply_text(_SEARCHING)
    resolved = await resolve_query_to_track_url(text)
    if not resolved:
        await status.edit_text(
            f"❌ Could not find a Spotify track for: `{_esc(text)}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    track_url, title, artist = resolved
    await status.edit_text(
        f"🎯 Found: *{_esc(title or 'Track')}* — {_esc(artist or '')}\n{_DOWNLOADING}",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    async def _on_progress(prog: ProgressUpdate) -> None:
        card = render_progress_card(
            ProgressCardData(
                stage_icon="📥",
                stage_name="Downloading FLAC",
                title=title,
                artist=artist,
                resolution="",
                bytes_done=prog.downloaded_bytes,
                total_bytes=prog.total_bytes,
                speed_mbps=prog.speed_mbps,
                elapsed_seconds=prog.elapsed_seconds,
            )
        )
        with contextlib.suppress(Exception):
            await status.edit_text(card, parse_mode=ParseMode.MARKDOWN_V2)

    request = DownloadRequest(user_id=user_id, query=track_url, is_url=True)

    try:
        result = await download_track(request, on_progress=_on_progress)
        await _send_audio_result(message, status, result)
        await status.delete()
        cleanup_session(result)

    except FileTooLargeError as exc:
        log.warning("File too large for user %s: %s", user_id, exc)
        await status.edit_text(
            "⚠️ File is too large to send via Telegram \\(\\>50 MB\\)\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except DownloadFailedError as exc:
        log.error("Download failed for user %s: %s", user_id, exc)
        await status.edit_text(
            "❌ Download failed\\. "
            "Make sure the link is valid and providers are configured\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception:
        log.exception("Unexpected error for user %s", user_id)
        await status.edit_text("💥 Something went wrong\\. Please try again later\\.")


def _esc(text: str) -> str:
    """Escape special MarkdownV2 characters."""
    return esc_md(text)
