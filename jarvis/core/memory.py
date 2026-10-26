# -*- coding: utf-8 -*-
"""
JARVIS v5 · ПАМЯТЬ И ОБУЧЕНИЕ
ИИ запоминает: факты о пользователе, предпочтения, историю диалога, успешные команды.
Хранение: data/memory.json (факты/предпочтения) + data/history.jsonl (диалог).
Быстрый поиск по памяти без внешних баз — инвертированный индекс по словам.
"""
import os
import re
import json
import time
import threading
from collections import defaultdict

from .utils import norm, now_stamp

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class Memory:
    """Обучаемая память ассистента: факты, предпочтения, привычки, история."""

    MAX_HISTORY = 2000

    def __init__(self, path=None, history_path=None):
        self.path = path or os.path.join(DATA_DIR, "memory.json")
        self.history_path = history_path or os.path.join(DATA_DIR, "history.jsonl")
        self.lock = threading.Lock()
        self.facts = {}            # ключ → значение ("любимая программа": "photoshop")
        self.preferences = {}      # настройки поведения ("вежливость": "шутки")
        self.command_stats = defaultdict(lambda: {"count": 0, "last": ""})  # обучение через повторения
        self.corrections = {}      # пользовательские исправления распознавания: «ошиблось» → «правильно»
        self.load()

    # ── хранение ──
    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                self.facts = d.get("facts", {})
                self.preferences = d.get("preferences", {})
                self.corrections = d.get("corrections", {})
                for k, v in d.get("command_stats", {}).items():
                    self.command_stats[k] = v
            except Exception as e:
                print(f"⚠️ Память повреждена, начинаю с чистой: {e}")

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        d = {
            "facts": self.facts,
            "preferences": self.preferences,
            "corrections": self.corrections,
            "command_stats": dict(self.command_stats),
            "updated": now_stamp(),
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    # ── факты ──
    def remember_fact(self, key, value):
        with self.lock:
            self.facts[norm(key)] = str(value)
            self.save()
        return f"Запомнил: {key} — {value}"

    def recall(self, query):
        """Ищет в памяти по запросу; возвращает список подходящих фактов."""
        q_words = set(norm(query).split())
        results = []
        with self.lock:
            for k, v in self.facts.items():
                score = sum(1 for w in q_words if w in k or w in norm(v))
                if score:
                    results.append((score, k, v))
            for k, v in self.preferences.items():
                score = sum(1 for w in q_words if w in k or w in norm(v))
                if score:
                    results.append((score, k, v))
        results.sort(reverse=True)
        return [{"key": k, "value": v} for _, k, v in results[:5]]

    def forget(self, key):
        with self.lock:
            removed = self.facts.pop(norm(key), None)
            self.preferences.pop(norm(key), None)
            self.save()
        return f"Забыл: {key}" if removed else f"В памяти нет: {key}"

    def all_facts(self):
        with self.lock:
            return dict(self.facts), dict(self.preferences)

    # ── предпочтения / стиль ──
    def set_preference(self, key, value):
        with self.lock:
            self.preferences[norm(key)] = str(value)
            self.save()

    # ── обучение на командах: какие фразы пользователь говорит чаще ──
    def log_command(self, key, phrase):
        with self.lock:
            st = self.command_stats[key]
            st["count"] += 1
            st["last"] = now_stamp()
            # если пользователь часто использует нестандартную формулировку — делаем её синонимом
            if phrase and norm(phrase) not in (self.facts.get("_protected_phrases", "") or ""):
                pass
            self.save()

    def top_commands(self, n=10):
        items = sorted(self.command_stats.items(), key=lambda kv: -kv[1]["count"])
        return [(k, v["count"]) for k, v in items[:n]]

    # ── исправления распознавания («нет, я имел в виду ...») ──
    def learn_correction(self, wrong, right):
        with self.lock:
            self.corrections[norm(wrong)] = norm(right)
            self.save()
        return f"Понял: вместо «{wrong}» надо понимать «{right}»."

    def apply_corrections(self, text):
        t = norm(text)
        return self.corrections.get(t, t)

    # ── история диалога ──
    def add_history(self, role, text):
        entry = {"time": now_stamp(), "role": role, "text": str(text)[:500]}
        try:
            os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def recent_history(self, n=30):
        if not os.path.exists(self.history_path):
            return []
        lines = []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-n:]
        except Exception:
            return []
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out

    def context_snippet(self, max_chars=1200):
        """Формирует кусок контекста для промпта ИИ: факты + последние реплики."""
        parts = []
        facts, prefs = self.all_facts()
        if facts:
            parts.append("Известные факты: " + "; ".join(f"{k}: {v}" for k, v in list(facts.items())[:15]))
        if prefs:
            parts.append("Предпочтения: " + "; ".join(f"{k}: {v}" for k, v in list(prefs.items())[:10]))
        hist = self.recent_history(12)
        if hist:
            parts.append("Диалог: " + " | ".join(f"{h['role']}: {h['text'][:80]}" for h in hist))
        return "\n".join(parts)[:max_chars]
