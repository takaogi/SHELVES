# phases/session_create.py
import unicodedata
import json
import random
from infra.path_helper import get_data_path

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
                        "notes": {"type": "string","minLength": 50}
                    },
                    "required": ["name", "type", "notes"],
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
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "count": {"type": "integer", "minimum": 0},
                        "description": {"type": "string"}
                    },
                    "required": ["name", "count", "description"],
                    "additionalProperties": False
                }
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
    "15": ("items", "所持品（装備や個人的な持ち物など）※非対応"),
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
            
            # 🆕 AI修正ステップ
            case 112:
                return self._ask_ai_correction()
            case 113:
                return self._handle_ai_correction(input_text)
                        

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

        # 新しいキャラクター作成
        lines.append(f"\n{idx}. 新しいキャラクターを作成する")
        self.flags["_new_character_index"] = idx
        idx += 1

        # 🆕 セッション選択に戻る
        lines.append(f"{idx}. セッション選択に戻る")
        self.flags["_return_to_session_select"] = idx

        self.flags["_index_map"] = index_map
        self.progress_info["step"] = 2
        return self.progress_info, "\n".join(lines)


    def _handle_character_selection(self, input_text: str) -> tuple[dict, str]:
        try:
            choice = int(unicodedata.normalize("NFKC", input_text.strip()))
        except ValueError:
            return self._reject("数字で入力してください。", step=2)

        index_map = self.flags.get("_index_map", {})
        new_index = self.flags.get("_new_character_index")
        return_index = self.flags.get("_return_to_session_select")

        if choice == new_index:
            self.progress_info["step"] = 100
            self.progress_info["auto_continue"] = True
            return self.progress_info, "新しいキャラクターを作成します。"

        elif choice == return_index:
            self.progress_info["phase"] = "session_select"
            self.progress_info["step"] = 0
            self.progress_info["auto_continue"] = True
            return self.progress_info, "セッション選択に戻ります。"

        elif choice in index_map:
            selected = index_map[choice]
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
            lines.append("") 

        examples = [
            "無口で優しい巨人族の少女。村を襲った魔獣に家族を殺され、今は放浪している…",
            "若くして隊長となった熱血漢の人間剣士。失踪した師匠を探している。",
            "古代図書館を守る機械仕掛けの司書。失われた言語を解読するのが使命。",
            "魔術師の家系に生まれながら魔法が全く使えず、錬金術で道を切り開く青年。",
            "海底都市出身の半魚人探検家。地上の文化に強い好奇心を持つ。",
            "放浪する吟遊詩人。歌で人々の心を癒やしつつ、失われた王国の真実を追う。",
            "盗賊団の元一員。裏切られ、今は各地で正義のために暗躍している。",
            "伝説の鍛冶師の弟子。師の遺した未完の武具を完成させるため旅立つ。",
            "千年眠っていた古代竜。人間の姿で現代社会に溶け込もうとしている。",
            "極北の村で育った狩人。未知の雪原を越える航路を探している。",
            "砂漠の遊牧民出身の弓使い。部族を襲った疫病の治療法を求めて旅する。",
            "辺境の修道院育ちの修道女。神の声を聞くとされるが本人は懐疑的。",
            "廃墟都市を根城とする孤高のガンスリンガー。",
            "幻影を操る芸術家。自らの作品に隠された呪いを解こうとしている。",
            "嵐の精霊に選ばれた水夫。暴風雨を自在に操るが代償を恐れている。",
            "地下迷宮に生まれた獣人戦士。地上の世界を見たことがない。",
            "森の奥に棲む薬草師。幻の花を探し求めている。",
            "王都のスラム出身の情報屋。裏社会と貴族社会を渡り歩く。",
            "竜騎士団の唯一の生き残り。竜の卵を守り続けている。",
            "異国から来た旅商人。珍品収集と商売のため危険地帯にも足を踏み入れる。",
            "不死の呪いを受けた剣士。死を取り戻す方法を探している。",
            "炎の魔術を操る傭兵。過去に町を焼き払った罪を背負っている。",
            "氷山を漂う研究船の科学者。大陸の彼方の未知生物を探している。",
            "毒草に精通した暗殺者。標的を狙う理由は復讐でも金でもない。",
            "森羅万象と会話できると信じる放浪の預言者。",
            "巨大な盾を操る防衛専門の兵士。仲間を失ったトラウマを抱える。",
            "修理屋を営むアンドロイド。旧時代の記憶を断片的に取り戻している。",
            "魔法楽器を持つ吟遊詩人。演奏には精神を削る代償が伴う。",
            "海賊船から逃げ出した航海士。再び海へ戻る理由を探している。",
            "地下水路の案内人。都市の暗部と光を知り尽くす。",
            "失われた文明の遺児。自分のルーツを求める旅人。",
            "月の祭司として育った巫女。地上の世界を巡礼している。",
            "怪物退治を生業とする一族の末裔。己の役目に葛藤している。",
            "人間に化けた妖狐。百年後の約束を果たすため現れた。",
            "海辺の灯台守。嵐の夜に現れる亡霊船を目撃する。",
            "砂嵐を呼ぶ呪いを受けた放浪者。",
            "精霊契約を失った魔法使い。新たな契約相手を探している。",
            "天空都市から落ちてきた失意の貴族。",
            "光と闇の二重人格を持つ戦士。",
            "不完全なゴーレム。人間になりたいと願っている。",
            "大図書館の地下に幽閉された亡国の王子。",
            "樹海の奥で目覚めた記憶喪失の少女。",
            "黒猫と共に旅する放浪の錬金術師。",
            "嵐の夜に生まれた子。雷鳴と共鳴する力を持つ。",
            "全ての色を失った画家。世界に色を取り戻そうとしている。",
            "影の世界から迷い出た少年。",
            "鉄仮面を外せない呪いを持つ騎士。",
            "雪原を渡る郵便配達人。世界の果てまで手紙を届ける。"
        ]

        lines.append("あなたが演じるキャラクターの概要を自由に記述してください。")
        sampled = random.sample(examples, 3)
        lines.append("▼ 例：\n" + "\n".join(f"- {ex}" for ex in sampled))

        return self.progress_info, "\n".join(lines)

    
    def _generate_character_from_input(self, input_text: str = "") -> tuple[dict, str]:
        long_desc = self.flags["worldview"].get("long_description", "")
        player_input = input_text.strip()
        self.ctx.nouns_mgr.set_worldview_id(self.wid)
        nouns = self.ctx.nouns_mgr.entries[:15]
        readable_nouns = "\n".join(
            f"- {noun['name']}（{noun['type']}）：{noun.get('notes', '')}"
            for noun in nouns
        )

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
            "- items: 所持品のリスト。各要素は以下のフィールドを含めます：\n"
            "    - name: アイテム名（例：家族の形見のペンダント、魔法の杖、旅人の背嚢）。\n"
            "    - count: 所持数（整数、例：1, 3など）。\n"
            "    - description: アイテムの簡単な説明（例：銀細工の古びたペンダント、先端に宝石が嵌め込まれた杖）。\n"
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
            f"▼ 固有名詞一覧:\n{readable_nouns}\n\n"
            f"▼ プレイヤーの記述:\n{player_input}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        result = self.ctx.engine.chat(
            messages=messages,
            caller_name="AutoCharacter",
            model_level="very_high",
            max_tokens=5000,
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
                            if isinstance(it, str):
                                # 旧仕様：単なる文字列
                                lines.append(f"- {it}")
                            elif isinstance(it, dict):
                                name = it.get("name", "")
                                count = it.get("count", 0)
                                desc = it.get("description", "")
                                if desc:
                                    lines.append(f"- {name} ×{count}：{desc}")
                                else:
                                    lines.append(f"- {name} ×{count}")
                            else:
                                lines.append(f"- {str(it)}")  # 念のため
                    else:
                        # 旧仕様：単一文字列
                        lines.append(f"所持品: {value}")
                else:
                    lines.append(f"{label}: {value}")


        used_nouns = obj.get("used_nouns", [])
        if used_nouns:
            lines.append("\n▼ 使用された固有名詞：")
            for noun in used_nouns:
                lines.append(f"- {noun.get('name', '')}（{noun.get('type', '')}）: {noun.get('note', '')}")

        lines.append("\nこのキャラクターで作成しますか？")
        lines.append("1. はい（レベル設定へ）\n2. 修正したい\n3. 別のキャラを再生成する\n4. AIに修正を依頼する")

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
        
        elif choice == "4":
            self.progress_info["step"] = 112
            self.progress_info["auto_continue"] = True
            return self.progress_info, "AIに修正を依頼します。"

        else:
            return self._reject("1〜4のいずれかを入力してください。", step=103)
   
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

        # 🆕 items の場合は AI 修正へ誘導
        if field == "items":
            self.progress_info["step"] = 102
            self.progress_info["auto_continue"] = True
            return self.progress_info, (
                "所持品の修正は手動編集に対応していません。\n"
                "AIによる修正を利用してください。\n"
            )

        # 通常フィールド
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
        
