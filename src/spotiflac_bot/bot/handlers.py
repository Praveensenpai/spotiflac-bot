from __future__ import annotations

import contextlib
import logging

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

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
_DOWNLOADING = "⏳ Downloading lossless FLAC via provider extensions…"
_UPLOADING = "📤 Download done\\! Uploading to Telegram…"


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


def _format_size(num_bytes: int) -> str:
    mb = num_bytes / (1024 * 1024)
    return f"{mb:.1f} MB"


def _format_time(seconds: int) -> str:
    mins, secs = divmod(seconds, 60)
    return f"{mins:02d}:{secs:02d}"


def _render_bar(percent: float | None, length: int = 12) -> str:
    if percent is None or percent <= 0:
        return "▱" * length
    filled = max(0, min(length, int(length * (percent / 100.0))))
    return "▰" * filled + "▱" * (length - filled)


def _format_progress_text(update: ProgressUpdate, title: str, artist: str) -> str:
    track_info = f"*{_esc(title)}* — {_esc(artist)}" if title else "Lossless Audio"
    bar = _render_bar(update.percent)
    size_str = _format_size(update.downloaded_bytes)
    if update.total_bytes and update.total_bytes > 0:
        size_disp = f"{size_str} / {_format_size(update.total_bytes)}"
    else:
        size_disp = size_str

    pct_str = f"{update.percent:.0f}%" if update.percent is not None else ""
    speed_str = f"{update.speed_mbps:.1f} MB/s"
    time_str = _format_time(update.elapsed_seconds)

    return (
        f"⏳ Downloading: {track_info}\n\n"
        f"`{bar}` {pct_str} \\({_esc(size_disp)}\\)\n"
        f"⚡ Speed: `{_esc(speed_str)}` · ⏱ `{_esc(time_str)}`"
    )


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


async def _send_audio_result(
    message: Message, result: DownloadResult, title: str, artist: str
) -> None:
    final_title = result.title or title or "Audio"
    final_artist = result.artist or artist or "Unknown Artist"
    res_badge = f"\n✨ `{_esc(result.resolution)}`" if result.resolution else ""
    caption = (
        f"🎵 *{_esc(final_title)}*\n"
        f"👤 {_esc(final_artist)}"
        f"{res_badge}\n"
        f"💾 `{result.file_size_bytes // (1024 * 1024)} MB`"
    )
    with result.file_path.open("rb") as audio_file:
        await message.reply_audio(
            audio=audio_file,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN_V2,
            filename=result.file_path.name,
        )


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
        card = _format_progress_text(prog, title, artist)
        with contextlib.suppress(Exception):
            await status.edit_text(card, parse_mode=ParseMode.MARKDOWN_V2)

    request = DownloadRequest(user_id=user_id, query=track_url, is_url=True)

    try:
        result = await download_track(request, on_progress=_on_progress)
        await status.edit_text(_UPLOADING, parse_mode=ParseMode.MARKDOWN_V2)
        await _send_audio_result(message, result, title, artist)
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
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)
