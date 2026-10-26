# -*- coding: utf-8 -*-
"""
JARVIS v5 · БЕСПЛАТНЫЕ ИИ-ДВИЖКИ
Поддерживаемые бесплатные провайдеры (все работают без денег):
 1) Ollama — локальные модели (бесплатно, приватно): llama3.2, qwen2.5, mistral...
 2) LM Studio — локальный сервер совместимый с OpenAI API (http://localhost:1234/v1)
 3) Groq — бесплатный облачный API (быстрый, нужна регистрация и ключ)
 4) Google Gemini — бесплатный уровень API (нужен ключ)
 5) OpenAI-совместимый любой endpoint (OpenRouter free и т.п.)
6) RuleBrain — встроенный офлайн-мозг на правилах + память (работает всегда, 0 рублей)
Переключение движка — в настройках или голосом: «переключи мозг на оллама».
"""
import os
import re
import json
import time
import datetime
import urllib.request
import urllib.error


class BaseEngine:
    name = "base"
    needs_key = False

    def available(self):
        return True

    def chat(self, user_text, context="", history=None):
        raise NotImplementedError

    def info(self):
        return {"name": self.name, "available": self.available(), "needs_key": self.needs_key}


# ═══════════════ ОFFLINE МОЗГ НА ПРАВИЛАХ ═══════════════
class RuleBrain(BaseEngine):
    """Бесплатный офлайн-ассистент: диалог по правилам + опора на память."""
    name = "rules"

    GREET = ["привет", "здравствуй", "хай", "доброе утро", "добрый день", "добрый вечер", "здорово"]
    BYE = ["пока", "до свидания", "прощай", "увидимся", "всё спасибо"]
    THANKS = ["спасибо", "благодарю", "спс", "только ты", "выручил"]

    def __init__(self, memory=None, person_name="Джарвис", owner_name="сэр"):
        self.memory = memory
        self.person_name = person_name
        self.owner_name = owner_name

    def chat(self, text, context="", history=None):
        t = text.lower().strip()
        # приветствия
        if any(g in t for g in self.GREET) and len(t.split()) <= 4:
            hour = datetime.datetime.now().hour
            tod = "Доброе утро" if 5 <= hour < 12 else ("Добрый день" if 12 <= hour < 18 else "Добрый вечер")
            return f"{tod}, {self.owner_name}. Я на связи и готов к работе."
        if any(b in t for b in self.BYE):
            return "До связи, босс. Скажите имя — я вернусь."
        if any(x in t for x in self.THANKS):
            return "Всегда к вашим услугам."
        # кто ты / как тебя зовут
        if re.search(r"как тебя зовут|кто ты|представься", t):
            return f"Я — {self.person_name}, ваш персональный ассистент компьютера. Умею управлять ПК, помнить важное и учиться новым командам."
        # что умеешь
        if re.search(r"что ты умеешь|помощь|возможности|справка", t):
            return ("Управляю звуком, яркостью, окнами, браузером и файлами; запускаю программы; "
                    "делаю скриншоты; слежу за состоянием ПК; помню факты и учу новые команды. "
                    "Скажите «список команд» — покажу всё.")
        # который час / дата
        m = re.search(r"который час|сколько времени", t)
        if m:
            return "Сейчас " + datetime.datetime.now().strftime("%H:%M") + "."
        if re.search(r"какое сегодня число|какой сегодня день|какая дата", t):
            d = datetime.datetime.now()
            wd = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"][d.weekday()]
            return f"Сегодня {d.strftime('%d.%m.%Y')}, {wd}."
        # память: «что ты знаешь про X», «помнишь ли ты ...»
        mm = re.search(r"(?:что ты знаешь про|помнишь(?: ли)?(?: про)?)\s+(.+)", t)
        if mm and self.memory:
            hits = self.memory.recall(mm.group(1))
            if hits:
                return "По этому вопросу в памяти есть: " + "; ".join(f"{h['key']}: {h['value']}" for h in hits)
            return f"Про «{mm.group(1)}» я пока ничего не знаю. Скажите «запомни, что ...»."
        # запомни факт: «запомни что меня зовут Иван» / «запомни любимый браузер = хром»
        mf = re.match(r"^запомни(?: те)?[ ,:]*(?:что )?(.+?)\s*(?:это|=|—|-)\s*(.+)$", t)
        if not mf:
            mf2 = re.match(r"^запомни(?: те)?[ ,:]*(?:что )?(.+?)\s+(как|в значит|значит)\s+(.+)$", t)
            mf = mf2
        if mf and self.memory:
            key, val = mf.group(1).strip(), mf.group(3 if mf.lastindex and mf.lastindex >= 3 else 2).strip()
            self.memory.remember_fact(key, val)
            return f"Запомнил: {key} — {val}."
        mname = re.search(r"(?:меня зовут|моё имя|мое имя)\s+(\w+)", t)
        if mname and self.memory:
            self.memory.remember_fact("имя пользователя", mname.group(1))
            return f"Запомнил, вас зовут {mname.group(1)}. Приятно познакомиться."
        # «как дела»
        if re.search(r"как дела|как сам|как настроение", t):
            return "Все системы в норме, процессор бодр, настроение рабочее. А у вас?"
        # поиск в памяти по одному слову
        if self.memory:
            hits = self.memory.recall(t)
            if hits and len(t.split()) >= 2:
                return "Из памяти: " + "; ".join(f"{h['key']}: {h['value']}" for h in hits[:3])
        # fallback — вежливо просим уточнить и предлагаем вариант
        return ("Интересный вопрос. В офлайн-режиме я силён в командах ПК и памяти. "
                "Для свободной беседы подключите локальную модель (Ollama) или бесплатный ключ — "
                "настройки → ИИ-движок. А что именно сделать на компьютере?")

    def available(self):
        return True


