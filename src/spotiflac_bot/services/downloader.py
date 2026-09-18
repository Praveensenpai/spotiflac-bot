from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

# SpotiFLAC is a sync library — we run it in a thread executor
from SpotiFLAC import SpotiFLAC

from spotiflac_bot.config import settings
from spotiflac_bot.exceptions import DownloadFailedError, FileTooLargeError
from spotiflac_bot.models.download import DownloadRequest, DownloadResult


def _run_download(url: str, out_dir: Path) -> list[Path]:
    """Blocking SpotiFLAC call — executed in a thread pool."""
    SpotiFLAC(
        url=url,
        output_dir=str(out_dir),
        services=settings.services,
        use_artist_subfolders=False,
        use_album_subfolders=False,
    )
    files = sorted(out_dir.glob("*.flac")) + sorted(out_dir.glob("*.mp3"))
    return files


def _collect_metadata(file_path: Path) -> tuple[str, str]:
    """Extract title/artist from filename as fallback."""
    stem = file_path.stem
    parts = stem.split(" - ", maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip(), parts[0].strip()
    return stem, "Unknown Artist"


async def download_track(request: DownloadRequest) -> DownloadResult:
    """Async wrapper: runs SpotiFLAC in executor and returns result."""
    session_dir = settings.download_dir / str(uuid.uuid4())
    session_dir.mkdir(parents=True, exist_ok=True)

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
                f"File is {size // (1024 * 1024)} MB — exceeds Telegram's limit."
            )

        title, artist = _collect_metadata(file_path)
        return DownloadResult(
            file_path=file_path,
            title=title,
            artist=artist,
            file_size_bytes=size,
        )

    except (DownloadFailedError, FileTooLargeError):
        shutil.rmtree(session_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(session_dir, ignore_errors=True)
        raise DownloadFailedError(f"SpotiFLAC error: {exc}") from exc


def cleanup_session(result: DownloadResult) -> None:
    """Remove the session directory after upload."""
    session_dir = result.file_path.parent
    shutil.rmtree(session_dir, ignore_errors=True)
