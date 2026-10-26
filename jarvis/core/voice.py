# -*- coding: utf-8 -*-
"""
JARVIS v5 · ГОЛОС (TTS) И РАСПОЗНАВАНИЕ РЕЧИ (STT) — полностью бесплатно.

TTS (текст → речь):
  • pyttsx3  — офлайн, голоса системы Windows (выбор мужской/женский, скорость, громкость)
  • edge-tts — бесплатные нейросетевые голоса Microsoft (ru-RU-DmitryNeural / SvetlanaNeural...)
  • espeak   — резерв на Linux
STT (речь → текст):
  • faster-whisper / openai-whisper — локальная модель Whisper (бесплатно, офлайн, русский)
  • vosk — лёгкая офлайн-модель
  • speech_recognition + Google — облачный бесплатный вариант
Если микрофона/библиотек нет — приложение работает в текстовом режиме (чат с ИИ).
"""
import os
import re
import queue
import threading
import subprocess
import tempfile
import wave

# ─────────── TTS ───────────
class VoiceBox:
    """Озвучка. Потокобезопасно, очередью, чтобы команды не ждали окончания речи."""

    def __init__(self, settings):
        self.settings = settings
        self.backend = None
        self.engine = None
        self.voices = []
        self._queue = queue.Queue()
        self._thread = None
        self._stop_flag = threading.Event()
        self.init_backend()

    # ── инициализация ──
    def init_backend(self):
        pref = self.settings.get("tts_backend")
        backends = [pref] if pref else []
        backends += ["pyttsx3", "edge", "espeak"]
        for b in backends:
            try:
                if b == "pyttsx3" and self._init_pyttsx3():
                    self.backend = "pyttsx3"
                    return True
                if b == "edge" and self._init_edge():
                    self.backend = "edge"
                    return True
                if b == "windows_sapi" and self._init_pyttsx3():
                    self.backend = "pyttsx3"
                    return True
                if b == "espeak" and self._init_espeak():
                    self.backend = "espeak"
                    return True
            except Exception:
                continue
        self.backend = None
        return False

    def _init_pyttsx3(self):
        import pyttsx3
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", int(self.settings.get("speech_rate", 200)))
        self.engine.setProperty("volume", float(self.settings.get("speech_volume", 1.0)))
        self.voices = self.engine.getProperty("voices") or []
        self._pick_voice()
        return True

    def _pick_voice(self):
        gender = self.settings.get("voice_gender", "any")
        idx = int(self.settings.get("voice_index", -1))
        if not self.engine or not self.voices:
            return
        if 0 <= idx < len(self.voices):
            self.engine.setProperty("voice", self.voices[idx].id)
            return
        if gender in ("male", "female"):
            for v in self.voices:
                name = (v.name or "").lower()
                male_hints = ["male", "david", "mark", "ivan", "мужск", "дмитрий"]
                female_hints = ["female", "zira", "susan", "milena", "svetlana", "женск", "катерина", "irina"]
                if gender == "male" and any(h in name for h in male_hints):
                    self.engine.setProperty("voice", v.id)
                    return
                if gender == "female" and any(h in name for h in female_hints):
                    self.engine.setProperty("voice", v.id)
                    return

    def _init_edge(self):
        import edge_tts  # noqa
        return True

    def _init_espeak(self):
        return shutil_which("espeak") or shutil_which("espeak-ng")

    # ── список голосов для интерфейса ──
    def list_voices(self):
        out = []
        if self.backend == "pyttsx3" and self.voices:
            for i, v in enumerate(self.voices):
                out.append({"index": i, "name": v.name, "id": v.id})
        elif self.backend == "edge":
            out = [{"index": -1, "name": n, "id": n} for n in (
                "ru-RU-DmitryNeural (мужской)", "ru-RU-SvetlanaNeural (женский)",
                "ru-RU-PavelMultilingualNeural (мужской мульт.)", "en-US-GuyNeural (англ. мужской)",
                "en-US-JennyNeural (англ. женский)")]
        return out

    # ── говорим ──
    def speak(self, text):
        if not text:
            return
        text = str(text)[:600]
        if self.backend is None:
            print(f"🗣 {text}")
            return
        self._queue.put(text)
        if self._thread is None or not self._thread.is_alive():
            self._stop_flag.clear()
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_flag.set()
        try:
            while not self._queue.empty():
                self._queue.get_nowait()
        except queue.Empty:
            pass

    def _worker(self):
        while not self._stop_flag.is_set():
            try:
                text = self._queue.get(timeout=0.4)
            except queue.Empty:
                break
            try:
                if self.backend == "pyttsx3":
                    self.engine.say(text)
                    self.engine.runAndWait()
                elif self.backend == "edge":
                    self._edge_say(text)
                elif self.backend == "espeak":
                    exe = shutil_which("espeak-ng") or shutil_which("espeak")
                    subprocess.run([exe, "-v", "ru", "-s", str(int(self.settings.get("speech_rate", 200))), text])
            except Exception as e:
                print(f"⚠️ Ошибка озвучки: {e}")

    EDGE_VOICES = {
        "ru-RU-DmitryNeural": "ru-RU-DmitryNeural",
        "ru-RU-SvetlanaNeural": "ru-RU-SvetlanaNeural",
    }

    def _edge_say(self, text):
        import asyncio
        import edge_tts
        voice = self.settings.get("edge_voice", "ru-RU-DmitryNeural").split(" ")[0]
        mp3 = os.path.join(tempfile.gettempdir(), "jarvis_tts.mp3")

        async def gen():
            tts = edge_tts.Communicate(text, voice)
            await tts.save(mp3)

        asyncio.run(gen())
        # проигрываем без лишних зависимостей: Windows — через PowerShell/FFplay
        player = shutil_which("ffplay")
        if player:
            subprocess.run([player, "-nodisp", "-autoexit", "-loglevel", "quiet", mp3],
                           timeout=60, stdout=subprocess.DEVNULL)
        elif os.name == "nt":
            ps = f'(New-Object Media.SoundPlayer "{mp3}").PlaySync()'
            subprocess.run(["powershell", "-Command", ps], timeout=60)


