# main.py
import argparse
import shutil
import threading
import time
import sys
from pathlib import Path

from core.main_controller import MainController
from core.session_state import SessionState
from core.app_context import AppContext
from core.worldview_manager import WorldviewManager
from core.session_manager import SessionManager
from core.nouns_manager import NounsManager
from core.character_manager import CharacterManager
from core.canon_manager import CanonManager
from core.dice import roll_dice

from ai.chat_engine import ChatEngine

from infra.path_helper import get_data_path, get_resource_path
from infra.logging import get_logger, set_debug_enabled
from infra.net_status import check_online

log = get_logger("Main")

def ensure_api_key_file() -> Path:
    """resources/api_key.txt を保証し、無ければダミーを生成"""
    api_key_path = get_resource_path("resources/api_key.txt")
    api_key_path.parent.mkdir(parents=True, exist_ok=True)

    if not api_key_path.exists():
        dummy_text = "PUT_YOUR_API_KEY_HERE\n"
        api_key_path.write_text(dummy_text, encoding="utf-8")
        msg = f"[致命的エラー] APIキーが存在しないため、ダミーファイルを生成しました: {api_key_path}\n" \
              "このファイルを編集して正しいAPIキーを入力し、再実行してください。"
        raise RuntimeError(msg)

    return api_key_path

def clean_temp_folder():
    temp_path = get_data_path("temp")
    temp_path.mkdir(parents=True, exist_ok=True)  # 必ず存在する状態にする

    for item in temp_path.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
        except Exception as e:
            log.warning(f"[Temp Clean] {item} の削除失敗: {e}")



def run_loop(ui, controller: MainController, progress_info: dict, last_input: str = ""):
    def loop():
        nonlocal progress_info, last_input

        current_input = last_input or ""
        while True:

            phase = progress_info.get("phase")
            step = progress_info.get("step")
            log.debug(f"[Progress] phase: {phase}, step: {step}, last_input:{last_input}")

            if progress_info.get("flags", {}).get("request_dice_roll"):
                expr = progress_info["flags"].pop("request_dice_roll") or "2d6"

                ui.wait_for_enter(f"【エンターで {expr} を振ります】")
                result = roll_dice(expr)

                dice_str = " + ".join(str(d) for d in result["dice"])
                # 1個ならそのまま、複数なら合計表示付き
                if result["count"] > 1:
                    last_input = f"{dice_str} = {result['total']}"
                else:
                    last_input = f"{result['total']}"

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
    # 起動オプション解析
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="デバッグモードを有効にする")
    parser.add_argument("--ui", choices=["tk", "kivy"], default="kivy", help="UIフレームワークを選択 (tk/kivy)")
    args = parser.parse_args()
    set_debug_enabled(args.debug)

    clean_temp_folder()

    #api_keyとネットワークをチェック
    try:
        api_key_path = ensure_api_key_file()
        if not check_online():
            raise RuntimeError("[致命的エラー] ネットワークに接続できません。オンライン専用アプリです。")
        engine = ChatEngine(api_key_path=api_key_path, debug=args.debug)

    except Exception as e:
        log.error(str(e))
        input("Enter を押して終了します。")
        sys.exit(1)

    # --- UI切り替え ---
    if args.ui == "kivy":
        from ui.message_console_kivy import MessageConsole_kivyApp
        ui = MessageConsole_kivyApp()
    elif args.ui == "tk":
        from ui.message_console import MessageConsole_tk
        ui = MessageConsole_tk()
    else :
        pass

    state = SessionState()

    interrupted_session = (
        state.last_session.copy()
        if state.last_session and state.last_session.get("interrupted")
        else None
    )
    state.reset()


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

    if args.debug:
        ui.safe_print("System", "［Debug］デバッグモード有効")

    controller = MainController(ctx, debug=args.debug)

    progress_info = {
        "phase": "prologue",
        "step": 0,
        "flags": {
            "interrupted_session": interrupted_session,
            "startup": True
        }
    }

    # --- UI差分処理 ---
    if args.ui == "kivy":
        # Kivy は run() 内でメインループ開始
        ui.run()
    else:
        ui.root.after(0, lambda: run_loop(ui, controller, progress_info))
        ui.run()

if __name__ == "__main__":
    main()
