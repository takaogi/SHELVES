# main_android.py
import os
import shutil
import time
import threading
from infra.path_helper import get_data_path
from infra.logging import get_logger, set_debug_enabled
from infra.net_status import check_online

from ai.chat_engine import ChatEngine
from core.main_controller import MainController
from core.session_state import SessionState
from core.app_context import AppContext
from core.worldview_manager import WorldviewManager
from core.session_manager import SessionManager
from core.character_manager import CharacterManager
from core.nouns_manager import NounsManager
from core.canon_manager import CanonManager
from core.dice import roll_dice

# Android は Kivy 固定
from ui.message_console_kivy import MessageConsole_kivyApp

log = get_logger("MainAndroid")
os.environ["KIVY_NO_ARGS"] = "1"  # argparse 無効化


def init_engine_with_retry(ui, state: SessionState, interrupted_session):
    api_key_path = get_data_path("api_key.txt")

    def check_and_retry(user_input=None):
        if user_input is not None:
            api_key_path.write_text(user_input.strip(), encoding="utf-8")
            log.info("APIキーを保存しました。")

        if not api_key_path.exists():
            ui.safe_print("System", "APIキーが存在しません。入力してください：")
            ui.wait_for_input(check_and_retry)
            return

        api_key = api_key_path.read_text(encoding="utf-8").strip()
        if not api_key or not api_key.startswith("sk-"):
            ui.safe_print("System", "APIキーが不正です。再入力してください：")
            ui.wait_for_input(check_and_retry)
            return

        if not check_online():
            ui.safe_print("System", "ネットワーク未接続。接続してから Enter を押してください。")
            ui.wait_for_enter("", lambda _: check_and_retry(None))
            return

        try:
            engine = ChatEngine(api_key_path=api_key_path, debug=False)
            ctx = AppContext(
                engine=engine,
                ui=ui,
                state=state,
                worldview_mgr=WorldviewManager(),
                session_mgr=SessionManager(),
                character_mgr=CharacterManager(),
                nouns_mgr=NounsManager(),
                canon_mgr=CanonManager()
            )
            controller = MainController(ctx)

            progress_info = {
                "phase": "prologue",
                "step": 0,
                "flags": {"interrupted_session": interrupted_session, "startup": True}
            }
            run_loop(ui, controller, progress_info)

        except Exception as e:
            log.error(f"APIキー検証に失敗: {e}")
            ui.safe_print("System", "APIキーが無効です。再入力してください：")
            ui.wait_for_input(check_and_retry)

    check_and_retry()


def clean_temp_folder():
    temp_path = get_data_path("temp")
    temp_path.mkdir(parents=True, exist_ok=True)
    for item in temp_path.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
        except Exception as e:
            log.warning(f"[Temp Clean] {item} 削除失敗: {e}")


def run_loop(ui, controller: MainController, progress_info: dict, last_input: str = ""):
    def loop():
        nonlocal progress_info, last_input
        current_input = last_input or ""
        while True:
            if progress_info.get("flags", {}).get("request_dice_roll"):
                expr = progress_info["flags"].pop("request_dice_roll") or "2d6"
                prompt = f"【エンターで {expr} を振ります】"

                def _after_enter(_=""):
                    result = roll_dice(expr)
                    dice_str = " + ".join(str(d) for d in result["dice"])
                    user_input = f"{dice_str} = {result['total']}" if result["count"] > 1 else f"{result['total']}"
                    ui.start_spinner()
                    run_loop(ui, controller, progress_info, user_input)

                ui.wait_for_enter(prompt, _after_enter)
                break

            progress_info, output = controller.step(progress_info, current_input)
            if output is not None:
                ui.safe_print("System", output)
                if progress_info.get("auto_continue"):
                    time.sleep(progress_info.get("wait_seconds", 1.0))
                    progress_info["auto_continue"] = False
                    current_input = last_input
                    continue
                else:
                    ui.wait_for_input(lambda user_input: run_loop(ui, controller, progress_info, user_input))
                    break

            time.sleep(progress_info.get("wait_seconds", 0))
            progress_info.pop("wait_seconds", None)
            progress_info["auto_continue"] = False
            current_input = last_input

    ui.start_spinner()
    threading.Thread(target=loop, daemon=True).start()


def main():
    set_debug_enabled(False)
    clean_temp_folder()

    ui = MessageConsole_kivyApp()
    state = SessionState()
    interrupted_session = (
        state.last_session.copy()
        if state.last_session and state.last_session.get("interrupted")
        else None
    )
    state.reset()

    from kivy.clock import Clock
    Clock.schedule_once(lambda dt: init_engine_with_retry(ui, state, interrupted_session), 0)
    ui.run()


if __name__ == "__main__":
    main()
