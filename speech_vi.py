from __future__ import annotations
import threading, time
import sounddevice as sd
import speech_recognition as sr

class VietnameseSpeechListener:
    def __init__(self, on_text, on_status, language="vi-VN", seconds=4.0):
        self.on_text = on_text
        self.on_status = on_status
        self.language = "vi-VN"  # cố định chỉ nhận dạng tiếng Việt Việt Nam
        self.seconds = float(seconds)
        self.sample_rate = 16000
        self.running = False
        self.thread = None
        self.recognizer = sr.Recognizer()

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _loop(self):
        self.on_status("🎤 Đang nghe tiếng Việt")
        while self.running:
            try:
                frames = int(self.sample_rate * self.seconds)
                audio = sd.rec(frames, samplerate=self.sample_rate, channels=1, dtype="int16")
                sd.wait()
                if not self.running:
                    break

                data = sr.AudioData(audio.reshape(-1).tobytes(), self.sample_rate, 2)
                try:
                    text = self.recognizer.recognize_google(data, language="vi-VN")
                    text = (text or "").strip()
                    if text:
                        self.on_text(text)
                except sr.UnknownValueError:
                    pass
                except sr.RequestError:
                    self.on_status("🎤 Mic bật - nhận dạng giọng nói cần Internet")
                    time.sleep(1)
            except Exception as e:
                self.on_status(f"🎤 Lỗi mic: {e}")
                time.sleep(1)

        self.on_status("🎤 Mic đã tắt")