def shutil_which(name):
    import shutil
    return shutil.which(name)


# ─────────── STT ───────────
class Ear:
    """Распознавание речи. Локальные модели бесплатны; при отсутствии — текстовый ввод."""

    def __init__(self, settings):
        self.settings = settings
        self.backend = None
        self.model = None
        self.rec = None
        self.mic = None
        self._init()

    def _init(self):
        pref = self.settings.get("stt_backend", "whisper_local")
        order = [pref, "faster_whisper", "whisper_local", "vosk", "sphinx", "google"]
        for b in order:
            try:
                if b == "faster_whisper" and self._init_faster_whisper():
                    self.backend = "faster_whisper"
                    return
                if b == "whisper_local" and self._init_whisper():
                    self.backend = "whisper_local"
                    return
                if b == "vosk" and self._init_vosk():
                    self.backend = "vosk"
                    return
                if b == "sphinx" and self._init_sphinx():
                    self.backend = "sphinx"
                    return
                if b == "google" and self._init_google():
                    self.backend = "google"
                    return
            except Exception:
                continue
        self.backend = None

    def _init_faster_whisper(self):
        from faster_whisper import WhisperModel
        self.model = WhisperModel("small", device="cpu", compute_type="int8")
        import sounddevice  # noqa
        import numpy as np  # noqa
        self._np = np
        self._sd = sounddevice
        return True

    def _init_whisper(self):
        import whisper  # openai-whisper
        self.model = whisper.load_model("base")
        import sounddevice  # noqa
        import numpy as np  # noqa
        self._np = np
        self._sd = sounddevice
        return True

    def _init_vosk(self):
        from vosk import Model, KaldiRecognizer
        import sounddevice  # noqa
        import numpy as np  # noqa
        model_dir = os.path.join(os.path.expanduser("~"), ".jarvis", "vosk-model-small-ru-0.22")
        if not os.path.isdir(model_dir):
            return False
        self.vmodel = Model(model_dir)
        self.KaldiRecognizer = KaldiRecognizer
        self._np = np
        self._sd = sounddevice
        return True

    def _init_sphinx(self):
        import speech_recognition as sr
        self.rec = sr.Recognizer()
        self.mic = sr.Microphone()
        self.use_sphinx = True
        return True

    def _init_google(self):
        import speech_recognition as sr
        self.rec = sr.Recognizer()
        self.mic = sr.Microphone()
        self.use_sphinx = False
        return True

    def available(self):
        return self.backend is not None

    def listen_once(self, timeout=None):
        """Слушает одну фразу, возвращает текст или None."""
        timeout = timeout or int(self.settings.get("listen_timeout", 6))
        try:
            if self.backend in ("faster_whisper", "whisper_local"):
                return self._listen_whisper(timeout)
            if self.backend == "vosk":
                return self._listen_vosk(timeout)
            if self.backend in ("sphinx", "google"):
                return self._listen_sr()
        except Exception as e:
            print(f"⚠️ Слушание: {e}")
        return None

    def _record(self, seconds):
        fs = 16000
        data = self._sd.recording = self._sd.rec(seconds, samplerate=fs, channels=1, dtype="int16")
        self._sd.rec.start()
        self._sd.wait(seconds)
        audio = self._sd.rec.stop()
        return self._np.array(audio).flatten()

    def _listen_whisper(self, timeout):
        # ждём начало речи максимум timeout сек, потом пишем 5 секунд
        import numpy as np
        fs = 16000
        chunk = 0.5
        started = False
        frames = []
        waited = 0.0
        while waited < timeout:
            rec = self._sd.rec(int(chunk * fs), samplerate=fs, channels=1, dtype="int16")
            self._sd.rec.start()
            self._sd.wait(chunk)
            buf = self._np.array(rec.stop()).flatten()
            energy = abs(buf).mean()
            if energy > int(self.settings.get("energy_threshold", 500)):
                started = True
            if started:
                frames.append(buf)
                waited = 0  # речь идёт — не считаем таймаут
                if sum(len(f) for f in frames) > fs * 12:
                    break
            else:
                waited += chunk
        if not frames:
            return None
        audio = self._np.concatenate(frames)
        if self.backend == "faster_whisper":
            segs, _ = self.model.transcribe(audio, language="ru", vad_filter=True)
            return " ".join(s.text for s in segs).strip() or None
        res = self.model.transcribe(audio, language="ru")
        return res.get("text", "").strip() or None

    def _listen_vosk(self, timeout):
        import json as _json
        fs = 16000
        k = self.KaldiRecognizer(self.vmodel, fs)
        with self._sd.InputStream(samplerate=fs, channels=1, dtype="int16") as stream:
            end = time.time() + timeout
            while time.time() < end:
                data = stream.read(int(0.25 * fs), exception_on_overflow=False)[0]
                if k.AcceptWaveform(data):
                    res = _json.loads(k.Result()).get("text", "")
                    if res:
                        return res
            res = _json.loads(k.FinalResult()).get("text", "")
            return res or None

    def _listen_sr(self):
        import speech_recognition as sr
        with self.mic as source:
            self.rec.adjust_for_ambient_noise(source, duration=0.4)
            audio = self.rec.listen(source, timeout=int(self.settings.get("listen_timeout", 6)),
                                     phrase_time_limit=8)
        try:
            if getattr(self, "use_sphinx", False):
                return self.rec.recognize_sphinx(audio, language="ru-RU").replace(" ", "")
            return self.rec.recognize_google(audio, language="ru-RU")
        except sr.UnknownValueError:
            return None
        except Exception as e:
            print(f"⚠️ Распознавание: {e}")
            return None


import time  # noqa: E402  (для _listen_vosk)