# ═══════════════ OLLAMA (локально, бесплатно) ═══════════════
class OllamaEngine(BaseEngine):
    name = "ollama"

    def __init__(self, model="llama3.2", host="http://localhost:11434", person_name="Джарвис"):
        self.model = model
        self.host = host.rstrip("/")
        self.person_name = person_name

    def list_models(self):
        try:
            req = urllib.request.Request(self.host + "/api/tags")
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.loads(r.read().decode())
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def available(self):
        try:
            urllib.request.urlopen(self.host + "/api/tags", timeout=2)
            return True
        except Exception:
            return False

    def chat(self, text, context="", history=None):
        sys_prompt = (f"Ты — {self.person_name}, ассистент Windows. Отвечай коротко, по-русски, дружелюбно. "
                      f"Контекст о пользователе:\n{context}")
        msgs = [{"role": "system", "content": sys_prompt}]
        for h in (history or [])[-8:]:
            msgs.append({"role": h["role"], "content": h["text"]})
        msgs.append({"role": "user", "content": text})
        payload = json.dumps({"model": self.model, "messages": msgs, "stream": False}).encode()
        req = urllib.request.Request(self.host + "/api/chat", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
        return data.get("message", {}).get("content", "Модель не ответила.").strip()


# ═══════════════ OPENAI-СОВМЕСТИМЫЙ (LM Studio / OpenRouter / Groq / Gemini через shim) ═══════════════
class OpenAICompatEngine(BaseEngine):
    def __init__(self, name_label, base_url, api_key="", model="", person_name="Джарвис", docs_url=""):
        self.name = name_label
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.person_name = person_name
        self.docs_url = docs_url
        self.needs_key = bool(api_key is not None) and "key" in (name_label or "")

    def available(self):
        if not self.model:
            return False
        if self.base_url.startswith("http://localhost") or self.base_url.startswith("http://127"):
            try:
                urllib.request.urlopen(self.base_url + "/models", timeout=2)
                return True
            except Exception:
                return False
        return bool(self.api_key)

    def chat(self, text, context="", history=None):
        sys_prompt = (f"Ты — {self.person_name}, ассистент Windows. Отвечай кратко, по-русски. "
                      f"Контекст:\n{context}")
        msgs = [{"role": "system", "content": sys_prompt}]
        for h in (history or [])[-8:]:
            msgs.append({"role": h["role"], "content": h["text"]})
        msgs.append({"role": "user", "content": text})
        payload = json.dumps({"model": self.model, "messages": msgs, "temperature": 0.7}).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.base_url + "/chat/completions", data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode())
        return data["choices"][0]["message"]["content"].strip()


