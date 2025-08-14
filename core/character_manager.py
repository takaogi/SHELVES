# core/character_manager.py
import json
import uuid
from datetime import datetime
from core.base_manager import BaseManager
from infra.path_helper import get_data_path
from infra.logging import get_logger


class CharacterManager(BaseManager):
    def __init__(self):
        self.worldview_id = None
        self.base_dir = None
        self.index_file = None
        self.entries = []
        self.log = get_logger("CharacterManager")


    def set_worldview_id(self, wid: str):
        """worldview_id を切り替えて再初期化"""
        self.worldview_id = wid
        self.base_dir = get_data_path(f"worlds/{wid}/characters")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.base_dir / "character_index.json"
        self.entries = self._load_index()
        self.log.info(f"CharacterManager: worldview_id を {wid} に切り替えました")


    def create_character(self, name: str, data: dict, tags: list[str] = None, notes: str = "") -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        char_id = f"char_{ts}_{uuid.uuid4().hex[:4]}"
        created = datetime.now().isoformat()

        data["items"] = self._normalize_items(data.get("items", []))

        data["id"] = char_id
        self.save_character_file(char_id, data)

        entry = {
            "id": char_id,
            "name": name,
            "created": created,
            "tags": tags or [],
            "notes": notes,
            "level": data.get("level")
        }

        self.entries.append(entry)
        self._save_index()
        self.log.info(f"キャラクター作成: {name} (id={char_id})")
        return char_id

    def save_character_file(self, char_id: str, data: dict):
        path = self.base_dir / f"{char_id}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


    def load_character_file(self, char_id: str) -> dict:
        path = self.base_dir / f"{char_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"キャラクターファイルが見つかりません: {char_id}")
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # itemsを統一形式に変換
        data["items"] = self._normalize_items(data.get("items", []))
        return data


    def delete_character(self, char_id: str) -> bool:
        file_path = self.base_dir / f"{char_id}.json"
        if file_path.exists():
            file_path.unlink()
            self.log.info(f"キャラクターファイル削除: {char_id}")
        return self.delete_entry_by_id(char_id)

    def update_character_entry(self, char_id: str, updates: dict) -> bool:
        return self.update_entry(char_id, updates)

    def rename_character(self, char_id: str, new_name: str) -> bool:
        """キャラクターのnameフィールドとインデックスのnameを変更"""
        try:
            data = self.load_character_file(char_id)
            data["name"] = new_name
            self.save_character_file(char_id, data)

            # インデックス上の表示名も更新
            self.update_character_entry(char_id, {"name": new_name})
            return True
        except FileNotFoundError:
            self.log.warning(f"名前変更失敗（キャラが存在しません）: {char_id}")
            return False
        

    def _normalize_items(self, items):
        """旧仕様（文字列配列）を新仕様（オブジェクト配列）に変換"""
        if isinstance(items, list):
            new_items = []
            for i, item in enumerate(items):
                if isinstance(item, str):
                    new_items.append({"name": item, "count": 1, "description": ""})
                elif isinstance(item, dict):
                    new_items.append({
                        "name": item.get("name", f"item_{i}"),
                        "count": item.get("count", 1),
                        "description": item.get("description", "")
                    })
            return new_items
        return []

