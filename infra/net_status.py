# infra/net_status.py
import socket

FORCE_OFFLINE = False  # ← True にすれば強制オフライン

_cached_online_status = None

def check_online(host="8.8.8.8", port=53, timeout=3) -> bool:
    """ネット接続の有無を確認し、結果をキャッシュに保存する"""
    global _cached_online_status

    if FORCE_OFFLINE:
        _cached_online_status = False
        return False

    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        _cached_online_status = True
    except socket.error:
        _cached_online_status = False
    return _cached_online_status

def is_online() -> bool:
    """チェック済みのオンライン状態を返す（未チェックならFalse）"""
    return _cached_online_status is True
