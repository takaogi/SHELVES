import unicodedata


class SessionResume:
    def __init__(self, ctx, progress_info):
        self.ctx = ctx
        self.progress_info = progress_info
        self.flags = progress_info.setdefault("flags", {})
        self.session_mgr = ctx.session_mgr

    def handle(self, input_text: str) -> tuple[dict, str]:
        step = self.progress_info.get("step", 0)

        match step:
            case 0:
                return self._handle_session_selection(input_text)
            case 1:
                return self._handle_continuation_decision(input_text)
            case _:
                return self.progress_info, "【System】不正なステップです。"

    def _handle_session_selection(self, input_text: str) -> tuple[dict, str]:
        sid = self.flags.get("id")
        wid = self.flags.get("worldview_id")

        if not sid or not wid:
            return self._fail("セッションIDまたは世界観IDが見つかりません。")

        result = self.session_mgr.resume_session(sid)

        if result == "resumed":
            self.ctx.state.mark_session_start(wid, sid)

            self.progress_info["phase"] = "scenario"
            self.progress_info["step"] = 0
            self.progress_info["auto_continue"] = True
            return self.progress_info, "セッションを再開します。"

        elif result == "not_started":
            self.session_mgr.activate_session(sid)
            self.ctx.state.mark_session_start(wid, sid)

            self.progress_info["phase"] = "scenario"
            self.progress_info["step"] = 0
            return self.progress_info, None

        elif result == "ended":
            session = self.session_mgr.get_entry_by_id(sid)
            title = session.get("title", "（無題）")

            self.flags["id"] = sid
            self.flags["title"] = title
            self.flags["worldview_id"] = wid

            self.progress_info["step"] = 1
            return self.progress_info, (
                f"セッション『{title}』はすでに終了しています。\n"
                "このセッションの続編として新しいセッションを開始しますか？（はい／いいえ）"
            )

        else:
            return self._fail("指定されたセッションは存在しないか、再開できません。")


    def _handle_continuation_decision(self, input_text: str) -> tuple[dict, str]:
        text = unicodedata.normalize("NFKC", input_text.strip())

        if text in ("はい", "はい。", "yes", "y", "うん"):
            old_sid = self.flags["id"]
            wid = self.flags.get("worldview_id")

            # 元セッションのプレイヤーキャラを取得
            session = self.session_mgr.get_entry_by_id(old_sid) or {}
            pcid = session.get("player_character")
            pc_data = None
            if pcid:
                self.ctx.character_mgr.set_worldview_id(wid)
                try:
                    pc_data = self.ctx.character_mgr.load_character_file(pcid)
                except FileNotFoundError:
                    pc_data = None

            self.progress_info["phase"] = "session_create"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = {
                "sequel_to": old_sid,
                "worldview_id": wid,
                "player_character": pc_data
            }
            self.progress_info["auto_continue"] = True
            return self.progress_info, "続編セッションの作成を開始します。"



        else:
            return self._fail("セッションの再開は中止されました。")

    def _fail(self, message: str) -> tuple[dict, str]:
        self.progress_info["phase"] = "prologue"
        self.progress_info["step"] = 0
        return self.progress_info, f"【System】{message}"
