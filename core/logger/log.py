import logging
import os

# ANSI color codes
COLORS = {
    "reset": "\033[0m",
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "purple": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "light_black": "\033[90m",
    "light_red": "\033[91m",
    "light_green": "\033[92m",
    "light_yellow": "\033[93m",
    "light_blue": "\033[94m",
    "light_purple": "\033[95m",
    "light_cyan": "\033[96m",
    "light_white": "\033[97m",
    "bold": "\033[1m",
    "bold_red": "\033[1;31m",
    "bold_white": "\033[1;37m",
    "bg_bold_red": "\033[1;41m",
    "fg_bold_white_bg_bold_red": "\033[1;37;41m",
}

LEVEL_COLORS = {
    "DEBUG": COLORS["cyan"],
    "INFO": COLORS["green"],
    "WARNING": COLORS["yellow"],
    "ERROR": COLORS["red"],
    "CRITICAL": COLORS["fg_bold_white_bg_bold_red"],
}

MESSAGE_COLORS = {
    "DEBUG": COLORS["light_black"],
    "INFO": COLORS["light_white"],
    "WARNING": COLORS["yellow"],
    "ERROR": COLORS["bold_red"],
    "CRITICAL": COLORS["fg_bold_white_bg_bold_red"],
}

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL


class QiCustomFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord):
        # Format the timestamp
        record.asctime = self.formatTime(record, "%y-%m-%d %H:%M:%S")

        # Get colors for current log level
        log_color = LEVEL_COLORS.get(record.levelname, COLORS["reset"])
        message_color = MESSAGE_COLORS.get(record.levelname, COLORS["reset"])

        # Apply the color formatting (matching the colorlog format exactly)
        colored_format = (
            f"{COLORS['light_black']}{record.asctime}{COLORS['reset']} | "
            f"{log_color}{record.levelname:<8}{COLORS['reset']} | "
            f"{message_color}{record.getMessage()}{COLORS['reset']} "
            f"{COLORS['light_black']}- ({record.name}.{record.funcName} - {record.filename}:{record.lineno}){COLORS['reset']}"
        )

        return colored_format


handler = logging.StreamHandler()
handler.setFormatter(QiCustomFormatter())
handler.setLevel(DEBUG)

root_logger = logging.getLogger()
root_logger.addHandler(handler)
root_logger.setLevel(DEBUG)


def set_level(level: int) -> None:
    handler.setLevel(level)
    root_logger.setLevel(level)


def get_logger(name: str | None = None, level: int | None = None) -> logging.Logger:
    """
    Get a logger with a custom formatter.
    """
    qi_dev_mode = os.getenv("QI_DEV_MODE", "0") == "1"
    qi_log_level = os.getenv("QI_LOG_LEVEL", "WARNING").upper()

    level_map = {
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
    }

    if level is not None:
        qi_log_level = level
    if qi_dev_mode:
        qi_log_level = "DEBUG"

    level = level_map[qi_log_level]
    set_level(level)
    return logging.getLogger(name)


if __name__ == "__main__":
    log = get_logger("TestLogger")
    log.debug("Testing log formatting..")
    log.info("Testing log formatting..")
    log.warning("Testing log formatting..")
    log.error("Testing log formatting..")
    log.critical("Testing log formatting..")
