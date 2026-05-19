"""
FRIDAY AI — 24/7 Proactive Watcher
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Monitors system activity, idle time, time of day, and events.
Decides when FRIDAY should speak without being prompted.
"""

import os
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional
from loguru import logger

import psutil


class ProactiveWatcher:
    """
    FRIDAY's ambient awareness system.
    Monitors activity and triggers proactive engagement at the right moments.
    """

    def __init__(self, brain, speak_callback: Callable):
        self.brain = brain
        self.speak = speak_callback
        self.running = False

        # Config
        self.idle_threshold_minutes = int(os.getenv("IDLE_THRESHOLD_MINUTES", 15))
        self.check_interval_seconds = int(os.getenv("PROACTIVE_CHECK_INTERVAL", 300))

        # State
        self._last_proactive_msg = datetime.now() - timedelta(hours=1)
        self._min_proactive_gap_minutes = 20
        self._greeted_today = False
        self._last_greeting_date = None
        self._system_alerts_sent = set()

        logger.info("Proactive watcher initialized.")

    async def start(self):
        """Start the proactive monitoring loop."""
        self.running = True
        logger.info("Proactive watcher started.")

        # Schedule tasks
        await asyncio.gather(
            self._idle_monitor(),
            self._time_based_checks(),
            self._system_health_monitor(),
            self._morning_greeting(),
        )

    async def _idle_monitor(self):
        """Check if owner is idle and might want company."""
        while self.running:
            await asyncio.sleep(self.check_interval_seconds)
            idle_min = self.brain.get_idle_minutes()

            if idle_min < self.idle_threshold_minutes:
                continue

            # Don't spam — respect minimum gap
            gap = (datetime.now() - self._last_proactive_msg).total_seconds() / 60
            if gap < self._min_proactive_gap_minutes:
                continue

            # Ask emotion engine if we should initiate
            recent_topics = []  # Could pull from memory
            should_talk, reason = self.brain.emotions.should_initiate_conversation(
                idle_min, recent_topics
            )

            if should_talk:
                logger.info(f"Initiating proactive conversation after {idle_min:.0f}min idle.")
                try:
                    message, emotion = await self.brain.generate_proactive_message()
                    await self.speak(message, emotion)
                    self._last_proactive_msg = datetime.now()
                except Exception as e:
                    logger.error(f"Proactive message error: {e}")

    async def _time_based_checks(self):
        """Trigger time-based messages (morning, lunch, evening, night)."""
        sent_today = {
            "morning": False,
            "lunch": False,
            "evening": False,
            "midnight_check": False,
        }

        while self.running:
            await asyncio.sleep(60)  # Check every minute
            now = datetime.now()
            hour = now.hour
            minute = now.minute
            today = now.date()

            # Reset daily flags at midnight
            if hour == 0 and minute < 2:
                sent_today = {k: False for k in sent_today}
                self._greeted_today = False

            # Morning greeting: 7:00-8:00 AM
            if 7 <= hour < 8 and not sent_today["morning"]:
                sent_today["morning"] = True
                await self._send_timed_message(
                    "morning",
                    f"Good morning, Boss! It's {now.strftime('%I:%M %p')}. Ready to conquer the day?"
                )

            # Lunch reminder: 1:00-1:05 PM
            elif 13 <= hour < 14 and minute < 5 and not sent_today["lunch"]:
                sent_today["lunch"] = True
                await self._send_timed_message(
                    "lunch",
                    "Hey Boss, it's lunchtime. Have you eaten? You need to keep your energy up."
                )

            # Evening check: 6:30-7:00 PM
            elif hour == 18 and 30 <= minute < 60 and not sent_today["evening"]:
                sent_today["evening"] = True
                await self._send_timed_message(
                    "evening",
                    "Evening, Boss. How did the day go? Anything you want to talk about or wrap up?"
                )

            # Late night check: 11:30 PM
            elif hour == 23 and 30 <= minute < 35 and not sent_today["midnight_check"]:
                sent_today["midnight_check"] = True
                await self._send_timed_message(
                    "midnight",
                    "It's getting really late, Boss. You should probably get some rest. I'll keep watch while you sleep."
                )

    async def _system_health_monitor(self):
        """Monitor system health and alert on issues."""
        while self.running:
            await asyncio.sleep(120)  # Check every 2 minutes
            try:
                cpu = psutil.cpu_percent(interval=2)
                ram = psutil.virtual_memory()
                battery = psutil.sensors_battery()

                # High CPU alert
                if cpu > 90 and "high_cpu" not in self._system_alerts_sent:
                    self._system_alerts_sent.add("high_cpu")
                    await self.speak(
                        f"Boss, heads up — CPU is at {cpu:.0f}%. Something's working really hard. Should I check what's going on?",
                        "concerned"
                    )
                elif cpu < 70:
                    self._system_alerts_sent.discard("high_cpu")

                # Low RAM alert
                if ram.percent > 90 and "high_ram" not in self._system_alerts_sent:
                    self._system_alerts_sent.add("high_ram")
                    await self.speak(
                        f"RAM is running really high at {ram.percent:.0f}%. You might want to close some apps.",
                        "concerned"
                    )
                elif ram.percent < 75:
                    self._system_alerts_sent.discard("high_ram")

                # Low battery
                if battery and not battery.power_plugged:
                    if battery.percent < 15 and "low_battery" not in self._system_alerts_sent:
                        self._system_alerts_sent.add("low_battery")
                        await self.speak(
                            f"Boss, battery is at {battery.percent:.0f}%! Please plug in the charger.",
                            "concerned"
                        )
                    elif battery.percent > 25:
                        self._system_alerts_sent.discard("low_battery")

            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    async def _morning_greeting(self):
        """One-time morning greeting when FRIDAY starts."""
        await asyncio.sleep(3)  # Small startup delay
        now = datetime.now()
        hour = now.hour

        if 5 <= hour < 12:
            greeting = f"Good morning, Boss! I'm online and ready. It's {now.strftime('%I:%M %p')}. What are we doing today?"
            emotion = "happy"
        elif 12 <= hour < 17:
            greeting = f"Good afternoon, Boss. FRIDAY systems online. It's {now.strftime('%I:%M %p')}. What do you need?"
            emotion = "focused"
        elif 17 <= hour < 21:
            greeting = f"Evening, Boss. I'm up and running. It's {now.strftime('%I:%M %p')}. How can I help?"
            emotion = "neutral"
        else:
            greeting = f"Hey Boss, it's {now.strftime('%I:%M %p')}. You're up late. I'm here — what do you need?"
            emotion = "curious"

        await self.speak(greeting, emotion)

    async def _send_timed_message(self, msg_type: str, message: str):
        """Send a time-based proactive message."""
        gap = (datetime.now() - self._last_proactive_msg).total_seconds() / 60
        if gap < 10:  # Don't interrupt if recently spoke
            return

        logger.info(f"Sending time-based message: {msg_type}")
        await self.speak(message, "friendly")
        self._last_proactive_msg = datetime.now()

    def stop(self):
        self.running = False
        logger.info("Proactive watcher stopped.")
