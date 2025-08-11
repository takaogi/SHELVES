# phases/worldview_create.py
import unicodedata
import random
from infra.logging import get_logger

CORRECTABLE_FIELDS = {
    "1": ("name", "名前"),
    "2": ("description", "説明"),
    "3": ("genre", "ジャンル"),
    "4": ("period", "時代"),
    "5": ("tone", "トーン"),
    "6": ("world_shape", "地理構造"),
    "7": (None, "確認画面に戻る")
}
# === 追加: スキーマ ===
WORLDVIEW_SCHEMA = {
    "type": "json_schema",
    "name": "WorldviewDraft",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "genre":        {"type": "string"},
            "period":       {"type": "string"},
            "tone":         {"type": "string"},
            "world_shape":  {"type": "string"},
            "name":         {"type": "string"},
            "description":  {"type": "string"}
        },
        "required": ["genre", "period", "tone", "world_shape", "name", "description"]
    }
}

NOUNS_SCHEMA = {
    "type": "json_schema",
    "name": "ProperNouns",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "nouns": {
                "type": "array",
                "minItems": 10,
                "maxItems": 15,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},  # 地名/国家/組織/宗教/伝承/その他 など
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "note": {"type": "string"}   # 補足説明（>=100字をプロンプトで要求）
                    },
                    "required": ["name", "type", "tags", "note"]
                }
            }
        },
        "required": ["nouns"],
        "additionalProperties": False
    }
}


