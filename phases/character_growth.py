import unicodedata
import copy
from infra.path_helper import get_data_path

# 1回の成長フェーズで新規に支給されるポイント（好みで調整OK）
GROWTH_POOL_PER_PHASE = 6

class CharacterGrowth:
    def __init__(self, ctx, progress_info):
        self.ctx = ctx
        self.progress_info = progress_info
        self.flags = progress_info.setdefault("flags", {})
        self.wid = self.flags.get("growth_worldview_id")
        self.pcid = self.flags.get("growth_character_id")

        self.char_mgr = ctx.character_mgr
        self.char_mgr.set_worldview_id(self.wid)
        self.character = self.char_mgr.load_character_file(self.pcid)
        self.engine = ctx.engine

        # スキル表示順＆説明（作成時と対応）
        self.skill_descriptions = {
            "探知": "五感を使って異常や隠されたものを見つけ出す。",
            "操身": "跳ぶ・登る・避けるなど、身体を使った動作全般。",
            "剛力": "重い物を動かす、破壊する、力で突破する。",
            "知性": "知識や論理思考によって物事を理解・分析する。",
            "直感": "違和感や正解を感覚的に見抜く。",
            "隠形": "姿や痕跡を隠し、気づかれずに行動する。",
            "看破": "嘘や偽りを見抜く。",
            "技巧": "鍵開けや罠の解除、道具の精密な操作など。",
            "説得": "言葉や態度で相手を動かす・納得させる。",
            "意志": "精神的影響に抗い、決して心折れず自我を保つ。",
            "強靭": "毒や病気、苦痛や疲労に耐える身体的抵抗力。",
            "希望": "???",
        }

    #==================================================
    # ハンドラ
    #==================================================
    def handle(self, input_text: str) -> tuple[dict, str]:
        step = self.progress_info.get("step", 0)

        match step:
            case 0:   return self._step_intro()
            case 10:  return self._step_show_level_info()
            case 11:  return self._step_level_up(input_text)

            # ← ここから割り振り式に変更
            case 20:  return self._start_skill_distribution()
            case 21:  return self._handle_skill_distribution(input_text)
            case 22:  return self._confirm_skill_distribution()
            case 23:  return self._finalize_skill_distribution(input_text)

            case 30:  return self._step_show_summary_proposal()
            case 31:  return self._step_history_confirm(input_text)
            case 32:  return self._step_history_manual_input(input_text)
            case 100: return self._step_finalize()
            case _:   return self._fail("不正なステップです。")

    #==================================================
    # イントロ〜レベル
    #==================================================
    def _step_intro(self) -> tuple[dict, str]:
        self.progress_info["step"] = 10
        self.progress_info["auto_continue"] = True
        return self.progress_info, f"キャラクター『{self.character.get('name', '無名')}』は物語を通じて成長しました。\n\n"

    def _step_show_level_info(self) -> tuple[dict, str]:
        self.progress_info["step"] = 11
        level = self.character.get("level", 0)
        return self.progress_info, (
            f"現在のレベル: {level}\n"
            "レベルは戦闘能力の指標で、以下のような目安です：\n"
            "0：一般人（非戦闘員）\n"
            "1〜3：初心者〜見習い冒険者\n"
            "4〜6：熟練者クラス（一人前）\n"
            "7〜10：超人的な存在\n"
            "11〜13：伝説・神話級の英雄\n"
            "14〜15：神や精霊に匹敵する存在\n\n"
            "※レベルは主にシナリオのスケール調整に使用されます（難易度には影響しません）\n\n"
            "レベルを上げますか？\n"
            "1. 上げる\n"
            "2. そのままにする\n\n"
            "数字で入力してください。"
        )

    def _step_level_up(self, input_text: str) -> tuple[dict, str]:
        choice = unicodedata.normalize("NFKC", input_text.strip())
        level = self.character.get("level", 0)

        if choice == "1":
            level = min(level + 1, 15)
            self.character["level"] = level
            self.char_mgr.save_character_file(self.pcid, self.character)
            msg = f"レベルが {level} に上昇しました。\n\n"
        elif choice == "2":
            msg = "レベルは変更されませんでした。\n\n"
        else:
            self.progress_info["step"] = 11
            return self.progress_info, "[入力エラー] 1 または 2 を入力してください。"

        self.progress_info["step"] = 20
        self.progress_info["auto_continue"] = True
        return self.progress_info, msg

    #==================================================
    # ポイント割り振り（作成時と同じ操作UI）
    #==================================================
    def _init_growth_buffers(self):
        # 既存チェック
        base_checks = copy.deepcopy(self.character.get("checks", {}))
        # スキルが無い場合は全0で初期化（作成時リストに合わせる）
        if not base_checks:
            for k in self.skill_descriptions.keys():
                base_checks[k] = 0

        # ベースライン：この成長回で下回れない
        self.flags["_baseline_checks"] = copy.deepcopy(base_checks)
        # 編集中の現在値
        self.flags["_current_checks"] = copy.deepcopy(base_checks)

        # 成長ポイント：持ち越し＋今回支給
        carry = int(self.character.get("growth_pool", 0) or 0)
        self.flags["_carry_over"] = carry
        self.flags["_granted"] = GROWTH_POOL_PER_PHASE
        self.flags["_available_pool"] = carry + GROWTH_POOL_PER_PHASE

        # 現在の消費（デルタに対するコスト合計）
        self.flags["_spent"] = 0

    def _tri_cost(self, k: int) -> int:
        """+k のとき 1+...+k。-k は -k（返却）。kはデルタ単位。"""
        if k > 0:
            return sum(range(1, k + 1))
        if k < 0:
            return k  # 返却としてマイナス（合計に足すと減る）
        return 0

    def _calc_spent(self, cur: dict, base: dict) -> int:
        total = 0
        for name, base_v in base.items():
            dv = int(cur.get(name, 0)) - int(base_v)
            total += self._tri_cost(dv)
        return total

    def _render_distribution(self) -> str:
        base = self.flags["_baseline_checks"]
        cur  = self.flags["_current_checks"]
        ordered = [k for k in self.skill_descriptions.keys() if k in cur]

        spent = self._calc_spent(cur, base)
        self.flags["_spent"] = spent
        avail = self.flags["_available_pool"]
        remain = avail - spent

        lines = []
        lines.append("行為判定スキルの成長ポイントを割り振ります。")
        lines.append("作成時と同じ操作： 例）1 +1  /  11 -1  /  done\n")
        lines.append("【ルール】")
        lines.append("・この成長回の開始時点（ベースライン）よりも下げることはできません。")
        lines.append("・1上げるたびに 1pt、さらに上げると 2pt, 3pt…（三角コスト）。")
        lines.append("・今回内で下げた分は返却（プラス残高）として扱います。")
        lines.append(f"・未使用の残りは持ち越し（キャラの growth_pool に保存）。\n")

        lines.append("▼ スキル（左：現在 / 右：ベースライン）")
        for i, k in enumerate(ordered, 1):
            cur_v = int(cur.get(k, 0))
            base_v = int(base.get(k, 0))
            status = "（最大）" if cur_v >= 3 else ""
            lines.append(f"{i:>2}. 〈{k}〉：{cur_v:+d}  /  {base_v:+d} {status}")

        lines.append("")
        lines.append(f"▶ 今回支給: {self.flags['_granted']}pt, 持ち越し: {self.flags['_carry_over']}pt")
        lines.append(f"▶ 合計残高: {avail}pt   消費(三角計): {max(spent,0)}pt   残り: {remain}pt")
        lines.append("")
        lines.append("入力：番号（1〜）と増減（-3〜+3）を半角スペース区切りで。例）3 +2")
        lines.append("入力：done → 確認へ")
        return "\n".join(lines)

    def _start_skill_distribution(self) -> tuple[dict, str]:
        self._init_growth_buffers()
        self.progress_info["step"] = 21
        self.progress_info["auto_continue"] = False
        return self.progress_info, self._render_distribution()

    def _handle_skill_distribution(self, input_text: str) -> tuple[dict, str]:
        text = unicodedata.normalize("NFKC", input_text.strip())

        # 完了
        if text.lower() == "done":
            # 最終チェック：消費が残高を超えない
            spent = max(self.flags["_spent"], 0)
            avail = self.flags["_available_pool"]
            if spent > avail:
                self.progress_info["step"] = 21
                return self.progress_info, f"[エラー] 消費が残高を超えています（消費 {spent} / 残高 {avail}）。調整してください。"
            self.progress_info["step"] = 22
            self.progress_info["auto_continue"] = True
            return self.progress_info, "割り振りを確認します。"

        parts = text.split()
        if len(parts) != 2:
            self.progress_info["step"] = 21
            return self.progress_info, "[入力エラー] 操作形式が無効です。例：1 +1"

        try:
            index = int(parts[0])
            delta = int(parts[1])
        except ValueError:
            self.progress_info["step"] = 21
            return self.progress_info, "[入力エラー] 数字で指定してください。例：1 +1"

        cur  = self.flags["_current_checks"]
        base = self.flags["_baseline_checks"]
        names = [k for k in self.skill_descriptions.keys() if k in cur]

        if not (1 <= index <= len(names)):
            self.progress_info["step"] = 21
            return self.progress_info, "[入力エラー] スキル番号が範囲外です。"

        name = names[index - 1]
        before = int(cur[name])
        after  = before + delta

        # 上限下限（ゲーム全体のルール）
        if after < -3 or after > 3:
            self.progress_info["step"] = 21
            return self.progress_info, "[エラー] その変更は許可範囲（-3〜+3）を超えます。"

        # ベースライン割れ禁止
        if after < int(base[name]):
            self.progress_info["step"] = 21
            return self.progress_info, f"[エラー] 〈{name}〉はこの成長回のベースライン {base[name]:+d} を下回れません。"

        # 仮適用してコスト確認
        cur[name] = after
        spent = self._calc_spent(cur, base)
        avail = self.flags["_available_pool"]

        if spent > avail:
            # 戻す
            cur[name] = before
            self.flags["_spent"] = self._calc_spent(cur, base)
            self.progress_info["step"] = 21
            return self.progress_info, f"[エラー] 残高不足（消費 {spent} / 残高 {avail}）。"

        # 反映OK → 再描画
        self.flags["_spent"] = spent
        return self._redisplay_distribution()

    def _redisplay_distribution(self) -> tuple[dict, str]:
        self.progress_info["step"] = 21
        self.progress_info["auto_continue"] = False
        return self.progress_info, self._render_distribution()

    def _confirm_skill_distribution(self) -> tuple[dict, str]:
        cur  = self.flags["_current_checks"]
        base = self.flags["_baseline_checks"]
        spent = max(self._calc_spent(cur, base), 0)
        avail = self.flags["_available_pool"]
        remain = avail - spent

        lines = ["スキル成長の割り振りを確認してください：\n"]
        for name in self.skill_descriptions.keys():
            if name in cur:
                lines.append(f"- 〈{name}〉：{int(cur[name]):+d}（基準 {int(base[name]):+d}）")

        lines.extend([
            "",
            f"▶ 今回支給 {self.flags['_granted']}pt + 持ち越し {self.flags['_carry_over']}pt = 残高 {avail}pt",
            f"▶ 消費 {spent}pt → 残り {remain}pt（この残りは持ち越し保存）",
            "",
            "この内容で確定しますか？",
            "1. はい（保存）",
            "2. いいえ（割り振りをやり直す）"
        ])

        self.progress_info["step"] = 23
        self.progress_info["auto_continue"] = False
        return self.progress_info, "\n".join(lines)

    def _finalize_skill_distribution(self, input_text: str) -> tuple[dict, str]:
        choice = unicodedata.normalize("NFKC", input_text.strip())

        if choice == "2":
            self.progress_info["step"] = 21
            self.progress_info["auto_continue"] = True
            return self.progress_info, "割り振りをやり直します。"

        if choice != "1":
            self.progress_info["step"] = 23
            return self.progress_info, "[入力エラー] 1 または 2 を入力してください。"

        # 保存処理
        cur  = self.flags["_current_checks"]
        base = self.flags["_baseline_checks"]
        spent = max(self._calc_spent(cur, base), 0)
        avail = self.flags["_available_pool"]
        remain = avail - spent
        if remain < 0:
            # 念のため
            self.progress_info["step"] = 21
            return self.progress_info, "[エラー] 残高不足です。調整してください。"

        # キャラへ反映
        self.character["checks"] = copy.deepcopy(cur)
        # 残りを持ち越し保存
        self.character["growth_pool"] = int(remain)
        self.char_mgr.save_character_file(self.pcid, self.character)

        # 次へ（履歴作成フロー）
        self.progress_info["step"] = 30
        self.progress_info["auto_continue"] = True
        return self.progress_info, "成長を保存しました。次に要約履歴の作成へ進みます。"

    #==================================================
    # 履歴（既存ロジックを流用）
    #==================================================
    def _step_show_summary_proposal(self) -> tuple[dict, str]:
        history = self._generate_summary_history()
        if not history:
            self.progress_info["step"] = 100
            return self.progress_info, "履歴生成に失敗しました。"

        self.flags["_history_proposal"] = history
        self.progress_info["step"] = 31
        return self.progress_info, (
            f"要約された履歴候補：\n「{history['text']}」\n\n"
            "この内容を履歴に追加しますか？\n"
            "1. 追記する\n"
            "2. 修正して追記する（文章を自分で入力）\n"
            "3. 追記しない\n\n"
            "数字で入力してください。"
        )

    def _step_history_confirm(self, input_text: str) -> tuple[dict, str]:
        choice = unicodedata.normalize("NFKC", input_text.strip())

        if choice == "1":
            history = self.flags.pop("_history_proposal", None)
            if history:
                self.character.setdefault("history", []).append(history)
                self.char_mgr.save_character_file(self.pcid, self.character)
                self.progress_info["step"] = 100
                self.progress_info["auto_continue"] = True
                return self.progress_info, "キャラクターの履歴に成長記録を追加しました。"
            else:
                self.progress_info["step"] = 100
                self.progress_info["auto_continue"] = True
                return self.progress_info, "履歴データが見つかりませんでした。"

        elif choice == "2":
            self.progress_info["step"] = 32
            return self.progress_info, "修正後の履歴を一文で入力してください。"

        else:
            self.progress_info["step"] = 100
            self.progress_info["auto_continue"] = True
            return self.progress_info, "成長記録は追加されませんでした。"

    def _step_history_manual_input(self, input_text: str) -> tuple[dict, str]:
        text = unicodedata.normalize("NFKC", input_text.strip())
        if not text:
            self.progress_info["step"] = 32
            return self.progress_info, "[入力エラー] 空の履歴は追加できません。"

        history = {"text": text}
        self.character.setdefault("history", []).append(history)
        self.char_mgr.save_character_file(self.pcid, self.character)

        self.progress_info["step"] = 100
        self.progress_info["auto_continue"] = True
        return self.progress_info, "入力された内容を履歴に追加しました。"

    #==================================================
    # 終了
    #==================================================
    def _step_finalize(self) -> tuple[dict, str]:
        self.progress_info["phase"] = "prologue"
        self.progress_info["step"] = 0
        self.progress_info["flags"] = {}
        self.progress_info["auto_continue"] = True
        return self.progress_info, "キャラクター成長フェーズを終了します。"

    #==================================================
    # 既存の履歴生成ロジック
    #==================================================
    def _generate_summary_history(self) -> dict | None:
        sid = self.flags.get("growth_session_id")
        summary_path = get_data_path(f"worlds/{self.wid}/sessions/{sid}/summary.txt")
        if not summary_path.exists():
            return None

        summary_text = summary_path.read_text(encoding="utf-8").strip()
        if not summary_text:
            return None

        prompt = [
            {"role": "system", "content": "あなたはキャラクター記録の作成者です。以下のセッション要約をもとに、三人称視点から短く一文で記録を生成してください。"},
            {"role": "user", "content": summary_text}
        ]

        result = self.engine.chat(prompt, caller_name="GrowthHistory", model_level="high", max_tokens=5000)
        if not result.strip():
            return None

        return {"text": result.strip()}

    def _fail(self, message: str) -> tuple[dict, str]:
        self.progress_info["phase"] = "prologue"
        self.progress_info["step"] = 0
        return self.progress_info, f"[致命的エラー] {message}"
