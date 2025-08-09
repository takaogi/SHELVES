# phases/scenario/state.py

import json
from infra.path_helper import get_data_path


class ScenarioState:
    def __init__(self, worldview_id: str, session_id: str):
        self.worldview_id = worldview_id
        self.session_id = session_id
        self._path = get_data_path(
            f"worlds/{worldview_id}/sessions/{session_id}/scenario_state.json"
        )

        self.chapter = 0
        self.scene = "exploration"
        self.section = 0
        self.markers = {}  # e.g., {"room::A3::visited": True}

        self._load()

    def _load(self):
        if self._path.exists():
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
                self.chapter = data.get("chapter", 0)
                self.scene = data.get("scene", "exploration")
                self.section = data.get("section", 0)
                self.markers = data.get("markers", {})

    def save(self):
        data = {
            "chapter": self.chapter,
            "scene": self.scene,
            "section": self.section,
            "markers": self.markers
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # -- marker 操作用 --

    def set_marker(self, key: str, value=True):
        self.markers[key] = value

    def get_marker(self, key: str, default=False):
        return self.markers.get(key, default)

    def remove_marker(self, key: str):
        if key in self.markers:
            del self.markers[key]

    def clear_all(self):
        self.chapter = 0
        self.scene = "exploration"
        self.section = 0
        self.markers = {}
        self.save()
