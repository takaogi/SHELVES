# ui/message_console_kivy.py

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.gridlayout import GridLayout
from kivy.properties import ObjectProperty
from kivy.utils import platform
from kivy.properties import ListProperty

from kivy.clock import Clock
from kivy.core.window import Window
import itertools

from infra.logging import get_logger
from infra.path_helper import get_data_path ,get_resource_path
import json
from pathlib import Path

DEFAULT_SETTINGS = {
    "font_family": "Meiryo.ttc",
    "font_size": 18,
    "text_color": (1, 1, 1, 1),
    "bg_color": (0.12, 0.12, 0.12, 1),
    "player_color": (1, 1, 0, 1),
    "player_bold": True,
    "auto_scroll": True
}

def load_ui_settings():
    path = get_data_path("ui_settings.json")
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_SETTINGS.copy()

def save_ui_settings(settings):
    path = get_data_path("ui_settings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


class GUISpinner:
    def __init__(self, label_widget, message="応答生成中...", interval=0.4):
        self.label = label_widget
        self.message = message
        self.spinner = itertools.cycle(["｜", "／", "－", "＼"])
        self.event = None
        self.interval = interval

    def start(self):
        self.stop()
        self.event = Clock.schedule_interval(self._animate, self.interval)

    def stop(self):
        if self.event:
            self.event.cancel()
            self.event = None
        self.label.text = ""

    def _animate(self, dt):
        frame = next(self.spinner)
        self.label.text = f"{frame} 【{self.message}】"

class MainWindow_kivy(RelativeLayout):
    bg_color = ListProperty(DEFAULT_SETTINGS["bg_color"])

    def on_clicled_enterButton(self):
        app = App.get_running_app()
        app.handle_submit()



class MessageConsole_kivyApp(App):
    def build(self):
        self.settings = load_ui_settings()
        self.font_path = str(get_resource_path(f"resources/fonts/{self.settings['font_family']}"))

        root = MainWindow_kivy()
        self.message_label = root.ids.message_label
        self.entry = root.ids.entry
        self.spinner_label = root.ids.spinner_label
        self.scroll = root.ids.scroll
  
        self.auto_scroll_enabled = self.settings.get("auto_scroll", True)# 自動スクロール有効フラグ

        self.spinner = GUISpinner(self.spinner_label)

        if platform in ("win", "linux", "macosx"):  # PC の場合だけ
            Window.bind(on_key_down=self._on_key_down_pc)

        return root
    
    def on_start(self):
        # アプリ起動後に適用
        self.apply_settings()

    def handle_submit(self):
        """入力欄の内容を送信する共通処理"""
        text = self.entry.text.strip()
        if text:
            self.print_message("Player", text)
            if self.input_callback:
                cb = self.input_callback
                self.input_callback = None
                cb(text)
        self.entry.text = ""

    def toggle_auto_scroll(self): #自動スクロールの ON/OFF を切り替える
        self.auto_scroll_enabled = not self.auto_scroll_enabled
        self.settings["auto_scroll"] = self.auto_scroll_enabled
        save_ui_settings(self.settings)
        state = "ON" if self.auto_scroll_enabled else "OFF"
        self.safe_print("System", f"自動スクロールを {state} にしました")

    def _scroll_to_bottom(self, *args):
        if not self.auto_scroll_enabled:
            return
        if self.message_label.texture_size[1] > self.scroll.height:
            self.scroll.scroll_y = 0

    def apply_settings(self):
        font_size = self.settings["font_size"]
        font_path = self.font_path

        self.message_label.font_name = font_path
        self.message_label.font_size = font_size

        self.entry.font_name = font_path
        self.entry.font_size = font_size

        self.spinner_label.font_name = font_path
        self.spinner_label.font_size = font_size

        # 🔹 MainWindow の bg_color を更新
        if self.root:
            self.root.bg_color = self.settings["bg_color"]


    def _update_height(self, instance, size):
        self.message_label.height = size[1]
        self.message_label.text_size = (self.scroll.width * 0.95, None)
        self.scroll.scroll_y = 0

    def print_message(self, sender: str, message: str):
        is_player = sender and sender.lower() in ["user", "player"]
        color = self.settings["player_color"] if is_player else self.settings["text_color"]
        prefix = "-- " if is_player else ""
        self.message_label.text += f"[color={self._rgba_to_hex(color)}]{prefix}{message}[/color]\n"
        Clock.schedule_once(self._scroll_to_bottom, 0)

    def safe_print(self, sender, message):
        Clock.schedule_once(lambda dt: self.print_message(sender, message))

    def _on_enter_text(self, instance):
        value = self.entry.text.strip()
        if value and self.input_callback:
            self.print_message("Player", value)
            self.input_callback(value)
        self.entry.text = ""

    def wait_for_input(self, on_input_received):
        def _setup(dt):
            self.input_callback = on_input_received
            self.spinner.stop()
            self.spinner_label.text = ""
            self.entry.opacity = 1
            self.entry.disabled = False
            self.entry.text = ""
            self.entry.focus = True
            self.entry.unbind(on_text_validate=self._on_enter_text)
            self.entry.bind(on_text_validate=self._on_enter_text)
            Clock.schedule_once(self._scroll_to_bottom, 0) 
        Clock.schedule_once(_setup)

    def wait_for_enter(self, prompt: str = "【エンターで決定】", on_enter_pressed=None):
        def _setup(dt):
            self.spinner.stop()
            self.spinner_label.text = ""
            self.safe_print("System", prompt)
            self.entry.opacity = 1
            self.entry.disabled = False
            self.entry.text = ""
            self.entry.focus = False
            Clock.schedule_once(self._scroll_to_bottom, 0) 
            # …（on_enter_pressedの処理は今のまま）
        Clock.schedule_once(_setup)

    def _on_key_down_pc(self, window, key, scancode, codepoint, modifiers):
        if codepoint == "enter" or key in (13, 271):
            if "shift" in modifiers:
                self.entry.insert_text("\n")
            else:
                self.handle_submit()
            return True
        return False

    def start_spinner(self):
        def _setup(dt):
            self.entry.opacity = 0
            self.entry.disabled = True
            self.spinner_label.opacity = 1   # ← 表示
            self.spinner.start()
        Clock.schedule_once(_setup)

    def stop_spinner(self):
        def _setup(dt):
            self.spinner.stop()
            self.spinner_label.text = ""
            self.spinner_label.opacity = 0   # ← 非表示
            self.entry.opacity = 1
            self.entry.disabled = False
        Clock.schedule_once(_setup)


    def _rgba_to_hex(self, rgba):
        r, g, b, a = [int(c * 255) for c in rgba]
        return f"#{r:02x}{g:02x}{b:02x}"
