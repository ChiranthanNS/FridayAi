"""
FRIDAY AI — Voice System
━━━━━━━━━━━━━━━━━━━━━━━━
Wake word detection, speech recognition, and neural TTS with emotions.
FRIDAY listens always, speaks beautifully.
"""

import os
import io
import asyncio
import threading
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict
from datetime import datetime

import speech_recognition as sr
from loguru import logger

# Edge TTS for neural voice
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logger.warning("edge-tts not available, falling back to pyttsx3")

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


class VoiceSystem:
    """
    FRIDAY's complete voice I/O system.
    - Microphone input with speech recognition
    - Neural TTS output with emotional styling
    - Always-on listening mode
    """

    def __init__(self, emotion_engine=None):
        self.emotion_engine = emotion_engine
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.is_listening = False
        self.is_speaking = False
        self._speech_callback: Optional[Callable] = None
        self._listening_thread: Optional[threading.Thread] = None

        # TTS settings
        self.tts_voice = os.getenv("TTS_VOICE", "en-US-AriaNeural")
        self.tts_rate = os.getenv("TTS_RATE", "+15%")
        self.tts_pitch = os.getenv("TTS_PITCH", "+5Hz")

        # Fallback pyttsx3
        if PYTTSX3_AVAILABLE:
            self._pyttsx3_engine = pyttsx3.init()
            voices = self._pyttsx3_engine.getProperty("voices")
            # Prefer female voice
            for voice in voices:
                if "zira" in voice.id.lower() or "aria" in voice.id.lower() or "female" in voice.name.lower():
                    self._pyttsx3_engine.setProperty("voice", voice.id)
                    break
            self._pyttsx3_engine.setProperty("rate", 185)
            self._pyttsx3_engine.setProperty("volume", 0.95)

        # Adjust for ambient noise
        self._calibrate_microphone()
        logger.info("Voice system initialized. FRIDAY is listening.")

    def _calibrate_microphone(self):
        """Calibrate microphone for ambient noise."""
        try:
            mic_list = sr.Microphone.list_microphone_names()
            if mic_list:
                self.microphone = sr.Microphone()
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    self.recognizer.energy_threshold = max(
                        self.recognizer.energy_threshold, 300
                    )
                logger.info(f"Microphone calibrated. Energy threshold: {self.recognizer.energy_threshold:.0f}")
            else:
                logger.warning("No microphone detected.")
        except Exception as e:
            logger.error(f"Microphone calibration failed: {e}")

    async def speak(self, text: str, emotion: str = "neutral", force_edge: bool = True) -> bool:
        """
        Speak text using neural TTS with emotional styling.
        Returns True on success.
        """
        if not text or not text.strip():
            return False

        self.is_speaking = True
        logger.info(f"Speaking [{emotion}]: {text[:100]}...")

        try:
            if EDGE_TTS_AVAILABLE and force_edge:
                await self._speak_edge_tts(text, emotion)
            elif PYTTSX3_AVAILABLE:
                self._speak_pyttsx3(text)
            else:
                logger.warning(f"No TTS available. Would say: {text}")
        except Exception as e:
            logger.error(f"TTS error: {e}")
            if PYTTSX3_AVAILABLE:
                self._speak_pyttsx3(text)
        finally:
            self.is_speaking = False

        return True

    async def _speak_edge_tts(self, text: str, emotion: str = "neutral"):
        """Use Microsoft Edge TTS with SSML emotional styling."""
        voice = self.tts_voice
        rate = self.tts_rate
        pitch = self.tts_pitch

        # Adjust based on emotion
        if emotion in ("excited", "happy"):
            rate = "+25%"
            pitch = "+10Hz"
        elif emotion in ("concerned", "empathetic"):
            rate = "+0%"
            pitch = "-5Hz"
        elif emotion == "playful":
            rate = "+20%"
            pitch = "+8Hz"
        elif emotion == "focused":
            rate = "+15%"

        # Create temp audio file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate,
                pitch=pitch
            )
            await communicate.save(tmp_path)

            # Play audio (Windows)
            if os.name == "nt":
                subprocess.run(
                    ["powershell", "-c", f"(New-Object Media.SoundPlayer '{tmp_path}').PlaySync()"],
                    capture_output=True
                )
                # Use Windows Media Player for mp3
                os.startfile(tmp_path)
                await asyncio.sleep(len(text) * 0.065)  # Estimate playback time
            else:
                subprocess.run(["mpg123", "-q", tmp_path])
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _speak_pyttsx3(self, text: str):
        """Fallback TTS using pyttsx3."""
        if PYTTSX3_AVAILABLE:
            self._pyttsx3_engine.say(text)
            self._pyttsx3_engine.runAndWait()

    def listen_once(self, timeout: int = 8, phrase_limit: int = 30) -> Optional[str]:
        """Listen for one voice command and return transcription."""
        if not self.microphone:
            return None

        try:
            with self.microphone as source:
                logger.debug("Listening for command...")
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_limit
                )

            text = self.recognizer.recognize_google(audio, language="en-IN")
            logger.info(f"Heard: {text}")
            return text

        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition error: {e}")
            return None

    def start_continuous_listening(self, callback: Callable[[str], None]):
        """Start background listener that calls callback with transcribed text."""
        self._speech_callback = callback
        self.is_listening = True
        self._listening_thread = threading.Thread(
            target=self._listen_loop, daemon=True
        )
        self._listening_thread.start()
        logger.info("Continuous listening started.")

    def _listen_loop(self):
        """Background listening loop."""
        if not self.microphone:
            logger.error("No microphone available for continuous listening.")
            return

        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            while self.is_listening:
                try:
                    if self.is_speaking:
                        import time; time.sleep(0.5)
                        continue

                    audio = self.recognizer.listen(
                        source, timeout=3, phrase_time_limit=20
                    )
                    text = self.recognizer.recognize_google(audio, language="en-IN")

                    if text and self._speech_callback:
                        logger.info(f"User said: {text}")
                        self._speech_callback(text)

                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except Exception as e:
                    logger.error(f"Listening error: {e}")
                    import time; time.sleep(1)

    def stop_listening(self):
        """Stop the background listener."""
        self.is_listening = False
        logger.info("Listening stopped.")

    def wake_word_detected(self, text: str) -> bool:
        """Check if the wake word 'Friday' is in the text."""
        wake_words = ["friday", "hey friday", "okay friday"]
        text_lower = text.lower().strip()
        return any(w in text_lower for w in wake_words)

    def extract_command(self, text: str) -> str:
        """Remove wake word from command text."""
        wake_words = ["hey friday", "okay friday", "friday"]
        text_lower = text.lower()
        for w in wake_words:
            if text_lower.startswith(w):
                return text[len(w):].strip(" ,.")
        return text
