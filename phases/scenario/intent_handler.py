# phases/scenario/intent_handler.py
from phases.scenario.gameflow.director import Director
from phases.scenario.gameflow.informations import Informations
from phases.scenario.gameflow.narrator import Narrator
from phases.scenario.gameflow.add_command import append_brackets_to_text
from phases.scenario.gameflow.intro_handler import IntroHandler
from phases.scenario.gameflow.misc_handler import MiscHandler

class IntentHandler:
    def __init__(self, ctx, state, flags, convlog):
        self.ctx = ctx
        self.state = state
        self.flags = flags
        self.convlog = convlog

        # 共通情報束ね
        self.infos = Informations(state, ctx)  # informations.py 構造に準拠 :contentReference[oaicite:1]{index=1}

        # 進行JSONを作る司令塔（I/Oあり／前回Progression保持）
        self.director = Director(ctx, state, flags, convlog, self.infos)  # director() で呼ぶ実装 :contentReference[oaicite:2]{index=2}

        # 導入系・雑系ハンドラ（どちらも Informations 連結に対応済） 
        self.intro = IntroHandler(ctx, state, convlog, self.infos)  # :contentReference[oaicite:3]{index=3}
        self.misc = MiscHandler(ctx, state, convlog, self.infos)    # :contentReference[oaicite:4]{index=4}

    def handle(self, intent_or_label, player_input: str | None):
        """
        intent_or_label:
          - dict: {"label": "..."} でも
          - str : "action" 等のラベル文字列でもOK
        player_input は None 可。
        post系のときは flags から補完する。
        """
        # --- ラベルの正規化（dict or str の両対応） ---
        if isinstance(intent_or_label, dict):
            label = (intent_or_label or {}).get("label", "other")
        else:
            label = str(intent_or_label) if intent_or_label else "other"

        output_text: str

        # flags から補完する
        if label == "post_check_description":
            player_input = self.flags.get("last_check_result", "")
        elif label == "post_combat_description":
            player_input = self.flags.get("last_combat_result", "")

        if label in ("action", "post_check_description", "post_combat_description"):
            # 1) 進行JSON（Progression）生成
            progression = self.director.handle(label, player_input) 
            # 2) 描写生成（I/Oなし）。Narratorは Informations を内部で読む。 :contentReference[oaicite:6]{index=6}
            narr = Narrator(self.ctx, self.state, self.flags, self.convlog, self.infos)
            desc = narr.handle(
                label=label,
                player_input=player_input,
                progression=progression,
            )

            # 3) 旧式[]命令を末尾に追記（cmd→[command:…], cue→[action_check]/[combat_start]/[end_session]） :contentReference[oaicite:7]{index=7}
            output_text = append_brackets_to_text(desc, progression)

        elif label in ("chapter_intro", "section_intro"):
            # Intro のプロンプトは Informations 連結へ更新済み。 :contentReference[oaicite:8]{index=8}
            output_text = self.intro.handle(label)

        elif label in ("info_request", "gm_query","system", "other"):
            # 雑系も Informations 連結に対応済み。 :contentReference[oaicite:9]{index=9}
            output_text = self.misc.handle(label, player_input)

        else:
            output_text = f"未対応のintentです: {label}"

        # === ロギングを一元化（ここが本題） ===
        # 各ハンドラでは append しない方針に寄せるため、intent_handler で統一して書く
        self.convlog.append("user", player_input)
        self.convlog.append("assistant", output_text)

        return output_text
