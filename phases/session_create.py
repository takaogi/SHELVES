# phases/session_create.py
import unicodedata
import json

# === Structured JSON Schemas ===
SCENARIO_META_SCHEMA = {
    "type": "json_schema",
    "name": "ScenarioMeta",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "theme": {"type": "string"},
            "tone": {"type": "string"},
            "style": {"type": "string"},
            "length": {"type": "string", "enum": ["short", "medium", "long"]}
        },
        "required": ["theme", "tone", "style", "length"],
        "additionalProperties": False
    }
}
SCENARIO_DRAFT_SCHEMA = {
    "type": "json_schema",
    "name": "ScenarioDraft",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "goal": {"type": "string"},
            "chapters": {
                "type": "array",
                "minItems": 2,
                "maxItems": 10,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "goal":{"type": "string"},
                        "overview": {"type": "string","minLength": 100}
                    },
                    "required": ["title", "goal", "overview"],
                    "additionalProperties": False
                }
            },
            "canon_facts": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "note": {"type": "string","minLength": 50}
                    },
                    "required": ["name", "type", "note"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["title", "summary", "goal", "chapters", "canon_facts"],
        "additionalProperties": False
    }
}
CHARACTER_GENERATION_SCHEMA = {
    "type": "json_schema",
    "name": "GeneratedCharacter",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "gender": {"type": "string"},
            "age": {"type": "string"},
            "race": {"type": "string"},
            "origin": {"type": "string"},
            "occupation": {"type": "string"},
            "personality": {"type": "string"},
            "appearance": {"type": "string"},
            "physique": {"type": "string"},
            "abilities": {"type": "string"},
            "weaknesses": {"type": "string"},
            "likes": {"type": "string"},
            "dislikes": {"type": "string"},
            "items": {
                "type": "array",
                "items": {"type": "string"}
            },
            "beliefs": {"type": "string"},
            "summary": {"type": "string"},
            "background": {"type": "string"},
            "notes": {"type": "string"},
            "used_nouns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "note": {"type": "string"}
                    },
                    "required": ["name", "type", "note"],
                    "additionalProperties": False
                }
            }
        },
        "required": [
            "name", "tags", "gender", "age", "race", "origin", "occupation",
            "personality", "appearance", "physique", "abilities", "weaknesses",
            "likes", "dislikes", "items", "beliefs", "summary", "background",
            "notes", "used_nouns"
        ],
        "additionalProperties": False
    }
}

CORRECTABLE_FIELDS = {
    "1": ("name", "名前（このキャラクターのフルネームや呼び名）"),
    "2": ("gender", "性別（自由記述可。例：男性、女性、中性、不明など）"),
    "3": ("age", "年齢（数値または『若い』『老齢』のような表現でも可）"),
    "4": ("race", "種族（例：人間、エルフ、機械生命体など）"),
    "5": ("origin", "出身地（地名または地域。例：王都アストリア、辺境の森）"),
    "6": ("occupation", "職業（例：冒険者、司書、元兵士など）"),
    "7": ("personality", "性格（短い形容で傾向を示す。例：冷静沈着、好奇心旺盛）"),
    "8": ("appearance", "容姿（髪・目・服装・印象など）"),
    "9": ("physique", "体格（身長・体型・特徴的な部位など）"),
    "10": ("abilities", "能力（得意なこと。例：剣術、追跡術、魔法詠唱）"),
    "11": ("weaknesses", "弱点（苦手なこと。例：方向音痴、人付き合い）"),
    "12": ("beliefs", "信条・価値観（例：力こそ正義、命はすべて等しい）"),
    "13": ("likes", "好きなもの（猫、歴史、静かな場所など）"),
    "14": ("dislikes", "苦手なもの（虫、大声、嘘など）"),
    "15": ("items", "所持品（装備や個人的な持ち物など）"),
    "16": ("summary", "一言紹介（このキャラを要約する1文）"),
    "17": ("background", "背景（経歴、動機、過去の出来事など自由記述）"),
    "18": ("notes", "備考・補足（その他なんでも）"),
    "19": ("戻る", "戻る")
}


