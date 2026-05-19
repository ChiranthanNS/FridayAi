"""
FRIDAY AI — Main Orchestrator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The entry point. Starts all systems, runs 24/7.
Voice → Brain → Agent → Voice, with proactive monitoring.
"""

import os
import asyncio
import signal
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows so the banner prints correctly
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load environment
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
import uvicorn

from core.brain import FridayBrain
from core.voice import VoiceSystem
from core.watcher import ProactiveWatcher
from core.server import create_app, broadcast_friday_speech


# ── Logging setup ───────────────────────────────────────────────────────────
log_path = os.getenv("LOG_PATH", "./logs/friday.log")
Path(log_path).parent.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(sys.stderr, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
logger.add(log_path, rotation="10 MB", retention="30 days", level="DEBUG")


class FRIDAY:
    """
    The complete FRIDAY AI system.
    Orchestrates voice, brain, agent, watcher, and dashboard.
    """

    def __init__(self):
        self._running = False
        self.brain: FridayBrain = None
        self.voice: VoiceSystem = None
        self.watcher: ProactiveWatcher = None

        self._print_boot_banner()

    def _print_boot_banner(self):
        banner = r"""
+--------------------------------------------------------------+
|                                                              |
|   ______  ____   _____  _____      _     __  __             |
|  |  ____||  _ \ |_   _||  __ \   / \   |  \/  |            |
|  | |__   | |_) |  | |  | |  | | / _ \  | \  / |            |
|  |  __|  |  _ /   | |  | |  | |/ /_\ \ | |\/| |            |
|  | |     | | \ \  | |  | |__| / _____ \| |  | |            |
|  |_|     |_|  \_\ |_|  |_____/_/     \_\_|  |_|            |
|                                                              |
|     Female Replacement Intelligent Digital Assistant        |
|                  v1.0.0  |  Always Online                   |
+--------------------------------------------------------------+
        """
        print(banner)
        logger.info(f"FRIDAY starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    async def initialize(self):
        """Initialize all subsystems."""
        logger.info("Initializing FRIDAY subsystems...")

        # 1. Brain (LLM + Memory + Emotions)
        logger.info("[*] Starting neural brain...")
        self.brain = FridayBrain()
        self.brain.voice = None  # Will be set after voice init

        # 2. Voice system
        logger.info("[*] Starting voice system...")
        try:
            self.voice = VoiceSystem(emotion_engine=self.brain.emotions)
            self.brain.voice = self.voice
        except Exception as e:
            logger.warning(f"Voice system failed (running in text-only mode): {e}")
            self.voice = None

        # 3. Proactive watcher
        logger.info("[*] Starting proactive watcher...")
        self.watcher = ProactiveWatcher(
            brain=self.brain,
            speak_callback=self._speak_and_broadcast
        )

        logger.info("All systems initialized. FRIDAY is online.")

    async def _speak_and_broadcast(self, text: str, emotion: str = "neutral"):
        """Speak and simultaneously broadcast to dashboard."""
        try:
            # Broadcast to web dashboard
            await broadcast_friday_speech(text, emotion)

            # Speak aloud
            if self.voice:
                await self.voice.speak(text, emotion)
        except Exception as e:
            logger.error(f"Speak/broadcast error: {e}")

    def _on_voice_input(self, text: str):
        """Called when microphone captures speech."""
        if not text or not text.strip():
            return

        # Check for wake word
        if self.voice and self.voice.wake_word_detected(text):
            command = self.voice.extract_command(text)
            if command:
                logger.info(f"Wake word detected. Command: {command}")
                asyncio.create_task(self._handle_voice_command(command))
        elif self.brain.get_idle_minutes() < 2:
            # If recently interacted, treat all speech as command
            asyncio.create_task(self._handle_voice_command(text))

    async def _handle_voice_command(self, text: str):
        """Process a voice command through the brain."""
        try:
            response, emotion = await self.brain.process_input(text)
            await self._speak_and_broadcast(response, emotion)
        except Exception as e:
            logger.error(f"Voice command error: {e}")
            await self._speak_and_broadcast("Sorry Boss, something went wrong.", "concerned")

    async def run(self):
        """Main run loop."""
        self._running = True
        await self.initialize()

        # Start voice listener
        if self.voice:
            self.voice.start_continuous_listening(self._on_voice_input)

        # Start dashboard server
        port = int(os.getenv("DASHBOARD_PORT", 8765))
        app = create_app(self.brain)

        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=port,
            log_level="warning",
        )
        server = uvicorn.Server(config)

        logger.info(f"Dashboard available at http://localhost:{port}")

        # Run everything concurrently
        await asyncio.gather(
            server.serve(),
            self.watcher.start(),
            self._memory_consolidation_loop(),
        )

    async def _memory_consolidation_loop(self):
        """Periodically consolidate memories."""
        while self._running:
            await asyncio.sleep(3600)  # Every hour
            try:
                await self.brain.memory.consolidate_memories()
            except Exception as e:
                logger.error(f"Memory consolidation error: {e}")

    async def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self.voice:
            self.voice.stop_listening()
        if self.watcher:
            self.watcher.stop()

        farewell = "Shutting down, Boss. I'll be here when you need me."
        if self.voice:
            await self.voice.speak(farewell, "empathetic")
        logger.info("FRIDAY shutdown complete.")


def main():
    friday = FRIDAY()

    try:
        asyncio.run(friday.run())
    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")
        asyncio.run(friday.shutdown())


if __name__ == "__main__":
    main()
