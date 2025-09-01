# infra/path_helper.py
from pathlib import Path
import sys, os

def get_resource_path(relative_path: str) -> Path:
    """
    読み取り専用のリソース（フォントや初期設定）へのパス
    APKにバンドルされる想定。
    """
    if getattr(sys, 'frozen', False):
        base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).resolve().parent.parent
    return base_path / relative_path


def get_data_base() -> Path:
    """
    書き込み可能なデータ保存先のベースディレクトリを返す。
    - PC: ./data/
    - Android: $HOME/.shelves_data/
    """
    if hasattr(sys, "getandroidapilevel"):  # Python-for-android 環境
        return Path(os.path.expanduser("~")) / ".shelves_data"
    else:
        return get_resource_path("data")


def get_data_path(relative_path: str) -> Path:
    """
    data/配下のファイル・ディレクトリを返す。
    必要なら自動でディレクトリ作成。
    """
    full_path = get_data_base() / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    return full_path
