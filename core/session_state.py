from pathlib import Path
import json
from infra.path_helper import get_data_path
from infra.logging import get_logger

class SessionState:
    def __init__(self):
        self.log = get_logger("SessionState")

        self.worldview_id: str = "default"
        self.session_id: str = "default"
        self.last_session: dict | None = None

        self._state_path = get_data_path("worlds/state.json")
        self._load_state()

    def reset(self):
        self.worldview_id = "default"
        self.session_id = "default"
        self.last_session = None
        self._save_state()
        self.log.info("セッション状態を初期化しました")

    def mark_session_start(self, wid: str, sid: str):
        self.worldview_id = wid
        self.session_id = sid
        self.last_session = {
            "wid": wid,
            "sid": sid,
            "interrupted": True
        }
        self._save_state()
        self.log.info(f"セッション開始: {wid} / {sid}")

    def mark_session_end(self):
        if self.last_session:
            self.last_session["interrupted"] = False
        self._save_state()
        self.log.info("セッション終了: 中断フラグ解除")

    def has_interrupted_session(self) -> bool:
        return bool(self.last_session and self.last_session.get("interrupted", False))


    def _save_state(self):
        state = {
            "worldview_id": self.worldview_id,
            "session_id": self.session_id,
            "last_session": self.last_session
        }
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log.warning(f"状態保存失敗: {e}")

    def _load_state(self):
        if not self._state_path.exists():
            self.log.info("state.json が存在しないため初期化")
            return
        try:
            with open(self._state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
                self.worldview_id = state.get("worldview_id", "default")
                self.session_id = state.get("session_id", "default")
                self.last_session = state.get("last_session", None)
                self.log.info(f"状態復元: last_session: {self.last_session}")

        except Exception as e:
            self.log.warning(f"状態読み込み失敗: {e}")
