# core/base_manager.py

import json
from infra.path_helper import get_data_path
from infra.logging import get_logger


class BaseManager:
    def __init__(self, logger_name: str, index_path: str):
        self.log = get_logger(logger_name)
        self.index_file = get_data_path(index_path)
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        self.entries = self._load_index()

    def _load_index(self) -> list:
        if self.index_file.exists():
            with self.index_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_index(self):
        with self.index_file.open("w", encoding="utf-8") as f:
            json.dump(self.entries, f, indent=2, ensure_ascii=False)

    def list_entries(self) -> list:
        """全エントリを返す"""
        return self.entries

    def get_entry_by_id(self, entry_id: str) -> dict | None:
        """指定IDのエントリを返す（なければNone）"""
        return next((e for e in self.entries if e.get("id") == entry_id), None)

    def delete_entry_by_id(self, entry_id: str) -> bool:
        """指定IDのエントリを削除する"""
        index = next((i for i, e in enumerate(self.entries) if e.get("id") == entry_id), None)
        if index is not None:
            del self.entries[index]
            self._save_index()
            self.log.info(f"エントリ削除: {entry_id}")
            return True
        self.log.warning(f"削除対象のエントリが見つかりません: {entry_id}")
        return False

    def update_entry(self, entry_id: str, updates: dict) -> bool:
        """指定IDのエントリに updates を適用する"""
        entry = self.get_entry_by_id(entry_id)
        if entry:
            entry.update(updates)
            self._save_index()
            self.log.info(f"エントリ更新: {entry_id} -> {updates}")
            return True
        self.log.warning(f"更新対象のエントリが見つかりません: {entry_id}")
        return False
