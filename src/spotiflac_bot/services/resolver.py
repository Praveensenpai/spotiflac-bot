from __future__ import annotations

import re

SPOTIFY_URL_PATTERN = re.compile(
    r"https?://open\.spotify\.com/(track|album|playlist)/[A-Za-z0-9]+"
)


def is_spotify_url(text: str) -> bool:
    return bool(SPOTIFY_URL_PATTERN.search(text.strip()))


def extract_spotify_url(text: str) -> str | None:
    match = SPOTIFY_URL_PATTERN.search(text.strip())
    return match.group(0) if match else None
