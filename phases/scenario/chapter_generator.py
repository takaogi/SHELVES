# phases/scenario/chapter_generator.py
import json
from infra.path_helper import get_data_path

CHAPTER_PLAN_SCHEMA = {
    "type": "json_schema",
    "name": "ChapterPlan",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "flow": {
                "type": "array",
                "minItems": 1,
                "maxItems":5,
                "items": {
                    "type": "object",
                    "properties": {
                        "section": {"type": "integer", "minimum": 1},
                        "scene": {"type": "string", "enum": ["exploration"]}, 
                        "intro": {"type": "string"},
                        "goal": {"type": "string","maxLength":50},
                        "description": {"type": "string","minLength": 100},
                        "has_combat": {"type": "boolean"}
                    },
                    "required": ["section", "scene", "intro", "goal", "description", "has_combat"],
                    "additionalProperties": False
                }
            },
            "canon": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "note": {"type": "string", "minLength": 100}
                    },
                    "required": ["name", "type", "note"],
                    "additionalProperties": False
                }
            }
        },
        # strict=True なので properties の全キーを required に
        "required": ["title", "flow", "canon"],
        "additionalProperties": False
    }
}


class ChapterGenerator:
    def __init__(self, ctx, wid: str, sid: str, chapter: int):
        self.ctx = ctx
        self.wid = wid
        self.sid = sid
        self.chapter = chapter

        # worldview, session は indexから取得（辞書形式）
        self.worldview = ctx.worldview_mgr.get_entry_by_id(wid)
        self.session = ctx.session_mgr.get_entry_by_id(sid)

        ctx.character_mgr.set_worldview_id(wid)
        
        # nouns, canon はマネージャーに読み込ませる
        ctx.nouns_mgr.set_worldview_id(wid)
        self.nouns = ctx.nouns_mgr.list_entries()

        ctx.canon_mgr.set_context(wid, sid)
        self.canon = ctx.canon_mgr.list_entries()


        # シナリオ全体の読み込み
        scenario_path = get_data_path(f"worlds/{wid}/sessions/{sid}/scenario.json")
        self.scenario_data = {}
        if scenario_path.exists():
            with open(scenario_path, encoding="utf-8") as f:
                self.scenario_data = json.load(f)
        # 既存: scenario_data の読み込み直後に追記
        draft = self.scenario_data.get("draft", {})
        self._chapters_all = draft.get("chapters", []) or []
        self.total_chapters = len(self._chapters_all)
        self.is_final_chapter = (self.total_chapters > 0 and self.chapter == self.total_chapters)


    def generate(self) -> dict:
        """
        次に来るべき章のプランを、構造化JSON（CHAPTER_PLAN_SCHEMA）で生成する。
        失敗時は最低限の骨組みでフォールバック。
        """
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._build_prompt()},
        ]

        try:
            plan = self.ctx.engine.chat(
                messages=messages,
                max_tokens=30000,              # chat() 側で max_output_tokens に変換される想定
                caller_name="ChapterGenerator",
                model_level="very_high", 
                schema=CHAPTER_PLAN_SCHEMA,    # ★ 構造化出力
            )

            if not isinstance(plan, dict):
                # スキーマ外出力などの保険
                plan = {"title": "", "flow": [], "canon": [], "error": "invalid schema output"}

        except Exception as e:
            # APIやスキーマバリデーション失敗時の保険
            plan = {"title": "", "flow": [], "canon": [], "error": f"generation failed: {e}"}

        # 保存（title/flow をファイル、canon は canon_mgr 側へ）
        self._save(plan)
        return plan


    def _system_prompt(self) -> str:
        return (
            "あなたはTRPGのシナリオ構成を専門とするAIです。\n"
            "与えられた情報（セッション全体構想、世界観、キャラクター、カノン）に基づき、"
            f"『第{self.chapter}章』の構成のみを作成してください。\n"
            "章番号を勝手に変えたり、他章の内容を混在させてはいけません。\n\n"
            + self._output_format_sample()
        )



    def _build_prompt(self) -> str:
        lines = []
        draft = self.scenario_data.get("draft", {})
        chapters = draft.get("chapters", [])

        lines.append(f"# 指定: 第{self.chapter}章 の展開計画を作成してください。")
        if self.total_chapters:
            lines.append(f"- 全{self.total_chapters}章構成。これは第{self.chapter}章です。")
        if self.is_final_chapter:
            lines.append(
                "※この章は【最終章】です。以下を満たしてください：\n"
                "・主要な伏線の回収とクライマックスセクション\n"
                "・PCの選択が結末に反映される明確な帰結\n"
                "・必要なら短い余韻（簡潔なエピローグ用のセクションを用意）\n"
                "・重要な未解決を残さない（続編の“余地”は軽い示唆に留める）"
            )

        lines.append(
            f"※絶対条件：出力は『第{self.chapter}章』のみ。他章の展開は書かないこと。"
        )

        lines.append(f"\n## セッションタイトル: {draft.get('title', self.session.get('title', '(タイトル不明)'))}")

        # 全体構想（参照用）
        lines.append(f"\n## セッション全体構想（参照用・生成は第{self.chapter}章のみ）:")
        lines.append(f"- 目的: {draft.get('goal', '')}")
        lines.append(f"- 概要: {draft.get('summary', '')}")

        # 章一覧（参照用）
        if chapters:
            lines.append("\n## チャプター構成（参照用）:")
            for i, ch in enumerate(chapters, 1):
                title = ch.get("title", f"Chapter {i}")
                overview = ch.get("overview", "")
                lines.append(f"- 第{i}章「{title}」: {overview}")

        # 直前章のhistory（既存処理のまま）
        lines += self._load_previous_chapter_history()

        # 世界観説明
        lines.append("\n## 世界観の説明:")
        lines.append(self.worldview.get("long_description") or self.worldview.get("description", ""))

        # PC
        lines.append("\n## PC:")
        pcid = self.session.get("player_character")

        pc = None
        if pcid:
            try:
                pc = self.ctx.character_mgr.load_character_file(pcid)
            except FileNotFoundError:
                self.ctx.character_mgr.log.warning(f"キャラクターが見つかりません: {pcid}")

        if pc:
            name = pc.get("name", "名無し")
            level = pc.get("level", "")
            background = pc.get("background", "（背景情報なし）")

            lines.append(f"- 名前: {name}")
            lines.append(f"- レベル: {level}")
            lines.append(f"- 背景: {background}")
            lines.append(
                "レベルは戦闘能力の指標で、以下のような目安です：\n"
                "0：一般人（非戦闘員）\n"
                "1〜3：初心者〜見習い戦闘員\n"
                "4〜6：熟練者クラス（一人前）\n"
                "7〜10：超人的な存在\n"
                "11〜13：伝説・神話級の英雄\n"
                "14〜15：神や精霊に匹敵する存在\n\n"
            )
        # 固有名詞
        lines.append("\n## 世界観の固有名詞一覧:")
        lines.append(json.dumps(self.nouns, ensure_ascii=False, indent=2))


        # これまでのカノン
        lines.append("\n## これまでに確定したカノン:")
        lines.append(json.dumps(self.canon, ensure_ascii=False, indent=2))


        return "\n".join(lines)
    
    def _load_previous_chapter_history(self) -> list[str]:
        history_path = get_data_path(
            f"worlds/{self.wid}/sessions/{self.sid}/chapters/chapter_{self.chapter - 1:02}/history.json"
        )
        if not history_path.exists():
            return [
                "\n## 直前の章の記録:",
                "- このセッションはまだ開始されていません。",
                "- 一番最初の章を、全体構想と整合するように構築してください。"
            ]


        with open(history_path, encoding="utf-8") as f:
            data = json.load(f)

        lines = ["\n## 直前の章の記録:"]
        if summary := data.get("summary"):
            lines.append(f"- 概要: {summary}")
        if events := data.get("important_events"):
            lines.append("- 主な出来事:")
            for event in events:
                lines.append(f"  - {event}")
        if canon := data.get("canon_updates"):
            lines.append("- 確定したカノン:")
            for c in canon:
                lines.append(f"  - {c.get('name', '')}: {c.get('note', '')}")

        return lines

    def _output_format_sample(self) -> str:
        return (
            "【flow補足】\n"
            "- section: セクションの順番をあらわす番号（1〜5つ程度）。必ず連番で。章の内容にあわせて、一つ一つのセクションが長くも短くもなりすぎないように分割。\n"
            "- scene: 以下の分類から英語で指定してください。\n"
            "   ・exploration：AI主導の通常探索。一本道の街道、町、拠点など。基本的にほぼ全てこれ。 これ以外未実装だから全部これ。\n"
            #"   ・dungeon：大規模な構造物や迷宮。AIの管理が難しく、手動操作や構造探索が中心。セッションごとに1つ2つ程度。無い章のほうが多い。\n"
            #"   ・transition：章間・移動・補給・休息など。物語の繋ぎやテンポ調整として機能。チャプターごとに1つあるかないか。\n"
            "- intro:この場面に入ったとき、プレイヤーが最初に目にする描写。視覚・音・匂いなど感覚描写も含めて自然に。50字程度で。\n"
            "- goal: プレイヤーがこの場面で目指すべき行動や成果。基本的に、指定地点への到達、あるいはそれ自体が目的となるものに限る（例：地下第二層へ侵入する、銀の鍵を入手する等。　準備を完了する、何かを把握する等は基準が分かり辛いので避ける。あまり具体的すぎるのも、縛られてしまうので避ける。）。\n"
            "- description: NPCの動き、罠やイベント、選択肢、背景など状況の詳細および、場面の背景、展開、環境変化など詳細な補足。推奨される進行ルートや選択肢も含める。200字程度で。\n"
            "- has_combat: 戦闘が発生する可能性の有無（true/false）\n"
            "\n"
            "【canon補足】\n"
            "- この章で新たに明らかになった事実・要素に限定 **絶対に既にあるカノンや世界観の固有名詞を含めてはいけない**\n"
            "- type: 以下から選んでください：\n"
            "    ・場所（町、遺跡、ダンジョンなどの具体的な地理的地点）\n"
            "    ・NPC（登場人物。名前があるキャラクター）\n"
            "    ・知識（歴史、文化、宗教、信仰、技術、伝承など背景設定）\n"
            "    ・アイテム（武器、道具、遺物など重要な物品）\n"
            "    ・ギミック（仕掛け、封印、装置、トラップなどのプレイヤーの障害　noteにはその解除方法も必ず追記する）\n"           
            "    ・その他（上記に当てはまらないが記録すべきもの）\n"
            "- note: 要素の詳細説明。100文字以上が望ましい。\n"
            "\n"
            "このシナリオの流れを生成するにあたって、まずチャプター構成（全体）の流れから大きく外れないことを念頭に置いてください。\n"
            "次に、PCの意思を勝手に決定しないでください。PCの自由意思の担保はTRPGにおいて前提です。その選択を誘導はしても勝手に定めてはいけません。不要な時間制限等も決して設けないでください。\n"
            "また、あくまでソロ用のTRPGシナリオであり、進行もAIが行うため、過度なNPCの出演を控え、パーティー結成等は特にやめてください。制御しきれません。\n"
            "最後に、これが最も重要ですが、地に足ついた、リアリティのあるシナリオを作ってください。目標ははっきりと具体的な動作に基づき、展開もくっきりさせてください。"
            )

    def _extract_json(self, response_text: str) -> dict:
        try:
            start = response_text.index("{")
            end = response_text.rindex("}") + 1
            return json.loads(response_text[start:end])
        except Exception:
            return {
                "error": "JSON解析に失敗しました",
                "raw_output": response_text
            }

    def _save(self, plan_data: dict):
        # title と flow のみを plan.json に保存
        slim_plan = {
            "title": plan_data.get("title", ""),
            "flow": plan_data.get("flow", [])
        }
        plan_path = get_data_path(f"worlds/{self.wid}/sessions/{self.sid}/chapters/chapter_{self.chapter:02}/plan.json")
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(slim_plan, f, ensure_ascii=False, indent=2)

        # canon は別途 canon_mgr に登録
        new_canons = plan_data.get("canon", [])
        for c in new_canons:
            name = c.get("name", "")
            type_ = c.get("type", "その他")
            note = c.get("note", "")
            if name and note:
                self.ctx.canon_mgr.create_fact(name=name, type=type_, notes=note, chapter=self.chapter)
