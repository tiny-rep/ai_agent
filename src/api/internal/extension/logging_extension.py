import logging
import os.path

from concurrent_log_handler import ConcurrentTimedRotatingFileHandler
from flask import Flask


def init_log_app(app: Flask):
    """初始化日志库"""
    logging.getLogger().setLevel(
        logging.DEBUG if app.debug or os.getenv("FLASK_ENV") == "development" else logging.WARNING
    )

    log_folder = os.path.join(os.getcwd(), "storage", "log")
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)

    log_file = os.path.join(log_folder, "app.log")

    handler = ConcurrentTimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] %(filename)s -> %(funcName)s line:%(lineno)d [%(levelname)s]: %(message)s"
    )
    handler.setLevel(logging.DEBUG if app.debug or os.getenv("FLASK_ENV") == "development" else logging.WARNING)
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)

    # 如果在开发者模型，同时输出到控制台
    if app.debug or os.getenv("FLASK_ENV") == "development":
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logging.getLogger().addHandler(console_handler)
