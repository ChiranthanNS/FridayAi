# FRIDAY AI 🚀

FRIDAY is a highly advanced, emotionally intelligent digital assistant designed for complete system automation and proactive companionship. Unlike generic AI, FRIDAY features a persistent neural memory, an evolving emotional state, and deep integration with your OS.

## ✨ Key Features

- **🧠 Neural Brain**: Powered by Gemini LLMs with automatic model fallback.
- **🎙️ Voice Interface**: Neural TTS via Microsoft Edge and continuous listening with wake-word detection.
- **❤️ Emotion Engine**: Real-time sentiment analysis that affects FRIDAYs voice, personality, and proactivity.
- **💾 Long-Term Memory**: Hybrid storage using ChromaDB (semantic search) and SQLite (episodic/fact memory).
- **🛠️ System Agent**: Full control over files, applications, WhatsApp, Email, and system settings.
- **🌐 Real-time Dashboard**: A FastAPI + WebSocket dashboard for monitoring and interacting with FRIDAY.
- **🕒 Proactive Awareness**: Ambient monitoring of system health and idle time to initiate conversations naturally.

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.11 or 3.12** (Stable releases recommended)
- **Windows OS** (for full system automation capabilities)
- **Gemini API Key** (from [ai.google.dev](https://ai.google.dev))

### 2. Installation
Clone the repository and run the setup script:
```bash
git clone https://github.com/ChiranthanNS/FridayAi.git
cd FridayAi
./setup.bat
```

### 3. Configuration
Rename `.env.example` to `.env` and fill in your details:
```env
GEMINI_API_KEY=your_api_key_here
OWNER_NAME=Your Name
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
CHROME_PROFILE_PATH=C:\\Users\\YourUser\\AppData\\Local\\Google\\Chrome\\User Data
```

### 4. Running FRIDAY
```bash
./start_friday.bat
```
Once online, access the dashboard at `http://localhost:8765`.

## 🛠️ Architecture

- `friday.py`: The main orchestrator.
- `core/brain.py`: Intelligence, LLM routing, and action parsing.
- `core/voice.py`: Speech-to-Text (STT) and Text-to-Speech (TTS).
- `core/memory.py`: Vector and relational memory management.
- `core/agent.py`: OS-level automation handlers.
- `core/emotions.py`: VADER-based sentiment and emotional state machine.
- `core/watcher.py`: Ambient system monitoring and proactivity logic.
- `core/server.py`: FastAPI backend for the web dashboard.

## 🛡️ Safety & Permissions
FRIDAY has full access to your system to perform tasks. Please ensure you run her in a trusted environment.

## 📜 License
MIT License

