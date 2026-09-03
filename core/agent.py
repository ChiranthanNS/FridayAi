"""
FRIDAY AI — System Agent (Full Automation Brain)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Complete system control: files, apps, browser, WhatsApp, email, and more.
FRIDAY can do literally anything on your computer.
"""

import os
import sys
import json
import asyncio
import subprocess
import shutil
import platform
import webbrowser
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

import psutil
import pyautogui
import keyboard
import requests

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5


class TaskResult:
    """Result of an agent task execution."""
    def __init__(self, success: bool, output: str, data: Any = None, error: str = ""):
        self.success = success
        self.output = output
        self.data = data
        self.error = error

    def __str__(self):
        return self.output


class SystemAgent:
    """
    FRIDAY's automation backbone.
    Handles all system-level tasks with full Windows control.
    """

    # Action map for routing parsed actions to handlers
    ACTION_MAP = {
        "create_file": "create_file",
        "read_file": "read_file",
        "delete_file": "delete_file",
        "list_directory": "list_directory",
        "search_files": "search_files",
        "run_command": "run_command",
        "open_application": "open_application",
        "close_application": "close_application",
        "get_system_info": "get_system_info",
        "open_url": "open_url",
        "web_search": "web_search",
        "send_whatsapp": "send_whatsapp_message",
        "send_email": "send_email",
        "take_screenshot": "take_screenshot",
        "type_text": "type_text",
        "click_at": "click_at",
        "press_key": "press_key",
        "set_volume": "set_volume",
        "get_weather": "get_weather",
        "get_time_date": "get_time_date",
        "set_reminder": "set_reminder",
        "get_clipboard": "get_clipboard",
        "set_clipboard": "set_clipboard",
        "lock_system": "lock_system",
        "sleep_system": "sleep_system",
        "shutdown_system": "shutdown_system",
    }

    def __init__(self):
        self.os_name = platform.system()
        self.username = os.getenv("USERNAME") or os.getenv("USER", "user")
        self.home = Path.home()
        self._whatsapp_driver = None
        logger.info(f"System agent online. OS: {self.os_name}, User: {self.username}")

    # ── FILE SYSTEM ────────────────────────────────────────────────────────

    async def create_file(self, path: str, content: str = "") -> TaskResult:
        """Create a file with optional content."""
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return TaskResult(True, f"Created file: {path}", data=path)
        except Exception as e:
            return TaskResult(False, f"Failed to create file: {e}", error=str(e))

    async def read_file(self, path: str) -> TaskResult:
        """Read a file's contents."""
        try:
            content = Path(path).read_text(encoding="utf-8")
            return TaskResult(True, content, data=content)
        except Exception as e:
            return TaskResult(False, f"Cannot read {path}: {e}", error=str(e))

    async def delete_file(self, path: str) -> TaskResult:
        """Delete a file or directory."""
        try:
            p = Path(path)
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(path)
            return TaskResult(True, f"Deleted: {path}")
        except Exception as e:
            return TaskResult(False, f"Delete failed: {e}", error=str(e))

    async def list_directory(self, path: str = ".") -> TaskResult:
        """List files in a directory."""
        try:
            p = Path(path)
            items = []
            for item in p.iterdir():
                size = item.stat().st_size if item.is_file() else 0
                items.append({
                    "name": item.name,
                    "type": "file" if item.is_file() else "dir",
                    "size": size,
                    "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                })
            return TaskResult(
                True,
                f"Directory {path} has {len(items)} items",
                data=items
            )
        except Exception as e:
            return TaskResult(False, f"Cannot list {path}: {e}", error=str(e))

    async def search_files(self, query: str, search_path: str = None) -> TaskResult:
        """Search for files by name or content."""
        search_root = Path(search_path) if search_path else self.home
        results = []
        try:
            for p in search_root.rglob(f"*{query}*"):
                if len(results) >= 50:
                    break
                results.append(str(p))
            return TaskResult(True, f"Found {len(results)} files matching '{query}'", data=results)
        except Exception as e:
            return TaskResult(False, f"Search failed: {e}", error=str(e))

    # ── PROCESS MANAGEMENT ─────────────────────────────────────────────────

    async def run_command(self, command: str, shell: bool = True) -> TaskResult:
        """Run a shell command and return output."""
        try:
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout + result.stderr
            return TaskResult(
                result.returncode == 0,
                output.strip() or "(no output)",
                data={"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
            )
        except subprocess.TimeoutExpired:
            return TaskResult(False, "Command timed out after 30 seconds")
        except Exception as e:
            return TaskResult(False, f"Command error: {e}", error=str(e))

    async def open_application(self, app_name: str) -> TaskResult:
        """Open an application by name."""
        try:
            apps = {
                "notepad": "notepad.exe",
                "calculator": "calc.exe",
                "paint": "mspaint.exe",
                "explorer": "explorer.exe",
                "chrome": "chrome.exe",
                "firefox": "firefox.exe",
                "word": "winword.exe",
                "excel": "excel.exe",
                "vscode": "code",
                "terminal": "cmd.exe",
                "powershell": "powershell.exe",
                "spotify": "spotify.exe",
                "task manager": "taskmgr.exe",
                "control panel": "control.exe",
            }

            exe = apps.get(app_name.lower(), app_name)
            subprocess.Popen([exe])
            return TaskResult(True, f"Opened {app_name}")
        except Exception as e:
            return TaskResult(False, f"Cannot open {app_name}: {e}", error=str(e))

    async def close_application(self, app_name: str) -> TaskResult:
        """Close an application by name."""
        try:
            for proc in psutil.process_iter(["name", "pid"]):
                if app_name.lower() in proc.info["name"].lower():
                    proc.terminate()
            return TaskResult(True, f"Closed {app_name}")
        except Exception as e:
            return TaskResult(False, f"Cannot close {app_name}: {e}", error=str(e))

    async def get_system_info(self) -> TaskResult:
        """Get comprehensive system information."""
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        battery = psutil.sensors_battery()

        info = {
            "cpu_percent": cpu,
            "ram_total_gb": round(ram.total / 1e9, 2),
            "ram_used_gb": round(ram.used / 1e9, 2),
            "ram_percent": ram.percent,
            "disk_total_gb": round(disk.total / 1e9, 2),
            "disk_free_gb": round(disk.free / 1e9, 2),
            "disk_percent": disk.percent,
            "battery_percent": battery.percent if battery else None,
            "battery_plugged": battery.power_plugged if battery else None,
            "uptime_hours": round((datetime.now().timestamp() - psutil.boot_time()) / 3600, 1),
            "process_count": len(psutil.pids()),
        }

        summary = (
            f"CPU: {cpu}% | RAM: {ram.percent}% ({info['ram_used_gb']}/{info['ram_total_gb']} GB) | "
            f"Disk: {disk.percent}% full | "
            f"Battery: {info['battery_percent']}%" if battery else ""
        )

        return TaskResult(True, summary, data=info)

    async def get_running_processes(self) -> TaskResult:
        """List top running processes by CPU usage."""
        procs = []
        for proc in sorted(psutil.process_iter(["name", "pid", "cpu_percent", "memory_percent"]),
                           key=lambda p: p.info.get("cpu_percent", 0), reverse=True)[:20]:
            procs.append(proc.info)
        return TaskResult(True, f"Top {len(procs)} processes", data=procs)

    # ── BROWSER & WEB ──────────────────────────────────────────────────────

    async def open_url(self, url: str) -> TaskResult:
        """Open a URL in the default browser."""
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
        return TaskResult(True, f"Opened: {url}")

    async def web_search(self, query: str) -> TaskResult:
        """Search the web using DuckDuckGo API."""
        try:
            url = f"https://api.duckduckgo.com/?q={requests.utils.quote(query)}&format=json&no_html=1"
            resp = requests.get(url, timeout=10)
            data = resp.json()

            abstract = data.get("AbstractText", "")
            answer = data.get("Answer", "")
            results = [r.get("Text", "") for r in data.get("RelatedTopics", [])[:5] if "Text" in r]

            output = answer or abstract or "\n".join(results) or "No results found."
            return TaskResult(True, output, data=data)
        except Exception as e:
            return TaskResult(False, f"Search failed: {e}", error=str(e))

    # ── WHATSAPP ───────────────────────────────────────────────────────────

    async def send_whatsapp_message(self, phone: str, message: str) -> TaskResult:
        """Send a WhatsApp message using pywhatkit."""
        try:
            import pywhatkit
            now = datetime.now()
            hour = now.hour
            minute = now.minute + 2  # 2 minute delay

            pywhatkit.sendwhatmsg(
                phone_no=phone,
                message=message,
                time_hour=hour,
                time_min=minute,
                wait_time=15,
                tab_close=True,
                close_time=3
            )
            return TaskResult(True, f"WhatsApp message scheduled to {phone}")
        except Exception as e:
            return TaskResult(False, f"WhatsApp error: {e}", error=str(e))

    async def send_whatsapp_to_contact(self, name: str, message: str) -> TaskResult:
        """Send WhatsApp message to a saved contact by name."""
        try:
            import pywhatkit
            pywhatkit.sendwhatmsg_to_group_instantly(name, message) if "group" in name.lower() \
                else pywhatkit.sendwhats_image(name, "")
            # Use selenium for more reliable sending
            return await self._selenium_whatsapp(name, message)
        except Exception as e:
            return TaskResult(False, f"WhatsApp contact error: {e}", error=str(e))

    async def _selenium_whatsapp(self, contact: str, message: str) -> TaskResult:
        """Use Selenium to send WhatsApp Web messages."""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager
            import time

            options = Options()
            profile_path = os.getenv("CHROME_PROFILE_PATH", "")
            if profile_path:
                options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument("--no-sandbox")

            driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
            driver.get(f"https://web.whatsapp.com/send?phone={contact}&text={requests.utils.quote(message)}")

            time.sleep(15)  # Wait for WhatsApp to load

            # Click send button
            send_btn = driver.find_element(By.XPATH, "//span[@data-icon='send']")
            send_btn.click()
            time.sleep(3)
            driver.quit()

            return TaskResult(True, f"WhatsApp message sent to {contact}")
        except Exception as e:
            return TaskResult(False, f"Selenium WhatsApp error: {e}", error=str(e))

    # ── EMAIL ──────────────────────────────────────────────────────────────

    async def send_email(self, to: str, subject: str, body: str) -> TaskResult:
        """Send an email via Gmail SMTP."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            email_addr = os.getenv("EMAIL_ADDRESS")
            email_pass = os.getenv("EMAIL_PASSWORD")

            if not email_addr or not email_pass:
                return TaskResult(False, "Email credentials not configured in .env")

            msg = MIMEMultipart()
            msg["From"] = email_addr
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com"),
                              int(os.getenv("EMAIL_SMTP_PORT", 587))) as server:
                server.starttls()
                server.login(email_addr, email_pass)
                server.send_message(msg)

            return TaskResult(True, f"Email sent to {to} with subject '{subject}'")
        except Exception as e:
            return TaskResult(False, f"Email error: {e}", error=str(e))

    # ── SCREEN & GUI ───────────────────────────────────────────────────────

    async def take_screenshot(self, save_path: Optional[str] = None) -> TaskResult:
        """Take a screenshot of the screen."""
        try:
            screenshot = pyautogui.screenshot()
            if not save_path:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = str(self.home / "Pictures" / f"friday_screenshot_{ts}.png")
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            screenshot.save(save_path)
            return TaskResult(True, f"Screenshot saved to {save_path}", data=save_path)
        except Exception as e:
            return TaskResult(False, f"Screenshot error: {e}", error=str(e))

    async def type_text(self, text: str) -> TaskResult:
        """Type text at the current cursor position."""
        try:
            pyautogui.typewrite(text, interval=0.05)
            return TaskResult(True, f"Typed: {text[:50]}...")
        except Exception as e:
            return TaskResult(False, f"Typing error: {e}", error=str(e))

    async def click_at(self, x: int, y: int) -> TaskResult:
        """Click at screen coordinates."""
        try:
            pyautogui.click(x, y)
            return TaskResult(True, f"Clicked at ({x}, {y})")
        except Exception as e:
            return TaskResult(False, f"Click error: {e}", error=str(e))

    async def press_key(self, key: str) -> TaskResult:
        """Press a keyboard key or hotkey."""
        try:
            if "+" in key:
                keys = key.split("+")
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(key)
            return TaskResult(True, f"Pressed: {key}")
        except Exception as e:
            return TaskResult(False, f"Key press error: {e}", error=str(e))

    # ── VOLUME & MEDIA ─────────────────────────────────────────────────────

    async def set_volume(self, level: int) -> TaskResult:
        """Set system volume (0-100)."""
        try:
            level = max(0, min(100, level))
            if self.os_name == "Windows":
                script = f"""
                $audio = New-Object -ComObject WScript.Shell
                $volume = [Math]::Round({level} / 2)
                1..$volume | % {{ $audio.SendKeys([char]175) }}
                """
                subprocess.run(["powershell", "-c", script], capture_output=True)
            return TaskResult(True, f"Volume set to {level}%")
        except Exception as e:
            return TaskResult(False, f"Volume error: {e}", error=str(e))

    async def play_media(self, file_path: str) -> TaskResult:
        """Play a media file."""
        try:
            if self.os_name == "Windows":
                os.startfile(file_path)
            return TaskResult(True, f"Playing: {file_path}")
        except Exception as e:
            return TaskResult(False, f"Media error: {e}", error=str(e))

    # ── CLIPBOARD ──────────────────────────────────────────────────────────

    async def get_clipboard(self) -> TaskResult:
        """Get clipboard content."""
        try:
            import pyperclip
            content = pyperclip.paste()
            return TaskResult(True, f"Clipboard: {content[:200]}", data=content)
        except Exception as e:
            return TaskResult(False, f"Clipboard error: {e}", error=str(e))

    async def set_clipboard(self, text: str) -> TaskResult:
        """Set clipboard content."""
        try:
            import pyperclip
            pyperclip.copy(text)
            return TaskResult(True, f"Copied to clipboard: {text[:50]}")
        except Exception as e:
            return TaskResult(False, f"Clipboard error: {e}", error=str(e))

    # ── INTERNET & API ─────────────────────────────────────────────────────

    async def get_weather(self, city: str = "auto") -> TaskResult:
        """Get current weather for a city."""
        try:
            if city == "auto":
                city = ""
            url = f"https://wttr.in/{requests.utils.quote(city)}?format=j1"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            current = data["current_condition"][0]

            weather_info = {
                "temp_c": current["temp_C"],
                "feels_like_c": current["FeelsLikeC"],
                "description": current["weatherDesc"][0]["value"],
                "humidity": current["humidity"],
                "wind_kmph": current["windspeedKmph"],
            }

            summary = (
                f"{weather_info['description']}, {weather_info['temp_c']}°C "
                f"(feels like {weather_info['feels_like_c']}°C), "
                f"humidity {weather_info['humidity']}%"
            )

            return TaskResult(True, summary, data=weather_info)
        except Exception as e:
            return TaskResult(False, f"Weather error: {e}", error=str(e))

    async def get_time_date(self) -> TaskResult:
        """Get current time and date."""
        now = datetime.now()
        info = {
            "time": now.strftime("%I:%M %p"),
            "date": now.strftime("%A, %B %d, %Y"),
            "day": now.strftime("%A"),
            "timestamp": now.isoformat(),
        }
        return TaskResult(
            True,
            f"It's {info['time']} on {info['date']}",
            data=info
        )

    # ── REMINDER & SCHEDULE ────────────────────────────────────────────────

    async def set_reminder(self, text: str, minutes: int) -> TaskResult:
        """Set a reminder for N minutes from now."""
        try:
            import threading
            def _remind():
                import time
                time.sleep(minutes * 60)
                # Will call back to FRIDAY's speak system
                logger.info(f"REMINDER: {text}")
                # Windows notification
                subprocess.run([
                    "powershell", "-c",
                    f"""New-BurntToastNotification -Text 'FRIDAY Reminder', '{text}'"""
                ], capture_output=True)

            t = threading.Timer(minutes * 60, lambda: logger.info(f"REMINDER: {text}"))
            t.daemon = True
            t.start()

            return TaskResult(True, f"Reminder set for {minutes} minutes: {text}")
        except Exception as e:
            return TaskResult(False, f"Reminder error: {e}", error=str(e))

    # ── POWER ──────────────────────────────────────────────────────────────

    async def sleep_system(self) -> TaskResult:
        """Put the system to sleep."""
        await self.run_command("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return TaskResult(True, "System going to sleep.")

    async def lock_system(self) -> TaskResult:
        """Lock the workstation."""
        await self.run_command("rundll32.exe user32.dll,LockWorkStation")
        return TaskResult(True, "System locked.")

    async def shutdown_system(self, minutes: int = 0) -> TaskResult:
        """Schedule a shutdown."""
        if minutes > 0:
            await self.run_command(f"shutdown /s /t {minutes * 60}")
            return TaskResult(True, f"Shutdown scheduled in {minutes} minutes.")
        else:
            await self.run_command("shutdown /s /t 0")
            return TaskResult(True, "Shutting down now.")

    # ── TASK ROUTER ────────────────────────────────────────────────────────

    async def execute(self, action: str, params: Dict) -> TaskResult:
        """Route a parsed action to the correct handler."""
        handler_name = self.ACTION_MAP.get(action)
        if not handler_name:
            return TaskResult(False, f"Unknown action: {action}")

        handler = getattr(self, handler_name, None)
        if not handler:
            return TaskResult(False, f"Handler {handler_name} not found")

        try:
            return await handler(**params)
        except TypeError as e:
            return TaskResult(False, f"Invalid parameters for {action}: {e}", error=str(e))
