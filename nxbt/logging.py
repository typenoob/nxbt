import logging
from datetime import datetime


def create_logger(debug=False, log_to_file=False, disable_logging=False):
    logger = logging.getLogger("nxbt")

    if disable_logging:
        null_handler = logging.NullHandler()
        logger.addHandler(null_handler)
        return logger

    if debug:
        logger.setLevel(logging.DEBUG)

    if log_to_file:
        log_filename = (
            log_to_file
            if isinstance(log_to_file, str)
            else f"./nxbt {datetime.now()}.log"
        )
        nxbt_handler = logging.FileHandler(log_filename)
        nxbt_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
        )
        logger.addHandler(nxbt_handler)
        # Bumble uses its own ColorFormatter for the same file
        from bumble.logging import ColorFormatter

        bumble_handler = logging.FileHandler(log_filename)
        bumble_handler.setFormatter(ColorFormatter())
        logging.getLogger("bumble").addHandler(bumble_handler)
        logging.getLogger("bumble").setLevel(logging.DEBUG if debug else logging.INFO)
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
        )
        logger.addHandler(stream_handler)

    return logger
