# phases/scenario/conversation_log.py

import os
import json
from typing import Literal
from infra.path_helper import get_data_path

Role = Literal["system", "user", "assistant", "summary"]


class ConversationLog:
    def __init__(self, wid: str, sid: str, ctx=None):
        self.wid = wid
        self.sid = sid
        self.ctx = ctx
        self.engine = ctx.engine if ctx else None

        self.messages: list[dict] = []
        self.slim_messages: list[dict] = []

        self.path = get_data_path(f"worlds/{wid}/sessions/{sid}/conversation.json")
        self.slim_path = get_data_path(f"worlds/{wid}/sessions/{sid}/conversation_slim.json")

        self._load()
        self._load_slim()

    def append(self, role: Role, content: str):
        entry = {"role": role, "content": content.strip()}
        self.messages.append(entry)
        self._save()

        self.slim_messages.append(entry)
        self._summarize_if_needed()
        self._save_slim()

    def get(self) -> list[dict]:
        return self.messages.copy()

    def get_slim(self) -> list[dict]:
        """OpenAI互換のメッセージリストを返す（summary → system）"""
        result = []
        for m in self.slim_messages:
            role = m["role"]
            content = m["content"]
            if role == "summary":
                role = "system"
                content = f"[要約] {content}"
            result.append({"role": role, "content": content})
        return result

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self.messages = json.load(f)
        else:
            self.messages = []

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)

    def _load_slim(self):
        if os.path.exists(self.slim_path):
            with open(self.slim_path, encoding="utf-8") as f:
                self.slim_messages = json.load(f)
        else:
            self.slim_messages = []

    def _save_slim(self):
        os.makedirs(os.path.dirname(self.slim_path), exist_ok=True)
        with open(self.slim_path, "w", encoding="utf-8") as f:
            json.dump(self.slim_messages, f, ensure_ascii=False, indent=2)

    def _summarize_if_needed(self, block_size=10, summarize_n=5):
        if not self.engine or not self.ctx:
            return

        # --- 背景情報を取得 ---
        wid = self.wid
        sid = self.sid
        worldview = self.ctx.worldview_mgr.get_entry_by_id(wid) or {}
        session = self.ctx.session_mgr.get_entry_by_id(sid) or {}

        pcid = session.get("player_character", {}).get("id") if isinstance(session.get("player_character"), dict) else None
        pc = self.ctx.character_mgr.load_character_file(pcid) if pcid else {}

        self.ctx.nouns_mgr.set_worldview_id(wid)
        nouns = self.ctx.nouns_mgr.entries

        self.ctx.canon_mgr.set_context(wid, sid)
        canon = self.ctx.canon_mgr.list_entries()

        # --- 現在の slim_messages を再構成（summaryは保持） ---
        existing_summaries = [m for m in self.slim_messages if m["role"] == "summary"]
        non_summary_msgs = [m for m in self.slim_messages if m["role"] != "summary"]

        # --- user → assistant のペアをループとして抽出 ---
        loops = []
        buf = []
        for m in non_summary_msgs:
            if m["role"] == "user":
                buf = [m]
            elif m["role"] == "assistant" and buf:
                buf.append(m)
                loops.append(buf)
                buf = []

        if len(loops) <= block_size:
            return  # 十分にたまっていない場合はスキップ

        # --- 要約対象の先頭Nループと、残りのループを分割 ---
        target = loops[:summarize_n]
        remaining = loops[summarize_n:]

        flat = [msg for loop in target for msg in loop]
        text = "\n".join(f"{m['role']}: {m['content']}" for m in flat)

        # --- AIによる要約プロンプト生成 ---
        prompt = [
            {"role": "system", "content": (
                "あなたはTRPGセッションログの要約専門AIです。\n"
                "以下の背景情報(世界観、PC、固有名詞、カノン)を考慮し、会話ログの重要な出来事だけを簡潔に要約してください。\n"
                "確認応答・雑談・プレイヤーのメタ発言は除外し、進行や展開に関わる事実のみを抽出してください。"
            )},
            {"role": "system", "content": f"■ 世界観:\n{worldview.get('long_description') or worldview.get('description', '')}"},
            {"role": "system", "content": f"■ PC:\n{json.dumps(pc, ensure_ascii=False, indent=2)}"},
            {"role": "system", "content": f"■ 固有名詞:\n{json.dumps(nouns, ensure_ascii=False, indent=2)}"},
            {"role": "system", "content": f"■ カノン:\n{json.dumps(canon, ensure_ascii=False, indent=2)}"},
            {"role": "user", "content": text}
        ]

        # --- AIで要約し、新しい summary エントリを生成 ---
        summary = self.engine.chat(prompt, caller_name="LogSummary", max_tokens=1500).strip()
        summary_entry = {"role": "summary", "content": summary}

        # --- 要約 + 残りループを新しい slim_messages として保存 ---
        self.slim_messages = existing_summaries + [summary_entry] + [m for loop in remaining for m in loop]

    def build_context_prompt(self) -> list[dict]:
        """世界観・キャラ・カノン・固有名詞を含む前提情報"""
        wid = self.wid
        sid = self.sid

        worldview = self.ctx.worldview_mgr.get_entry_by_id(wid) or {}
        session = self.ctx.session_mgr.get_entry_by_id(sid) or {}

        pcid = session.get("player_character", {}).get("id") if isinstance(session.get("player_character"), dict) else None
        pc = self.ctx.character_mgr.load_character_file(pcid) if pcid else {}

        self.ctx.nouns_mgr.set_worldview_id(wid)
        nouns = self.ctx.nouns_mgr.entries

        self.ctx.canon_mgr.set_context(wid, sid)
        canon = self.ctx.canon_mgr.list_entries()

        return [
            {"role": "system", "content": f"■ 世界観:\n{worldview.get('long_description') or worldview.get('description', '')}"},
            {"role": "system", "content": f"■ PC:\n{json.dumps(pc, ensure_ascii=False, indent=2)}"},
            {"role": "system", "content": f"■ 固有名詞:\n{json.dumps(nouns, ensure_ascii=False, indent=2)}"},
            {"role": "system", "content": f"■ カノン:\n{json.dumps(canon, ensure_ascii=False, indent=2)}"},
        ]

    def summarize_now(self):
        if not self.engine or not self.ctx:
            return

        # --- 背景情報を準備 ---
        prompt = self.build_context_prompt()
        prompt.insert(0, {
            "role": "system", "content": (
                "あなたはTRPGセッションログの要約専門AIです。\n"
                "以下の背景情報(世界観、PC、固有名詞、カノン)を考慮し、会話ログの重要な出来事だけを簡潔に要約してください。\n"
                "確認応答・雑談・プレイヤーのメタ発言は除外し、進行や展開に関わる事実のみを抽出してください。"
            )
        })

        prompt += self.get_slim()
        prompt.append({"role": "user", "content": "以上を要約してください。"})

        summary = self.engine.chat(
            messages=prompt,
            caller_name="ForcedSummary",
            model_level="high",
            max_tokens=1800
        ).strip()

        self.slim_messages = [{"role": "summary", "content": summary}]
        self._save_slim()

    def generate_story_summary(self) -> str:
        if not self.engine or not self.ctx:
            return ""

        prompt = self.build_context_prompt()
        prompt.insert(0, {
            "role": "system", "content": (
                "あなたはソロTRPGの物語を美しく要約する語り手です。\n"
                "以下の会話ログは、PCが経験した物語の記録です。\n"
                "内容をもとに、感情の起伏や展開の魅力を伝える物語的要約を作成してください。\n"
                "文体は三人称・地の文・常体で、500字程度にまとめてください。"
            )
        })

        # 会話ログ本体を追加
        prompt += self.get_slim()
        prompt.append({"role": "user", "content": "ここまでの物語を、三人称の語りとして要約してください。"}
)
        return self.engine.chat(
            messages=prompt,
            caller_name="StorySummary",
            model_level="high",
            max_tokens=2000
        ).strip()

