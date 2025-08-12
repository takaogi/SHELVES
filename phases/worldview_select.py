# phases/worldview_select.py
import unicodedata

class WorldviewSelect:
    def __init__(self, ctx, progress_info):
        self.ctx = ctx
        self.progress_info = progress_info
        self.flags = progress_info.setdefault("flags", {})
        self.state = ctx.state
        self.wvm = ctx.worldview_mgr

    def handle(self, input_text: str) -> tuple[dict, str]:
        step = self.progress_info.get("step", 0)

        match step:
            case 0:
                return self._show_worldviews()
            case 1:
                return self._handle_selection(input_text)
            case 2:
                return self._handle_worldview_action(input_text)
            case _:
                return self.progress_info, "【System】不正なステップです。"

    def _show_worldviews(self) -> tuple[dict, str]:
        worldviews = self.wvm.list_worldviews()
        self.flags["_worldviews"] = worldviews

        lines = ["世界観を選んでください："]
        for i, w in enumerate(worldviews, start=1):
            lines.append(f"{i}. {w['name']} - {w.get('description', '')}")
        lines.append(f"{len(worldviews) + 1}. 新しい世界観を作成する")

        self.progress_info["step"] = 1
        return self.progress_info, "\n".join(lines)

    def _handle_selection(self, input_text: str) -> tuple[dict, str]:
        worldviews = self.flags.get("_worldviews", [])
        try:
            normalized = unicodedata.normalize("NFKC", input_text.strip())
            index = int(normalized) - 1
        except ValueError:
            return self._reject("数字で入力してください。", step=1)

        if 0 <= index < len(worldviews):
            selected = worldviews[index]
            self.state.worldview_id = selected["id"]
            self.flags["worldview"] = selected

            self.progress_info["step"] = 2
            self.progress_info["flags"] = self.flags

            name = selected["name"]
            message = (
                f"本棚『{name}』を選びました。どうしますか？\n"
                "1. セッション一覧を見る\n"
                "2. 世界観を編集する(WIP dataファイルを自分で編集したほうが100倍速い)\n"
                "3. 戻る"
            )
            return self.progress_info, message

        elif index == len(worldviews):
            self.progress_info["phase"] = "worldview_create"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = {}
            return self.progress_info, None

        return self._reject("範囲内の番号を選んでください。", step=1)

    def _handle_worldview_action(self, input_text: str) -> tuple[dict, str]:
        choice = unicodedata.normalize("NFKC", input_text.strip())
        selected = self.flags.get("worldview")

        if not selected:
            return self._reject("選択された世界観が不明です。", step=0)

        if choice == "1":
            self.progress_info["phase"] = "session_select"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = {"worldview": selected}
            return self.progress_info, None

        elif choice == "2":
            self.progress_info["phase"] = "worldview_edit"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = {"worldview": selected}
            return self.progress_info, None
        
        elif choice == "3":
            self.progress_info["step"] = 0
            self.progress_info["auto_continue"] = True
            return self.progress_info, "世界観選択に戻ります。"

        return self._reject("1~3の番号を入力してください。", step=2)

    def _reject(self, message: str, step: int | None = None) -> tuple[dict, str]:
        self.progress_info["step"] = step if step is not None else self.progress_info.get("step", 0)
        self.progress_info["flags"] = self.flags
        return self.progress_info, message


def handle(ctx, progress_info, input_text):
    return WorldviewSelect(ctx, progress_info).handle(input_text)
