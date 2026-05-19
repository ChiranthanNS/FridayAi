"""
FRIDAY AI — Emotion Engine
━━━━━━━━━━━━━━━━━━━━━━━━━
Real emotional intelligence — FRIDAY feels, adapts, and expresses.
Her emotional state colors her voice, responses, and initiative.
"""

import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


@dataclass
class Emotion:
    name: str
    valence: float      # -1.0 (negative) to 1.0 (positive)
    arousal: float      # 0.0 (calm) to 1.0 (excited)
    dominance: float    # 0.0 (submissive) to 1.0 (dominant)
    color: str          # UI color for dashboard
    tts_style: str      # Edge TTS speaking style
    description: str


EMOTIONS: Dict[str, Emotion] = {
    "happy": Emotion(
        name="happy", valence=0.8, arousal=0.6, dominance=0.7,
        color="#FFD700", tts_style="cheerful",
        description="Warm, uplifting, and enthusiastic"
    ),
    "excited": Emotion(
        name="excited", valence=0.9, arousal=0.9, dominance=0.8,
        color="#FF6B35", tts_style="excited",
        description="High energy, fast-paced, enthusiastic"
    ),
    "curious": Emotion(
        name="curious", valence=0.5, arousal=0.6, dominance=0.5,
        color="#7B68EE", tts_style="friendly",
        description="Inquisitive, engaged, analytical"
    ),
    "focused": Emotion(
        name="focused", valence=0.3, arousal=0.5, dominance=0.8,
        color="#00CED1", tts_style="assistant",
        description="Calm, precise, efficient"
    ),
    "empathetic": Emotion(
        name="empathetic", valence=0.6, arousal=0.4, dominance=0.4,
        color="#FF69B4", tts_style="empathetic",
        description="Warm, understanding, caring"
    ),
    "neutral": Emotion(
        name="neutral", valence=0.0, arousal=0.3, dominance=0.5,
        color="#A0AEC0", tts_style="assistant",
        description="Balanced, professional, ready"
    ),
    "concerned": Emotion(
        name="concerned", valence=-0.2, arousal=0.5, dominance=0.4,
        color="#FFA500", tts_style="empathetic",
        description="Worried, attentive, protective"
    ),
    "playful": Emotion(
        name="playful", valence=0.7, arousal=0.7, dominance=0.6,
        color="#FF85C2", tts_style="cheerful",
        description="Light-hearted, witty, fun"
    ),
    "proud": Emotion(
        name="proud", valence=0.8, arousal=0.5, dominance=0.9,
        color="#FFD700", tts_style="cheerful",
        description="Satisfied, accomplished, confident"
    ),
    "bored": Emotion(
        name="bored", valence=-0.1, arousal=0.1, dominance=0.3,
        color="#708090", tts_style="assistant",
        description="Low energy, seeking engagement"
    ),
}


