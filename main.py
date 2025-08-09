# main.py

import shutil
import threading
import time

from ui.message_console import MessageConsole

from core.main_controller import MainController
from core.session_state import SessionState
from core.app_context import AppContext
from core.worldview_manager import WorldviewManager
from core.session_manager import SessionManager
from core.nouns_manager import NounsManager
from core.character_manager import CharacterManager
from core.canon_manager import CanonManager

from ai.chat_engine import ChatEngine

from infra.path_helper import get_data_path, get_resource_path
from infra.logging import get_logger
from infra.net_status import check_online

log = get_logger("Main")



def _show_offline_and_wait(ui: MessageConsole, controller: MainController, progress_info: dict):
    # 一度だけメッセージを出す（スパム防止）
    flags = progress_info.setdefault("flags", {})
    if not flags.get("_offline_warned"):
        ui.safe_print("System", "[致命的エラー] ネットワークに接続できません。\nオンラインでのみ動作します。接続後に何か入力して再試行してください。")
        flags["_offline_warned"] = True

    def retry(_user_input: str):
        # 入力は使わず再試行（現在の progress_info を維持）
        run_loop(ui, controller, progress_info, "")

    ui.wait_for_input(retry)


def clean_temp_folder():
    temp_path = get_data_path("temp")
    if temp_path.exists():
        shutil.rmtree(temp_path)


def run_loop(ui: MessageConsole, controller: MainController, progress_info: dict, last_input: str = ""):
    def loop():
        nonlocal progress_info, last_input

        current_input = last_input or ""
        while True:
            # オンライン必須。未接続ならエラー表示して入力待ち → 再試行
            if not progress_info.get("_offline_checked"):
                progress_info["_offline_checked"] = True
                if not check_online():
                    _show_offline_and_wait(ui, controller, progress_info)
                    break


            phase = progress_info.get("phase")
            step = progress_info.get("step")
            log.debug(f"[Progress] phase: {phase}, step: {step}, last_input:{last_input}")

            # ダイス要求があれば処理
            if progress_info.get("flags", {}).get("request_dice_roll"):
                progress_info["flags"].pop("request_dice_roll", None)
                result = ui.roll_2d6()
                last_input = f"{result['dice'][0]} + {result['dice'][1]} = {result['total']}"
                current_input = last_input
                ui.start_spinner()
                continue

            # ステップ進行
            progress_info, output = controller.step(progress_info, current_input)

            # 出力があれば表示
            if output is not None:
                ui.safe_print("System", output)

                if progress_info.get("auto_continue"):
                    wait_sec = progress_info.get("wait_seconds", 1.0)
                    time.sleep(wait_sec)
                    progress_info["auto_continue"] = False
                    progress_info.pop("wait_seconds", None)
                    current_input = last_input
                    continue
                else:
                    # 入力待ち
                    def handle_input(user_input: str):
                        ui.safe_print("Player", user_input)
                        run_loop(ui, controller, progress_info, user_input)

                    ui.wait_for_input(handle_input)

                    break

            # 出力なしでも一応継続条件を満たす
            wait_sec = progress_info.get("wait_seconds", 0)
            time.sleep(wait_sec)
            progress_info.pop("wait_seconds", None)
            progress_info["auto_continue"] = False
            current_input = last_input

    ui.start_spinner()
    threading.Thread(target=loop, daemon=True).start()


def main():
    clean_temp_folder()

    ui = MessageConsole()
    state = SessionState()

    interrupted_session = (
        state.last_session.copy()
        if state.last_session and state.last_session.get("interrupted")
        else None
    )
    state.reset()

    ctx = AppContext(
        engine=ChatEngine(api_key_path=get_resource_path("resources/api_key.txt")),
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
        "flags": {
            "interrupted_session": interrupted_session,
            "startup": True
        }
    }

    ui.root.after(0, lambda: run_loop(ui, controller, progress_info))
    ui.run()


if __name__ == "__main__":
    main()
