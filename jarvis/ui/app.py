# -*- coding: utf-8 -*-
"""
JARVIS v5 · ИНТЕРФЕЙС (tkinter, тёмная тема, без сайтов)
Вкладки:
 • 💬 Диалог  — чат с ИИ + кнопка микрофона + статус
 • 🎛 Команды — все системные действия по группам, клик = выполнить, редактирование синонимов письменно
 • 🧩 Мои команды — создание/редактирование кастомных команд и сценариев письменно (и голосом тоже можно)
 • 🧠 Память  — факты, предпочтения, статистика команд, история диалога
 • ⚙️ Настройки — имя, движок ИИ, голос, wake word, скорость речи, опасные действия
Голосовой цикл работает в отдельном потоке; интерфейс не блокируется.
"""
import os
import sys
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.assistant import Assistant          # noqa: E402
from core.actions import ACTIONS              # noqa: E402
from core.utils import norm                   # noqa: E402

try:
    from core.voice import VoiceBox, Ear
except Exception:
    VoiceBox = Ear = None

BG = "#0b1220"
PANEL = "#111a2e"
CARD = "#16233c"
ACCENT = "#22d3ee"
ACCENT2 = "#7c3aed"
TEXT = "#e2e8f0"
MUTED = "#94a3b8"
OK = "#34d399"
WARN = "#fbbf24"
DANGER = "#f87171"

FONT = ("Segoe UI", 11)
FONT_B = ("Segoe UI", 12, "bold")
FONT_TITLE = ("Segoe UI", 16, "bold")


class JarvisApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("JARVIS v5 — персональный ИИ ассистент ПК")
        self.root.geometry("1100x720")
        self.root.configure(bg=BG)
        self.msg_queue = queue.Queue()
        self.speaking_flag = threading.Event()

        self.voice = VoiceBox(self._tmp_settings()) if VoiceBox else None
        self.ear = Ear(self._tmp_settings()) if Ear else None
        self.asst = Assistant(voice=self.voice, ear=self.ear)
        self.asst.on_event = lambda ev: self.msg_queue.put(ev)

        self._build_style()
        self._build_layout()
        self._fill_commands_tab()
        self._fill_custom_tab()
        self._fill_memory_tab()
        self.root.after(100, self._poll_events)

        self.listening = False
        self._mic_thread = None
        self._append("system", f"Приветствую! Я {self.asst.settings.get('assistant_name')}. "
                      "Говорите команду или напишите сообщение. Всё бесплатно и на вашем ПК.")
        if self.ear and self.ear.backend:
            self._append("system", f"Микрофон активен ({self.ear.backend}). Скажите «{self.asst.settings.get('wake_word')}» или нажмите «Слушать».")
        else:
            self._append("system", "Микрофон недоступен — работайте текстом; голос подключится после установки whisper/vosk.")

    def _tmp_settings(self):
        from core.settings import Settings
        return Settings()

    # ═════════ STYLE ═════════
    def _build_style(self):
        st = ttk.Style(self.root)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background=BG, foreground=TEXT, font=FONT)
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=[14, 8], font=FONT_B)
        st.map("TNotebook.Tab", background=[("selected", CARD)], foreground=[("selected", ACCENT)])
        st.configure("TFrame", background=BG)
        st.configure("Card.TFrame", background=CARD)
        st.configure("TLabel", background=BG, foreground=TEXT)
        st.configure("Card.TLabel", background=CARD, foreground=TEXT)
        st.configure("Muted.TLabel", background=BG, foreground=MUTED)
        st.configure("TButton", background=CARD, foreground=TEXT, borderwidth=0, padding=[10, 6], font=FONT_B)
        st.map("TButton", background=[("active", ACCENT2)], foreground=[("active", "#ffffff")])
        st.configure("Accent.TButton", background=ACCENT, foreground="#04263a")
        st.map("Accent.TButton", background=[("active", "#67e8f9")])
        st.configure("Danger.TButton", background=DANGER, foreground="#3b0a0a")
        st.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT, rowheight=26)
        st.configure("Treeview.Heading", background=PANEL, foreground=ACCENT, font=FONT_B)
        st.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=TEXT)
        st.configure("Horizontal.TScale", background=BG)

    # ═════════ LAYOUT ═════════
    def _build_layout(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=14, pady=(10, 4))
        ttk.Label(top, text="⚡ JARVIS v5", font=FONT_TITLE, foreground=ACCENT).pack(side="left")
        self.status_lbl = ttk.Label(top, text="", style="Muted.TLabel")
        self.status_lbl.pack(side="right")

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=14, pady=6)

        # ── вкладка диалога ──
        tab_chat = ttk.Frame(self.nb)
        self.nb.add(tab_chat, text="  💬 Диалог  ")
        self.chat_box = tk.Text(tab_chat, bg=PANEL, fg=TEXT, insertbackground=TEXT, wrap="word",
                                font=("Consolas", 11), relief="flat", padx=12, pady=10, state="disabled")
        self.chat_box.pack(fill="both", expand=True, pady=(6, 6))
        self.chat_box.tag_config("user", foreground="#7dd3fc")
        self.chat_box.tag_config("asst", foreground=OK)
        self.chat_box.tag_config("action", foreground=WARN)
        self.chat_box.tag_config("system", foreground=MUTED)

        inp = ttk.Frame(tab_chat)
        inp.pack(fill="x")
        self.entry = ttk.Entry(inp, font=FONT)
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", self._on_send)
        ttk.Button(inp, text="Отправить", style="Accent.TButton", command=self._on_send).pack(side="left", padx=6)
        self.mic_btn = ttk.Button(inp, text="🎙 Слушать", command=self._toggle_mic)
        self.mic_btn.pack(side="left")
        ttk.Button(inp, text="⏹ Молчать", command=lambda: self.voice and self.voice.stop()).pack(side="left", padx=6)

        # ── вкладка команд ──
        tab_cmd = ttk.Frame(self.nb)
        self.nb.add(tab_cmd, text="  🎛 Команды  ")
        left = ttk.Frame(tab_cmd)
        left.pack(side="left", fill="y", padx=(0, 8), pady=6)
        self.cmd_tree = ttk.Treeview(left, columns=("label",), show="tree headings", selectmode="browse")
        self.cmd_tree.heading("#0", text="Группа")
        self.cmd_tree.column("#0", width=170)
        self.cmd_tree.heading("label", text="Действие")
        self.cmd_tree.column("label", width=200)
        vsb = ttk.Scrollbar(left, orient="vertical", command=self.cmd_tree.yview)
        self.cmd_tree.configure(yscrollcommand=vsb.set)
        self.cmd_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.cmd_tree.bind("<<TreeviewSelect>>", self._on_cmd_select)

        right = ttk.Frame(tab_cmd)
        right.pack(side="left", fill="both", expand=True, pady=6)
        self.sel_title = ttk.Label(right, text="Выберите действие слева", font=FONT_B)
        self.sel_title.pack(anchor="w")
        row = ttk.Frame(right)
        row.pack(fill="x", pady=6)
        ttk.Button(row, text="▶ Выполнить", style="Accent.TButton", command=self._run_selected).pack(side="left")
        ttk.Button(row, text="➕ Выучить синоним", command=self._add_synonym_dialog).pack(side="left", padx=6)
        ttk.Button(row, text="♻ Сбросить синонимы", command=self._reset_synonyms).pack(side="left")
        self.syn_list = tk.Listbox(right, bg=PANEL, fg=TEXT, font=FONT, relief="flat", exportselection=False)
        self.syn_list.pack(fill="both", expand=True, pady=6)
        srow = ttk.Frame(right)
        srow.pack(fill="x")
        self.syn_entry = ttk.Entry(srow, font=FONT)
        self.syn_entry.pack(side="left", fill="x", expand=True, ipady=4)
        ttk.Button(srow, text="Добавить", command=self._add_synonym_entry).pack(side="left", padx=6)
        ttk.Button(srow, text="Удалить выделенный", command=self._del_synonym).pack(side="left")

        # ── вкладка моих команд ──
        tab_cust = ttk.Frame(self.nb)
        self.nb.add(tab_cust, text="  🧩 Мои команды  ")
        crow = ttk.Frame(tab_cust)
        crow.pack(fill="x", pady=8)
        ttk.Label(crow, text="Название:").pack(side="left")
        self.cust_name = ttk.Entry(crow, width=24, font=FONT)
        self.cust_name.pack(side="left", padx=6)
        ttk.Button(crow, text="💾 Сохранить команду", command=self._save_custom).pack(side="left", padx=4)
        ttk.Button(crow, text="🎬 Сохранить сценарий", command=self._save_scenario).pack(side="left", padx=4)
        ttk.Button(crow, text="▶ Запустить", style="Accent.TButton", command=self._run_custom).pack(side="left", padx=4)
        ttk.Button(crow, text="🗑 Удалить", style="Danger.TButton", command=self._del_custom).pack(side="left")
        steps_frame = ttk.Frame(tab_cust)
        steps_frame.pack(fill="both", expand=True)
        ttk.Label(steps_frame, text="Шаги (каждый с новой строки, понимает русский: "
                                   "«громче», «новая вкладка», «пауза 2», «напиши привет», "
                                   "«запусти notepad.exe», «открой https://site.com»):",
                  style="Muted.TLabel").pack(anchor="w")
        self.steps_box = tk.Text(steps_frame, bg=PANEL, fg=TEXT, height=8, font=FONT, relief="flat",
                                 insertbackground=TEXT, wrap="word")
        self.steps_box.pack(fill="x", pady=4)
        ttk.Label(steps_frame, text="Сохранённые:", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        self.saved_list = tk.Listbox(tab_cust, bg=CARD, fg=TEXT, height=8, font=FONT, relief="flat")
        self.saved_list.pack(fill="both", expand=True, pady=4)
        self.saved_list.bind("<Double-1>", lambda e: self._load_custom())

        # ── вкладка памяти ──
        tab_mem = ttk.Frame(self.nb)
        self.nb.add(tab_mem, text="  🧠 Память  ")
        mrow = ttk.Frame(tab_mem)
        mrow.pack(fill="x", pady=6)
        ttk.Label(mrow, text="Ключ:").pack(side="left")
        self.fact_key = ttk.Entry(mrow, width=20, font=FONT)
        self.fact_key.pack(side="left", padx=4)
        ttk.Label(mrow, text="Значение:").pack(side="left")
        self.fact_val = ttk.Entry(mrow, width=30, font=FONT)
        self.fact_val.pack(side="left", padx=4)
        ttk.Button(mrow, text="Запомнить", style="Accent.TButton", command=self._add_fact).pack(side="left", padx=4)
        ttk.Button(mrow, text="Забыть выбранное", command=self._del_fact).pack(side="left")
        self.mem_tree = ttk.Treeview(tab_mem, columns=("key", "value"), show="headings")
        self.mem_tree.heading("key", text="Что помню")
        self.mem_tree.heading("value", text="Значение")
        self.mem_tree.column("key", width=300)
        self.mem_tree.column("value", width=500)
        self.mem_tree.pack(fill="both", expand=True, pady=6)
        stats = ttk.LabelFrame(tab_mem, text="Статистика использования (автообучение)")
        stats.pack(fill="x", pady=6)
        self.stats_lbl = ttk.Label(stats, text="", style="Muted.TLabel", wraplength=1000)
        self.stats_lbl.pack(anchor="w", padx=8, pady=6)

        # ── вкладка настроек ──
        tab_set = ttk.Frame(self.nb)
        self.nb.add(tab_set, text="  ⚙️ Настройки  ")
        g = ttk.LabelFrame(tab_set, text="Личность")
        g.pack(fill="x", padx=8, pady=8)
        self._setting_row(g, "Имя ассистента", "assistant_name")
        self._setting_row(g, "Как обращаться к вам", "owner_name")
        self._setting_row(g, "Слово пробуждения", "wake_word")
        g2 = ttk.LabelFrame(tab_set, text="ИИ-движок (все бесплатные)")
        g2.pack(fill="x", padx=8, pady=8)
        self._setting_combo(g2, "Мозг", "engine",
                            ["rules", "ollama", "lmstudio", "groq", "gemini", "openrouter", "custom"])
        self._setting_row(g2, "Ollama модель", "ollama_model")
        self._setting_row(g2, "Groq ключ (бесплатный)", "groq_key")
        self._setting_row(g2, "Gemini ключ (бесплатный)", "gemini_key")
        self._setting_row(g2, "OpenRouter ключ", "openrouter_key")
        g3 = ttk.LabelFrame(tab_set, text="Голос")
        g3.pack(fill="x", padx=8, pady=8)
        self._setting_combo(g3, "Движок озвучки", "tts_backend", ["pyttsx3", "edge", "espeak"])
        self._setting_combo(g3, "Пол голоса", "voice_gender", ["any", "male", "female"])
        self._setting_row(g3, "Edge голос (имя)", "edge_voice")
        self.rate_var = tk.IntVar(value=int(self.asst.settings.get("speech_rate")))
        ttk.Label(g3, text="Скорость речи").pack(anchor="w")
        ttk.Scale(g3, from_=120, to=320, variable=self.rate_var, orient="horizontal",
                  command=lambda v: self.asst.settings.set("speech_rate", int(float(v)))).pack(fill="x", padx=8)
        g4 = ttk.LabelFrame(tab_set, text="Безопасность")
        g4.pack(fill="x", padx=8, pady=8)
        self.confirm_var = tk.BooleanVar(value=bool(self.asst.settings.get("confirm_dangerous")))
        ttk.Checkbutton(g4, text="Подтверждать опасные действия (выключение, удаление)",
                        variable=self.confirm_var,
                        command=lambda: self.asst.settings.set("confirm_dangerous", self.confirm_var.get())).pack(anchor="w", padx=8)
        ttk.Button(tab_set, text="💾 Применить всё", style="Accent.TButton", command=self._apply_settings).pack(pady=10)

    def _setting_row(self, parent, label, key):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=8, pady=3)
        ttk.Label(row, text=label, width=24).pack(side="left")
        var = tk.StringVar(value=str(self.asst.settings.get(key, "")))
        ent = ttk.Entry(row, textvariable=var, font=FONT)
        ent.pack(side="left", fill="x", expand=True)
        setattr(self, "_setvar_" + key, var)

    def _setting_combo(self, parent, label, key, values):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=8, pady=3)
        ttk.Label(row, text=label, width=24).pack(side="left")
        var = tk.StringVar(value=str(self.asst.settings.get(key, values[0])))
        cb = ttk.Combobox(row, textvariable=var, values=values, state="readonly", width=22)
        cb.pack(side="left")
        setattr(self, "_setvar_" + key, var)

    def _apply_settings(self):
        data = {}
        for attr in dir(self):
            if attr.startswith("_setvar_"):
                key = attr[len("_setvar_"):]
                data[key] = getattr(self, attr).get()
        self.asst.settings.update(data)
        self.asst.brain.person_name = data.get("assistant_name", self.asst.settings.get("assistant_name"))
        self.asst.brain.owner_name = data.get("owner_name", "")
        self.asst.brain.rebuild()
        if self.voice:
            self.voice.init_backend()
        messagebox.showinfo("Готово", "Настройки сохранены и применены.")

    # ═════════ CHAT ═════════
    def _append(self, who, text):
        self.chat_box.configure(state="normal")
        prefix = {"user": "🟦 Вы: ", "asst": "🟢 ", "action": "⚙️ ", "system": "• "}[who]
        name = self.asst.settings.get("assistant_name") if who == "asst" else ""
        self.chat_box.insert("end", prefix + (name + ": " if name else "") + text + "\n\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _on_send(self, _evt=None):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._append("user", text)
        threading.Thread(target=self._process_bg, args=(text,), daemon=True).start()

    def _process_bg(self, text):
        reply = self.asst.process(text)
        if reply:
            self.msg_queue.put({"kind": "reply", "text": reply})

    def _poll_events(self):
        try:
            while True:
                ev = self.msg_queue.get_nowait()
                k = ev["kind"]
                if k == "reply":
                    self._append("asst", ev["text"])
                elif k == "action":
                    self._append("action", f"{ev['label']} → {ev['report'] or 'ок'}")
                elif k == "speak":
                    self.status_lbl.configure(text="🔊 говорю…")
                elif k == "ai_reply":
                    self.status_lbl.configure(text=f"🧠 мозг: {ev['engine']}")
                elif k == "heard":
                    self._append("user", "🎙 " + ev["text"])
                    threading.Thread(target=self._process_bg, args=(ev["text"],), daemon=True).start()
                elif k == "listening":
                    self.mic_btn.configure(text="🎙 Слушаю…" if ev["on"] else "🎙 Слушать")
                    self.status_lbl.configure(text="🎙 слушаю" if ev["on"] else "🎙 сплю")
        except queue.Empty:
            pass
        self.root.after(120, self._poll_events)

    # ═════════ MIC LOOP ═════════
    def _toggle_mic(self):
        if self.listening:
            self.listening = False
            return
        if not self.ear or not self.ear.available():
            messagebox.showwarning("Микрофон", "Распознавание речи недоступно. Установите: pip install faster-whisper sounddevice")
            return
        self.listening = True
        self._mic_thread = threading.Thread(target=self._mic_loop, daemon=True)
        self._mic_thread.start()

    def _mic_loop(self):
        wake = norm(self.asst.settings.get("wake_word", "джарвис"))
        idle_since = time.time()
        while self.listening:
            self.msg_queue.put({"kind": "listening", "on": True})
            heard = self.ear.listen_once(timeout=3)
            if not heard:
                # если тихо больше минуты — экономим ресурс, ждём кнопку
                if time.time() - idle_since > 60:
                    self.listening = False
                    self.msg_queue.put({"kind": "listening", "on": False})
                    return
                continue
            idle_since = time.time()
            h = norm(heard)
            self.msg_queue.put({"kind": "heard", "text": heard})
            if not self.asst.listening and wake not in h:
                continue
            # фраза сама уйдёт в обработку через _process_bg из _poll_events
        self.msg_queue.put({"kind": "listening", "on": False})

    # ═════════ COMMANDS TAB ═════════
    def _fill_commands_tab(self):
        groups = {}
        for k, (label, group, fn, needs) in ACTIONS.items():
            groups.setdefault(group, []).append((k, label))
        for g in sorted(groups):
            node = self.cmd_tree.insert("", "end", text=g, open=False)
            for k, label in groups[g]:
                self.cmd_tree.insert(node, "end", iid=k, text="", values=(label,))
        self._sel_key = None

    def _on_cmd_select(self, _e):
        sel = self.cmd_tree.selection()
        if not sel or sel[0] not in ACTIONS:
            return
        self._sel_key = sel[0]
        label = ACTIONS[self._sel_key][0]
        self.sel_title.configure(text=f"Действие: {label}")
        self._refresh_syn_list()

    def _refresh_syn_list(self):
        self.syn_list.delete(0, "end")
        for p in self.asst.matcher.synonyms.get(self._sel_key, []):
            self.syn_list.insert("end", p)

    def _run_selected(self):
        if not getattr(self, "_sel_key", None):
            return
        threading.Thread(target=self._process_bg, args=(ACTIONS[self._sel_key][0],), daemon=True).start()

    def _add_synonym_dialog(self):
        if not getattr(self, "_sel_key", None):
            return
        phrase = simpledialog.askstring("Новый синоним", f"Фраза для «{ACTIONS[self._sel_key][0]}»:")
        if phrase:
            self.asst.matcher.add_synonym(self._sel_key, phrase)
            self._refresh_syn_list()

    def _add_synonym_entry(self):
        if not getattr(self, "_sel_key", None):
            return
        phrase = self.syn_entry.get().strip()
        if phrase:
            self.asst.matcher.add_synonym(self._sel_key, phrase)
            self.syn_entry.delete(0, "end")
            self._refresh_syn_list()

    def _del_synonym(self):
        if not getattr(self, "_sel_key", None):
            return
        sel = self.syn_list.curselection()
        if not sel:
            return
        phrase = self.syn_list.get(sel[0])
        rest = [p for p in self.asst.matcher.synonyms.get(self._sel_key, []) if p != phrase]
        self.asst.matcher.set_synonyms(self._sel_key, rest)
        self._refresh_syn_list()

    def _reset_synonyms(self):
        if getattr(self, "_sel_key", None):
            self.asst.matcher.reset_synonyms(self._sel_key)
            self._refresh_syn_list()

    # ═════════ CUSTOM TAB ═════════
    def _steps_to_list(self):
        raw = self.steps_box.get("1.0", "end").strip()
        known = {"keys": [], }
        steps = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            hit = self.asst.matcher.match(line)
            if hit:
                steps.append({"kind": "action", "id": hit[0], "text": hit[1]})
                continue
            low = norm(line)
            if low.startswith("пауза"):
                n = 1
                for ch in low:
                    if ch.isdigit():
                        n = int(ch)
                        break
                steps.append({"kind": "wait", "sec": n})
                continue
            if low.startswith(("напиши", "введи")):
                steps.append({"kind": "type", "text": line.split(maxsplit=1)[1]})
                continue
            if low.startswith(("запусти",)):
                steps.append({"kind": "run", "cmd": line.split(maxsplit=1)[1]})
                continue
            if low.startswith("открой http"):
                steps.append({"kind": "url", "url": line.split(maxsplit=1)[1]})
                continue
            steps.append({"kind": "raw", "text": line})
        return steps

    def _save_custom(self):
        name = self.cust_name.get().strip()
        if not name:
            messagebox.showwarning("Нужно имя", "Введите название команды")
            return
        msg = self.asst.custom.add_command(name, self._steps_to_list())
        self._append("system", msg)
        self._fill_custom_tab()

    def _save_scenario(self):
        name = self.cust_name.get().strip()
        if not name:
            messagebox.showwarning("Нужно имя", "Введите название сценария")
            return
        msg = self.asst.custom.add_scenario(name, self._steps_to_list())
        self._append("system", msg)
        self._fill_custom_tab()

    def _run_custom(self):
        name = self.cust_name.get().strip()
        if not name:
            return
        cmds = self.asst.custom.commands()
        if norm(name) in cmds:
            for step in cmds[norm(name)]["steps"]:
                from core.custom import execute_step
                execute_step(step, self.asst)
                time.sleep(0.35)
            self._append("system", f"Команда «{name}» выполнена.")
        else:
            msg = self.asst.custom.run_scenario(name, self.asst)
            self._append("system", msg)

    def _del_custom(self):
        name = self.cust_name.get().strip()
        if not name:
            return
        m1 = self.asst.custom.remove_command(name)
        m2 = self.asst.custom.remove_scenario(name)
        self._append("system", m1 if "удалена" in m1 else m2)
        self._fill_custom_tab()

    def _load_custom(self):
        sel = self.saved_list.curselection()
        if not sel:
            return
        item = self.saved_list.get(sel[0])
        name = item.split(": ", 1)[-1]
        self.cust_name.delete(0, "end")
        self.cust_name.insert(0, name)
        data = self.asst.custom.commands().get(norm(name)) or self.asst.custom.scenarios().get(norm(name))
        self.steps_box.delete("1.0", "end")
        if data:
            for s in data["steps"]:
                if s.get("kind") == "action":
                    lbl = ACTIONS.get(s.get("id"), (s.get("id"),))[0]
                    self.steps_box.insert("end", lbl + "\n")
                elif s.get("kind") == "type":
                    self.steps_box.insert("end", "напиши " + s.get("text", "") + "\n")
                elif s.get("kind") == "run":
                    self.steps_box.insert("end", "запусти " + s.get("cmd", "") + "\n")
                elif s.get("kind") == "url":
                    self.steps_box.insert("end", "открой " + s.get("url", "") + "\n")
                elif s.get("kind") == "wait":
                    self.steps_box.insert("end", f"пауза {s.get('sec', 1)}\n")
                else:
                    self.steps_box.insert("end", s.get("text", "") + "\n")

    def _fill_custom_tab(self):
        self.saved_list.delete(0, "end")
        for k in self.asst.custom.commands():
            self.saved_list.insert("end", "🧩 команда: " + k)
        for k in self.asst.custom.scenarios():
            self.saved_list.insert("end", "🎬 сценарий: " + k)

    # ═════════ MEMORY TAB ═════════
    def _fill_memory_tab(self):
        self.mem_tree.delete(*self.mem_tree.get_children())
        facts, prefs = self.asst.memory.all_facts()
        for k, v in facts.items():
            self.mem_tree.insert("", "end", values=("📌 " + k, v))
        for k, v in prefs.items():
            self.mem_tree.insert("", "end", values=("⚙️ " + k, v))
        top = self.asst.memory.top_commands(8)
        self.stats_lbl.configure(text="Часто используемые: " +
                                 (", ".join(f"{k}×{c}" for k, c in top) if top else "пока пусто — пользуйтесь!"))

    def _add_fact(self):
        k, v = self.fact_key.get().strip(), self.fact_val.get().strip()
        if k and v:
            self.asst.memory.remember_fact(k, v)
            self.fact_key.delete(0, "end")
            self.fact_val.delete(0, "end")
            self._fill_memory_tab()

    def _del_fact(self):
        sel = self.mem_tree.selection()
        if not sel:
            return
        key = self.mem_tree.item(sel[0])["values"][0].lstrip("📌⚙️ ")
        self.asst.memory.forget(key)
        self._fill_memory_tab()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    JarvisApp().run()
