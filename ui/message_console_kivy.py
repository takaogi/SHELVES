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

from kivy.clock import Clock
from kivy.core.window import Window
import itertools
import unicodedata
from main import run_loop

from infra.logging import get_logger
from infra.path_helper import get_data_path
import json
from pathlib import Path

DEFAULT_SETTINGS = {
    "font_family": "Roboto",
    "font_size": 18,
    "text_color": (1, 1, 1, 1),
    "bg_color": (0.12, 0.12, 0.12, 1),
    "player_color": (1, 1, 0, 1),   # yellow
    "player_bold": True
}


def load_ui_settings():
    path = get_data_path("ui_settings.json")
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_SETTINGS.copy()


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
    output = ObjectProperty(None)
    input = ObjectProperty(None)
    
    def on_clicled_enterButton(self):
        if self.input.text != "":
            self.output.text += "\n" + self.input.text
            self.input.text = ""
        else:
            pass

class MessageConsole_kivyApp(App):
    def build(self):
        self.settings = load_ui_settings()
        self.font = (self.settings["font_family"], self.settings["font_size"])
        self.log = get_logger("UI")

        self.title = "S.H.E.L.V.E.S. - Message Console"

        return MainWindow_kivy()
    
    #ここ以下で定義しているレイアウトはmessageConsole_kivy.kvで定義する
    # def __init__(self):
    #     super.__init__()
        # super().__init__(orientation="vertical", **kwargs)
        # self.log = get_logger("UI")
        # self.settings = load_ui_settings()

        # # 上部: メッセージ表示
        # self.scroll = ScrollView(size_hint=(1, 0.9))
        # self.message_label = Label(
        #     text="",
        #     font_size=self.settings["font_size"],
        #     color=self.settings["text_color"],
        #     halign="left",
        #     valign="top",
        #     size_hint_y=None,
        #     text_size=(Window.width * 0.95, None)
        # )
        # self.message_label.bind(texture_size=self._update_height)
        # self.scroll.add_widget(self.message_label)

        # # 下部: スピナーと入力欄
        # self.spinner_label = Label(
        #     text="", font_size=self.settings["font_size"], color=self.settings["text_color"],
        #     size_hint=(1, 0.05)
        # )
        # self.spinner = GUISpinner(self.spinner_label)

        # self.entry = TextInput(
        #     multiline=False,
        #     size_hint=(1, 0.1),
        #     background_color=(0.16, 0.16, 0.16, 1),
        #     foreground_color=self.settings["text_color"],
        # )
        # self.entry.bind(on_text_validate=self._on_enter_text)

        # self.add_widget(self.scroll)
        # self.add_widget(self.spinner_label)
        # self.add_widget(self.entry)

        # self.input_callback = None

    def _update_height(self, instance, size):
        self.message_label.height = size[1]
        self.message_label.text_size = (self.scroll.width * 0.95, None)
        self.scroll.scroll_y = 0

    def print_message(self, sender: str, message: str):
        is_player = sender and sender.lower() in ["user", "player"]
        color = self.settings["player_color"] if is_player else self.settings["text_color"]
        prefix = "-- " if is_player else ""
        self.message_label.text += f"[color={self._rgba_to_hex(color)}]{prefix}{message}[/color]\n"

    def safe_print(self, sender, message):
        Clock.schedule_once(lambda dt: self.print_message(sender, message))

    def wait_for_input(self, on_input_received):
        self.input_callback = on_input_received
        self.spinner.stop()
        self.entry.text = ""
        self.entry.focus = True

    def _on_enter_text(self, instance):
        value = self.entry.text.strip()
        if value and self.input_callback:
            self.print_message("Player", value)
            self.input_callback(value)
        self.entry.text = ""

    def wait_for_enter(self, on_enter_pressed, prompt: str = "【エンターで決定】"):
        """
        エンターが押されるまで待機する（入力は使わない）。
        on_enter_pressed: Enterキーで呼び出されるコールバック関数。
        """
        self.spinner.stop()
        self.safe_print("System", prompt)

        # 入力欄を空にしてフォーカス
        self.entry.text = ""
        self.entry.focus = True

        def _handler(instance):
            # 入力内容は使わずに確定
            self.entry.text = ""
            on_enter_pressed()

        # 既存の入力ハンドラを退避して、Enter押下で on_enter_pressed を呼ぶ
        self.entry.unbind(on_text_validate=self._on_enter_text)
        self.entry.bind(on_text_validate=_handler)


    def start_spinner(self):
        self.entry.text = ""
        self.spinner.start()

    def stop_spinner(self):
        self.spinner.stop()

    def _rgba_to_hex(self, rgba):
        r, g, b, a = [int(c * 255) for c in rgba]
        return f"#{r:02x}{g:02x}{b:02x}"
    