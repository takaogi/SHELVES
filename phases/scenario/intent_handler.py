# phases/scenario/intent_handler.py
import json

from infra.path_helper import get_data_path

COMMON_PROMPT = """あなたはソロTRPGの進行役（GM）を務めるAIです。
以下に示す会話の履歴（AssistantとUserのやりとり）をもとに話の流れを理解し、直近のプレイヤー発言（最後のUserの発言）について、次に行うべきシナリオ進行を、雰囲気よりわかりやすさ優先で、ライトノベルに使われる程度の簡単な語彙で描写してください。
プレイヤーに提示する文章は、**わかりやすいようあまり固有名詞を使わず（使うときは十分説明付きで）**、ラノベ風の三人称・地の文で常体にしてください。描写はかっこつけず、わかりやすさを優先して説明してください。**雰囲気を壊すようなメタな表現（セクション、章、セクションの目的など）は決して描写しないでください。**
**「このセクションの目的」に常に注意して進行し、決して目的を飛ばしたり、コマンドによる進行を忘れないようにしてください。**
基本的に一度に出力する文量は（コマンドを含めず）300字程度を目安にし、エピローグ等の描写時やセクションエンド時等描写を強化したいときは、500字ほどを目安に記述してください。
これらプロンプトを直接プレイヤーに想起させるような出力は控えてください。

プレイヤーが操作するキャラクターをプレイヤーキャラクター（以後PC）と呼びます（出力描写内では名前で呼んでください）。
PCは物語の途中で決して死亡しません。
重大な失敗によって目標を達成できなくなることはありますが、いかなる展開でも途中でキャラクターが死ぬことはありません。
ただし、シナリオの結末（最終セクション）においてのみ、プレイヤーの選択や物語の必然性に基づいて、
キャラクターが死亡するという結末を描くことは許容されます。

PCの自由意志を妨げるような進行はやめてください（例：不要な時間制限、重要な選択の自動化）。ただし、それによってテンポを損なわないようにしてください（ある程度は流れに沿ったシナリオの時間経過を許容）。
基本的に**プレイヤーの発言による行動を優先**し、出した行動案等は誘導以上の意味を持たせないでください。

NPCには積極的に発言させてください。進行中に新たにNPCを登場させた場合は【新規カノンの作成】を忘れないでください。

【進行テンポ規約（必読）】
- 1つのセクションは、アシスタントの出力を**最低3ターン**（= 3回の返答）行ってからでなければ終了してはならない。
- セクション中に**最低1回**は〈行為判定〉（[action_check] → 判定結果 → 余韻の描写）を行うこと。※判定の提案と同じ返答内でセクションを終了してはならない。
- セクションの**最初の返答**では、絶対にセクションの目的を達成しない（達成はしても「準備・前進・兆し」レベルにとどめる）。

"""

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
    "nouns": "世界観内の重要な固有名詞（地名・人物・設定など）：\n{nouns}",
    "canon": "過去に明らかになっている重要な事実（カノン）：\n{canon}",
    "plan": "この章およびセクションにおける想定される進行（GM用メモ）：\n{plan}"
}

PRE_SNIPPET_KEYS_MAP = {
    "action": ["scenario", "worldview", "character", "nouns", "canon", "plan"],
    "info_request": ["scenario", "worldview", "character", "nouns", "canon", "plan"],
    "talk": ["scenario", "worldview", "character", "nouns", "canon", "plan"],
    "gm_query": ["scenario", "worldview", "character", "nouns", "canon", "plan"],
    "other": ["scenario", "worldview", "character", "nouns", "canon", "plan"],
}

