"""开发日志系统

使用 Python 标准库 logging，输出到 data/logs/ 目录下的滚动日志文件。
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
LOG_DIR = DATA_DIR / "logs"

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    """初始化全局日志配置。在 main.py 启动时调用。"""
    os.makedirs(LOG_DIR, exist_ok=True)

    log_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    file_handler = TimedRotatingFileHandler(
        filename=str(LOG_DIR / "marginalia.log"),
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.suffix = "%Y-%m-%d"

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger("marginalia")
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_logger(component: str) -> logging.Logger:
    """获取组件级 logger。组件名会显示在日志的 {组件} 字段。"""
    return logging.getLogger(f"marginalia.{component}")


def set_level(level: str) -> None:
    """动态调整日志级别（无需重启服务）。"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger("marginalia").setLevel(log_level)
