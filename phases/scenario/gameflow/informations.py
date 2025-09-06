# phases/scenario/gameflow/informations.py

import json
from core.app_context import AppContext
from core.session_state import SessionState
from infra.path_helper import get_data_path
from infra.logging import get_logger

log = get_logger("Informations")

PRE_PROMPT_SNIPPETS = {
    "scenario": (
        "【今回のシナリオ設定】\n"
        "主題: {theme}\n"
        "雰囲気: {tone}\n"
        "進行スタイル: {style}\n"
        "**これに従った進行を心がけてください。**"
    ),
    "worldview": "この世界は以下のような特徴を持っています：\n{worldview}",
    "character": "PCの情報：\n{character}",
    "nouns": "世界観内の重要な固有名詞：\n{nouns}",
    "canon": "過去に明らかになっている重要な事実：\n{canon}",
    "plan": "この章およびセクションにおける進行計画：\n{plan}"
}


class Informations:
    def __init__(self, state: SessionState, ctx: AppContext):
        self.state = state
        self.ctx = ctx
        self.wid = state.worldview_id
        self.sid = state.session_id

    def build(self, key: str, chapter: int = 1) -> str:
        wid, sid = self.wid, self.sid

        if key == "scenario":
            # scenario.json から meta
            theme = tone = style = "（未設定）"
            scenario_path = get_data_path(f"worlds/{wid}/sessions/{sid}/scenario.json")
            if scenario_path.exists():
                with open(scenario_path, encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("meta", {})
                theme = meta.get("theme", theme)
                tone = meta.get("tone", tone)
                style = meta.get("style", style)
            return PRE_PROMPT_SNIPPETS["scenario"].format(theme=theme, tone=tone, style=style)

        elif key == "worldview":
            worldview = self.ctx.worldview_mgr.get_entry_by_id(wid) or {}
            long_desc = worldview.get("long_description") or worldview.get("description", "")
            tone = worldview.get("tone", "")
            genre = worldview.get("genre", "")
            extra_info = []
            if genre: extra_info.append(f"ジャンル: {genre}")
            if tone: extra_info.append(f"トーン: {tone}")
            full_desc = long_desc.strip()
            if extra_info:
                full_desc += "\n" + " / ".join(extra_info)
            return PRE_PROMPT_SNIPPETS["worldview"].format(worldview=full_desc)

        elif key == "character":
            session = self.ctx.session_mgr.get_entry_by_id(sid) or {}
            pcid = session.get("player_character")
            if not pcid:
                return PRE_PROMPT_SNIPPETS["character"].format(character="（PC未設定）")

            self.ctx.character_mgr.set_worldview_id(wid)
            char = self.ctx.character_mgr.load_character_file(pcid)
            name = char.get("name", "？？？")
            level = char.get("level", "?")
            background = char.get("background", "不明")
            items = char.get("items", [])
            checks = char.get("checks", {})

            text = f"{name}（レベル{level}）\n背景: {background}"
            if items:
                item_lines = []
                for item in items:
                    if isinstance(item, str):
                        item_lines.append(f"- {item}")
                    elif isinstance(item, dict):
                        iname = item.get("name", "")
                        count = item.get("count", 0)
                        desc = item.get("description", "")
                        line = f"- {iname} ×{count}"
                        if desc: line += f"：{desc}"
                        item_lines.append(line)
                text += "\n所持アイテム:\n" + "\n".join(item_lines)
            if checks:
                skill_lines = [f"- {k}：+{v}" for k, v in checks.items()]
                text += "\nスキル:\n" + "\n".join(skill_lines)
            return PRE_PROMPT_SNIPPETS["character"].format(character=text.strip())

        elif key == "nouns":
            self.ctx.nouns_mgr.set_worldview_id(wid)
            nouns = self.ctx.nouns_mgr.entries[:20]
            noun_lines = [
                f"- {n.get('name','')}（{n.get('type','')}）：{n.get('notes','')}"
                for n in nouns
            ]
            return PRE_PROMPT_SNIPPETS["nouns"].format(nouns="\n".join(noun_lines))

        elif key == "canon":
            self.ctx.canon_mgr.set_context(wid, sid)
            canon = self.ctx.canon_mgr.list_entries() if hasattr(self.ctx.canon_mgr,"list_entries") else self.ctx.canon_mgr.entries
            lines = []
            for entry in canon:
                name = entry.get("name", "")
                typ = entry.get("type", "")
                notes = entry.get("notes", "")
                line = f"- {name}（{typ}）"
                if notes:
                    line += f"：{notes}"
                lines.append(line)
                history = entry.get("history", [])
                if history:
                    lines.append("  履歴:")
                    for h in history:
                        ch = h.get("chapter","?")
                        text = h.get("text","")
                        label = "初期設定" if (isinstance(ch,int) and ch==0) else f"第{ch}章"
                        lines.append(f"    - {label}: {text}")
            return PRE_PROMPT_SNIPPETS["canon"].format(canon="\n".join(lines))

        elif key == "plan":
            plan_path = get_data_path(f"worlds/{wid}/sessions/{sid}/chapters/chapter_{chapter:02}/plan.json")
            scenario_path = get_data_path(f"worlds/{wid}/sessions/{sid}/scenario.json")
            scenario_goal = ""
            chapter_goal = ""
            overviews = []
            if scenario_path.exists():
                with open(scenario_path, encoding="utf-8") as f:
                    scenario = json.load(f)
                draft = scenario.get("draft", {})
                scenario_goal = draft.get("goal","").strip()
                overviews = draft.get("chapters",[])
                if 0 <= (chapter-1) < len(overviews):
                    chapter_goal = overviews[chapter-1].get("goal","").strip()
            plan = {}
            if plan_path.exists():
                with open(plan_path, encoding="utf-8") as f:
                    plan = json.load(f)
            title = plan.get("title","")
            flow = plan.get("flow",[])
            section_idx = self.state.section - 1
            flow_lines = []
            for i, sec in enumerate(flow,1):
                goal = sec.get("goal","")
                desc = sec.get("description","").strip()
                combat_flag = "戦闘の可能性あり" if sec.get("has_combat") else "戦闘の可能性なし"
                mark = "▶" if i-1 == section_idx else " "
                flow_lines.append(f"{mark} 第{i}セクション - 目的: {goal}")
                if desc: flow_lines.append(f"    説明: {desc}")
                flow_lines.append(f"    {combat_flag}")
            lines = []
            if scenario_goal: lines.append(f"【シナリオ全体の目的】{scenario_goal}")
            if title: lines.append(f"章タイトル: {title}")
            if chapter_goal: lines.append(f"【この章の目的】{chapter_goal}")
            lines.append("この章の全セクション構成:")
            lines.extend(flow_lines)
            return PRE_PROMPT_SNIPPETS["plan"].format(plan="\n".join(lines))

        return f"（未対応キー: {key}）"

    def build_prompt(self, include=None, chapter: int = 1) -> str:
        include = include or ["scenario","worldview","character","nouns","canon","plan"]
        parts = [self.build(k, chapter=chapter) for k in include]
        return "\n\n".join(p for p in parts if p)

    def get_current_section_goal(self) -> str:
        """
        現在のセクションのゴールを返す。
        goal が未設定なら空文字列を返す。
        """
        wid, sid = self.wid, self.sid
        chapter = self.state.chapter
        section_idx = self.state.section - 1

        plan_path = get_data_path(f"worlds/{wid}/sessions/{sid}/chapters/chapter_{chapter:02}/plan.json")
        if not plan_path.exists():
            return ""

        try:
            with open(plan_path, encoding="utf-8") as f:
                plan = json.load(f)
        except Exception as e:
            log.warning(f"plan.json 読み込み失敗: {e}")
            return ""

        flow = plan.get("flow", [])
        if 0 <= section_idx < len(flow):
            return flow[section_idx].get("goal", "").strip()

        return ""