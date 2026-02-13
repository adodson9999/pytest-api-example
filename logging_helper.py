import logging
import sys

RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RESET = "\033[0m"
WHITE = "\033[97m"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def log_status(status, message, extra=""):
    status = status.lower()
    color = WHITE  # default

    if status == "error":
        color = RED
    elif status == "warning":
        color = YELLOW
    elif status == "good":
        color = GREEN

    if not extra:
        logging.info(f"{color}{message}{RESET}")
    else:
        logging.info(f"{color}{message}{extra}{RESET}")