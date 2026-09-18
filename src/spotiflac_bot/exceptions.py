class SpotiFlacBotError(Exception):
    """Base exception for all bot errors."""


class UnauthorizedUserError(SpotiFlacBotError):
    """Raised when a non-whitelisted user sends a request."""


class DownloadFailedError(SpotiFlacBotError):
    """Raised when SpotiFLAC fails to download a track."""


class FileTooLargeError(SpotiFlacBotError):
    """Raised when the downloaded file exceeds Telegram's 50 MB limit."""


class InvalidInputError(SpotiFlacBotError):
    """Raised when the user input is neither a valid URL nor a track name."""
