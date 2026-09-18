from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


def _allowed_ids() -> list[int]:
    raw = os.getenv("ALLOWED_USER_IDS", "")
    if not raw.strip():
        return []
    return [int(uid.strip()) for uid in raw.split(",") if uid.strip()]


def _services() -> list[str]:
    raw = os.getenv("SERVICES", "tidal,qobuz,amazon,deezer")
    return [s.strip() for s in raw.split(",") if s.strip()]


@dataclass(frozen=True)
class Settings:
    bot_token: str
    allowed_user_ids: list[int]
    download_dir: Path
    services: list[str]
    max_file_bytes: int

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            bot_token=_require("BOT_TOKEN"),
            allowed_user_ids=_allowed_ids(),
            download_dir=Path(os.getenv("DOWNLOAD_DIR", "/tmp/spotiflac")),
            services=_services(),
            max_file_bytes=int(os.getenv("MAX_FILE_MB", "49")) * 1024 * 1024,
        )


settings: Settings = Settings.from_env()