class SessionCreate:
    def __init__(self, ctx, progress_info):
        self.ctx = ctx
        self.progress_info = progress_info
        self.flags = progress_info.setdefault("flags", {})
        self.wid = (
            self.flags.get("worldview_id")
            or self.flags.get("worldview", {}).get("id", "")
        )

        self.state = ctx.state
        self.session_mgr = ctx.session_mgr

    def handle(self, input_text: str) -> tuple[dict, str]:
        step = self.progress_info.get("step", 0)

        match step:
            case 0:
                return self._intro_message()
            case 1:
                return self._show_character_choices()
            case 2:
                return self._handle_character_selection(input_text)

            case 100:
                return self._ask_character_description()
            case 101:
                return self._generate_character_from_input(input_text)
            case 102:
                return self._review_generated_character()
            case 103:
                return self._handle_character_review_choice(input_text)
            case 104:
                return self._ask_correction_target()
            case 105:
                return self._handle_correction_target(input_text)
            case 106:
                return self._handle_correction_input(input_text)
            case 107:
                return self._handle_level_input(input_text)
            case 108:
                return self._start_skill_distribution()
            case 109:
                return self._handle_skill_distribution(input_text)
            case 110:
                return self._confirm_skill_distribution()
            case 111:
                return self._finalize_character(input_text)

                        
            case 1000:
                return self._ask_scenario_direction()
            case 1001:
                return self._handle_scenario_direction_input(input_text)
            case 1002:
                return self._handle_scenario_generate(input_text)
            case 1003:
                return self._review_generated_scenario()
            case 1004:
                return self._handle_scenario_review_choice(input_text)





            
            case _:
                return self.progress_info, "【System】不正なステップです。"

    def _intro_message(self) -> tuple[dict, str]:
        if "sequel_to" in self.flags:
            # 続編セッションなのでキャラ選択をスキップ
            self.progress_info["step"] = 1000
            return self.progress_info, None

        # 通常の新規セッション
        self.progress_info["step"] = 1
        return self.progress_info, None

    
    def _show_character_choices(self) -> tuple[dict, str]:
        cm = self.ctx.character_mgr
        cm.set_worldview_id(self.wid)

        pcs = [e for e in cm.entries if "PC" in e.get("tags", [])]
        others = [e for e in cm.entries if "PC" not in e.get("tags", [])]

        self.flags["_pcs"] = pcs
        self.flags["_others"] = others

        lines = ["セッションの作成を開始します。\nPCを選んでください："]

        idx = 1
        index_map = {}

        if pcs:
            lines.append("\n▼ PCタグ付きキャラクター：")
            for c in pcs:
                lines.append(f"{idx}. {c['name']} [PC]")
                index_map[idx] = c
                idx += 1

        if others:
            lines.append("\n▼ その他のキャラクター：")
            for c in others:
                lines.append(f"{idx}. {c['name']}")
                index_map[idx] = c
                idx += 1

        lines.append(f"\n{idx}. 新しいキャラクターを作成する")
        self.flags["_index_map"] = index_map
        self.flags["_new_character_index"] = idx

        self.progress_info["step"] = 2
        return self.progress_info, "\n".join(lines)


    def _handle_character_selection(self, input_text: str) -> tuple[dict, str]:
        try:
            choice = int(unicodedata.normalize("NFKC", input_text.strip()))
        except ValueError:
            return self._reject("数字で入力してください。", step=2)

        index_map = self.flags.get("_index_map", {})
        new_index = self.flags.get("_new_character_index")

        if choice == new_index:
            self.progress_info["step"] = 100
            self.progress_info["auto_continue"] = True
            return self.progress_info, "新しいキャラクターを作成します。"

        elif choice in index_map:
            selected = index_map[choice]

            # 🔽 ここでIDからフルデータを取得
            cm = self.ctx.character_mgr
            cm.set_worldview_id(self.wid)
            full_data = cm.load_character_file(selected.get("id")) or selected

            self.flags["player_character"] = full_data
            self.progress_info["step"] = 1000
            self.progress_info["auto_continue"] = True
            return self.progress_info, f"キャラクター『{full_data.get('name', '不明')}』を選択しました。"


        else:
            return self._reject("範囲内の番号を選んでください。", step=2)
        

    def _ask_character_description(self) -> tuple[dict, str]:
        self.progress_info["step"] = 101

        worldview = self.flags.get("worldview", {})
        wid = worldview.get("id", "")
        long_desc = worldview.get("long_description", "").strip()

        self.ctx.nouns_mgr.set_worldview_id(wid)
        noun_list = self.ctx.nouns_mgr.entries[:10]  # 最大10件に制限

        lines = []

        if long_desc:
            lines.append("▼ この世界の詳細紹介：\n" + long_desc + "\n")

        if noun_list:
            lines.append("▼ この世界の登場要素（固有名詞）：")
            for n in noun_list:
                name = n.get("name", "名称不明")
                ntype = n.get("type", "分類不明")
                note = n.get("notes", "").strip()
                lines.append(f"- {name}（{ntype}）：{note}")
            lines.append("")  # 空行

        lines.append("あなたが演じるキャラクターの概要を自由に記述してください。")
        lines.append("（例：無口で優しい巨人族の少女。村を襲った魔獣に家族を殺され、今は放浪している…）")

        return self.progress_info, "\n".join(lines)

    
    def _generate_character_from_input(self, input_text: str = "") -> tuple[dict, str]:
        long_desc = self.flags["worldview"].get("long_description", "")
        player_input = input_text.strip()
        self.ctx.nouns_mgr.set_worldview_id(self.wid)
        nouns = self.ctx.nouns_mgr.entries[:10]

        system_prompt = (
            "あなたはTRPGのキャラクターを自動生成するアシスタントです。\n"
            "以下の世界観説明・固有名詞・プレイヤーの記述を元に、\n"
            "その世界で自然に生きるキャラクターを構築してください。ただし、無理に固有名詞を使う必要はありません。\n\n"
            "以下の各フィールドは次のように埋めてください：\n\n"
            "- name: キャラクターの名前。\n"
            "- tags: PCを含む、種族・職業・性格などの分類タグ。文字列のリスト。\n"
            "- gender: 性別（自由な表記でよい）。\n"
            "- age: 年齢（数字でも世代的表現でもOK）。\n"
            "- race: 種族名（人間、エルフなど）。\n"
            "- origin: 出身地、育った場所など。\n"
            "- occupation: 職業・社会的役割（冒険者、司書など）。\n"
            "- personality: 一言で性格傾向を説明。\n"
            "- appearance: 容姿（髪色、目の色、肌の色、髪型、服装、表情などの外見的特徴）。\n"
            "- physique: 体格（身長・体型・特徴的な部位など）。\n"
            "- abilities: 特徴的な技能・才能（例：剣術と瞬発力に優れる、炎の魔法に長けるなど）。\n"
            "- weaknesses: 苦手なこと・欠点・弱点（例：方向音痴、人付き合いが苦手）。\n"
            "- likes: 好きなもの、興味対象（例：猫、静かな場所、古代文明）。\n"
            "- dislikes: 苦手なもの、嫌悪対象（例：虫、大声、嘘）。\n"
            "- items: 所持品（例：家族の形見のペンダント、魔法の杖、旅人の背嚢）。\n"
            "- beliefs: 価値観・信条（例：力こそ正義、命はすべて等しい）。\n"
            "- summary: 一言紹介（キャラをわかりやすくまとめる）。\n"
            "- background: そのキャラの来歴や動機などを自由に記述。\n"
            "- notes: その他の備考や自由なメモ（必要なら）。\n"
            "- used_nouns: 使用した固有名詞があれば列挙。各要素は {\"name\": 名称, \"type\": 分類, \"note\": 説明}。\n\n"
        )

        user_prompt = (
            f"▼ 世界観の説明:\n{long_desc}\n\n"
            f"▼ 固有名詞一覧:\n" +
            json.dumps(nouns, ensure_ascii=False, indent=2) +
            f"\n\n▼ プレイヤーの記述:\n{player_input}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        result = self.ctx.engine.chat(
            messages=messages,
            caller_name="AutoCharacter",
            model_level="high",
            max_tokens=10000,
            schema=CHARACTER_GENERATION_SCHEMA
        )

        if isinstance(result, dict):
            self.flags["_char_generation_obj"] = result
            self.progress_info["step"] = 102
            self.progress_info["auto_continue"] = True
            return self.progress_info, "キャラクターが生成されました。内容を確認してください。"

        self.progress_info["step"] = 102
        self.progress_info["auto_continue"] = True
        return self.progress_info, (
            "⚠️ キャラクターの生成には成功しましたが、スキーマに適合しないため解析に失敗しました。\n"
            f"そのまま表示して確認します。\n\n{result}"
        )

    def _review_generated_character(self) -> tuple[dict, str]:
        obj = self.flags.get("_char_generation_obj")
        if not obj:
            # fallback: raw表示
            raw_text = self.flags.get("_char_generation_raw", "")
            return self._reject("構造化されたキャラ情報が見つかりません。", step=101) if not raw_text else (
                self.progress_info.update({"step": 103}) or
                (self.progress_info, f"キャラクター情報を表示できませんでした。\n\n{raw_text}")
            )

        # 整形表示
        PARAGRAPH_FIELDS = {"summary", "background", "notes"}
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

        lines = []
        for field, label in FIELD_LABELS.items():
            value = obj.get(field)
            if value:
                if field in PARAGRAPH_FIELDS:
                    lines.append(f"\n▼ {label}:\n{value}")
                elif field == "items":
                    if isinstance(value, list):
                        lines.append("\n▼ 所持品:")
                        for it in value:
                            lines.append(f"- {it}")
                    else:
                        lines.append(f"所持品: {value}")
                else:
                    lines.append(f"{label}: {value}")


        used_nouns = obj.get("used_nouns", [])
        if used_nouns:
            lines.append("\n▼ 使用された固有名詞：")
            for noun in used_nouns:
                lines.append(f"- {noun.get('name', '')}（{noun.get('type', '')}）: {noun.get('note', '')}")

        lines.append("\nこのキャラクターで作成しますか？")
        lines.append("1. はい（レベル設定へ）\n2. 修正したい\n3. 別のキャラを再生成する")

        self.progress_info["step"] = 103
        return self.progress_info, "\n".join(lines)

    def _handle_character_review_choice(self, input_text: str) -> tuple[dict, str]:

        choice = unicodedata.normalize("NFKC", input_text.strip())
        obj = self.flags.get("_char_generation_obj")

        if not obj:
            return self._reject("キャラ情報が見つかりませんでした。", step=101)

        if choice == "1":
            self.progress_info["step"] = 107
            self.progress_info["auto_continue"] = False
            return self.progress_info, (
                "キャラクターを確定する前に、戦闘レベルを入力してください。\n\n"
                "このキャラクターの戦闘レベル（0〜15）を入力してください。\n\n"
                "レベルは戦闘能力の指標で、以下のような目安です：\n"
                "0：一般人（非戦闘員）\n"
                "1〜3：初心者〜見習い冒険者\n"
                "4〜6：熟練者クラス（一人前）\n"
                "7〜10：超人的な存在\n"
                "11〜13：伝説・神話級の英雄\n"
                "14〜15：神や精霊に匹敵する存在\n\n"
                "数字で入力してください（例：5）\n"
                "レベルは、主にシナリオのスケール調整に使用されます。（難易度は大きく変わりません）"
            )

        elif choice == "2":
            self.progress_info["step"] = 104
            self.progress_info["auto_continue"] = True
            return self.progress_info, "修正を行います。"

        elif choice == "3":
            self.progress_info["step"] = 100
            self.progress_info["auto_continue"] = True
            return self.progress_info, "キャラクターを再生成します。"

        else:
            return self._reject("1〜3のいずれかを入力してください。", step=103)
   
    def _ask_correction_target(self) -> tuple[dict, str]:

        self.progress_info["step"] = 105
        lines = ["修正したい項目を選んでください："]
        for i in range(1, 19 + 1):
            label = CORRECTABLE_FIELDS.get(str(i), (None, "???"))[1]
            lines.append(f"{i}. {label}")
        return self.progress_info, "\n".join(lines)  
       
    def _handle_correction_target(self, input_text: str) -> tuple[dict, str]:

        choice = unicodedata.normalize("NFKC", input_text.strip())
        if choice == "19":
            self.progress_info["step"] = 102
            self.progress_info["auto_continue"] = True
            return self.progress_info, "確認画面に戻ります。"

        field_info = CORRECTABLE_FIELDS.get(choice)
        if not field_info:
            return self._reject("1〜19の番号で入力してください。", step=104)

        field, label = field_info
        self.flags["_correction_field"] = field
        current = self.flags["_char_generation_obj"].get(field, "（未設定）")

        if isinstance(current, list):
            current = ", ".join(current)

        self.progress_info["step"] = 106
        return self.progress_info, f"現在の{label}：\n{current}\n\n新しい値を入力してください。"

    def _handle_correction_input(self, input_text: str) -> tuple[dict, str]:
        field = self.flags.get("_correction_field")
        if not field:
            return self._reject("修正対象が見つかりません。", step=104)

        value = input_text.strip()

        self.flags["_char_generation_obj"][field] = value
        self.progress_info["step"] = 102
        self.progress_info["auto_continue"] = True
        return self.progress_info, f"{field}を更新しました。確認画面に戻ります。"

    def _handle_level_input(self, input_text: str) -> tuple[dict, str]:
        try:
            level = int(unicodedata.normalize("NFKC", input_text.strip()))
            if not (0 <= level <= 15):
                raise ValueError
        except ValueError:
            return self._reject("0〜15の整数を入力してください。", step=107)

        # キャラクター情報にレベルを反映
        obj = self.flags.get("_char_generation_obj", {})
        obj["level"] = level
        obj["tags"] = list(set(obj.get("tags", []) + ["PC"]))

        # スキル初期化
        self.flags["_check_assignments"] = {name: 0 for name in [
            "探知", "操身", "剛力", "知性", "直感", "隠形",
            "看破", "技巧", "説得", "意志", "強靭", "希望"
        ]}

        self.flags["_check_total_cost"] = 0

        self.progress_info["step"] = 108
        self.progress_info["auto_continue"] = True
        return self.progress_info, "レベルが設定されました。次に行為判定スキルの割り振りに進みます。"


    def _start_skill_distribution(self) -> tuple[dict, str]:
        self.progress_info["step"] = 109
        self.progress_info["auto_continue"] = False

        skills = self.flags.get("_check_assignments", {})
        total_cost = self._calculate_total_skill_cost(skills)
        self.flags["_check_total_cost"] = total_cost

        skill_list = []
        for i, name in enumerate(skills.keys(), start=1):
            val = skills[name]
            skill_list.append(f"{i}. {name}：{val:+d}")

        lines = [
            "行為判定スキルの割り振りを行います。",
            "各スキルには得意・不得意の度合いを示す値を設定できます。",
            "数値が高いほど行為判定に有利になりますが、より多くのコストを消費します。",
            ""

        ]
        skill_descriptions = {
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
            "希望": ""  # ← 意図的に説明なし
        }

        lines.append("▼ スキルの説明")
        for name in skills:
            desc = skill_descriptions.get(name, "")
            if desc:
                lines.append(f"{name}：{desc}")
            else:
                lines.append(f"{name}：？？？")


        lines.append("\n現在のスキルと割り振り状況：")
        # スキル表示
        skills = self.flags.get("_check_assignments", {})
        for i, name in enumerate(skills.keys(), start=1):
            val = skills[name]
            lines.append(f"{i}. {name}：{val:+d}")


        # コスト表示と操作方法
        lines.extend([
            "",
            f"▶ 合計コスト：{self.flags.get('_check_total_cost', 0)} / 上限：12pt",
            "",
            "以下の形式でスキルを調整してください：",
            "例：1 +1   → 『探知』を +1",
            "例：11 +2  → 『強靭』を +2",
            "",
            "入力：done → 割り振りを終了して確認に進む"
        ])


        return self.progress_info, "\n".join(lines)

    def _calculate_total_skill_cost(self, skill_values: dict[str, int]) -> int:
        def skill_cost(val: int) -> int:
            if val < -3 or val > 3:
                raise ValueError("無効な入力です")
            if val > 0:
                return sum(range(1, val + 1))   # 1→1, 2→3, 3→6
            elif val < 0:
                return val                     # -1→+1, -2→+2, -3→+3
            else:
                return 0

        return sum(skill_cost(v) for v in skill_values.values())

    def _handle_skill_distribution(self, input_text: str) -> tuple[dict, str]:
        text = unicodedata.normalize("NFKC", input_text.strip())

        # 完了処理
        if text.lower() == "done":
            skills = self.flags.get("_check_assignments", {})
            total = self._calculate_total_skill_cost(skills)
            if total > 12:
                return self._reject(f"合計コストが上限を超えています（現在: {total} / 上限: 12）", step=109)
            self.progress_info["step"] = 110
            self.progress_info["auto_continue"] = True
            return self.progress_info, "割り振りが完了しました。確認に進みます。"

        # 操作入力（例: 1 +1）
        parts = text.split()
        if len(parts) != 2:
            return self._reject("操作形式が無効です。例：1 +1", step=109)

        try:
            index = int(parts[0])
            change = int(parts[1])
        except ValueError:
            return self._reject("数字で指定してください。例：1 +1", step=109)

        skills = self.flags.get("_check_assignments", {})
        skill_names = list(skills.keys())

        if not (1 <= index <= len(skill_names)):
            return self._reject("スキル番号が範囲外です。", step=109)

        name = skill_names[index - 1]
        current_value = skills[name]
        new_value = current_value + change

        if not (-3 <= new_value <= 3):
            return self._reject("無効な範囲です。", step=109)


        skills[name] = new_value
        self.flags["_check_assignments"] = skills
        total = self._calculate_total_skill_cost(skills)
        self.flags["_check_total_cost"] = total

        return self._start_skill_distribution()

    def _confirm_skill_distribution(self) -> tuple[dict, str]:
        self.progress_info["step"] = 111
        self.progress_info["auto_continue"] = False

        skills = self.flags.get("_check_assignments", {})
        total_cost = self._calculate_total_skill_cost(skills)
        self.flags["_check_total_cost"] = total_cost

        lines = ["スキルの割り振りを確認してください："]

        for name, val in skills.items():
            lines.append(f"- {name}：{val:+d}")

        lines.extend([
            "",
            f"▶ 合計コスト：{total_cost} / 上限：12pt",
            "",
            "この内容でキャラクターを作成しますか？(使用しなかったポイントは持ち越せますが、シナリオ終了時まで振り直せません。)",
            "1. はい（確定して保存）",
            "2. いいえ（割り振りをやり直す）"
        ])

        return self.progress_info, "\n".join(lines)

    def _finalize_character(self, input_text: str) -> tuple[dict, str]:
        choice = unicodedata.normalize("NFKC", input_text.strip())

        if choice == "1":
            obj = self.flags.get("_char_generation_obj", {})
            skills = self.flags.get("_check_assignments", {})
            obj["checks"] = skills
            obj["tags"] = list(set(obj.get("tags", []) + ["PC"]))

            # 余ったポイントを growth_pool に保存
            total_cost = self._calculate_total_skill_cost(skills)
            point_limit = 12  # ここは持ち越し対応するなら self.flags.get("_point_limit", 12)
            obj["growth_pool"] = max(0, point_limit - total_cost)

            cm = self.ctx.character_mgr
            cm.set_worldview_id(self.wid)

            char_id = cm.create_character(
                name=obj.get("name", "無名キャラ"),
                data=obj,
                tags=obj["tags"]
            )
            obj["id"] = char_id
            self.flags["player_character"] = obj

            self.progress_info["step"] = 1
            self.progress_info["auto_continue"] = True
            return self.progress_info, f"キャラクター『{obj['name']}』（レベル{obj.get('level', '?')}）を作成しました。\n"

        elif choice == "2":
            self.progress_info["step"] = 108
            self.progress_info["auto_continue"] = True
            return self.progress_info, "スキルの割り振りをやり直します。"

        else:
            return self._reject("1 または 2 を入力してください。", step=110)
        


    def _ask_scenario_direction(self) -> tuple[dict, str]:
        pc = self.flags.get("player_character", {})
        wid = self.wid
        worldview = self.ctx.worldview_mgr.get_entry_by_id(wid)
        is_sequel = "sequel_to" in self.flags

        lines = []

        # 案内文（通常 or 続編）
        if is_sequel:
            lines.append("これは前回のセッションの続編です。")
            lines.append("これまでの物語を踏まえ、今回どのような展開を望むか自由に記述してください。")
            lines.append("テーマや雰囲気、スタイル、長さなどを指定できます。\n")

            # 前回要約の読み込み
            sid = self.flags.get("sequel_to")
            prev_path = self.ctx.session_mgr.get_summary_path(wid, sid)
            try:
                with open(prev_path, "r", encoding="utf-8") as f:
                    summary_text = f.read().strip()

                # 端折り処理：長すぎる場合は前半だけ抜粋
                if len(summary_text) > 500:
                    summary_text = summary_text[:450].rsplit("。", 1)[0] + "。…（以下略）"

                lines.append("\n▼ 前回のあらすじ：")
                lines.append(summary_text)

            except FileNotFoundError:
                lines.append("\n▼ 前回のあらすじは見つかりませんでした。")

        else:
            lines.append("セッションを開始する前に、物語の方向性を自由に記述してください。")
            lines.append("以下のような情報を含めていただけると、AIがより適切なシナリオを提案できます：\n")

        # 共通案内（続編でも表示）
        lines.append("・テーマ（例：復讐、成長、冒険、探索、陰謀など）")
        lines.append("・雰囲気（例：明るい、シリアス、陰鬱、コミカル、神秘的など）")
        lines.append("・進行スタイル（例：依頼型、自由探索型、事件解決型など）")
        lines.append("・長さ（以下から選択）")
        lines.append("　short：2～4章の短編")
        lines.append("　medium：5〜7章の中編")
        lines.append("　long：8～10章の長編")

        # プレイヤーキャラ情報
        lines.append("\n▼ 現在のキャラクター：")
        lines.append(f"名前：{pc.get('name', '不明')}（レベル{pc.get('level', '?')}）")
        if pc.get("summary"):
            lines.append(f"{pc['summary']}")
        elif pc.get("background"):
            lines.append(f"{pc['background']}")

        # 世界観情報
        lines.append("\n▼ 世界観：『" + worldview.get("name", "無名世界") + "』")
        description = worldview.get("description", "")
        if description:
            lines.append(description.strip())

        # 入力例
        lines.append("\n▼ 入力例：")
        lines.append("- 師匠の死の真相を探る物語にしたい。静かで神秘的な雰囲気。探索型の中編が理想。")
        lines.append("- とある村で起きた事件の裏に巨大な陰謀が隠されている。雰囲気はシリアスで、自由探索型。")
        lines.append("※ すべて記入する必要はありません。\n書かれていない項目については、AIがランダムまたは適切に補完してシナリオを提案します。")

        self.progress_info["step"] = 1001
        self.progress_info["auto_continue"] = False
        return self.progress_info, "\n".join(lines)


    def _handle_scenario_direction_input(self, input_text: str) -> tuple[dict, str]:
        self.progress_info["step"] = 1002
        self.progress_info["auto_continue"] = True

        system_content = (
            "あなたはTRPGのゲームマスター補助AIです。\n"
            "プレイヤーが記述した物語の希望から、次の4つの情報を推定してください：\n"
            "- theme（主題）例：復讐、成長、冒険、探索、陰謀、喪失、再会\n"
            "- tone（雰囲気）例：明るい、シリアス、陰鬱、コミカル、静か、神秘的\n"
            "- style（進行スタイル）例：依頼型、自由探索型、事件解決型、成り行き任せ、拠点運営型\n"
            "- length（short / medium / long のいずれか）\n\n"
            "theme / tone / style / length のうち、プレイヤーの記述に含まれていない要素は、自然な文脈に基づいて適切に補完してください。\n"
            "特に指定が見当たらない場合は、ランダムに選択して構いません。"
        )

        # 続編セッションなら、前回の要約を補完情報として追加
        sequel_from = self.flags.get("sequel_to")
        if sequel_from:
            wid = self.wid
            path = self.ctx.session_mgr.get_summary_path(wid, sequel_from)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    summary_text = f.read().strip()
                if len(summary_text) > 700:
                    summary_text = summary_text[:650].rsplit("。", 1)[0] + "。…（以下略）"

                system_content += (
                    "\n\nこのセッションは続編であり、前回のセッションは以下のような内容でした：\n"
                    f"{summary_text}\n"
                    "今回のプレイヤー入力に theme / tone / style / length の情報が不足している場合に限り、"
                    "この前回内容を参考にして自然な形で補完してください。"
                )
            except FileNotFoundError:
                pass

        prompt = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": input_text.strip()},
        ]

        try:
            # ★ 構造化出力で直接 dict を受ける。max_tokens→内部で変換される前提OK
            result = self.ctx.engine.chat(
                messages=prompt,
                caller_name="ScenarioMetaExtract",
                max_tokens=5000,
                schema=SCENARIO_META_SCHEMA,
            )

            meta = result if isinstance(result, dict) else {}

            # かるい妥当性チェック（足りなければreject）
            if not all(k in meta for k in ("theme", "tone", "style", "length")):
                return self._reject("シナリオの方向性を読み取れませんでした。もう一度入力してください。", step=1000)

            if meta.get("length") not in ("short", "medium", "long", "unlimited"):
                meta["length"] = "medium"

            self.flags["_scenario_meta"] = meta
            return self.progress_info, "シナリオ構成を作成中です…"

        except Exception:
            return self._reject("シナリオの方向性を読み取れませんでした。もう一度入力してください。", step=1000)

    def _review_generated_scenario(self) -> tuple[dict, str]:
        draft = self.flags.get("_scenario_draft", {})
        title = draft.get("title", "（タイトル不明）")
        summary = draft.get("summary", "（概要なし）")

        lines = []
        lines.append("シナリオの構成が生成されました。以下の内容で進めてもよろしいですか？\n")
        lines.append(f"■ タイトル：{title}")
        lines.append(f"■ 概要：{summary}")
        lines.append("\n1. この内容でセッションを開始する")
        lines.append("2. もう一度生成しなおす")
        lines.append("3. 最初からやり直す")

        self.progress_info["step"] = 1004
        self.progress_info["auto_continue"] = False
        return self.progress_info, "\n".join(lines)

    def _handle_scenario_generate(self, input_text: str) -> tuple[dict, str]:
        self.progress_info["step"] = 1003
        self.progress_info["auto_continue"] = True

        meta = self.flags.get("_scenario_meta", {})
        length = meta.get("length", "")
        pc = self.flags.get("player_character", {})
        wid = self.wid
        worldview = self.ctx.worldview_mgr.get_entry_by_id(wid)

        self.ctx.nouns_mgr.set_worldview_id(wid)
        nouns = self.ctx.nouns_mgr.entries
        worldview_description = worldview.get("description", "")
        worldview_name = worldview.get("name", "無名世界")
        summary = ""

        # 前回セッションの要約
        sequel_from = self.flags.get("sequel_to")
        if sequel_from:
            path = self.ctx.session_mgr.get_summary_path(wid, sequel_from)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    summary = f.read().strip()
                if len(summary) > 700:
                    summary = summary[:650].rsplit("。", 1)[0] + "。…（以下略）"
            except FileNotFoundError:
                summary = ""

        # nounsの整形
        noun_lines = []
        for noun in nouns:
            name = noun.get("name", "")
            desc = noun.get("description", "")
            noun_lines.append(f"- {name}：{desc}")

        # キャラ紹介＋履歴
        pc_desc = pc.get("background") or pc.get("summary") or "（説明なし）"
        history = pc.get("history", [])
        if history:
            history_lines = []
            for entry in history:
                if isinstance(entry, str):
                    history_lines.append(f"- {entry}")
                elif isinstance(entry, dict):
                    chapter = entry.get("chapter", "?")
                    text = entry.get("text", "")
                    history_lines.append(f"- 第{chapter}章: {text}")
            if history_lines:
                pc_desc += "\n\n▼ 過去の出来事:\n" + "\n".join(history_lines)

        # ユーザープロンプト組み立て
        user_parts = []
        user_parts.append(f"■ プレイヤーの希望：\n{input_text.strip()}")
        user_parts.append(f"\n■ メタ情報：")
        user_parts.append(f"- theme: {meta.get('theme', '不明')}")
        user_parts.append(f"- tone: {meta.get('tone', '不明')}")
        user_parts.append(f"- style: {meta.get('style', '不明')}")
        user_parts.append(f"- length: {length}")

        user_parts.append(f"\n■ 主人公キャラクター：")
        user_parts.append(f"名前：{pc.get('name', '???')}（レベル{pc.get('level', '?')}）")
        user_parts.append(pc_desc)

        user_parts.append(f"\n■ 世界観：『{worldview_name}』")
        if worldview_description:
            user_parts.append(worldview_description.strip())

        if noun_lines:
            user_parts.append("\n■ 世界観の要素：")
            user_parts.extend(noun_lines)

        if summary:
            user_parts.append("\n■ 前回のあらすじ（参考）：")
            user_parts.append(summary)

        user_prompt = "\n".join(user_parts)

        # システムプロンプト（JSON例は削除、説明だけ残す）
        system_parts = [
                "あなたはTRPGのゲームマスターAIです。以下の情報をもとに、物語全体の構成を生成してください。",
                "",
                "■ 出力形式（JSON）：",
                "{",
                '  "title": "シナリオのタイトル（10〜25文字、象徴的または詩的な表現とし、展開の核心を直接示さないようにしてください。）",',
                '  "summary": "物語の概要（150文字以内、物語の「真相」や「伏線の回収結果」などのネタバレを含めないでください。）",',
                '  "goal": "プレイヤーが最終的に達成すべき目標（具体的に！ぼんやりとした概要にならないように）",',
                '  "chapters": [',
                '    { "title": "章タイトル", "overview": "章の内容概要（150文字以上）" }, ...',
                "  ]",
                "}",
                "",
                "■ 各要素の定義：",
                "- theme（主題）：物語が扱う中心的なテーマ（例：復讐、喪失、再会）",
                "- tone（雰囲気）：全体の空気感や情緒（例：陰鬱、明るい、神秘的）",
                "- style（進行形式）：シナリオの構造や進め方（例：依頼型、事件解決型、自由探索型）",
                "- length（規模）：short = 3〜4章、medium = 5〜7章、long = 8章以上",
                "",
                "■ chapters の出力ルール：",
                '章構成は "chapters": [ ... ] というリスト形式で出力してください。',
                "章数は length に応じて決定してください：",
                " - short：2〜4章",
                " - medium：5〜7章",
                " - long：8章以上",
                "",
                "各章は次のような構造です：",
                '{ "title": "章のタイトル（詩的かつ内容を示唆）",',
                '  "goal": "その章を終了し、次の章に移る条件。それが最終章なら、最終的に迎えるべきエンディング。目標達成のための手段ではなく、目標そのものにすることを心がけ、かつ自由度を確保するために、ある程度の大雑把さも許容する。",',
                '  "overview": "プレイヤーが経験する展開（150文字程度）" }',
                "",
                "全体を通してプレイヤーキャラの行動が活きるような、かつその時々での行動目標がわかりやすい展開にしてください。セッションの最後の章には山場を用意し、達成感を得られるようにしてください。",
                "また、特別指定がない場合（戦闘はしたくない、会話中心のシナリオが良い等）を除いて、プレイヤーのレベルに合わせた戦闘も入れてください。",
                "章ごとのoverviewは、おおざっぱに目的を決定できる程度に記述してください。固有名詞（NPCやアイテム、地名など）を勝手に生成して登場させても構いません。",
                "",
                "■ レベルの意味：",
                "キャラクターには 0〜15 のレベルがあり、7以上は超人的、13以上は神話的です。",
                "シナリオ難易度や規模感をこのレベルに合わせて設計してください。基本的に、話のスケールは小さいほうがプレイヤーが把握しやすくていいです。",
                "",
                
                "最後に、これが最も重要ですが、地に足ついた、リアリティのあるシナリオを作ってください。はっきりとしない目標や、浮ついた展開は臨場感を欠きます。",
                "NPCを含め、確かにそこで生きていることを実感できる内容にしてください。PCはあくまで一キャラクターであり、（レベルにもよりますが）大きく特別な存在ではありません。",
                "また、PCの意思を勝手に決定しないでください。PCの自由意思の担保はTRPGにおいて前提です。その選択を誘導はしても勝手に定めてはいけません。",
                "",
                "あくまでソロ用のTRPGシナリオであり、進行もAIが行うため、過度なNPCの出演およびパーティー結成等は控えてください。制御しきれません。",               
            ]
        system_parts.append(
                "■ 設定カノン（canon_facts）の出力について：\n"
                "このシナリオで新たに明らかになる重要な設定（世界観・文化・歴史・信仰・人物背景など）や、キーとなるアイテムがあれば、それらを \"canon_facts\" フィールドとして最大5つまで出力してください。\n"
                "\n"
                "形式は以下のようにしてください：\n"
                "\"canon_facts\": [\n"
                "  {\n"
                "    \"name\": \"霧の村の結界\",\n"
                "    \"type\": \"地理\",\n"
                "    \"note\": \"村を覆う霧は、外界からの侵入を防ぐ古代の結界である。侵入しようとする人々を迷わせる形で働く。\"\n"
                "  },\n"
                "  {\n"
                "    \"name\": \"星霊信仰\",\n"
                "    \"type\": \"信仰・宗教\",\n"
                "    \"note\": \"この地域では死者の魂は星になると信じられており、夜空の観察が重要な儀式となっている。\"\n"
                "  }\n"
                "]\n"
                "\n"
                "- name: 一文のラベル（名詞的・記憶に残りやすい形式）\n"
                "- type: 以下から選んでください：\n"
                "    ・場所（町、遺跡、ダンジョンなどの具体的な地理的地点）\n"
                "    ・NPC（登場人物。名前があるキャラクター）\n"
                "    ・知識（歴史、文化、宗教、信仰、技術、伝承など背景設定）\n"
                "    ・アイテム（武器、道具、遺物など重要な物品）\n"
                "    ・ギミック（仕掛け、封印、装置、トラップなどのプレイヤーの障害　noteにはその解除方法も必ず追記する）\n"  
                "    ・その他（上記に当てはまらないが記録すべきもの）\n"
                "- note: その内容を100字程度で自然文として説明（特にアイテムの場合は、その形や大きさ、具体的な持っている力などをわかりやすく）\n"
                "\n"
                "重要な設定が存在しない場合は空リストで構いません。**世界観の要素として渡している内容と同等のものは、設定し直さないでください。**混乱の元となります。"
            )

        prompt = [
            {"role": "system", "content": "\n".join(system_parts)},
            {"role": "user", "content": user_prompt}
        ]

        try:
            result = self.ctx.engine.chat(
                messages=prompt,
                caller_name="ScenarioGenerator",
                model_level="very_high",   # reasoning強すぎない設定
                max_tokens=20000,     # 内部でmax_output_tokens化される
                schema=SCENARIO_DRAFT_SCHEMA
            )
            scenario = result if isinstance(result, dict) else {}
            self.flags["_scenario_draft"] = scenario
            return self.progress_info, "シナリオ構成を生成しました。"

        except Exception:
            return self._reject("シナリオの生成に失敗しました。入力内容を見直してください。", step=1000)







    def _handle_scenario_review_choice(self, input_text: str) -> tuple[dict, str]:
        choice = unicodedata.normalize("NFKC", input_text.strip())

        if choice == "1":
            wid = self.wid
            pc = self.flags.get("player_character")
            draft = self.flags.get("_scenario_draft", {})
            meta = self.flags.get("_scenario_meta", {})
            raw_input = self.flags.get("raw_input", "")
            sequel_from = self.flags.get("sequel_to")

            # プレイヤーキャラID
            pcid = pc.get("id")

            # 📦 タイトル取得（空文字許容）
            title = draft.get("title", "")

            # ✅ セッションIDの発行
            if sequel_from:
                sid = self.ctx.session_mgr.clone_session_as_sequel(
                    old_sid=sequel_from,
                    new_title=title
                )
            else:
                sid = self.ctx.session_mgr.new_session(
                    worldview_id=wid,
                    title=title,
                    player_character_id=pcid
                )

            # ✅ 構成情報の保存（canon_facts を除外した draft を使う）
            draft_copy = draft.copy()
            draft_copy.pop("canon_facts", None)  # ← canon は別保存なので除去

            self.ctx.session_mgr.save_scenario_data(
                worldview_id=wid,
                session_id=sid,
                meta=meta,
                draft=draft_copy,
                raw_input=raw_input
            )


            # シナリオからカノン（設定事実）を保存
            canon_facts = draft.get("canon_facts", [])
            if canon_facts:
                canon_mgr = self.ctx.canon_mgr
                canon_mgr.set_context(wid, sid)
                for fact in canon_facts:
                    try:
                        canon_mgr.create_fact(
                            name=fact.get("name", "名称未設定"),
                            type=fact.get("type", "その他"),
                            notes=fact.get("note", ""),
                            chapter=0  # シナリオ生成時は0章として扱う
                        )
                    except Exception as e:
                        self.ctx.ui.safe_print("System", f"カノン保存失敗: {fact.get('name', '?')} - {e}")


            self.progress_info["phase"] = "session_resume"
            self.progress_info["step"] = 0
            self.progress_info["flags"] = {
                "id": sid,
                "worldview_id": wid
            }
            self.progress_info["auto_continue"] = True
            return self.progress_info, f"セッション『{title or '無題'}』を開始します。"

        elif choice == "2":
            self.progress_info["step"] = 1002
            self.progress_info["auto_continue"] = True
            return self.progress_info, "もう一度シナリオを生成し直します。"

        elif choice == "3":
            self.progress_info["step"] = 0
            self.progress_info["auto_continue"] = True
            return self.progress_info, "最初からやり直します。"

        else:
            return self._reject("1〜3の番号で入力してください。", step=1004)

    def _reject(self, message: str, step: int) -> tuple[dict, str]:
        self.progress_info["step"] = step
        self.progress_info["flags"] = self.flags
        return self.progress_info, message

