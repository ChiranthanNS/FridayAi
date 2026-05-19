"""
FRIDAY AI — Neural Memory System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Episodic memory, semantic search, emotional tagging, and long-term recall.
Every single conversation is stored, indexed, and retrieved intelligently.
"""

import os
import json
import uuid
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from loguru import logger

import numpy as np
import hashlib
import chromadb
from chromadb.config import Settings

# Try to load sentence-transformer (needs model downloaded first)
try:
    from sentence_transformers import SentenceTransformer as _ST
    _ENCODER_MODEL = None  # Lazy load

    def _load_encoder():
        global _ENCODER_MODEL
        if _ENCODER_MODEL is None:
            try:
                _ENCODER_MODEL = _ST("all-MiniLM-L6-v2")
                logger.info("Neural sentence encoder loaded.")
            except Exception as e:
                logger.warning(f"Encoder download failed ({e}). Using hash fallback.")
                _ENCODER_MODEL = None
        return _ENCODER_MODEL

    def _encode_text(text: str) -> list:
        """Encode text to a 384-dim vector (neural or hash fallback)."""
        enc = _load_encoder()
        if enc:
            return enc.encode(text).tolist()
        # Hash-based fallback: deterministic 384-dim vector
        h = hashlib.sha256(text.encode()).digest()
        vec = []
        for i in range(384):
            byte_val = h[i % 32]
            bit = (byte_val >> (i % 8)) & 1
            vec.append(float(bit) * 2 - 1 + (i * 0.001))
        norm = max(sum(v*v for v in vec) ** 0.5, 1e-9)
        return [v / norm for v in vec]

except ImportError:
    logger.warning("sentence-transformers not installed. Using hash embeddings.")

    def _encode_text(text: str) -> list:
        h = hashlib.sha256(text.encode()).digest()
        vec = []
        for i in range(384):
            byte_val = h[i % 32]
            bit = (byte_val >> (i % 8)) & 1
            vec.append(float(bit) * 2 - 1 + (i * 0.001))
        norm = max(sum(v*v for v in vec) ** 0.5, 1e-9)
        return [v / norm for v in vec]


class MemoryType:
    CONVERSATION = "conversation"
    TASK = "task"
    FACT = "fact"
    EMOTION = "emotion"
    SYSTEM = "system"
    PREFERENCE = "preference"
    EVENT = "event"


class EmotionState:
    HAPPY = "happy"
    CURIOUS = "curious"
    CONCERNED = "concerned"
    NEUTRAL = "neutral"
    EXCITED = "excited"
    FOCUSED = "focused"
    EMPATHETIC = "empathetic"
    PLAYFUL = "playful"


