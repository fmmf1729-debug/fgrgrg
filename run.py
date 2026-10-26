# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════
 JARVIS v5 · ПОЛНОЦЕННОЕ НАСТОЛЬНОЕ ИИ-ПРИЛОЖЕНИЕ (без сайтов)
 • ~120 системных действий × 15–25 синонимов = тысячи понятных фраз
 • Бесплатные ИИ-движки: Ollama / LM Studio / Groq / Gemini / OpenRouter
   + встроенный офлайн-мозг (работает всегда и без ключей)
 • Обучаемая память: запоминает факты, учит синонимы, исправления,
   сценарии и команды пользователя — голосом и письменно
 • Голос: выбор движка, пола, скорости; распознавание Whisper/Vosk/офлайн
 • Интерфейс: тёмная тема, вкладки Диалог/Команды/Мои команды/Память/Настройки
 Запуск:  python run.py            (интерфейс)
          python run.py --cli      (консольный режим, удобно для тестов)
═══════════════════════════════════════════════════════════════════
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "jarvis"))


def main():
    if "--cli" in sys.argv:
        from core.assistant import Assistant
        try:
            from core.voice import VoiceBox, Ear
            settings_path = os.path.join(BASE, "jarvis", "data", "settings.json")
            from core.settings import Settings
            s = Settings()
            voice = VoiceBox(s)
            ear = Ear(s)
        except Exception as e:
            print(f"(голос недоступен: {e})")
            voice = ear = None
        a = Assistant(voice=voice, ear=ear)
        a.on_event = lambda ev: None
        print("JARVIS CLI. Введите 'exit' для выхода.")
        while True:
            try:
                line = input("Вы > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if line.lower() in ("exit", "выход"):
                break
            reply = a.process(line)
            print(f"{a.settings.get('assistant_name')} > {reply}")
        return

    # графический интерфейс
    from ui.app import JarvisApp
    JarvisApp().run()


if __name__ == "__main__":
    main()
