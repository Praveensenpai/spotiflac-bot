from __future__ import annotations

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
from spotiflac_bot.models.download import DownloadRequest
from spotiflac_bot.services.downloader import cleanup_session, download_track
from spotiflac_bot.services.resolver import extract_spotify_url, is_spotify_url

log = logging.getLogger(__name__)

_WELCOME = (
    "🎵 *SpotiFLAC Bot*\n\n"
    "Send me:\n"
    "• A Spotify track / album / playlist URL\n"
    "• Or a song name — I'll find it for you\n\n"
    "I'll download the lossless FLAC and send it right here. 🎧"
)

_SEARCHING = "🔍 Searching and downloading — this may take a minute…"
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

    url = extract_spotify_url(text) if is_spotify_url(text) else None
    query = url if url else text
    is_url = url is not None

    status = await message.reply_text(_SEARCHING)

    request = DownloadRequest(user_id=user_id, query=query, is_url=is_url)

    try:
        result = await download_track(request)

        await status.edit_text(_UPLOADING, parse_mode=ParseMode.MARKDOWN_V2)

        caption = (
            f"🎵 *{_esc(result.title)}*\n"
            f"👤 {_esc(result.artist)}\n"
            f"💾 `{result.file_size_bytes // (1024 * 1024)} MB`"
        )

        with result.file_path.open("rb") as audio_file:
            await message.reply_audio(
                audio=audio_file,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN_V2,
                filename=result.file_path.name,
            )

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