class Memory:
    """A single memory unit in FRIDAY's brain."""
    def __init__(
        self,
        content: str,
        memory_type: str = MemoryType.CONVERSATION,
        emotion: str = EmotionState.NEUTRAL,
        importance: float = 0.5,
        metadata: Optional[Dict] = None,
        memory_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.id = memory_id or str(uuid.uuid4())
        self.content = content
        self.memory_type = memory_type
        self.emotion = emotion
        self.importance = importance  # 0.0 to 1.0
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now()
        self.access_count = 0
        self.last_accessed = self.timestamp

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "emotion": self.emotion,
            "importance": self.importance,
            "metadata": json.dumps(self.metadata),
            "timestamp": self.timestamp.isoformat(),
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Memory":
        m = cls(
            content=data["content"],
            memory_type=data["memory_type"],
            emotion=data.get("emotion", EmotionState.NEUTRAL),
            importance=data.get("importance", 0.5),
            metadata=json.loads(data.get("metadata", "{}")),
            memory_id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )
        m.access_count = data.get("access_count", 0)
        m.last_accessed = datetime.fromisoformat(
            data.get("last_accessed", data["timestamp"])
        )
        return m


class NeuralMemory:
    """
    FRIDAY's complete memory system — combines:
    - SQLite for persistent episodic memory
    - ChromaDB for semantic vector search
    - In-memory working buffer (short-term memory)
    """

    def __init__(self, db_path: str = "./data/memory.db", vector_path: str = "./data/chromadb"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(vector_path).mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._working_memory: List[Memory] = []  # Short-term buffer (last 50)
        self._max_working = 50

        # Initialize vector store
        self.chroma_client = chromadb.PersistentClient(
            path=vector_path,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="friday_memory",
            metadata={"hnsw:space": "cosine"}
        )

        # Initialize SQLite
        self._init_db()
        self._load_working_memory()
        logger.info(f"Memory system online. {self._count_memories()} total memories loaded.")

    def _init_db(self):
        """Create the memory database schema."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                emotion TEXT DEFAULT 'neutral',
                importance REAL DEFAULT 0.5,
                metadata TEXT DEFAULT '{}',
                timestamp TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                emotion TEXT DEFAULT 'neutral',
                timestamp TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS owner_facts (
                id TEXT PRIMARY KEY,
                fact_key TEXT UNIQUE NOT NULL,
                fact_value TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                summary TEXT,
                emotion_arc TEXT,
                topics TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _count_memories(self) -> int:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM memories")
        count = c.fetchone()[0]
        conn.close()
        return count

    def _load_working_memory(self):
        """Load recent memories into working buffer."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT * FROM memories 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (self._max_working,))
        rows = c.fetchall()
        conn.close()

        columns = ["id", "content", "memory_type", "emotion", "importance",
                   "metadata", "timestamp", "access_count", "last_accessed"]
        self._working_memory = [
            Memory.from_dict(dict(zip(columns, row))) for row in rows
        ]
        self._working_memory.reverse()

    async def store(self, memory: Memory) -> str:
        """Store a memory in both SQLite and ChromaDB."""
        # SQLite storage
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        d = memory.to_dict()
        c.execute("""
            INSERT OR REPLACE INTO memories 
            (id, content, memory_type, emotion, importance, metadata, timestamp, access_count, last_accessed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (d["id"], d["content"], d["memory_type"], d["emotion"], d["importance"],
              d["metadata"], d["timestamp"], d["access_count"], d["last_accessed"]))
        conn.commit()
        conn.close()

        # Vector store — embed content
        embedding = _encode_text(memory.content)
        self.collection.upsert(
            ids=[memory.id],
            embeddings=[embedding],
            documents=[memory.content],
            metadatas=[{
                "type": memory.memory_type,
                "emotion": memory.emotion,
                "importance": str(memory.importance),
                "timestamp": memory.timestamp.isoformat(),
            }]
        )

        # Update working memory
        self._working_memory.append(memory)
        if len(self._working_memory) > self._max_working:
            self._working_memory.pop(0)

        return memory.id

    async def recall(self, query: str, top_k: int = 10, memory_type: Optional[str] = None) -> List[Memory]:
        """Semantic search across all memories."""
        query_embedding = _encode_text(query)

        where_filter = {}
        if memory_type:
            where_filter["type"] = memory_type

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, max(1, self.collection.count())),
            where=where_filter if where_filter else None,
        )

        memories = []
        if results["ids"] and results["ids"][0]:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            columns = ["id", "content", "memory_type", "emotion", "importance",
                       "metadata", "timestamp", "access_count", "last_accessed"]
            for mem_id in results["ids"][0]:
                c.execute("SELECT * FROM memories WHERE id = ?", (mem_id,))
                row = c.fetchone()
                if row:
                    m = Memory.from_dict(dict(zip(columns, row)))
                    # Update access count
                    c.execute("""
                        UPDATE memories SET access_count = access_count + 1, last_accessed = ?
                        WHERE id = ?
                    """, (datetime.now().isoformat(), mem_id))
                    memories.append(m)
            conn.commit()
            conn.close()

        return memories

    async def remember_conversation_turn(
        self, session_id: str, role: str, content: str, emotion: str = EmotionState.NEUTRAL
    ):
        """Log every single conversation turn."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO conversations (id, session_id, role, content, emotion, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), session_id, role, content, emotion, datetime.now().isoformat()))
        conn.commit()
        conn.close()

        # Also store as a general memory
        mem = Memory(
            content=f"[{role.upper()}]: {content}",
            memory_type=MemoryType.CONVERSATION,
            emotion=emotion,
            importance=0.6 if role == "user" else 0.4,
        )
        await self.store(mem)

    async def get_conversation_history(
        self, session_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """Retrieve full conversation history."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if session_id:
            c.execute("""
                SELECT role, content, emotion, timestamp FROM conversations
                WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?
            """, (session_id, limit))
        else:
            c.execute("""
                SELECT role, content, emotion, timestamp FROM conversations
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
        rows = c.fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1], "emotion": r[2], "timestamp": r[3]} for r in rows]

    async def learn_fact(self, key: str, value: str, confidence: float = 1.0):
        """Store a fact about the owner (name, preferences, habits)."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO owner_facts (id, fact_key, fact_value, confidence, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), key, value, confidence, datetime.now().isoformat()))
        conn.commit()
        conn.close()

        # Also store in vector memory
        mem = Memory(
            content=f"Owner fact: {key} = {value}",
            memory_type=MemoryType.FACT,
            importance=0.9,
        )
        await self.store(mem)
        logger.info(f"Learned new fact: {key} = {value}")

    async def get_facts(self) -> Dict[str, str]:
        """Get all known facts about the owner."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT fact_key, fact_value FROM owner_facts ORDER BY updated_at DESC")
        rows = c.fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}

    async def get_context_summary(self, query: str, max_memories: int = 15) -> str:
        """Build a rich context string from relevant memories for LLM prompts."""
        relevant = await self.recall(query, top_k=max_memories)
        recent = self._working_memory[-10:] if self._working_memory else []
        facts = await self.get_facts()

        context_parts = []

        if facts:
            fact_str = "\n".join([f"  • {k}: {v}" for k, v in list(facts.items())[:20]])
            context_parts.append(f"[Owner Facts]\n{fact_str}")

        if recent:
            recent_str = "\n".join([
                f"  [{m.emotion}] {m.content[:200]}" for m in recent[-5:]
            ])
            context_parts.append(f"[Recent Context]\n{recent_str}")

        if relevant:
            mem_str = "\n".join([
                f"  [{m.memory_type}|{m.timestamp.strftime('%Y-%m-%d')}] {m.content[:200]}"
                for m in relevant[:8]
            ])
            context_parts.append(f"[Relevant Memories]\n{mem_str}")

        return "\n\n".join(context_parts)

    def get_working_memory(self) -> List[Memory]:
        """Get current short-term working memory."""
        return self._working_memory[-20:]

    async def consolidate_memories(self):
        """Periodic memory consolidation — increase importance of frequently accessed memories."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            UPDATE memories SET importance = MIN(1.0, importance + 0.1)
            WHERE access_count > 5
        """)
        # Decay old low-importance memories
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        c.execute("""
            DELETE FROM memories 
            WHERE importance < 0.2 AND timestamp < ? AND memory_type = 'conversation'
        """, (cutoff,))
        conn.commit()
        conn.close()
        logger.info("Memory consolidation complete.")