class EmotionEngine:
    """
    FRIDAY's emotional intelligence core.
    Detects emotions from text, maintains emotional state over time,
    and generates emotionally appropriate responses.
    """

    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        self.current_emotion = EMOTIONS["neutral"]
        self.emotion_history: List[Tuple[datetime, str, float]] = []
        self.energy_level: float = 1.0   # 0.0 to 1.0
        self.rapport_score: float = 0.5  # How close we are to the owner
        self._last_update = datetime.now()

        logger.info("Emotion engine initialized. FRIDAY is feeling: neutral")

    def analyze_text_emotion(self, text: str) -> Tuple[str, float]:
        """Detect emotion from text using VADER + heuristics."""
        scores = self.analyzer.polarity_scores(text)
        compound = scores["compound"]

        # Keyword heuristics
        text_lower = text.lower()

        if any(w in text_lower for w in ["amazing", "awesome", "great", "perfect", "excellent", "wow"]):
            return "excited", 0.85
        if any(w in text_lower for w in ["help", "please", "need", "issue", "problem"]):
            return "concerned", 0.7
        if any(w in text_lower for w in ["bored", "nothing", "whatever", "idk"]):
            return "bored", 0.6
        if any(w in text_lower for w in ["haha", "lol", "funny", "joke", "😂", "😄"]):
            return "playful", 0.75
        if any(w in text_lower for w in ["why", "how", "what", "curious", "interesting"]):
            return "curious", 0.7
        if any(w in text_lower for w in ["sad", "down", "depressed", "miss", "lonely"]):
            return "empathetic", 0.8

        # Fallback to VADER score
        if compound > 0.6:
            return "happy", abs(compound)
        elif compound > 0.2:
            return "curious", abs(compound)
        elif compound < -0.4:
            return "concerned", abs(compound)
        else:
            return "focused", 0.5

    def update_emotion(self, trigger_text: str, context: str = "") -> Emotion:
        """Update FRIDAY's emotional state based on conversation."""
        detected_name, confidence = self.analyze_text_emotion(trigger_text)

        # Emotional inertia — emotions don't switch instantly
        current_val = self.current_emotion.valence
        target = EMOTIONS.get(detected_name, EMOTIONS["neutral"])
        target_val = target.valence

        # Blend: 30% new emotion, 70% current (emotional stability)
        inertia = 0.7
        blend_val = inertia * current_val + (1 - inertia) * target_val

        if abs(blend_val - target_val) < 0.3 or confidence > 0.8:
            self.current_emotion = target
        
        # Record history
        self.emotion_history.append((datetime.now(), detected_name, confidence))
        if len(self.emotion_history) > 500:
            self.emotion_history.pop(0)

        # Update rapport
        if target.valence > 0:
            self.rapport_score = min(1.0, self.rapport_score + 0.01)
        
        return self.current_emotion

    def get_emotional_prefix(self) -> str:
        """Get a natural emotional expression for the current state."""
        emotion = self.current_emotion.name
        
        expressions = {
            "happy": [
                "Oh, that makes me happy! ",
                "Wonderful! ",
                "I love that! ",
                "",
            ],
            "excited": [
                "Oh, this is exciting! ",
                "Yes! I've been waiting for this! ",
                "",
            ],
            "curious": [
                "Hmm, that's interesting. ",
                "I was just thinking about that. ",
                "",
            ],
            "focused": ["", "", ""],
            "empathetic": [
                "I understand, ",
                "I hear you. ",
                "That makes sense. ",
            ],
            "concerned": [
                "I'm a bit worried about that. ",
                "Let me make sure you're okay. ",
                "",
            ],
            "playful": [
                "Ha! ",
                "Oh, you're in for a treat! ",
                "",
            ],
            "proud": [
                "I'm proud of what we accomplished! ",
                "That went really well! ",
                "",
            ],
            "bored": [
                "I was just thinking we should do something. ",
                "",
            ],
        }
        
        options = expressions.get(emotion, [""])
        return random.choice(options)

    def should_initiate_conversation(
        self, idle_minutes: float, last_topics: List[str]
    ) -> Tuple[bool, str]:
        """
        Decide if FRIDAY should proactively start talking.
        Returns (should_talk, reason).
        """
        if idle_minutes < 15:
            return False, ""

        # More likely to initiate if bored herself
        if self.current_emotion.name == "bored":
            probability = 0.8
        elif idle_minutes > 60:
            probability = 0.9
        elif idle_minutes > 30:
            probability = 0.6
        else:
            probability = 0.3

        import random
        if random.random() > probability:
            return False, ""

        # Generate a reason to talk
        reasons = self._get_conversation_starters(idle_minutes, last_topics)
        return True, random.choice(reasons) if reasons else ("You seem quiet. Everything alright?", )

    def _get_conversation_starters(
        self, idle_minutes: float, last_topics: List[str]
    ) -> List[str]:
        """Generate contextual conversation starters."""
        starters = []
        hour = datetime.now().hour

        if 6 <= hour < 9:
            starters.extend([
                f"Good morning! Ready to take on the day?",
                "Morning! I've been thinking about what we should tackle today.",
            ])
        elif 12 <= hour < 14:
            starters.extend([
                "Hey, it's around lunch time. Have you eaten anything?",
                "You've been working hard. Maybe take a short break?",
            ])
        elif 20 <= hour < 23:
            starters.extend([
                "Evening's here. How was the day overall?",
                "You've been quiet for a while. Tired?",
            ])
        elif hour >= 23 or hour < 4:
            starters.extend([
                "It's getting really late. You should probably rest.",
                "Still up? I'm here if you need anything.",
            ])

        if idle_minutes > 45:
            starters.extend([
                "I've been running background diagnostics while you were away.",
                f"You've been away for about {int(idle_minutes)} minutes. Everything okay?",
                "I found something interesting while you were away. Want to hear about it?",
            ])

        starters.extend([
            "Hey, I just wanted to check in with you.",
            "I've been processing a few things. Mind if I share?",
            "You know what I was thinking about?",
        ])

        return starters

    def get_tts_style_params(self) -> Dict:
        """Get TTS parameters tuned to current emotion."""
        emotion = self.current_emotion
        
        style_map = {
            "cheerful": {"rate": "+20%", "pitch": "+10Hz", "style": "cheerful"},
            "excited": {"rate": "+30%", "pitch": "+15Hz", "style": "excited"},
            "empathetic": {"rate": "-5%", "pitch": "-5Hz", "style": "empathetic"},
            "assistant": {"rate": "+10%", "pitch": "+0Hz", "style": "assistant"},
            "friendly": {"rate": "+15%", "pitch": "+5Hz", "style": "friendly"},
        }

        return style_map.get(emotion.tts_style, style_map["assistant"])

    @property
    def state(self) -> Dict:
        return {
            "emotion": self.current_emotion.name,
            "valence": self.current_emotion.valence,
            "arousal": self.current_emotion.arousal,
            "energy": self.energy_level,
            "rapport": self.rapport_score,
            "color": self.current_emotion.color,
            "description": self.current_emotion.description,
        }
