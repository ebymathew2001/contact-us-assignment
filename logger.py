# logger.py
import logging

logger = logging.getLogger("contactbot")
logger.setLevel(logging.DEBUG)
logger.propagate = False  # don't pass to root logger (avoids duplicate console output)

if not logger.handlers:
    handler = logging.FileHandler("contact_logs.log")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)