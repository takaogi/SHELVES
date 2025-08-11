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
        elif step == 2:
            return self._handle_action_choice(input_text)
        elif step == 3:
            return self._handle_delete_confirm(input_text)
        else:
            return self.progress_info, "【System】不正なステップです。"

    # --- セッション一覧表示 ---
    def _show_sessions(self) -> tuple[dict, str]:
        sessions = self.session_mgr.list_sessions_by_worldview(self.wid)
        self.flags["_sessions"] = sessions
        self.flags.pop("_selected_session", None)

        lines = [f"『{self.worldview.get('name', '未知の世界')}』のセッションを選んでください："]
        for i, s in enumerate(sessions, start=1):
            title = s.get('title', '(タイトル未設定)')
            status = s.get('status', '?')
            total_chapters = s.get('total_chapters')
            if total_chapters:
                lines.append(f"{i}. {title} [{status}] / 全{total_chapters}章")
            else:
                lines.append(f"{i}. {title} [{status}]")

        lines.append(f"{len(sessions)+1}. 新しいセッションを作成する")

        self.progress_info["step"] = 1
        return self.progress_info, "\n".join(lines)

    # --- 一覧で番号を受け取る ---
    def _handle_selection(self, input_text: str) -> tuple[dict, str]:
        sessions = self.flags.get("_sessions", [])
        try:
            normalized = unicodedata.normalize("NFKC", input_text.strip())
            index = int(normalized) - 1
        except ValueError:
            return self._reject("数字で入力してください。", step=1)

        # 既存セッションを選んだ
        if 0 <= index < len(sessions):
            selected = sessions[index]
            self.flags["_selected_session"] = selected

            title = selected.get("title", "(タイトル未設定)")
            status = selected.get("status", "?")
            total_chapters = selected.get("total_chapters")

            lines = [f"選択: 『{title}』 [{status}]"]

            if total_chapters:
                lines.append(f"全{total_chapters}章構成")

            lines.append("次の操作を選んでください：")
            lines.append("1. セッションを再開する")
            lines.append("2. このセッションを削除する")
            lines.append("3. 一覧に戻る")

            self.progress_info["step"] = 2
            return self.progress_info, "\n".join(lines)

        # 新規作成
        elif index == len(sessions):
            self.progress_info["phase"] = "session_create"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = {"worldview": self.worldview}
            return self.progress_info, None

        return self._reject("範囲内の番号を選んでください。", step=1)

    # --- 再開 or 削除 or 戻る ---
    def _handle_action_choice(self, input_text: str) -> tuple[dict, str]:
        selected = self.flags.get("_selected_session")
        if not selected:
            return self._reject("内部状態が失われました。もう一度選択してください。", step=0)

        try:
            choice = int(unicodedata.normalize("NFKC", input_text.strip()))
        except ValueError:
            return self._reject("数字で入力してください。", step=2)

        if choice == 1:
            # 再開へ移譲
            self.progress_info["phase"] = "session_resume"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = selected
            return self.progress_info, None

        elif choice == 2:
            # 削除確認
            title = selected.get("title", "(タイトル未設定)")
            self.progress_info["step"] = 3
            return self.progress_info, f"『{title}』を本当に削除しますか？\n1. はい（削除）\n2. いいえ（戻る）"

        elif choice == 3:
            # 一覧に戻る
            self.progress_info["step"] = 0
            return self._show_sessions()

        else:
            return self._reject("1〜3の番号で選んでください。", step=2)

    # --- 削除の最終確認 ---
    def _handle_delete_confirm(self, input_text: str) -> tuple[dict, str]:
        selected = self.flags.get("_selected_session")
        if not selected:
            return self._reject("内部状態が失われました。もう一度選択してください。", step=0)

        try:
            choice = int(unicodedata.normalize("NFKC", input_text.strip()))
        except ValueError:
            return self._reject("数字で入力してください。", step=3)

        if choice == 1:
            sid = selected.get("id")
            ok = self.session_mgr.delete_session(sid)
            if ok:
                msg = "セッションを削除しました。"
            else:
                msg = "セッションの削除に失敗しました。"

            # 一覧を再表示
            self.progress_info["step"] = 0
            base_progress, list_text = self._show_sessions()
            # 直前メッセージを冒頭に差し込む
            return base_progress, f"{msg}\n\n{list_text}"

        elif choice == 2:
            # 削除キャンセル → サブメニューへ戻る
            self.progress_info["step"] = 2
            title = selected.get("title", "(タイトル未設定)")
            status = selected.get("status", "?")
            text = (
                f"選択: 『{title}』 [{status}]\n"
                "次の操作を選んでください：\n"
                "1. セッションを再開する\n"
                "2. このセッションを削除する\n"
                "3. 一覧に戻る"
            )
            return self.progress_info, text

        else:
            return self._reject("1か2で選んでください。", step=3)

    # --- 共通リジェクト ---
    def _reject(self, message: str, step: int) -> tuple[dict, str]:
        self.progress_info["step"] = step
        self.progress_info["flags"] = self.flags
        return self.progress_info, message


def handle(ctx, progress_info, input_text):
    return SessionSelect(ctx, progress_info).handle(input_text)
