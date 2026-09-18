from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_CONFIG_PATH = Path("config.toml")


def _require_secret(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required secret in environment: {key}")
    return val


def _read_toml_config() -> dict[str, object]:
    path = Path(os.getenv("CONFIG_PATH", DEFAULT_CONFIG_PATH))
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _parse_allowed_ids(bot_cfg: object) -> list[int]:
    if isinstance(bot_cfg, dict):
        raw_ids = bot_cfg.get("allowed_user_ids", [])
        if isinstance(raw_ids, list):
            return [int(x) for x in raw_ids]
    return []


@dataclass(frozen=True)
class DownloadConfig:
    download_dir: Path
    max_file_bytes: int
    services: list[str]
    quality: str
    allow_fallback: bool


def _parse_download_cfg(dl_cfg: object) -> DownloadConfig:
    dl_dir = Path("/tmp/spotiflac")
    max_mb = 49
    services = ["tidal-web", "qobuz-web", "deezer", "amazon"]
    quality = "HI_RES_LOSSLESS"
    allow_fallback = True

    if isinstance(dl_cfg, dict):
        if "download_dir" in dl_cfg:
            dl_dir = Path(str(dl_cfg["download_dir"]))
        if "max_file_mb" in dl_cfg:
            max_mb = int(str(dl_cfg["max_file_mb"]))
        if "services" in dl_cfg and isinstance(dl_cfg["services"], list):
            services = [str(s) for s in dl_cfg["services"]]
        if "quality" in dl_cfg:
            quality = str(dl_cfg["quality"]).strip().upper()
        if "allow_fallback" in dl_cfg:
            allow_fallback = bool(dl_cfg["allow_fallback"])

    return DownloadConfig(
        download_dir=dl_dir,
        max_file_bytes=max_mb * 1024 * 1024,
        services=services,
        quality=quality,
        allow_fallback=allow_fallback,
    )


def _parse_registries(ext_cfg: object) -> list[str]:
    default_url = (
        "https://raw.githubusercontent.com/zarzet/SpotiFLAC-Extension/"
        "main/registry.json"
    )
    if isinstance(ext_cfg, dict) and "registries" in ext_cfg:
        raw_reg = ext_cfg["registries"]
        if isinstance(raw_reg, list):
            return [str(r) for r in raw_reg]
    return [default_url]


@dataclass(frozen=True)
class Settings:
    bot_token: str
    allowed_user_ids: list[int]
    download: DownloadConfig
    registries: list[str]

    @property
    def download_dir(self) -> Path:
        return self.download.download_dir

    @property
    def max_file_bytes(self) -> int:
        return self.download.max_file_bytes

    @property
    def services(self) -> list[str]:
        return self.download.services

    @property
    def quality(self) -> str:
        return self.download.quality

    @property
    def allow_fallback(self) -> bool:
        return self.download.allow_fallback

    @classmethod
    def load(cls) -> Settings:
        cfg = _read_toml_config()
        allowed_ids = _parse_allowed_ids(cfg.get("bot"))
        dl_config = _parse_download_cfg(cfg.get("download"))
        registries = _parse_registries(cfg.get("extensions"))

        if registries and "SPOTIFLAC_REGISTRIES" not in os.environ:
            os.environ["SPOTIFLAC_REGISTRIES"] = ",".join(registries)

        return cls(
            bot_token=_require_secret("BOT_TOKEN"),
            allowed_user_ids=allowed_ids,
            download=dl_config,
            registries=registries,
        )


settings: Settings = Settings.load()
