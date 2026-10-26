# -*- coding: utf-8 -*-
"""
JARVIS v5 · ДЕЙСТВИЯ ВЫСОКОГО УРОВНЯ (высокоуровневые команды)
«запусти хром», «открой фотошопа», «найди котиков в гугле», «сверни всё»,
«увеличь громкость до 30» — исполняет, не требуя от пользователя создавать команды.
Использует actions.ACTIONS + реестр программ Windows + поиск Start-меню.
"""
import os
import re
import sys
import glob
import time
import json
import subprocess
import webbrowser
import urllib.parse

import pyautogui

from .utils import norm, type_russian, extract_num
from .actions import ACTIONS

# Частые программы → как их искать / запускать
KNOWN_PROGRAMS = {
    "хром": ["chrome", "google chrome"],
    "гугл хром": ["chrome"],
    "браузер": ["chrome", "msedge", "firefox"],
    "firefox": ["firefox"],
    "файрфокс": ["firefox"],
    "оперa": ["opera"],
    "опера": ["opera gx", "opera"],
    "edge": ["msedge"],
    "край": ["msedge"],
    "ворд": ["winword"],
    "ексель": ["excel"],
    "эксель": ["excel"],
    "powerpoint": ["powerpnt"],
    "пауэрпойнт": ["powerpnt"],
    "блокнот": ["notepad"],
    "калькулятор": ["calc"],
    "кальк": ["calc"],
    "paint": ["mspaint"],
    "пейнт": ["mspaint"],
    "фотошоп": ["photoshop"],
    "adobe": ["photoshop"],
    "премьер": ["adobe premiere pro"],
    "ворд": ["winword"],
    "спотифай": ["spotify"],
    "дискорд": ["discord"],
    "телеграм": ["telegram"],
    "whatsapp": ["whatsapp"],
    "vscode": ["code"],
    "вс код": ["code"],
    "visual studio code": ["code"],
    "терминал": ["wt", "cmd"],
    "командная строка": ["cmd"],
    "консоль": ["cmd"],
    "powershell": ["powershell"],
    "проводник": ["explorer"],
    "explorer": ["explorer"],
    "диспетчер задач": ["taskmgr"],
    "настройки": ["start ms-settings:"],
    "параметры": ["start ms-settings:"],
    "steam": ["steam"],
    "strem": ["steam"],
    "obs": ["obs64", "obs"],
    "обс": ["obs64", "obs"],
    "vlc": ["vlc"],
    "музыка": ["wmplayer"],
    "видеоплеер": ["wmplayer"],
    "кино": ["wmplayer"],
    "карты": ["start ms-windows-store:"],
}


def _whereis(exe):
    """Ищет exe в PATH и стандартных папках Windows."""
    if sys.platform != "win32":
        return None
    candidates = []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        candidates.append(os.path.join(d, exe + ".exe"))
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    la = os.environ.get("LOCALAPPDATA", "")
    for base in (pf, pf86, la):
        if base:
            candidates += glob.glob(os.path.join(base, "**", exe + ".exe"), recursive=True)[:1]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def start_program(query):
    """Пытается запустить программу по человеческому названию. Возвращает сообщение."""
    q = norm(query)
    exes = KNOWN_PROGRAMS.get(q)
    if not exes:
        # частичное совпадение ключей
        for k, v in KNOWN_PROGRAMS.items():
            if k in q or q in k:
                exes = v
                break
    if exes:
        for exe in exes:
            if exe.startswith("start "):
                try:
                    subprocess.Popen(exe, shell=True)
                    return f"Открываю {q}."
                except Exception:
                    continue
            path = _whereis(exe)
            if path:
                subprocess.Popen(path)
                return f"Запускаю {q}."
            try:
                subprocess.Popen([exe])
                return f"Запускаю {q}."
            except Exception:
                pass
    # 2) через поиск Пуска (Win+S → ввод → Enter) — универсальный способ для любой программы
    try:
        pyautogui.press("winleft")
        time.sleep(0.6)
        type_russian(query)
        time.sleep(1.2)
        pyautogui.press("enter")
        return f"Ищу «{query}» в Пуске и открываю первый результат."
    except Exception as e:
        return f"Не удалось открыть «{query}»: {e}"


