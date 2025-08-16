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
                "minItems": 2,
                "maxItems":5,
                "items": {
                    "type": "object",
                    "properties": {
                        "section": {"type": "integer", "minimum": 1},
                        "scene": {"type": "string", "enum": ["exploration"]}, 
                        "goal": {"type": "string","maxLength":50},
                        "description": {"type": "string","minLength": 100},
                        "has_combat": {"type": "boolean"}
                    },
                    "required": ["section", "scene", "goal", "description", "has_combat"],
                    "additionalProperties": False
                }
            },
            "canon": {
                "type": "array",
                "maxItems":3,
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
        self.nouns = ctx.nouns_mgr.list_entries()[:30]


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

        # --- 最終章なら固定エンディングセクションを追加 ---
        if getattr(self, "is_final_chapter", False):
            flow = plan.get("flow", [])
            if not any(sec.get("goal") == "エピローグを終え、プレイヤーにセッション終了の確認をする" for sec in flow):
                flow.append({
                    "section": len(flow) + 1,
                    "scene": "exploration",
                    "goal": "エピローグを終え、プレイヤーにセッション終了の確認をしてから'[end_section]'を行う",
                    "description": "シナリオの最後として、物語の結末とその後を簡潔に描写する。PCや重要NPCの運命、舞台の変化などを含める。",
                    "has_combat": False
                })
                plan["flow"] = flow

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
                "・最後のセクションのgoalは、シナリオ自体のgoalと一致させる\n"
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
                chapter_goal = ch.get("goal", "")
                overview = ch.get("overview", "")
                lines.append(f"- 第{i}章「{title}」-目的:{chapter_goal} -詳細（参考）: {overview}")

        # 直前章のhistory（既存処理のまま）
        lines += self._load_previous_chapter_history()

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

            # 所持品（新仕様: オブジェクト配列）
            items = pc.get("items", [])
            if items:
                lines.append("- 所持品:")
                for item in items:
                    item_name = item.get("name", "")
                    item_count = item.get("count", 0)
                    item_desc = item.get("description", "")
                    lines.append(f"  - {item_name} ×{item_count}：{item_desc}")

            lines.append(
                "レベルは戦闘能力の指標で、以下のような目安です：\n"
                "0：一般人（非戦闘員）\n"
                "1〜3：初心者〜見習い戦闘員\n"
                "4〜6：熟練者クラス（一人前）\n"
                "7〜10：超人的な存在\n"
                "11〜13：伝説・神話級の英雄\n"
                "14〜15：神や精霊に匹敵する存在\n\n"
            )

        # 世界観説明
        lines.append("\n## 世界観の説明:")
        lines.append(self.worldview.get("long_description") or self.worldview.get("description", ""))

        # 固有名詞
        lines.append("\n## 世界観の固有名詞一覧:")
        for noun in self.nouns:
            name = noun.get("name", "")
            type_ = noun.get("type", "")
            notes = noun.get("notes", "")
            lines.append(f"- {name}（{type_}）：{notes}")

        # これまでのカノン
        lines.append("\n## これまでに確定したカノン:")
        for canon_entry in self.canon:
            name = canon_entry.get("name", "")
            type_ = canon_entry.get("type", "")
            notes = canon_entry.get("notes", "")
            lines.append(f"- {name}（{type_}）：{notes}")


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
        return """
【goal（セクションの目的） - 最重要ルール】
※この項目はシナリオ進行の骨格となるため、厳密に守ること
- 各セクションのgoalは、そのセクションを終えると次に進める「結果」のみを記述する。
- 手段や工程は書かない。
- 中間の1〜2セクションに予想外の事態や障害を入れ、その解決を条件とする。
- 予想外の事態は、戦闘・交渉・隠密など複数の解決手段を許容する表現にする（例：「支配から解放する」「封印を解く」）。
- 最終セクションのgoalは章の目的とほぼ一致させる。
- セクション数は2〜5を目安にし、章の規模や展開に応じて調整する。

▼ goal設定の良い例（結果＋予想外の事態を含む）】
目的：井戸の底から秘鍵を入手する（3セクション）
1. 井戸の底に到達する
2. 突如現れた守護者から解放される
3. 秘鍵を入手する

目的：古代遺跡の中央祭壇で儀式を完遂する（4セクション）
1. 祭壇のある広間に到達する
2. 祭壇の封印を解く
3. 儀式中に現れた異形の妨害を退ける
4. 儀式を完遂する

目的：失踪した商人を生きたまま保護する（3セクション）
1. 商人の所在を突き止める
2. 商人を拘束する賊の支配から解放する
3. 商人を保護する

目的：賢者の遺言を読み解く（4セクション）
1. 遺言の保管場所を発見する
2. 偽の遺言であることが判明する
3. 真の遺言の所在を突き止める
4. 真の遺言を読み解く

▼ goal設定の悪い例
【手段羅列型】
- 潜る道具を準備し、井戸の様子を確認し、底にたどり着く
- 情報を集め、装備を整え、旅立つ
【目的分解型】
- 井戸まで移動する
- 井戸に入る
- 井戸の底に到達する
- 鍵を拾う
【説明過多型】
- 深く暗い井戸を慎重に降りながら底を目指し、やがてそこで輝く秘鍵を拾う
- 冒険者としての使命感を胸に、仲間のために秘鍵を手に入れる
【ぼんやり型】
- 鍵を探す
- 出発する
- 問題を解決する

【title補足】
- 基本的にはシナリオ構成時に決定した章タイトルをそのまま使用する。
- プレイヤーの行動によって章内容が大きく変わり、元のタイトルと展開がかけ離れた場合のみ変更を許可。
- 変更時は、シナリオ作成時に指定された命名パターン（名詞句型、動詞連体型、熟語型、比喩型など）を維持すること。
- 「第◯章」等の章番号は付けず、タイトル単体で完結する詩的な表現にする。

【命名パターン一覧（8系統）】
1. 名詞句型  
  例：「深海の記憶」「雪に閉ざされた約束」「黄昏の果樹園」「遠雷の王宮」「星屑の舟歌」
2. 動詞連体型  
  例：「沈まぬ月を追いかけて」「忘れられた名を呼ぶとき」「海を越えて光を探す」
3. 熟語拡張型（漢字2〜4字＋修飾/二段構造）  
  例：「紅蓮迷宮の肖像」「虚無回廊を渡る影」「星霜殿の末裔」「夢幻峡を越えて」
4. 比喩型（二項対比）  
  例：「黒い太陽、白い影」「鳥籠に降る星屑」「氷原と火の花」「森の底、海の上」
5. 名詞連続型（長音リズム：「〇〇と〇〇と〇〇〇〇〇」）  
  例：「月夜と鉄と硝子のかけら」「風と灰と真珠の瞳」「水と炎と忘却の街」
6. 疑問・呼びかけ型  
  例：「きみは灯を見つけられるか」「誰が夜を殺したのか」「そこに海はあったか」
7. 時・季節型  
  例：「冬至の檻」「三日月の約束」「春告鳥の消える夜」「夏至祭の灯火」
8. 叙事詩型（〜の物語／〜記／〜譚）  
  例：「白鯨の譚」「七つの門の記録」「灰色の都の物語」「双頭竜の年代記」


【flow補足】
- goal（セクションの目的 上記と同じ）:
  - 各セクションのgoalは、そのセクションを終えると次に進める「結果」のみを記述する。
  - 手段や工程は書かない。
  - 中間の1〜2セクションに予想外の事態や障害を入れ、その解決を条件とする。
  - 予想外の事態は、戦闘・交渉・隠密など複数の解決手段を許容する表現にする（例：「支配から解放する」「封印を解く」）。
  - 最終セクションのgoalは章の目的とほぼ一致させる。
  - セクション数は2〜5を目安にし、章の規模や展開に応じて調整する。

- scene: 以下の分類から英語で指定してください。
   ・exploration：AI主導の通常探索（街道、町、拠点など）。基本的にほぼ全てこれ。
   ※他のscene種別は未実装のため使用しない。

- description: NPCの動き、罠やイベント、選択肢、背景など状況の詳細。推奨される進行ルートや選択肢も含める。200字程度。

- has_combat: 戦闘が発生する可能性の有無（true/false）

- description:
  200字程度。NPCの行動、罠やイベント、環境変化、選択肢など詳細を記述。
  goal に書いた予想外の事態の背景や詳細はここで補足する。
- has_combat: 戦闘の有無（true/false）。

【canon補足】
- この章で新たに判明した重大事実のみ（最大3件）。
- 既存のカノンや世界観固有名詞は含めない。
- type: 以下から選んでください：
    ・場所（都市、村、遺跡、ダンジョン、建物、地域、自然地形、異界など具体的な地理的地点）
    ・人物（名前を持つNPC、神格、固有名の魔王や賢者、特定個体の怪物や英雄など）
    ・組織（国家、宗教、ギルド、一族、派閥、軍、会社など集団組織）
    ・種族（エルフやドワーフなどの種族、動物、魔物、アンデッド、人工生命など）
    ・物品（武器、道具、乗り物、遺物、財宝、文書、鍵など重要なアイテム）
    ・知識（伝承、歴史、文化、宗教教義、技術、魔法体系、法律、習俗など背景設定）
    ・ギミック（罠、装置、結界、封印、祭具、遺跡の機構など、このシナリオ内でのみ登場し解除や操作が必要な要素）
    ・現象（呪い、災厄、異常気象、魔力の渦など継続的または一時的に発生する事象）
    ・出来事（戦争、儀式、事件、探索行、反乱、条約、祭りなど特定の期間や場面の出来事）
- note: 100文字以上で詳細や背景を記述。

【全体方針】
- flow 全体は章の目的に沿わせる。
- PCの意思を勝手に決定しない。
- 不要な時間制限は設けない。
- 地に足ついたリアリティを重視。
"""


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
