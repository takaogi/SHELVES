# ui/message_console.py

import tkinter as tk
import threading
import itertools
import time
import unicodedata
import random
import json

from tkinter import colorchooser, ttk
from infra.path_helper import get_data_path
from infra.logging import get_logger

DEFAULT_SETTINGS = {
    "font_family": "Meiryo",
    "font_size": 12,
    "text_color": "#ffffff",
    "bg_color": "#1e1e1e",
    "player_color": "#ffff00",   # ← 追加: プレイヤーの色（既定は黄色）
    "player_bold": True          # ← 追加: 太字フラグ
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
    def __init__(self, label_widget, message="  待機中...   ", width=20, interval=0.4):
        self.label = label_widget
        self.spinner = itertools.cycle(["｜", "／", "－", "＼"])
        self.message = message
        self.width = width
        self.interval = interval
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._thread = None

    def _visual_width(self, s):
        return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)

    def _crop_to_width(self, s):
        result = ""
        width = 0
        for c in s:
            char_width = self._visual_width(c)
            if width + char_width > self.width:
                break
            result += c
            width += char_width
        return result + " " * (self.width - width)

    def _animate(self):
        scroll_text = self.message * 2
        idx = 0
        scroll_counter = 0

        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(0.1)
                continue
            frame = next(self.spinner)
            part = scroll_text[idx: idx + len(scroll_text)]
            display = self._crop_to_width(part)
            self.label.after(0, self.label.config, {"text": f"{frame} 【{display}】"})
            time.sleep(self.interval)
            scroll_counter += 1
            if scroll_counter % 3 == 0:
                idx = (idx + 1) % len(self.message)

        self.label.after(0, self.label.config, {"text": ""})

    def start(self):
        self._stop_event.clear()
        self._pause_event.clear()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()