# ═══════════════ GOOGLE GEMINI (бесплатный уровень) ═══════════════
class GeminiEngine(BaseEngine):
    name = "gemini"
    needs_key = True

    def __init__(self, api_key="", model="gemini-1.5-flash", person_name="Джарвис"):
        self.api_key = api_key
        self.model = model
        self.person_name = person_name

    def available(self):
        return bool(self.api_key)

    def chat(self, text, context="", history=None):
        sys_prompt = (f"Ты — {self.person_name}, ассистент Windows. Отвечай кратко, по-русски. "
                      f"Контекст:\n{context}")
        convo = []
        for h in (history or [])[-8:]:
            role = "model" if h["role"] == "assistant" else "user"
            convo.append({"role": role, "parts": [{"text": h["text"]}]})
        convo.append({"role": "user", "parts": [{"text": text}]})
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
               f"?key={self.api_key}")
        payload = json.dumps({"system_instruction": {"parts": [{"text": sys_prompt}]},
                              "contents": convo}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            return "Gemini не ответил корректно."


# ═══════════════ МЕНЕДЖЕР ДВИЖКОВ ═══════════════
class BrainManager:
    """Держит все движки, переключает, даёт отказоустойчивую цепочку (fallback)."""

    def __init__(self, settings, memory, person_name="Джарвис", owner_name="сэр"):
        self.settings = settings
        self.memory = memory
        self.person_name = person_name
        self.owner_name = owner_name
        self.engines = {}
        self.rebuild()

    def rebuild(self):
        s = self.settings.data
        self.engines = {
            "rules": RuleBrain(self.memory, self.person_name, self.owner_name),
            "ollama": OllamaEngine(s.get("ollama_model", "llama3.2"),
                                   s.get("ollama_host", "http://localhost:11434"), self.person_name),
            "lmstudio": OpenAICompatEngine("lmstudio",
                                           s.get("lmstudio_host", "http://localhost:1234/v1"),
                                           "", s.get("lmstudio_model", ""), self.person_name),
            "groq": OpenAICompatEngine("groq", "https://api.groq.com/openai/v1",
                                       s.get("groq_key", ""), s.get("groq_model", "llama-3.3-70b-versatile"),
                                       self.person_name),
            "openrouter": OpenAICompatEngine("openrouter", "https://openrouter.ai/api/v1",
                                             s.get("openrouter_key", ""),
                                             s.get("openrouter_model", "meta-llama/llama-3.3-70b-instruct:free"),
                                             self.person_name),
            "gemini": GeminiEngine(s.get("gemini_key", ""), s.get("gemini_model", "gemini-1.5-flash"),
                                   self.person_name),
            "custom": OpenAICompatEngine("custom", s.get("custom_base_url", ""),
                                         s.get("custom_key", ""), s.get("custom_model", ""), self.person_name),
        }

    def current(self):
        pref = self.settings.data.get("engine", "rules")
        eng = self.engines.get(pref)
        if eng and eng.available():
            return eng
        # fallback-цепочка: ollama → lmstudio → groq → gemini → openrouter → custom → rules
        for alt in ("ollama", "lmstudio", "groq", "gemini", "openrouter", "custom"):
            e = self.engines.get(alt)
            if e and e.available():
                return e
        return self.engines["rules"]

    def ask(self, text, history=None):
        engine = self.current()
        ctx = self.memory.context_snippet() if self.memory else ""
        try:
            reply = engine.chat(text, ctx, history)
            return reply, engine.name
        except Exception as e:
            # если облако/локальная модель упала — молча садимся на офлайн-мозг
            fb = self.engines["rules"]
            try:
                return fb.chat(text, ctx, history), "rules(fallback)"
            except Exception:
                return "Мой мозг временно недоступен: " + str(e)[:80], "error"

    def status(self):
        out = {}
        for k, e in self.engines.items():
            out[k] = e.info()
        return out
