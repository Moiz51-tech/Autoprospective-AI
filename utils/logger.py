from loguru import logger
import sys

# Remove default handler
logger.remove()

# Add console handler with clean format
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# Add file handler for persistent logs
logger.add(
    "logs/autoprospect.log",
    rotation="10 MB",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} - {message}",
    level="DEBUG",
)


def get_logger(name: str):
    return logger.bind(name=name)
