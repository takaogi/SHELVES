# core/worldview_manager.py

import uuid
from datetime import datetime

from core.base_manager import BaseManager
from infra.path_helper import get_data_path


class WorldviewManager(BaseManager):
    def __init__(self):
        super().__init__("WorldviewManager", "worlds/worldview_index.json")
        self.base_dir = get_data_path("worlds")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_worldview(self, name: str, description: str = "") -> dict:
        ts = datetime.now().strftime("%Y%m%d")
        uid = uuid.uuid4().hex[:4]
        wid = f"worldview_{ts}_{uid}"
        now = datetime.now().isoformat()

        if self.get_entry_by_id(wid):
            raise ValueError(f"同じIDの世界観が既に存在します: {wid}")

        entry = {
            "id": wid,
            "name": name,
            "description": description,
            "created": now,
            "is_default": False,
            "locked": False,

            # 拡張メタデータ（空欄初期化）
            "genre": "",
            "period": "",
            "tone": "",
            "tech_level": "",
            "power_structure": "",
            "world_shape": "",
            "tags": [],
            "nouns_count": 0,
            "characters_count": 0,
            "session_count": 0
        }

        self.entries.append(entry)
        self._save_index()

        dir_path = self.base_dir / wid
        for sub in ["sessions", "characters", "nouns"]:
            (dir_path / sub).mkdir(parents=True, exist_ok=True)

        self.log.info(f"新しい世界観を作成: {name} (id={wid})")
        return entry

    def list_worldviews(self) -> list:
        return self.entries

    def delete_worldview(self, wid: str) -> bool:
        success = self.delete_entry_by_id(wid)
        if success:
            dir_path = self.base_dir / wid
            if dir_path.exists():
                from shutil import rmtree
                rmtree(dir_path)
                self.log.info(f"世界観ディレクトリ削除: {dir_path}")
        return success

    def set_description(self, wid: str, new_description: str) -> bool:
        return self.update_entry(wid, {"description": new_description})
    
    def set_name(self, wid: str, new_name: str) -> bool:
        """世界観の名前を変更する"""
        return self.update_entry(wid, {"name": new_name})
