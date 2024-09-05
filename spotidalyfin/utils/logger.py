import logging

from rich.logging import RichHandler

log = logging.getLogger("spotidalyfin")


def setup_logger(debug: bool = False):
    log.handlers.clear()

    # Prevent tidalapi from logging
    tidalapilogger = logging.getLogger('tidalapi.request')
    tidalapilogger.disabled = True

    # Prevent rich from propagating logs to root logger
    log.propagate = False

    handler_with_formatter = RichHandler()
    handler_with_formatter.setFormatter(logging.Formatter('%(message)s'))

    log.addHandler(handler_with_formatter)
    log.setLevel(logging.DEBUG if debug else logging.INFO)
