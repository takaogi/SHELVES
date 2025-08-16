# core/nouns_manager.py
import uuid
from core.base_manager import BaseManager
from collections import defaultdict
from datetime import datetime
from infra.path_helper import get_data_path
from infra.logging import get_logger


class NounsManager(BaseManager):
    def __init__(self):
        self.wid = None
        self.log = get_logger("NounsManager")
        self.entries = []
        self.base_dir = None
        self.index_file = None

    def set_worldview_id(self, wid: str):
        self.wid = wid
        self.base_dir = get_data_path(f"worlds/{wid}/nouns")
        self.index_file = self.base_dir / "nouns_index.json"
        self.entries = self._load_index()
        self.log.info(f"NounsManager: worldview_id を {wid} に切り替えました")
        
    def create_noun(self, name: str, type: str, tags: list[str] = None,
                    category: str = "", notes: str = "", fame: int = 25,
                    details: dict = None) -> str:
        if not self.wid:
            raise ValueError("worldview_id が設定されていません。 set_worldview_id() を先に呼んでください。")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        noun_id = f"noun_{ts}_{uuid.uuid4().hex[:4]}"
        created = datetime.now().isoformat()

        entry = {
            "id": noun_id,
            "name": name,
            "type": type,
            "category": category,
            "tags": tags or [],
            "notes": notes,
            "fame": fame,  # ★ 追加
            "details": details or {},
            "created": created
        }

        self.entries.append(entry)
        self._save_index()
        self.log.info(f"固有名詞作成: {name} (id={noun_id}, type={type}, fame={fame})")
        return noun_id

    def delete_noun(self, noun_id: str) -> bool:
        return self.delete_entry_by_id(noun_id)

    def rename_noun(self, noun_id: str, new_name: str) -> bool:
        return self.update_entry(noun_id, {"name": new_name})

    def update_notes(self, noun_id: str, new_notes: str) -> bool:
        return self.update_entry(noun_id, {"notes": new_notes})

    def update_details(self, noun_id: str, new_details: dict) -> bool:
        return self.update_entry(noun_id, {"details": new_details})

    def filter_by_type(self, type_name: str) -> list[dict]:
        return [e for e in self.entries if e.get("type") == type_name]

    def filter_by_tag(self, tag: str) -> list[dict]:
        return [e for e in self.entries if tag in e.get("tags", [])]

    def search_nouns_by_name(self, keyword: str) -> list[dict]:
        return [e for e in self.entries if keyword.lower() in e.get("name", "").lower()]

    def get_grouped_by_type(self) -> dict[str, list[dict]]:
        grouped = defaultdict(list)
        for e in self.entries:
            grouped[e.get("type", "未分類")].append

    def sort_index_by_fame(self, ascending: bool = True) -> None:
        """
        fame の値で entries を並び替える。
        少ない順 (ascending=True) がデフォルト。
        """
        # デフォルト値は 0 にしておく（fame 未設定対策）
        self.entries.sort(key=lambda e: e.get("fame", 0), reverse=not ascending)
        self._save_index()
        self.log.info(f"nouns_index を fame {'昇順' if ascending else '降順'} に並び替えました")
