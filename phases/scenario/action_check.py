# phases/scenario/action_check.py
import re
import json
from infra.path_helper import get_data_path

ACTION_CHECK_PLAN_SCHEMA = {
    "type": "json_schema",
    "name": "ActionCheckPlan",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "skill":  {"type": "string"},
            "target": {"type": "integer", "minimum": 2, "maximum": 13},
            "reason": {"type": "string"},
            "action": {"type": "string"}
        },
        "required": ["skill", "target", "reason", "action"],
        "additionalProperties": False
    }
}

class ActionCheck:
    def __init__(self, ctx, state, flags, convlog):
        self.ctx = ctx
        self.state = state
        self.flags = flags
        self.convlog = convlog


    def suggest_check(self,player_input: str | None = None) -> str:
        """step=3001 → AIによるスキル候補・目標値提案"""
        is_revision = "action_check_plan" in self.flags

        # 会話ログ取得
        messages = self.convlog.get_slim()

        # プレプロンプト構築
        pre_snippets = self._render_snippet_group()

        # チェック提案専用プロンプト
        instruction = """
あなたはソロTRPGの行為判定支援AIです。
以下は、行為判定処理用の情報です。

🔷 判定方式（基本ルール）：
- 2d6（6面ダイス2個）を振り、出目の合計を達成値とし、目標値以上なら成功として判定します。
- 基本の目標値は【6】。状況に応じてこれを上下させてください。最低は2、最大は13です。高いほど難度も高くなります。
- キャラクターが対応スキルを持っている場合、その値分だけ達成値を補正します（±両対応）。これは、目標値とは関係ないので考慮しないでください。
- 出目が目標値以上 → 成功、未満 → 失敗
- ただし、出目が 2（=1+1）の場合は目標値に関わらず「自動失敗（ファンブル）」
- 出目が 12（=6+6）の場合は無条件で「自動成功（クリティカル）」

🔷 スキル選定：
行為判定が必要な行動に対して、以下のスキル群から最適なものを1つ選び、候補として提示してください。

🎲 Prologue 行為判定スキル一覧（AI向け詳細定義）：

【スキル一覧（詳細定義）】
以下のいずれかから必ず選んでください。スキル名は〈〉で囲んで記述してください。
後述するキャラクター情報の取得スキルも参考にして、もっとも適しているものを適している方法で使用してください。

① 探知（たんち）  
定義：視覚・聴覚・嗅覚などの五感を使って、対象・異常・気配・物品などを探す行為。  
使用例：隠された扉を見つける、足音を聞き取る、血の匂いに気づく。  
備考：最も基本的な探索手段であり、プレイヤーから自発的に使用される頻度が高い。

② 操身（そうしん）  
定義：身体全体の動きを制御し、移動や姿勢を調整する能力。  
使用例：跳躍、登攀、転倒回避、静かに歩く、片足で立ち続ける。  
備考：回避や軽業も含まれるが、あくまで“移動・動作”の制御に関わる。

③ 剛力（ごうりき）  
定義：腕力に限らず、身体全体を使って物理的な力を発揮する能力。力の直接かかわる特殊能力の使用も含む。  
使用例：扉をこじ開ける、大岩を押す、敵を押し返す、鎖を引きちぎる。 力の直接かかわる特殊能力。  
備考：筋力系すべてに適用。破壊・運搬・突破のほか、重量耐性にも使える。

④ 知性（ちせい）  
定義：知識・論理思考・理解力などを用いて、物事を解釈・分析する能力。体系化された魔法の使用。
使用例：魔術的記号の解読、歴史的事実の想起、仕組みの理解、専門知識の活用。魔法系の特殊能力。 
備考：キャラクターの設定に応じて専門分野を定め、専門外の場合は補正を加えることができる。

⑤ 直感（ちょっかん）  
定義：論理や感覚に頼らず、本能的に“正しさ”を察知する能力。  
使用例：探知に失敗した後にもう一度正しい選択を引き当てたいとき、危険な選択肢を避けるとき。  
備考：原則として他の手段で情報取得に失敗した後に限定的に使用。判定難易度は高め。

⑥ 隠形（おんぎょう）  
定義：自身の姿や存在感、または物品・痕跡・気配などを他者から隠す技術。  
使用例：物陰に隠れる、音を立てずに移動する、盗品を隠す、足跡を消す。  
備考：主用途は「隠れる」だが、広義に秘匿・痕跡除去までカバー。

⑦ 看破（かんぱ）  
定義：偽り・仕掛け・演技・錯覚などの“作為的な偽装”を見抜く能力。  
使用例：嘘を見抜く、幻影の見破り、封印の偽装構造の発見。  
備考：AIから提示することは原則行わず、プレイヤーの意志による使用申告が前提。

⑧ 技巧（ぎこう）  
定義：手先の器用さ、技術的な精密操作能力を扱う技能。  
使用例：鍵開け、装置の解除、罠の設置・解除、緻密な細工。  
備考：道具・機械・罠などの物理操作に関わる判定すべてを担う。

⑨ 説得（せっとく）  
定義：相手の意志を言葉・態度・威圧・魅力などで動かす技能。  
使用例：交渉で条件を引き出す、相手を安心させる、恐喝する。  
備考：プレイヤーのRPの質や内容に応じて目標値が上下する。演技などもこのカテゴリに含む。

⑩ 意志（いし）  
定義：精神的干渉に耐える強さ、自己制御、信念の持続。体系化されていない魔法の使用。
使用例：催眠・混乱・恐怖への抵抗、士気の維持、精神的疲労の克服。体系化されていない魔法系の特殊能力。  
備考：戦闘以外でも、説得や支配に対する“拒否”として使われる。

⑪ 強靭（きょうじん）  
定義：肉体的な抵抗力・持久力・痛みに耐える力。  
使用例：毒・病気・疲労・継続ダメージへの耐性、拷問への耐久、重労働、力の直接かかわらない肉体系の特殊能力など。  
備考：意志と対になる身体版の“抵抗”能力。強さではなく耐える力。

⑫ 希望（きぼう）  
定義：全てが手詰まりになったとき、最後の一手として提示される判定。  
使用例：絶体絶命の状況でAIが明示的に提示。成功すれば状況が劇的に好転する。targetは8固定。reasonもactionも「？？？」で固定。
備考：シナリオでの目標が達成できなくなりそうなときに使用可能（連続での判定失敗や戦闘敗北後など）。通常の行動には使用不可。使用する際は直前のアシスタントからの入力で「〈希望〉による行為判定を行います。」と記述される。


🔷 期待する出力フィールド：
- skill: 使用するスキル名（〈〉なしの素の名称）
- target: 2〜13の整数。状況を考慮して設定。高いほど難度も高くなる。
- reason: その目標値にした根拠（環境・難易度・相手など）（1~2文で簡潔に）
- action: PCが実際に行う具体的な行動内容（1文で簡潔に）
"""

        if is_revision:
            plan = self.flags.get("action_check_plan", {})
            skill = plan.get("skill", "不明")
            target = plan.get("target", "?")
            reason = plan.get("reason", "なし")
            action = plan.get("action", "不明")

            user_prompt = (
                "前回の提案とプレイヤーからの希望を考慮し、"
                "スキル名・目標値・理由・行動内容を適切に見直して、"
                "フォーマットに従って出力してください。\n\n"
                f"前回の提案:\n"
                f"- スキル候補：〈{skill}〉\n"
                f"- 目標値：{target}\n"
                f"- 理由：{reason}\n"
                f"- 行動内容：{action}\n\n"
                f"プレイヤーの発言：{player_input.strip() or '（発言なし）'}"
            )

        else:
            user_prompt = (
                "これまでの流れから、最適なスキル名、目標値およびその設定理由と行う動作を"
                "フォーマットに従って出力してください。"
            )


        all_messages = [
            {"role": "system", "content": instruction + "\n\n" + pre_snippets},
            *messages,
            {"role": "user", "content": user_prompt}
        ]

        result = self.ctx.engine.chat(
            messages=all_messages,
            caller_name="ActionCheck:suggest",
            model_level="high",
            max_tokens = 10000,
            schema=ACTION_CHECK_PLAN_SCHEMA
        )
        try:
            result
            self.flags["action_check_plan"] = result
        except Exception:
            self.flags["action_check_plan"] = {"error": "parse_failed", "raw": result}
            return "AIの出力の解析に失敗しました。JSON形式で出力されなかった可能性があります。"


        return (
            f"\n行動内容：{result['action']}\n"
            f"では、行為判定を行います。スキル候補：〈{result['skill']}〉 目標値：{result['target']}\n"
            f"理由：{result['reason']}\n"
            f"よろしいですか？"
        )
        

    def _render_snippet_group(self) -> str:
        wid = self.state.worldview_id
        sid = self.state.session_id
        lines = []

        # worldview
        worldview = self.ctx.worldview_mgr.get_entry_by_id(wid)
        desc = worldview.get("long_description") or worldview.get("description", "")
        if desc:
            lines.append("【世界観】\n" + desc.strip())

        # character
        session = self.ctx.session_mgr.get_entry_by_id(sid)
        pcid = session.get("player_character")
        self.ctx.character_mgr.set_worldview_id(wid)
        char = self.ctx.character_mgr.load_character_file(pcid)

        FIELD_LABELS = {
            "name": "名前",
            "race": "種族",
            "age": "年齢",
            "gender": "性別",
            "origin": "出身",
            "occupation": "職業",
            "personality": "性格",
            "beliefs": "信条",
            "appearance": "容姿",
            "physique": "体格",
            "abilities": "能力",
            "weaknesses": "弱点",
            "likes": "好きなもの",
            "dislikes": "苦手なもの",
            "summary": "一言紹介",
            "background": "背景",
            "items": "所持品",
            "notes": "備考"
        }

        char_lines = [f"{char.get('name', '？？？')}（レベル{char.get('level', '?')}）"]

        for key, label in FIELD_LABELS.items():
            value = char.get(key)
            if not value:
                continue
            if key == "items":
                if isinstance(value, str):
                    # 万一まだ旧仕様で単一文字列の場合
                    char_lines.append(f"{label}:\n- {value}")
                elif isinstance(value, list):
                    # 新仕様: オブジェクト配列
                    item_lines = []
                    for item in value:
                        if isinstance(item, str):
                            # 旧仕様の文字列アイテム
                            item_lines.append(f"- {item}")
                        elif isinstance(item, dict):
                            name = item.get("name", "")
                            count = item.get("count", 0)
                            desc = item.get("description", "")
                            if desc:
                                item_lines.append(f"- {name} ×{count}：{desc}")
                            else:
                                item_lines.append(f"- {name} ×{count}")
                    char_lines.append(f"{label}:\n" + "\n".join(item_lines))
            elif key in {"summary", "background", "notes"}:
                char_lines.append(f"\n▼ {label}:\n{value}")
            else:
                char_lines.append(f"{label}: {value}")

        # 行為判定スキル（checks）
        checks = char.get("checks", {})
        if checks:
            check_lines = [f"- {k}：{v}" for k, v in checks.items()]
            char_lines.append("所持スキル:\n" + "\n".join(check_lines))

        lines.append("【キャラクター】\n" + "\n".join(char_lines))

        # nouns
        self.ctx.nouns_mgr.set_worldview_id(wid)
        nouns = self.ctx.nouns_mgr.entries
        if nouns:
            noun_lines = []
            for n in nouns:
                name = n.get("name", "")
                typ = n.get("type", "")
                notes = n.get("notes", "")
                noun_lines.append(f"- {name}（{typ}）")
                if notes:
                    noun_lines.append(f"  概要: {notes}")
            lines.append("【世界観固有名詞】\n" + "\n".join(noun_lines))

        # canon
        self.ctx.canon_mgr.set_context(wid, sid)
        canon = self.ctx.canon_mgr.list_entries() if hasattr(self.ctx.canon_mgr, "list_entries") else self.ctx.canon_mgr.entries
        if canon:
            canon_lines = []
            for entry in canon:
                name = entry.get("name", "")
                typ = entry.get("type", "")
                notes = entry.get("notes", "")
                canon_lines.append(f"- {name}（{typ}）")
                if notes:
                    canon_lines.append(f"  概要: {notes}")
            lines.append("【設定メモ】\n" + "\n".join(canon_lines))

        return "\n\n".join(lines)


    def show_result(self, player_input: str) -> str:
        plan = self.flags.get("action_check_plan", {})
        self.flags.pop("action_check_plan", None)

        # キャラクター情報の取得
        wid, sid = self.state.worldview_id, self.state.session_id
        session = self.ctx.session_mgr.get_entry_by_id(sid)
        pcid = session.get("player_character")
        self.ctx.character_mgr.set_worldview_id(wid)
        char = self.ctx.character_mgr.load_character_file(pcid)

        checks = {}
        for k, v in char.get("checks", {}).items():
            try:
                checks[k] = int(v)
            except (ValueError, TypeError):
                checks[k] = 0

        skill = plan.get("skill", "")
        target = int(plan.get("target", 6))
        action = plan.get("action", "")

        # ダイス部分を抽出
        match = re.search(r"(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)", player_input)
        if not match:
            return "ダイスの出目を正しく読み取れませんでした。"

        d1, d2, raw_total = map(int, match.groups())
        modifier = checks.get(skill, 0)
        total = d1 + d2 + modifier

        critical = (raw_total == 12)
        fumble = (raw_total == 2)

        if critical:
            success = True
            result_text = "🎲 クリティカル！（自動成功）"
        elif fumble:
            success = False
            result_text = "🎲 ファンブル！（自動失敗）"
        else:
            success = total >= target
            result_text = "🎲 判定成功！" if success else "🎲 判定失敗…"

        detail = (
            f"【行為判定 結果】\n"
            f"行動内容: {action}\n"
            f"目標値: {target}\n"
            f"出目: {d1} + {d2} = {d1 + d2}\n"
            f"スキル補正（〈{skill}〉）: {modifier:+}\n"
            f"→ 達成値: {total}\n\n"
            f"{result_text}\n"
        )

        return detail
