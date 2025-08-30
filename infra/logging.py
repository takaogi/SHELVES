# infra/logging.py
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from infra.path_helper import get_resource_path

LOG_PATH = get_resource_path("data/SHELVES.log")
_current_level = logging.INFO

# 追加: コールバック保持用
_api_log_callback = None

class CallbackHandler(logging.Handler):
    """ログを外部コールバックに転送するハンドラ"""
    def emit(self, record: logging.LogRecord):
        global _api_log_callback
        if _api_log_callback:
            try:
                msg = self.format(record)
                _api_log_callback(msg)
            except Exception:
                pass

def set_api_log_callback(callback):
    """C#側などからコールバックを登録する"""
    global _api_log_callback
    _api_log_callback = callback

def setup_logging(level=None):
    global _current_level
    if level is not None:
        _current_level = level

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(_current_level)

    fmt = "[%(levelname)s] [%(name)s] %(message)s"
    handlers = []

    # コンソール出力
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(fmt))
    handlers.append(stream_handler)

    # ファイル出力
    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt))
    handlers.append(file_handler)

    # API出力用（追加）
    callback_handler = CallbackHandler()
    callback_handler.setFormatter(logging.Formatter(fmt))
    handlers.append(callback_handler)

    logging.basicConfig(
        level=_current_level,
        format=fmt,
        handlers=handlers,
    )

    for noisy_logger in [
        "openai", "httpx", "urllib3", "fsspec", "speechbrain", "pyannote",
        "pytorch_lightning", "torch", "comtypes", "comtypes.client", "comtypes.client._generate",
    ]:
        nlogger = logging.getLogger(noisy_logger)
        nlogger.setLevel(logging.CRITICAL + 1)
        nlogger.propagate = False

def get_logger(name: str = __name__) -> logging.Logger:
    root_logger = logging.getLogger()
    if not root_logger.hasHandlers():
        setup_logging()
    return logging.getLogger(name)


def set_debug_enabled(enabled: bool):
    global _current_level
    new_level = logging.DEBUG if enabled else logging.INFO
    _current_level = new_level
    logging.getLogger().setLevel(new_level)
    for handler in logging.getLogger().handlers:
        handler.setLevel(new_level)


def is_debug_enabled() -> bool:
    return _current_level == logging.DEBUG