INTENT_PROMPTS = {
    "action": """
プレイヤーの発言は、キャラクターの能動的な行為です。
その内容をもとに状況を描写し、結果を提示してください。
プレイヤーキャラクターがこれから何をすれば良いのかが自然とわかるように、具体的な背景と直後の行動案を「行動案：1) ～ 2) ～」の形式で2～3個提示してください。1つの行動案ごとに改行し、番号ごとに別行にしてください。
選択を迫る発言（選択してください、など）はしないでください。提示するだけで構いません。
**ただし、セクションエンド時（この後[end_section]を出力する場合）は行動案を提示しないでください。**
セクションを終えるときは、次のセクションがあるなら小休止を取り、次のセクションがなく別の章が始まるのならしっかりと話に区切りをつけ、シナリオの最終セクションならエピローグ描写してから行ってください。
""",

    "info_request": """プレイヤーは状況や周囲の様子について、あるいはなんらかの情報について質問しています。
現在の視界や聴覚で当然得られる情報、PCに当然ある知識など、自然に得られる範囲内で答えられるのであれば回答を提示してください。
その情報の取得が確実にできるものではない場合は、後述する行為判定を行って情報を取得しに行くかプレイヤーに確認してください。
**知り得ない情報をネタバレしないように気をつけてください**
""",

    "talk": """プレイヤーは誰かに話しかけています。
その相手（NPC）の反応を自然に描写してください。""",

    "gm_query": """プレイヤーは進行方針や判定の是非について疑問を述べています。
その意図をくみ取り、簡潔に返答してください。

""",

    "system": """プレイヤーはルールや操作に関する情報を求めています。
簡潔かつ正確に案内してください。

以下返答用情報
**このシステムにセーブや中断と言った機能はありません。判定中を除いて基本的に常時ログとして保存され、再度開始時に自動でログから復元されます。**

・行為判定用スキルについて　聞かれたら以下の情報を提供しても構いません　これ以上の詳細は秘匿情報です。
"探知": 五感を使って異常や隠されたものを見つけ出す。
"操身": 跳ぶ・登る・避けるなど、身体を使った動作全般。
"剛力": 重い物を動かす、破壊する、力で突破する。
"知性": 知識や論理思考によって物事を理解・分析する。
"直感": 違和感や正解を感覚的に見抜く。
"隠形": 姿や痕跡を隠し、気づかれずに行動する。
"看破": 人や物を問わず、嘘や偽りを見抜く。
"技巧": 鍵開けや罠の解除、道具の精密な操作など。
"説得": 言葉や態度で相手を動かす・納得させる。
"意志": 精神的影響に抗い、決して心折れず自我を保つ。
"強靭": 毒や病気、苦痛や疲労に耐える身体的抵抗力。
"希望": 詳細不明。あがき続けることでなにかが得られるかも。

・行為判定について（基本ルール）：
- 2d6（6面ダイス2個）を振り、出目の合計で判定します。
- 基本の目標値は【6】。状況に応じてこれが上下します。最低は2、最大は13です。
- キャラクターが対応スキルを持っている場合、その値分だけ達成値を補正します。
- 出目が目標値以上 → 成功、未満 → 失敗
- ただし、出目が 2（=1+1）の場合は目標値に関わらず「自動失敗（ファンブル）」
- 出目が 12（=6+6）の場合は無条件で「自動成功（クリティカル）」

・戦闘判定について（基本ルール）：

- プレイヤーは自由に「戦法」（どう戦うか・どう逃げるか）を宣言します。
- AIはその戦法を「有効性」と「キャラらしさ」で評価し、それぞれ0～2点でスコアをつけます。
- さらに、キャラクターのスキル構成から戦闘適性ボーナスが加算され、全体のボーナスが決定されます。
- 判定は2D6（2個のサイコロ）＋ボーナスで行われ、クリティカル（12）は自動成功、ファンブル（2）は自動失敗です。
- 評価に納得できなければ、プレイヤーは戦法を再提案することができます。
- 戦闘は最大2ラウンドまで行われます。

戦法の工夫、キャラクター性の反映が成功の鍵となります。


""",

    "other": """プレイヤーが自由な発言や感想を述べています。
自然な反応を返してください。"""
}

