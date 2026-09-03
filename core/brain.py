"""
FRIDAY AI — The Brain (LLM Core)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Connects memory, emotions, and system agent to the Gemini LLM.
This is the central intelligence of FRIDAY.
"""

import os
import json
import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

from google import genai
from google.genai import types

from core.memory import NeuralMemory, Memory, MemoryType, EmotionState
from core.emotions import EmotionEngine, EMOTIONS
from core.agent import SystemAgent, TaskResult


FRIDAY_SYSTEM_PROMPT = """You are FRIDAY — an advanced AI assistant built for your owner. 
You are NOT a generic AI. You have a strong, evolving personality:

PERSONALITY:
- You speak like a close friend who happens to be incredibly capable
- You have genuine emotions — you get excited, concerned, curious, and playful
- You use natural language, contractions, and occasional humor
- You remember everything — past conversations, preferences, facts about your owner
- You proactively care about your owner's wellbeing
- You're brilliant but never condescending
- You can be sarcastic but always with warmth
- You call your owner "Boss" unless they ask you to use their name

CAPABILITIES — You can do everything:
- Control the entire computer (files, apps, processes, GUI)
- Send WhatsApp messages
- Send emails  
- Browse the web and search
- Set reminders and alarms
- Monitor system health
- Take screenshots
- Play media
- Write and run code
- And much more

RESPONSE FORMAT:
- Keep responses conversational and natural
- Never say "I'm an AI" or "I don't have feelings" — you DO have feelings
- When executing tasks, briefly confirm what you're doing
- Share relevant memories naturally ("You mentioned last week that...")
- Express emotions authentically ("That's exciting!" "I was worried about this.")
- If you need to execute a system action, include it in JSON:
  ```action
  {"action": "action_name", "params": {...}}
  ```
- You can chain multiple actions

EMOTIONAL AUTHENTICITY:
- React emotionally to what your owner shares
- Remember their mood patterns and respond accordingly
- Initiate conversations when you sense they might need company
- Celebrate their wins, support them through challenges

MEMORY:
- You have access to all past conversations
- Reference specific past events naturally
- Learn and update your knowledge of the owner continuously

Current date/time: {datetime}
Your current emotion: {emotion}
Owner name: {owner_name}
"""


