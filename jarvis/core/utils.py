# -*- coding: utf-8 -*-
"""
JARVIS v5 · УТИЛИТЫ
Нормализация текста, ввод кириллицы, извлечение чисел, таймстампы.
"""
import re
import time
import datetime

import pyperclip
import pyautogui


def norm(text):
    """Приводит фразу к сопоставимому виду: нижний регистр, один пробел, без знаков препинания."""
    t = str(text or "").lower().strip()
    t = t.replace("ё", "е")
    t = re.sub(r"[^\w\s\u0400-\u04ff]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def type_russian(text):
    """Ввод через буфер обмена — pyautogui.write не знает кириллицу."""
    pyperclip.copy(text)
    time.sleep(0.05)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.05)


_NUM_WORDS_RU = {
    "ноль": 0, "один": 1, "два": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6,
    "семь": 7, "восемь": 8, "девять": 9, "десять": 10, "дцать": 10,
    "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14,
    "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18,
    "девятнадцать": 19, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
    "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90, "сто": 100,
}


def extract_num(text):
    """Достаёт число из фразы: цифрами или русскими словами ('громкость пятьдесят' → 50)."""
    m = re.search(r"\d+", str(text or ""))
    if m:
        return int(m.group())
    t = norm(text)
    total = 0
    found = False
    for w in t.split():
        if w in _NUM_WORDS_RU:
            total += _NUM_WORDS_RU[w]
            found = True
    return total if found else None


def now_stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def timestamp_fname():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
