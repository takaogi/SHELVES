# phases/scenario/combat.py
import re
import json

COMBAT_EVAL_SCHEMA = {
    "type": "json_schema",
    "name": "CombatEvaluation",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "strategy_score": {"type": "integer", "minimum": 0, "maximum": 2},
            "character_fit_score": {"type": "integer", "minimum": 0, "maximum": 2},
            "reason": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "string"},
                    "character_fit": {"type": "string"}
                },
                "required": ["strategy", "character_fit"],
                "additionalProperties": False
            },
            "action": {"type": "string"}
        },
        "required": ["strategy_score", "character_fit_score", "reason", "action"],
        "additionalProperties": False
    }
}

SKILL_WEIGHTS = {
    "探知": 4,     # 五感での索敵・異常察知など
    "操身": 8,    # 身体制御（回避・移動・軽業）
    "剛力": 10,    # 力による突破・破壊・押し返し
    "知性": 5,     # 戦略判断・仕組みの理解
    "直感": 9,     # 勘・危機回避・本能的判断
    "隠形": 7,     # 接近・回避・隠れなどの撹乱
    "看破": 6,     # 罠・偽装・敵の意図の看破
    "技巧": 7,     # 道具・罠・装置の操作
    "説得": 3,     # 威嚇・牽制など限定的用途
    "意志": 8,     # 精神的抵抗力・自己制御
    "強靭": 9,     # 肉体的耐性・痛みに耐える
    "希望": 10      # 勝負は時の運
}

