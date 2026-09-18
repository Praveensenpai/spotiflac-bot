from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

PROVIDER_LABELS: dict[str, str] = {
    "tidal": "🎵 Tidal",
    "qobuz": "🎶 Qobuz",
    "amazon": "📦 Amazon",
    "deezer": "🎧 Deezer",
}


def provider_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(label, callback_data=f"provider:{key}")
        for key, label in PROVIDER_LABELS.items()
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
    )