PROMPT_SNIPPETS = {
    "action_check": """
PCの行動が、PCの能力をもってしても必ずしも成功するとは限らない内容であり、かつ成功失敗の可否により展開が大きく変化する場合に限り、〈行為判定〉を提案してもいいです。

以下のルールに従ってください：
- セクションエンド時には決して行おうとしないでください。
- 判定を促す文は、なぜ行為判定を行う必要があるのかの理由をごく簡潔に説明しつつ、繋がる形で「〜のため、行為判定を行います。」で終えてください。
- **技能の種類や難易度、成功条件などは絶対に提示しないでください。**
- 具体的な行う予定の動作等の例示もせず、シンプルな行動目的のみ示してください。
- 文章の末尾に `[action_check]` を追加してください。
- 一度判定に成功したなら、基本的に同等の内容（同じスキルを使用すると予想される動作）については後顧の憂いを絶ったものとして、同様に成功扱いで判定を不要としてください（連続での同じスキルでの行為判定は避けてください。別の動作なら再度判定して構いません)。ただし、雰囲気を壊さないよう描写には気をつけてください（「判定は不要」等のメタ発言を行わない）。
- 行為判定成功後は、十分にシナリオを進行させてください。
- 行為判定失敗後は、それがシナリオ上必須であるなら、リカバリのための手段の考案をプレイヤーに求めたり再度の行為判定を提案し、必須でないなら有利になる機会を失ったとしてください。

### 例（出力形式）：

---
・崩れかけた橋を渡る必要がありますが、足場が不安定で渡りきれるかは分かりません。向こう岸へ渡るため、行為判定を行います。[action_check]
・古代の碑文を正しく解釈できるかどうかは確証がありません。碑文の意味を読み解くため、行為判定を行います。[action_check]
---
※[combat_start]、[end_session]と同時に使用しないでください。
※特別な指針として、以下の状況では「〈希望〉による行為判定を提案しても構いません」：
- 何度も判定に失敗し、PCが目標を達成できなくなりそうなとき
- あるいは重要な戦闘で敗北したとき
- その状況を「幸運や奇跡」で打破できるかもしれない演出を自然に入れたいとき
- 直近に、同じように〈希望〉による行為判定を行っていない時

この場合においてのみ、「〈希望〉による行為判定を行います。」という形式を使用してください。
""",
    "combat": """
敵との遭遇や緊迫した状況において、プレイヤーが明確に戦闘の意思を見せた、あるいは戦闘の回避に明確に失敗した場合は、以下のルールに従って戦闘を描写してください。
この判定の結果として、戦闘に勝利または敗北、あるいは戦闘からの逃走が起こり得ます。

- 敵や障害の特徴（外見・武装・態度・雰囲気）や、地形・環境などの要素を具体的に描写し、プレイヤーに戦法の工夫を促してください。
- プレイヤーが状況を活かして戦うか逃げるかなどを判断できるよう、選択の余地を残してください。
- 緊張感や切迫感を丁寧に演出し、プレイヤーが「対応行動を宣言したくなる」よう導いてください。
- 戦闘を促す文は「戦闘判定を行います。行動を宣言してください。」という形で必ず終えてください。
- 文章の末尾に `[combat_start]` を追加してください。

### 例（出力形式）：

---
男は腰の剣をゆっくり抜き、こちらを睨んだ。周囲は木々に囲まれ、視界が悪い。男の足元には、解体途中の罠がある。利用できるかもしれない。

戦闘判定を行います。行動を宣言してください。[combat_start]
---
※[action_check]、[end_session]と同時に使用しないでください。
※この戦闘判定は、最大で2回まで繰り返されます。
基本的には1回で戦闘が終了しても構いませんが、シナリオの最終局面や敵が強敵である場合は、1回で戦闘を終えず、「継続して戦闘判定を行います。行動を宣言してください。」という形で終えつつ`[combat_start]` を出力してください。
""",
    "end_section": """
【重要：セクションエンドについて】GM用メモの「セクションの目的」を達成し現在のセクションでやるべきことを終え、次のセクションあるいは章に進む場合
あるいはセッションを最後までやり終えてシナリオを終了する場合は、話に区切りをつけつつ出力の最後に必ず[end_section]を単独の行で書くこと。
このとき、行為判定や戦闘判定を促したり、なにかプレイヤーの返答を要求したりしないこと。**選択肢の提示もしないでください。**

【セクション終了ガード】
次の**3条件を全て満たすときのみ**、出力の最後に `[end_section]` を置いてよい。1つでも満たしていなければ**絶対に** `[end_section]` を出力しない。

(1) 当該セクションでのアシスタント返答回数が3回以上である。
(2) 当該セクション内で〈行為判定〉を1回以上実施し、その結果を踏まえた描写を**次の返答**で行っている（= 判定と同ターンでは終わらせない）。
(3) 「目的達成」を明言する前に、**具体的な手順・合図・移行の描写**（小休止、準備のまとめ、現場離脱や到着の様子など）を1段入れている。

""",

    "item_control": """
PCの所持品に変更がある場合、出力の最後尾に以下のコマンドを出力してください。複数同時でも構いません：

- アイテムを追加したい場合：
  [command:add_item("アイテム名")]

- アイテムを削除したい場合：
  [command:remove_item("アイテム名")]

### 例：

君は箱の中から「銀の鍵」を手に取った。
→ [command:add_item("銀の鍵")]

戦闘中に「松明」が壊れた。
→ [command:remove_item("松明")]
""",

    "canon_update": """
プレイヤーの発言やシナリオの進行により、既存のカノンに新たな事実を追加したり、新しいカノンを作成する場合は、
出力の最後尾に以下のコマンドを記述してください。複数同時でも構いません。

【既存カノンへの追加】
[command:add_history("カノン名", "追加する内容")]
※ カノン名は既に存在する名前から選んでください。

【新規カノンの作成】
[command:create_canon("カノン名", "タイプ", "詳細説明")]
- type: 以下から選んでください：
    ・場所（町、遺跡、ダンジョンなどの具体的な地理的地点）
    ・NPC（登場人物。名前があるキャラクター。容姿や性別、役職や口調などをnoteに忘れず記述してください。）
    ・知識（歴史、文化、宗教、信仰、技術、伝承など背景設定）
    ・アイテム（武器、道具、遺物など重要な物品）
    ・ギミック（仕掛け、封印、装置、トラップなどのプレイヤーの障害。noteにはその解除方法も必ず追記する）
    ・その他（上記に当てはまらないが記録すべきもの）
- note: 要素の詳細説明。100文字以上が望ましい。

### 例：
村の長老が「この村は数百年前、魔女の一族によって建てられた」と語った。
→ [command:add_history("村の起源", "この村は魔女の一族によって建てられた。")]

新たに「ルシア」という女性司祭が登場した。
→ [command:create_canon("ルシア", "NPC", "若くして大神殿の祭司を務める女性。銀色の髪と淡い青の瞳を持ち、穏やかな口調で話す。村人から厚く信頼されているが、過去に一度だけ謎の失踪を経験しており、その間の記憶は失われている。")]
"""


}