#
class MessageConsole_tk:
    def __init__(self):
        self.settings = load_ui_settings()
        self.font = (self.settings["font_family"], self.settings["font_size"])
        self.log = get_logger("UI")

        self.root = tk.Tk()
        self.root.title("S.H.E.L.V.E.S. - Message Console")
        self.root.geometry("1600x900")
        self.root.configure(bg=self.settings["bg_color"])

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_columnconfigure(0, weight=1)

        self.message_frame = tk.Frame(self.root, bg=self.settings["bg_color"])
        self.message_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0))

        self.scrollbar = tk.Scrollbar(self.message_frame)
        self.scrollbar.pack(side="right", fill="y")

        self.message_area = tk.Text(
            self.message_frame,
            yscrollcommand=self.scrollbar.set,
            state='disabled',
            wrap='char',
            font=self.font,
            bg=self.settings["bg_color"],
            insertbackground=self.settings["text_color"],
            bd=0,
            highlightthickness=0,
            relief="flat"
        )
        self.message_area.tag_config("default",
            foreground=self.settings["text_color"],
            lmargin1=0,
            lmargin2=0,
            tabs=("1c",),
            spacing1=1
        )
        self.message_area.tag_config(
            "player",
            foreground=self.settings.get("player_color", "#ffff00"),
            font=(self.settings["font_family"], self.settings["font_size"], "bold"),
            lmargin1=0,
            lmargin2=0,
            tabs=("1c",),
            spacing1=1
        )



        self.message_area.pack(side="left", expand=True, fill="both")
        self.scrollbar.config(command=self.message_area.yview)

        self.bottom_frame = tk.Frame(self.root, bg=self.settings["bg_color"])
        self.bottom_frame.grid(row=1, column=0, sticky="ew")

        self.spinner_label = tk.Label(
            self.bottom_frame,
            text="",
            font=self.font,
            bg=self.settings["bg_color"],
            fg=self.settings["text_color"]
        )
        self.spinner_label.pack_forget()
        self.spinner = GUISpinner(self.spinner_label, message="応答生成中...", width=20, interval=0.4)


        self.entry = tk.Text(
            self.bottom_frame,
            height=3,
            font=(self.settings["font_family"], self.settings["font_size"] + 2),
            bg="#2a2a2a",
            fg=self.settings["text_color"],
            insertbackground=self.settings["text_color"],
            bd=0,
            highlightthickness=0,
            relief="flat",
            state="disabled"  # ← 追加
        )

        self.entry.bind("<Return>", self._on_enter_text)
        self.entry.bind("<Shift-Return>", lambda e: None)
        self.entry.pack_forget()

        self.input_callback = None
        menu = tk.Menu(self.root)
        self.root.config(menu=menu)
        config_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="設定", menu=config_menu)
        config_menu.add_command(label="UI設定...", command=self.open_settings_window)

    def print_message(self, sender: str, message: str):
        is_player = sender and sender.lower() in ["user", "player"]
        tag = "player" if is_player else "default"
        line = f"-- {message}\n" if is_player else f"{message}\n"

        self.message_area.configure(state='normal')
        self.message_area.insert('end', line, tag)
        self.message_area.configure(state='disabled')
        self.message_area.see('end')

    def safe_print(self, sender, message):
        self.root.after(0, lambda: self.print_message(sender, message))

    def wait_for_input(self, on_input_received):
        self.input_callback = on_input_received
        self.stop_spinner()
        self.entry.config(state="normal")
        self.entry.delete("1.0", "end")
        self.entry.pack(side='top', padx=10, pady=(5, 10), fill='x')
        self.entry.focus()
        # ここでバインドを必ず再設定
        self.entry.unbind("<Return>")
        self.entry.unbind("<Shift-Return>")
        self.entry.bind("<Return>", self._on_enter_text)
        self.entry.bind("<Shift-Return>", lambda e: None)
        self.root.after(100, lambda: self.message_area.see("end"))


    def _on_enter_text(self, event):
        if event.state & 0x0001:
            return
        value = self.entry.get("1.0", "end-1c") 
        self.log.debug(f"[InputRaw] repr={repr(value)}")

        if value and self.input_callback:
            self.entry.delete("1.0", "end")
            self.entry.pack_forget()
            # 入力をUIに即表示
            self.print_message("Player", value)
            # その後、上位ロジックに渡す
            self.input_callback(value)
        return "break"


    def start_spinner(self):
        self.entry.pack_forget()
        self.spinner_label.pack(padx=10, pady=(5, 5), anchor='w')
        self.spinner.start()

    def stop_spinner(self):
        self.spinner.stop()
        self.spinner_label.pack_forget()
        
    def wait_for_enter(self, arg=None, on_enter=None):
        """
        非ブロッキング専用:
        - wait_for_enter(callback)
        - wait_for_enter("表示メッセージ", callback)
        """
        if callable(arg) and on_enter is None:
            on_enter = arg
            prompt = "【エンターで決定】"
        elif isinstance(arg, str) and callable(on_enter):
            prompt = arg
        else:
            raise TypeError("wait_for_enter は callback（必須）を受け取る非ブロッキング専用です")

        self.stop_spinner()
        self.entry.config(state="normal")

        # コールバックを保存
        self.enter_callback = on_enter

        def _handle_enter_nonblock(_ev):
            if self.enter_callback:
                cb = self.enter_callback
                self.enter_callback = None  # 一度きりにしたい場合
                self.entry.delete("1.0", "end")
                self.entry.pack_forget()
                cb("")  # 空文字を渡す
            return "break"

        self.entry.delete("1.0", "end")
        self.entry.pack(side='top', padx=10, pady=(5, 10), fill='x')
        self.entry.focus()
        self.entry.unbind("<Return>")
        self.entry.unbind("<Shift-Return>")
        self.entry.bind("<Return>", _handle_enter_nonblock)
        self.entry.bind("<Shift-Return>", lambda e: None)

        if prompt:
            self.safe_print("System", prompt)
        self.root.after(100, lambda: self.message_area.see("end"))


    def run(self):
        self.root.mainloop()

    def open_settings_window(self):
        win = tk.Toplevel(self.root)
        win.title("UI設定")
        win.geometry("400x250")
        win.resizable(False, False)

        font_choices = ["Consolas", "Meiryo", "MS Gothic", "Courier", "Arial", "游ゴシック", "Noto Sans JP"]

        tk.Label(win, text="フォント:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        font_var = tk.StringVar(value=self.settings["font_family"])
        font_menu = ttk.Combobox(win, textvariable=font_var, values=font_choices, state="readonly")
        font_menu.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(win, text="サイズ:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        size_var = tk.StringVar(value=str(self.settings["font_size"]))
        size_spin = tk.Spinbox(win, from_=8, to=32, textvariable=size_var, width=5)
        size_spin.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        text_color_var = tk.StringVar(value=self.settings["text_color"])
        bg_color_var = tk.StringVar(value=self.settings["bg_color"])

        player_color_var = tk.StringVar(value=self.settings.get("player_color", "#ffff00"))
        player_bold_var = tk.BooleanVar(value=self.settings.get("player_bold", True))


        # --- 文字色 ---
        tk.Label(win, text="文字色:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        text_color_entry = tk.Entry(win, textvariable=text_color_var, width=10)
        text_color_entry.grid(row=2, column=1, padx=(10, 0), pady=5, sticky="w")

        def choose_text_color():
            initial_color = text_color_var.get() or "#FFFFFF"
            color = colorchooser.askcolor(title="文字色を選択", initialcolor=initial_color)[1]
            if color:
                text_color_var.set(color)

        tk.Button(win, text="選択", command=choose_text_color).grid(row=2, column=2, padx=5, pady=5)

        # --- 背景色 ---
        tk.Label(win, text="背景色:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        bg_color_entry = tk.Entry(win, textvariable=bg_color_var, width=10)
        bg_color_entry.grid(row=3, column=1, padx=(10, 0), pady=5, sticky="w")

        def choose_bg_color():
            initial_color = bg_color_var.get() or "#1e1e1e"
            color = colorchooser.askcolor(title="背景色を選択", initialcolor=initial_color)[1]
            if color:
                bg_color_var.set(color)

        tk.Button(win, text="選択", command=choose_bg_color).grid(row=3, column=2, padx=5, pady=5)

        # --- プレイヤー色 ---
        tk.Label(win, text="プレイヤー色:").grid(row=4, column=0, sticky="w", padx=10, pady=5)
        player_color_entry = tk.Entry(win, textvariable=player_color_var, width=10)
        player_color_entry.grid(row=4, column=1, padx=(10, 0), pady=5, sticky="w")

        def choose_player_color():
            initial_color = player_color_var.get() or "#ffff00"
            color = colorchooser.askcolor(title="プレイヤー色を選択", initialcolor=initial_color)[1]
            if color:
                player_color_var.set(color)

        tk.Button(win, text="選択", command=choose_player_color).grid(row=4, column=2, padx=5, pady=5)

        # --- プレイヤー太字 ---
        player_bold_chk = tk.Checkbutton(win, text="プレイヤーを太字にする", variable=player_bold_var)
        player_bold_chk.grid(row=5, column=0, columnspan=3, sticky="w", padx=10, pady=5)


        def apply():
            self.settings["font_family"] = font_var.get()
            self.settings["font_size"] = int(size_var.get())
            self.settings["text_color"] = text_color_var.get()
            self.settings["bg_color"] = bg_color_var.get()
            # ↓↓↓ 追加
            self.settings["player_color"] = player_color_var.get()
            self.settings["player_bold"] = bool(player_bold_var.get())
            # ↑↑↑ 追加
            save_ui_settings(self.settings)
            self.apply_settings()
            win.destroy()


        tk.Button(win, text="適用", command=apply).grid(row=6, column=0, columnspan=4, pady=15)

    def apply_settings(self):
        self.font = (self.settings["font_family"], self.settings["font_size"])
        self.message_area.config(
            font=self.font,
            bg=self.settings["bg_color"],
            insertbackground=self.settings["text_color"]
        )
        self.message_area.tag_config("default", foreground=self.settings["text_color"])
        player_font = (
            self.settings["font_family"],
            self.settings["font_size"],
            "bold" if self.settings.get("player_bold", True) else "normal"
        )
        self.message_area.tag_config(
            "player",
            foreground=self.settings.get("player_color", "#ffff00"),
            font=player_font
        )

        self.entry.config(
            font=(self.settings["font_family"], self.settings["font_size"] + 2),
            fg=self.settings["text_color"],
            bg="#2a2a2a",
            insertbackground=self.settings["text_color"]
        )
        self.root.config(bg=self.settings["bg_color"])
        self.message_frame.config(bg=self.settings["bg_color"])
        self.bottom_frame.config(bg=self.settings["bg_color"])
        self.spinner_label.config(font=self.font, bg=self.settings["bg_color"], fg=self.settings["text_color"])
    