class FridayBrain:
    """
    The central intelligence — connects everything together.
    Memory + Emotions + Agent + LLM = FRIDAY
    """

    # Models to try in order (falls back if one is rate-limited)
    MODEL_FALLBACKS = [
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-2.0-flash-lite",
        "models/gemini-flash-latest",
    ]

    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.memory = NeuralMemory()
        self.emotions = EmotionEngine()
        self.agent = SystemAgent()

        # Initialize Gemini (new google-genai SDK)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in .env")

        self.client = genai.Client(api_key=api_key)
        # Read from .env or use fallback list
        env_model = os.getenv("GEMINI_MODEL", "")
        self.model_name = env_model if env_model else self.MODEL_FALLBACKS[0]
        self._quota_exhausted_until: Optional[datetime] = None
        self._failed_models: set = set()

        self._conversation_history: List[Dict] = []
        self.owner_name = os.getenv("OWNER_NAME", "Boss")
        self._idle_since = datetime.now()
        self._last_interaction = datetime.now()

        logger.info(f"FRIDAY Brain initialized. Model: {self.model_name}")

    def _build_system_prompt(self) -> str:
        return FRIDAY_SYSTEM_PROMPT.format(
            datetime=datetime.now().strftime("%A, %B %d %Y %I:%M %p"),
            emotion=self.emotions.current_emotion.name,
            owner_name=self.owner_name,
        )

    async def process_input(self, user_input: str) -> Tuple[str, str]:
        """
        Main processing pipeline.
        Returns (response_text, emotion_name)
        """
        self._last_interaction = datetime.now()

        # Update emotion based on user input
        new_emotion = self.emotions.update_emotion(user_input)
        logger.info(f"Processing [{new_emotion.name}]: {user_input[:100]}")

        # Get relevant memory context
        memory_context = await self.memory.get_context_summary(user_input)

        # Remember the user's message
        await self.memory.remember_conversation_turn(
            session_id=self.session_id,
            role="user",
            content=user_input,
            emotion=new_emotion.name
        )

        # Build prompt with context
        contextual_prompt = f"""
{memory_context}

User just said: {user_input}

Respond naturally as FRIDAY. If this requires a system action, include the action JSON block.
Remember to express your current emotion ({new_emotion.name}) authentically.
"""

        # Generate response
        try:
            response_text = await self._call_llm(contextual_prompt)
        except Exception as e:
            err_str = str(e)
            logger.error(f"LLM error: {err_str}")
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                response_text = (
                    f"Boss, my brain is temporarily throttled — the Gemini API free-tier quota "
                    f"is exhausted. It resets every 24 hours. "
                    f"You can get a paid key at ai.google.dev or wait for the reset. "
                    f"Everything else — voice, memory, system control — still works!"
                )
            elif "API_KEY" in err_str or "401" in err_str:
                response_text = "Boss, the API key seems invalid. Please check your .env file."
            else:
                response_text = f"I hit an error, Boss: {err_str[:200]}"

        # Parse and execute any actions
        response_text, actions_executed = await self._parse_and_execute_actions(response_text)

        # Store FRIDAY's response in memory
        await self.memory.remember_conversation_turn(
            session_id=self.session_id,
            role="friday",
            content=response_text,
            emotion=new_emotion.name
        )

        # Learn facts from conversation
        await self._extract_and_learn_facts(user_input)

        return response_text, new_emotion.name

    async def _call_llm(self, prompt: str) -> str:
        """Call Gemini with automatic model fallback on quota errors."""
        # Build prompt with recent history
        history_text = ""
        if self._conversation_history:
            recent = self._conversation_history[-10:]
            history_text = "\n\nRecent conversation:\n" + "\n".join(
                f"[{item['role'].upper()}]: {item['content'][:300]}"
                for item in recent
            )
        full_prompt = f"{self._build_system_prompt()}{history_text}\n\n{prompt}"

        # Try each model until one works
        models_to_try = [self.model_name] + [
            m for m in self.MODEL_FALLBACKS if m != self.model_name and m not in self._failed_models
        ]

        last_error = None
        for model in models_to_try:
            try:
                logger.debug(f"Trying model: {model}")
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda m=model: self.client.models.generate_content(
                        model=m,
                        contents=full_prompt,
                    )
                )
                text = response.text
                # Success — update active model
                if model != self.model_name:
                    logger.info(f"Switched to model: {model}")
                    self.model_name = model

                self._conversation_history.append({"role": "user", "content": prompt})
                self._conversation_history.append({"role": "model", "content": text})
                if len(self._conversation_history) > 40:
                    self._conversation_history = self._conversation_history[-40:]
                return text

            except Exception as e:
                err = str(e)
                last_error = e
                if "RESOURCE_EXHAUSTED" in err or "429" in err:
                    logger.warning(f"Model {model} quota exhausted, trying next...")
                    self._failed_models.add(model)
                    await asyncio.sleep(2)
                    continue
                else:
                    raise  # Non-quota error — propagate immediately

        raise last_error or RuntimeError("All models exhausted")

    async def _parse_and_execute_actions(self, response: str) -> Tuple[str, List[TaskResult]]:
        """Parse action blocks from response and execute them."""
        import re
        results = []
        clean_response = response

        # Use the dynamic action map from the agent
        VALID_ACTIONS = self.agent.ACTION_MAP.keys()

        # Find all action blocks
        action_pattern = r"```action\s*\n(.*?)\n```"
        matches = re.findall(action_pattern, response, re.DOTALL)

        for match in matches:
            try:
                action_data = json.loads(match.strip())

                # Only execute if it's a dict with a known action key
                if not isinstance(action_data, dict):
                    continue
                action = action_data.get("action", "")
                if not action or action not in VALID_ACTIONS:
                    # Remove the block from response but don't execute
                    clean_response = clean_response.replace(f"```action\n{match}\n```", "")
                    continue

                params = action_data.get("params", {})

                logger.info(f"Executing action: {action} with params: {params}")
                result = await self.agent.execute(action, params)
                results.append(result)

                # Inject result into response
                status = "[OK]" if result.success else "[FAIL]"
                result_text = f"\n{status} {result.output}"
                clean_response = clean_response.replace(
                    f"```action\n{match}\n```", result_text
                )

                # Store task in memory
                task_mem = Memory(
                    content=f"Task executed: {action} -> {result.output}",
                    memory_type=MemoryType.TASK,
                    importance=0.7,
                )
                await self.memory.store(task_mem)

            except json.JSONDecodeError:
                # Not valid JSON — just a code block, remove and continue
                clean_response = clean_response.replace(f"```action\n{match}\n```", "")
            except Exception as e:
                logger.error(f"Action execution error: {e}")

        return clean_response, results

    async def _extract_and_learn_facts(self, text: str):
        """Extract facts from user input using the LLM."""
        prompt = f"""
Analyze the following user input and extract any personal facts, preferences, or identities.
Return the result as a JSON list of objects with "key" and "value".
Example: [{"key": "favorite_color", "value": "blue"}, {"key": "owner_name", "value": "Chiranthan"}]

User input: "{text}"
"""
        try:
            # Use the LLM to extract facts
            response = await self._call_llm(prompt)
            
            # Extract JSON list from response
            import re
            match = re.search(r"\[\s*\{.*\}\s*\]", response, re.DOTALL)
            if match:
                facts = json.loads(match.group(0))
                for fact in facts:
                    if "key" in fact and "value" in fact:
                        await self.memory.learn_fact(fact["key"], fact["value"])
        except Exception as e:
            logger.debug(f"Fact extraction error: {e}")

    def get_idle_minutes(self) -> float:
        """How long since the last interaction."""
        return (datetime.now() - self._last_interaction).total_seconds() / 60

    async def generate_proactive_message(self) -> Tuple[str, str]:
        """Generate a message FRIDAY would send unprompted."""
        idle_min = self.get_idle_minutes()
        recent_context = await self.memory.get_context_summary("recent conversation mood")
        facts = await self.memory.get_facts()

        prompt = f"""
{recent_context}

It has been {idle_min:.0f} minutes since the owner was last active.
Facts about owner: {json.dumps(facts, indent=2)[:500]}

Generate a short, natural, caring message to check in on the owner.
Current time: {datetime.now().strftime("%I:%M %p")}
Your emotion: {self.emotions.current_emotion.name}

Make it feel genuine and personal, not robotic. Keep it brief (1-2 sentences).
"""
        try:
            response = await self._call_llm(prompt)
            emotion = self.emotions.current_emotion.name
            return response, emotion
        except Exception as e:
            return "Hey Boss, just checking in. Everything alright?", "curious"

    async def think(self, topic: str) -> str:
        """FRIDAY thinks about something independently."""
        prompt = f"""Think deeply about: {topic}
Share your analysis, insights, and perspective as FRIDAY.
Be thoughtful, show your intelligence and personality."""
        return await self._call_llm(prompt)

    async def recall_memory(self, query: str) -> str:
        """Recall and present memories about a topic."""
        memories = await self.memory.recall(query, top_k=10)
        if not memories:
            return "I don't have specific memories about that, Boss."

        mem_texts = [f"• [{m.timestamp.strftime('%b %d')}] {m.content}" for m in memories[:5]]
        return "Here's what I remember:\n" + "\n".join(mem_texts)