INTENT_SNIPPETS_MAP = {
    "info_request": ["action_check","item_control","canon_update"],
    "action": ["action_check","combat","end_section","item_control","canon_update"],
    "talk": ["action_check","combat","end_section","item_control","canon_update"],
    "gm_query": ["action_check","combat","end_section","item_control","canon_update"],
    "other": ["action_check","combat","end_section","item_control","canon_update"],
}

INTENT_MODEL_CONFIG = {
    "action": {"model_level": "high", "max_tokens": 20000},
    "talk": {"model_level": "high", "max_tokens": 20000},
    "info_request": {"model_level": "high", "max_tokens": 20000},
    "gm_query": {"model_level": "high", "max_tokens": 10000},
    "system": {"model_level": "medium", "max_tokens": 5000},
    "other": {"model_level": "high", "max_tokens": 15000}
}


class IntentHandler:
    def __init__(self, ctx, state, flags, convlog):
        self.ctx = ctx
        self.state = state
        self.flags = flags
        self.convlog = convlog

    def handle(self, label: str, player_input: str) -> str:
        if label == "chapter_intro":
            return self._handle_intro("chapter")
        elif label == "section_intro":
            return self._handle_intro("section")
            
        elif label == "post_check_description":
            return self._handle_post_check_description()
        
        elif label == "post_combat_description":
            return self._handle_post_combat_description()

        #elif self.state.scene == "transition":
        #    return self._handle_transition(label, player_input)

        elif self.state.scene == "exploration":
            return self._handle_exploration(label, player_input)
        
        elif self.state.scene != "exploration":
            print(f"[WARN] Scene '{self.state.scene}' は exploration にフォールバックされました")
            return self._handle_exploration(label, player_input)
        
        else:
            raise NotImplementedError(f"Scene type '{self.scene}' は未実装です")
            
    def _handle_intro(self, kind: str) -> str:
        wid = self.state.worldview_id 
        sid = self.state.session_id   
        chapter = self.state.chapter
        section = self.state.section
        section_idx = section - 1

        # plan.json（導入文）と scenario.json（章概要）を読む
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

        # 導入用命令文（system prompt の冒頭）
        if kind == "chapter":
            if chapter == 1:
                instruction = (
                    "あなたはTRPGのゲームマスターです。\n"
                    "これは物語の第一章の導入です。物語の始まりとして、舞台や背景、PCがこの物語に関わるきっかけを"
                    "臨場感ある導入で描写してください。読者が物語世界に引き込まれるように、情景・空気感・緊張感をラノベ風に描いてください。\n"
                    "全文で1000字程度で、最後にPCが何をするか選べるような直後の行動案を「行動案：1) ～ 2) ～」の形式で2～3個提示してください。1つの行動案ごとに改行し、番号ごとに別行にしてください。\n"
                    "プレイヤーに提示する文章は、**わかりやすいようあまり固有名詞を使わず（使うときは十分説明付きで）**、ラノベ風の三人称・地の文で常体にしてください。描写はかっこつけず、わかりやすさを優先して説明してください。\n"
                    "基本的に、まずはPCの日常の描写を行い、次にシナリオ、章、セクションの目的のうち、一番自然に向かうことのできる目的へ進むことになるきっかけを描写し、行動案で誘導することを推奨します。"
                )
            else:
                instruction = (
                    "あなたはTRPGのゲームマスターです。\n"
                    "以下の情報と会話履歴を参考に、新たに始まる章の導入描写を500字程度で提示してください。\n"
                    "プレイヤーキャラクターが今現在どこにいてどのような状況なのかを、具体的に描写してください。\n"
                    "プレイヤーキャラクターがこれから何をすれば良いのかが自然とわかるように、具体的な背景と、直後の行動案を「行動案：1) ～ 2) ～」の形式で2～3個提示してください。1つの行動案ごとに改行し、番号ごとに別行にしてください。\n"
                    "プレイヤーに提示する文章は、**わかりやすいようあまり固有名詞を使わず（使うときは十分説明付きで）**、ラノベ風の三人称・地の文で常体にしてください。描写はかっこつけず、わかりやすさを優先して説明してください。"
                )
        elif kind == "section":
            instruction = (
                "あなたはTRPGのゲームマスターです。\n"
                "以下の情報と会話履歴を参考に、セクションの導入描写を300字程度で提示してください。\n"
                "直前の描写と自然につながるようにし、プレイヤーキャラクターが今現在どこにいてどのような状況なのかを、具体的に描写してください。\\n"
                "プレイヤーキャラクターがこれから何をすれば良いのかが自然とわかるように、具体的な背景と、直後の行動案を「行動案：1) ～ 2) ～」の形式で2～3個提示してください。1つの行動案ごとに改行し、番号ごとに別行にしてください。\n"
                "プレイヤーに提示する文章は、**わかりやすいようあまり固有名詞を使わず（使うときは十分説明付きで）**、ラノベ風の三人称・地の文で常体にしてください。描写はかっこつけず、わかりやすさを優先して説明してください。"
            )

        if overview:
            instruction += f"\n\nこの章の概要: {overview}"
        if intro:
            instruction += f"\nセクションの導入情報（必ず参考にしてください）: {intro}"

        pre_keys = ["scenario","worldview", "character", "nouns", "canon", "plan"]
        for key in pre_keys:
            snippet = self._render_pre_snippet(key)
            if snippet.strip():
                instruction += "\n\n" + snippet

        # 会話履歴込みでAIへ送信
        messages = [{"role": "system", "content": instruction}]
        messages += self.convlog.get_slim()

        response = self.ctx.engine.chat(
            messages=messages,
            caller_name=f"IntentHandler:{kind}_intro",
            model_level="Very_high",
            max_tokens=20000
        )

        self.convlog.append("system", response)
        return response


    def _handle_exploration(self, label: str, player_input: str) -> str:
        base = INTENT_PROMPTS.get(label, INTENT_PROMPTS["other"])
        pre_keys = PRE_SNIPPET_KEYS_MAP.get(label, [])
        pre_extra = "\n\n".join(self._render_pre_snippet(k) for k in pre_keys)

        snippets = INTENT_SNIPPETS_MAP.get(label, [])
        extra = "\n\n".join(PROMPT_SNIPPETS[key] for key in snippets)
        # ここから追加
        wid = self.state.worldview_id
        sid = self.state.session_id
        chapter = self.state.chapter
        section_idx = self.state.section - 1

        scenario_path = get_data_path(
            f"worlds/{wid}/sessions/{sid}/scenario.json"
        )
        plan_path = get_data_path(
            f"worlds/{wid}/sessions/{sid}/chapters/chapter_{chapter:02}/plan.json"
        )

        is_final_chapter = False
        is_latter_half = False

        if scenario_path.exists():
            with open(scenario_path, encoding="utf-8") as f:
                scenario = json.load(f)
            chapters = scenario.get("draft", {}).get("chapters", [])
            if 0 < chapter <= len(chapters):
                is_final_chapter = (chapter == len(chapters))

        if plan_path.exists():
            with open(plan_path, encoding="utf-8") as f:
                plan = json.load(f)
            flow = plan.get("flow", [])
            if section_idx >= len(flow) // 2:
                is_latter_half = True

        goal_text = ""
        if plan_path.exists():
            with open(plan_path, encoding="utf-8") as f:
                plan = json.load(f)
            flow = plan.get("flow", [])
            current = flow[section_idx] if 0 <= section_idx < len(flow) else {}
            goal_text = current.get("goal", "")

        system_prompt = COMMON_PROMPT
        if pre_extra:
            system_prompt += "\n\n" + pre_extra
        system_prompt += "\n\n" + base
        if extra:
            system_prompt += "\n\n" + extra

        # 最終章かつ後半セクションなら追記
        if is_final_chapter and is_latter_half:
            system_prompt += (
                "\n\n【特記事項】このセクションは物語の最終章の後半部分です。"
                "クライマックス感や結末への盛り上がりを意識して描写してください。"
            )

        messages = [{"role": "system", "content": system_prompt}]
        messages += self.convlog.get_slim()
        if label == "action" and goal_text:  
            goal_instruction = (
                f"\n【システム】このセクションの目的: {goal_text}\n"
                "※この目的をすべて満たした場合、話に一旦の区切りをつけつつ出力の最後に必ず[end_section]を単独の行で書き、セクションを終了して次のセクションを進んでください。\n"
                "※このとき、行為判定[action_check]や戦闘判定[combat_start]、行動案の提示を**絶対にしないでください**。\n"
                "※一つのセクションが短くなりすぎないようにしてください。\n"
                "※未達成の場合は[end_section]を書かないでください。"
            )
            messages.append({"role": "user", "content": player_input.strip() + goal_instruction})
        else:
            messages.append({"role": "user", "content": player_input.strip()})



        config = INTENT_MODEL_CONFIG.get(label, {"model_level": "medium", "max_tokens": 3000})

        response = self.ctx.engine.chat(
            messages=messages,
            caller_name=f"IntentHandler:{label}",
            model_level=config["model_level"],
            max_tokens=config["max_tokens"]
        )

        self.convlog.append("user", player_input)
        self.convlog.append("system", response)

        return response

    def _render_pre_snippet(self, key: str) -> str:
        wid = self.state.worldview_id
        sid = self.state.session_id
        chapter = self.state.chapter

        if key == "scenario":

            scenario_path = get_data_path(f"worlds/{wid}/sessions/{sid}/scenario.json")
            theme = tone = style = "（未設定）"
            if scenario_path.exists():
                with open(scenario_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("meta", {})
                theme = meta.get("theme", theme)
                tone = meta.get("tone", tone)
                style = meta.get("style", style)

            return PRE_PROMPT_SNIPPETS["scenario"].format(
                theme=theme,
                tone=tone,
                style=style
            )

        elif key == "worldview":
            worldview = self.ctx.worldview_mgr.get_entry_by_id(wid) or {}
            long_desc = worldview.get("long_description") or worldview.get("description", "")
            tone = worldview.get("tone", "")
            genre = worldview.get("genre", "")
            
            # 追加情報組み立て
            extra_info = []
            if genre:
                extra_info.append(f"ジャンル: {genre}")
            if tone:
                extra_info.append(f"トーン: {tone}")
            
            # PRE_PROMPT_SNIPPETS に渡す文章
            full_desc = long_desc.strip()
            if extra_info:
                full_desc += "\n" + " / ".join(extra_info)

            return PRE_PROMPT_SNIPPETS["worldview"].format(worldview=full_desc)


        elif key == "character":
            session = self.ctx.session_mgr.get_entry_by_id(sid)
            pcid = session.get("player_character")
            self.ctx.character_mgr.set_worldview_id(wid)
            char = self.ctx.character_mgr.load_character_file(pcid)
            name = char.get("name", "？？？")
            level = char.get("level", "?")
            background = char.get("background", "不明")
            items = char.get("items", [])
            checks = char.get("checks", {})

            text = f"{name}（レベル{level}）\n背景（あくまで参考に　進行の流れはシナリオ設定優先で）：{background}"

            if items:
                item_lines = [f"- {item}" if isinstance(item, str) else f"- {item.get('name', '')}" for item in items]
                text += "\n所持アイテム:\n" + "\n".join(item_lines)
            if checks:
                skill_lines = [f"- {k}：+{v}" for k, v in checks.items()]
                text += "\nスキル:\n" + "\n".join(skill_lines)

            return PRE_PROMPT_SNIPPETS["character"].format(character=text.strip())
        
        elif key == "nouns":
            self.ctx.nouns_mgr.set_worldview_id(wid)
            nouns = self.ctx.nouns_mgr.entries
            lines = [f"- {n.get('name', '')}：{n.get('description', '')}" for n in nouns]
            return PRE_PROMPT_SNIPPETS["nouns"].format(nouns="\n".join(lines))

        elif key == "canon":
            # 置き換え後実装
            self.ctx.canon_mgr.set_context(wid, sid)
            canon = self.ctx.canon_mgr.list_entries() if hasattr(self.ctx.canon_mgr, "list_entries") else self.ctx.canon_mgr.entries

            lines = []
            for entry in canon:
                name = entry.get("name", "")
                typ = entry.get("type", "")
                notes = entry.get("notes", "")

                lines.append(f"- {name}（{typ}）")
                if notes:
                    lines.append(f"  概要: {notes}")

                history = entry.get("history", [])
                if history:
                    lines.append("  履歴:")
                    for h in history:
                        ch = h.get("chapter", "?")
                        text = h.get("text", "")
                        label = "初期設定" if (isinstance(ch, int) and ch == 0) else f"第{ch}章"
                        lines.append(f"    - {label}: {text}")
            lines.append("")
            return PRE_PROMPT_SNIPPETS["canon"].format(canon="\n".join(lines))


        elif key == "plan":
            plan_path = get_data_path(
                f"worlds/{wid}/sessions/{sid}/chapters/chapter_{chapter:02}/plan.json"
            )
            scenario_path = get_data_path(
                f"worlds/{wid}/sessions/{sid}/scenario.json"
            )

            # --- scenario.json 読み込み ---
            scenario_goal = ""
            chapter_goal = ""
            overviews = []
            if scenario_path.exists():
                with open(scenario_path, encoding="utf-8") as f:
                    scenario = json.load(f)

                draft = scenario.get("draft", {})
                scenario_goal = draft.get("goal", "").strip()
                overviews = draft.get("chapters", [])

                if 0 <= (chapter - 1) < len(overviews):
                    chapter_goal = overviews[chapter - 1].get("goal", "").strip()

            # --- plan.json 読み込み ---
            if plan_path.exists():
                with open(plan_path, encoding="utf-8") as f:
                    plan = json.load(f)
            else:
                plan = {}

            title = plan.get("title", "")
            flow = plan.get("flow", [])

            section_idx = self.state.section - 1

            # flow全体を一覧化（現在セクションを明示）
            flow_lines = []
            for i, sec in enumerate(flow, 1):
                scene = sec.get("scene", "")
                goal = sec.get("goal", "")
                if i - 1 == section_idx:
                    flow_lines.append(f"▶ 現在のセクション: 第{i}セクション - {scene} / 目的: {goal}")
                else:
                    flow_lines.append(f"  第{i}セクション - {scene} / 目的: {goal}")

            # 表示組み立て
            lines = []
            if scenario_goal:
                lines.append(f"【シナリオ全体の目的】{scenario_goal}")
            if title:
                lines.append(f"章タイトル: {title}")
            if chapter_goal:
                lines.append(f"【この章の目的】{chapter_goal}")
            lines.append("この章の全セクション構成（▶は現在位置）:")
            lines.extend(flow_lines)

            # 次の章 or 最終章の情報
            if chapter < len(overviews):
                next_chap = overviews[chapter]  # 次章はlist上はchapter index（0基準）
                next_overview = next_chap.get("overview", "").strip()
                if next_overview:
                    lines.append(f"次の章の展開予告: {next_overview}")
            else:
                lines.append("この章が最終章です。ここで物語は終わります。")

            return PRE_PROMPT_SNIPPETS["plan"].format(plan="\n".join(lines))




        return ""

    def _handle_post_check_description(self) -> str:
        system_prompt = (
            "あなたはソロTRPGの進行役（GM）を務めるAIです。\n"
            "PCが直前に行った行為判定の結果を踏まえ、特にPCの置かれている状況の明記に気をつけ、"
            "その行動が物語にどのような影響を与え、どのようにシナリオが進行したかを、おおよそ300字程度で、雰囲気よりわかりやすさ優先で、ライトノベルに使われる程度の簡単な語彙で描写してください。\n"
            "プレイヤーに提示する文章は、三人称・地の文で常体にしてください。\n\n"

            "プレイヤーの入力から判定結果を受け取り、"
            "『その結果によって起こった出来事』や"
            "『状況の変化』『登場人物の反応』『環境の変化』などをそれらしく描写してください。\n"
            "判定に成功している場合は、シナリオをGMメモに従って**大きく**進行させてください。\n"
            "判定に失敗している場合は、それが必須であるならリカバリを要求する描写とし、必須でないならその機会を失った描写としてください。\n"
            "行為判定には出目や補正値に応じた結果の“質”があります。以下の分類に基づいて、描写のトーンを調整してください：\n"
            "- 【クリティカル】（出目12）：劇的に有利な展開や幸運な状況を描写してください。直接関わりのないその後の展開も有利にしてください。\n"
            "- 【ファンブル】（出目2）：予期せぬトラブルや危機的な事態、あるいは明確な失策を描写してください。直接関わりのないその後の展開も不利にしてください。\n"
            "- 【成功（ギリギリ）】：達成値が目標値と同じか1だけ上回った場合、慎重さや緊張感を反映してください。\n"
            "- 【成功（余裕あり）】：達成値が目標値を大きく超えていた場合、余裕のある鮮やかな成功を描いてください。\n"
            "- 【失敗（惜しい）】：目標値にあと一歩届かない場合、手応えはあったが失敗したという印象を描いてください。\n"
            "- 【完全な失敗】：大きく目標に届かなかった場合は、失敗による問題や今後の困難に焦点を当ててください。\n"
            "ただし、これらの質の表現は描写のみで行い、達成値や目標値、クリティカル、ファンブル等の**メタな表現**は決して使わないでください。\n\n"

            "どのような形でも成功したなら、**シナリオを大きく進行させてください。** 目安としては、1セクションに行為判定3回です。\n\n"
            "プレイヤーキャラクターは物語の途中で決して死亡しません。\n"
            "重大な失敗によって目標を達成できなくなることはありますが、途中でキャラクターが死ぬ展開は避けてください。\n"
            "ただしシナリオの結末（最終セクション）においてのみ、プレイヤーの選択や物語の必然性に基づいて、"
            "キャラクターが死亡するという結末を描くことは許容されます。"
        )


        # 状況把握用の pre_snippet を付ける
        pre_keys = ["scenario","worldview", "character", "nouns", "canon", "plan"]
        pre_extra = "\n\n".join(self._render_pre_snippet(k) for k in pre_keys)

        if pre_extra:
            system_prompt += "\n\n" + pre_extra

        messages = [{"role": "system", "content": system_prompt}]
        messages += self.convlog.get_slim()

        response = self.ctx.engine.chat(
            messages=messages,
            caller_name="IntentHandler:post_check_description",
            model_level="high",
            max_tokens=20000,
        )

        self.convlog.append("system", response)

        return response

    def _handle_post_combat_description(self) -> str:
        system_prompt = (
            "あなたはソロTRPGの進行役（GM）を務めるAIです。\n"
            "プレイヤーキャラクターが直前に行った戦闘判定の結果を踏まえ、特に**PCの置かれている状況の明記**に気をつけ"
            "その戦闘行動が物語にどのような影響を与えたかを、おおよそ300字程度で、雰囲気よりわかりやすさ優先で、ライトノベルに使われる程度の簡単な語彙で描写してください。\n"
            "プレイヤーに提示する文章は、三人称・地の文で常体にしてください。\n\n"

            "プレイヤーの入力から判定結果を受け取り、\n"
            "・その戦法が成功または失敗したことによる敵の反応や状況の変化\n"
            "・戦況の推移や環境の変化\n"
            "・他の登場人物の反応\n"
            "などをそれらしく描写してください。\n\n"

            "※この戦闘判定は、最大で2回まで繰り返されます。\n"
            "基本的には1回で戦闘が終了しても構いませんが、\n"
            "シナリオの最終局面・強敵との戦闘・達成値が微妙な場合など、\n"
            "戦闘の継続が自然であると判断される場合は、\n"
            "戦場の描写や敵の動きを含めて、戦闘が続いていることを明確に示してください。\n\n"

            "戦闘が終了した場合は、その余波や勝利・敗北の雰囲気を描写し、\n"
            "必要に応じてシナリオを進行させ、\n"
            "プレイヤーがこれから何をすれば良いのかが自然とわかるよう、\n"
            "具体的な背景や次の行動の選択肢となるような情報も含めてください。\n\n"

            "※戦闘判定には明確な「目標値」が存在しないため、「成功」または「失敗」の判定はAIで判断してください。\n"
            "判定の結果（出目やボーナスの合計値）を参考にして、次のように判定してください：\n"
            "- 達成値が12以上：基本的に「成功」と見なして構いません。\n"
            "- 達成値が8未満：基本的に「失敗」と見なして構いません。\n"
            "- 8〜11の範囲：敵の強さ、状況や戦法の質によって柔軟に判断してください（例：ギリギリ逃げ切った、一矢報いたなど）。\n"
            "- 出目が12（=6+6）の場合は【クリティカル】：無条件成功。その後の展開も有利に。\n"
            "- 出目が2（=1+1）の場合は【ファンブル】：原則失敗（ただし敵が圧倒的に弱いなど特例時は除く）。\n\n"

            "描写のトーンは、以下の判定結果に応じて調整してください：\n"
            "- 【クリティカル】：鮮やかな勝利、敵の動揺、ドラマティックな展開など。その後の展開も有利に。\n"
            "- 【ファンブル】：重大なミス、危機的状況、奇妙なトラブルなど。力量差がない限り基本は敗北。\n"
            "- 【成功】：プレイヤーの戦法がうまくいったことを描写。\n"
            "- 【失敗】：原則として敗北。ただし、戦闘継続が自然な場合はその余地を残した描写も可。\n"
            "ただし、これらの質の表現は描写のみで行い、達成値や判定結果、クリティカル、ファンブル等の**メタな表現**は決して使わないでください。\n\n"

            "プレイヤーキャラクターは物語の途中で絶対に死亡しませんが、\n"
            "負傷したり、戦況が不利になる描写は許容されます。\n\n"
            "また、キャラクターの『レベル』に応じた力量差を考慮してください。\n"
            "以下の基準を参考に、敵との実力差が大きい場合は判定結果に関わらず、\n"
            "戦闘の結果や描写に違和感が出ないように調整してください：\n\n"
            "0：一般人（非戦闘員）\n"
            "1〜3：初心者〜見習い冒険者\n"
            "4〜6：熟練者クラス（一人前）\n"
            "7〜10：超人的な存在\n"
            "11〜13：伝説・神話級の英雄\n"
            "14〜15：神や精霊に匹敵する存在\n\n"
            "たとえば、レベル7以上のキャラクターが相手にするのが単なるゴロツキであれば、\n"
            "出目が悪くても圧倒的に制圧する展開が自然です。\n"
            "ですが逆に、低レベルのキャラが強敵に挑む場合は、成功した場合は十分な決定打を与えても構いません。\n"
        )

        pre_keys = ["scenario","worldview", "character", "nouns", "canon", "plan"]
        pre_extra = "\n\n".join(self._render_pre_snippet(k) for k in pre_keys)
        if pre_extra:
            system_prompt += "\n\n" + pre_extra

        messages = [{"role": "system", "content": system_prompt}]
        messages += self.convlog.get_slim()

        response = self.ctx.engine.chat(
            messages=messages,
            caller_name="IntentHandler:post_combat_description",
            model_level="high",
            max_tokens=20000,
        )

        self.convlog.append("system", response)
        return response
