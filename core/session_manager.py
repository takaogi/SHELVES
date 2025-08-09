# core/session_manager.py

import uuid
import shutil
import json
from datetime import datetime
from pathlib import Path

from core.base_manager import BaseManager
from infra.path_helper import get_data_path


class SessionManager(BaseManager):
    def __init__(self):
        super().__init__("SessionManager", "worlds/session_index.json")
        self.active_session_id = "default"

    def list_sessions(self) -> list:
        return self.entries

    def list_sessions_by_worldview(self, worldview_id: str) -> list:
        return [s for s in self.entries if s.get("worldview_id") == worldview_id]

    def new_session(self, worldview_id: str, title: str = "", player_character_id: str| None = None, chapter: int = 1) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        sid = f"session_{ts}_{uuid.uuid4().hex[:4]}"
        created = datetime.now().isoformat()

        entry = {
            "id": sid,
            "worldview_id": worldview_id,
            "status": "preparation",
            "title": title,
            "player_character": player_character_id or None,
            "current_chapter": chapter,
            "created": created
        }

        self.entries.append(entry)
        self._save_index()
        self.active_session_id = sid

        session_dir = get_data_path(f"worlds/{worldview_id}/sessions/{sid}")
        session_dir.mkdir(parents=True, exist_ok=True)

        self.log.info(f"新しいセッションを作成: {sid}（世界観: {worldview_id}, タイトル: {title}）")
        return sid

    def clone_session_as_sequel(self, old_sid: str, new_title: str) -> str:
        old = self.get_entry_by_id(old_sid)
        if not old:
            raise ValueError(f"指定されたセッションIDが存在しません: {old_sid}")

        worldview_id = old["worldview_id"]
        player_character = old.get("player_character", {})
        created = datetime.now().isoformat()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_sid = f"session_{ts}_{uuid.uuid4().hex[:4]}"

        new_entry = {
            "id": new_sid,
            "worldview_id": worldview_id,
            "status": "preparation",
            "title": new_title,
            "player_character": player_character,
            "current_chapter": 1,
            "created": created,
            "cloned_from": old_sid
        }

        self.entries.append(new_entry)
        self._save_index()
        self.active_session_id = new_sid

        to_dir = get_data_path(f"worlds/{worldview_id}/sessions/{new_sid}")
        to_dir.mkdir(parents=True, exist_ok=True)

        from_summary = get_data_path(f"worlds/{worldview_id}/sessions/{old_sid}/summary.txt")
        to_summary = to_dir / "previous_summary.txt"
        if from_summary.exists():
            shutil.copy2(from_summary, to_summary)

        self.log.info(f"セッション {old_sid} を元に続編セッション作成: {new_sid} → {new_title}")
        return new_sid

    def resume_session(self, sid: str) -> str | None:
        entry = self.get_entry_by_id(sid)
        if not entry:
            self.log.warning(f"指定されたセッションが見つかりません: {sid}")
            return None

        status = entry.get("status")

        if status == "active":
            self.active_session_id = sid
            self.log.info(f"セッション再開: {sid}")
            return "resumed"

        elif status == "preparation":
            self.active_session_id = sid
            self.log.info(f"セッションは未開始（準備中）: {sid}")
            return "not_started"

        elif status == "ended":
            self.log.info(f"セッションは終了済み: {sid}")
            return "ended"

        self.log.warning(f"セッションの状態が不明: {sid} -> {status}")
        return None


    def end_session(self, sid: str) -> bool:
        success = self.update_entry(sid, {"status": "ended"})
        if success and self.active_session_id == sid:
            self.active_session_id = "default"
        return success

    def delete_session(self, sid: str) -> bool:
        entry = self.get_entry_by_id(sid)
        if not entry:
            self.log.warning(f"削除対象のセッションが見つかりません: {sid}")
            return False

        worldview_id = entry["worldview_id"]
        success = self.delete_entry_by_id(sid)

        if success:
            if self.active_session_id == sid:
                self.active_session_id = "default"

            session_dir = get_data_path(f"worlds/{worldview_id}/sessions/{sid}")
            if session_dir.exists():
                shutil.rmtree(session_dir)
                self.log.info(f"セッションディレクトリを削除しました: {session_dir}")
            else:
                self.log.info(f"セッションディレクトリが存在しません: {session_dir}")
        return success

    def set_session_title(self, sid: str, title: str) -> bool:
        return self.update_entry(sid, {"title": title})

    def activate_session(self, sid: str) -> bool:
        entry = self.get_entry_by_id(sid)
        if entry and entry["status"] == "preparation":
            return self.update_entry(sid, {"status": "active"})
        self.log.warning(f"アクティブ化対象のセッションが見つからないか既に開始済み: {sid}")
        return False

    def leave_session(self) -> bool:
        if self.active_session_id != "default":
            self.log.info(f"セッション {self.active_session_id} から退出しました（defaultに移行）")
            self.active_session_id = "default"
            return True
        else:
            self.log.info("退出操作：すでに default またはアクティブなセッションが存在しません。")
            return False

    def get_summary_path(self, worldview_id: str, session_id: str) -> Path:
        return get_data_path(f"worlds/{worldview_id}/sessions/{session_id}/previous_summary.txt")
    
    def save_scenario_data(self, worldview_id: str, session_id: str, meta: dict, draft: dict, raw_input: str = "") -> None:
        base_dir = get_data_path(f"worlds/{worldview_id}/sessions/{session_id}")
        base_dir.mkdir(parents=True, exist_ok=True)

        combined = {
            "meta": meta,
            "draft": draft,
            "raw_input": raw_input.strip()
        }

        path = base_dir / "scenario.json"
        path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")

        self.log.info(f"シナリオ構成情報を保存: {path}")


