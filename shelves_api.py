# shelves_api.py
import threading, time, shutil
from pathlib import Path

from core.app_context import AppContext
from core.main_controller import MainController
from core.session_state import SessionState
from core.worldview_manager import WorldviewManager
from core.session_manager import SessionManager
from core.character_manager import CharacterManager
from core.nouns_manager import NounsManager
from core.canon_manager import CanonManager
from ai.chat_engine import ChatEngine

from core.dice import roll_dice
from infra.path_helper import get_data_path, get_resource_path
from infra.logging import get_logger, set_debug_enabled
from infra.net_status import check_online
from infra.logging import set_api_log_callback

log = get_logger("ShelvesAPI")

class ShelvesAPI:
    def __init__(self, debug: bool = False):
        set_debug_enabled(debug)
        self.debug = debug
        self.engine = None
        self.ctx = None
        self.controller = None
        self.state = None
        self.progress_info = None
        self._output_callback = None
        self._input_callback = None
        self._spinner_callback = None

    # -----------------------------
    # 起動準備
    # -----------------------------
    def _ensure_api_key_file(self) -> Path:
        api_key_path = get_resource_path("resources/api_key.txt")
        api_key_path.parent.mkdir(parents=True, exist_ok=True)
        if not api_key_path.exists():
            api_key_path.write_text("PUT_YOUR_API_KEY_HERE\n", encoding="utf-8")
            raise RuntimeError(f"APIキーが存在しません: {api_key_path}")
        return api_key_path

    def _clean_temp_folder(self):
        temp_path = get_data_path("temp")
        temp_path.mkdir(parents=True, exist_ok=True)
        for item in temp_path.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            except Exception as e:
                log.warning(f"[Temp Clean] {item} の削除失敗: {e}")

    def initialize(self):
        """起動準備と初期化"""
        self._clean_temp_folder()
        api_key_path = self._ensure_api_key_file()
        if not check_online():
            raise RuntimeError("ネットワークに接続できません")
        self.engine = ChatEngine(api_key_path=api_key_path, debug=self.debug)

        self.state = SessionState()
        interrupted_session = (
            self.state.last_session.copy()
            if self.state.last_session and self.state.last_session.get("interrupted")
            else None
        )
        self.state.reset()

        self.ctx = AppContext(
            engine=self.engine,
            ui=None,  # UI依存を排除
            state=self.state,
            worldview_mgr=WorldviewManager(),
            session_mgr=SessionManager(),
            character_mgr=CharacterManager(),
            nouns_mgr=NounsManager(),
            canon_mgr=CanonManager()
        )
        self.controller = MainController(self.ctx, debug=self.debug)
        self.progress_info = {
            "phase": "prologue",
            "step": 0,
            "flags": {"interrupted_session": interrupted_session, "startup": True},
        }

    # -----------------------------
    # コールバック設定
    # -----------------------------
    def set_callbacks(self, output_callback, input_callback, spinner_callback=None):
        """
        output_callback(message: str)
        input_callback(prompt: str) -> str
        spinner_callback(action: str)   # "start"/"stop"
        """
        self._output_callback = output_callback
        self._input_callback = input_callback
        self._spinner_callback = spinner_callback

    def set_log_callback(self, log_callback):
        """
        ログをC#側に転送するためのコールバックを登録する
        log_callback(message: str)
        """
        set_api_log_callback(log_callback)

    def _spinner(self, action: str):
        if self._spinner_callback:
            self._spinner_callback(action)

    # -----------------------------
    # ループ制御
    # -----------------------------
    def run_loop(self):
        """ゲームループ（UIイベントをC#に委譲する）"""
        self._running = True

        def loop():
            while self._running:
                # --- ダイスロール要求 ---
                if self.progress_info.get("flags", {}).get("request_dice_roll"):
                    expr = self.progress_info["flags"].pop("request_dice_roll") or "2d6"
                    if self._output_callback:
                        self._output_callback(f"【エンターで {expr} を振ります】")

                    if self._input_callback:
                        _ = self._input_callback("Enterを押してください")

                    result = roll_dice(expr)
                    dice_str = " + ".join(str(d) for d in result["dice"])
                    self.last_input = (
                        f"{dice_str} = {result['total']}" if result["count"] > 1 else f"{result['total']}"
                    )
                    continue

                # --- スピナー開始 ---
                self._spinner("start")

                # ステップ進行
                self.progress_info, output = self.controller.step(
                    self.progress_info, getattr(self, "last_input", "")
                )

                # --- スピナー停止 ---
                self._spinner("stop")

                # 出力があった場合
                if output is not None:
                    if self._output_callback:
                        self._output_callback(output)

                    if self.progress_info.get("auto_continue"):
                        time.sleep(self.progress_info.get("wait_seconds", 1.0))
                        self.progress_info["auto_continue"] = False
                        self.progress_info.pop("wait_seconds", None)
                        continue

                    if self._input_callback:
                        user_input = self._input_callback("入力してください:")
                        self.last_input = user_input
                    else:
                        break

                else:
                    # 出力がなかった場合も自動進行
                    wait_sec = self.progress_info.get("wait_seconds", 0)
                    time.sleep(wait_sec)
                    self.progress_info.pop("wait_seconds", None)
                    self.progress_info["auto_continue"] = False
                    continue

        threading.Thread(target=loop, daemon=True).start()

    def stop_loop(self):
        """ゲームループを終了する"""
        self._running = False
