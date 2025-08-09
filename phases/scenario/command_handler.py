# phases/scenario/command_handler.py

class CommandHandler:
    def __init__(self, ctx, wid, sid):
        self.ctx = ctx
        self.wid = wid
        self.sid = sid

    def execute(self, command: str, args: list[str], chapter: int = 0):
        if command == "add_item" and len(args) == 1:
            return self._add_item(args[0])
        elif command == "remove_item" and len(args) == 1:
            return self._remove_item(args[0])
        elif command == "add_history" and len(args) == 2:
            return self._add_history(args[0], args[1], chapter)
        return False

    # --- helpers ---
    def _get_player_character_id(self) -> str | None:
        session = self.ctx.session_mgr.get_entry_by_id(self.sid)
        pc = session.get("player_character")
        if isinstance(pc, dict):
            return pc.get("id")
        return pc  # 文字列ID or None

    # --- inventory ops ---
    def _add_item(self, item_name: str):
        cm = self.ctx.character_mgr
        pcid = self._get_player_character_id()
        if not pcid:
            return False

        char = cm.load_character_file(pcid)
        items = char.setdefault("items", [])
        if item_name not in items:
            items.append(item_name)
        char["items"] = items

        cm.save_character_file(pcid, char)  # ← 正しいシグネチャ
        return True

    def _remove_item(self, item_name: str):
        cm = self.ctx.character_mgr
        pcid = self._get_player_character_id()
        if not pcid:
            return False

        char = cm.load_character_file(pcid)
        items = char.get("items", [])
        if item_name in items:
            items.remove(item_name)
        char["items"] = items

        cm.save_character_file(pcid, char)  # ← 正しいシグネチャ
        return True

    # --- canon ops ---
    def _add_history(self, canon_name: str, text: str, chapter: int):
        canon_mgr = self.ctx.canon_mgr
        canon_mgr.set_context(self.wid, self.sid)

        # 既存を名前検索 → あれば追記、なければ新規作成
        entry = next((e for e in canon_mgr.entries if e.get("name") == canon_name), None)
        if entry:
            canon_mgr.append_history(entry["id"], text, chapter)
        else:
            canon_mgr.create_fact(canon_name, "fact", text, chapter)

        return True
