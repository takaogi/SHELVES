# phases/scenario/intent_router.py

from typing import Literal

from infra.logging import get_logger

log = get_logger("IntentRouter")



IntentLabel = Literal[
    "action", "talk", "info_request", "gm_query",
    "system", "invalid", "other"
]

CATEGORIES = [
    "action", "info_request", "gm_query", "system", "invalid", "other"
]

INTENT_SCHEMA = {
    "type": "json_schema",
    "name": "IntentCategory",
    "schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": CATEGORIES
            }
        },
        "required": ["category"],
        "additionalProperties": False
    }
}

SYSTEM_PROMPT = (
    "あなたはTRPG支援AIです。以下に示す会話の履歴（AssistantとUserのやりとり）をもとに、\n"
    "直近のプレイヤー発言（最後のUserの発言）について、その意図を以下の6カテゴリのいずれかに分類してください。\n\n"
    "【分類カテゴリと定義】\n"
    "- action: キャラクターが能動的に行おうとしている行動や操作全般。スキル使用、発言や呼びかけなどの会話も含む。返答としての了承・拒否もこれに含める。\n"
    "  （例: 「扉を開ける」「調べる」「隠れる」「説得を振ります」「回避振っていいですか？」「こんにちは」「誰かいますか？」「その男に話しかける」など）\n"  
    "- info_request: 周囲の状況や現状に対する質問（例: 「机の上に何が見える？」「今どういう状況？」「今何持ってたっけ」など）\n"
    "- gm_query: シーンや判定、進行方針などGM側の処理に関する質問（例: 「なんで〈探知〉？」「これってイベント？」「さっきそのアイテム拾ったよ」など）\n"
    "- system: セーブ、中断、ルールの確認などシステム的操作・情報要求　行為判定用のスキルについての質問（例: 「セーブしたい」「判定ってどうやるの？」「スキルって何があるの？」など）\n"
    "- invalid: 発言が意味不明・途中で切れてる・ノイズ・構文不明 （例:「助走をつけてｚ」 「あああ」「……」「oo」など 迷ったらこれでいい）\n"
    "- other: 感想、雑談、意図的行動に該当しない発言（例: 「この村いいな」「怖くなってきた」など）\n\n"
    "※ 分類すべきは最後のPlayerの発言だけです。それ以前の文脈も参考にして構いません。疑問形だから質問、断定しているから行動などと一意に判別せず、文脈から適切なカテゴリへ分類してください。"
)

def classify_intent(ctx, input_text: str, convlog) -> IntentLabel:
    messages = convlog.get_slim() + [{"role": "user", "content": input_text.strip()}]
    messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    result = ctx.engine.chat(
        messages=messages,
        caller_name="IntentRouter",
        model_level="medium",
        max_tokens=1000,
        schema=INTENT_SCHEMA,
    )

    if isinstance(result, dict):
        label = result.get("category", "other")
    else:
        log.warning(f"[分類失敗] スキーマ外の応答: {result}")
        label = "other"

    if label not in CATEGORIES:
        log.warning(f"[分類失敗] 不明なカテゴリ: {label}")
        return "other"

    log.info(f"[分類結果] {label}")
    return label
