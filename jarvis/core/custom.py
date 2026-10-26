# -*- coding: utf-8 -*-
"""
JARVIS v5 · КАСТОМНЫЕ КОМАНДЫ И СЦЕНАРИИ
Пользователь создаёт команды голосом («создай команду кофейня: открой spotify, поставь громкость 30»)
или письменно в интерфейсе. Сценарий = последовательность шагов с паузами.
Хранение: data/config.json (кэш — перечитывается только при изменении файла).
Шаги могут ссылаться на системные действия (id) или быть сырыми командами (клавиши/файл/url/shell).
"""
import os
import json
import time
import shlex
import subprocess
import webbrowser
import threading

import pyautogui

from .utils import norm, type_russian
from .synonyms import OPEN_VERBS

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")


class CustomStore:
    """Кастомные команды + сценарии с кэшированием по mtime."""

    def __init__(self, path=CONFIG_FILE):
        self.path = path
        self._cache = None
        self._mtime = 0
        self.lock = threading.Lock()

    # ── низкоуровневое чтение/запись ──
    def _load(self):
        if not os.path.exists(self.path):
            return {"commands": {}, "scenarios": {}}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            d.setdefault("commands", {})
            d.setdefault("scenarios", {})
            return d
        except Exception as e:
            print(f"⚠️ config.json повреждён: {e}")
            return {"commands": {}, "scenarios": {}}

    def _save(self, data):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
        self._mtime = os.path.getmtime(self.path)
        self._cache = data

    def data(self):
        """Кэш перечитывается только если файл изменился на диске."""
        m = os.path.getmtime(self.path) if os.path.exists(self.path) else 0
        if self._cache is None or m != self._mtime:
            with self.lock:
                self._save(self._load())
        return self._cache

    # ── команды ──
    def commands(self):
        return dict(self.data()["commands"])

    def add_command(self, name, steps, synonyms=None):
        d = self.data()
        d["commands"][norm(name)] = {"steps": steps, "synonyms": [norm(s) for s in (synonyms or [])]}
        self._save(d)
        return f"Команда «{name}» создана ({len(steps)} шагов)."

    def remove_command(self, name):
        d = self.data()
        if norm(name) in d["commands"]:
            del d["commands"][norm(name)]
            self._save(d)
            return f"Команда «{name}» удалена."
        return f"Команды «{name}» нет."

    def match_command(self, text):
        """Точный и fuzzy поиск по имени/синонимам кастомной команды."""
        t = norm(text)
        stripped = t
        for v in OPEN_VERBS:
            if stripped.startswith(v):
                stripped = stripped[len(v):].strip()
                break
        cmds = self.commands()
        for name, c in cmds.items():
            if t == name or stripped == name or t in c.get("synonyms", []) or stripped in c.get("synonyms", []):
                return name, c
        try:
            from thefuzz import process
            names = list(cmds.keys())
            if names:
                match, score = process.extractOne(stripped, names)
                if score >= 88:
                    return match, cmds[match]
        except ImportError:
            pass
        return None, None

    # ── сценарии ──
    def scenarios(self):
        return dict(self.data()["scenarios"])

    def add_scenario(self, name, steps):
        d = self.data()
        d["scenarios"][norm(name)] = {"steps": steps}
        self._save(d)
        return f"Сценарий «{name}» сохранён."

    def remove_scenario(self, name):
        d = self.data()
        if norm(name) in d["scenarios"]:
            del d["scenarios"][norm(name)]
            self._save(d)
            return f"Сценарий «{name}» удалён."
        return f"Сценария «{name}» нет."

    def run_scenario(self, name, engine, speak=None):
        sc = self.scenarios().get(norm(name))
        if not sc:
            return f"Сценарий «{name}» не найден."
        results = []
        for step in sc["steps"]:
            out = execute_step(step, engine)
            results.append(out)
            delay = step.get("wait", 0.6)
            if delay:
                time.sleep(delay)
        return f"Сценарий «{name}» выполнен: {len(sc['steps'])} шагов."


def make_step(kind, **kw):
    """Конструктор шага. kind: action|keys|type|run|url|wait|speak|window"""
    step = {"kind": kind}
    step.update(kw)
    return step


