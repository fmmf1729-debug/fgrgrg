# -*- coding: utf-8 -*-
"""
JARVIS v5 · ОРКЕСТРАТОР (Assistant)
Единая точка входа: принимает фразу (голос или текст), решает — команда это, обучение,
сценарий или диалог с ИИ; выполняет, отвечает текстом и голосом; всё запоминает.
Порядок обработки:
 1) исправления памяти («нет, я имел в виду ...»)
 2) команды управления самим ассистентом (имя, движок, голос, сон/бодрствование)
 3) обучение синонимам / создание команд и сценариев голосом
 4) запуск кастомных команд и сценариев
 5) системные действия (матчер синонимов + высокоуровневые шаблоны)
 6) диалог с выбранным ИИ-движком (бесплатным)
"""
import re
import time
import datetime

from .utils import norm
from .settings import Settings, DANGEROUS_KEYS
from .memory import Memory
from .synonyms import CommandMatcher
from .actions import ACTIONS
from .custom import CustomStore, parse_creation, execute_step
from .brains import BrainManager
from . import highlevel


class Assistant:
    def __init__(self, voice=None, ear=None):
        self.settings = Settings()
        self.memory = Memory()
        self.matcher = CommandMatcher()
        self.custom = CustomStore()
        self.voice = voice
        self.ear = ear
        self.brain = BrainManager(self.settings, self.memory,
                                  self.settings.get("assistant_name"),
                                  self.settings.get("owner_name"))
        self.listening = bool(self.settings.get("wake_enabled", True))
        self.awaiting_confirm = None   # ("dangerous", key, payload)
        self.last_phrase_time = time.time()
        self.on_event = None           # callback(event_dict) для интерфейса

    # ── служебное ──
    def emit(self, kind, **kw):
        ev = {"kind": kind, "time": time.time()}
        ev.update(kw)
        if self.on_event:
            try:
                self.on_event(ev)
            except Exception:
                pass
        return ev

    def say(self, text):
        self.memory.add_history("assistant", text)
        self.emit("speak", text=text)
        if self.voice:
            self.voice.speak(text)
        return text

    # ── главный вход ──
    def process(self, text):
        """Обрабатывает одну фразу. Возвращает строку-ответ."""
        if not text or not str(text).strip():
            return ""
        raw = str(text).strip()
        t = norm(raw)
        # применяем выученные исправления распознавания
        t_corrected = self.memory.apply_corrections(t)
        if t_corrected != t:
            t = t_corrected
        self.memory.add_history("user", raw)
        self.last_phrase_time = time.time()

        # 1) подтверждение опасных действий
        if self.awaiting_confirm:
            if any(w in t for w in ("да", "подтверждаю", "выполняй", "ок", "хорошо", "согласен")):
                kind, key, payload = self.awaiting_confirm
                self.awaiting_confirm = None
                return self._run_action(key, payload, announce=False)
            if any(w in t for w in ("нет", "отмена", "не надо", "не выполняй")):
                self.awaiting_confirm = None
                return self.say("Отменил. Мудрое решение.")
            self.awaiting_confirm = None  # реплика не про подтверждение — обрабатываем дальше

        # 2) управление ассистентом
        resp = self._meta_command(t, raw)
        if resp is not None:
            return self.say(resp)

        # 3) обучение (только если это точно не обычный диалог — начиналось с «научи/запомни»)
        learn = self.matcher.try_learn(raw)
        if learn:
            return self.say(learn["msg"])
        corr = re.match(r"^(?:нет[,:]?\s*)?я имел в виду\s+(.+)$", t)
        if corr and len(corr.group(1)) > 2:
            wrong = norm(raw.split("имел в виду")[0]).strip(" ,нет")
            self.memory.learn_correction(wrong or t, corr.group(1))
            return self.say(f"Понял, буду понимать «{corr.group(1)}».")
        mremember = re.match(r"^запомни(?: те)?[ ,:]*(?:что )?(.+?)\s*(?:=|—|-|это|значит)\s*(.+)$", t)
        if mremember:
            return self.say(self.memory.remember_fact(mremember.group(1), mremember.group(2)))

        # 4) создание команд/сценариев голосом
        created = parse_creation(raw, {"matcher": self.matcher, "engine": self})
        if created:
            is_scen, name, steps = created
            if is_scen:
                msg = self.custom.add_scenario(name, steps)
            else:
                msg = self.custom.add_command(name, steps)
            unknown = [s for s in steps if s.get("kind") == "raw"]
            if unknown:
                msg += " Не распознал шаги: " + "; ".join(s["text"] for s in unknown) + \
                       ". Опишите их иначе или отредактируйте в интерфейсе."
            return self.say(msg)

        # 5) запуск кастомной команды / сценария
        cname, cmd = self.custom.match_command(t)
        if cmd:
            results = []
            for step in cmd["steps"]:
                out = execute_step(step, self)
                results.append(out)
                if step.get("wait"):
                    time.sleep(step["wait"])
                elif step.get("kind") in ("keys", "type", "action", "run", "url"):
                    time.sleep(0.35)
            self.memory.log_command("cmd:" + cname, t)
            return self.say(f"Команда «{cname}»: выполнено {len(cmd['steps'])} шагов.")
        sc = self.custom.scenarios()
        for sname in sc:
            if t == sname or t.endswith(" сценарий " + sname) or re.match(rf"^(?:запусти|выполни|исполни)\s+сценарий\s+{re.escape(sname)}$", t):
                msg = self.custom.run_scenario(sname, self)
                return self.say(msg)

        # 6) системные действия (только уверенные совпадения: точное/открыть/триггер/regex)
        hit = self.matcher.match(t, conservative=True)
        if hit:
            key, payload = hit
            if key == "__websearch":
                return self.say(highlevel.web_search(payload))
            if key in DANGEROUS_KEYS and self.settings.get("confirm_dangerous", True):
                label = ACTIONS[key][0]
                self.awaiting_confirm = ("dangerous", key, payload)
                return self.say(f"{label} — опасное действие. Подтвердите: скажите «да» или «нет».")
            return self._run_action(key, payload)

        # 7) высокоуровневые шаблоны (запусти программу / открой сайт / найди)
        res = highlevel.smart_execute(t, matcher=None)
        if res and res.get("result"):
            return self.say(res["result"])

        # 8) диалог с ИИ
        engine_reply, engine_name = self.brain.ask(raw, history=self.memory.recent_history(14))
        self.emit("ai_reply", engine=engine_name, text=engine_reply)
        reply = self.say(engine_reply)
        # 9) автообучение: если пользователь пересказывает известную команду своими словами —
        # предлагаем сохранить формулировку как синоним (один раз, тихо)
        if self.settings.get("auto_learn", True):
            loose = self.matcher.match(t)
            if loose and not any(w in t for w in ("почему", "зачем", "как ", "что ", "кто ")):
                key = loose[0]
                if len(t.split()) >= 2 and norm(t) not in self.matcher.exact:
                    self.matcher.add_synonym(key, t)
        return reply

    # ── исполнение системного действия ──
    def run_key(self, key, payload=""):
        """Вызывается из шагов сценариев/кастомных команд."""
        return self._run_action(key, payload, announce=False)

    def _run_action(self, key, payload, announce=True):
        action = ACTIONS.get(key)
        if not action:
            return self.say(f"Действие «{key}» не найдено.") if announce else f"Нет действия {key}"
        fn = action[2]
        try:
            result = fn(payload)
        except Exception as e:
            return self.say(f"Ошибка выполнения «{action[0]}»: {e}") if announce else f"Ошибка: {e}"
        self.memory.log_command(key, payload)
        self.emit("action", key=key, label=action[0], report=result or "")
        if isinstance(result, str) and result:
            return self.say(result) if announce else result
        if announce:
            return self.say(random_success(action[0]))
        return action[0]

    # ── управление самим ассистентом ──
    def _meta_command(self, t, raw):
        # переключить мозг: «переключи мозг на оллама/groq/jarvis офлайн»
        m = re.match(r"^(?:переключи|смени|поставь)\s+(?:мозг|ии|нейросеть|движок)\s+(?:на\s+)?(\w+)", t)
        if m:
            alias = {"офлайн": "rules", "правила": "rules", "оллама": "ollama", "локально": "ollama",
                     "lmstudio": "lmstudio", "грок": "groq", "gemini": "gemini", "джимини": "gemini",
                     "openrouter": "openrouter"}
            eng = alias.get(m.group(1), m.group(1))
            if eng in self.brain.engines:
                self.settings.set("engine", eng)
                self.brain.rebuild()
                avail = self.brain.current().name
                return f"Мозг переключён на {eng}. Сейчас активно: {avail}."
            return f"Не знаю движок «{m.group(1)}». Есть: офлайн, оллама, lmstudio, грок, gemini, openrouter."
        # имя ассистента
        m = re.match(r"^(?:назови себя|твое имя|переименуй себя)(?: на)? (.+)", t)
        if m:
            new_name = raw.split(m.group(0)[:10], 1)[-1].strip() or m.group(1)
            self.settings.set("assistant_name", new_name)
            self.brain.person_name = new_name
            self.brain.rebuild()
            return f"Хорошо, теперь меня зовут {new_name}."
        # как меня зовут / владельца
        if re.search(r"как меня зовут", t):
            hits = self.memory.recall("имя пользователя")
            if hits:
                return f"Вас зовут {hits[0]['value']}."
            return "Вы мне ещё не представлялись. Скажите: «меня зовут ...»."
        m = re.match(r"^(?:обращайся ко мне|зови меня) (.+)", t)
        if m:
            who = norm(m.group(1))
            self.settings.set("owner_name", who)
            self.brain.owner_name = who
            self.brain.rebuild()
            return f"Как скажете, {who}."
        # голос
        m = re.match(r"^(?:смени голос|выбери голос|голос) (male|female|мужской|женский)", t)
        if m:
            g = "male" if "male" in m.group(1) or "мужск" in m.group(1) else "female"
            self.settings.set("voice_gender", g)
            if self.voice:
                self.voice.init_backend()
            return "Голос переключён: " + ("мужской" if g == "male" else "женский") + "."
        m = re.match(r"^(?:говорите |говорить )?(быстрее|медленнее)( говорить| речь)?", t)
        if m:
            rate = int(self.settings.get("speech_rate", 200))
            rate = min(320, rate + 30) if m.group(1) == "быстрее" else max(120, rate - 30)
            self.settings.set("speech_rate", rate)
            if self.voice and self.voice.engine:
                self.voice.engine.setProperty("rate", rate)
            return f"Скорость речи: {rate}."
        # сон/пробуждение
        if re.match(r"^(?:спи|засыпай|отдыхай)", t):
            self.listening = False
            return "Засыпаю. Разбудите словом «" + self.settings.get("wake_word") + "» или кнопкой."
        if re.match(r"^(?:проснись|ты тут|ау|эй)", t):
            self.listening = True
            return f"Я здесь, {self.settings.get('owner_name')}."
        # список команд
        if re.match(r"^(список команд|что ты умеешь делать|покажи команды)", t):
            groups = {}
            for k, (label, group, fn, needs) in ACTIONS.items():
                groups.setdefault(group, []).append(label)
            lines = [f"{g}: " + ", ".join(v[:8]) for g, v in sorted(groups.items())]
            cmds = list(self.custom.commands().keys())
            scs = list(self.custom.scenarios().keys())
            extra = []
            if cmds:
                extra.append("Ваши команды: " + ", ".join(cmds[:20]))
            if scs:
                extra.append("Сценарии: " + ", ".join(scs[:20]))
            total = len(ACTIONS) * 15
            return self.say_text_only("Всего системных действий: ~" + str(len(ACTIONS)) +
                                      " (каждое понимает десятки формулировок — всего "
                                      f"{total}+ фраз). " + " | ".join(lines) + " | " + " | ".join(extra))
        # состояние самого джарвиса
        if re.match(r"^(диагностика джарвиса|самодиагностика|проверь себя)", t):
            st = self.brain.status()
            ok = [k for k, v in st.items() if v["available"]]
            return (f"Движки доступны: {', '.join(ok)}. Голос: {self.voice.backend if self.voice else 'нет'}. "
                    f"Слух: {self.ear.backend if self.ear else 'текстовый режим'}. "
                    f"Память: {len(self.memory.facts)} фактов, команд в базе: {len(self.matcher.exact)}.")
        return None

    def say_text_only(self, text):
        """Для длинных списков — печатаем, озвучиваем кратко."""
        self.emit("speak", text=text[:120])
        if self.voice:
            self.voice.speak(text[:120])
        return text


SUCCESS_WORDS = ["Готово", "Выполнено", "Сделано", "Есть", "Как прикажете", "Уже", "Исполнено"]
import random  # noqa: E402


def random_success(label):
    return f"{random.choice(SUCCESS_WORDS)}, {label.lower()}."
