# core/canon_manager.py
import uuid
from datetime import datetime
from core.base_manager import BaseManager
from infra.path_helper import get_data_path
from infra.logging import get_logger


class CanonManager(BaseManager):
    def __init__(self):
        self.wid = None
        self.sid = None
        self.log = get_logger("CanonManager")
        self.entries = []
        self.base_dir = None
        self.index_file = None

    def set_context(self, worldview_id: str, session_id: str):
        self.wid = worldview_id
        self.sid = session_id
        self.base_dir = get_data_path(f"worlds/{worldview_id}/sessions/{session_id}/canon")
        self.index_file = self.base_dir / "canon_index.json"
        
        # 📌 親ディレクトリがなければ作成
        self.index_file.parent.mkdir(parents=True, exist_ok=True)

        self.entries = self._load_index()
        self.log.info(f"CanonManager: context set to worldview={worldview_id}, session={session_id}")


    def create_fact(self, name: str, type: str, notes: str, chapter: int = 0) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        canon_id = f"canon_{ts}_{uuid.uuid4().hex[:4]}"
        created = datetime.now().isoformat()

        entry = {
            "id": canon_id,
            "name": name,
            "type": type,
            "notes": notes,
            "created": created
        }

        self.entries.append(entry)
        self._save_index()
        self.log.info(f"カノン作成: {name} (id={canon_id}, type={type})")
        return canon_id

    def append_history(self, canon_id: str, text: str, chapter: int):
        entry = self.get_entry_by_id(canon_id)
        if not entry:
            self.log.warning(f"append_history: 該当するcanonが存在しません: {canon_id}")
            return False
        entry.setdefault("history", []).append({
            "chapter": chapter,
            "text": text
        })
        self._save_index()
        self.log.info(f"カノン {canon_id} に履歴を追加: ch{chapter}")
        return True
