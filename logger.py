# logger.py
import logging

logging.basicConfig(
    filename="contact_logs.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)