from __future__ import annotations
from typing import Dict, Any, List

# ===== 文字列クォート =====
def _q(s: str | None) -> str:
    if s is None:
        s = ""
    # \ と " をエスケープ（古式フォーマットの安全側）
    s = str(s).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'

# ===== cmd 1件 → 角括弧行 =====
def _fmt_cmd_one(cmd: Dict[str, Any]) -> str:
    op = (cmd.get("op") or "").strip()

    if op == "add_item":
        # 仕様：「個数や説明も含める」
        name = _q(cmd.get("name"))
        count = int(cmd.get("count", 1))
        note = _q(cmd.get("note") or "")
        return f"[command:add_item({name}, {count}, {note})]"

    if op == "remove_item":
        # 仕様：「個数は省略可」。1なら省略、それ以外は明示。
        name = _q(cmd.get("name"))
        count = int(cmd.get("count", 1))
        if count == 1:
            return f"[command:remove_item({name})]"
        else:
            return f"[command:remove_item({name}, {count})]"

    if op == "add_history":
        # 既存カノンへの追加
        name = _q(cmd.get("name"))
        note = _q(cmd.get("note") or "")
        return f"[command:add_history({name}, {note})]"

    if op == "create_canon":
        # 新規カノン作成（引数順：name, type, note）
        name = _q(cmd.get("name"))
        typ  = _q(cmd.get("type"))
        note = _q(cmd.get("note") or "")
        return f"[command:create_canon({name}, {typ}, {note})]"

    # 未知の op は安全側で key順固定ダンプ（念のため）
    keys = ["op", "name", "type", "count", "note"]
    args: List[str] = []
    for k in keys:
        if k in cmd:
            v = cmd[k]
            if isinstance(v, int):
                args.append(str(v))
            else:
                args.append(_q(str(v)))
    return f"[command:unknown({', '.join(args)})]"

# ===== cue → 角括弧行 =====
def _fmt_cue(cue: str | None) -> str:
    m = (cue or "").strip().lower()
    if m == "action":
        return "[action_check]"
    if m == "combat":
        return "[combat_start]"
    if m == "end":
        return "[end_section]"
    # "none" や未知は出さない（無出力）
    return ""

# ===== Progression → 角括弧列 =====
def to_bracket_commands(progression: Dict[str, Any]) -> str:
    """
    指定：Progression(JSON dict) を旧式の角括弧命令列へ。
      - cmd…各行に [command:...] を出力
      - cue…末尾に [action_check] / [combat_start] / [end_session]
    """
    out: List[str] = []
    for c in progression.get("cmd", []) or []:
        if isinstance(c, dict) and c.get("op"):
            out.append(_fmt_cmd_one(c))
    cue_line = _fmt_cue(progression.get("cue"))
    if cue_line:
        out.append(cue_line)
    return "\n".join(out)

# ===== 本文末尾に追記 =====
def append_brackets_to_text(text: str, progression: Dict[str, Any]) -> str:
    """
    描写テキスト末尾に空行 + 角括弧命令列を追記。
    命令列が空なら本文のみ返す。
    """
    tail = to_bracket_commands(progression)
    if not tail:
        return text
    sep = "\n" if text.endswith("\n") else "\n\n"
    return f"{text}{sep}{tail}\n"