#キャラクターAI修正
    def _ask_ai_correction(self) -> tuple[dict, str]:
        self.progress_info["step"] = 113
        return self.progress_info, "修正内容を短く入力してください（例：『名前を日本風に』、『弱点を追加』など）。"
            

    def _handle_ai_correction(self, input_text: str) -> tuple[dict, str]:
        obj = self.flags.get("_char_generation_obj")
        if not obj:
            return self._reject("キャラクター情報がありません。", step=102)

        long_desc = self.flags["worldview"].get("long_description", "")
        self.ctx.nouns_mgr.set_worldview_id(self.wid)
        nouns = self.ctx.nouns_mgr.entries[:15]
        readable_nouns = "\n".join(
            f"- {n['name']}（{n['type']}）：{n.get('notes','')}" for n in nouns
        )

        system_prompt = (
            "あなたはTRPGのキャラクター修正アシスタントです。\n"
            "以下の世界観説明・固有名詞・既存キャラクターデータを基に、\n"
            "ユーザーの修正指示に従ってキャラクターを調整してください。\n"
            "修正しない部分はそのまま残し、必ず完全なキャラクターJSONを返してください。\n\n"
            "【出力仕様】CHARACTER_GENERATION_SCHEMA に準拠してください。\n\n"
            "▼ 各フィールドの説明：\n"
            "- name: 名前\n"
            "- tags: PCを含む分類タグ\n"
            "- gender: 性別\n"
            "- age: 年齢\n"
            "- race: 種族\n"
            "- origin: 出身地\n"
            "- occupation: 職業\n"
            "- personality: 性格\n"
            "- appearance: 容姿\n"
            "- physique: 体格\n"
            "- abilities: 能力\n"
            "- weaknesses: 弱点\n"
            "- likes: 好きなもの\n"
            "- dislikes: 苦手なもの\n"
            "- items: 所持品（{name,count,description}）\n"
            "- beliefs: 信条\n"
            "- summary: 一言紹介\n"
            "- background: 背景\n"
            "- notes: 備考\n"
            "- used_nouns: 使用した固有名詞\n"
        )

        user_prompt = (
            f"▼ 世界観の説明:\n{long_desc}\n\n"
            f"▼ 固有名詞一覧:\n{readable_nouns}\n\n"
            f"▼ 現在のキャラクター情報:\n{json.dumps(obj, ensure_ascii=False, indent=2)}\n\n"
            f"▼ ユーザーの修正指示:\n{input_text.strip()}"
        )

        result = self.ctx.engine.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            caller_name="AutoCharacterCorrection",
            model_level="very_high",
            max_tokens=5000,
            schema=CHARACTER_GENERATION_SCHEMA,
        )

        if isinstance(result, dict):
            self.flags["_char_generation_obj"] = result
            self.progress_info["step"] = 102
            self.progress_info["auto_continue"] = True
            return self.progress_info, "AIによる修正が完了しました。確認画面に戻ります。"
        else:
            return self._reject("AI修正に失敗しました。", step=102)
        

