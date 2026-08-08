import logging


def configure_logging(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    return logging.getLogger("alo_sm_voice")
