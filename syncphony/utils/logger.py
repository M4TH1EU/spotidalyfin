import logging

log = logging.getLogger("syncphony")


def setup_logger(level: str = "INFO"):
    # Prevent tidalapi from logging
    logging.getLogger('tidalapi.settings').disabled = True
    logging.getLogger('tidalapi.session').disabled = True

    log.setLevel(level)
