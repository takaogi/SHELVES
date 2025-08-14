# phases/scenario/command_handler.py
from infra.logging import get_logger

class CommandHandler:
    def __init__(self, ctx, wid, sid):
        self.ctx = ctx
        self.wid = wid
        self.sid = sid
        self.log = get_logger("CommandHandler")

    def execute(self, command: str, args: list[str], chapter: int = 0):
        if command == "add_item" and len(args) >= 1:
            # name, count, description の順（count, description は省略可）
            name = args[0]
            count = int(args[1]) if len(args) >= 2 and args[1].isdigit() else 1
            desc = args[2] if len(args) >= 3 else ""
            return self._add_item(name, count, desc)
        elif command == "remove_item" and len(args) >= 1:
            name = args[0]
            count = int(args[1]) if len(args) >= 2 and args[1].isdigit() else 1
            return self._remove_item(name, count)
        elif command == "add_history" and len(args) == 2:
            return self._add_history(args[0], args[1], chapter)
        elif command == "create_canon" and len(args) >= 3:
            return self._create_canon(args[0], args[1], args[2], chapter)
        else:
            self.log.warning(f"未対応または不正なコマンド: {command} {args}")
        return False
    
    # --- helpers ---
    def _get_player_character_id(self) -> str | None:
        session = self.ctx.session_mgr.get_entry_by_id(self.sid)
        pc = session.get("player_character")
        if isinstance(pc, dict):
            return pc.get("id")
        return pc  # 文字列ID or None

    # --- inventory ops ---
    def _add_item(self, item_name: str, count: int = 1, description: str = ""):
        cm = self.ctx.character_mgr
        pcid = self._get_player_character_id()
        if not pcid:
            self.log.warning(f"アイテム追加失敗（PC未設定）: {item_name}")
            return False

        char = cm.load_character_file(pcid)
        items = char.setdefault("items", [])

        # 既存アイテム検索
        existing = next((i for i in items if isinstance(i, dict) and i.get("name") == item_name), None)
        if existing:
            existing["count"] += count
            if description:
                existing["description"] = description
            self.log.info(f"アイテム更新: {item_name} ×{existing['count']} → PC={pcid}")
        else:
            items.append({"name": item_name, "count": count, "description": description})
            self.log.info(f"アイテム追加: {item_name} ×{count} → PC={pcid}")

        char["items"] = items
        cm.save_character_file(pcid, char)
        return True

    def _remove_item(self, item_name: str, count: int = 1):
        cm = self.ctx.character_mgr
        pcid = self._get_player_character_id()
        if not pcid:
            self.log.warning(f"アイテム削除失敗（PC未設定）: {item_name}")
            return False

        char = cm.load_character_file(pcid)
        items = char.get("items", [])
        removed = False

        for i in list(items):
            if isinstance(i, dict) and i.get("name") == item_name:
                if i["count"] > count:
                    i["count"] -= count
                else:
                    items.remove(i)
                removed = True
                break
            elif isinstance(i, str) and i == item_name:
                items.remove(i)
                removed = True
                break

        if removed:
            self.log.info(f"アイテム削除: {item_name} ×{count} → PC={pcid}")
        else:
            self.log.info(f"アイテム削除スキップ（未所持）: {item_name} → PC={pcid}")

        char["items"] = items
        cm.save_character_file(pcid, char)
        return removed

    # --- canon ops ---
    def _add_history(self, canon_name: str, text: str, chapter: int):
        canon_mgr = self.ctx.canon_mgr
        canon_mgr.set_context(self.wid, self.sid)

        entry = next((e for e in canon_mgr.entries if e.get("name") == canon_name), None)
        if entry:
            try:
                canon_mgr.append_history(entry["id"], text, chapter)
                self.log.info(f"カノン履歴追加: {canon_name}（ch={chapter}）")
            except Exception as e:
                self.log.error(f"カノン履歴追加失敗: {canon_name}（ch={chapter}）: {e}")
                return False
        else:
            # 履歴追加対象が存在しない → type不明で新規作成としてフォールバック
            try:
                canon_mgr.create_fact(canon_name, "unknown", text, chapter)
                self.log.warning(f"カノン履歴追加失敗（未登録）→ type=unknown で新規作成: {canon_name}（ch={chapter}）")
            except Exception as e:
                self.log.error(f"カノン新規作成（フォールバック）失敗: {canon_name}（type=unknown, ch={chapter}）: {e}")
                return False

        return True



    def _create_canon(self, name: str, typ: str, notes: str, chapter: int):
        canon_mgr = self.ctx.canon_mgr
        canon_mgr.set_context(self.wid, self.sid)
        try:
            canon_mgr.create_fact(name, typ, notes, chapter)
            self.log.info(f"カノン作成: {name}（type={typ}, ch={chapter}）")
            return True
        except Exception as e:
            self.log.warning(f"カノン作成失敗: {name}（type={typ}）: {e}")
            return False
