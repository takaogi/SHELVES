from __future__ import annotations
import json
from typing import Dict, Any

class Narrator:
    """
    Progression(JSON dict) と player_input を受け取り、
    プレイヤー提示用の「描写テキスト（日本語1段落）」を生成する。
    - I/Oなし（ディスクは読まない）
    - Director互換の構造（__init__で依存注入、narrator()で実行）
    """

    def __init__(self, ctx, state, flags, convlog, infos):
        self.ctx = ctx
        self.state = state
        self.flags = flags
        self.convlog = convlog
        self.infos = infos
        
    def _system_prompt_common(self, cue: str | None = None) -> str:
        base = """
あなたはソロTRPGの進行役（Narrator）です。以下の Progression JSON を厳密に読み取り、
プレイヤー提示用の描写テキストを **日本語で1段落のみ** 生成してください（目安100〜200字）。
シナリオの進行計画に基づき、シナリオを進行してください。

【スタイル（厳守）】
- 三人称・地の文・常体。メタ語（達成値/判定/クリティカル等）や記号箇条書きは禁止。
- わかりやすさ最優先（web小説程度の非常に簡単な語彙で）。不要な新事実は作らない。

【必須反映】
- flow.loc / env /obj は、すでに言及されているならいちいち描写する必要はない。
- flow.nps の行動を自然に織り込む。
- flow.pts の各項目は本文で **必ず言及**。
- cmd の確定事実は、叙述として自然に（箇条書きは禁止）。

描写は三人称・地の文・常体で、web小説程度の簡単な語彙を使ってください。
"""

    # cue に応じて追加ルールを付ける
        if cue == "action":
            base += """
【重要ルール（cue=action）】
- この返答の最後は必ず「〜のため、行為判定を行います。」で締めてください。
- 技能名や難易度は提示しないでください。
"""
        elif cue == "combat":
            base += """
【重要ルール（cue=combat）】
- この返答の最後は必ず「〜のため、戦闘判定を行います。戦法を提示してください。」で締めてください。
- 戦闘の舞台・敵・状況を描写し、プレイヤーが戦法を宣言できるよう導いてください。
"""
        elif cue == "end":
            base += """
【重要ルール（cue=end）】
- この返答では、話をある程度収束させつつ、次の展開やセクションへの自然なつながりを描写してください。
"""
        else:  # cue==None
            base += """
【重要ルール（cueがnone）】
- この返答の最後には、objと矛盾せず、かつシナリオを進行できるような、プレイヤーキャラクターが取りうる行動案を提示してください。
- 「行動案：1) ～ 2) ～」の形式で2～3個、改行で区切ってください。
"""

        return base


    def _system_prompt_for_label(self, label: str) -> str:
        
        if label == "post_check_description":
            return """
【補足（post_check_description）】
- 行為判定の帰結を非メタで反映。
"""
        if label == "post_combat_description":
            return """
【補足（post_combat_description）】
- 戦闘直後の残響（傷・匂い・熱気）、NPC反応、戦利品/痕跡、継続戦の余地や収束の気配を自然に描く。
"""
        return ""

    def handle(
        self,
        *,
        label: str,
        player_input: str,
        progression: Dict[str, Any],
    ) -> str:
        """
        描写テキストを1段落で返す。
        label: "action" | "post_check_description" | "post_combat_description" | "none" 等
        """
        # 参照情報（Directorと同様に Informations から束ねる）
        prompt_infos = self.infos.build_prompt(
            include=["scenario", "worldview", "character", "nouns", "canon", "plan"],
            chapter=self.state.chapter
        )
        history = self.convlog.get_slim()

        prog_blob = json.dumps(progression, ensure_ascii=False, indent=2)

        messages = [
            {"role": "system", "content": self._system_prompt_common(progression.get("cue")) + self._system_prompt_for_label(label)},
            {"role": "system", "content": prompt_infos},
            *history,
            {"role": "user", "content":
                "【Progression JSON（入力）】\n"
                f"{prog_blob}\n\n"
                "【プレイヤー直近発話（参照用）】\n"
                f"{player_input}"
            },
        ]

        text = self.ctx.engine.chat(
            messages=messages,
            caller_name=f"Narrator.{label}",
            model_level="high",
            max_tokens=5000,
            schema=None,  # 文章出力
        )
        return text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
