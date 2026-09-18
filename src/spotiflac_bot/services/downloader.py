from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from mutagen.flac import FLAC
from SpotiFLAC import SpotiFLAC
from SpotiFLAC.core.progress import DownloadManager
from SpotiFLAC.core.quality import quality_fallback_chain
from SpotiFLAC.extensions.manager import ExtensionManager

from spotiflac_bot.config import settings
from spotiflac_bot.exceptions import DownloadFailedError, FileTooLargeError
from spotiflac_bot.models.download import (
    DownloadRequest,
    DownloadResult,
    ProgressUpdate,
)

log = logging.getLogger(__name__)


def ensure_extensions() -> None:
    """Bootstrap and verify installed extensions from registry."""
    log.info("Checking and updating SpotiFLAC extensions...")
    try:
        mgr = ExtensionManager()
        mgr.ensure_download_providers()
        installed = [ext.name for ext in mgr.list_installed()]
        log.info("Installed extensions available: %s", installed)
    except Exception as exc:
        log.warning("Extension check encountered issue: %s", exc)


def _detect_resolution(file_path: Path) -> str:
    """Inspect audio header to detect true bit-depth and sample rate."""
    if file_path.suffix.lower() == ".flac":
        try:
            # upstream mutagen lacks typed stubs
            audio = FLAC(file_path)  # type: ignore[no-untyped-call]
            bits = getattr(audio.info, "bits_per_sample", 0)
            rate_khz = getattr(audio.info, "sample_rate", 0) / 1000.0
            if bits > 0 and rate_khz > 0:
                return f"{bits}-bit / {rate_khz:.1f} kHz FLAC"
        except Exception:
            pass
        return "Lossless FLAC"
    return file_path.suffix.lstrip(".").upper()


def _attempt_tier_download(
    url: str, out_dir: Path, tier: str, allow_fb: bool
) -> list[Path]:
    log.info("Probing providers for tier: %s (fallback=%s)", tier, allow_fb)
    try:
        SpotiFLAC(
            url=url,
            output_dir=str(out_dir),
            services=settings.services,
            quality=tier,
            allow_fallback=allow_fb,
            use_artist_subfolders=False,
            use_album_subfolders=False,
        )
        return sorted(out_dir.glob("*.flac")) + sorted(out_dir.glob("*.mp3"))
    except Exception as exc:
        log.debug("Tier %s attempt failed: %s", tier, exc)
        return []


def _run_download(url: str, out_dir: Path) -> list[Path]:
    """Cascades from highest quality tier down to lowest across all providers."""
    chain = quality_fallback_chain(settings.quality)
    if not settings.allow_fallback:
        chain = [chain[0]]

    for idx, tier in enumerate(chain):
        is_last = idx == len(chain) - 1
        allow_fb = is_last
        files = _attempt_tier_download(url, out_dir, tier, allow_fb)
        if files:
            log.info("Resolved at tier %s: %s", tier, files[0].name)
            return files

    return sorted(out_dir.glob("*.flac")) + sorted(out_dir.glob("*.mp3"))


def _collect_metadata(file_path: Path) -> tuple[str, str]:
    """Extract title/artist from filename as fallback."""
    stem = file_path.stem
    parts = stem.split(" - ", maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip(), parts[0].strip()
    return stem, "Unknown Artist"


def _scan_dir_bytes(dir_path: Path) -> int:
    """Sum size of all files in directory safely."""
    total = 0
    if not dir_path.exists():
        return 0
    for f in dir_path.rglob("*"):
        if f.is_file():
            with contextlib.suppress(OSError):
                total += f.stat().st_size
    return total


async def _monitor_progress(
    session_dir: Path,
    stop_event: asyncio.Event,
    callback: Callable[[ProgressUpdate], Awaitable[None]],
    interval: float = 3.5,
) -> None:
    """Periodically collect metrics and emit progress updates."""
    start_time = time.time()
    last_bytes = 0
    last_time = start_time

    while not stop_event.is_set():
        try:
            await asyncio.sleep(interval)
            if stop_event.is_set():
                break

            now = time.time()
            elapsed = int(now - start_time)
            cur_bytes = _scan_dir_bytes(session_dir)

            total_bytes: int | None = None
            speed_mbps = 0.0
            percent: float | None = None

            try:
                stats = await DownloadManager().get_stats()
                downloads = stats.get("downloads", [])
                if downloads:
                    item = downloads[-1]
                    total_mb = item.get("total_size", 0.0)
                    prog_mb = item.get("progress", 0.0)
                    if total_mb > 0:
                        total_bytes = int(total_mb * 1024 * 1024)
                        if cur_bytes == 0 and prog_mb > 0:
                            cur_bytes = int(prog_mb * 1024 * 1024)
                        percent = min(100.0, (cur_bytes / total_bytes) * 100.0)
                    if item.get("speed", 0.0) > 0:
                        speed_mbps = float(item["speed"])
            except Exception:
                pass

            if speed_mbps == 0.0 and now > last_time:
                time_diff = now - last_time
                bytes_diff = max(0, cur_bytes - last_bytes)
                speed_mbps = (bytes_diff / (1024 * 1024)) / time_diff

            last_bytes = cur_bytes
            last_time = now

            update = ProgressUpdate(
                elapsed_seconds=elapsed,
                downloaded_bytes=cur_bytes,
                total_bytes=total_bytes,
                speed_mbps=round(speed_mbps, 2),
                percent=round(percent, 1) if percent is not None else None,
            )
            with contextlib.suppress(Exception):
                await callback(update)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


async def download_track(
    request: DownloadRequest,
    on_progress: Callable[[ProgressUpdate], Awaitable[None]] | None = None,
) -> DownloadResult:
    """Async wrapper: runs SpotiFLAC in executor with optional progress ticker."""
    session_dir = settings.download_dir / str(uuid.uuid4())
    session_dir.mkdir(parents=True, exist_ok=True)

    stop_event = asyncio.Event()
    monitor_task: asyncio.Task[None] | None = None
    if on_progress:
        monitor_task = asyncio.create_task(
            _monitor_progress(session_dir, stop_event, on_progress)
        )

    try:
        loop = asyncio.get_running_loop()
        files = await loop.run_in_executor(
            None, _run_download, request.query, session_dir
        )

        if not files:
            raise DownloadFailedError(
                f"No audio file was produced for: {request.query}"
            )

        file_path = files[0]
        size = file_path.stat().st_size

        if size > settings.max_file_bytes:
            raise FileTooLargeError(
                f"File is {size // (1024 * 1024)} MB — exceeds Telegram limit."
            )

        title, artist = _collect_metadata(file_path)
        resolution = _detect_resolution(file_path)
        return DownloadResult(
            file_path=file_path,
            title=title,
            artist=artist,
            file_size_bytes=size,
            resolution=resolution,
        )

    except (DownloadFailedError, FileTooLargeError):
        shutil.rmtree(session_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(session_dir, ignore_errors=True)
        raise DownloadFailedError(f"SpotiFLAC error: {exc}") from exc
    finally:
        stop_event.set()
        if monitor_task:
            monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor_task


def cleanup_session(result: DownloadResult) -> None:
    """Remove the session directory after upload."""
    session_dir = result.file_path.parent
    shutil.rmtree(session_dir, ignore_errors=True)
