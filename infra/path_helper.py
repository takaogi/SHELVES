# infra/path_helper.py
from pathlib import Path
import sys


def get_resource_path(relative_path: str) -> Path:
    """
    .exeでも動く安全なリソースパス解決。Pathを返す。
    resources/ 以下など固定データの読み込みに使う
    """
    if getattr(sys, 'frozen', False):
        base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).resolve().parent.parent
    return base_path / relative_path


def get_data_path(relative_path: str) -> Path:
    """
    実行時に生成されるファイルを保存するベースディレクトリ（data/）
    該当ディレクトリが存在しなければ自動で作成する
    """
    full_path = get_resource_path("data") / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    return full_path

