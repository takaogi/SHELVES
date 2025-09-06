# phases/scenario/gameflow/director.py
import json
import logging
from typing import Optional, Dict, Any
from infra.path_helper import get_data_path

class Director:

    # ===== 共通スキーマ =====
    progression_schema = {
        "type": "json_schema",
        "name": "Progression",
        "strict": True,
        "schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "act": {"type": "string", "maxLength": 100},
                "flow": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "loc": {"type": "string", "maxLength": 60},
                        "obj": {"type": "string", "maxLength": 60},
                        "nps": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                            "maxItems": 5
                        },
                        "env": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "t": {"type": "string", "maxLength": 20},
                                "w": {"type": "string", "maxLength": 20},
                                "s": {"type": "string", "maxLength": 20}
                            },
                            "required": ["t","w","s"]
                        },
                        "pts": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1, "maxLength": 24},
                            "maxItems": 5
                        }
                    },
                    "required": ["loc", "obj", "nps", "env", "pts"]
                },
                "cmd": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "op":   {"type": "string", "enum": ["add_item","remove_item","add_history","create_canon"]},
                            "name": {"type": "string", "minLength": 1},
                            "count":{"type": "integer", "minimum": 0},  # 使わないときは 0
                            "type": {"type": "string"},                  # 使わないときは ""
                            "note": {"type": "string"}                   # 使わないときは ""
                        },
                        "required": ["op","name","count","type","note"]
                    }
                },
                "cue": {
                    "type": "string",
                    "enum": ["action", "combat", "end", "none"]
                }
            },
            "required": ["act", "flow", "cmd", "cue"]
        }
    }




    def __init__(self, ctx, state, flags, convlog, infos: None):
        self.ctx = ctx
        self.state = state
        self.flags = flags
        self.convlog = convlog
        self.infos = infos
        self.log = logging.getLogger("shelves.gameflow")  # ← 直接logging

        # 起動時にディスクから前回Progressionを読む
        self._last_progression: Optional[Dict[str, Any]] = self._load_progression_from_disk()

    def _load_progression_from_disk(self) -> Optional[Dict[str, Any]]:
        wid = getattr(self.state, "worldview_id", None) or getattr(self.state, "wid", None)
        sid = getattr(self.state, "session_id", None) or getattr(self.state, "sid", None)
        if not (wid and sid):
            return None
        p = get_data_path(f"worlds/{wid}/sessions/{sid}/progression_last.json")
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            #self.log.warning(f"[Director] failed to load progression: {e}")
            return None

    def _persist_progression(self, prog: Dict[str, Any]) -> None:
        # メモリ保持
        self._last_progression = prog
        # ディスク保存
        wid = getattr(self.state, "worldview_id", None) or getattr(self.state, "wid", None)
        sid = getattr(self.state, "session_id", None) or getattr(self.state, "sid", None)
        if not (wid and sid):
            return
        p = get_data_path(f"worlds/{wid}/sessions/{sid}/progression_last.json")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(prog, f, ensure_ascii=False, indent=2)
        except Exception as e:
            #self.log.warning(f"[Director] failed to persist progression: {e}")
            return None

    # ===== プロンプト差し替え =====
    def _get_system_prompt(self, label: str) -> str:
        common = """
【Progression JSON 共通仕様】

あなたはTRPGの進行AI（GameFlow AI）です。プレイヤー発話、直近会話要約（slim）、worldview / character / nouns / canon / plan を読み、
シナリオ進行用の Progression JSON を厳密に生成してください。**出力はJSONのみ**です。

【フィールド規約】
- act … プレイヤー発話の“行為”を一行の自然な日本語に言い換える（主語はPC名）。結果断定や目的混入は禁止（100字以内）。
- flow
  - loc … 現在地（≤60字）
  - obj … PC本人の“現在の行動目的（志向）”。章/セクション目標とズレていてもよいが、PCの知識に基づくこと（≤60字）
  - nps … 関与NPCの **canon名** リスト（最大5件、重複禁止）
  - env … {"t":時刻, "w":天候, "s":季節}（不要なら空白入力で省略可）
  - pts … 次の描写で **必ず言及** させる要素を短句で列挙（各≤24字、最大5件、重要度順）
    - cmd の各動作は必ず pts に人間語でミラーする
    - cue 連携：cue="action"→どの行動に対する判定か、cue="combat"→誰とどんな状況で戦うか、cue="end"→セクションgoalを満たした根拠を含める
- cmd … **このターンで確定する変更のみ** を構造化JSONで列挙（無ければ []）。自然文や角括弧コマンドは出力しない
- cue … 次段の進行合図（"action" | "combat" | "end" | "none" のいずれか）

【act（行為の言い換え）の厳密ルール】
- 目的ではなく“いま実際にやる行為”を、日本語として自然に**文体整形**して一行で書く。
- 主語はPC名を補い、場面固有の名詞があれば明示する（扉／通路／対象NPCなど）。
- プレイヤー原文に**忠実**だが、敬体・常体・助詞などを整えて読みやすくする。
- 例（→が出力イメージ）
  - 「とりあえず扉を開けて様子を見ます」
    → 「〈PC名〉は扉を開け、その先の様子をうかがう」
  - 「蹴り破る」
    → 「〈PC名〉は〈対象の扉〉を蹴り破ろうとする」
- 禁止：結果の断定（成功/失敗）、目的の混入（“宝を得るために扉を～”は obj 側へ）。

【obj（PCの行動目的＝志向）の厳密ルール】
- **PC本人が現在もっている“行動の目的”**を書く。短〜中期の個人的志向を60字以内で。
- **シナリオの章/セクション目的とズレていてよい**。PCがまだ知らない情報を前提にしない。
- プレイヤーが“キャラとして今なぜ行動しているか”を一目で把握できる内容にする。
- 良い例：「遺跡の奥の宝を手に入れたい」「遭難者の手がかりを集めたい」「〈カイ〉を助けたい」
- 悪い例：「扉を開けたい」（← act に書く）/「NPCは黒幕だと暴く」（←未取得の確定情報）

【objの整合性規約】
- **情報非開示**：plan/GMメモ等のメタ情報を obj に混ぜない（PCの知識のみ）。
- **継続**：新たな動機が出ない限り、直前ターンの obj を維持してよい。
- **更新**：判定・情報取得で動機が変わる場合、post系で obj を更新する。
- **論理一致**：act と obj は矛盾しないこと（act「逃走」 vs obj「ここを調査」は不可）。

【flow の他キー】
- nps: 直接関わるNPCの**canon名**（最大5件）。
- env: {"t":時刻,"w":天候,"s":季節}。不要なら省略。
- **pts（必読：生成規約）**
  - 目的：Narrator が**本文で必ず言及**すべき要素を揺れの少ない短文で列挙する。
  - 形式：常体の短句（主語省略可）。**各項目≤24字**、基本1~2件、最大5件。順序は重要度順。大雑把でよく、同じような内容は書かない。
  - 推奨テンプレ（語彙を固定して揺れを減らす）：
    - 取得：「〈アイテム〉を受け取る／手に入れる」
    - 失う：「〈アイテム〉を失う／消費する」
    - 開閉・通行：「〈対象〉が開く／閉まる」「〈場所〉への通行が許可される」
    - 反応：「〈NPC〉が頷く／渋る／警戒する」
    - 情報：「〈痕跡/手掛かり〉を見つける」「〈事実〉が判明する」
    - 余波（戦闘後）：「〈負傷/血痕/徽章〉が残る」「周囲が静まる」
  - **cue との連携（重要）**
    - cue="action" のとき、どの行動に対して行為判定を行うのかをptsに含める。
    - cue="combat" のとき、誰とどのような状況で戦うのかをptsに含める。
    - cue="end" のとき、**現在セクションの goal を満たした根拠**を pts に含める（例：「遭難者を救出する」「祭壇の封印を解く」など）。

【cmd】
- このターンで確定する変更のみ。
- 例：add_item/remove_item、ログ的history、軽微なcanonの確定など。
- 成否依存の結果は **post_check / post_combat** フェーズで反映する（その際も cmd↔pts を対応）。

【cmd の仕様（重要）— “op” とペイロード】

このターンで「確定する状態変化」だけを機械可読に列挙してください。出力は JSON 配列（cmd）です。

■ 共通形式（厳守）
各要素は必ず次の5キーを含めること：
{ "op": string, "name": string, "count": integer>=0, "type": string, "note": string }

- 使わないフィールドも必ず入れる（未使用の埋め方を厳守）  
  ・未使用の数値 → count: 0  
  ・未使用の文字列 → type / note: ""（空文字）
- op は次のいずれかのみ： "add_item" | "remove_item" | "add_history" | "create_canon"
- 1ターンで複数要素を並べてよい（配列）。

■ 各 op の書式（未使用は 0 / "" で埋める）

1) アイテム追加
{ "op":"add_item", "name": <string>, "count": <integer>=1, "type":"", "note": <string or ""> }
- プレイヤーが取得したアイテムを追加。  
- 既存アイテムの再取得で説明を変更しない場合は note を "" にする。

2) アイテム削除
{ "op":"remove_item", "name": <string>, "count": <integer>=1, "type":"", "note":"" }
- 破損・消費などで所持品から減る場合。note は常に ""。

3) 既存カノンへの履歴追加
{ "op":"add_history", "name": <string>, "count":0, "type":"", "note": <string> }
- 既存 canon に「新事実」「新解釈」を追記。note は 1 文以上。

4) 新規カノン作成
{ "op":"create_canon", "name": <string>, "count":0, "type": <string>, "note": <string> }
- 新しい canon を記録。type は次から厳密に選択：  
  「場所 / NPC / 知識 / アイテム / ギミック / その他」
- note は 100 文字以上が望ましい。  
  ・NPC → 容姿・性別・役職・口調を必ず含める  
  ・ギミック → 解除方法を必ず含める

■ 例

- 箱の中から「銀の鍵」を入手：
{ "op":"add_item","name":"銀の鍵","count":1,"type":"","note":"古びた装飾が施された鍵" }

- 戦闘中に「松明」を1つ失う：
{ "op":"remove_item","name":"松明","count":1,"type":"","note":"" }

- 既存カノン「村の起源」に事実を追加：
{ "op":"add_history","name":"村の起源","count":0,"type":"","note":"この村は魔女の一族によって建てられた。" }

- 新NPC「ルシア」を作成：
{ "op":"create_canon","name":"ルシア","count":0,"type":"NPC","note":"若い女性司祭。銀色の髪と淡い青の瞳、穏やかな口調。村人から厚く信頼されるが、過去に一度失踪しその間の記憶がない。" }

■ 注意
- cmd に列挙した事実は、flow.pts に人間語で必ずミラーする（ズレ防止）。
- cue は "action" / "combat" / "end" / "none" のいずれか。end のときはセクション goal を満たした根拠を pts に含める。


【cue（進行合図：厳密運用）】
- "action"：**行為判定**を実施すべきと判断した場合。
- "combat"：**戦闘開始**が最適/不可避。
- "end"：**セクション終了を確定提案**。**現在セクションの goal（plan 提供）を今回の描写で満たしたら必ず選ぶ。選び漏れは進行破綻を招くため禁止。**
  - 例：goal「遭難者を救出」→ このターンで救出が完了したなら cue="end" を必ず返す。
- "none"：特別な処理は不要（描写のみで次の入力へ）。判定/戦闘/終了の条件を満たさない場合に選ぶ。


【整合・制約】
- act と obj は論理矛盾を起こさないこと（例：act「逃走」 vs obj「ここを調査」は不可）
- obj は PCの知る事実/推測のみで書く（plan等のメタ情報を混ぜない）
- 文字数上限：act≤100字、flow内各文字列≤60字、pts各項目≤24字
- リスト上限：nps/pts は各最大5件（cmdは必要数で可）
- 必要キーは必ず含める（cmd は空配列 [] 可）
- plan（章/セクション目標）は参照のみ。**obj には“PCの目的”だけ**を書く
"""
        if label == "action":
            return f"""{common}

【このフェーズは 通常】
- プレイヤーが能動的な行動を宣言した段階。
- act は行動要約。flow.obj はpcの直近の目的。
- 判定成否に依存しない、確定した cmd のみを追加可。
- cue の選択基準:
  - 判定が必要: "action"
  - 戦闘開始不可避: "combat"
  - セクション終了: "end"
  - それ以外（通常の進行）: "none"
"""
        elif label == "post_check_description":
            return f"""{common}

【このフェーズは post_check_description（行為判定 直後）】
- act：結果を織り込んだ行為の要約（例：説得が通り門を通過する／鍵開けは叶わず扉は閉ざされたまま）。
- flow.obj：判定によりPCの志向が**変化した場合のみ更新**（変化が無ければ維持）。
- flow.pts：この判定で**新たに確定した事実**や、次描写で必ず触れるべき要素を最大3件。
- cmd：今回で**確定**した変化（取得/損失/情報確定/履歴追加など）のみ。
- cue：通常は "none"。ただし**現在セクションの goal を満たしたら "end"**。

【“結果の質”による調整ルール（**内部判断**）】
- 直前ログの「行為判定 結果」（出目/達成値/目標値）から質を推定し、各フィールドへ反映する。
- 目安（例）：
  - クリティカル または（達成値-目標値）≥+5 … **極めて良好**
  - +3〜+4 … **余裕の成功**
  - 0〜+2 … **ぎりぎり成功**
  - -1〜-2 … **惜しい失敗**
  - ≤-3 … **大きな失敗**
  - ファンブル … **最悪級の失策**
- フィールド反映方針：
  - **極めて良好 / 余裕**：
    - flow.pts：副次的な有利（近道が開く、NPCの信頼が増す等）を入れる。
    - cmd：情報確定や有益な取得（add_history / add_item 等）を積極的に反映。
  - **ぎりぎり成功**：
    - flow.pts：成功はしたが緊張や制約が残る要素を記す。
    - cmd：最小限の確定のみ。余韻や不安定要素は cmd に入れない（pts で言及）。
  - **惜しい失敗**：
    - flow.pts：手応えはあった事実・次の試みで突破可能な示唆。
    - cmd：失敗で確定した事実のみ（例：時間経過による状況変化の履歴追加）。
  - **大きな失敗 / 最悪級**：
    - flow.pts：明確な不利や障害・リスクの顕在化。
    - cmd：後に影響する**確定的な不利**（例：資源損失、騒ぎの拡大を add_history 等で記録）。
"""
        elif label == "post_combat_description":
            return f"""{common}
    
【このフェーズは post_combat_description（戦闘 直後）】
- act にはプレイヤー入力から得られた「戦闘の成否」を踏まえ、
  PCがどう戦い、どういう理由で勝利したのか／逆にどうして不利になったのかを
  一行で簡潔に要約する。
  例：
    - 「〈PC名〉は渾身の一撃で敵を倒した」
    - 「〈PC名〉は防御を崩され窮地に追い込まれた」
- flow.obj：戦闘の帰結でPCの志向が**変化した場合のみ更新**（変化が無ければ維持）。
- flow.pts：戦闘余波として**次の描写で必ず言及**すべき要素を最大5件（各≤24字、重要度順）にまとめる。
  - 必須候補（状況に応じて選択）：敵の反応／戦況推移／環境の変化／味方・NPCの反応／戦利品・痕跡／次行動の手掛かり
  - **メタ語は禁止**（達成値/判定語/クリティカル/ファンブル等は書かない）。
- cmd：今回で**確定**した変化のみ（例：戦利品の獲得、消耗、重傷に伴う履歴追加、地形・装置の確定、NPC関係値の更新など）。
  - 例：戦利品 → add_item、消耗/破損 → remove_item、顕在化した事実 → add_history、新規確定要素 → create_canon
  - cmd の各事実は **flow.pts に人間語でミラー** する（ズレ防止）。
- cue：
  - 通常は "none"
  - **戦闘継続が自然**（最終局面/強敵/僅差など）の場合は "combat"（※戦闘判定は**最大2回まで**を想定）
  - **現在セクションの goal を満たしたら "end"**（満たした根拠を flow.pts に入れる）

【内部判断：成否・質の解釈（描写は非メタで反映）】
- 目安：
  - 高達成（おおよそ12以上に相当） … 基本は有利な帰結
  - 低達成（おおよそ8未満に相当） … 基本は不利な帰結
  - 境界（8〜11） … 敵の強さ・戦法の質・状況で裁量判断
  - 出目最大（6+6） … **圧倒的に有利な展開**（副次的メリットも）
  - 出目最小（1+1） … **重大な不利やトラブル**（ただし敵が雑魚なら致命傷化は回避し得る）
- 反映方針：
  - 有利：flow.pts に「敵の動揺」「包囲の解消」「逃走路の確保」等の追い風を入れ、cmd に戦利品や有益情報を反映。
  - 僅差の有利：余韻や制約（弾薬の残り、騒ぎの拡大など）を pts に、cmd は最小限。
  - 僅差の不利：次に繋がるヒントや代替案（遮蔽物、地形利用、会話転換）を pts に。
  - 不利：明確な障害やリスク（負傷/拘束/警報）を pts に、cmd に確定不利（消耗・損壊・関係悪化）を記録。
- **PCは物語途中で死亡しない**。重傷や劣勢の描写は許容するが、ゲーム不能化は避ける。

【実力差の補正（レベル基準）】
- PCレベル目安：
  0：一般人／1〜3：初心者〜見習い／4〜6：一人前／7〜10：超人的／11〜13：伝説級／14〜15：神格級
- **圧倒的な格下**を相手にする高レベルPC：出目が悪くても結果は制圧的に傾く（cmdは有利寄り）。
- **格上に挑む低レベルPC**：成功時は決定打を許容。不利時も「退路」「会話」「環境利用」等の次手を pts で提示。
- 補正は**描写とcmdの重みづけ**で表現（メタ語は使わない）。

【継続戦の取り扱い】
- 戦闘の継続が自然なら cue="combat" を返す。flow.pts に「継続理由（敵の再編／増援／危険ギミックの起動）」と
  「次の勝ち筋（遮蔽へ移動／要人確保／装置停止）」を1つ以上含める。
- 継続しても **最大で2回目まで** を前提に、過剰な引き延ばしはしない。

"""
        else:
            return common


    # ===== 共通呼び出し =====
    def handle(self, label: str, player_input: str) -> Dict[str, Any]:
        # Informations
        prompt_infos = self.infos.build_prompt(
            include=["scenario", "worldview", "character", "nouns", "canon", "plan"],
            chapter=self.state.chapter
        )

        # convlog は読むだけ（ここで append しない）
        history = self.convlog.get_slim()

        # 前回Progressionを最終入力へ同梱
        prev_prog = self._last_progression
        if prev_prog:
            prev_blob = json.dumps(prev_prog, ensure_ascii=False)
            final_user = (
                "【前回のProgression JSON（参考）】\n"
                f"{prev_blob}\n\n"
                "【今回のプレイヤー入力】\n"
                f"{player_input}"
            )
        else:
            final_user = player_input

        # ← ここから追記：現在セクションのgoalを提示し、満たしたら必ず cue='end' を返すよう指示
        goal_text = self.infos.get_current_section_goal()
        final_user += (
            "\n\n【現在のセクションのgoal】\n"
            f"{(goal_text or '（未設定）')}\n"
            "※今回の描写でこのgoalを満たすなら、Progression の \"cue\" は必ず \"end\" を返してください。"
        )

        system_prompt = self._get_system_prompt(label)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": prompt_infos},
            *history,
            {"role": "user", "content": final_user},
        ]

        prog = self.ctx.engine.chat(
            messages=messages,
            caller_name=f"Director.{label}",
            model_level="high",
            schema=self.progression_schema,
            max_tokens=3000
        )

        # 生成されたProgressionをディスクへ保存（次ターン参照用）
        if isinstance(prog, dict):
            self._persist_progression(prog)
        return prog