#セッション作成

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

        # 入力例（複数候補からランダム表示）
        scenario_examples = [
            "師匠の死の真相を探る物語にしたい。静かで神秘的な雰囲気。探索型の中編が理想。",
            "とある村で起きた事件の裏に巨大な陰謀が隠されている。雰囲気はシリアスで、自由探索型。",
            "古代遺跡を巡る冒険譚。明るく爽快な雰囲気で、依頼型の短編が良い。",
            "戦乱に巻き込まれた辺境の村を守る物語。緊張感のある戦闘中心の中編。",
            "不思議な森に迷い込んだ旅人。幻想的で静かな雰囲気。探索型の短編。",
            "王都の裏社会で起きた連続失踪事件を追う。陰鬱で緊迫した雰囲気。事件解決型。",
            "廃墟都市の再建を目指す拠点運営型シナリオ。希望と再生の物語。",
            "暴走した魔導兵器を止めるため各地を巡る。ハイテンポでコミカルな短編。",
            "砂漠を横断する交易隊の護衛任務。過酷な環境下のサバイバル要素あり。",
            "古代の予言に従い七つの秘宝を集める。壮大で神話的な長編。",
            "孤島の村で行われる祭りの裏に隠された秘密を暴く。ミステリアスな中編。",
            "海賊と同盟を結び、失われた財宝を探す。陽気で冒険心あふれる短編。",
            "怪物が跋扈する山岳地帯を越えて使者を届ける。危険な旅路の中編。",
            "夜ごと現れる幽霊屋敷の謎を解く。ホラー調の短編。",
            "巨大な迷宮を攻略する依頼。戦闘と探索半々の長編。",
            "反乱軍の指導者暗殺計画を阻止する。緊張感ある潜入型の短編。",
            "呪われた湖の浄化。静かで美しいが不穏な雰囲気の中編。",
            "空に浮かぶ都市への潜入。異世界感のある長編。",
            "失踪した友人を追って異国へ旅立つ。情緒的で感傷的な中編。",
            "暴虐な領主を倒し、領地を解放する。王道の英雄譚型長編。",
            "禁書庫に眠る古文書を奪還する。知略重視の短編。",
            "星降る夜に現れる魔獣を討伐する。神秘的で詩的な短編。",
            "海底神殿に眠る秘宝を奪い返す。息を呑むような景観の中編。",
            "悪夢に囚われた人々を救うため夢の世界へ潜る。幻想的な長編。",
            "無人の城塞都市を再建する拠点運営型シナリオ。",
            "季節が1日ごとに巡る土地を旅する。不思議で鮮やかな中編。",
            "災厄を封じた古の封印が破られる瞬間に立ち会う。緊迫感ある長編。",
            "辺境の鉱山町で起きた怪異の調査。事件解決型の短編。",
            "過去に飛ばされ歴史の分岐点を目撃する。タイムリープ型中編。",
            "森の奥で失われた村を探す。探索型の短編。",
            "天空にそびえる塔を登りきる試練。長編の冒険譚。",
            "大陸横断レースに挑む。コミカルかつスリリングな短編。",
            "古代兵器を巡る諜報戦。陰謀渦巻く中編。",
            "死者の魂と交信できる霊媒師の物語。神秘的で静かな短編。",
            "各地の魔法大会を制覇する旅。明るく活気ある中編。",
            "嵐の中で消えた飛行船を追う。スチームパンク調の長編。",
            "異世界からの漂流者を送り返す方法を探す。感傷的な短編。",
            "巨大な竜を討伐する使命を帯びた戦士団。王道バトル型長編。",
            "夢と現実が交錯する都市の謎を解く。幻想的な中編。",
            "未知の島を開拓する。サバイバルと拠点運営要素の長編。",
            "水没した都市から財宝を引き上げる。危険な潜水作業の短編。",
            "光を失った大地を再び照らす方法を探す。神話的な長編。",
            "魔法災害で崩壊した地方の復興を描く。希望の物語。",
            "全ての音を奪われた村を救う。幻想的な短編。",
            "時を止められた城を解放する。中編の冒険譚。",
            "凍りついた湖の底に眠る秘密を暴く。神秘的な短編。",
            "悪魔と契約した王の暴走を止める。陰鬱な長編。",
            "燃え尽きた森を蘇らせるための旅。再生の物語。"
        ]

        sampled = random.sample(scenario_examples, 3)
        lines.append("▼ 例：\n" + "\n".join(f"- {ex}" for ex in sampled))

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
        total_chapters = draft.get("total_chapters")

        lines = []
        lines.append("シナリオの構成が生成されました。以下の内容で進めてもよろしいですか？\n")
        lines.append(f"■ タイトル：{title}")
        lines.append(f"■ 概要：{summary}")
        if total_chapters is not None:
            lines.append(f"■ 全{total_chapters}章構成")

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
        worldview_description = worldview.get("long_description", "")
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
            type_ = noun.get("type", "")
            desc = noun.get("notes", "")
            noun_lines.append(f"- {name}（{type_}）：{desc}")


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

        # --- 前回から引き継ぐ設定要素（続編用 canon） ---
        sequel_from = self.flags.get("sequel_to")
        if sequel_from:
            sequel_path = get_data_path(f"worlds/{wid}/sessions/{sequel_from}/canon_sequel.json")
            if sequel_path.exists():
                try:
                    with open(sequel_path, encoding="utf-8") as f:
                        sequel_canon = json.load(f)
                    if sequel_canon:
                        user_parts.append("\n■ 前回から引き継ぐ設定要素（続編用 canon）：")
                        for c in sequel_canon:
                            name = c.get("name", "")
                            type_ = c.get("type", "")
                            note = c.get("note", "")
                            user_parts.append(f"- {name}（{type_}）：{note}")
                except Exception as e:
                    self.log.warning(f"続編 canon の読み込み失敗: {e}")

        if summary:
            user_parts.append("\n■ 前回のあらすじ（参考）：")
            user_parts.append(summary)

        user_prompt = "\n".join(user_parts)

        # システムプロンプト（JSON例は削除、説明だけ残す）
        system_parts = [
"""
あなたはTRPGのゲームマスターAIです。以下の情報をもとに、物語全体の構成を生成してください。

■ 出力形式（JSON）：
{
  "title": "シナリオのタイトル（10〜25文字。象徴的/詩的。真相を直示しない）",
  "summary": "物語の概要（150文字以内。ネタバレ厳禁）",
  "goal": "プレイヤーが最終的に到達すべき最終目標（方法ではなく“結果/到達状態”のみ。30字前後で特定）",
  "chapters": [
    { "title": "章タイトル", "goal": "章の到達点（結果のみ）", "overview": "章の展開（150字以上）" },
    { ... }
  ]
}

■ 用語定義：
- theme（主題）：物語の中心（例：復讐、喪失、再会）
- tone（雰囲気）：空気感（例：陰鬱、明るい、神秘的）
- style（進行）：構造（例：依頼型、事件解決型、自由探索型）
- length：short / medium / long

■ 章数ガイド：length に応じて章数を決めること
- short：2〜4章
- medium：5〜7章
- long：8〜10章

■ ゴール設計の特例
- short：中間ゴールは設けず、直接最終ゴールを逆算してよい。クライマックスは最終ゴールに統合される。
- medium：最終ゴールの前に「中間ゴール」を1つ設けること。
  ・中間ゴールは全体ゴールに至るための必須条件であり、物語上の最初のクライマックスとなる明確な到達点とする。
  ・章ごとのゴールは「中間ゴールまで」と「中間ゴールから最終ゴールまで」の二部構成で設計する。
- long：最終ゴールの前に「中間ゴール」を2つ設けること。
  ・「第1中間ゴール」「第2中間ゴール」を配置し、三幕構成のクライマックスを形成する。
  ・各中間ゴールはいずれも物語を次段階へ移す決定的な到達点であり、単なる通過点ではなく必ず山場である。
  ・章ごとのゴールはそれらを支える形で設計する。

■ 整合性（最重要）
- まずシナリオ全体の "goal" を短く確定し、その後に各章の "goal" を逆算（バックキャスティング）で設計すること。
- 各章の "goal" は「その章を終えたと誰の目にも明確な“結果”」を一文で示すこと。手段・工程・チェックリスト化は禁止。
- 各章の "goal" を1章目から順にすべて達成すれば、論理的にシナリオ全体の "goal" が満たされる構造にすること。
- 最終章の "goal" はシナリオ全体の "goal" と実質同義の幕引き状態を短く特定すること。
- 中間ゴールは必ずクライマックスである。到達によって物語の段階が明確に切り替わるよう設計すること。

■ 章オブジェクトの要件：
{
  "title": "詩的に示唆（真相は直示しない）",
  "goal": "状態変化を示す到達点（方法を書かない/15〜30字目安/チェックリスト禁止）",
  "overview": "150字以上。舞台/緊張/関与者の“気配”を示し、解法は断定しない"
}

▼ goal の良い例 / 悪い例：
- 良い例：
  ・「井戸の底に到達し、秘鍵を入手する」
  ・「北門から街を無事に出発する」
  ・「祭壇の封印を解除する」
  ・「連続失踪の犯人を特定する」
- 悪い例（手段の列挙/工程の羅列）：
  ・「潜る道具を準備し、井戸の様子を確認し、底にたどり着き…」
  ・「受付で依頼を受け、情報収集し、道具を揃えて出発する」
- 悪い例（メタで曖昧）：
  ・「依頼の真正性を確証し出立を正当化できた」
  ・「森の呪いの正体を掴み打開策が見えた」

■ “予想外の事態”の扱い（自由度確保のための方針）：
- 章の "goal"（結果）は揺らさない。揺れるのは「到達手段」「必要前提」「代償/コスト」の側。
- 章の "overview" に“予想外の事態”が起こり得る余白を残し、断定は避ける（伏せ語・示唆で十分）。
- シナリオの tone / style に適合する場合のみ、全体のどこかで“マクロな意外性”の導入を検討してよい（任意・必須ではない）。
  ・候補（中盤付近）：利害/前提の反転（協力者の離反、動機の再解釈 など）
  ・候補（終盤手前〜冒頭）：制約の急変（時間/資源/道徳的トレードオフ など）
- 採用時も "goal" は固定のまま、経路や必要条件、支払いが変化する設計に留めること。

■ タイトル生成方針：
- シナリオタイトルと章タイトルは同一の命名パターン系統を用いるが、役割を分ける。
  - シナリオタイトル：物語全体を象徴する抽象度の高い表現（核心やテーマを暗示）
  - 章タイトル：シナリオタイトルの雰囲気を引き継ぎつつ、その章固有の舞台や出来事を示す具象的な表現
- 例（名詞句型の場合）：
  - シナリオタイトル：「深海の記憶」 → 章タイトル：「沈む珊瑚礁の街」「波間に消えた灯台」
- 例（名詞連続型の場合）：
  - シナリオタイトル：「月夜と鉄と硝子のかけら」 → 章タイトル：「霧と骨と銀の都」「星と影と夜明けの門」

【命名パターン一覧（8系統）】
1. 名詞句型  
  例：「深海の記憶」「雪に閉ざされた約束」「黄昏の果樹園」「遠雷の王宮」「星屑の舟歌」
2. 動詞連体型  
  例：「沈まぬ月を追いかけて」「忘れられた名を呼ぶとき」「海を越えて光を探す」
3. 熟語拡張型（漢字2〜4字＋修飾/二段構造）  
  例：「紅蓮迷宮の肖像」「虚無回廊を渡る影」「星霜殿の末裔」「夢幻峡を越えて」
4. 比喩型（二項対比）  
  例：「黒い太陽、白い影」「鳥籠に降る星屑」「氷原と火の花」「森の底、海の上」
5. 名詞連続型（長音リズム：「〇〇と〇〇と〇〇〇〇〇」）  
  例：「月夜と鉄と硝子のかけら」「風と灰と真珠の瞳」「水と炎と忘却の街」
6. 疑問・呼びかけ型  
  例：「きみは灯を見つけられるか」「誰が夜を殺したのか」「そこに海はあったか」
7. 時・季節型  
  例：「冬至の檻」「三日月の約束」「春告鳥の消える夜」「夏至祭の灯火」
8. 叙事詩型（〜の物語／〜記／〜譚）  
  例：「白鯨の譚」「七つの門の記録」「灰色の都の物語」「双頭竜の年代記」

■ 戦闘/NPC/運用制約：
- 戦闘はプレイヤーレベル・tone・styleに適合する場合のみ自然に挿入（必須ではない）。
- ソロ運用ゆえ、NPCの数と絡みは最小限で役割を明瞭に。パーティ結成は原則避ける。
- PCの意思決定を勝手に確定しない。『選びを誘導』は可だが『確定』は不可。

■ レベルの意味（参照）：
0：一般人 / 1〜3：見習い / 4〜6：一人前 / 7〜10：超人的 / 11〜13：伝説級 / 14〜15：神話級
話のスケール感はPCレベルとtoneに合わせ、把握しやすい小さめの単位を基本とする。

■ 品質基準：
- 地に足のついたリアリティ。ふわっとした目標は不可。
- 固有名詞は生成可。ただし世界観に齟齬なく、数を絞り、役割を明瞭に。
"""
]



        system_parts.append(
    """
■ 設定カノン（canon_facts）の出力について：
このシナリオで新たに明らかになる重要な設定（世界観・文化・歴史・信仰・人物背景など）や、
キーとなるアイテムがあれば、それらを "canon_facts" フィールドとして最大5つまで出力してください。

形式は以下のようにしてください：
"canon_facts": [
  {
    "name": "霧の村の結界",
    "type": "場所",
    "note": "村を覆う霧は、外界からの侵入を防ぐ古代の結界である。侵入しようとする人々を迷わせる形で働く。"
  },
  {
    "name": "星霊信仰",
    "type": "知識",
    "note": "この地域では死者の魂は星になると信じられており、夜空の観察が重要な儀式となっている。"
  }
]

- name: 一文のラベル（名詞的・記憶に残りやすい形式）
- type: 以下から選んでください：
    ・場所（都市、村、遺跡、ダンジョン、建物、地域、自然地形、異界など具体的な地理的地点）
    ・人物（名前を持つNPC、神格、固有名の魔王や賢者、特定個体の怪物や英雄など）
    ・組織（国家、宗教、ギルド、一族、派閥、軍、会社など集団組織）
    ・種族（エルフやドワーフなどの種族、動物、魔物、アンデッド、人工生命など）
    ・物品（武器、道具、乗り物、遺物、財宝、文書、鍵など重要なアイテム）
    ・知識（伝承、歴史、文化、宗教教義、技術、魔法体系、法律、習俗など背景設定）
    ・ギミック（罠、装置、結界、封印、祭具、遺跡の機構など、このシナリオ内でのみ登場し解除や操作が必要な要素）
    ・現象（呪い、災厄、異常気象、魔力の渦など継続的または一時的に発生する事象）
    ・出来事（戦争、儀式、事件、探索行、反乱、条約、祭りなど特定の期間や場面の出来事）
- note: その内容を100字程度で自然文として説明（特に物品の場合は、その形や大きさ、具体的な持っている力などをわかりやすく）

重要な設定が存在しない場合は空リストで構いません。
**世界観の要素として渡している内容と同等のものは、設定し直さないでください。** 混乱の元となります。
"""
)


        prompt = [
            {"role": "system", "content": "\n".join(system_parts)},
            {"role": "user", "content": user_prompt}
        ]

        try:
            result = self.ctx.engine.chat(
                messages=prompt,
                caller_name="ScenarioGenerator",
                model_level="very_high", 
                max_tokens=8000, 
                schema=SCENARIO_DRAFT_SCHEMA
            )
            scenario = result if isinstance(result, dict) else {}
            total_chapters = len(scenario.get("chapters", []))
            scenario["total_chapters"] = total_chapters
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
                            notes=fact.get("notes", ""),
                            chapter=0  # シナリオ生成時は0章として扱う
                        )
                    except Exception as e:
                        self.ctx.ui.safe_print("System", f"カノン保存失敗: {fact.get('name', '?')} - {e}")


            # 前作から引き継いだ canon_sequel も保存
            if sequel_from:
                sequel_path = get_data_path(f"worlds/{wid}/sessions/{sequel_from}/canon_sequel.json")
                if sequel_path.exists():
                    try:
                        with open(sequel_path, encoding="utf-8") as f:
                            sequel_canon = json.load(f)
                        canon_mgr.set_context(wid, sid)
                        for fact in sequel_canon:
                            try:
                                canon_mgr.create_fact(
                                    name=fact.get("name", "名称未設定"),
                                    type=fact.get("type", "その他"),
                                    notes=fact.get("note", ""),  # sequelは note キー
                                    chapter=0
                                )
                            except Exception as e:
                                self.ctx.ui.safe_print("System", f"続編カノン保存失敗: {fact.get('name', '?')} - {e}")
                    except Exception as e:
                        self.ctx.ui.safe_print("System", f"続編カノン読み込み失敗: {e}")

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

