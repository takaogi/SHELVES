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
                "maxItems": 30,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "note": {"type": "string"},
                        "fame": {  # 追加部分
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 50,
                            "description": "0=世界中の住人がほぼ全員知っている, 50=誰も知らない"
                        }
                    },
                    "required": ["name", "type", "tags", "note", "fame"]
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
            case 107:
                return self._handle_revision_request(input_text)


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
            "2. 自動生成モード（自由記述から自動構築）\n"
            "3. 戻る"
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
        elif choice == "3":
            # ← ここで worldview_select に戻す
            self.progress_info["phase"] = "worldview_select"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = {}
            self.progress_info["auto_continue"] = True
            return self.progress_info, "世界観選択に戻ります。"
        else:
            self.progress_info["step"] = 1
            return self.progress_info, "1〜3 を入力してください。"

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
        random.shuffle(genres)
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
            "候補はあくまで例です。必ず候補外の語も含めて検討し、最も適したものを選んでください。\n"
            "出力は与えられた JSON Schema（genre, period, tone, world_shape, name, description）に**厳密**に従ってください。\n"
            "・各値は日本語で簡潔に。\n"
            "・name は世界観の名称です。\n"
            "　以下のいずれか、または複数を組み合わせた構造パターンを参考にしてください。\n"
            "　1. 固有名詞 + 副題　例：アルマリス — 星降る峰\n"
            "　2. 短い漢字地名（1〜3字）　例：砂廻, 暁都, 深礁\n"
            "　3. カタカナ + 地形/施設　例：ヴァルカシオン宙域, グリムフォード水路網\n"
            "　4. 漢字 + カタカナ混合　例：碧衣の廃都ゼランダ, 黒氷棚エゼクリア\n"
            "　5. 造語（カタカナ）単独　例：フロスティネア, オルフェリス\n"
            "　6. 地名 + 異語（英語/ラテン等）　例：オルド・セレスティア, テラ・ヴァロス帝国宙辺区\n"
            "　7. 漢字二字熟語 + 地形　例：燐影境, 緋焔荒野, 銀屑の沼野\n"
            "　8. 特殊構造（記号や中黒、ダッシュを含む）　例：断層群島フェルシア, トリスケリオン環市\n"
            "　※単純で凡庸な『魔法の国』『幻想世界』などは避けること。\n"
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
            max_tokens=3000,
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
            "与えられた設定（ジャンル・時代・トーン・地理構造・概要文）を元に、"
            "その世界を百科事典の記事のように、500文字前後で解説してください。\n"
            "条件:\n"
            "・三人称・地の文・常体で書く。\n"
            "・地理や社会構造を淡々と説明する。\n"
            "・文学的な比喩やポエム的表現は控える。\n"
            "・国家、都市、組織、種族、宗教など、世界の主要な要素には必ず触れること。\n"
            "・ただし名称は付けず、抽象的な表現にとどめる（例：『大陸中央の帝国』、『海上に散在する都市国家群』）。\n"
            "・必要に応じて歴史的背景や文化的特徴も加える。\n"
            "・世界観の名称は本文に含めないこと（別枠で管理されるため）。「この世界」「この星」等の指示語で言及するように。" 
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
        long_desc = self.ctx.engine.chat(messages=messages, caller_name="WorldviewDetail",model_level = "very_high",max_tokens = 5000)

        draft["long_description"] = long_desc.strip()
        self.progress_info["step"] = 103
        return self._confirm_final_creation()


    def _confirm_final_creation(self):
        draft = self.flags.get("worldview_draft", {})
        lines = ["以下の詳細紹介文が生成されました："]
        lines.append("\n▼ 詳細紹介 ▼")
        lines.append(draft.get("long_description", "（生成失敗）"))
        lines.append("\nこの内容で世界観を作成しますか？")
        lines.append("1. 作成する（固有名詞作成に1~3分ほどかかります）")
        lines.append("2. 詳細紹介を作り直す")
        lines.append("3. 最初からやり直す")
        lines.append("4. 自分で編集する")
        lines.append("5. AIに修正を依頼する") 
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
        system = """
あなたはTRPG世界観の固有名詞抽出アシスタントです。
与えられた長文説明から、重要な固有名詞を抽出・命名してください。
特に以下のカテゴリについて、説明文に言及がある場合は必ず抽出すること（言及が無い場合は出力しないでよい）：
- 神話や世界創造に関わる存在（例：神々、原初の存在）
- 主要な国家や地域
- 中心的な都市や拠点
- 世界観を規定する宗教・組織
- 主要な種族や文化的集団
- 敵対勢力や世界的事件

固有名詞は以下の type のいずれかに分類してください：
    ・場所（都市、村、遺跡、ダンジョン、建物、地域、自然地形、異界など具体的な地理的地点）
    ・人物（名前を持つNPC、神格、固有名の魔王や賢者、特定個体の怪物や英雄など）
    ・組織（国家、宗教、ギルド、一族、派閥、軍、会社など集団組織）
    ・種族（エルフやドワーフなどの種族、動物、魔物、アンデッド、人工生命など）
    ・物品（武器、道具、乗り物、遺物、財宝、文書、鍵など重要なアイテム）
    ・知識（伝承、歴史、文化、宗教教義、技術、魔法体系、法律、習俗など背景設定）
    ・現象（呪い、災厄、異常気象、魔力の渦など継続的または一時的に発生する事象）
    ・出来事（戦争、儀式、事件、探索行、反乱、条約、祭りなど特定の期間や場面の出来事）

【命名ルール】
- 命名スタイルは世界観ジャンルに合わせること。
    ・ファンタジー: カタカナ造語を多めにし、漢字は地理や遺跡名に限定。
    ・東方風／歴史改変: 漢字主体の名称を多くし、外来要素にのみカタカナを用いる。
    ・スチームパンク／近代: 漢字＋カタカナ混成を多めにする。
    ・SF／宇宙: カタカナ造語中心とし、漢字は極力用いない。
    ・ポストアポカリプス／ダーク: 漢字主体か漢字＋カタカナ混成を多用する。
- 英語やローマ字表記は用いない。
- 漢字のみの名称を多くしすぎない（読みづらいため）。

【異名ルール】
- 名称が漢字のみで構成されている場合に限り、異名を付与してよい。
- すべてに異名を付ける必要はない。
    - 特に重要・象徴的な存在や、複数文化で呼称が分かれる場合のみ付与する。
- 異名は必ずカタカナ表記とする。漢字やひらがなは使わない。
- 異名は「読み仮名」ではなく、別文化・別言語的な表現や異称とする。
    - 例：星辰議会〈セレスティアルコード〉
- 表記は必ず 〈 〉 を使用し、丸括弧 ( ) は使わない。

- 単なる音読み・訓読みなどの読み仮名や、直訳は避ける。
- 本名と異名は文化的・音韻的につながりがあること。
  ・完全に無関係な語に置き換えない。
  ・意味や象徴が対応していること。

【その他命名ルール】
- 既存の一般名詞/記号的名称（「古代寺院」「古文書」など）だけにしない。必ず固有名化する。
    - 例：「古代寺院」→「黎明環堂〈ドーンリング〉」
- 国家や宗教、軍事組織の名称は多様性を持たせること。
  例：〜王国、〜帝国、〜公国、〜共和国、〜教団、〜教会、〜派、〜騎士団、〜連盟 など。
- 地名は地勢・由来・機能が想起できる語構成にする（例：霧縁の環礁、斑雪峠）。
- 類似名の乱立を避け、セッション内での識別性・再利用性を優先する。
- 既存IPの名称や紛らわしい著名名称は使用しない。

【分類ごとの命名例】
- 場所: 「ウィンドリフト高原」「黒曜の岬」「シリウス環礁」
- 人物: 「ユルグ・ローヴァン／灰眼の査閲官」「アシマ・ザフリ／紅蓮の隊長」
- 組織: 「星辰議会〈セレスティアルコード〉」「蒼刃同盟」「ヴァルグ砦邦」
- 種族: 「ステップリン（草耳の民）」「ホロウフォーク（空殻の民）」「エルダー・クレスト」
- 物品: 「燈火の聖典」「アストラの連弩」「ルミナの鏡」
- 知識: 「星譜解読法」「灰冠の予言」「セレスティア暦」
- 現象: 「星落ちの夜」「虚影の渦」「ノクタの霧」
- 出来事: 「七潮の約束」「渡星の移動市」「灰燼戦争」

【重複・整合】
- 同一または極めて近い概念が複数あれば、最も説明密度の高い1件に統合し、note に別名を併記（別名：〜）。
- 明確に階層関係（上位/下位）がある場合、上位概念を先に出し、下位は簡潔に（例：組織の下に部門）。
- 「国家」とその「宗教」の関係など、関連は note の末尾に相互参照（関連：〜）。

【note 作成ルール】
- シナリオ作成に耐える密度で、最低100文字以上。役割／由来／現在の状況／対立・利害／プレイヤーが関与しうる接点を具体的に。
- 可能なら“具体的ディテール（地名・人物名・儀礼名・物的特徴・行動原理）”を1〜2個入れる。
- 時制・確度を明記（伝承・推測はその旨を書く）。

【fame フィールド】
- fame は 0〜50 の整数で、小さいほど知名度が高い。
- 0 は「その世界の住民のほぼ全員が知っている」。地球でいう「太陽」「王都の名前」など。
- 10 前後は「大半の住民が名前を聞いたことがある」。例：主要な都市、著名な英雄、国王の名前、宗教の総本山。
- 20 前後は「その地域圏では広く知られているが、遠隔地では無名もしくは誤解されている」。例：地方の大領主、名高い遺跡、地域限定の伝説。
- 30 前後は「限られた専門家・関係者・一部地域の人々だけが知る」。例：特定の学派、隠れ里、特異な自然現象。
- 40 前後は「ごく一部の人物だけが存在を知る」。例：密命を帯びた組織、封印された秘宝、極秘の儀式。
- 50 は「現時点で誰も知らない、または完全に失われた」。例：忘れられた神の名、時代と共に消えた文明、未発見の遺跡。

【付与基準】
- 知名度は世界全体での相対的評価とする。ただし、特定の地方・種族内で有名でも全世界では無名の場合、低 fame（高知名度）にはしない。
- 歴史的に有名だったが現在はほぼ忘れられている場合、現在の知名度を基準とする。
- 伝承や噂として広まっているだけでも、多くの人が名前を知っていれば fame を低く設定する。
- 秘密組織や隠匿された存在は、意図的に知名度が抑えられているため fame を高く設定する。
- 長期間続く組織・場所・人物は、存在期間が長く、露出が多いほど fame を低くする。
- 名称は広く知られていても詳細を正しく知る者が少ない場合は、「名前基準」で fame を決める。

必ず各要素に fame を設定すること。

"""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"対象文:\n{long_desc}"}
        ]

        result = self.ctx.engine.chat(
            messages=messages,
            caller_name="NounExtract",
            model_level="very_high",
            max_tokens=10000,
            schema=NOUNS_SCHEMA, 
        )
        return result.get("nouns", [])


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
                        fame=noun.get("fame", 25),  # ★ 新フィールドを受け取る
                        details={}
                    )
                except Exception as e:
                    self.log.warning(f"固有名詞保存失敗: {noun} / {e}")

            nouns_mgr.sort_index_by_fame()
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
        
        elif choice == "5":
            self.progress_info["step"] = 107
            return self.progress_info, "どのように修正したいですか？（例：もっと神秘的に／戦乱を強調して）"

        else:
            self.progress_info["step"] = 103
            return self.progress_info, "1〜4 を選んでください。"


    def _handle_revision_request(self, input_text: str):
        request = input_text.strip()
        if not request:
            return self.progress_info, "修正内容を入力してください。"
        
        draft = self.flags.get("worldview_draft", {})
        base_text = draft.get("long_description", "")
        name = draft.get("name", "この世界")

        system_prompt = (
            "あなたはTRPGの世界観紹介文リライターです。\n"
            "元の紹介文を保持しつつ、ユーザーの修正要望に応じて書き直してください。\n"
            "500文字程度、三人称・地の文・常体を維持してください。"
        )
        user_prompt = f"世界観名: {name}\n修正要望: {request}\n\n元の紹介文:\n{base_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        new_desc = self.ctx.engine.chat(messages, caller_name="WorldviewRevision", model_level="very_high", max_tokens=5000)

        draft["long_description"] = new_desc.strip()
        self.progress_info["step"] = 103
        return self._confirm_final_creation()

def handle(ctx, progress_info, input_text):
    return WorldviewCreate(ctx, progress_info).handle(input_text)