class WorldviewCreate:
    def __init__(self, ctx, progress_info):
        self.ctx = ctx
        self.progress_info = progress_info
        self.flags = progress_info.setdefault("flags", {})
        self.log = get_logger("WorldviewCreate") 

    def handle(self, input_text: str) -> tuple[dict, str]:
        step = self.progress_info.get("step", 0)

        match step:
            case 0:
                return self._ask_creation_mode()
            case 1:
                return self._handle_mode_selection(input_text)

            case 10:
                return self._ask_genre()
            case 11:
                return self._handle_genre_selection(input_text)
            case 12:
                return self._handle_free_genre(input_text)

            case 20:
                return self._ask_period()
            case 21:
                return self._handle_period_selection(input_text)
            case 22:
                return self._handle_free_period(input_text)

            case 30:
                return self._ask_tone()
            case 31:
                return self._handle_tone_selection(input_text)
            case 32:
                return self._handle_free_tone(input_text)

            case 40:
                return self._ask_world_shape()
            case 41:
                return self._handle_shape_selection(input_text)
            case 42:
                return self._handle_free_shape(input_text)

            case 50:
                return self._ask_worldview_name()
            case 51:
                return self._handle_worldview_name(input_text)
            case 52:
                return self._handle_worldview_description(input_text)

            case 100:
                return self._confirm_worldview()
            case 101:
                return self._handle_worldview_decision(input_text)
            case 102:
                return self._generate_long_description(input_text)           
            case 103:
                return self._handle_final_creation_decision(input_text)
            case 104:
                return self._handle_long_description_edit(input_text)
            case 105:
                return self._handle_correction_target(input_text)
            case 106:
                return self._handle_field_correction(input_text)



            case 200:
                return self._handle_auto_start(input_text)
            case 201:
                return self._handle_auto_description(input_text)

            case _:
                return self.progress_info, "【System】不正なステップです。"

    def _ask_creation_mode(self):
        self.progress_info["step"] = 1
        return self.progress_info, (
            "世界観の作成モードを選んでください：\n"
            "1. 通常作成モード（カテゴリを一つずつ指定）\n"
            "2. 自動生成モード（自由記述から自動構築）"
        )

    def _handle_mode_selection(self, input_text: str):
        choice = unicodedata.normalize("NFKC", input_text.strip())
        if choice == "1":
            self.progress_info["step"] = 10
            self.flags["mode"] = "manual"
            self.progress_info["auto_continue"] = True
            return self.progress_info, "通常作成モードを開始します。"
        elif choice == "2":
            self.progress_info["step"] = 200
            self.flags["mode"] = "auto"
            self.progress_info["auto_continue"] = True
            return self.progress_info, "自動生成モードを開始します。"
        else:
            self.progress_info["step"] = 1
            return self.progress_info, "1 または 2 を入力してください。"

    def _ask_genre(self):
        self.progress_info["step"] = 11
        self.flags.setdefault("worldview_draft", {})
        genres = ["ファンタジー", "SF", "スチームパンク", "ポストアポカリプス", "現代異能", "歴史改変"]
        self.flags["_genre_choices"] = genres
        lines = ["ジャンルを選んでください："] + [f"{i+1}. {g}" for i, g in enumerate(genres)]
        lines.append(f"{len(genres)+1}. 自由入力する")
        return self.progress_info, "\n".join(lines)

    def _handle_genre_selection(self, input_text: str):
        genres = self.flags.get("_genre_choices", [])
        choice = unicodedata.normalize("NFKC", input_text.strip())
        try:
            index = int(choice) - 1
            if 0 <= index < len(genres):
                self.flags["worldview_draft"]["genre"] = genres[index]
                self.progress_info["step"] = 20
                self.progress_info["auto_continue"] = True
                return self.progress_info, f"ジャンル：{genres[index]} が選ばれました。"
            elif index == len(genres):
                self.progress_info["step"] = 12
                return self.progress_info, "ジャンルを自由に入力してください："
        except ValueError:
            pass
        return self.progress_info, "有効な番号を選んでください。"

    def _handle_free_genre(self, input_text: str):
        genre = input_text.strip()
        if not genre:
            return self.progress_info, "ジャンルが空です。もう一度入力してください。"
        self.flags["worldview_draft"]["genre"] = genre
        self.progress_info["step"] = 20
        self.progress_info["auto_continue"] = True
        return self.progress_info, f"ジャンル：{genre} を設定しました。"

    def _ask_period(self):
        self.progress_info["step"] = 21
        periods = ["古代", "中世", "近代", "現代", "近未来", "遠未来"]
        self.flags["_period_choices"] = periods
        lines = ["時代背景を選んでください："] + [f"{i+1}. {p}" for i, p in enumerate(periods)]
        lines.append(f"{len(periods)+1}. 自由入力する")
        return self.progress_info, "\n".join(lines)

    def _handle_period_selection(self, input_text: str):
        periods = self.flags.get("_period_choices", [])
        choice = unicodedata.normalize("NFKC", input_text.strip())
        try:
            index = int(choice) - 1
            if 0 <= index < len(periods):
                self.flags["worldview_draft"]["period"] = periods[index]
                self.progress_info["step"] = 30
                self.progress_info["auto_continue"] = True
                return self.progress_info, f"時代：{periods[index]} を設定しました。"
            elif index == len(periods):
                self.progress_info["step"] = 22
                return self.progress_info, "時代を自由に入力してください："
        except ValueError:
            pass
        return self.progress_info, "有効な番号を選んでください。"

    def _handle_free_period(self, input_text: str):
        period = input_text.strip()
        if not period:
            return self.progress_info, "時代が空です。もう一度入力してください。"
        self.flags["worldview_draft"]["period"] = period
        self.progress_info["step"] = 30
        self.progress_info["auto_continue"] = True
        return self.progress_info, f"時代：{period} を設定しました。"

    def _ask_tone(self):
        self.progress_info["step"] = 31
        tones = ["明るい", "ダーク", "混沌", "秩序", "静寂", "戦乱"]
        self.flags["_tone_choices"] = tones
        lines = ["世界観の雰囲気（トーン）を選んでください："] + [f"{i+1}. {t}" for i, t in enumerate(tones)]
        lines.append(f"{len(tones)+1}. 自由入力する")
        return self.progress_info, "\n".join(lines)
    

    def _handle_tone_selection(self, input_text: str):
        tones = self.flags.get("_tone_choices", [])
        choice = unicodedata.normalize("NFKC", input_text.strip())
        try:
            index = int(choice) - 1
            if 0 <= index < len(tones):
                self.flags["worldview_draft"]["tone"] = tones[index]
                self.progress_info["step"] = 40
                self.progress_info["auto_continue"] = True
                return self.progress_info, f"トーン：{tones[index]} を設定しました。"
            elif index == len(tones):
                self.progress_info["step"] = 32
                return self.progress_info, "雰囲気（トーン）を自由に入力してください："
        except ValueError:
            pass
        return self.progress_info, "有効な番号を選んでください。"

    def _handle_free_tone(self, input_text: str):
        tone = input_text.strip()
        if not tone:
            return self.progress_info, "トーンが空です。もう一度入力してください。"
        self.flags["worldview_draft"]["tone"] = tone
        self.progress_info["step"] = 40
        self.progress_info["auto_continue"] = True
        return self.progress_info, f"トーン：{tone} を設定しました。"

    def _ask_world_shape(self):
        self.progress_info["step"] = 41
        shapes = ["大陸", "島嶼", "宇宙都市", "多次元", "地下世界", "天空国家"]
        self.flags["_shape_choices"] = shapes
        lines = ["世界の地理的な形状を選んでください："] + [f"{i+1}. {s}" for i, s in enumerate(shapes)]
        lines.append(f"{len(shapes)+1}. 自由入力する")
        return self.progress_info, "\n".join(lines)

    def _handle_shape_selection(self, input_text: str):
        shapes = self.flags.get("_shape_choices", [])
        choice = unicodedata.normalize("NFKC", input_text.strip())
        try:
            index = int(choice) - 1
            if 0 <= index < len(shapes):
                self.flags["worldview_draft"]["world_shape"] = shapes[index]
                self.progress_info["step"] = 50
                self.progress_info["auto_continue"] = True
                return self.progress_info, f"世界形状：{shapes[index]} を設定しました。"
            elif index == len(shapes):
                self.progress_info["step"] = 42
                return self.progress_info, "地理的形状を自由に入力してください："
        except ValueError:
            pass
        return self.progress_info, "有効な番号を選んでください。"

    def _handle_free_shape(self, input_text: str):
        shape = input_text.strip()
        if not shape:
            return self.progress_info, "形状が空です。もう一度入力してください。"
        self.flags["worldview_draft"]["world_shape"] = shape
        self.progress_info["step"] = 50
        self.progress_info["auto_continue"] = True
        return self.progress_info, f"世界形状：{shape} を設定しました。"

    def _ask_worldview_name(self):
        self.progress_info["step"] = 51
        return self.progress_info, "この世界観に名前をつけてください："

    def _handle_worldview_name(self, input_text: str):
        name = input_text.strip()
        if not name:
            return self.progress_info, "名前が空です。もう一度入力してください。"
        self.flags["worldview_draft"]["name"] = name
        self.progress_info["step"] = 52
        return self.progress_info, "この世界観の説明文を一言で入力してください："

    def _handle_worldview_description(self, input_text: str):
        desc = input_text.strip()
        self.flags["worldview_draft"]["description"] = desc
        self.progress_info["step"] = 100
        return self.progress_info, None



    def _handle_auto_start(self, input_text: str):
        examples = [
            # ファンタジー
            "果てしない砂漠とオアシス都市が点在する交易世界",
            "浮遊する島々と天空都市が文明の中心となる空の王国",
            "大樹の根元に広がる地下都市と精霊たちの世界",
            "四季が一日ごとに巡る奇妙な王国",
            "永遠に夕暮れが続く海辺の都市国家",
            "死者が眠らず歩き回る黄昏の大陸",
            "竜の骨で築かれた要塞国家とその守護騎士団",
            "大陸全土を覆う魔法嵐に包まれた漂流大陸群",
            "星を信仰する遊牧騎馬民族の広大な平原世界",
            "空を泳ぐ鯨が暮らす雲海の上の群島王国",

            # SF
            "星間航路を行き交う商船と宇宙海賊がひしめく銀河",
            "惑星全土が一つの巨大都市に覆われたメガプラネット",
            "ブラックホールの縁に建造された環状居住圏",
            "AIが支配する仮想現実宇宙に閉じ込められた人類圏",
            "資源採掘で穿たれた月面地下の蜂の巣惑星",
            "異星文明の遺跡が点在する不毛の惑星圏",
            "時空の裂け目を越える漂流コロニー銀河域",
            "酸の海と硫黄の空に覆われた辺境惑星群",
            "巨大生物の体内で営まれる生態系惑星",

            # スチームパンク
            "蒸気機関と魔法が同居する産業革命時代の帝国圏",
            "歯車仕掛けの天空大陸と空中鉄道網",
            "真鍮とガラスで造られた海底帝国",
            "蒸気甲冑を纏った兵士が行進する列強諸国群",
            "動力を持つ自律人形が外交を行う多国間同盟",
            "煙突が林立する空を覆う灰色の大陸都市圏",

            # ポストアポカリプス
            "終末戦争後の荒廃した大地を巡る生存国家群",
            "氷結した海を越えて移動する浮遊大陸船団",
            "有毒植物が繁茂する廃墟化した旧世界大陸",
            "地下シェルター群で暮らす閉ざされた世界圏",
            "放射線嵐が周期的に襲う荒野大陸",
            "遺伝子変異した生物が支配する失われた超大陸",

            # その他ユニーク
            "無限に続く階層都市世界と、その最下層に眠る禁忌の遺産",
            "世界の果てにそびえる逆さまの山脈大陸",
            "海そのものが意思を持ち動く群島世界",
            "空の彼方に吊り下げられた太陽灯が照らす人工大陸圏",
            "巨大生物の背中に築かれた移動国家群",
            "五つの月が巡る潮汐に支配された群島王国",
            "大地が周期的に反転する双面世界",
            "常に流転し続ける漂流大陸群とその諸国",
        ]


        sample = random.sample(examples, 3)  # 3つランダム選択

        self.progress_info["step"] = 201
        return self.progress_info, (
            "自由にこの世界の概要や雰囲気を記述してください。\n"
            "例：\n" + "\n".join(f"- {ex}" for ex in sample)
        )


    def _handle_auto_description(self, input_text: str):
        genres = ["ファンタジー", "SF", "スチームパンク", "ポストアポカリプス", "現代異能", "歴史改変"]
        periods = ["古代", "中世", "近代", "現代", "近未来", "遠未来"]
        tones = ["明るい", "ダーク", "混沌", "秩序", "静寂", "戦乱"]
        shapes = ["大陸", "島嶼", "宇宙都市", "多次元", "地下世界", "天空国家"]

        system_prompt = (
            "あなたはTRPG用世界観構築支援AIです。\n"
            "以下の選択肢群を参考にしつつ、ユーザーの自由記述から各項目を推測し補完してください。\n\n"
            f"ジャンル候補：{', '.join(genres)}\n"
            f"時代候補：{', '.join(periods)}\n"
            f"雰囲気候補：{', '.join(tones)}\n"
            f"地理形状候補：{', '.join(shapes)}\n\n"
            "出力は与えられた JSON Schema（genre, period, tone, world_shape, name, description）に**厳密**に従ってください。\n"
            "・各値は日本語で簡潔に。\n"
            "・name は世界の名称。\n"
            "・description は世界観の概要を1文程度で要約。"
        )

        prompt = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"自由記述：{input_text.strip()}"}
        ]

        # ★ スキーマ指定で構造化出力（dict）を直受け取り
        result = self.ctx.engine.chat(
            messages=prompt,
            caller_name="AutoWorldview",
            model_level="high",
            schema=WORLDVIEW_SCHEMA,
            max_tokens=2000,
        )


        draft = result if isinstance(result, dict) else {}
        draft["raw_input"] = input_text.strip()

        self.flags["worldview_draft"] = draft
        self.progress_info["step"] = 100
        self.progress_info["auto_continue"] = True
        return self.progress_info, "自動生成された世界観を確認します。"

    

    def _confirm_worldview(self):
        self.progress_info["step"] = 101
        draft = self.flags.get("worldview_draft", {})
        lines = ["以下の内容で世界観を生成します："]
        lines.append(f"名前: {draft.get('name', '(未設定)')}")
        lines.append(f"説明: {draft.get('description', '(未設定)')}")
        for key in ["genre", "period", "tone", "world_shape"]:
            lines.append(f"- {key}: {draft.get(key, '未設定')}")
        lines.append("\n1. これで生成する\n2. 最初からやり直す\n3. タグ内容を修正する")
        return self.progress_info, "\n".join(lines)


    def _handle_worldview_decision(self, input_text: str):
        choice = unicodedata.normalize("NFKC", input_text.strip())

        if choice == "1":
            self.progress_info["step"] = 102 
            return self._generate_long_description()

        elif choice == "2":
            self.progress_info["step"] = 0
            self.flags["worldview_draft"] = {}
            self.progress_info["auto_continue"] = True
            return self.progress_info, "最初からやり直します。"
        
        elif choice == "3":
            return self._ask_correction_target()

        else:
            self.progress_info["step"] = 101
            return self.progress_info, "1か2を選んでください。"
            
    def _ask_correction_target(self) -> tuple[dict, str]:
        self.progress_info["step"] = 105
        lines = ["修正したい項目を選んでください："]
        for i in range(1, 7 + 1):
            label = CORRECTABLE_FIELDS[str(i)][1]
            lines.append(f"{i}. {label}")
        return self.progress_info, "\n".join(lines)

    def _handle_correction_target(self, input_text: str) -> tuple[dict, str]:
        choice = unicodedata.normalize("NFKC", input_text.strip())

        if choice == "7":
            self.progress_info["step"] = 100
            self.progress_info["auto_continue"] = True
            return self.progress_info, "確認画面に戻ります。"

        field_info = CORRECTABLE_FIELDS.get(choice)
        if not field_info:
            return self._reject("1〜7の番号で入力してください。", step=104)

        field, label = field_info
        self.flags["_correction_field"] = field
        draft = self.flags.get("worldview_draft", {})
        current = draft.get(field, "（未設定）")

        if isinstance(current, list):
            current = ", ".join(current)

        self.progress_info["step"] = 106
        return self.progress_info, f"現在の{label}：\n{current}\n\n新しい値を入力してください。"
    
    def _handle_field_correction(self, input_text: str) -> tuple[dict, str]:
        field = self.flags.get("_correction_field")
        if not field:
            return self._reject("修正対象が不明です。", step=104)

        value = input_text.strip()
        if not value:
            return self.progress_info, "入力が空です。もう一度入力してください。"

        self.flags["worldview_draft"][field] = value
        self.progress_info["step"] = 100
        self.progress_info["auto_continue"] = True
        return self.progress_info, f"{field} を更新しました。"

    def _generate_long_description(self):
        draft = self.flags.get("worldview_draft", {})
        name = draft.get("name", "この世界")
        genre = draft.get("genre", "")
        tone = draft.get("tone", "")
        period = draft.get("period", "")
        shape = draft.get("world_shape", "")
        short_desc = draft.get("description", "")

        system_prompt = (
            "あなたはTRPGの世界観紹介文を執筆する語り手です。\n"
            "ジャンルやトーン、時代背景、地理構造、概要文を元に、"
            "その世界を500文字程度で、三人称・地の文・常体で解説してください。\n"
            "ジャンルやトーン、時代背景に基づく淡々とした情景描写と、地理や支配構造の説明を含んでください。"
        )
        raw_input = draft.get("raw_input", "")
        user_prompt = (
            f"ジャンル: {genre}\n"
            f"時代: {period}\n"
            f"トーン: {tone}\n"
            f"地理構造: {shape}\n"
            f"概要: {short_desc}\n"
            f"名前: {name}\n"
        )

        if raw_input:
            user_prompt += f"\n元の自由記述（参考）: {raw_input}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        long_desc = self.ctx.engine.chat(messages=messages, caller_name="WorldviewDetail",model_level = "very_high",max_tokens = 10000)

        draft["long_description"] = long_desc.strip()
        self.progress_info["step"] = 103
        return self._confirm_final_creation()


    def _confirm_final_creation(self):
        draft = self.flags.get("worldview_draft", {})
        lines = ["以下の詳細紹介文が生成されました："]
        lines.append("\n▼ 詳細紹介 ▼")
        lines.append(draft.get("long_description", "（生成失敗）"))
        lines.append("\nこの内容で世界観を作成しますか？")
        lines.append("1. 作成する")
        lines.append("2. 詳細紹介を作り直す")
        lines.append("3. 最初からやり直す")
        lines.append("4. 自分で編集する")

        return self.progress_info, "\n".join(lines)

    def _handle_long_description_edit(self, input_text: str):
        desc = input_text.strip()
        if not desc:
            return self.progress_info, "空の紹介文は設定できません。もう一度入力してください。"
        
        self.flags["worldview_draft"]["long_description"] = desc
        self.progress_info["step"] = 103
        self.progress_info["auto_continue"] = True
        return self.progress_info, "新しい紹介文を保存しました。"

    def _extract_proper_nouns(self, long_desc: str) -> list[dict]:
        system = (
            "あなたはTRPG世界観の固有名詞抽出アシスタントです。\n"
            "与えられた長文説明から、重要な地名・国名・組織・宗教・伝承などを抽出/命名し、"
            "スキーマに従って JSON 配列で返してください。この時、国や組織、地名などが固有の名称を持っていない場合、それを生成して記述してください。\n"
            "名称にカッコで横文字のルビを追記しても構いません。（例：星辰議会（セレスティアルコード）、黒曜同盟（ノクターンオーダー）　など）\n"
            "各要素はシナリオ作成に耐える密度で、note は最低100文字以上を目安に具体性を持たせてください。\n"
            "type 候補: 地名, 国家, 組織, 宗教, 伝承, その他"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"対象文:\n{long_desc}"}
        ]

        try:
            result = self.ctx.engine.chat(
                messages=messages,
                caller_name="NounExtract",
                model_level="very_high",
                max_tokens=15000,
                schema=NOUNS_SCHEMA, 
            )
            nouns_list = result.get("nouns", [])
            return nouns_list
        except Exception as e:
            self.log.warning(f"固有名詞抽出に失敗: {e}")
            return []


    def _handle_final_creation_decision(self, input_text: str):
        choice = unicodedata.normalize("NFKC", input_text.strip())
        draft = self.flags.get("worldview_draft", {})

        if choice == "1":
            wvm = self.ctx.worldview_mgr
            name = draft.get("name", "新しい世界")
            description = draft.get("description", "（説明なし）")
            entry = wvm.create_worldview(name=name, description=description)

            # 拡張フィールドを保存
            wvm.update_entry(entry["id"], {
                "genre": draft.get("genre", ""),
                "period": draft.get("period", ""),
                "tone": draft.get("tone", ""),
                "world_shape": draft.get("world_shape", ""),
                "long_description": draft.get("long_description", "")
            })
            # --- 固有名詞の自動抽出と保存 ---
            nouns = self._extract_proper_nouns(draft["long_description"])
            nouns_mgr = self.ctx.nouns_mgr
            nouns_mgr.set_worldview_id(entry["id"])

            for noun in nouns:
                try:
                    nouns_mgr.create_noun(
                        name=noun["name"],
                        type=noun.get("type", "その他"),
                        tags=noun.get("tags", []),
                        notes=noun.get("note", ""),
                        details=""
                    )
                except Exception as e:
                    self.log.warning(f"固有名詞保存失敗: {noun} / {e}")


            self.progress_info["phase"] = "worldview_select"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = {}
            self.progress_info["auto_continue"] = True
            return self.progress_info, f"世界観『{entry['name']}』を作成しました。"

        elif choice == "2":
            self.progress_info["step"] = 102
            return self._generate_long_description()

        elif choice == "3":
            self.progress_info["step"] = 0
            self.flags["worldview_draft"] = {}
            self.progress_info["auto_continue"] = True
            return self.progress_info, "最初からやり直します。"
            
        elif choice == "4":
            self.progress_info["step"] = 104
            return self.progress_info, "新しい詳細紹介文を入力してください："

        else:
            self.progress_info["step"] = 103
            return self.progress_info, "1〜4 を選んでください。"


def handle(ctx, progress_info, input_text):
    return WorldviewCreate(ctx, progress_info).handle(input_text)
