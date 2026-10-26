# -*- coding: utf-8 -*-
"""
JARVIS v5 · НАСТРОЙКИ
Единый файл data/settings.json: имя ассистента, имя владельца, движок ИИ, голоса, wake word,
громкость речи, скорость распознавания и т.д.
"""
import os
import json
import threading

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

DEFAULTS = {
    # личность
    "assistant_name": "Джарвис",
    "owner_name": "босс",
    "language": "ru",
    "style": "деловой с юмором",
    # ИИ-движок (все бесплатные)
    "engine": "rules",
    "ollama_host": "http://localhost:11434",
    "ollama_model": "llama3.2",
    "lmstudio_host": "http://localhost:1234/v1",
    "lmstudio_model": "",
    "groq_key": "",
    "groq_model": "llama-3.3-70b-versatile",
    "gemini_key": "",
    "gemini_model": "gemini-1.5-flash",
    "openrouter_key": "",
    "openrouter_model": "meta-llama/llama-3.3-70b-instruct:free",
    "custom_base_url": "",
    "custom_key": "",
    "custom_model": "",
    # голос
    "tts_backend": "pyttsx3",       # pyttsx3|windows_sapi|edge|espeak
    "voice_gender": "any",          # male|female|any
    "voice_index": -1,
    "speech_rate": 200,
    "speech_volume": 1.0,
    "edge_voice": "ru-RU-DmitryNeural",
    # распознавание
    "stt_backend": "whisper_local",  # whisper_local|faster_whisper|vosk|sphinx
    "wake_word": "джарвис",
    "wake_enabled": True,
    "listen_timeout": 6,
    "energy_threshold": 500,
    # поведение
    "confirm_dangerous": True,
    "auto_learn": True,
    "ui_theme": "dark",
}

DANGEROUS_KEYS = {"shutdown_pc", "restart_pc", "empty_recycle", "file_delete", "kill_process", "signout"}


class Settings:
    def __init__(self, path=SETTINGS_FILE):
        self.path = path
        self.lock = threading.Lock()
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                for k, v in stored.items():
                    self.data[k] = v
            except Exception as e:
                print(f"⚠️ settings.json повреждён: {e}")

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def get(self, key, default=None):
        return self.data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key, value):
        with self.lock:
            self.data[key] = value
            self.save()

    def update(self, mapping):
        with self.lock:
            self.data.update(mapping)
            self.save()
