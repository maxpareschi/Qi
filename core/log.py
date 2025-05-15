import logging

import colorlog
import webview

formatter = colorlog.ColoredFormatter(
    "{light_black}{asctime}{reset} | {log_color}{levelname:<8}{reset} | {message_log_color}{message}{reset} {light_black}- ({name}.{module}.{funcName} - {filename}:{lineno}){reset}",
    # " | {log_color}{levelname:<8}{reset} | {message_log_color}{message}{reset} {light_black}- ({name}.{module}.{funcName} - {filename}:{lineno}){reset}",
    datefmt="%y-%m-%d %H:%M:%S",
    style="{",
    reset=True,
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "fg_bold_white,bg_bold_red",
    },
    secondary_log_colors={
        "message": {
            # "DEBUG": "light_black",
            # "INFO": "white",
            "WARNING": "yellow",
            "ERROR": "bold_red",
            "CRITICAL": "fg_bold_white,bg_bold_red",
        },
    },
)

handler = colorlog.StreamHandler()
handler.setFormatter(formatter)

log = colorlog.getLogger()

for handler in log.handlers:
    log.removeHandler(handler)

log.addHandler(handler)
log.setLevel(logging.DEBUG)

for handler in webview.logger.handlers:
    webview.logger.removeHandler(handler)
webview.logger.addHandler(log.handlers[0])


if __name__ == "__main__":
    log.debug("Testing log formatting..")
    log.info("Testing log formatting..")
    log.warning("Testing log formatting..")
    log.error("Testing log formatting..")
    log.critical("Testing log formatting..")
