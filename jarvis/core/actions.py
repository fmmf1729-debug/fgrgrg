# -*- coding: utf-8 -*-
"""
JARVIS v5 · БАЗА ДЕЙСТВИЙ (System Actions)
Каждое действие = id → (метка, группа, обработчик).
Обработчик получает распознанный текст и опциональное число.
База рассчитана на масштабирование: добавляйте действия словарём ACTIONS.
"""
import os
import re
import sys
import time
import json
import shutil
import subprocess
import webbrowser
import urllib.parse
import datetime

import pyautogui
import pyperclip

try:
    import screen_brightness_control as sbc
except ImportError:
    sbc = None

try:
    import psutil
except ImportError:
    psutil = None

from .utils import norm, type_russian, extract_num, timestamp_fname

pyautogui.PAUSE = 0.01
pyautogui.FAILSAFE = True


# ═══════════════ ПОМОЩНИКИ ═══════════════
def _key(*keys):
    pyautogui.hotkey(*keys, _pause=False)


def _press(key, n=1):
    pyautogui.press(key, presses=n, _pause=False)


def _open_url(url):
    webbrowser.open(url)


def _run(cmd, shell=True):
    subprocess.Popen(cmd, shell=shell, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _volume_set(pct):
    """Громкость Windows через PowerShell (точнее, чем 50 нажатий)."""
    try:
        ps = f"(New-Object -ComObject WScript.Shell).SendKeys([char]175)"
        # fallback: клавиши
        _press("volumedown", 100)
        _press("volumeup", max(1, int(pct / 2)))
    except Exception:
        pass


def _brightness_get():
    if not sbc:
        return None
    b = sbc.get_brightness()
    return b[0] if isinstance(b, list) else b


# ═══════════════ ЗВУК ═══════════════
def act_vol_up(t=None):
    _press("volumeup", 5)


def act_vol_down(t=None):
    _press("volumedown", 5)


def act_vol_mute(t=None):
    _press("volumemute")


def act_vol_max(t=None):
    _press("volumeup", 50)


def act_vol_min(t=None):
    _press("volumedown", 50)


def act_vol_set(t):
    v = extract_num(t)
    if v is None:
        return "Скажите число, например «громкость 50»."
    _press("volumedown", 100)
    _press("volumeup", max(1, min(50, int(v / 2))))
    return f"Громкость {v} процентов."


# ═══════════════ ЯРКОСТЬ ═══════════════
def act_bright_up(t=None):
    if not sbc:
        return "Модуль яркости не установлен (pip install screen-brightness-control)."
    sbc.set_brightness(min(100, (_brightness_get() or 50) + 15))


def act_bright_down(t=None):
    if not sbc:
        return "Модуль яркости не установлен (pip install screen-brightness-control)."
    sbc.set_brightness(max(0, (_brightness_get() or 50) - 15))


def act_bright_set(t):
    if not sbc:
        return "Модуль яркости не установлен."
    v = extract_num(t)
    if v is None:
        return "Назовите число, например «яркость 70»."
    sbc.set_brightness(max(0, min(100, v)))
    return f"Яркость {v} процентов."


def act_night_light(t=None):
    _open_url("ms-settings:display")
    return "Открыл настройки экрана — там есть ночной свет."


# ═══════════════ ОКНА ═══════════════
def act_win_close(t=None):
    _key("alt", "f4")


def act_win_min(t=None):
    _key("win", "down")


def act_win_max(t=None):
    _key("win", "up")


def act_win_switch(t=None):
    _key("alt", "tab")


def act_snap_left(t=None):
    _key("win", "left")


def act_snap_right(t=None):
    _key("win", "right")


def act_snap_top(t=None):
    _key("win", "up")


def act_show_desktop(t=None):
    _key("win", "d")


def act_win_task_view(t=None):
    _key("win", "tab")


def act_win_projector(t=None):
    _key("win", "p")


def act_win_move_center(t=None):
    """Центрирует активное окно примерно по экрану."""
    w, h = pyautogui.size()
    try:
        win = pyautogui.getActiveWindow()
        if win:
            pyautogui.moveTo(w // 2, h // 2)
    except Exception:
        pass


# ═══════════════ ВКЛАДКИ / БРАУЗЕР ═══════════════
def act_tab_new(t=None):
    _key("ctrl", "t")


def act_tab_close(t=None):
    _key("ctrl", "w")


def act_tab_next(t=None):
    _key("ctrl", "tab")


def act_tab_prev(t=None):
    _key("ctrl", "shift", "tab")


def act_page_refresh(t=None):
    _press("f5")


def act_tab_restore(t=None):
    _key("ctrl", "shift", "t")


def act_incognito(t=None):
    _key("ctrl", "shift", "n")


def act_address_bar(t=None):
    _key("ctrl", "l")


def act_bookmark(t=None):
    _key("ctrl", "d")


def act_find_page(t=None):
    _key("ctrl", "f")


def act_print_page(t=None):
    _key("ctrl", "p")


def act_history(t=None):
    _key("ctrl", "h")


def act_downloads(t=None):
    _key("ctrl", "j")


def act_zoom_in(t=None):
    _key("ctrl", "+")


def act_zoom_out(t=None):
    _key("ctrl", "-")


def act_zoom_reset(t=None):
    _key("ctrl", "0")


def act_fullscreen(t=None):
    _press("f11")


# ═══════════════ ПРОВОДНИК / ФАЙЛЫ ═══════════════
def act_explorer_open(t=None):
    _key("win", "e")


def act_folder_new(t=None):
    _key("ctrl", "shift", "n")


def act_file_delete(t=None):
    _press("delete")


def act_file_rename(t=None):
    _press("f2")


def act_file_props(t=None):
    _key("alt", "enter")


def act_copy_path(t=None):
    _key("ctrl", "shift", "c")


def act_nav_back(t=None):
    _key("alt", "left")


def act_nav_fwd(t=None):
    _key("alt", "right")


def act_nav_up(t=None):
    _key("alt", "up")


def act_explorer_search(t=None):
    _key("ctrl", "f")


def act_select_all_files(t=None):
    _key("ctrl", "a")


def act_recycle_open(t=None):
    _run("explorer shell:RecycleBinFolder")


def act_create_file_desktop(t):
    """Создать файл на рабочем столе по имени из фразы: 'создай файл заметки.txt'."""
    m = re.search(r"(?:файл|документ)\s+([\w\.\-\u0400-\u04ff]+)", norm(t))
    name = m.group(1) if m else "новый_файл.txt"
    desk = os.path.join(os.path.expanduser("~"), "Desktop")
    path = os.path.join(desk, name)
    open(path, "a", encoding="utf-8").close()
    return f"Файл {name} создан на рабочем столе."


def act_create_folder_desktop(t):
    m = re.search(r"(?:папку|каталог)\s+(?:по имени |под названием )?([\w\-\u0400-\u04ff ]+?)(?:$|\s+(?:на|в )\w)", norm(t))
    name = (m.group(1).strip() if m else "новая папка") or "новая папка"
    desk = os.path.join(os.path.expanduser("~"), "Desktop")
    path = os.path.join(desk, name)
    os.makedirs(path, exist_ok=True)
    return f"Папка «{name}» создана на рабочем столе."


def act_open_documents(t=None):
    _run('explorer "%s"' % os.path.expanduser("~/Documents"))


def act_open_downloads(t=None):
    _run('explorer "%s"' % os.path.expanduser("~/Downloads"))


def act_open_picture_dir(t=None):
    _run('explorer "%s"' % os.path.expanduser("~/Pictures"))


def act_clean_temp(t=None):
    """Чистка временных файлов пользователя."""
    tmp = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp") or os.environ.get("TEMP", "")
    removed = 0
    freed = 0
    if tmp and os.path.isdir(tmp):
        for f in os.listdir(tmp):
            p = os.path.join(tmp, f)
            try:
                if os.path.isfile(p):
                    freed += os.path.getsize(p)
                    os.remove(p)
                    removed += 1
            except Exception:
                pass
    return f"Удалил {removed} временных файлов, освобождено ~{freed // 1024} КБ."


# ═══════════════ ПУСК / СИСТЕМА ═══════════════
def act_start_open(t=None):
    _press("winleft")


def act_start_close(t=None):
    _press("escape")


def act_run_dialog(t=None):
    _key("win", "r")


def act_task_manager(t=None):
    _key("ctrl", "shift", "esc")


def act_settings(t=None):
    _key("win", "i")


def act_lock(t=None):
    _key("win", "l")


def act_signout(t=None):
    _run("shutdown /l")


def act_sleep(t=None):
    if sys.platform == "win32":
        _run('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
    return "Перевожу систему в спящий режим."


def act_shutdown_pc(t=None):
    if sys.platform == "win32":
        _run("shutdown /s /t 5")
        return "Выключение через 5 секунд. Скажите «отмени выключение»."


def act_restart_pc(t=None):
    if sys.platform == "win32":
        _run("shutdown /r /t 5")
        return "Перезагрузка через 5 секунд. Скажите «отмени выключение»."


def act_cancel_shutdown(t=None):
    if sys.platform == "win32":
        _run("shutdown /a")
        return "Отменил завершение работы."


def act_screenshot(t=None):
    _key("win", "shift", "s")


def act_screenshot_full(t=None):
    _press("printscreen")


def act_keyboard_caps(t=None):
    _press("capslock")


# ═══════════════ МЕДИА ═══════════════
def act_track_next(t=None):
    _press("nexttrack")


def act_track_prev(t=None):
    _press("prevtrack")


def act_track_pause(t=None):
    _press("playpause")


def act_track_play(t=None):
    _press("playpause")


def act_media_stop(t=None):
    _press("stop")


# ═══════════════ КЛАВИАТУРА / БУФЕР ═══════════════
def act_key_enter(t=None):
    _press("enter")


def act_key_space(t=None):
    _press("space")


def act_key_copy(t=None):
    _key("ctrl", "c")


def act_key_paste(t=None):
    _key("ctrl", "v")


def act_key_cut(t=None):
    _key("ctrl", "x")


def act_key_selectall(t=None):
    _key("ctrl", "a")


def act_key_undo(t=None):
    _key("ctrl", "z")


def act_key_redo(t=None):
    _key("ctrl", "y")


def act_key_save(t=None):
    _key("ctrl", "s")


def act_key_print(t=None):
    _key("ctrl", "p")


def act_clipboard_clear(t=None):
    pyperclip.copy("")
    return "Буфер обмена очищен."


# ═══════════════ МЫШЬ ═══════════════
def act_mouse_click(t=None):
    pyautogui.click()


def act_mouse_rclick(t=None):
    pyautogui.click(button="right")


def act_mouse_dblclick(t=None):
    pyautogui.doubleClick()


def act_mouse_middle(t=None):
    pyautogui.click(button="middle")


def act_scroll_up(t=None):
    pyautogui.scroll(600)


def act_scroll_down(t=None):
    pyautogui.scroll(-600)


def act_mouse_to_center(t=None):
    w, h = pyautogui.size()
    pyautogui.moveTo(w // 2, h // 2)


def act_drag_window(t=None):
    """Перетаскивает активное окно заголовок → центр экрана (через Alt+Dragn мышь)."""
    w, h = pyautogui.size()
    _key("alt", "space")
    _press("m")
    pyautogui.moveRel(100, 100, duration=0.3)
    pyautogui.click()


# ═══════════════ ПОИСК / ИНТЕРНЕТ ═══════════════
def act_google_maps(t):
    q = re.sub(r"^(найди|покажи|карты)\s*", "", norm(t))
    _open_url("https://www.google.com/maps/search/" + urllib.parse.quote(q))


def act_youtube(t):
    q = re.sub(r"^(найди|посмотри|включи|открой)\s*(на ютубе|ютуб)?\s*", "", norm(t))
    _open_url("https://www.youtube.com/results?search_query=" + urllib.parse.quote(q))


def act_wiki(t):
    q = re.sub(r"^(вики|википедия)\s*", "", norm(t))
    _open_url("https://ru.wikipedia.org/w/index.php?search=" + urllib.parse.quote(q))


# ═══════════════ МОНИТОРИНГ ═══════════════
PROTECTED = {"system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
             "svchost.exe", "dwm.exe", "explorer.exe", "winlogon.exe", "fontdrvhost.exe", "sihost.exe",
             "taskhostw.exe", "conhost.exe", "searchhost.exe", "runtimebroker.exe",
             "shellexperiencehost.exe", "startmenuexperiencehost.exe", "textinputhost.exe",
             "applicationframehost.exe"}


def get_temperature():
    if psutil:
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                core = temps.get("coretemp") or next(iter(temps.values()))
                return max(t.current for t in core)
        except Exception:
            pass
    try:
        import wmi
        for ns in ("LibreHardwareMonitor", "OpenHardwareMonitor"):
            try:
                w = wmi.WMI(namespace=f"root\\{ns}")
                vals = [float(s.Value) for s in w.Sensor() if s.SensorType == "Temperature" and s.Value]
                if vals:
                    return max(vals)
            except Exception:
                continue
        w = wmi.WMI(namespace="root\\wmi")
        t = [int(x.CurrentTemperature) for x in w.MSAcpi_ThermalZoneTemperature()]
        if t:
            return (max(t) - 2732) / 10
    except Exception:
        pass
    return None


def system_report(t=None):
    if not psutil:
        return "psutil не установлен — состояние недоступно. pip install psutil"
    try:
        cpu = psutil.cpu_percent(interval=0.4)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\" if sys.platform == "win32" else "/")
        temp = get_temperature()
        for p in psutil.process_iter():
            try:
                p.cpu_percent()
            except Exception:
                pass
        time.sleep(0.5)
        tops = []
        for p in psutil.process_iter(["name"]):
            try:
                c = p.cpu_percent()
                if c > 1:
                    tops.append((c, p.info["name"]))
            except Exception:
                pass
        tops.sort(reverse=True)
        rep = f"Температура {int(temp)} градусов. " if temp else "Датчики температуры недоступны. "
        rep += (f"Процессор {int(cpu)} процентов. Память {int(ram.percent)} процентов из "
                f"{round(ram.total / 1024 ** 3)} гигабайт. Диск занят на {int(disk.percent)} процентов.")
        if tops:
            rep += " Сильнее всего грузят: " + ", ".join(f"{n} — {int(c)} процентов" for c, n in tops[:2]) + "."
            if cpu > 80 or (temp and temp > 80):
                rep += " Нагрузка критическая. Скажите «охладись» — закрою тяжёлое."
        else:
            rep += " Система отдыхает, всё спокойно."
        return rep
    except Exception as e:
        return f"Не удалось прочитать датчики: {e}"


def cool_down_report(t=None):
    if not psutil:
        return "Не установлен psutil — не вижу процессы."
    try:
        me = os.getpid()
        for p in psutil.process_iter():
            try:
                p.cpu_percent()
            except Exception:
                pass
        time.sleep(0.7)
        victims = []
        for p in psutil.process_iter(["name", "pid"]):
            try:
                name = (p.info["name"] or "").lower()
                c = p.cpu_percent()
                if p.pid == me or name in PROTECTED or "python" in name or "jarvis" in name:
                    continue
                if c >= 5:
                    victims.append((c, p))
            except Exception:
                pass
        victims.sort(key=lambda x: -x[0])
        closed = []
        for c, p in victims[:3]:
            try:
                nm = p.info["name"]
                p.terminate()
                try:
                    p.wait(timeout=2)
                except Exception:
                    p.kill()
                closed.append(nm)
            except Exception:
                pass
        if closed:
            return f"Закрыл тяжёлые процессы: {', '.join(closed)}. Стало прохладнее, босс."
        return "Тяжёлых процессов не нашёл — система и так дышит спокойно."
    except Exception as e:
        return f"Не получилось разгрузить: {e}"


def battery_status(t=None):
    if not psutil:
        return "psutil не установлен."
    b = psutil.sensors_battery()
    if not b:
        return "Батарея не найдена (возможно, ПК стационарный)."
    msg = f"Заряд {int(b.percent)} процентов. "
    msg += "Сеть, зарядка идёт. " if b.power_plugged else f"Хватит ещё на {int(b.secsleft // 60)} минут."
    return msg


def list_processes(t=None):
    if not psutil:
        return "psutil не установлен."
    procs = []
    for p in psutil.process_iter(["name"]):
        try:
            procs.append(p.info["name"])
        except Exception:
            pass
    uniq = sorted(set(procs))
    return "Открытые приложения: " + ", ".join(uniq[:15]) + ("..." if len(uniq) > 15 else "")


def kill_process_by_name(t):
    """«убей process chrome» — закрывает процесс по имени из фразы."""
    if not psutil:
        return "psutil не установлен."
    m = re.search(r"(?:убей|закрой|останови)\s+(?:процесс\s+|приложение\s+)?(\w[\w\-\.]*)", norm(t))
    if not m:
        return "Назовите имя процесса, например «убей процесс chrome»."
    target = m.group(1).lower()
    killed = 0
    me = os.getpid()
    for p in psutil.process_iter(["name", "pid"]):
        try:
            nm = (p.info["name"] or "").lower()
            if p.info["pid"] != me and target in nm and nm not in PROTECTED:
                p.terminate()
                killed += 1
        except Exception:
            pass
    return f"Закрыл процессов «{target}»: {killed}." if killed else f"Процесс «{target}» не найден."


# ═══════════════ УДАЛЕНИЕ / БЕЗОПАСНОСТЬ ═══════════════
def act_empty_recycle(t=None):
    if sys.platform == "win32":
        _run('powershell -Command "Clear-RecycleBin -Force"')
        return "Корзина очищена."
    return "Очистка корзины доступна на Windows."


# ═══════════════ ТАБЛИЦА ДЕЙСТВИЙ ═══════════════
# id: (метка, группа, функция, требует_ли_продолжения)
ACTIONS = {
    # Звук
    "vol_up": ("Громче", "🔊 Звук", act_vol_up, False),
    "vol_down": ("Тише", "🔊 Звук", act_vol_down, False),
    "vol_mute": ("Без звука", "🔊 Звук", act_vol_mute, False),
    "vol_max": ("Максимум звука", "🔊 Звук", act_vol_max, False),
    "vol_min": ("Минимум звука", "🔊 Звук", act_vol_min, False),
    "vol_set": ("Громкость N", "🔊 Звук", act_vol_set, True),
    # Яркость
    "bright_up": ("Ярче", "🖥 Экран", act_bright_up, False),
    "bright_down": ("Темнее", "🖥 Экран", act_bright_down, False),
    "bright_set": ("Яркость N", "🖥 Экран", act_bright_set, True),
    "night_light": ("Ночной свет", "🖥 Экран", act_night_light, False),
    "fullscreen": ("Полный экран", "🖥 Экран", act_fullscreen, False),
    "zoom_in": ("Приблизить", "🖥 Экран", act_zoom_in, False),
    "zoom_out": ("Отдалить", "🖥 Экран", act_zoom_out, False),
    "zoom_reset": ("Масштаб сбросить", "🖥 Экран", act_zoom_reset, False),
    # Окна
    "win_close": ("Закрыть окно", "🪟 Окна", act_win_close, False),
    "win_min": ("Свернуть", "🪟 Окна", act_win_min, False),
    "win_max": ("Развернуть", "🪟 Окна", act_win_max, False),
    "win_switch": ("Переключить окно", "🪟 Окна", act_win_switch, False),
    "snap_left": ("Прижать влево", "🪟 Окна", act_snap_left, False),
    "snap_right": ("Прижать вправо", "🪟 Окна", act_snap_right, False),
    "snap_top": ("Прижать вверх", "🪟 Окна", act_snap_top, False),
    "show_desktop": ("Рабочий стол", "🪟 Окна", act_show_desktop, False),
    "task_view": ("Обзор окон", "🪟 Окна", act_win_task_view, False),
    "projector": ("Проектор/экраны", "🪟 Окна", act_win_projector, False),
    # Браузер
    "tab_new": ("Новая вкладка", "🌐 Браузер", act_tab_new, False),
    "tab_close": ("Закрыть вкладку", "🌐 Браузер", act_tab_close, False),
    "tab_next": ("Следующая вкладка", "🌐 Браузер", act_tab_next, False),
    "tab_prev": ("Предыдущая вкладка", "🌐 Браузер", act_tab_prev, False),
    "page_refresh": ("Обновить страницу", "🌐 Браузер", act_page_refresh, False),
    "tab_restore": ("Вернуть вкладку", "🌐 Браузер", act_tab_restore, False),
    "incognito": ("Инкогнито", "🌐 Браузер", act_incognito, False),
    "address_bar": ("Адресная строка", "🌐 Браузер", act_address_bar, False),
    "bookmark": ("В закладки", "🌐 Браузер", act_bookmark, False),
    "find_page": ("Поиск на странице", "🌐 Браузер", act_find_page, False),
    "print_page": ("Печать страницы", "🌐 Браузер", act_print_page, False),
    "history": ("История браузера", "🌐 Браузер", act_history, False),
    "downloads": ("Загрузки", "🌐 Браузер", act_downloads, False),
    # Проводник
    "explorer_open": ("Открыть проводник", "📁 Файлы", act_explorer_open, False),
    "folder_new": ("Создать папку", "📁 Файлы", act_folder_new, False),
    "file_delete": ("Удалить", "📁 Файлы", act_file_delete, False),
    "file_rename": ("Переименовать", "📁 Файлы", act_file_rename, False),
    "file_props": ("Свойства", "📁 Файлы", act_file_props, False),
    "copy_path": ("Скопировать путь", "📁 Файлы", act_copy_path, False),
    "nav_back": ("Назад (папки)", "📁 Файлы", act_nav_back, False),
    "nav_fwd": ("Вперёд (папки)", "📁 Файлы", act_nav_fwd, False),
    "nav_up": ("Вверх (папки)", "📁 Файлы", act_nav_up, False),
    "explorer_search": ("Поиск в папке", "📁 Файлы", act_explorer_search, False),
    "select_all_files": ("Выделить всё", "📁 Файлы", act_select_all_files, False),
    "recycle_open": ("Открыть корзину", "📁 Файлы", act_recycle_open, False),
    "empty_recycle": ("Очистить корзину", "📁 Файлы", act_empty_recycle, False),
    "clean_temp": ("Почистить temp", "📁 Файлы", act_clean_temp, False),
    "open_documents": ("Мои документы", "📁 Файлы", act_open_documents, False),
    "open_downloads": ("Папка загрузок", "📁 Файлы", act_open_downloads, False),
    "open_pictures": ("Мои картинки", "📁 Файлы", act_open_picture_dir, False),
    "create_folder_named": ("Создать папку <имя>", "📁 Файлы", act_create_folder_desktop, True),
    "create_file_named": ("Создать файл <имя>", "📁 Файлы", act_create_file_desktop, True),
    # Система
    "start_open": ("Открыть Пуск", "🚀 Система", act_start_open, False),
    "start_close": ("Закрыть Пуск", "🚀 Система", act_start_close, False),
    "run_dialog": ("Окно «Выполнить»", "🚀 Система", act_run_dialog, False),
    "task_manager": ("Диспетчер задач", "🚀 Система", act_task_manager, False),
    "settings": ("Параметры Windows", "🚀 Система", act_settings, False),
    "screenshot": ("Скриншот", "🚀 Система", act_screenshot, False),
    "screenshot_full": ("Скриншот всего экрана", "🚀 Система", act_screenshot_full, False),
    "lock": ("Блокировка", "🚀 Система", act_lock, False),
    "signout": ("Выйти из системы", "🚀 Система", act_signout, False),
    "sleep": ("Спящий режим", "🚀 Система", act_sleep, False),
    "shutdown_pc": ("Выключить ПК", "🚀 Система", act_shutdown_pc, False),
    "restart_pc": ("Перезагрузить ПК", "🚀 Система", act_restart_pc, False),
    "cancel_shutdown": ("Отменить выключение", "🚀 Система", act_cancel_shutdown, False),
    "sys_status": ("Состояние ПК", "📊 Мониторинг", system_report, False),
    "sys_cool": ("Охладись", "📊 Мониторинг", cool_down_report, False),
    "battery": ("Заряд батареи", "📊 Мониторинг", battery_status, False),
    "list_processes": ("Что открыто", "📊 Мониторинг", list_processes, False),
    "kill_process": ("Убить процесс <имя>", "📊 Мониторинг", kill_process_by_name, True),
    # Медиа
    "track_next": ("Следующий трек", "🎵 Медиа", act_track_next, False),
    "track_prev": ("Предыдущий трек", "🎵 Медиа", act_track_prev, False),
    "track_pause": ("Пауза музыки", "🎵 Медиа", act_track_pause, False),
    "track_play": ("Играть музыку", "🎵 Медиа", act_track_play, False),
    "media_stop": ("Стоп воспроизведение", "🎵 Медиа", act_media_stop, False),
    # Клавиатура
    "key_enter": ("Enter", "⌨️ Клавиатура", act_key_enter, False),
    "key_space": ("Пробел / пауза", "⌨️ Клавиатура", act_key_space, False),
    "key_copy": ("Копировать", "⌨️ Клавиатура", act_key_copy, False),
    "key_paste": ("Вставить", "⌨️ Клавиатура", act_key_paste, False),
    "key_cut": ("Вырезать", "⌨️ Клавиатура", act_key_cut, False),
    "key_selectall": ("Выделить всё", "⌨️ Клавиатура", act_key_selectall, False),
    "key_undo": ("Отменить", "⌨️ Клавиатура", act_key_undo, False),
    "key_redo": ("Повторить", "⌨️ Клавиатура", act_key_redo, False),
    "key_save": ("Сохранить", "⌨️ Клавиатура", act_key_save, False),
    "clipboard_clear": ("Очистить буфер", "⌨️ Клавиатура", act_clipboard_clear, False),
    # Мышь
    "mouse_click": ("Клик", "🖱 Мышь", act_mouse_click, False),
    "mouse_rclick": ("Правый клик", "🖱 Мышь", act_mouse_rclick, False),
    "mouse_dblclick": ("Двойной клик", "🖱 Мышь", act_mouse_dblclick, False),
    "mouse_middle": ("Средний клик", "🖱 Мышь", act_mouse_middle, False),
    "scroll_up": ("Прокрутка вверх", "🖱 Мышь", act_scroll_up, False),
    "scroll_down": ("Прокрутка вниз", "🖱 Мышь", act_scroll_down, False),
    "mouse_center": ("Мышь в центр", "🖱 Мышь", act_mouse_to_center, False),
    # Интернет-поиски специфичные
    "search_maps": ("Карта: <запрос>", "🔎 Поиск", act_google_maps, True),
    "search_youtube": ("Ютуб: <запрос>", "🔎 Поиск", act_youtube, True),
    "search_wiki": ("Вики: <запрос>", "🔎 Поиск", act_wiki, True),
}
