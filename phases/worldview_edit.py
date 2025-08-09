# phases/worldview_edit.py
import unicodedata

class WorldviewEdit:
    def __init__(self, ctx, progress_info):
        self.ctx = ctx
        self.progress_info = progress_info
        self.flags = progress_info.setdefault("flags", {})
        self.wvm = ctx.worldview_mgr
        self.state = ctx.state

        self.worldview = self.flags.get("worldview", {})
        self.wid = self.worldview.get("id", "")
        self.meta_fields = [
            ("name", "名称"),
            ("description", "説明"),
            ("genre", "ジャンル"),
            ("period", "時代"),
            ("tone", "雰囲気"),
            ("world_shape", "世界の形"),
        ]

    def handle(self, input_text: str) -> tuple[dict, str]:
        step = self.progress_info.get("step", 0)

        if not self.wid:
            return self._fail("世界観IDが指定されていません。")

        match step:
            case 0:
                return self._ask_edit_target()
            case 1:
                return self._handle_target_selection(input_text)
            case 2:
                return self._handle_worldview_field_selection(input_text)
            case 3:
                return self._apply_worldview_update(input_text)
            case _:
                return self._fail("不正なステップです。")

    def _ask_edit_target(self) -> tuple[dict, str]:
        self.progress_info["step"] = 1
        return self.progress_info, (
            "編集対象を選んでください：\n"
            "1. 世界観のメタ情報\n"
            "2. 登場キャラクター（未実装）\n"
            "3. 固有名詞（未実装）\n"
            "4. 戻る\n"
            "5. この世界観を削除する"
        )

    def _handle_target_selection(self, input_text: str) -> tuple[dict, str]:
        choice = unicodedata.normalize("NFKC", input_text.strip())

        if choice == "1":
            self.progress_info["step"] = 2
            self.progress_info["auto_continue"] = True
            return self._show_worldview_fields()

        elif choice == "2":
            self.progress_info["auto_continue"] = True
            return self._reject("キャラクター編集機能は未実装です。", step=0)

        elif choice == "3":
            self.progress_info["auto_continue"] = True
            return self._reject("固有名詞編集機能は未実装です。", step=0)

        elif choice == "4":
            self.progress_info["phase"] = "worldview_select"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = {}
            self.progress_info["auto_continue"] = True
            return self.progress_info, "世界観選択に戻ります。"

        elif choice == "5":
            if self.worldview.get("locked"):
                self.progress_info["auto_continue"] = True
                return self._reject("この世界観は削除できません。", step=0)

            deleted = self.wvm.delete_worldview(self.wid)
            if deleted:
                self.progress_info["phase"] = "worldview_select"
                self.progress_info["step"] = 0
                self.progress_info["auto_continue"] = True
                self.progress_info["flags"] = {}
                return self.progress_info, f"世界観『{self.worldview.get('name', '')}』を削除しました。"
            else:
                self.progress_info["auto_continue"] = True
                return self._reject("削除に失敗しました。", step=0)

        return self._reject("1～5 の番号で選んでください。", step=1)

    def _show_worldview_fields(self) -> tuple[dict, str]:
        latest = self.wvm.get_entry_by_id(self.wid) or {}
        self.flags["worldview"] = latest

        lines = ["編集する項目を選んでください："]
        for i, (key, label) in enumerate(self.meta_fields, start=1):
            value = latest.get(key, "")
            lines.append(f"{i}. {label}：{value}")
        lines.append(f"{len(self.meta_fields)+1}. 編集対象選択に戻る")

        self.progress_info["step"] = 2
        return self.progress_info, "\n".join(lines)

    def _handle_worldview_field_selection(self, input_text: str) -> tuple[dict, str]:
        try:
            index = int(unicodedata.normalize("NFKC", input_text.strip())) - 1
        except ValueError:
            return self._reject("番号で選んでください。", step=2)

        if 0 <= index < len(self.meta_fields):
            key, label = self.meta_fields[index]
            self.flags["_edit_key"] = key
            self.flags["_edit_label"] = label
            self.progress_info["step"] = 3
            return self.progress_info, f"{label} の新しい値を入力してください："

        elif index == len(self.meta_fields):
            return self._ask_edit_target()

        return self._reject("範囲内の番号を選んでください。", step=2)

    def _apply_worldview_update(self, input_text: str) -> tuple[dict, str]:
        key = self.flags.get("_edit_key")
        label = self.flags.get("_edit_label")

        if not key:
            return self._reject("編集中の項目が不明です。", step=0)

        new_value = input_text.strip()
        if key == "tags":
            new_value = [t.strip() for t in new_value.split(",") if t.strip()]

        success = self.wvm.update_entry(self.wid, {key: new_value})
        if success:
            self.flags.pop("_edit_key", None)
            self.flags.pop("_edit_label", None)
            self.progress_info["step"] = 2
            self.progress_info["auto_continue"] = True
            return self.progress_info, f"{label} を更新しました。\n再度項目を選んでください："
        else:
            return self._reject("更新に失敗しました。", step=2)

    def _reject(self, message: str, step: int) -> tuple[dict, str]:
        self.progress_info["step"] = step
        return self.progress_info, message

    def _fail(self, message: str) -> tuple[dict, str]:
        self.progress_info["phase"] = "worldview_select"
        self.progress_info["step"] = 0
        self.progress_info["flags"] = {}
        return self.progress_info, f"【エラー】{message}"


def handle(ctx, progress_info, input_text):
    return WorldviewEdit(ctx, progress_info).handle(input_text)
