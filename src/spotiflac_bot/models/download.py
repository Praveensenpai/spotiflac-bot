from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DownloadRequest:
    user_id: int
    query: str  # Spotify URL or search term
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
