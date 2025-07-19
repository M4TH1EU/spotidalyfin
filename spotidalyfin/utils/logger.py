import logging

log = logging.getLogger("spotidalyfin")


def setup_logger(debug: bool = False):

    # Prevent tidalapi from logging
    logging.getLogger('tidalapi.settings').disabled = True
    logging.getLogger('tidalapi.session').disabled = True

    log.setLevel(logging.DEBUG if debug else logging.INFO)