def web_search(query, engine="google"):
    url = {
        "google": "https://www.google.com/search?q=",
        "yandex": "https://yandex.ru/search/?text=",
        "youtube": "https://www.youtube.com/results?search_query=",
        "wiki": "https://ru.wikipedia.org/w/index.php?search=",
    }.get(engine, "https://www.google.com/search?q=")
    webbrowser.open(url + urllib.parse.quote(query))
    return f"Ищу «{query}» в {engine}."


def open_site(name):
    """«открой ютуб», «зайди вконтакт» — известные сайты без создания команд."""
    sites = {
        "ютуб": "https://youtube.com", "youtube": "https://youtube.com",
        "вконтакт": "https://vk.com", "vk": "https://vk.com", "вк": "https://vk.com",
        "телеграм веб": "https://web.telegram.org",
        "авито": "https://avito.ru", "озон": "https://ozon.ru", "wildberries": "https://wb.ru",
        "хабр": "https://habr.com", "reddit": "https://reddit.com",
        "гитхаб": "https://github.com", "chatgpt": "https://chat.openai.com",
        "нейросеть": "https://chat.deepseek.com", "deepseek": "https://chat.deepseek.com",
        "почта": "https://mail.google.com", "gmail": "https://gmail.com", "google": "https://google.com",
        "яндек": "https://yandex.ru", "netflix": "https://netflix.com", "кинопоиск": "https://kinopoisk.ru",
        "стим": "https://store.steampowered.com", "twITCH": "https://twitch.tv",
        "переводчик": "https://translate.google.com", "карты": "https://maps.google.com",
    }
    q = norm(name)
    for k, url in sites.items():
        if k in q:
            webbrowser.open(url)
            return f"Открываю {k}."
    # если похоже на домен — идём напрямую
    if re.search(r"\.(ru|com|org|net|io|dev)\b", q):
        m = re.search(r"[\w\-\.]+\.(ru|com|org|net|io|dev)", q)
        if m:
            webbrowser.open("https://" + m.group(0))
            return f"Открываю сайт {m.group(0)}."
    return web_search(q)


SET_VOLUME_RE = re.compile(r"(?:громкость|звук).*(\d{1,3})")
SET_BRIGHT_RE = re.compile(r"(?:яркость|подсветк).*(\d{1,3})")


def smart_execute(text, matcher=None):
    """
    Универсальный исполнитель фразы. Сначала матчер системных команд,
    затем глагольные шаблоны (запусти/открой/найди/перейди), затем ИИ-ответ.
    """
    t = norm(text)
    if matcher:
        hit = matcher.match(text)
        if hit:
            key, payload = hit
            if key == "__websearch":
                return {"kind": "search", "result": web_search(payload)}
            fn = ACTIONS[key][2]
            try:
                res = fn(payload)
                return {"kind": "action", "key": key, "result": res}
            except Exception as e:
                return {"kind": "error", "result": str(e)}
    # глагольные шаблоны
    m = re.match(r"^(?:запусти|открой|включи|стартуй)\s+(.+)$", t)
    if m:
        obj = m.group(1)
        if any(s in obj for s in ("сайт", "http", ".")):
            return {"kind": "site", "result": open_site(obj)}
        return {"kind": "program", "result": start_program(obj)}
    m = re.match(r"^(?:найди|поищи|загугли|поищи в интернете)\s+(?:про\s+)?(.+)$", t)
    if m:
        return {"kind": "search", "result": web_search(m.group(1))}
    m = SET_VOLUME_RE.search(t)
    if m and "громкост" in t or "звук" in t:
        if m:
            v = int(m.group(1))
            from .actions import act_vol_set
            return {"kind": "action", "key": "vol_set", "result": act_vol_set(str(v))}
    return None
