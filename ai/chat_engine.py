# ai/chat_engine.py
import json
import re
from openai import OpenAI

from infra.logging import get_logger

log = get_logger("ChatEngine")

def _strip_think(text: str) -> str:
    return re.sub(r"<think[\s\S]*?</think\s*>", "", text, flags=re.IGNORECASE)

# 1) 先頭付近に追加
def _usage_to_jsonable(obj, _depth=0):
    """resp.usage のような pydantic/SDK オブジェクトでも壊れずにJSON化する"""
    if _depth > 4:
        return str(obj)  # 過度なネストは打ち切り

    # プリミティブ系
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # リスト/タプル
    if isinstance(obj, (list, tuple)):
        return [_usage_to_jsonable(x, _depth + 1) for x in obj]

    # dict
    if isinstance(obj, dict):
        return {str(k): _usage_to_jsonable(v, _depth + 1) for k, v in obj.items()}

    # pydantic / SDK系（model_dump などがある場合）
    for attr in ("model_dump", "dict", "to_dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return _usage_to_jsonable(fn(), _depth + 1)
            except Exception:
                pass

    # __dict__ があれば属性を総なめ
    if hasattr(obj, "__dict__"):
        out = {}
        for k in dir(obj):
            if k.startswith("_"):
                continue
            try:
                v = getattr(obj, k)
            except Exception:
                continue
            # 呼び出し可能は除外
            if callable(v):
                continue
            # SDKの内部モデルで見た目だけ属性なことがあるので、数値/文字/配列/辞書/さらにオブジェクト だけ許可
            if isinstance(v, (str, int, float, bool, list, tuple, dict)) or hasattr(v, "__dict__"):
                try:
                    out[k] = _usage_to_jsonable(v, _depth + 1)
                except Exception:
                    out[k] = str(v)
        return out

    # ここまででだめなら文字列化
    return str(obj)

def resolve_model_name(model_input: str | None) -> str:
    """
    low / medium / high / very_high のラベルを OpenAI モデル名に解決
    ※必要に応じてここだけ編集すれば全体へ反映される
    """
    level_map = {
        "low": "gpt-5-nano",
        "medium": "gpt-5-mini",
        "high": "gpt-5-mini",
        "very_high": "gpt-5",
    }
    key = (model_input or "medium").lower()
    if key not in level_map:
        raise ValueError("model 引数は 'low' | 'medium' | 'high' | 'very_high' のいずれかにしてください")
    return level_map[key]


class ChatEngine:
    """
    OpenAI Responses API 専用エンジン
    - ローカルLLM対応・ネットワーク検出・Ollama起動などは全て削除
    - 既存の呼び出し側( chat(prompt=...) / chat(messages=...) )はそのまま動作
    """
    def __init__(self, api_key_path: str | None = None):
        if not api_key_path:
            raise ValueError("APIキーのパスを指定してください。")
        with open(api_key_path, "r", encoding="utf-8") as f:
            api_key = f.read().strip()
        self.client = OpenAI(api_key=api_key)
        log.info("ChatEngine: 初期化しました。")

    def chat(
        self,
        prompt: str | list[dict] = None,
        messages: list[dict] | None = None,
        caller_name: str = "",
        max_tokens: int = 2048,
        model_level: str | None = None,
        schema: dict | None = None,
    ) -> str | dict:
        """
        Responses API に問い合わせて応答テキストを返す。
        - prompt: 文字列でもOK（内部で user メッセージ化）
        - messages: [{"role": "...", "content": "..."}] 形式でもOK
        """
        payload = messages if messages is not None else prompt
        if payload is None:
            raise ValueError("ChatEngine.chat: prompt または messages のいずれかを指定してください。")

        # メッセージ正規化
        msgs: list[dict]
        if isinstance(payload, list):
            msgs = payload
        else:
            msgs = [{"role": "user", "content": payload}]

        model = resolve_model_name(model_level)
        log.info(f"[{caller_name}] Responses API 送信 (model={model})")
        log.info(f"[{caller_name}] 送信メッセージ全体: {json.dumps(msgs, ensure_ascii=False, indent=2)}")

        # reasoning 努力度（任意）
        reasoning = None
        if model_level == "low":
            reasoning = {"effort": "minimal"}
        elif model_level == "medium":
            reasoning = {"effort": "minimal"}
        elif model_level == "high":
            reasoning = {"effort": "low"}
        elif model_level == "very_high":
            reasoning = {"effort": "low"}

        try:
            req_args = {
                "model": model,
                "input": msgs,
                "max_output_tokens": max_tokens,
                **({"reasoning": reasoning} if reasoning else {}),
            }

            # スキーマ指定があれば構造化出力モードに
            if schema:
                req_args["text"] = {"format": schema}

            resp = self.client.responses.create(**req_args)      
            # --- usage 全量ログ出力 ---
            usage = getattr(resp, "usage", None)
            if usage is not None:
                try:
                    usage_all = _usage_to_jsonable(usage)
                    log.info(f"[{caller_name}] Usage (ALL): {json.dumps(usage_all, ensure_ascii=False)}")
                except Exception as e:
                    log.warning(f"[{caller_name}] usage のJSON化に失敗: {e}")


            text = getattr(resp, "output_text", None)

            # usage ログ（ある場合のみ）
            usage = getattr(resp, "usage", None)
            if usage:
                inp = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
                out = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)
                tot = getattr(usage, "total_tokens", None)
                log.info(f"[{caller_name}] トークン使用量: input={inp} / output={out} / total={tot}")

            log.info(f"[{caller_name}] Responses API 受信")
            log.info(f"[{caller_name}] 応答テキスト: {text[:500]}{'...' if len(text) > 500 else ''}")

            if schema:
                try:
                    return json.loads(text)
                except Exception:
                    log.warning(f"[{caller_name}] JSONパース失敗: {text[:200]}")
                    return text
            else:
                return _strip_think(text)
        except Exception as e:
            log.exception(f"[{caller_name}] Responses API 応答エラー: {e}")
            return "API応答中にエラーが発生しました。"
