# phases/prologue.py

import unicodedata

class Prologue:
    def __init__(self, ctx, progress_info):
        self.ctx = ctx
        self.progress_info = progress_info
        self.flags = progress_info.setdefault("flags", {})

    def handle(self, input_text: str) -> tuple[dict, str]:
        step = self.progress_info.get("step", 0)

        match step:
            case 0:
                return self._step_startup()
            case 10:
                return self._step_check_interrupted()
            case 11:
                return self._step_handle_resume_choice(input_text)
            case _:
                return self.progress_info, "【System】不正なステップです。"


    def _step_startup(self) -> tuple[dict, str]:
        if self.flags.get("startup", False):
            lines = [
                "＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝",
                "　　　S.H.E.L.V.E.S.",
                "　Script Handlers for the Emulated Library and Virtual Experience System",
                "＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝",
                "",
                "空想の書架へようこそ。\n"
            ]
            index = self.flags.get("_boot_index", 0)

            # 0.5秒ごとに自動進行
            self.progress_info["auto_continue"] = True
            self.flags["_boot_index"] = index + 1

            if index < len(lines):
                # まだ残り行がある
                self.progress_info["step"] = 0
                self.progress_info["wait_seconds"] = 0.5
                return self.progress_info, lines[index]
            else:
                # 全行出力完了
                self.flags.pop("_boot_index", None)
                self.flags["startup"] = False
                self.progress_info["step"] = 10
                return self.progress_info, ""
        else:
            self.progress_info["step"] = 10
            return self.progress_info, None


    def _step_check_interrupted(self) -> tuple[dict, str]:
        if self.flags.get("interrupted_session"):
            self.progress_info["step"] = 11
            return self.progress_info, "前回のセッションが中断されています。再開しますか？\n1. はい\n2. いいえ"
        else:
            return self._go_to_worldview_select()

    def _step_handle_resume_choice(self, input_text: str) -> tuple[dict, str]:
        choice = unicodedata.normalize("NFKC", input_text.strip())

        if choice == "1":
            raw = self.flags.get("interrupted_session")
            if raw and "sid" in raw and "wid" in raw:
                session = {
                    "id": raw["sid"],
                    "worldview_id": raw["wid"]
                }
                self.progress_info["phase"] = "session_resume"
                self.progress_info["step"] = 0
                self.progress_info["flags"] = session
                return self.progress_info, None
            else:
                return self._reject("中断情報が見つかりません。", step=10)

        elif choice == "2":
            return self._go_to_worldview_select()

        else:
            return self._reject("1 または 2 を選んでください。", step=11)

    def _go_to_worldview_select(self) -> tuple[dict, str]:
        self.progress_info["phase"] = "worldview_select"
        self.progress_info["step"] = 0
        self.progress_info["flags"] = {}
        return self.progress_info, None

    def _reject(self, message: str, step: int) -> tuple[dict, str]:
        self.progress_info["step"] = step
        self.progress_info["flags"] = self.flags
        return self.progress_info, message
