import unicodedata
from infra.path_helper import get_data_path

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

    def handle(self, input_text: str) -> tuple[dict, str]:
        step = self.progress_info.get("step", 0)

        match step:
            case 0: return self._step_intro()
            case 10: return self._step_show_level_info()
            case 11: return self._step_level_up(input_text)
            case 20: return self._step_show_skill_list()
            case 21: return self._step_skill_up(input_text)
            case 30: return self._step_show_summary_proposal()
            case 31: return self._step_history_confirm(input_text)
            case 32: return self._step_history_manual_input(input_text)
            case 100: return self._step_finalize()
            case _: return self._fail("不正なステップです。")

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

    def _step_show_skill_list(self) -> tuple[dict, str]:
        self.progress_info["step"] = 21
        return self.progress_info, self._render_skill_list()

    def _step_skill_up(self, input_text: str) -> tuple[dict, str]:
        choice = unicodedata.normalize("NFKC", input_text.strip())
        checks = self.character.setdefault("checks", {})
        skills = list(checks.keys())

        if choice in ["0", "スキップ", "成長しない", "いいえ", "なし", "やめる", ""] or not skills:
            self.progress_info["step"] = 30
            self.progress_info["auto_continue"] = True
            return self.progress_info, "能力値の成長はスキップされました。\n\n次に進みます。"

        try:
            index = int(choice) - 1
            skill = skills[index]
        except (ValueError, IndexError):
            self.progress_info["step"] = 21
            return self.progress_info, "[入力エラー] スキルを番号で選んでください。"

        value = int(checks.get(skill, 0))
        if value >= 3:
            self.progress_info["step"] = 21
            return self.progress_info, f"[入力エラー] 〈{skill}〉 はすでに最大値です（+3）。"

        checks[skill] = value + 1
        self.char_mgr.save_character_file(self.pcid, self.character)

        self.progress_info["step"] = 30
        self.progress_info["auto_continue"] = True
        return self.progress_info, f"〈{skill}〉 が {value + 1} に成長しました。\n\n次に進みます。"

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

    def _step_finalize(self) -> tuple[dict, str]:
        self.progress_info["phase"] = "prologue"
        self.progress_info["step"] = 0
        self.progress_info["flags"] = {}
        self.progress_info["auto_continue"] = True
        return self.progress_info, "キャラクター成長フェーズを終了します。"

    def _render_skill_list(self) -> str:
        checks = self.character.get("checks", {})
        if not checks:
            self.progress_info["auto_continue"] = True
            return "このキャラクターには成長可能なスキルがありません。"

        # 表示順を固定（skill_descriptionsにある順）
        ordered_skills = [s for s in self.skill_descriptions if s in checks]

        lines = ["次に、能力値を1つだけ成長できます。", "数字で選んでください："]
        for i, k in enumerate(ordered_skills, 1):
            v = int(checks.get(k, 0))
            status = "（最大）" if v >= 3 else ""
            desc = self.skill_descriptions.get(k, "")
            lines.append(f"{i}. 〈{k}〉：{v} {status}")
            if desc:
                lines.append(f"　　{desc}")
        lines.append("0. 成長しない")
        return "\n".join(lines)


    def _generate_summary_history(self) -> dict | None:
        sid = self.flags.get("growth_session_id")
        summary_path = get_data_path(f"worlds/{self.wid}/sessions/{sid}/summary.txt")
        if not summary_path.exists():
            return None

        summary_text = summary_path.read_text(encoding="utf-8").strip()
        if not summary_text:
            return None

        prompt = [
            {"role": "system", "content": "あなたはキャラクター記録の作成者です。以下のセッション要約をもとに、キャラクターの視点から短く一文で記録を生成してください。"},
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
