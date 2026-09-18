from __future__ import annotations

import logging
import re

from SpotiFLAC.core.spotify_metadata import SpotifyMetadataClient

log = logging.getLogger(__name__)

SPOTIFY_URL_PATTERN = re.compile(
    r"https?://open\.spotify\.com/(?:intl-[a-zA-Z]+/)?(track|album|playlist)/[A-Za-z0-9]+"
)


def is_spotify_url(text: str) -> bool:
    return bool(SPOTIFY_URL_PATTERN.search(text.strip()))


def extract_spotify_url(text: str) -> str | None:
    match = SPOTIFY_URL_PATTERN.search(text.strip())
    return match.group(0) if match else None


async def resolve_query_to_track_url(
    query: str,
) -> tuple[str, str, str] | None:
    """Resolve a Spotify URL or plain song name to (url, title, artist)."""
    trimmed = query.strip()
    if is_spotify_url(trimmed):
        url = extract_spotify_url(trimmed)
        if url:
            return url, "", ""

    log.info("Searching Spotify for track name: %s", trimmed)
    try:
        client = SpotifyMetadataClient()
        results = await client.search_tracks_async(trimmed, limit=1)
        if results and results[0].external_url:
            track = results[0]
            log.info(
                "Resolved '%s' -> %s (%s - %s)",
                trimmed,
                track.external_url,
                track.title,
                track.artists,
            )
            return track.external_url, track.title, track.artists
    except Exception as exc:
        log.warning("Spotify track search failed for '%s': %s", trimmed, exc)

    return None
