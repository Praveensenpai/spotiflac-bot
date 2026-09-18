from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass


def format_size(num_bytes: int) -> str:
    mb = num_bytes / (1024 * 1024)
    return f"{mb:.1f} MB"


def format_time(seconds: int) -> str:
    mins, secs = divmod(seconds, 60)
    return f"{mins:02d}:{secs:02d}"


def render_bar(percent: float | None, length: int = 14) -> str:
    if percent is None or percent <= 0:
        return "░" * length
    filled = max(0, min(length, int(length * (percent / 100.0))))
    return "█" * filled + "░" * (length - filled)


def esc_md(text: str) -> str:
    """Escape special MarkdownV2 characters."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


@dataclass(frozen=True)
class ProgressCardData:
    stage_icon: str
    stage_name: str
    title: str
    artist: str
    resolution: str
    bytes_done: int
    total_bytes: int | None
    speed_mbps: float
    elapsed_seconds: int


def render_progress_card(d: ProgressCardData) -> str:
    """Renders a rich Unicode progress card for Telegram messages."""
    track = f"*{esc_md(d.title)}* — {esc_md(d.artist)}" if d.title else "Audio"
    res_line = f"✨ `{esc_md(d.resolution)}`\n" if d.resolution else ""

    pct = (
        min(100.0, (d.bytes_done / d.total_bytes) * 100.0)
        if d.total_bytes and d.total_bytes > 0
        else None
    )
    pct_str = f"{pct:.0f}%" if pct is not None else ""
    bar = render_bar(pct)

    size_done = format_size(d.bytes_done)
    size_total = format_size(d.total_bytes) if d.total_bytes else None
    size_str = f"{size_done} / {size_total}" if size_total else size_done

    speed_str = f"⚡ `{d.speed_mbps:.1f} MB/s`"
    time_str = f"⏱ `{format_time(d.elapsed_seconds)}`"

    eta_str = ""
    if d.total_bytes and d.speed_mbps > 0 and d.bytes_done < d.total_bytes:
        remain = d.total_bytes - d.bytes_done
        eta_secs = int(remain / (d.speed_mbps * 1024 * 1024))
        eta_str = f" · ⏳ `ETA {format_time(eta_secs)}`"

    return (
        f"{d.stage_icon} *{d.stage_name}*: {track}\n"
        f"{res_line}\n"
        f"`[{bar}]` {pct_str}\n"
        f"📦 `{esc_md(size_str)}` · {speed_str}\n"
        f"{time_str}{eta_str}"
    )


class TrackedFileReader(io.BufferedReader):
    """Raw stream reader tracking upload bytes delivered to Telegram."""

    def __init__(
        self,
        raw_io: io.RawIOBase,
        total_size: int,
        on_read: Callable[[int], None],
    ) -> None:
        super().__init__(raw_io)
        self._total_size = total_size
        self._read_bytes = 0
        self._on_read = on_read

    def read(self, size: int | None = -1) -> bytes:
        chunk = super().read(size)
        if chunk:
            self._read_bytes += len(chunk)
            self._on_read(self._read_bytes)
        return chunk
