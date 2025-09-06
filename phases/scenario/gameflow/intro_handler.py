# phases/scenario/handlers/intro_handler.py

import json
from infra.path_helper import get_data_path
from phases.scenario.gameflow.informations import Informations  # 追加

class IntroHandler:
    def __init__(self, ctx, state, convlog, infos: Informations):  # 変更
        self.ctx = ctx
        self.state = state
        self.convlog = convlog
        self.infos = infos  # 追加

    def handle(self, label: str) -> str:
        kind = "chapter" if label == "chapter_intro" else "section"
        return self._handle_intro(kind)

    def _handle_intro(self, kind: str) -> str:
        wid = self.state.worldview_id
        sid = self.state.session_id
        chapter = self.state.chapter
        section_idx = self.state.section - 1

        plan_path = get_data_path(f"worlds/{wid}/sessions/{sid}/chapters/chapter_{chapter:02}/plan.json")
        scenario_path = get_data_path(f"worlds/{wid}/sessions/{sid}/scenario.json")

        intro = ""
        overview = ""

        if plan_path.exists():
            with open(plan_path, encoding="utf-8") as f:
                plan = json.load(f)
            flow = plan.get("flow", [])
            if 0 <= section_idx < len(flow):
                intro = flow[section_idx].get("intro", "")

        if scenario_path.exists():
            with open(scenario_path, encoding="utf-8") as f:
                scenario = json.load(f)
            if 0 < chapter <= len(scenario.get("chapters", [])):
                overview = scenario["chapters"][chapter - 1].get("overview", "")

        # ── ここまで従来どおり ──

        if kind == "chapter":
            if chapter == 1:
                instruction = (
                    "あなたはTRPGのゲームマスターです。\n"
                    "これは物語の第一章の導入です。舞台や背景、PCの関わりのきっかけを、"
                    "臨場感重視・わかりやすさ優先でラノベ風に描写してください（三人称・常体・約500字）。\n"
                    "最後に「行動案：1) ～ 2) ～」の形式で2～3個、直後の行動案を提示してください（番号ごとに改行）。"
                )
            else:
                instruction = (
                    "あなたはTRPGのゲームマスターです。\n"
                    "以下の情報と会話履歴を踏まえ、新たに始まる章の導入描写を約300字で提示してください。\n"
                    "現在位置と状況を具体的に描き、直後の行動案を「行動案：1) ～ 2) ～」の形式で2～3個提示（番号ごとに改行）。\n"
                    "わかりやすさ優先・三人称・常体・ラノベ風で。"
                )
        else:
            instruction = (
                "あなたはTRPGのゲームマスターです。\n"
                "以下の情報と会話履歴を踏まえ、セクションの導入描写を約300字で提示してください。\n"
                "直前から自然につなぎ、現在位置と状況を具体的に示し、直後の行動案を2～3個（前述の形式）。\n"
                "わかりやすさ優先・三人称・常体・ラノベ風で。"
            )

        if overview:
            instruction += f"\n\nこの章の概要: {overview}"
        if intro:
            instruction += f"\nセクションの導入情報（必ず参考にしてください）: {intro}"

        # ✅ snippetsを使わずInformationsで一括生成（scenario/worldview/character/nouns/canon/plan）
        instruction += "\n\n" + self.infos.build_prompt(
            include=["scenario","worldview","character","nouns","canon","plan"],
            chapter=chapter
        )

        messages = [{"role": "system", "content": instruction}]
        messages += self.convlog.get_slim()
        model_level = "high" if kind == "chapter" else "high"

        response = self.ctx.engine.chat(
            messages=messages,
            caller_name=f"IntroHandler:{kind}_intro",
            model_level=model_level,
            max_tokens=5000
        )
        
        return response
