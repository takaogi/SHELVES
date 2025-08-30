# phases/scenario_handler.py
import json
import re
from json import JSONDecodeError


from infra.path_helper import get_data_path
from infra.logging import get_logger

from phases.scenario.state import ScenarioState
from phases.scenario.chapter_generator import ChapterGenerator
from phases.scenario.intent_router import classify_intent
from phases.scenario.intent_handler import IntentHandler
from phases.scenario.conversation_log import ConversationLog
from phases.scenario.command_handler import CommandHandler

class ScenarioHandler:
    def __init__(self, ctx: object, progress_info: dict, debug: bool = False):
        self.ctx = ctx
        self.progress_info = progress_info
        self.debug = debug
        self.flags = self.progress_info.setdefault("flags", {})
        self.log = get_logger("ScenarioHandler")

        self.wid = self.flags.get("worldview_id")
        self.sid = self.flags.get("id")

        self.state: ScenarioState | None = None

    def handle(self, player_input: str) -> tuple[dict, str]:
        self.flags = self.progress_info.setdefault("flags", {})
        step = self.progress_info.get("step", 0)

        match step:
            case 0:
                return self._session_start()
            case 100:
                return self._start_log_restore()
            case 101:
                return self._continue_log_restore()
            case 1000:
                return self._step_start_chapter()
            case 1100:
                return self._step_select_section()
            case 2000:
                return self._intent_router(player_input)
            case 2010:
                return self._intent_handler(player_input)
            case 3000:
                return self._handle_action_check_init()
            case 3001:
                return self._handle_action_check_suggest()
            case 3010:
                return self._handle_action_check_response(player_input)
            case 3021:
                return self._handle_action_check_show_result(player_input)
            case 3022:
                return self._handle_action_check_finalize()
            case 4000:
                return self._handle_combat_init()
            case 4001:
                return self._handle_combat_suggest(player_input)
            case 4010:
                return self._handle_combat_response(player_input)
            case 4021:
                return self._handle_combat_show_result(player_input)
            case 4022:
                return self._handle_combat_finalize()
            case 9990:
                return self._request_dice_roll()
            case 9999:
                return self._step_finalize_scenario()
            case _:
                return self._fail(f"未定義のステップです: {step}")

    def _session_start(self) -> tuple[dict, str]:
        sid = self.flags.get("id")
        wid = self.flags.get("worldview_id")
        if not sid or not wid:
            return self._fail("セッションまたは世界観のIDが不足しています。")

        self.state = ScenarioState(wid, sid)
        self.convlog = ConversationLog(wid, sid, ctx=self.ctx)


        if self.state.chapter == 0:
            self.progress_info["step"] = 1000  # 新規チャプター開始用の次ステップへ
            return self.progress_info, None
        else:
            self.progress_info["step"] = 100 # 中断シナリオ復元用の次ステップへ
            self.progress_info["auto_continue"] = True
            return self.progress_info, f"中断されたシナリオを再開します（第{self.state.chapter}章 - セクション{self.state.section}）"
        
    def _start_log_restore(self) -> tuple[dict, str]:
        self.state = ScenarioState(self.wid, self.sid)
        self.convlog = ConversationLog(self.wid, self.sid, ctx=self.ctx)

        self._slim_restore_index = 0
        self._slim_restore_msgs = self.convlog.get_slim()

        # 末尾がplayer/user単独なら除外（復元中断時など）
        if self._slim_restore_msgs and self._slim_restore_msgs[-1]["role"] in ("user", "player"):
            self._slim_restore_msgs.pop()

        self.progress_info["step"] = 101
        self.progress_info["auto_continue"] = True
        return self.progress_info, "ログの復元を行います..."

    def _continue_log_restore(self) -> tuple[dict, str]:
        self.progress_info["auto_continue"] = True
        self.progress_info["wait_seconds"] = 0
        if not hasattr(self, "_slim_restore_msgs"):
            self._slim_restore_index = 0
            self._slim_restore_msgs = self.convlog.get_slim()
            if self._slim_restore_msgs and self._slim_restore_msgs[-1]["role"] in ("user", "player"):
                self._slim_restore_msgs.pop()

        idx = self._slim_restore_index
        messages = self._slim_restore_msgs

        if idx >= len(messages):
            self.progress_info["step"] = 2000  # 本編フェーズへ
            self.progress_info["auto_continue"] = False
            return self.progress_info, "（ログ復元完了）"

        msg = messages[idx]
        self._slim_restore_index += 1

        role = msg.get("role", "")
        content = msg.get("content", "")

        if role in ("user", "player"):
            return self.progress_info, f"-- {content}"
        elif role == "summary":
            return self.progress_info, f"[要約] {content}"
        else:
            return self.progress_info, content
      
    def _step_start_chapter(self) -> tuple[dict, str]:
        # 章が1になるときを除き、ここで要約
        if getattr(self.state, "chapter", 0) != 0:
            if hasattr(self, "convlog") and self.convlog:
                try:
                    self.convlog.summarize_now()
                except Exception as e:
                    self.ctx.logger.warning(f"[ScenarioHandler] 章切り替え時の要約に失敗: {e}")
        
        self.state.chapter += 1
        self.state.section = 0
        chapter = self.state.chapter

        # シナリオの総チャプター数をチェック
        scenario_path = get_data_path(f"worlds/{self.wid}/sessions/{self.sid}/scenario.json")
        if not scenario_path.exists():
            return self._fail("scenario.json が存在しません")

        with open(scenario_path, encoding="utf-8") as f:
            scenario = json.load(f)

        chapters = scenario.get("draft", {}).get("chapters", [])
        if chapter > len(chapters):
            # 最終章を超えた → 終了ステップへ
            self.progress_info["step"] = 9999
            return self.progress_info, None

        # 通常の章生成
        generator = ChapterGenerator(self.ctx, self.wid, self.sid, chapter)
        plan = generator.generate()
        self.state.save()

        title = plan.get("title", "")
        heading = f"\n第{chapter}章「{title}」を開始します。\n" if title else f"\n第{chapter}章を開始します。\n"

        self.flags["intent"] = "chapter_intro"
        self.progress_info["step"] = 1100
        self.progress_info["auto_continue"] = True
        return self.progress_info, heading


    def _step_select_section(self) -> tuple[dict, str]:
        self.state.section += 1
        section = self.state.section

        plan_path = get_data_path(
            f"worlds/{self.wid}/sessions/{self.sid}/chapters/chapter_{self.state.chapter:02}/plan.json"
        )

        if not plan_path.exists():
            return self._fail(f"plan.json が見つかりません: {plan_path}")

        try:
            with open(plan_path, encoding="utf-8") as f:
                plan = json.load(f)
        except JSONDecodeError:
            return self._fail(f"plan.json が破損しています: {plan_path}")

        sections = plan.get("flow", [])
        if section > len(sections):
            self.progress_info["step"] = 1000  # 新チャプターへ
            return self.progress_info, None

        section_info = sections[section - 1]
        scene = section_info.get("scene", "exploration")

        self.state.scene = scene
        self.state.save()

        if self.flags.get("intent") != "chapter_intro":
            self.flags["intent"] = "section_intro"
        self.progress_info["step"] = 2000
        if self.flags.get("intent") == "chapter_intro":
            return self.progress_info, None
        self.progress_info["auto_continue"] = True
        return self.progress_info, "(セクション進行)"


    def _intent_router(self, player_input: str) -> tuple[dict, str]:
        # --- デバッグ専用コマンド（--debug 時のみ有効） ---
        if getattr(self, "debug", False):
            cmd = player_input.strip().lower()

            # 進行状況確認系
            if cmd == "status":
                state_info = [
                    "【デバッグ】現在の状態:",
                    f"- 章: {getattr(self.state, 'chapter', '?')} / セクション: {getattr(self.state, 'section', '?')}",
                    f"- シーン: {getattr(self.state, 'scene', '(不明)')}",
                    f"- Intent: {self.flags.get('intent', '(未設定)')}",
                    f"- Step: {self.progress_info.get('step', '(不明)')}"
                ]
                return self.progress_info, "\n".join(state_info)

            elif cmd == "flags":
                import json
                try:
                    flags_str = json.dumps(self.flags, ensure_ascii=False, indent=2)
                except Exception:
                    flags_str = str(self.flags)
                return self.progress_info, f"【デバッグ】Flags 内容:\n{flags_str}"

            # シナリオ終了
            if cmd == "end":
                self.progress_info["step"] = 9999
                self.progress_info["auto_continue"] = True
                return self.progress_info, "【デバッグ】シナリオ終了処理へ移行します。"

            # セクションスキップ
            elif cmd == "skipsec":
                self.progress_info["step"] = 1100
                self.progress_info["auto_continue"] = True
                return self.progress_info, "【デバッグ】現在のセクションをスキップしました。"

            # 章スキップ
            elif cmd == "skipchap":
                self.progress_info["step"] = 1000
                self.progress_info["auto_continue"] = True
                return self.progress_info, "【デバッグ】現在の章をスキップしました。"

            # 章・セクション移動
            elif cmd.startswith("goto "):
                try:
                    chap, sec = cmd.split()[1].split("-")
                    self.state.chapter = int(chap)
                    self.state.section = int(sec)
                    self.state.save()
                    self.progress_info["step"] = 2000
                    return self.progress_info, f"【デバッグ】第{chap}章 セクション{sec} へ移動しました。"
                except Exception:
                    return self.progress_info, "[デバッグ] goto コマンド形式: goto <章>-<セクション>"

        # --- 通常ルート ---
        if self.flags.get("intent") in ("section_intro", "chapter_intro"):
            self.progress_info["step"] = 2010
            return self.progress_info, None

        label = classify_intent(self.ctx, player_input, self.convlog)
        self.flags["intent"] = label
        self.log.debug(f"intent: {label}")

        if label == "invalid":
            return self._reject("発言が認識できませんでした。もう一度お願いします。")

        self.progress_info["step"] = 2010
        return self.progress_info, None

    def _intent_handler(self, player_input: str) -> tuple[dict, str]:
        if "intent" not in self.flags:
            return self._fail("意図が設定されていません")

        label = self.flags["intent"]
        handler = IntentHandler(self.ctx, self.state, self.flags, self.convlog)
        message = handler.handle(label, player_input)

        self.flags.pop("intent", None)

        return self._handle_intent_response(message)

    def _handle_intent_response(self, message: str) -> tuple[dict, str]:
        clean = message.strip()
        chapter = getattr(self.state, "chapter", 0)

        # 🔸[command: func(args)] の処理
        func_commands = re.findall(r"\[command:\s*(\w+)\((.*?)\)\s*\]", clean)
        parsed_commands = [
            (cmd, [arg.strip().strip("\"'") for arg in args.split(",") if arg.strip()])
            for cmd, args in func_commands
        ]
        
        if parsed_commands:
            executor = CommandHandler(self.ctx, self.wid, self.sid)
            for cmd, args in parsed_commands:
                executor.execute(cmd, args, chapter)

        # 🔸[end_section] など簡易コマンドの処理
        tag_commands = []
        pattern = re.compile(r"\[(\w+)\]")
        for match in pattern.finditer(clean):
            tag_commands.append(match.group(1))

        for cmd in tag_commands:
            if cmd == "end_section":
                self.progress_info["step"] = 1100
                self.progress_info["auto_continue"] = True
            elif cmd == "action_check":
                self.progress_info["step"] = 3000
                self.progress_info["auto_continue"] = True
            elif cmd == "combat_start":
                self.progress_info["step"] = 4000

        # 🔸すべてのタグを除去（command:も含む）
        clean = re.sub(r"\[command:\s*\w+\(.*?\)\s*\]", "", clean)
        clean = pattern.sub("", clean).strip()


        if "step" not in self.progress_info or self.progress_info["step"] == 2010:
            self.progress_info["step"] = 2000

        return self.progress_info, clean

    def _force_summarize_section(self):
        if hasattr(self, "convlog") and self.convlog:
            try:
                self.convlog.summarize_now()
            except Exception as e:
                print(f"[WARNING] summarize_now() failed: {e}")

    def _handle_action_check_init(self) -> tuple[dict, str | None]:
        self.flags.pop("action_check_plan", None)
        self.progress_info["step"] = 3001
        return self.progress_info, None

    def _handle_action_check_suggest(self) -> tuple[dict, str]:
        from phases.scenario.action_check import ActionCheck
        handler = ActionCheck(self.ctx, self.state, self.flags, self.convlog)
        message = handler.suggest_check()
        self.progress_info["step"] = 3010
        return self.progress_info, message

    def _handle_action_check_response(self, player_input: str) -> tuple[dict, str]:
        classification = self._classify_response(player_input)

        if classification == "yes":
            self.progress_info["step"] = 9990
            return self.progress_info, None

        elif classification == "suggest":
            from phases.scenario.action_check import ActionCheck
            handler = ActionCheck(self.ctx, self.state, self.flags, self.convlog)
            message = handler.suggest_check(player_input)
            return self.progress_info, message

        # 拒否や曖昧な返答
        return self._reject("無効な入力です。提案を受け入れるか、行動の修正を具体的に述べてください。")
    
    def _handle_action_check_show_result(self, player_input: str) -> tuple[dict, str]:
        from phases.scenario.action_check import ActionCheck
        handler = ActionCheck(self.ctx, self.state, self.flags, self.convlog)

        result_text = handler.show_result(player_input)
        self.convlog.append("user", result_text)

        self.progress_info["step"] = 3022
        self.progress_info["auto_continue"] = True
        return self.progress_info, result_text

    def _handle_action_check_finalize(self) -> tuple[dict, str]:
        self.flags["intent"] = "post_check_description"
        self.progress_info["step"] = 2010
        return self.progress_info, None

    def _handle_combat_init(self) -> tuple[dict, str | None]:
        self.flags.pop("combat_evaluation", None)
        self.progress_info["step"] = 4001
        return self.progress_info, None

    def _handle_combat_suggest(self, player_input: str) -> tuple[dict, str]:
        from phases.scenario.combat import CombatHandler
        handler = CombatHandler(self.ctx, self.state, self.flags, self.convlog)
        message = handler.evaluate_strategy(player_input)
        self.progress_info["step"] = 4010
        return self.progress_info, message

    def _handle_combat_response(self, player_input: str) -> tuple[dict, str]:
        classification = self._classify_response(player_input)

        if classification == "yes":
            self.progress_info["step"] = 9990
            return self.progress_info, None

        elif classification == "suggest":
            from phases.scenario.combat import CombatHandler
            handler = CombatHandler(self.ctx, self.state, self.flags, self.convlog)
            message = handler.evaluate_strategy(player_input)
            return self.progress_info, message

        return self._reject("無効な入力です。提案を受け入れるか、行動の修正を具体的に述べてください。")

    def _handle_combat_show_result(self, player_input: str) -> tuple[dict, str]:
        from phases.scenario.combat import CombatHandler
        handler = CombatHandler(self.ctx, self.state, self.flags, self.convlog)

        result_text = handler.show_result(player_input)
        self.convlog.append("user", result_text)

        self.progress_info["step"] = 4022
        self.progress_info["auto_continue"] = True
        return self.progress_info, result_text

    def _handle_combat_finalize(self) -> tuple[dict, str]:
        self.flags["intent"] = "post_combat_description"
        self.progress_info["step"] = 2010
        return self.progress_info, None



    def _request_dice_roll(self) -> tuple[dict, None]:
        flags = self.progress_info.setdefault("flags", {})
        flags["request_dice_roll"] = "2d6"

        # 判定種別に応じた戻り先の設定
        if "action_check_plan" in flags:
            self.progress_info["step"] = 3021
        elif "combat_evaluation" in flags:
            self.progress_info["step"] = 4021
        else:
            return self._fail("判定種別が不明です。")

        return self.progress_info, None

    def _classify_response(self, text: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "次の発言を以下のいずれかに分類してください：\n"
                    "- yes: 提案を受け入れている、あるいは肯定している（はい、いいよ、おねがい、受け入れる　等）\n"
                    "- no: 提案を拒否している、あるいは否定しているが、具体的な代案は出していない\n"
                    "- suggest: 肯定していないが、なんらかの動作や意思表示、提案が読み取れる 迷ったらこれ\n"
                    "- invalid: 発言が意味不明・途中で切れてる・ノイズ・構文不明 （例:「助走をつけてｚ」「あああ」「……」「oo」など）\n"
                    "出力は one word で 'yes', 'no', 'suggest', 'invalid' のいずれかのみとしてください。"
                )
            },
            {"role": "user", "content": text.strip()}
        ]

        result = self.ctx.engine.chat(messages, model_level="medium", max_tokens=2000).strip().lower()
        return result

    def _step_finalize_scenario(self) -> tuple[dict, str]:
        self.ctx.session_mgr.end_session(self.sid)
        self.ctx.state.mark_session_end()
        if self.state:
            self.state.clear_all()

        try:
            self._generate_session_summary()
        except Exception as e:
            print(f"[WARNING] summary generation failed: {e}")

        session = self.ctx.session_mgr.get_entry_by_id(self.sid) or {}
        pcid = session.get("player_character") or "default"

        self.progress_info["phase"] = "character_growth"
        self.progress_info["step"] = 0
        self.progress_info["flags"] = {
            "id": "default",
            "worldview_id": "default",
            "growth_session_id": self.sid,
            "growth_worldview_id": self.wid,
            "growth_character_id": pcid,
        }
        self.progress_info["auto_continue"] = True
        return self.progress_info, "セッションを終了し、キャラクター成長へ移ります。"


    def _generate_session_summary(self):
        try:
            convlog = ConversationLog(self.wid, self.sid, ctx=self.ctx)
            summary = convlog.generate_story_summary()

            if not summary.strip():
                print("[INFO] セッション要約が空だったため summary.txt は生成されません")
                return

            path = get_data_path(f"worlds/{self.wid}/sessions/{self.sid}/summary.txt")
            path.write_text(summary.strip(), encoding="utf-8")
            print(f"[INFO] セッション要約を書き出しました: {path}")

        except Exception as e:
            print(f"[WARNING] 要約生成中にエラー: {e}")

    def _reject(self, message: str) -> tuple[dict, str]:
        return self.progress_info, f"[エラー] {message}"
    
    def _fail(self, message: str) -> tuple[dict, str]:
        self.progress_info["phase"] = "prologue"
        self.progress_info["step"] = 0
        return self.progress_info, f"[致命的エラー] {message}"