def execute_step(step, engine):
    """Выполняет один шаг. engine — ActionEngine для ссылки на системные действия."""
    kind = step.get("kind", "action")
    try:
        if kind == "action":
            return engine.run_key(step.get("id"), step.get("text", ""))
        if kind == "keys":
            keys = step.get("keys", [])
            if len(keys) == 1:
                pyautogui.press(keys[0], _pause=False)
            else:
                pyautogui.hotkey(*keys, _pause=False)
            return f"Нажато {'+'.join(keys)}"
        if kind == "type":
            type_russian(step.get("text", ""))
            return f"Введено «{step.get('text', '')[:40]}»"
        if kind == "run":
            subprocess.Popen(step.get("cmd", ""), shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Запущено: {step.get('cmd', '')}"
        if kind == "url":
            webbrowser.open(step.get("url", ""))
            return f"Открыт {step.get('url', '')}"
        if kind == "wait":
            time.sleep(float(step.get("sec", 1)))
            return f"Пауза {step.get('sec', 1)} сек"
        if kind == "speak":
            if engine and getattr(engine, "on_speak", None):
                engine.on_speak(step.get("text", ""))
            return f"Реплика: {step.get('text', '')}"
    except Exception as e:
        return f"Шаг {kind}: ошибка {e}"
    return f"Неизвестный шаг {kind}"


# ═══════════════ ПАРСЕР ГОЛОСОВОГО СОЗДАНИЯ КОМАНД ═══════════════
# «создай команду <имя>: <шаг 1>, <шаг 2>, ...» / «добавь сценарий <имя>: ...»
CREATE_CMD_RE = None  # заполняется лениво, чтобы избежать циклического импорта re-констант


def parse_creation(text, known_actions):
    """
    Разбирает фразу создания команды/сценария на имя + шаги.
    Шаги распознаются среди синонимов системных действий и базовых глаголов.
    Возвращает (is_scenario, name, steps) или None.
    """
    import re
    global CREATE_CMD_RE
    if CREATE_CMD_RE is None:
        CREATE_CMD_RE = re.compile(
            r"^(?:создай|добавь|сделай)\s+(команду|сценарий|скрипт)\s+(?:под именем |с названием )?"
            r"(?P<name>[^:：]+)[:：]\s*(?P<body>.+)$", re.I)
    t = text.strip()
    m = CREATE_CMD_RE.match(t)
    if not m:
        return None
    is_scen = "сценар" in m.group(1).lower() or "скрипт" in m.group(1).lower()
    name = norm(m.group("name"))
    body = m.group("body")
    # разделяем шаги: через «потом», «затем», «после этого», «;», « и » между глаголами
    parts = re.split(r"\s*(?:потом|затем|далее|после этого|следом|;\s*)\s*", body, flags=re.I)
    steps = []
    matcher = known_actions.get("matcher")
    engine = known_actions.get("engine")
    for p in parts:
        p = p.strip(" .,")
        if not p:
            continue
        pm = norm(p)
        # пауза: «пауза 2 секунды»
        mp = re.match(r"^пауза\s*(\d+)?\s*(сек|секунд|секунды|с)?$", pm)
        if mp:
            sec = int(mp.group(1) or 1)
            steps.append(make_step("wait", sec=sec))
            continue
        # ввод текста: «напиши привет»
        mt = re.match(r"^(?:напиши|введи|напечатай)\s+(.+)$", pm)
        if mt:
            steps.append(make_step("type", text=p[len(p.split(maxsplit=1)[0]):].strip()))
            continue
        # запуск программы: «запусти notepad.exe» / «открой http://...»
        mr = re.match(r"^(?:запусти|открой)\s+([\w\.\-\\/: ]+\.(exe|com|bat|cmd|lnk|html?))$", pm)
        if mr:
            steps.append(make_step("run", cmd=p.split(maxsplit=1)[1].strip()))
            continue
        mu = re.match(r"^(?:открой|перейди)\s+(https?://\S+)$", pm)
        if mu:
            steps.append(make_step("url", url=p.split(maxsplit=1)[1].strip()))
            continue
        # системное действие через матчер синонимов
        if matcher:
            hit = matcher.match(p)
            if hit:
                key, payload = hit
                steps.append(make_step("action", id=key, text=payload))
                continue
        steps.append({"kind": "raw", "text": p})
    return (is_scen, name, steps)
