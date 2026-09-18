from __future__ import annotations

import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from spotiflac_bot.bot.handlers import cmd_help, cmd_start, handle_message
from spotiflac_bot.config import settings
from spotiflac_bot.services.downloader import ensure_extensions


def build_app() -> Application:  # type: ignore[type-arg]
    app = Application.builder().token(settings.bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


def run() -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
        level=logging.INFO,
    )
    log = logging.getLogger(__name__)
    log.info("Starting SpotiFLAC bot — providers: %s", settings.services)
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    ensure_extensions()
    build_app().run_polling(drop_pending_updates=True)
