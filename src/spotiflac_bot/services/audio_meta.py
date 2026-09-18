from __future__ import annotations

import contextlib
import io
import logging
from pathlib import Path

from mutagen.flac import FLAC
from PIL import Image

log = logging.getLogger(__name__)


def detect_resolution(file_path: Path) -> str:
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


def detect_duration_seconds(file_path: Path) -> int:
    """Inspect audio header to extract track length in seconds."""
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".flac":
            # upstream mutagen lacks typed stubs
            audio = FLAC(file_path)  # type: ignore[no-untyped-call]
            return int(getattr(audio.info, "length", 0.0))
        if suffix == ".mp3":
            from mutagen.mp3 import MP3

            audio_mp3 = MP3(file_path)  # type: ignore[no-untyped-call]
            return int(getattr(audio_mp3.info, "length", 0.0))
    except Exception as exc:
        log.debug("Failed reading duration from %s: %s", file_path.name, exc)
    return 0


def collect_metadata(
    file_path: Path,
    expected_title: str = "",
    expected_artist: str = "",
) -> tuple[str, str]:
    """Extract title and artist from tags, falling back to expected or filename."""
    title = ""
    artist = ""
    suffix = file_path.suffix.lower()

    if suffix == ".flac":
        with contextlib.suppress(Exception):
            # upstream mutagen lacks typed stubs
            audio = FLAC(file_path)  # type: ignore[no-untyped-call]
            tags = getattr(audio, "tags", None)
            if tags is not None:
                raw_title = getattr(tags, "get", lambda _: None)("title")
                raw_artist = getattr(tags, "get", lambda _: None)("artist")
                if raw_title:
                    first_t = raw_title[0] if isinstance(raw_title, list) else raw_title
                    title = str(first_t).strip()
                if raw_artist:
                    is_lst = isinstance(raw_artist, list)
                    first_a = raw_artist[0] if is_lst else raw_artist
                    artist = str(first_a).strip()

    elif suffix == ".mp3":
        with contextlib.suppress(Exception):
            from mutagen.easyid3 import EasyID3

            id3 = EasyID3(file_path)  # type: ignore[no-untyped-call]
            raw_title = getattr(id3, "get", lambda _: None)("title")
            raw_artist = getattr(id3, "get", lambda _: None)("artist")
            if raw_title:
                title = str(raw_title[0]).strip()
            if raw_artist:
                artist = str(raw_artist[0]).strip()

    if not title and expected_title:
        title = expected_title.strip()
    if not artist and expected_artist:
        artist = expected_artist.strip()

    if not title or not artist:
        stem = file_path.stem
        parts = stem.split(" - ", maxsplit=1)
        if not title:
            title = parts[0].strip() if len(parts) == 2 else stem
        if not artist:
            artist = parts[1].strip() if len(parts) == 2 else "Unknown Artist"

    return title, artist


def extract_and_create_thumbnail(file_path: Path) -> Path | None:
    """Extract front cover from audio and generate a Telegram-ready 320x320 JPEG."""
    cover_bytes: bytes | None = None
    suffix = file_path.suffix.lower()

    if suffix == ".flac":
        try:
            # upstream mutagen lacks typed stubs
            audio = FLAC(file_path)  # type: ignore[no-untyped-call]
            pictures = getattr(audio, "pictures", [])
            for pic in pictures:
                if getattr(pic, "type", None) == 3:  # PictureType.COVER_FRONT
                    cover_bytes = getattr(pic, "data", None)
                    break
            if not cover_bytes and pictures:
                cover_bytes = getattr(pictures[0], "data", None)
        except Exception as exc:
            log.debug("Failed reading FLAC picture for thumbnail: %s", exc)

    elif suffix == ".mp3":
        try:
            from mutagen.id3 import ID3

            id3 = ID3(file_path)  # type: ignore[no-untyped-call]
            for key in id3:
                if key.startswith("APIC"):
                    cover_bytes = getattr(id3[key], "data", None)
                    break
        except Exception as exc:
            log.debug("Failed reading MP3 picture for thumbnail: %s", exc)

    if not cover_bytes:
        return None

    try:
        thumb_path = file_path.parent / "thumb.jpg"
        with Image.open(io.BytesIO(cover_bytes)) as img:
            rgb_img = img.convert("RGB")
            rgb_img.thumbnail((320, 320), Image.Resampling.LANCZOS)
            rgb_img.save(thumb_path, format="JPEG", quality=85, optimize=True)
            return thumb_path
    except Exception as exc:
        log.warning("Failed to create Telegram thumbnail: %s", exc)
        return None
