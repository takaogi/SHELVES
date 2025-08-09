import json
from pathlib import Path
from infra.path_helper import get_data_path


class Scriber:
    def __init__(self, ai_name: str, ai_type: str = "operation",
                 worldview_id: str = None, session_id: str = None, temp: bool = False):
        self.ai_name = ai_name
        self.ai_type = ai_type
        self.worldview_id = worldview_id
        self.session_id = session_id
        self.temp = temp

        self.record_path = self._resolve_record_path()
        if not self.temp:
            self.record_path.parent.mkdir(parents=True, exist_ok=True)

    def _resolve_record_path(self) -> Path:
        if self.temp or self.ai_type == "operation":
            return get_data_path(f"temp/operation/{self.ai_name}.record.jsonl")
        elif self.ai_type == "builder":
            return get_data_path(f"temp/worlds/{self.worldview_id}/builder_records/{self.ai_name}.jsonl")
        elif self.ai_type == "scenario":
            return get_data_path(f"worlds/{self.worldview_id}/sessions/{self.session_id}/records/{self.ai_name}.jsonl")
        else:
            return get_data_path(f"temp/misc/{self.ai_name}.record.jsonl")

    def append_role(self, role: str, content: str):
        entry = {"role": role, "content": content}
        with self.record_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def say(self, content: str):
        self.append_role("assistant", content)

    def log_user(self, content: str):
        self.append_role("user", content)

    def load_recent_exchanges(self, count: int = 20) -> list[dict]:
        if not self.record_path.exists():
            return []

        with self.record_path.open("r", encoding="utf-8") as f:
            messages = []
            for line in f:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # 不正な行はスキップ

        # 後方からN往復分（= 2N個）取得
        result = []
        user_count = 0
        i = len(messages) - 1
        while i >= 1 and user_count < count:
            if messages[i]["role"] == "assistant" and messages[i - 1]["role"] == "user":
                result[0:0] = [messages[i - 1], messages[i]]  # 順序維持
                user_count += 1
                i -= 2
            else:
                i -= 1  # ずれてたら1つ戻る

        return result

    def clear(self):
        if self.record_path.exists() and not self.temp:
            self.record_path.unlink()