class CombatHandler:
    def __init__(self, ctx, state, flags, convlog):
        self.ctx = ctx
        self.state = state
        self.flags = flags
        self.convlog = convlog  # ✅ 共有ログを使う


    def _compute_combat_score(self, checks: dict[str, int]) -> int:
        MULTIPLIER = {
            -3: -10, -2: -5, -1: -2,
             0:  0,  1:  2,  2:  6, 3: 14
        }

        score = 0
        for skill, level in checks.items():
            weight = SKILL_WEIGHTS.get(skill, 0)
            multiplier = MULTIPLIER.get(level, 0)
            score += weight * multiplier
        return score

    def _convert_score_to_bonus(self, score: int) -> int:
        if score >= 1200:
            return 7
        elif score >= 840:
            return 6
        elif score >= 540:
            return 5
        elif score >= 360:
            return 4
        elif score >= 240:
            return 3
        elif score >= 160:
            return 2
        elif score >= 80:
            return 1
        else:
            return 0

    def evaluate_strategy(self, player_input: str | None = None) -> str:
        """step=4011 → プレイヤー戦法の評価（構造化出力対応）"""
        is_revision = "combat_evaluation" in self.flags
        wid, sid = self.state.worldview_id, self.state.session_id

        # キャラクタ読込
        session = self.ctx.session_mgr.get_entry_by_id(sid)
        pcid = session.get("player_character")
        self.ctx.character_mgr.set_worldview_id(wid)
        self.char = self.ctx.character_mgr.load_character_file(pcid)

        # 会話ログ（戦闘前の状況説明）
        messages = self.convlog.get_slim()

        # スニペット
        pre_snippets = self._render_snippet_group()

        # ガイド（JSON例は出さない。形はスキーマで縛る）
        instruction = """
    あなたはソロTRPGの戦闘支援AIです。
    PCの戦法を評価し、以下の2軸で数値的ボーナスを決定してください。
    戦法の目的には、勝利のほかに無事での逃走も含み得ます。

    1. 戦法の有効性（strategy_score）：
    - 2 = 良策（状況に合って効果が高い）
    - 1 = 普通（妥当）
    - 0 = 愚策（効果が薄い／矛盾）

    2. キャラらしさ（character_fit_score）：
    - 2 = 非常にらしい（性格・信条・経歴に一致）
    - 1 = 違和感はない
    - 0 = 不自然（原理に反する）

    出力の各フィールド：
    - strategy_score: 0〜2 の整数
    - character_fit_score: 0〜2 の整数
    - reason.strategy / reason.character_fit: それぞれの理由（簡潔で具体的に）
    - action: 実際にPCが行う具体的な行動（1文）
    """

        # ユーザープロンプト
        if is_revision:
            prev = self.flags.get("combat_evaluation", {})
            strategy_score = prev.get("strategy_score", "?")
            fit_score = prev.get("character_fit_score", "?")
            reason_strategy = prev.get("reason", {}).get("strategy", "（不明）")
            reason_fit = prev.get("reason", {}).get("character_fit", "（不明）")
            action_prev = prev.get("action", "（不明）")

            user_prompt = (
                "前回の評価とプレイヤーの再提案を考慮し、"
                "戦法の有効性およびキャラ適合度を再評価してください。\n\n"
                f"前回の評価:\n"
                f"- 戦法: {action_prev}\n"
                f"- 有効性: {strategy_score}\n"
                f"- キャラ適合度: {fit_score}\n"
                f"- 理由（有効性）: {reason_strategy}\n"
                f"- 理由（らしさ）: {reason_fit}\n\n"
                f"再提案された戦法：{(player_input or '').strip() or '（発言なし）'}"
            )
        else:
            user_prompt = (
                f"プレイヤーの戦法：{(player_input or '').strip() or '（発言なし）'}\n"
                "これを評価し、指定されたフィールドだけを出力してください。"
            )

        all_messages = [
            {"role": "system", "content": instruction + "\n\n" + pre_snippets},
            *messages,
            {"role": "user", "content": user_prompt},
        ]

        # ★ Responses API 構造化出力
        try:
            parsed = self.ctx.engine.chat(
                messages=all_messages,
                caller_name="CombatHandler:evaluate_strategy",
                model_level="high",
                max_tokens=10000,
                schema=COMBAT_EVAL_SCHEMA
            )
            if not isinstance(parsed, dict):
                raise ValueError("invalid schema output")

        except Exception:
            return "AIの応答が解析できませんでした。もう一度お試しください。"

        # 戦法ボーナス
        parsed["bonus"] = parsed["strategy_score"] + parsed["character_fit_score"]

        # プレイヤーキャラのスキル構成から戦闘適性を算出
        safe_checks = {}
        for k, v in self.char.get("checks", {}).items():
            try:
                safe_checks[k] = int(v)
            except (ValueError, TypeError):
                safe_checks[k] = 0
        char_score = self._compute_combat_score(safe_checks)
        char_bonus = self._convert_score_to_bonus(char_score)

        # 合計ボーナス
        total_bonus = parsed["bonus"] + char_bonus

        # 記録
        parsed["char_score"] = char_score
        parsed["char_bonus"] = char_bonus
        parsed["total_bonus"] = total_bonus
        self.flags["combat_evaluation"] = parsed

        # ラベル整形
        def label(v, good, normal, bad):
            return good if v == 2 else normal if v == 1 else bad

        return (
            f"\n戦闘内容：{parsed['action']}\n"
            f"では、戦闘判定を行います。\n"
            f"戦法評価ボーナス：+{parsed['strategy_score']}（{label(parsed['strategy_score'], '良策', '普通', '愚策')}）"
            f" +{parsed['character_fit_score']}（{label(parsed['character_fit_score'], '非常にらしい', '違和感はない', '不自然')}）\n"
            f"キャラクター戦闘適性：+{char_bonus}（スコア: {char_score}）\n"
            f"―― 合計ボーナス：+{total_bonus}\n"
            f"評価理由：{parsed['reason']['strategy']} / {parsed['reason']['character_fit']}\n"
            f"よろしいですか？"
        )


    def _render_snippet_group(self) -> str:
        # キャラクター・世界観・状況の情報を連結
        wid = self.state.worldview_id
        char = self.char

        lines = []

        # キャラクター情報（ActionCheckと同様に取得）
        worldview = self.ctx.worldview_mgr.get_entry_by_id(wid)
        desc = worldview.get("long_description") or worldview.get("description", "")
        if desc:
            lines.append("【世界観】\n" + desc.strip())

        # 固有名詞
        self.ctx.nouns_mgr.set_worldview_id(wid)
        nouns = self.ctx.nouns_mgr.entries
        if nouns:
            noun_lines = []
            for n in nouns:
                name = n.get("name", "")
                typ = n.get("type", "")
                notes = n.get("notes", "")
                noun_lines.append(f"- {name}（{typ}）：{notes}")
            lines.append("\n## 世界観の固有名詞一覧:\n" + "\n".join(noun_lines))

        # カノン
        self.ctx.canon_mgr.set_context(wid, self.state.session_id)
        canon_entries = self.ctx.canon_mgr.entries
        if canon_entries:
            canon_lines = []
            for c in canon_entries:
                name = c.get("name", "")
                typ = c.get("type", "")
                notes = c.get("notes", "")
                canon_lines.append(f"- {name}（{typ}）：{notes}")
            lines.append("\n## これまでに確定したカノン:\n" + "\n".join(canon_lines))



        char_lines = [f"{char.get('name', '？？？')}（レベル{char.get('level', '?')}）"]
        for key in ("summary", "background", "personality", "physique", "abilities", "weaknesses", "beliefs", "items"):
            val = char.get(key)
            if not val:
                continue

            if key == "items":
                if isinstance(val, str):
                    # 万一旧仕様で単一文字列
                    char_lines.append(f"- {key}: {val}")
                elif isinstance(val, list):
                    item_lines = []
                    for item in val:
                        if isinstance(item, str):
                            # 旧仕様の文字列アイテム
                            item_lines.append(item)
                        elif isinstance(item, dict):
                            name = item.get("name", "")
                            count = item.get("count", 0)
                            desc = item.get("description", "")
                            if desc:
                                item_lines.append(f"{name} ×{count}：{desc}")
                            else:
                                item_lines.append(f"{name} ×{count}")
                    char_lines.append(f"- {key}: " + "、".join(item_lines))
            elif isinstance(val, list):
                # 旧仕様の配列型（items以外）
                joined = "、".join(val)
                char_lines.append(f"- {key}: {joined}")
            else:
                char_lines.append(f"- {key}: {val}")


        lines.append("【キャラクター】\n" + "\n".join(char_lines))


        return "\n\n".join(lines)

    def show_result(self, player_input: str) -> str:
        eval_result = self.flags.get("combat_evaluation")
        self.flags.pop("combat_evaluation", None)

        if not eval_result:
            return "戦闘評価データが見つかりません。"

        # 評価値の抽出
        action_label = eval_result.get("action", "？")
        strategy_score = eval_result.get("strategy_score", 0)
        fit_score = eval_result.get("character_fit_score", 0)
        char_bonus = eval_result.get("char_bonus", 0)
        total_bonus = eval_result.get("total_bonus", 0)
        reason_strategy = eval_result.get("reason", {}).get("strategy", "")
        reason_fit = eval_result.get("reason", {}).get("character_fit", "")

        # ダイス部分を抽出（5 + 3 = 8 形式）
        match = re.search(r"(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)", player_input)
        if not match:
            return "ダイスの出目を正しく読み取れませんでした。"

        d1, d2, raw_total = map(int, match.groups())
        final_total = d1 + d2 + total_bonus

        # クリティカル / ファンブル
        critical = (raw_total == 12)
        fumble = (raw_total == 2)

        if critical:
            result_text = "🎲 クリティカル！（自動成功）"
        elif fumble:
            result_text = "🎲 ファンブル！（自動失敗）"
        else:
            result_text = f"🎲 達成値: {final_total}"

        return (
            f"【戦闘判定 結果】\n"
            f"行動内容: {action_label}\n"
            f"出目: {d1} + {d2} = {raw_total}\n"
            f"ボーナス: +{total_bonus}\n"
            f"{result_text}\n\n"
            f"● 評価詳細：\n"
            f"- 戦法の有効性: +{strategy_score}\n"
            f"- キャラらしさ: +{fit_score}\n"
            f"- 戦闘適性: +{char_bonus}\n\n"
            f"● 評価理由：\n"
            f"- 有効性: {reason_strategy}\n"
            f"- らしさ: {reason_fit}\n"
        )
