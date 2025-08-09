# phases/session_select.py
import unicodedata

class SessionSelect:
    def __init__(self, ctx, progress_info):
        self.ctx = ctx
        self.progress_info = progress_info
        self.flags = progress_info.setdefault("flags", {})
        self.session_mgr = ctx.session_mgr
        self.worldview = self.flags.get("worldview", {})
        self.wid = self.worldview.get("id", "")

    def handle(self, input_text: str) -> tuple[dict, str]:
        step = self.progress_info.get("step", 0)
        if step == 0:
            return self._show_sessions()
        elif step == 1:
            return self._handle_selection(input_text)
        else:
            return self.progress_info, "【System】不正なステップです。"

    def _show_sessions(self) -> tuple[dict, str]:
        sessions = self.session_mgr.list_sessions_by_worldview(self.wid)
        self.flags["_sessions"] = sessions

        lines = [f"『{self.worldview.get('name', '未知の世界')}』のセッションを選んでください："]
        for i, s in enumerate(sessions, start=1):
            lines.append(f"{i}. {s.get('title', '(タイトル未設定)')} [{s['status']}]")
        lines.append(f"{len(sessions)+1}. 新しいセッションを作成する")

        self.progress_info["step"] = 1
        return self.progress_info, "\n".join(lines)

    def _handle_selection(self, input_text: str) -> tuple[dict, str]:
        sessions = self.flags.get("_sessions", [])
        try:
            normalized = unicodedata.normalize("NFKC", input_text.strip())
            index = int(normalized) - 1
        except ValueError:
            return self._reject("数字で入力してください。", step=1)

        if 0 <= index < len(sessions):
            selected = sessions[index]
            self.progress_info["phase"] = "session_resume"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = selected 
            return self.progress_info, None

        elif index == len(sessions):
            self.progress_info["phase"] = "session_create"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = {
                "worldview": self.worldview
            }
            return self.progress_info, None

        return self._reject("範囲内の番号を選んでください。", step=1)

    def _reject(self, message: str, step: int) -> tuple[dict, str]:
        self.progress_info["step"] = step
        self.progress_info["flags"] = self.flags
        return self.progress_info, message


def handle(ctx, progress_info, input_text):
    return SessionSelect(ctx, progress_info).handle(input_text)
