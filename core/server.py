"""
FRIDAY AI — WebSocket Dashboard Server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FastAPI + WebSocket backend for the real-time FRIDAY dashboard.
Handles API calls, live status streaming, and voice pass-through.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Set, Optional
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from loguru import logger


# ── Request Models ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str

class ActionRequest(BaseModel):
    action: str
    params: dict = {}

class FactRequest(BaseModel):
    key: str
    value: str


# ── WebSocket Manager ────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.add(ws)
        logger.info(f"Dashboard connected. Total: {len(self.active_connections)}")

    def disconnect(self, ws: WebSocket):
        self.active_connections.discard(ws)
        logger.info(f"Dashboard disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        dead = set()
        for ws in self.active_connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        self.active_connections -= dead

    async def send_to(self, ws: WebSocket, data: dict):
        try:
            await ws.send_json(data)
        except Exception:
            self.active_connections.discard(ws)


manager = ConnectionManager()


def create_app(friday_instance) -> FastAPI:
    """Create the FastAPI app with FRIDAY as the backend."""

    app = FastAPI(
        title="FRIDAY AI",
        description="Your personal AI assistant dashboard",
        version="1.0.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve dashboard static files
    dashboard_path = Path(__file__).parent.parent / "dashboard"
    if dashboard_path.exists():
        app.mount("/assets", StaticFiles(directory=str(dashboard_path / "assets")), name="assets")

    friday = friday_instance

    # ── REST API ──────────────────────────────────────────────────────────

    @app.get("/")
    async def root():
        dashboard_file = Path(__file__).parent.parent / "dashboard" / "index.html"
        if dashboard_file.exists():
            return FileResponse(str(dashboard_file))
        return {"status": "FRIDAY online", "time": datetime.now().isoformat()}

    @app.get("/api/status")
    async def get_status():
        """Get FRIDAY's current status."""
        sys_info = await friday.agent.get_system_info()
        return {
            "status": "online",
            "emotion": friday.emotions.state,
            "idle_minutes": friday.get_idle_minutes(),
            "session_id": friday.session_id,
            "memory_count": friday.memory._count_memories(),
            "system": sys_info.data,
            "timestamp": datetime.now().isoformat(),
        }

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        """Send a text message to FRIDAY."""
        response, emotion = await friday.process_input(req.message)

        # Broadcast to all dashboard connections
        await manager.broadcast({
            "type": "chat",
            "role": "friday",
            "content": response,
            "emotion": emotion,
            "timestamp": datetime.now().isoformat(),
        })

        return {"response": response, "emotion": emotion}

    @app.post("/api/action")
    async def execute_action(req: ActionRequest):
        """Execute a system action directly."""
        result = await friday.agent.execute(req.action, req.params)
        return {
            "success": result.success,
            "output": result.output,
            "data": result.data,
            "error": result.error,
        }

    @app.get("/api/memory")
    async def get_memory(query: str = "", limit: int = 20):
        """Retrieve memories."""
        if query:
            memories = await friday.memory.recall(query, top_k=limit)
        else:
            memories = friday.memory.get_working_memory()
            memories = memories[-limit:]

        return {
            "memories": [m.to_dict() for m in memories],
            "count": len(memories),
        }

    @app.get("/api/conversation")
    async def get_conversation(limit: int = 50):
        """Get recent conversation history."""
        history = await friday.memory.get_conversation_history(limit=limit)
        return {"history": history}

    @app.get("/api/facts")
    async def get_facts():
        """Get all known facts about the owner."""
        facts = await friday.memory.get_facts()
        return {"facts": facts}

    @app.post("/api/facts")
    async def add_fact(req: FactRequest):
        """Manually add a fact."""
        await friday.memory.learn_fact(req.key, req.value)
        return {"success": True, "key": req.key, "value": req.value}

    @app.get("/api/emotion")
    async def get_emotion():
        """Get current emotional state."""
        return friday.emotions.state

    @app.post("/api/speak")
    async def speak(req: ChatRequest):
        """Make FRIDAY speak something."""
        if friday.voice:
            await friday.voice.speak(req.message, friday.emotions.current_emotion.name)
        return {"spoken": req.message}

    @app.delete("/api/memory/{memory_id}")
    async def delete_memory(memory_id: str):
        """Delete a specific memory."""
        import sqlite3
        conn = sqlite3.connect(friday.memory.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        conn.close()
        return {"deleted": memory_id}

    # ── WebSocket ─────────────────────────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await manager.connect(ws)

        # Send initial state
        await manager.send_to(ws, {
            "type": "connected",
            "emotion": friday.emotions.state,
            "timestamp": datetime.now().isoformat(),
        })

        # Start status broadcaster for this connection
        async def send_status_loop():
            while True:
                try:
                    sys_info = await friday.agent.get_system_info()
                    await manager.send_to(ws, {
                        "type": "status",
                        "emotion": friday.emotions.state,
                        "idle_minutes": friday.get_idle_minutes(),
                        "system": sys_info.data,
                        "timestamp": datetime.now().isoformat(),
                    })
                    await asyncio.sleep(5)  # Update every 5 seconds
                except Exception:
                    break

        status_task = asyncio.create_task(send_status_loop())

        try:
            while True:
                data = await ws.receive_json()
                msg_type = data.get("type")

                if msg_type == "chat":
                    user_msg = data.get("content", "")

                    # Echo user message to all dashboards
                    await manager.broadcast({
                        "type": "chat",
                        "role": "user",
                        "content": user_msg,
                        "timestamp": datetime.now().isoformat(),
                    })

                    # Process and respond
                    response, emotion = await friday.process_input(user_msg)

                    if friday.voice:
                        asyncio.create_task(
                            friday.voice.speak(response, emotion)
                        )

                    await manager.broadcast({
                        "type": "chat",
                        "role": "friday",
                        "content": response,
                        "emotion": emotion,
                        "timestamp": datetime.now().isoformat(),
                    })

                elif msg_type == "action":
                    action = data.get("action")
                    params = data.get("params", {})
                    result = await friday.agent.execute(action, params)

                    await manager.send_to(ws, {
                        "type": "action_result",
                        "success": result.success,
                        "output": result.output,
                        "data": str(result.data) if result.data else None,
                    })

                elif msg_type == "ping":
                    await manager.send_to(ws, {"type": "pong"})

        except WebSocketDisconnect:
            pass
        finally:
            status_task.cancel()
            manager.disconnect(ws)

    return app


async def broadcast_friday_speech(text: str, emotion: str):
    """Called when FRIDAY speaks — broadcasts to all dashboard clients."""
    await manager.broadcast({
        "type": "speech",
        "content": text,
        "emotion": emotion,
        "timestamp": datetime.now().isoformat(),
    })
