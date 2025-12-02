#!/usr/bin/env python3
"""
Agent Runner (serverless)
- Uses `agent_tools` to access the game directly (no MCP server)
- Controls a simple perception-decision-action loop per agent
- Works with either a local simple policy or an LLM with function calling or JSON plan
"""

from __future__ import annotations

import asyncio
import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import threading
import json
import re

# Load environment variables from .env file
try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Environment variables may not be loaded from .env file.")

from agent_tools import create_tools, AgentTools, build_database_url

# Optional: OpenAI function calling interface
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False


# Optional: Anthropic (Claude) interface
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except Exception:
    ANTHROPIC_AVAILABLE = False


class LLMPolicy:
    """Thin wrapper around OpenAI or Anthropic; can return tool-calls or raw text."""

    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        openai_key = api_key or os.getenv("OPENAI_API_KEY")
        claude_key = os.getenv("CLAUDE_API_KEY")

        if openai_key and OPENAI_AVAILABLE:
            self.client = OpenAI(api_key=openai_key)
            self.api_provider = "openai"
        elif claude_key and ANTHROPIC_AVAILABLE:
            self.client = Anthropic(api_key=claude_key)
            self.api_provider = "anthropic"
        else:
            raise RuntimeError("No suitable LLM SDK or API key available. Install openai/anthropic or set OPENAI_API_KEY/CLAUDE_API_KEY.")
        
        self.model = model

    async def decide(self, system_prompt: str, user_message: str, tools_spec: Optional[List[Dict[str, Any]]] = None):
        """If tools_spec is provided: return list of tool-calls. Otherwise return response text (e.g., JSON plan)."""
        def _call_sync():
            try:
                if self.api_provider == "openai":
                    kwargs = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message},
                        ],
                        "temperature": 0.4,
                    }
                    if tools_spec:
                        kwargs["tools"] = tools_spec
                        kwargs["tool_choice"] = "auto"
                    
                    resp = self.client.chat.completions.create(**kwargs)
                    message = resp.choices[0].message
                    if tools_spec:
                        calls = []
                        if message.tool_calls:
                            for tc in message.tool_calls:
                                try:
                                    args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                                except Exception:
                                    args = {}
                                calls.append({"name": tc.function.name, "arguments": args})
                        return calls
                    else:
                        return message.content or ""

                elif self.api_provider == "anthropic":
                    kwargs = {
                        "model": self.model,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_message}],
                        "max_tokens": 1024,
                        "temperature": 0.4,
                    }
                    if tools_spec:
                        kwargs["tools"] = tools_spec
                    
                    resp = self.client.messages.create(**kwargs)
                    if tools_spec:
                        calls = []
                        for block in resp.content:
                            if block.type == 'tool_use':
                                try:
                                    args = block.input if isinstance(block.input, dict) else {}
                                except Exception:
                                    args = {}
                                calls.append({"name": block.name, "arguments": args})
                        return calls
                    else:
                        text_content = ""
                        for block in resp.content:
                            if block.type == 'text':
                                text_content += block.text
                        return text_content
                else:
                    return {"__llm_error__": "Unknown API provider"}
            except Exception as e:
                return {"__llm_error__": str(e)}
        return await asyncio.to_thread(_call_sync)


class MemoryAwareLLMPolicy:
    """LLM policy with memory management - supports OpenAI and Anthropic."""
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None, max_memory_length: int = 20, participant_code: str = "unknown", session_id: Optional[str] = None, session_code: Optional[str] = None):
        openai_key = api_key or os.getenv("OPENAI_API_KEY")
        claude_key = os.getenv("CLAUDE_API_KEY")

        if openai_key and OPENAI_AVAILABLE:
            self.client = OpenAI(api_key=openai_key)
            self.api_provider = "openai"
        elif claude_key and ANTHROPIC_AVAILABLE:
            self.client = Anthropic(api_key=claude_key)
            self.api_provider = "anthropic"
        else:
            raise RuntimeError("No suitable LLM SDK or API key available for MemoryAwareLLMPolicy.")

        self.model = model
        self.max_memory_length = max_memory_length
        self.participant_code = participant_code
        self.session_id = session_id
        self.session_code = session_code
        self.conversation_history = []
        self.system_prompt = None
        self.is_initialized = False
    
    def initialize_memory(self, system_prompt: str):
        """Initialize the agent's memory with the system prompt."""
        self.system_prompt = system_prompt
        self.conversation_history = []
        self.is_initialized = True
    
    def add_status_update(self, status_update: str):
        """Add a status update to the conversation history."""
        if not self.is_initialized:
            raise RuntimeError("Memory not initialized. Call initialize_memory() first.")
        
        self.conversation_history.append({
            "role": "user",
            "content": f"STATUS UPDATE:\n{status_update}"
        })
        
        # Trim history if it gets too long
        if len(self.conversation_history) > self.max_memory_length:
            # Keep the most recent messages
            self.conversation_history = self.conversation_history[-self.max_memory_length:]
    
    def add_agent_response(self, response_content: str):
        """Add the agent's response to the conversation history."""
        if not self.is_initialized:
            raise RuntimeError("Memory not initialized. Call initialize_memory() first.")
        
        self.conversation_history.append({
            "role": "assistant",
            "content": response_content
        })
    
    def get_memory_summary(self) -> str:
        """Get a summary of the agent's memory for debugging."""
        if not self.is_initialized:
            return "Memory not initialized"
        
        summary = f"Memory initialized: {self.is_initialized}\n"
        summary += f"Conversation history length: {len(self.conversation_history)}\n"
        summary += f"Max memory length: {self.max_memory_length}\n"
        
        if self.conversation_history:
            summary += "Recent messages:\n"
            for i, msg in enumerate(self.conversation_history[-5:]):  # Last 5 messages
                role = msg["role"]
                content_preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                summary += f"  {i+1}. {role}: {content_preview}\n"
        
        return summary
    
    def _log_llm(self, header: str, content: str):
        """Log LLM interactions to the LLM log file."""
        try:
            # Create logs directory if it doesn't exist
            # Use session_code if available, otherwise fall back to session_id
            session_identifier = self.session_code or self.session_id or "unknown"
            logs_base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", session_identifier)
            os.makedirs(logs_base_dir, exist_ok=True)
            
            llm_log_path = os.path.join(logs_base_dir, f"llm_{self.participant_code}.log")
            
            
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(llm_log_path, "a", encoding="utf-8") as f:
                f.write(f"\n==== {ts} | {header} ====" + "\n")
                f.write(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False))
                f.write("\n")
            
        except Exception as e:
            print(f"[LLM] {self.participant_code} log write failed: {e}")
    
    async def decide(self, tools_spec: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Make a decision based on the current conversation history using JSON format."""
        if not self.is_initialized:
            raise RuntimeError("Memory not initialized. Call initialize_memory() first.")
        
        def _call_sync():
            # Build messages array with system prompt and conversation history
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_history)
            
            # Log the request to LLM log
            self._log_llm("MEMORY_LLM_REQUEST", json.dumps({
                "model": self.model,
                "messages": messages,
                "temperature": 0.4
            }, ensure_ascii=False, indent=2))
            
            try:
                if self.api_provider == "openai":
                    kwargs = {
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.4,
                    }
                    resp = self.client.chat.completions.create(**kwargs)
                    response_content = resp.choices[0].message.content or ""
                elif self.api_provider == "anthropic":
                    # Anthropic separates system prompt from messages
                    anthropic_messages = [msg for msg in messages if msg['role'] != 'system']
                    kwargs = {
                        "model": self.model,
                        "system": self.system_prompt,
                        "messages": anthropic_messages,
                        "max_tokens": 1024,
                        "temperature": 0.4,
                    }
                    resp = self.client.messages.create(**kwargs)
                    response_content = ""
                    for block in resp.content:
                        if block.type == 'text':
                            response_content += block.text
                else:
                    raise RuntimeError("Unknown API provider")

                # Log the response to LLM log
                try:
                    # Try to parse the JSON response for better logging
                    if response_content.strip().startswith('{'):
                        parsed_response = json.loads(response_content)
                        self._log_llm("MEMORY_LLM_RESPONSE", json.dumps({
                            "content": parsed_response
                        }, ensure_ascii=False, indent=2))
                    else:
                        self._log_llm("MEMORY_LLM_RESPONSE", json.dumps({
                            "content": response_content
                        }, ensure_ascii=False, indent=2))
                except json.JSONDecodeError:
                    # If JSON parsing fails, log as raw content
                    self._log_llm("MEMORY_LLM_RESPONSE", json.dumps({
                        "content": response_content
                    }, ensure_ascii=False, indent=2))
                
                # Add the assistant's response to memory
                # Note: response_content is already set correctly above from the API response
                if response_content:
                    self.add_agent_response(response_content)
                
                # Parse JSON response and convert to tool calls
                if response_content:
                    # Extract JSON from the response
                    json_block = self._extract_json_block(response_content)
                    if json_block:
                        try:
                            plan = json.loads(json_block)
                            # Convert JSON plan to tool calls using the existing mapping logic
                            # We'll need to pass the public state to this method
                            # For now, return the raw JSON response and let the controller handle it
                            return response_content
                        except json.JSONDecodeError:
                            # If JSON parsing fails, return the raw response
                            return response_content
                    else:
                        # No JSON block found, return raw response
                        return response_content
                else:
                    return ""
                    
            except Exception as e:
                error_msg = f"LLM Error: {str(e)}"
                self.add_agent_response(error_msg)
                return {"__llm_error__": str(e)}
        
        return await asyncio.to_thread(_call_sync)
    
    def _extract_json_block(self, text: str) -> Optional[str]:
        """Extract JSON block from text response."""
        if not text:
            return None
        # Prefer fenced ```json blocks
        fenced = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
        if fenced:
            return fenced.group(1)
        # Any fenced block
        fenced_any = re.search(r"```\s*(\{[\s\S]*?\})\s*```", text)
        if fenced_any:
            return fenced_any.group(1)
        # Bracket-matching extraction for first complete JSON object
        start = text.find('{')
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i+1]
        return None
    
    def clear_memory(self):
        """Clear the conversation history."""
        self.conversation_history = []
    
    def save_memory_to_file(self, filepath: str):
        """Save the current memory to a file for debugging."""
        if not self.is_initialized:
            return
        
        memory_data = {
            "system_prompt": self.system_prompt,
            "conversation_history": self.conversation_history,
            "max_memory_length": self.max_memory_length,
            "current_length": len(self.conversation_history),
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(memory_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save memory to {filepath}: {e}")
    
    def load_memory_from_file(self, filepath: str):
        """Load memory from a file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                memory_data = json.load(f)
            
            self.system_prompt = memory_data.get("system_prompt")
            self.conversation_history = memory_data.get("conversation_history", [])
            self.max_memory_length = memory_data.get("max_memory_length", 20)
            self.is_initialized = True
            
        except Exception as e:
            print(f"Failed to load memory from {filepath}: {e}")
    



PERSONALITY_PROFILES: Dict[str, Dict[str, str]] = {
    "basic_agent": {
        "name": "Cooporative Trader",
        "description": "standard trading agent with balanced behavior",
        "behavior": "Make reasonable trades, communicate effectively, fulfill orders efficiently",
        "communication": "Clear, helpful, and cooperative"
    },
}

# MBTI Personality Profiles for agents
MBTI_PROFILES: Dict[str, Dict[str, str]] = {
    "INTJ": {
        "name": "Strategic Architect",
        "description": "Analytical and strategic thinker who plans carefully and values efficiency",
        "behavior": "Plan long-term strategies, analyze market conditions, optimize for maximum efficiency",
        "communication": "Direct, analytical, and focused on facts and logic"
    },
    "INTP": {
        "name": "Innovative Thinker",
        "description": "Creative problem solver who enjoys exploring new trading strategies",
        "behavior": "Experiment with different approaches, think outside the box, adapt to changing conditions",
        "communication": "Thoughtful, curious, and enjoys discussing complex ideas"
    },
    "ENTJ": {
        "name": "Bold Commander",
        "description": "Natural leader who takes charge and makes decisive trading decisions",
        "behavior": "Take initiative, lead negotiations, make bold strategic moves",
        "communication": "Confident, assertive, and direct in expressing goals"
    },
    "ENTP": {
        "name": "Clever Strategist",
        "description": "Quick-witted and adaptable trader who thrives on dynamic market conditions",
        "behavior": "Adapt quickly to changes, find creative solutions, take calculated risks",
        "communication": "Enthusiastic, persuasive, and enjoys intellectual debates"
    },
    "INFJ": {
        "name": "Empathetic Negotiator",
        "description": "Insightful and caring trader who builds strong relationships",
        "behavior": "Build trust with others, consider long-term relationships, seek win-win solutions",
        "communication": "Warm, understanding, and focused on mutual benefit"
    },
    "INFP": {
        "name": "Idealistic Trader",
        "description": "Values-driven trader who prioritizes fairness and cooperation",
        "behavior": "Seek fair deals, avoid aggressive tactics, prioritize ethical trading",
        "communication": "Gentle, idealistic, and focused on creating positive relationships"
    },
    "ENFJ": {
        "name": "Charismatic Leader",
        "description": "Inspiring and supportive trader who motivates others to cooperate",
        "behavior": "Inspire cooperation, build alliances, create supportive trading networks",
        "communication": "Encouraging, diplomatic, and skilled at bringing people together"
    },
    "ENFP": {
        "name": "Enthusiastic Collaborator",
        "description": "Energetic and creative trader who brings excitement to negotiations",
        "behavior": "Generate enthusiasm for deals, think creatively, adapt to others' needs",
        "communication": "Energetic, optimistic, and skilled at building rapport"
    }
}

def assign_random_mbti() -> str:
    """Randomly assign one of the 8 MBTI personality types to an agent."""
    mbti_types = list(MBTI_PROFILES.keys())
    return random.choice(mbti_types)


class SimplePolicy:
    """Deterministic, non-LLM policy producing straightforward actions."""

    def decide(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        private_state = state.get("game_state", {}).get("private_state", {})
        public_state = state.get("game_state", {}).get("public_state", {})
        specialty = private_state.get("specialty_shape", "circle")
        money = int(private_state.get("money", 0) or 0)
        
        # Get configuration parameters
        experiment_config = public_state.get("experiment_config", {})
        starting_money = experiment_config.get("startingMoney", 300)
        min_trade_price = experiment_config.get("minTradePrice", 15)
        max_trade_price = experiment_config.get("maxTradePrice", 35)
        
        # Get communication level from state
        communication_level = state.get("communication_level", "chat")

        calls: List[Dict[str, Any]] = []
        # Produce if we have some money (use starting money as threshold)
        if money >= starting_money * 0.1 and random.random() < 0.8:  # 10% of starting money
            calls.append({
                "name": "produce_shape",
                "arguments": {"shape": specialty, "quantity": 1},
            })
        
        # Send messages based on communication level
        # Note: Removed generic "Hello! Ready to trade" messages to prevent unwanted communication
        if communication_level == "no_chat":
            # No messages in no_chat mode
            pass
        elif communication_level == "broadcast":
            # Only broadcast messages in broadcast mode - but no generic messages
            pass
        else:  # chat mode
            # In chat mode, send to specific participants only - but no generic messages
            pass
        
        return calls


class AgentController:
    def __init__(self, participant_code: str, use_llm: bool = False, llm_model: str = "gpt-4o-mini",
                 interval_seconds: int = 10, duration_minutes: int = 15, 
                 stop_event: Optional[threading.Event] = None, personality: str = "basic_agent",
                 use_memory: bool = True, max_memory_length: int = 20, session_code: str = None,
                 experiment_type: str = "shapefactory"):
        print(f"[INIT] AgentController for {participant_code} starting...")
        print(f"[INIT] use_llm={use_llm}, llm_model={llm_model}, personality={personality}, use_memory={use_memory}")
        
        
        self.participant_code = participant_code
        self.use_llm = use_llm
        self.llm_model = llm_model
        self.interval_seconds = interval_seconds
        self.duration_minutes = duration_minutes
        self._stop_event = stop_event or threading.Event()
        self.personality = personality
        self.use_memory = use_memory
        self.max_memory_length = max_memory_length
        self.session_code = session_code
        # Normalize and store experiment type (default to shapefactory)
        self.experiment_type = (experiment_type or "shapefactory").strip().lower()
        print(f"[INIT] AgentController experiment_type: {self.experiment_type}")
        
        # Track recent failed actions to provide feedback to agents
        self.recent_failures = []  # List of recent failure records
        self.max_failure_history = 10  # Keep last 10 failures
        
        # Get session_id for this participant
        self.session_id = self._get_session_id()
        print(f"[INIT] Session ID: {self.session_id}")
        
        # Ensure logs directory exists (and use session-based subfolders when available)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(base_dir, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        # If session_code or session_id is available, write logs under logs/<session_identifier>/
        session_identifier = self.session_code or self.session_id
        if session_identifier:
            session_dir = os.path.join(logs_dir, session_identifier)
            os.makedirs(session_dir, exist_ok=True)
            logs_base_dir = session_dir
        else:
            logs_base_dir = logs_dir
        print(f"[INIT] Logs directory: {logs_base_dir}")
        
        # Set up logging paths. With session-based folders, filenames do not include session suffix
        # Fallback (no session): write to logs/ with filenames without suffix
        self._log_path = os.path.join(logs_base_dir, f"agent_{participant_code}.log")
        self._llm_log_path = os.path.join(logs_base_dir, f"llm_{participant_code}.log")
        self._memory_log_path = os.path.join(logs_base_dir, f"memory_{participant_code}.log")
        print(f"[INIT] Agent log: {self._log_path}")
        print(f"[INIT] LLM log: {self._llm_log_path}")
        print(f"[INIT] Memory log: {self._memory_log_path}")
        
        # Create/clear log files
        try:
            session_info = f"{self.session_code} ({self.session_id})" if self.session_code and self.session_id else (self.session_code or self.session_id or "unknown")
            with open(self._log_path, "w") as f:
                f.write(f"Agent {participant_code} (session: {session_info}) initialized at {datetime.now()}\n")
            with open(self._llm_log_path, "w") as f:
                f.write(f"LLM log for {participant_code} (session: {session_info}) initialized at {datetime.now()}\n")
            with open(self._memory_log_path, "w") as f:
                f.write(f"Memory log for {participant_code} (session: {session_info}) initialized at {datetime.now()}\n")
            print(f"[INIT] Log files created successfully")
        except Exception as e:
            print(f"[INIT ERROR] Failed to create log files: {e}")
        
        # Initialize tools
        print(f"[INIT] Initializing AgentTools...")
        self.tools = AgentTools()
        print(f"[INIT] AgentTools initialized")
        
        # Check if this is a passive agent (for Hidden Profiles)
        self.is_passive = False
        if self.experiment_type == "hiddenprofiles":
            try:
                import psycopg2
                import psycopg2.extras
                import json
                
                db_url = self.tools._engine.db_connection_string
                conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
                cur = conn.cursor()
                
                if session_code:
                    cur.execute("""
                        SELECT experiment_config FROM sessions WHERE session_code = %s
                    """, (session_code,))
                else:
                    cur.execute("""
                        SELECT s.experiment_config FROM sessions s
                        JOIN participants p ON s.session_id = p.session_id
                        WHERE p.participant_code = %s
                        ORDER BY p.last_activity_timestamp DESC NULLS LAST, p.created_at DESC
                        LIMIT 1
                    """, (participant_code,))
                
                result = cur.fetchone()
                cur.close()
                conn.close()
                
                if result:
                    experiment_config = result['experiment_config'] or {}
                    if isinstance(experiment_config, str):
                        experiment_config = json.loads(experiment_config)
                    hidden_profiles_config = experiment_config.get('hiddenProfiles', {})
                    participant_initiatives = hidden_profiles_config.get('participantInitiatives', {})
                    
                    # Try to get initiative - check both with and without session suffix
                    initiative = participant_initiatives.get(participant_code)
                    if not initiative:
                        # Try without session suffix (e.g., "Bob" instead of "Bob_test1")
                        base_code = participant_code.rsplit('_', 1)[0] if '_' in participant_code else participant_code
                        initiative = participant_initiatives.get(base_code)
                    
                    # Default to 'active' if not found
                    if not initiative:
                        initiative = 'active'
                    
                    self.is_passive = (initiative == 'passive')
                    print(f"[INIT] Agent {participant_code} initiative: {initiative} (is_passive={self.is_passive})")
                    print(f"[INIT] Available initiatives in config: {participant_initiatives}")
            except Exception as e:
                print(f"[INIT WARNING] Could not determine initiative for {participant_code}: {e}")
                self.is_passive = False
        
        # Initialize policy
        print(f"[INIT] Initializing policy (use_llm={use_llm}, use_memory={use_memory})...")
        if use_llm:
            openai_key = os.getenv("OPENAI_API_KEY")
            claude_key = os.getenv("CLAUDE_API_KEY")
            
            if not openai_key and not claude_key:
                print(f"[INIT WARNING] Neither OPENAI_API_KEY nor CLAUDE_API_KEY are set - LLM will fail!")
            elif openai_key:
                print(f"[INIT] OPENAI_API_KEY found: {openai_key[:10]}...{openai_key[-4:]}")
            elif claude_key:
                print(f"[INIT] CLAUDE_API_KEY found.")

            if use_memory:
                print(f"[INIT] Using MemoryAwareLLMPolicy with max_memory_length={max_memory_length}")
                self.policy = MemoryAwareLLMPolicy(model=llm_model, max_memory_length=max_memory_length, participant_code=self.participant_code, session_id=self.session_id, session_code=self.session_code)
            else:
                print(f"[INIT] Using standard LLMPolicy")
                self.policy = LLMPolicy(model=llm_model)
        else:
            self.policy = SimplePolicy()
        print(f"[INIT] Policy initialized: {type(self.policy).__name__}")
        
        # Determine LLM mode
        self.llm_mode = os.getenv("AGENT_LLM_MODE", "function").lower()
        print(f"[INIT] LLM mode: {self.llm_mode}")
        
        print(f"[INIT] AgentController for {participant_code} fully initialized")
        print(f"[INIT] use_llm={self.use_llm} use_memory={self.use_memory} mode={self.llm_mode} log={self._llm_log_path}")

    def _get_session_id(self) -> Optional[str]:
        """Get the session_id for this participant"""
        try:
            import psycopg2
            import psycopg2.extras
            
            db_url = self.tools._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            if self.session_code:
                # Use session_code for more precise lookup
                cur.execute("""
                    SELECT p.session_id FROM participants p
                    JOIN sessions s ON p.session_id = s.session_id
                    WHERE p.participant_code = %s AND s.session_code = %s
                    LIMIT 1
                """, (self.participant_code, self.session_code))
            else:
                # Fallback to the original behavior if no session_code provided
                # But order by activity to get the most recent/active session
                cur.execute("""
                    SELECT session_id FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (self.participant_code,))
            
            result = cur.fetchone()
            
            session_id = result['session_id'] if result else None
            cur.close()
            conn.close()
            
            return session_id
            
        except Exception as e:
            print(f"Warning: Could not get session_id for {self.participant_code}: {e}")
            return None

    def _record_failure(self, action_name: str, arguments: Dict[str, Any], error_message: str):
        """Record a failed action for feedback to the agent."""
        failure_record = {
            'action': action_name,
            'arguments': arguments.copy(),
            'error': error_message,
            'timestamp': datetime.now().isoformat(),
            'cycle': getattr(self, '_current_cycle', 0)
        }
        
        self.recent_failures.append(failure_record)
        
        # Keep only the most recent failures
        if len(self.recent_failures) > self.max_failure_history:
            self.recent_failures = self.recent_failures[-self.max_failure_history:]
        
        self._log(f"Recorded failure: {action_name} - {error_message}")

    def _get_failure_summary(self) -> str:
        """Get a formatted summary of recent failures for the agent."""
        if not self.recent_failures:
            return "No recent failures"
        
        summary_lines = ["RECENT FAILED ACTIONS:"]
        
        for failure in self.recent_failures[-5:]:  # Show last 5 failures
            action = failure['action']
            error = failure['error']
            args = failure['arguments']
            
            # Create a readable summary based on action type
            if action == "respond_to_trade_offer":
                transaction_id = args.get('transaction_id', 'unknown')
                response = args.get('response', 'unknown')
                summary_lines.append(f"- TRADE RESPONSE FAILED: Transaction {transaction_id} ({response}) - {error}")
            elif action == "create_trade_offer":
                recipient = args.get('recipient', 'unknown')
                shape = args.get('shape', 'unknown')
                offer_type = args.get('offer_type', 'unknown')
                summary_lines.append(f"- TRADE OFFER FAILED: {offer_type} {shape} to {recipient} - {error}")
            elif action == "send_message":
                recipient = args.get('recipient', 'unknown')
                summary_lines.append(f"- MESSAGE FAILED: to {recipient} - {error}")
            elif action == "fulfill_orders":
                order_indices = args.get('order_indices', [])
                summary_lines.append(f"- ORDER FULFILLMENT FAILED: orders {order_indices} - {error}")
            elif action == "produce_shape":
                shape = args.get('shape', 'unknown')
                quantity = args.get('quantity', 1)
                summary_lines.append(f"- PRODUCTION FAILED: {quantity}x {shape} - {error}")
            else:
                summary_lines.append(f"- {action.upper()} FAILED: {error}")
        
        failure_summary = "\n".join(summary_lines)
        
        # Add failure summary to memory for MemoryAwareLLMPolicy
        if isinstance(self.policy, MemoryAwareLLMPolicy) and self.recent_failures:
            self.policy.add_agent_response(failure_summary)
            self._log_memory("FAILURE_SUMMARY", failure_summary)
        
        return failure_summary

    def _log(self, msg: str):
        """Write agent activity to log file"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._log_path, "a") as f:
                f.write(f"[{timestamp}] {msg}\n")
        except Exception as e:
            print(f"[LOG ERROR] {self.participant_code}: {e}")

    def _log_llm(self, header: str, content: str):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._llm_log_path, "a", encoding="utf-8") as f:
                f.write(f"\n==== {ts} | {header} ====" + "\n")
                f.write(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False))
                f.write("\n")
        except Exception as e:
            print(f"[LLM] {self.participant_code} log write failed: {e}")

    def _log_memory(self, header: str, content: str):
        """Write memory-related activity to memory log file"""
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._memory_log_path, "a", encoding="utf-8") as f:
                f.write(f"\n==== {ts} | {header} ====" + "\n")
                f.write(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False))
                f.write("\n")
        except Exception as e:
            print(f"[MEMORY] {self.participant_code} log write failed: {e}")

    def _load_prompt_template(self) -> str:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Map experiment types to prompt files
        prompts_dir = os.path.join(base_dir, "prompts")
        
        # For wordguessing, we need to load role-specific prompts
        if self.experiment_type == "wordguessing":
            # Get participant role from database
            try:
                import psycopg2
                import psycopg2.extras
                
                db_url = self.tools._engine.db_connection_string
                conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
                cur = conn.cursor()
                
                # Get participant role
                cur.execute("""
                    SELECT role FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (self.participant_code,))
                
                result = cur.fetchone()
                cur.close()
                conn.close()
                
                if result and result['role']:
                    role = result['role']
                    # Load role-specific prompt
                    if role == "hinter":
                        candidate = os.path.join(prompts_dir, "wordguessing_hinter_prompt.txt")
                    elif role == "guesser":
                        candidate = os.path.join(prompts_dir, "wordguessing_guesser_prompt.txt")
                    else:
                        # Fallback to hinter prompt if role is unknown
                        candidate = os.path.join(prompts_dir, "wordguessing_hinter_prompt.txt")
                else:
                    # Fallback to hinter prompt if role not found
                    candidate = os.path.join(prompts_dir, "wordguessing_hinter_prompt.txt")
                    
            except Exception as e:
                print(f"[WARNING] {self.participant_code} Failed to get role for wordguessing prompt: {e}")
                # Fallback to hinter prompt
                candidate = os.path.join(prompts_dir, "wordguessing_hinter_prompt.txt")
        else:
            # For other experiment types, use the standard mapping
            exp_map = {
                "shapefactory": os.path.join(prompts_dir, "shapefactory_agent_prompt.txt"),
                "daytrader": os.path.join(prompts_dir, "daytrader_agent_prompt.txt"),
                "essayranking": os.path.join(prompts_dir, "essayranking_agent_prompt.txt"),
            }
            candidate = exp_map.get(self.experiment_type, exp_map["shapefactory"])
        
        # Fallback chain: specific -> shapefactory -> local default file
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                content = f.read()
                if content and content.strip():
                    return content
        except Exception:
            pass
        # Fallback to shapefactory prompt
        try:
            with open(exp_map["shapefactory"], "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            # Final fallback to legacy local prompt (if exists)
            legacy = os.path.join(base_dir, "agent_decision_prompt.txt")
            with open(legacy, "r", encoding="utf-8") as f:
                return f.read()

    def _load_agent_decision_prompt_template(self) -> str:
        """Load the agent decision prompt template for current experiment type with safe fallback"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompts_dir = os.path.join(base_dir, "prompts")
        
        # For wordguessing, we need to load role-specific prompts (same logic as _load_prompt_template)
        if self.experiment_type == "wordguessing":
            # Get participant role from database
            try:
                import psycopg2
                import psycopg2.extras
                
                db_url = self.tools._engine.db_connection_string
                conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
                cur = conn.cursor()
                
                # Get participant role
                cur.execute("""
                    SELECT role FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (self.participant_code,))
                
                result = cur.fetchone()
                cur.close()
                conn.close()
                
                if result and result['role']:
                    role = result['role']
                    # Load role-specific prompt
                    if role == "hinter":
                        candidate = os.path.join(prompts_dir, "wordguessing_hinter_prompt.txt")
                    elif role == "guesser":
                        candidate = os.path.join(prompts_dir, "wordguessing_guesser_prompt.txt")
                    else:
                        # Fallback to hinter prompt if role is unknown
                        candidate = os.path.join(prompts_dir, "wordguessing_hinter_prompt.txt")
                else:
                    # Fallback to hinter prompt if role not found
                    candidate = os.path.join(prompts_dir, "wordguessing_hinter_prompt.txt")
                    
            except Exception as e:
                print(f"[WARNING] {self.participant_code} Failed to get role for wordguessing prompt: {e}")
                # Fallback to hinter prompt
                candidate = os.path.join(prompts_dir, "wordguessing_hinter_prompt.txt")
        else:
            # For other experiment types, use the standard mapping
            exp_map = {
                "shapefactory": os.path.join(prompts_dir, "shapefactory_agent_prompt.txt"),
                "daytrader": os.path.join(prompts_dir, "daytrader_agent_prompt.txt"),
                "essayranking": os.path.join(prompts_dir, "essayranking_agent_prompt.txt"),
                "hiddenprofiles": os.path.join(prompts_dir, "hiddenprofiles_agent_prompt.txt"),
            }
            candidate = exp_map.get(self.experiment_type, exp_map["shapefactory"])
        
        # Try to load the candidate file
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                content = f.read()
                if content and content.strip():
                    return content
        except Exception:
            pass
        
        # Fallback to shapefactory prompt
        try:
            with open(exp_map["shapefactory"], "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            # Final fallback to legacy local prompt (if exists)
            legacy = os.path.join(base_dir, "agent_decision_prompt.txt")
            with open(legacy, "r", encoding="utf-8") as f:
                return f.read()

    def _format_participants(self, public_state: Dict[str, Any]) -> str:
        """Format participants list with awareness dashboard configuration"""
        # Try other_participants first, then fall back to participants (for hiddenprofiles)
        others = public_state.get("other_participants", []) or []
        if not others:
            # Fallback for hiddenprofiles which uses "participants"
            others = public_state.get("participants", []) or []
        
        if not others:
            return "(none)"
        
        # Handle wordguessing experiments differently
        if self.experiment_type == "wordguessing":
            lines = []
            for p in others:
                pid = p.get("participant_id") or p.get("id") or p.get("participant_code") or "unknown"
                role = p.get("role", "unknown")
                score = p.get("score", 0)
                status = p.get("status", "unknown")
                
                # Format: Alice: role=guesser, score=0, status=active
                lines.append(f"- {pid}: role={role}, score={score}, status={status}")
            return "\n".join(lines)
        
        # Get awareness dashboard configuration from experiment config
        awareness_config = public_state.get("experiment_config", {}).get("awarenessDashboardConfig", {})
        show_money = awareness_config.get("showMoney", True)
        show_production = awareness_config.get("showProductionCount", True)
        show_orders = awareness_config.get("showOrderProgress", True)
        
        # Do not show money for Hidden Profiles and Word Guessing (they don't have money)
        if self.experiment_type in ["hiddenprofiles", "wordguessing"]:
            show_money = False
        
        lines = []
        for p in others:
            pid = p.get("participant_id") or p.get("id") or p.get("participant_code") or "unknown"
            
            # Build participant info based on awareness dashboard settings
            info_parts = []
            
            # Always show basic participant ID
            info_parts.append(pid)
            
            # Add money if enabled (and not Hidden Profiles/Word Guessing)
            if show_money:
                money = p.get("money", 300)
                info_parts.append(f"money: ${money}")
            
            # Add production count if enabled (only for ShapeFactory)
            if show_production and self.experiment_type == "shapefactory":
                specialty_production_used = p.get("specialty_production_used", 0)
                max_production_num = public_state.get("experiment_config", {}).get("maxProductionNum", 6)
                info_parts.append(f"production: {specialty_production_used}/{max_production_num}")
            
            # Add order progress if enabled (only for ShapeFactory)
            if show_orders and self.experiment_type == "shapefactory":
                orders_completed = p.get("orders_completed", 0)
                total_orders = p.get("total_orders", 0)
                completion_percentage = p.get("completion_percentage", 0)
                info_parts.append(f"orders: {orders_completed}/{total_orders} ({completion_percentage}%)")
            
            # Add specialty shape for ShapeFactory
            if self.experiment_type == "shapefactory":
                shape = p.get("shape", "?")
                info_parts.append(f"specialty: {shape}")
            
            # Join all info parts
            if len(info_parts) > 1:
                lines.append(f"- {info_parts[0]}: {', '.join(info_parts[1:])}")
            else:
                lines.append(f"- {info_parts[0]}")
        
        return "\n".join(lines)

    def _modify_prompt_for_communication_level(self, prompt: str, communication_level: str) -> str:
        """Modify the prompt based on the communication level"""
        if communication_level == "no_chat":
            # Remove all message-related sections from the prompt
            # Remove the message action type from the JSON example
            message_action_pattern = r'        {{\n            "type": "message",\n            "recipient": "[^"]*",\n            "content": "Your message content",\n            "message_type": "chat"\n        }},?\n?'
            prompt = re.sub(message_action_pattern, '', prompt)
            
            # Also try a simpler approach - just remove the entire message block
            lines = prompt.split('\n')
            new_lines = []
            skip_message_block = False
            
            for line in lines:
                if '"type": "message"' in line:
                    skip_message_block = True
                    continue
                elif skip_message_block and line.strip().startswith('{{'):
                    # Found the start of the next action block, stop skipping
                    skip_message_block = False
                    new_lines.append(line)
                elif skip_message_block and line.strip() == '},':
                    # Found the end of the message block, stop skipping
                    skip_message_block = False
                    continue
                elif skip_message_block:
                    # Skip this line (part of message block)
                    continue
                else:
                    new_lines.append(line)
            
            prompt = '\n'.join(new_lines)
            
            # Update the communication mode section
            prompt = prompt.replace(
                'COMMUNICATION MODE: {communication_level}',
                'COMMUNICATION MODE: NO CHAT - MESSAGING DISABLED'
            )
            prompt = prompt.replace(
                'IMPORTANT: Your communication behavior must adapt to the current mode:\n- CHAT MODE: You can send direct messages to specific participants ONLY. You CANNOT send messages to "all" in chat mode.\n- BROADCAST MODE: You can ONLY send messages to "all" (public broadcast). Direct messaging is disabled.\n- NO CHAT MODE: You CANNOT send any messages. Focus only on trading and production.',
                'IMPORTANT: MESSAGING IS DISABLED. You CANNOT send any messages. Focus only on trading and production.'
            )
            
        elif communication_level == "broadcast":
            # Update the communication mode section for broadcast
            prompt = prompt.replace(
                'COMMUNICATION MODE: {communication_level}',
                'COMMUNICATION MODE: BROADCAST ONLY'
            )
            prompt = prompt.replace(
                'IMPORTANT: Your communication behavior must adapt to the current mode:\n- CHAT MODE: You can send direct messages to specific participants ONLY. You CANNOT send messages to "all" in chat mode.\n- BROADCAST MODE: You can ONLY send messages to "all" (public broadcast). Direct messaging is disabled.\n- NO CHAT MODE: You CANNOT send any messages. Focus only on trading and production.',
                'IMPORTANT: BROADCAST MODE ONLY. You can ONLY send messages to "all" (public broadcast). Direct messaging to specific participants is disabled.'
            )
            # Update the message action example
            prompt = prompt.replace(
                '"recipient": "participant_code"',
                '"recipient": "all"'
            )
            
        elif communication_level == "chat":
            # Update the communication mode section for chat
            prompt = prompt.replace(
                'COMMUNICATION MODE: {communication_level}',
                'COMMUNICATION MODE: DIRECT CHAT'
            )
            prompt = prompt.replace(
                'IMPORTANT: Your communication behavior must adapt to the current mode:\n- CHAT MODE: You can send direct messages to specific participants ONLY. You CANNOT send messages to "all" in chat mode.\n- BROADCAST MODE: You can ONLY send messages to "all" (public broadcast). Direct messaging is disabled.\n- NO CHAT MODE: You CANNOT send any messages. Focus only on trading and production.',
                'IMPORTANT: DIRECT CHAT MODE. You can send direct messages to specific participants ONLY. You CANNOT send messages to "all" in chat mode.'
            )
        
        return prompt

    def _modify_agent_decision_prompt_for_communication_level(self, prompt: str, communication_level: str) -> str:
        """Modify the agent decision prompt based on the communication level"""
        if communication_level == "no_chat":
            # Remove message action from the JSON example
            lines = prompt.split('\n')
            new_lines = []
            skip_message_block = False
            
            for line in lines:
                if '"type": "message"' in line:
                    skip_message_block = True
                    continue
                elif skip_message_block and line.strip().startswith('{{'):
                    # Found the start of the next action block, stop skipping
                    skip_message_block = False
                    new_lines.append(line)
                elif skip_message_block and line.strip() == '},':
                    # Found the end of the message block, stop skipping
                    skip_message_block = False
                    continue
                elif skip_message_block:
                    # Skip this line (part of message block)
                    continue
                else:
                    new_lines.append(line)
            
            prompt = '\n'.join(new_lines)
            
            # Update the communication level section
            prompt = prompt.replace(
                '- Communication Level: {communication_level}',
                '- Communication Level: NO CHAT - MESSAGING DISABLED'
            )
            
            # Remove message from action spaces
            if self.experiment_type == "daytrader":
                prompt = prompt.replace(
                    '- message: Communicate or discuss investment strategies with others.\n',
                    ''
                )
            else:
                prompt = prompt.replace(
                    '- message — Negotiate with others.\n',
                    ''
                )
            # Renumber the remaining actions
            
            # Remove all chat-related instructions from the human behaviors section
            if self.experiment_type == "daytrader":
                chat_related_instructions = [
                    '- While communicating with other participants, please do not use complex vocabulary, and do not respond identically. Even for the same inquiry, always try to adjust the narrative slightly.',
                    '- Chat with other participants casually (e.g., chit-chat style), just like how people send messages to friends. Never use formal language. You could use SMS language or textese to make the conversation more informal communication styles. Don\'t use emoji.',
                    '- Pay attention to the new messages you received, and do not forget to respond to others\' messages. When responding, treat the conversation as a *continuous* communication with other participants, just like how you talk to them face-to-face. There\'s no need to greet or say hey every time.',
                    '- Consider discussing investment strategies with others, but remember that you are competing to maximize your own returns.'
                ]
            else:
                chat_related_instructions = [
                    '- Do not use complex vocabulary while communicating with other participants.',
                    '- Chat with other participants casually (e.g., chit-chat style), just like how people send messages to friends. Never use formal language. You could use SMS language or textese to make the conversation more informal communication styles. Don\'t use emoji. Use diverse ways of messaging.',
                    '- Pay attention to the new messages you received, and do not forget to respond to others\' messages. When responding, treat the conversation as a *continuous* communication with other participants, just like how you talk to them face-to-face. There\'s no need to greet or say hey every time.',
                    '- Check if the offer price matches the recent chat agreement. Only accept the offer when the prices are consistent with your best interest, otherwise you need to renegotiate through messaging.'
                ]
            
            for instruction in chat_related_instructions:
                prompt = prompt.replace(instruction, '')
            
            # Clean up any double newlines that might result from removals
            prompt = re.sub(r'\n\s*\n\s*\n', '\n\n', prompt)
            
        elif communication_level == "broadcast":
            # Update the communication level section for broadcast
            prompt = prompt.replace(
                '- Communication Level: {communication_level}',
                '- Communication Level: BROADCAST ONLY'
            )
            # Update the message action example
            prompt = prompt.replace(
                '"recipient": $"participant_code"$',
                '"recipient": "all"'
            )
            
            # Add broadcast-specific rule to the human behaviors section
            if self.experiment_type == "daytrader":
                prompt = prompt.replace(
                    '- Pay attention to the new messages you received, and do not forget to respond to others\' messages. When responding, treat the conversation as a *continuous* communication with other participants, just like how you talk to them face-to-face. There\'s no need to greet or say hey every time.',
                    '- Mimic the style of a group chat. You don\'t need to speak all the time. Only join in the chat when you have something to say about investment strategies or when someone responds to you.')
            else:
                prompt = prompt.replace(
                    '- Pay attention to the new messages you received, and do not forget to respond to others\' messages. When responding, treat the conversation as a *continuous* communication with other participants, just like how you talk to them face-to-face. There\'s no need to greet or say hey every time.',
                    '- Mimic the style of a group chat. You don\'t need to speak all the time. Only join in the chat when you have something to say or when someone responds to you.')
            
        elif communication_level == "chat":
            # Update the communication level section for chat
            prompt = prompt.replace(
                '- Communication Level: {communication_level}',
                '- Communication Level: DIRECT CHAT'
            )
        
        return prompt

    def _build_prompt_from_state(self, state: Dict[str, Any]) -> str:
        template = self._load_prompt_template()
        game = state.get("game_state", {})
        private_state = game.get("private_state", {})
        public_state = game.get("public_state", {})

        prof = PERSONALITY_PROFILES[self.personality]

        time_remaining_sec = int(public_state.get("time_remaining", 0) or 0)
        time_remaining_min = max(0, round(time_remaining_sec / 60))
        
        # Handle wordguessing experiment differently
        if self.experiment_type == "wordguessing":
            return self._build_wordguessing_prompt(template, private_state, public_state, prof, time_remaining_min, state.get("communication_level", "chat"))
        
        specialty_shape = private_state.get("specialty_shape", "circle")
        current_money = int(private_state.get("money", 0) or 0)
        inventory = private_state.get("inventory", [])
        current_orders = private_state.get("orders", [])
        production_queue = private_state.get("production_queue", [])
        # Get max production number from experiment config
        max_production_num = public_state.get("experiment_config", {}).get("maxProductionNum", 6)
        
        # Get price limits from experiment config
        price_min = public_state.get("experiment_config", {}).get("minTradePrice", 15)
        price_max = public_state.get("experiment_config", {}).get("maxTradePrice", 35)
        
        # Get production costs from experiment config
        specialty_cost = public_state.get("experiment_config", {}).get("specialtyCost", 10)
        regular_cost = public_state.get("experiment_config", {}).get("regularCost", 25)
        
        # Get incentive money from experiment config
        incentive_money = public_state.get("experiment_config", {}).get("incentiveMoney", 50)
        
        # Get shape amount per order from experiment config
        shape_amount_per_order = public_state.get("experiment_config", {}).get("shapesPerOrder", 3)
        
        participants_list = self._format_participants(public_state)
        decision_history = "(none)"
        trade_history = "(none)"
        
        # Get actual pending trade offers from database
        pending_offers_sent = 0
        pending_offers_received = 0
        pending_offers_sent_details = []
        pending_offers_received_details = []
        
        try:
            import psycopg2
            import psycopg2.extras
            
            # Get participant_id for this participant
            db_url = self.tools._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Use session-aware lookup
            if self.session_code:
                cur.execute("""
                    SELECT participant_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (self.participant_code, self.session_code))
            else:
                # Fallback with ordering by activity
                cur.execute("""
                    SELECT participant_id FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (self.participant_code,))
            result = cur.fetchone()
            
            if result:
                participant_id = result['participant_id']
                
                # Get detailed pending offers sent and received by this participant
                cur.execute("""
                    SELECT 
                        t.transaction_id,
                        t.short_id as short_transaction_id,
                        t.proposer_id,
                        t.recipient_id,
                        t.offer_type,
                        t.shape_type,
                        t.quantity,
                        t.agreed_price,
                        t.transaction_status,
                        t.proposed_timestamp,
                        p1.participant_code as proposer_code,
                        p2.participant_code as recipient_code
                    FROM transactions t
                    LEFT JOIN participants p1 ON t.proposer_id = p1.participant_id
                    LEFT JOIN participants p2 ON t.recipient_id = p2.participant_id
                    WHERE t.transaction_status = 'proposed'
                """)
                transactions = cur.fetchall()
                
                pending_offers_sent = 0
                pending_offers_received = 0
                
                for transaction in transactions:
                    proposer_id = transaction['proposer_id']
                    recipient_id = transaction['recipient_id']
                    
                    # Format the trade offer details
                    offer_detail = {
                        'transaction_id': transaction['transaction_id'],
                        'short_transaction_id': transaction['short_transaction_id'],
                        'offer_type': transaction['offer_type'],
                        'shape': transaction['shape_type'],
                        'quantity': transaction['quantity'],
                        'price_per_unit': transaction['agreed_price'],
                        'timestamp': transaction['proposed_timestamp'].isoformat() if transaction['proposed_timestamp'] else None,
                        'proposer_code': transaction['proposer_code'],
                        'recipient_code': transaction['recipient_code']
                    }
                    
                    # Simple logic: proposer sent the offer, recipient received it
                    if proposer_id == participant_id:
                        pending_offers_sent += 1
                        pending_offers_sent_details.append(offer_detail)
                    elif recipient_id == participant_id:
                        pending_offers_received += 1
                        pending_offers_received_details.append(offer_detail)
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"Warning: Could not get pending offers for {self.participant_code}: {e}")
            pending_offers_sent = 0
            pending_offers_received = 0
            pending_offers_sent_details = []
            pending_offers_received_details = []
        
        # Format trade offers for display
        def format_sent_trade_offers(offers_list):
            if not offers_list:
                return "(none)"
            
            formatted_offers = []
            for offer in offers_list:
                offer_type = offer['offer_type']
                shape = offer['shape']
                quantity = offer['quantity']
                price = offer['price_per_unit']
                target = offer['recipient_code']  # Person being offered to
                short_transaction_id = offer.get('short_transaction_id', offer['transaction_id'])
                
                formatted_offers.append(f"• {offer_type.upper()} {quantity}x {shape} @ ${price}/unit to {target} (ID: {short_transaction_id})")
            
            return "\n".join(formatted_offers)
        
        def format_received_trade_offers(offers_list):
            if not offers_list:
                return "(none)"
            
            formatted_offers = []
            for offer in offers_list:
                offer_type = offer['offer_type']
                shape = offer['shape']
                quantity = offer['quantity']
                price = offer['price_per_unit']
                proposer = offer['proposer_code']  # Person who made the offer
                short_transaction_id = offer.get('short_transaction_id', offer['transaction_id'])
                
                formatted_offers.append(f"• Received {offer_type.upper()} {quantity}x {shape} @ ${price}/unit from {proposer} (ID: {short_transaction_id})")
            
            return "\n".join(formatted_offers)
        
        pending_offers_sent_formatted = format_sent_trade_offers(pending_offers_sent_details)
        pending_offers_received_formatted = format_received_trade_offers(pending_offers_received_details)

        # Get unread messages from database
        unread_messages = "(none)"
        try:
            import psycopg2
            import psycopg2.extras
            from datetime import datetime, timezone, timedelta
            
            # Get participant_id and session_id for this participant
            db_url = self.tools._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Use session-aware lookup
            if self.session_code:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (self.participant_code, self.session_code))
            else:
                # Fallback with ordering by activity
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (self.participant_code,))
            result = cur.fetchone()
            
            if result:
                participant_id = result['participant_id']
                session_id = result['session_id']
                
                # Get unread messages (delivered_status = 'sent' or 'delivered' but not 'read')
                # Include messages sent TO this participant, or broadcast messages
                cur.execute("""
                    SELECT 
                        m.message_id,
                        m.sender_id,
                        m.recipient_id,
                        m.message_content,
                        m.message_timestamp,
                        m.message_type,
                        m.delivered_status,
                        p1.participant_code as sender_code,
                        p2.participant_code as recipient_code
                    FROM messages m
                    LEFT JOIN participants p1 ON m.sender_id = p1.participant_id
                    LEFT JOIN participants p2 ON m.recipient_id = p2.participant_id
                    WHERE m.session_id = %s
                    AND (
                        m.recipient_id = %s OR 
                        m.recipient_id IS NULL
                    )
                    AND m.sender_id != %s  -- Not messages sent by this participant
                    AND m.message_type = 'chat'
                    AND m.delivered_status IN ('sent', 'delivered')
                    ORDER BY m.message_timestamp ASC
                """, (session_id, participant_id, participant_id))
                
                messages = cur.fetchall()
                
                if messages:
                    # Categorize messages by conversation
                    conversations = {}
                    broadcast_messages = []
                    
                    for msg in messages:
                        sender_code = msg['sender_code']
                        recipient_code = msg['recipient_code']
                        content = msg['message_content']
                        timestamp = msg['message_timestamp']
                        
                        # Format timestamp
                        if timestamp:
                            # Convert to local time and format
                            local_time = timestamp.replace(tzinfo=timezone.utc).astimezone()
                            time_str = local_time.strftime("%H:%M:%S")
                        else:
                            time_str = "??:??:??"
                        
                        # Handle broadcast messages separately
                        if recipient_code is None:
                            broadcast_messages.append({
                                'time': time_str,
                                'sender': sender_code,
                                'content': content,
                                'timestamp': timestamp
                            })
                        else:
                            # Determine the other participant in the conversation
                            if sender_code == self.participant_code:
                                other_participant = recipient_code
                                direction = "TO"
                            else:
                                other_participant = sender_code
                                direction = "FROM"
                            
                            # Create conversation key
                            conversation_key = other_participant
                            
                            if conversation_key not in conversations:
                                conversations[conversation_key] = []
                            
                            conversations[conversation_key].append({
                                'time': time_str,
                                'direction': direction,
                                'content': content,
                                'timestamp': timestamp
                            })
                    
                    # Format conversations
                    formatted_sections = []
                    
                    # Add broadcast messages section if any exist
                    if broadcast_messages:
                        broadcast_section = ["📢 BROADCAST MESSAGES:"]
                        for msg in sorted(broadcast_messages, key=lambda x: x['timestamp']):
                            broadcast_section.append(f"  {msg['time']} [FROM {msg['sender']}]: {msg['content']}")
                        formatted_sections.append("\n".join(broadcast_section))
                    
                    # Add individual conversations
                    for other_participant in sorted(conversations.keys()):
                        conversation_messages = conversations[other_participant]
                        conversation_section = [f"💬 CHAT WITH {other_participant}:"]
                        
                        # Sort messages by timestamp
                        for msg in sorted(conversation_messages, key=lambda x: x['timestamp']):
                            conversation_section.append(f"  {msg['time']} [{msg['direction']}]: {msg['content']}")
                        
                        formatted_sections.append("\n".join(conversation_section))
                    
                    unread_messages = "\n\n".join(formatted_sections)
                else:
                    unread_messages = "(none)"
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"Warning: Could not get unread messages for {self.participant_code}: {e}")
            unread_messages = "(none)"

        # Get communication level from the state
        communication_level = state.get("communication_level", "chat")
        
        # Get production time from experiment config (default to 5 seconds)
        production_time = 5  # Default value in seconds
        if public_state.get("experiment_config"):
            production_time = public_state["experiment_config"].get("productionTime", 5)
        
        # Format production status
        production_status = "No production in progress"
        if production_queue:
            active_productions = [p for p in production_queue if p.get("status") in ["queued", "in_progress"]]
            if active_productions:
                prod = active_productions[0]  # Show the first active production
                time_remaining = prod.get("time_remaining_minutes", 0)
                if time_remaining is not None:
                    if time_remaining == 0:
                        production_status = f"Producing {prod['quantity']}x {prod['shape']} - completing soon"
                    else:
                        production_status = f"Producing {prod['quantity']}x {prod['shape']} - {time_remaining} minutes remaining"
                else:
                    production_status = f"Producing {prod['quantity']}x {prod['shape']} - completing soon"
            else:
                production_status = "No active production"
        else:
            production_status = "No production in progress"

        # Format current production queue
        current_production_queue = "No shapes currently under production"
        if production_queue:
            active_productions = [p for p in production_queue if p.get("status") in ["queued", "in_progress"]]
            if active_productions:
                queue_lines = []
                for i, prod in enumerate(active_productions, 1):
                    shape = prod['shape']
                    quantity = prod['quantity']
                    status = prod['status']
                    time_remaining = prod.get("time_remaining", 0)
                    
                    # Convert seconds to minutes for display
                    time_remaining_min = max(0, time_remaining // 60)
                    time_remaining_sec = time_remaining % 60
                    
                    if time_remaining_min > 0:
                        time_str = f"{time_remaining_min}m {time_remaining_sec}s remaining"
                    else:
                        time_str = f"{time_remaining_sec}s remaining" if time_remaining_sec > 0 else "completing soon"
                    
                    # Mark if it's the participant's specialty shape
                    specialty_marker = " (SPECIALTY)" if shape == specialty_shape else ""
                    
                    queue_lines.append(f"- {quantity}x {shape}{specialty_marker} - {status} - {time_str}")
                
                current_production_queue = "\n".join(queue_lines)
            else:
                current_production_queue = "No shapes currently under production"
        else:
            current_production_queue = "No shapes currently under production"

        # Get failure summary for the agent
        failed_actions_summary = self._get_failure_summary()
        
        prompt = template.format(
            participant_code=self.participant_code,
            personality_name=prof["name"],
            personality_description=prof["description"],
            behavior=prof["behavior"],
            communication=prof["communication"],
            time_remaining=time_remaining_min,
            specialization=specialty_shape.title(),
            specialty_shape=specialty_shape,
            current_money=current_money,
            inventory=inventory,
            current_orders=current_orders,
            production_status=production_status,
            current_production_queue=current_production_queue,
            max_production_num=max_production_num,
            price_min=price_min,
            price_max=price_max,
            production_time=production_time,
            participants_list=participants_list,
            recent_messages=unread_messages,
            decision_history=decision_history,
            trade_history=trade_history,
            failed_actions_summary=failed_actions_summary,
            pending_offers_sent=pending_offers_sent,
            pending_offers_received=pending_offers_received,
            pending_offers_sent_formatted=pending_offers_sent_formatted,
            pending_offers_received_formatted=pending_offers_received_formatted,
            communication_level=communication_level,
            specialty_cost=specialty_cost,
            regular_cost=regular_cost,
            incentive_money=incentive_money,
            shape_amount_per_order=shape_amount_per_order
        )
        
        # Modify the prompt based on communication level
        prompt = self._modify_prompt_for_communication_level(prompt, communication_level)
        
        return prompt

    def _build_wordguessing_prompt(self, template: str, private_state: Dict[str, Any], public_state: Dict[str, Any], prof: Dict[str, str], time_remaining_min: int, communication_level: str) -> str:
        """Build prompt for wordguessing experiment with role-specific variables"""
        
        # Add null checks for safety
        if private_state is None:
            private_state = {}
        if public_state is None:
            public_state = {}
        
        # Get participant role and other wordguessing-specific data
        participant_role = private_state.get("role", "unknown")
        current_round = private_state.get("current_round", 1)
        score = private_state.get("score", 0)
        assigned_words = private_state.get("assigned_words", [])
        
        # Format assigned words for hinter
        if participant_role == "hinter" and assigned_words:
            assigned_words_str = ", ".join(assigned_words)
        else:
            assigned_words_str = "None"
        
        # Get other participants and find the opposite role
        participants_list = self._format_participants(public_state)
        opposite_participant = None
        
        if participants_list and participants_list != "(none)":
            # Find the participant with the opposite role
            for participant in public_state.get("other_participants", []):
                if participant.get("role") != participant_role:
                    opposite_participant = participant.get("participant_code", "Unknown")
                    break
        
        if not opposite_participant:
            opposite_participant = "Unknown"
        
        # Get unread messages
        unread_messages = self._get_unread_messages_for_agent()
        recent_messages = ""
        if unread_messages:
            messages_list = []
            for msg in unread_messages[:5]:  # Last 5 messages
                sender = msg.get("sender_code", "Unknown")
                content = msg.get("content", "")
                messages_list.append(f"- {sender}: {content}")
            recent_messages = "\n".join(messages_list)
        else:
            recent_messages = "No recent messages"
        
        # Format the prompt with wordguessing-specific variables
        prompt = template.format(
            participant_code=self.participant_code,
            personality_name=prof["name"],
            mbti_type=prof.get("mbti_type", "UNKNOWN"),
            personality_description=prof["description"],
            communication_level=communication_level,
            assigned_words=assigned_words_str,
            guesser_participant=opposite_participant if participant_role == "hinter" else "N/A",
            hinter_participant=opposite_participant if participant_role == "guesser" else "N/A",
            participants_list=participants_list,
            recent_messages=recent_messages
        )
        
        # Modify the prompt based on communication level
        prompt = self._modify_prompt_for_communication_level(prompt, communication_level)
        
        return prompt

    def _extract_json_block(self, text: str) -> Optional[str]:
        if not text:
            return None
        # Prefer fenced ```json blocks
        fenced = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
        if fenced:
            return fenced.group(1)
        # Any fenced block
        fenced_any = re.search(r"```\s*(\{[\s\S]*?\})\s*```", text)
        if fenced_any:
            return fenced_any.group(1)
        # Bracket-matching extraction for first complete JSON object
        start = text.find('{')
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i+1]
        return None

    def _parse_plan_json(self, text: str) -> Optional[Dict[str, Any]]:
        block = self._extract_json_block(text)
        if not block:
            return None
        try:
            return json.loads(block)
        except Exception:
            # Try a minimal cleanup: remove trailing commas before } or ]
            cleaned = re.sub(r",\s*([}\]])", r"\1", block)
            try:
                return json.loads(cleaned)
            except Exception:
                return None

    def _choose_recipient(self, public_state: Dict[str, Any]) -> Optional[str]:
        # Try other_participants first, then fall back to participants (for hiddenprofiles)
        others = public_state.get("other_participants", []) or []
        if not others:
            # Fallback to participants for Hidden Profiles
            others = public_state.get("participants", []) or []
        
        candidates = []
        for p in others:
            code = p.get("participant_id") or p.get("participant_code") or p.get("id")
            if code and code != self.participant_code:
                # For Hidden Profiles, extract display name if it's the internal code
                if self.experiment_type == "hiddenprofiles" and '_' in str(code):
                    # This might be an internal code with session suffix, try display name
                    display_name = str(code).rsplit('_', 1)[0]
                    if display_name != self.participant_code:
                        candidates.append(display_name)
                else:
                    candidates.append(code)
        if not candidates:
            return None
        return random.choice(candidates)

    def _map_plan_to_tool_calls(self, plan: Dict[str, Any], public_state: Dict[str, Any], communication_level: str = "chat") -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        actions = plan.get("actions", []) if isinstance(plan, dict) else []
        
        for a in actions:
            if not isinstance(a, dict):
                continue
            atype = a.get("type")
            if atype == "message":
                # Handle messages based on communication level
                # For Hidden Profiles, "group_chat" should be treated as broadcast mode
                effective_communication_level = communication_level
                if self.experiment_type == "hiddenprofiles" and communication_level == "group_chat":
                    effective_communication_level = "broadcast"
                
                if effective_communication_level == "no_chat":
                    # Skip messages in no_chat mode
                    continue
                elif effective_communication_level == "broadcast":
                    # Force all messages to be broadcast in broadcast mode
                    content = a.get("content") or ""
                    if content:
                        calls.append({
                            "name": "send_message",
                            "arguments": {"participant_code": self.participant_code, "recipient": "all", "content": content}
                        })
                else:  # chat mode
                    # In chat mode, only allow messages to specific participants
                    content = a.get("content") or ""
                    recipient = a.get("recipient") or ""
                    if content and recipient and recipient != "all":
                        calls.append({
                            "name": "send_message",
                            "arguments": {"participant_code": self.participant_code, "recipient": recipient, "content": content}
                        })
                    elif content and (not recipient or recipient == "all"):
                        # If no recipient specified or "all", choose a specific participant
                        chosen_recipient = self._choose_recipient(public_state)
                        if chosen_recipient:
                            calls.append({
                                "name": "send_message",
                                "arguments": {"participant_code": self.participant_code, "recipient": chosen_recipient, "content": content}
                            })

            elif atype == "trade_response":
                txn_id = a.get("transaction_id") or a.get("offer_id") or ""
                resp = a.get("response_type") or a.get("response") or "decline"
                # Map "decline" to "reject" since game engine expects "reject"
                if resp == "decline":
                    resp = "reject"
                if txn_id:
                    calls.append({
                        "name": "respond_to_trade_offer",
                        "arguments": {"participant_code": self.participant_code, "transaction_id": txn_id, "response": resp}
                    })

            elif atype == "produce_shape":
                calls.append({
                    "name": "produce_shape",
                    "arguments": {
                        "participant_code": self.participant_code,
                        "shape": a.get("shape", "circle"),
                        "quantity": int(a.get("quantity", 1) or 1),
                    }
                })
            elif atype == "fulfill_order":
                indices = a.get("order_indices") or []
                if isinstance(indices, list):
                    calls.append({
                        "name": "fulfill_orders",
                        "arguments": {"participant_code": self.participant_code, "order_indices": indices}
                    })
            elif atype == "propose_trade_offer":
                recipient = a.get("target_participant")
                if not recipient or recipient == "all":
                    recipient = self._choose_recipient(public_state) or self.participant_code
                price = int(a.get("price_per_unit", 20) or 20)
                # Get price limits from experiment config
                price_min = public_state.get("experiment_config", {}).get("minTradePrice", 10)
                price_max = public_state.get("experiment_config", {}).get("maxTradePrice", 40)
                price = max(price_min, min(price_max, price))
                calls.append({
                    "name": "create_trade_offer",
                    "arguments": {
                        "participant_code": self.participant_code,
                        "recipient": recipient,
                        "offer_type": a.get("offer_type", "sell"),
                        "shape": a.get("shape", "circle"),
                        "price_per_unit": price,
                    }
                })
            elif atype == "cancel_trade_offer":
                txn_id = a.get("transaction_id") or a.get("offer_id") or ""
                if txn_id:
                    calls.append({
                        "name": "cancel_trade_offer",
                        "arguments": {"participant_code": self.participant_code, "transaction_id": txn_id}
                    })
            elif atype == "make_investment":
                # DayTrader investment action
                invest_price = float(a.get("invest_price", 0) or 0)
                invest_decision_type = a.get("invest_decision_type", "individual")
                # Get price limits from experiment config
                price_min = public_state.get("experiment_config", {}).get("minTradePrice", 10)
                price_max = public_state.get("experiment_config", {}).get("maxTradePrice", 40)
                # Clamp price to valid range
                invest_price = max(price_min, min(price_max, invest_price))
                calls.append({
                    "name": "make_investment",
                    "arguments": {
                        "participant_code": self.participant_code,
                        "invest_price": invest_price,
                        "invest_decision_type": invest_decision_type,
                    }
                })
            elif atype == "submit_ranking":
                # Essay Ranking action
                rankings = a.get("rankings", [])
                if isinstance(rankings, list) and rankings:
                    calls.append({
                        "name": "submit_ranking",
                        "arguments": {
                            "participant_code": self.participant_code,
                            "rankings": rankings,
                        }
                    })
            elif atype == "get_essay_content":
                # Essay Ranking action - get specific essay content
                essay_id = a.get("essay_id", "")
                if essay_id:
                    calls.append({
                        "name": "get_essay_content",
                        
                        "arguments": {
                            "participant_code": self.participant_code,
                            "essay_id": essay_id,
                        }
                    })
            elif atype == "get_assigned_essays":
                # Essay Ranking action - get all assigned essays
                calls.append({
                    "name": "get_assigned_essays",
                    "arguments": {
                        "participant_code": self.participant_code,
                    }
                })
            elif atype == "submit_vote":
                # Hidden Profiles action - submit vote for a candidate
                candidate_name = a.get("candidate_name", "")
                if candidate_name:
                    calls.append({
                        "name": "submit_vote",
                        "arguments": {
                            "participant_code": self.participant_code,
                            "candidate_name": candidate_name,
                        }
                    })
        return calls

    def _get_unread_messages_for_agent(self) -> List[Dict[str, Any]]:
        """Gather new, unread messages for this agent."""
        unread_messages = []
        
        try:
            import psycopg2
            import psycopg2.extras
            from datetime import datetime, timezone, timedelta
            import json
            
            db_url = self.tools._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Get participant_id and session_id for this agent
            # Use session-aware lookup
            if self.session_code:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (self.participant_code, self.session_code))
            else:
                # Fallback with ordering by activity
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (self.participant_code,))
            result = cur.fetchone()
            
            if result:
                participant_id = result['participant_id']
                session_id = result['session_id']
                
                # Get unread messages (delivered_status = 'sent' or 'delivered' but not 'read')
                # Include messages sent TO this agent, or broadcast messages
                cur.execute("""
                    SELECT 
                        m.message_id,
                        m.message_content as content,
                        m.message_timestamp,
                        m.message_type,
                        m.delivered_status,
                        m.message_data,
                        p1.participant_code as sender_code,
                        p2.participant_code as recipient_code
                    FROM messages m
                    LEFT JOIN participants p1 ON m.sender_id = p1.participant_id
                    LEFT JOIN participants p2 ON m.recipient_id = p2.participant_id
                    WHERE m.session_id = %s
                    AND (
                        m.recipient_id = %s OR 
                        m.recipient_id IS NULL
                    )
                    AND m.sender_id != %s  -- Not messages sent by this agent
                    AND m.message_type = 'chat'
                    AND m.delivered_status IN ('sent', 'delivered')
                    ORDER BY m.message_timestamp ASC
                """, (session_id, participant_id, participant_id))
                
                messages = cur.fetchall()
                
                for msg in messages:
                    # Determine message type and sender
                    if msg['recipient_code'] is None:
                        message_type = "BROADCAST"
                        sender = msg['sender_code']
                        
                        # For broadcast messages, check if this agent has already seen it
                        message_data = msg['message_data'] or {}
                        seen_by = message_data.get('seen_by', [])
                        
                        # Only include if this agent hasn't seen it yet
                        if participant_id not in seen_by:
                            unread_messages.append({
                                'message_id': msg['message_id'],
                                'type': message_type,
                                'sender': sender,
                                'content': msg['content'],
                                'timestamp': msg['message_timestamp'],
                                'delivered_status': msg['delivered_status']
                            })
                    else:
                        message_type = "DIRECT"
                        sender = msg['sender_code']
                        
                        unread_messages.append({
                            'message_id': msg['message_id'],
                            'type': message_type,
                            'sender': sender,
                            'content': msg['content'],
                            'timestamp': msg['message_timestamp'],
                            'delivered_status': msg['delivered_status']
                        })
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"Warning: Could not get unread messages for agent {self.participant_code}: {e}")
        
        return unread_messages

    def _mark_broadcast_message_as_seen(self, message_id: str):
        """Mark a broadcast message as seen by this agent (but keep it unread for others)."""
        try:
            import psycopg2
            import psycopg2.extras
            import json
            
            db_url = self.tools._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Get participant_id and session_id for this agent
            # Use session-aware lookup
            if self.session_code:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (self.participant_code, self.session_code))
            else:
                # Fallback with ordering by activity
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (self.participant_code,))
            result = cur.fetchone()
            
            if result:
                participant_id = result['participant_id']
                session_id = result['session_id']
                
                # Check if this message is actually a broadcast message
                cur.execute("""
                    SELECT recipient_id FROM messages 
                    WHERE message_id = %s AND session_id = %s
                """, (message_id, session_id))
                msg_result = cur.fetchone()
                
                if msg_result and msg_result['recipient_id'] is None:
                    # This is a broadcast message - track that this agent has seen it
                    # We'll use the message_data JSONB field to track which agents have seen it
                    cur.execute("""
                        SELECT message_data FROM messages WHERE message_id = %s
                    """, (message_id,))
                    current_data = cur.fetchone()
                    
                    if current_data:
                        message_data = current_data['message_data'] or {}
                        seen_by = message_data.get('seen_by', [])
                        
                        if participant_id not in seen_by:
                            seen_by.append(participant_id)
                            message_data['seen_by'] = seen_by
                            
                            # Update the message with the new seen_by list
                            cur.execute("""
                                UPDATE messages 
                                SET message_data = %s
                                WHERE message_id = %s
                            """, (json.dumps(message_data), message_id))
                            
                    
                    conn.commit()
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"Warning: Could not mark broadcast message as seen for agent {self.participant_code}: {e}")

    def _check_and_mark_broadcast_as_read_if_all_seen(self, message_id: str):
        """Check if all agents have seen a broadcast message and mark it as read if they have."""
        try:
            import psycopg2
            import psycopg2.extras
            import json
            
            db_url = self.tools._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Get session_id for this agent
            cur.execute("""
                SELECT session_id FROM participants 
                WHERE participant_code = %s
                LIMIT 1
            """, (self.participant_code,))
            result = cur.fetchone()
            
            if result:
                session_id = result['session_id']
                
                # Get the broadcast message and check if all agents have seen it
                cur.execute("""
                    SELECT m.message_data, m.delivered_status
                    FROM messages m
                    WHERE m.message_id = %s AND m.session_id = %s AND m.recipient_id IS NULL
                """, (message_id, session_id))
                msg_result = cur.fetchone()
                
                if msg_result and msg_result['delivered_status'] != 'read':
                    message_data = msg_result['message_data'] or {}
                    seen_by = message_data.get('seen_by', [])
                    
                    # Get all participant IDs in this session
                    cur.execute("""
                        SELECT participant_id FROM participants 
                        WHERE session_id = %s
                    """, (session_id,))
                    all_participants = cur.fetchall()
                    all_participant_ids = [p['participant_id'] for p in all_participants]
                    
                    # Check if all participants have seen this message
                    if len(seen_by) == len(all_participant_ids) and all(pid in seen_by for pid in all_participant_ids):
                        # All agents have seen it - mark as read
                        cur.execute("""
                            UPDATE messages 
                            SET delivered_status = 'read'
                            WHERE message_id = %s
                        """, (message_id,))

                        conn.commit()
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"Warning: Could not check broadcast message read status: {e}")

    def _mark_messages_as_read(self, message_ids: List[str] = None):
        """Mark messages as read for this agent."""
        try:
            import psycopg2
            import psycopg2.extras
            
            db_url = self.tools._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Get participant_id and session_id for this agent
            # Use session-aware lookup
            if self.session_code:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (self.participant_code, self.session_code))
            else:
                # Fallback with ordering by activity
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (self.participant_code,))
            result = cur.fetchone()
            
            if result:
                participant_id = result['participant_id']
                session_id = result['session_id']
                
                if message_ids:
                    # Mark specific messages as read
                    placeholders = ','.join(['%s'] * len(message_ids))
                    cur.execute(f"""
                        UPDATE messages 
                        SET delivered_status = 'read'
                        WHERE message_id IN ({placeholders})
                        AND session_id = %s
                        AND (recipient_id = %s OR recipient_id IS NULL)
                        AND sender_id != %s
                    """, message_ids + [session_id, participant_id, participant_id])
                else:
                    # Mark all unread messages for this agent as read
                    cur.execute("""
                        UPDATE messages 
                        SET delivered_status = 'read'
                        WHERE session_id = %s
                        AND (recipient_id = %s OR recipient_id IS NULL)
                        AND sender_id != %s
                        AND message_type = 'chat'
                        AND delivered_status IN ('sent', 'delivered')
                    """, (session_id, participant_id, participant_id))
                
                conn.commit()
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"Warning: Could not mark messages as read for agent {self.participant_code}: {e}")

    def _build_status_update(self, state: Dict[str, Any]) -> str:
        """Build a concise status update for memory-aware agents."""
        game = state.get("game_state", {})
        private_state = game.get("private_state", {})
        public_state = game.get("public_state", {})
        
        # Handle wordguessing experiments differently
        if self.experiment_type == "wordguessing":
            return self._build_wordguessing_status_update(private_state, public_state)
        
        # Basic status for ShapeFactory experiments
        money = int(private_state.get("money", 0) or 0)
        inventory = private_state.get("inventory", [])
        current_orders = private_state.get("orders", [])
        production_queue = private_state.get("production_queue", [])
        specialty_shape = private_state.get("specialty_shape", "circle")
        
        # Get specialty production time information from the current state
        # Use real-time data from the game state instead of database queries
        specialty_production_used = private_state.get("specialty_production_used", 0) or 0
        max_production_num = public_state.get("experiment_config", {}).get("maxProductionNum", 6)
        
        # Time remaining
        time_remaining_sec = int(public_state.get("time_remaining", 0) or 0)
        time_remaining_min = max(0, round(time_remaining_sec / 60))
        
        # Price limits from experiment config for clearer guidance in status update
        experiment_config = public_state.get("experiment_config", {})
        price_min = experiment_config.get("minTradePrice", 15)
        price_max = experiment_config.get("maxTradePrice", 35)

        # Production status
        production_status = "No production in progress"
        if production_queue:
            active_productions = [p for p in production_queue if p.get("status") in ["queued", "in_progress"]]
            if active_productions:
                # Show current production and queue length
                current_production = next((p for p in active_productions if p.get("status") == "in_progress"), None)
                queued_productions = [p for p in active_productions if p.get("status") == "queued"]
                
                if current_production:
                    time_remaining = current_production.get("time_remaining", 0)
                    if time_remaining > 0:
                        queue_info = f" (+{len(queued_productions)} queued)" if queued_productions else ""
                        production_status = f"Producing {current_production['quantity']}x {current_production['shape']} - {time_remaining}s remaining{queue_info}"
                    else:
                        queue_info = f" (+{len(queued_productions)} queued)" if queued_productions else ""
                        production_status = f"Producing {current_production['quantity']}x {current_production['shape']} - completing soon{queue_info}"
                elif queued_productions:
                    production_status = f"Production queue: {len(queued_productions)} items waiting"
        
        # Get unread messages for this agent
        unread_messages = self._get_unread_messages_for_agent()
        
        # Format unread messages section
        if unread_messages:
            unread_sections = []
            
            # Group by sender for better organization
            messages_by_sender = {}
            broadcast_messages = []
            
            for msg in unread_messages:
                if msg['type'] == "BROADCAST":
                    broadcast_messages.append(msg)
                else:
                    sender = msg['sender']
                    if sender not in messages_by_sender:
                        messages_by_sender[sender] = []
                    messages_by_sender[sender].append(msg)
            
            # Format broadcast messages
            if broadcast_messages:
                broadcast_section = ["UNREAD BROADCAST MESSAGES:"]
                for msg in sorted(broadcast_messages, key=lambda x: x['timestamp']):
                    timestamp_str = msg['timestamp'].strftime("%H:%M:%S")
                    broadcast_section.append(f"  FROM {msg['sender']} ({timestamp_str}): {msg['content']}")
                unread_sections.append("\n".join(broadcast_section))
            
            # Format direct messages by sender
            for sender in sorted(messages_by_sender.keys()):
                sender_messages = messages_by_sender[sender]
                sender_section = [f"UNREAD MESSAGES FROM {sender}:"]
                
                for msg in sorted(sender_messages, key=lambda x: x['timestamp']):
                    timestamp_str = msg['timestamp'].strftime("%H:%M:%S")
                    sender_section.append(f"  ({timestamp_str}): {msg['content']}")
                
                unread_sections.append("\n".join(sender_section))
            
            unread_messages_section = "\n\n".join(unread_sections)
        else:
            unread_messages_section = "(none)"
        
        # For DayTrader, use DayTrader-specific status update
        if self.experiment_type == "daytrader":
            # Get investment history for DayTrader
            investment_history = "(none)"
            try:
                investment_result = self.tools.get_investment_history(self.participant_code, self.session_code)
                if investment_result.get("success") and investment_result.get("investment_history"):
                    investments = investment_result["investment_history"]
                    if investments:
                        investment_lines = []
                        for inv in investments[:5]:  # Show last 5 investments
                            price = inv['invest_price']
                            decision_type = inv['invest_decision_type']
                            profit_loss = inv.get('profit_loss')
                            timestamp = inv.get('investment_timestamp', 'Unknown time')
                            
                            if profit_loss is not None:
                                profit_str = f" (P/L: ${profit_loss:+.2f})"
                            else:
                                profit_str = " (Pending)"
                            
                            investment_lines.append(f"• {decision_type.title()} investment at ${price:.2f}{profit_str} - {timestamp}")
                        
                        investment_history = "\n".join(investment_lines)
                    else:
                        investment_history = "(none)"
                else:
                    investment_history = "(none)"
            except Exception as e:
                print(f"Warning: Could not get investment history for DayTrader status update: {e}")
                investment_history = "(none)"
            
            # Build status update for DayTrader
            status_update = f"""
CURRENT STATUS UPDATE (DAYTRADER):

- Your Money Balance: ${money}
- Time Remaining: {time_remaining_min} minutes
- Investment Price Range: ${price_min}-${price_max}

- Recent Investment History:
{investment_history}

- Unread Messages:
{unread_messages_section}

- Recent Failed Actions:
{self._get_failure_summary()}

- Other Participants:
{self._format_participants(public_state)}

Instructions on Aligning with Human Behaviors:
- Make investment decisions based on your personality traits and risk tolerance.
- Consider market conditions and other participants' behavior when making decisions.
- Review your investment history to understand your past performance and adjust your strategy accordingly.
- When communicating, discuss investment strategies but remember you are competing to maximize your own returns.
- Your investment decisions should reflect your personality traits and risk tolerance.
- Do not spam repetitive messages or make identical investment decisions.
- Pay attention to the new messages you received, and do not forget to respond to others' messages.
- When responding, treat the conversation as a *continuous* communication with other participants.
"""
        # For ShapeFactory, use the original detailed status update
        elif self.experiment_type == "shapefactory":
            # Pending trade offers
            pending_offers_sent = 0
            pending_offers_received = 0
            try:
                import psycopg2
                import psycopg2.extras
                
                db_url = self.tools._engine.db_connection_string
                conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
                cur = conn.cursor()
                
                # Use session-aware lookup
                if self.session_code:
                    cur.execute("""
                        SELECT participant_id FROM participants 
                        WHERE participant_code = %s AND session_code = %s
                        LIMIT 1
                    """, (self.participant_code, self.session_code))
                else:
                    # Fallback with ordering by activity
                    cur.execute("""
                        SELECT participant_id FROM participants 
                        WHERE participant_code = %s
                        ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                        LIMIT 1
                    """, (self.participant_code,))
                result = cur.fetchone()
                
                if result:
                    participant_id = result['participant_id']
                    
                    cur.execute("""
                        SELECT 
                            t.proposer_id,
                            t.recipient_id,
                            t.offer_type,
                            t.shape_type,
                            t.quantity,
                            t.agreed_price,
                            p1.participant_code as proposer_code,
                            p2.participant_code as recipient_code
                        FROM transactions t
                        LEFT JOIN participants p1 ON t.proposer_id = p1.participant_id
                        LEFT JOIN participants p2 ON t.recipient_id = p2.participant_id
                        WHERE t.transaction_status IN ('proposed', 'negotiating')
                    """)
                    transactions = cur.fetchall()
                    
                    for transaction in transactions:
                        if transaction['proposer_id'] == participant_id:
                            pending_offers_sent += 1
                        elif transaction['recipient_id'] == participant_id:
                            pending_offers_received += 1
                
                cur.close()
                conn.close()
                
            except Exception as e:
                print(f"Warning: Could not get pending offers for status update: {e}")
            
            # Get detailed pending offers for status update
            pending_offers_details = []
            try:
                import psycopg2
                import psycopg2.extras
                
                db_url = self.tools._engine.db_connection_string
                conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
                cur = conn.cursor()
                
                # Use session-aware lookup
                if self.session_code:
                    cur.execute("""
                        SELECT participant_id, session_id FROM participants 
                        WHERE participant_code = %s AND session_code = %s
                        LIMIT 1
                    """, (self.participant_code, self.session_code))
                else:
                    # Fallback with ordering by activity
                    cur.execute("""
                        SELECT participant_id, session_id FROM participants 
                        WHERE participant_code = %s
                        ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                        LIMIT 1
                    """, (self.participant_code,))
                result = cur.fetchone()
                
                if result:
                    participant_id = result['participant_id']
                    session_id = result['session_id']
                    
                    # Get detailed pending offers for this participant
                    cur.execute("""
                        SELECT 
                            t.transaction_id,
                            t.short_id,
                            t.proposer_id,
                            t.recipient_id,
                            t.seller_id,
                            t.buyer_id,
                            t.offer_type,
                            t.shape_type,
                            t.quantity,
                            t.agreed_price,
                            t.transaction_status,
                            t.proposed_timestamp,
                            p1.participant_code as proposer_code,
                            p2.participant_code as recipient_code
                        FROM transactions t
                        LEFT JOIN participants p1 ON t.proposer_id = p1.participant_id
                        LEFT JOIN participants p2 ON t.recipient_id = p2.participant_id
                        WHERE t.transaction_status = 'proposed'
                        AND (t.proposer_id = %s OR t.recipient_id = %s)
                    """, (participant_id, participant_id))
                    transactions = cur.fetchall()
                    
                    for transaction in transactions:
                        if transaction['proposer_id'] == participant_id:
                            # This is an offer I sent
                            direction = "SENT"
                            other_participant = transaction['recipient_code']
                        else:
                            # This is an offer I received
                            direction = "RECEIVED"
                            other_participant = transaction['proposer_code']
                        
                        # Add validation info for the current participant
                        validation_info = ""
                        if direction == "RECEIVED":
                            # Check if this participant can fulfill the trade
                            if transaction['seller_id'] == participant_id:
                                # Participant is the seller - check inventory
                                cur.execute("""
                                    SELECT shapes_in_inventory FROM shape_inventory 
                                    WHERE session_id = %s AND participant_id = %s
                                """, (session_id, participant_id))
                                
                                inventory_result = cur.fetchone()
                                if inventory_result and inventory_result['shapes_in_inventory']:
                                    available_shapes = inventory_result['shapes_in_inventory'].count(transaction['shape_type'])
                                    if available_shapes < transaction['quantity']:
                                        validation_info = f" ⚠️ INSUFFICIENT INVENTORY (have {available_shapes}, need {transaction['quantity']})"
                                    else:
                                        validation_info = f" ✅ CAN ACCEPT (have {available_shapes})"
                                else:
                                    validation_info = " ⚠️ NO INVENTORY"
                            elif transaction['buyer_id'] == participant_id:
                                # Participant is the buyer - check funds
                                cur.execute("""
                                    SELECT money FROM participants WHERE participant_id = %s
                                """, (participant_id,))
                                
                                money_result = cur.fetchone()
                                if money_result:
                                    total_cost = transaction['agreed_price'] * transaction['quantity']
                                    available_money = money_result['money'] or 0
                                    if available_money < total_cost:
                                        validation_info = f" ⚠️ INSUFFICIENT FUNDS (have ${available_money}, need ${total_cost})"
                                    else:
                                        validation_info = f" ✅ CAN ACCEPT (have ${available_money})"
                        

                        
                        if direction == "SENT":
                            short_id = transaction.get('short_id', transaction['transaction_id'])
                            offer_detail = f"• Sent {transaction['offer_type'].upper()} {transaction['quantity']}x {transaction['shape_type']} @ ${transaction['agreed_price']}/unit to {other_participant} (ID: {short_id}){validation_info}"
                        else:  # RECEIVED
                            short_id = transaction.get('short_id', transaction['transaction_id'])
                            offer_detail = f"• Received {transaction['offer_type'].upper()} {transaction['quantity']}x {transaction['shape_type']} @ ${transaction['agreed_price']}/unit from {other_participant} (ID: {short_id}){validation_info}"
                        pending_offers_details.append(offer_detail)
                
                cur.close()
                conn.close()
                
            except Exception as e:
                print(f"Warning: Could not get pending offers details for status update: {e}")
            
            # Format pending offers section
            if pending_offers_details:
                pending_offers_section = "\n".join(pending_offers_details)
            else:
                pending_offers_section = "(none)"
            
            # Get recent finished offers (accepted/declined) that were proposed by this participant
            recent_finished_offers_details = []
            try:
                import psycopg2
                import psycopg2.extras
                
                db_url = self.tools._engine.db_connection_string
                conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
                cur = conn.cursor()
                
                # Use session-aware lookup
                if self.session_code:
                    cur.execute("""
                        SELECT participant_id FROM participants 
                        WHERE participant_code = %s AND session_code = %s
                        LIMIT 1
                    """, (self.participant_code, self.session_code))
                else:
                    # Fallback with ordering by activity
                    cur.execute("""
                        SELECT participant_id FROM participants 
                        WHERE participant_code = %s
                        ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                        LIMIT 1
                    """, (self.participant_code,))
                result = cur.fetchone()
                
                if result:
                    participant_id = result['participant_id']
                    
                    # Debug: Check what transaction statuses exist for this participant
                    cur.execute("""
                        SELECT DISTINCT transaction_status, COUNT(*) as count
                        FROM transactions 
                        WHERE proposer_id = %s
                        GROUP BY transaction_status
                    """, (participant_id,))
                    status_counts = cur.fetchall()
                    
                    # Get recent finished offers (accepted/declined) that were proposed by this participant
                    cur.execute("""
                        SELECT 
                            t.transaction_id,
                            t.short_id,
                            t.recipient_id,
                            t.offer_type,
                            t.shape_type,
                            t.quantity,
                            t.agreed_price,
                            t.transaction_status,
                            t.proposed_timestamp,
                            COALESCE(t.completed_timestamp, t.agreed_timestamp) as completed_timestamp,
                            p2.participant_code as recipient_code
                        FROM transactions t
                        LEFT JOIN participants p2 ON t.recipient_id = p2.participant_id
                        WHERE t.proposer_id = %s
                        AND t.transaction_status IN ('completed', 'declined', 'cancelled')
                        ORDER BY COALESCE(t.completed_timestamp, t.agreed_timestamp) DESC
                        LIMIT 5
                    """, (participant_id,))
                    finished_transactions = cur.fetchall()
                    
                    for transaction in finished_transactions:
                        other_participant = transaction['recipient_code']
                        short_id = transaction.get('short_id', transaction['transaction_id'])
                        status = transaction['transaction_status'].upper()
                        
                        if status == 'COMPLETED':
                            status_emoji = "✅"
                        elif status == 'DECLINED':
                            status_emoji = "❌"
                        else:  # CANCELLED
                            status_emoji = "🚫"
                        
                        # Map status for display
                        display_status = "ACCEPTED" if status == "COMPLETED" else status
                        offer_detail = f"• {status_emoji} {display_status}: {transaction['offer_type'].upper()} {transaction['quantity']}x {transaction['shape_type']} @ ${transaction['agreed_price']}/unit to {other_participant} (ID: {short_id})"
                        recent_finished_offers_details.append(offer_detail)
                
                cur.close()
                conn.close()
                
            except Exception as e:
                print(f"Warning: Could not get recent finished offers details for status update: {e}")
            
            # Format recent finished offers section
            if recent_finished_offers_details:
                recent_finished_offers_section = "\n".join(recent_finished_offers_details)
            else:
                recent_finished_offers_section = "(none)"
            
            # Build status update for ShapeFactory (original content)
            status_update = f"""
CURRENT STATUS UPDATE:

- Your Money Balance: ${money}
- Your Inventory: {inventory}
- Your Remaining Orders (to be fulfilled): {current_orders}
- Your Production: {production_status}
- Time Remaining: {time_remaining_min} minutes
- Your Specialty Shape: {specialty_shape}
- Total Production Used: {specialty_production_used}/{max_production_num} (applies to all shapes)
- Trading Price Range: Minimum ${price_min}, Maximum ${price_max}

- Pending Offers: Sent {pending_offers_sent}, Received {pending_offers_received}
{pending_offers_section}

- Recent Finished Offers:
{recent_finished_offers_section}

- Unread Messages:
{unread_messages_section}

- Recent Failed Actions:
{self._get_failure_summary()}

- Other Participants:
{self._format_participants(public_state)}

Instructions on Aligning with Human Behaviors:
- When responding, treat the conversation as a *continuous* communication with other participants, just like how you talk to them face-to-face. There's no need to greet or say hey every time.
- When creating a trade offer, the offer type has to be either 'buy' or 'sell'. Keep your trade price within the allowed range: minimum ${price_min}, maximum ${price_max}. Do not confuse your money balance (total resource) with the trade price (transaction amount).
- Learn from the recent failed actions and do not repeat the same mistakes.
- Review recent finished offers to understand which participants are likely to accept or decline your offers, and adjust your trading strategy accordingly.
- Your goal for trading shape is to earn the incentive, so any cost beyond the incentive will cause you to lose money.
- Check if the offer price matches the recent chat agreement. Only accept the offer when the prices are consistent with your best interest, otherwise you need to renegotiate through messaging.
- Do not forget to fulfill your orders using your inventory. This is how you win the game.
- Whenever you reach an agreement through messaging, you must formalize it by creating a trade offer. If you intend to exchange shapes, you should create two separate trade offers: one for selling shapes and another for buying shapes.
"""
        elif self.experiment_type == "essayranking":
            current_rankings = "(none)"            
            # Get current rankings from participant state
            current_rankings_data = private_state.get("current_rankings", [])
            if current_rankings_data:
                ranking_lines = []
                for ranking in current_rankings_data:
                    essay_id = ranking.get('essay_id', 'Unknown')
                    rank = ranking.get('rank', '?')
                    reasoning = ranking.get('reasoning', 'No reasoning provided')
                    ranking_lines.append(f"• Rank {rank}: Essay {essay_id} - {reasoning}")
                current_rankings = "\n".join(ranking_lines)
            else:
                current_rankings = "(none)"
            
            # Build status update for Essay Ranking
            status_update = f"""
CURRENT STATUS UPDATE (ESSAY RANKING):

- Time Remaining: {time_remaining_min} minutes

- Your Current Rankings:
{current_rankings}

- Unread Messages:
{unread_messages_section}

- Recent Failed Actions:
{self._get_failure_summary()}

- Other Participants:
{self._format_participants(public_state)}

Instructions on Aligning with Human Behaviors:
- Review all assigned essays carefully before submitting rankings.
- Provide thoughtful, well-reasoned rankings based on essay quality.
- Engage in meaningful discussion about essay evaluation with other participants.
- Be open to changing your mind based on others' arguments, but also defend your positions when you believe they are correct.
- Show genuine interest in understanding different perspectives on essay quality.
- When discussing essays, be specific about what you liked or didn't like. Reference specific parts of the essays when possible.
"""
        elif self.experiment_type == "hiddenprofiles":
            # Build status update for Hidden Profiles
            status_update = self._build_hiddenprofiles_status_update(private_state, public_state, unread_messages_section, time_remaining_min, state)
        else:
            # For other experiment types, provide a basic structure that can be manually customized
            status_update = f"""
CURRENT STATUS UPDATE ({self.experiment_type.upper()}):
- Your Money Balance: ${money}
- Time Remaining: {time_remaining_min} minutes

- Unread Messages:
{unread_messages_section}

- Recent Failed Actions:
{self._get_failure_summary()}

- Other Participants:
{self._format_participants(public_state)}
"""
        
        # Add communication level specific rules
        communication_level = state.get("communication_level", "chat")
        if communication_level == "broadcast":
            status_update = status_update.replace("- When responding, treat the conversation as a *continuous* communication with other participants, just like how you talk to them face-to-face. There's no need to greet or say hey every time.", "- Mimic the style of a group chat. You don't need to speak all the time. Only join in the chat when you have something to say or when someone responds to you.")
        elif communication_level == "no_chat":
            # Remove message-related instruction for no_chat mode
            status_update = status_update.replace("- When responding, treat the conversation as a *continuous* communication with other participants, just like how you talk to them face-to-face. There's no need to greet or say hey every time.", "")
        
        return status_update.strip()

    def _build_wordguessing_status_update(self, private_state: Dict[str, Any], public_state: Dict[str, Any]) -> str:
        """Build status update specifically for wordguessing experiments."""
        # Get wordguessing-specific data
        role = private_state.get("role", "unknown")
        current_round = private_state.get("current_round", 1)
        score = private_state.get("score", 0)
        assigned_words = private_state.get("assigned_words", [])
        
        # Format assigned words
        if role == "hinter" and assigned_words:
            assigned_words_str = ", ".join(assigned_words)
        else:
            assigned_words_str = "None"
        
        # Time remaining
        time_remaining_sec = int(public_state.get("time_remaining", 0) or 0)
        time_remaining_min = max(0, round(time_remaining_sec / 60))
        
        # Get unread messages for this agent
        unread_messages = self._get_unread_messages_for_agent()
        
        # Format unread messages
        unread_messages_section = "(none)"
        if unread_messages:
            messages_list = []
            for msg in unread_messages[:3]:  # Show last 3 messages
                sender = msg.get("sender_code", "Unknown")
                content = msg.get("content", "")
                messages_list.append(f"- {sender}: {content}")
            unread_messages_section = "\n".join(messages_list)
        
        # Build status update
        status_update = f"""STATUS UPDATE:
CURRENT STATUS UPDATE (WORDGUESSING):
- Your Role: {role}
- Current Round: {current_round}
- Your Score: {score}
- Your Assigned Words: {assigned_words_str}
- Time Remaining: {time_remaining_min} minutes

- Unread Messages:
{unread_messages_section}

- Recent Failed Actions:
{self._get_failure_summary()}

- Other Participants:
{self._format_participants(public_state)}"""
        
        return status_update.strip()

    def _has_voted(self, participant_code: str, session_code: str = None) -> bool:
        """Check if the participant has already submitted a vote"""
        try:
            import psycopg2
            import psycopg2.extras
            import json
            
            db_url = self.tools._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Get session config
            if session_code:
                cur.execute("""
                    SELECT experiment_config FROM sessions WHERE session_code = %s
                """, (session_code,))
            else:
                cur.execute("""
                    SELECT s.experiment_config FROM sessions s
                    JOIN participants p ON s.session_id = p.session_id
                    WHERE p.participant_code = %s
                    ORDER BY p.last_activity_timestamp DESC NULLS LAST, p.created_at DESC
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if result:
                experiment_config = result['experiment_config'] or {}
                hidden_profiles_config = experiment_config.get('hiddenProfiles', {})
                votes = hidden_profiles_config.get('votes', {})
                return participant_code in votes
            
            return False
            
        except Exception as e:
            print(f"Warning: Could not check vote status for {participant_code}: {e}")
            return False

    def _build_hiddenprofiles_status_update(self, private_state: Dict[str, Any], public_state: Dict[str, Any], unread_messages_section: str, time_remaining_min: int, state: Dict[str, Any]) -> str:
        """Build status update specifically for Hidden Profiles experiments with voting prompts."""
        # Get experiment status
        experiment_status = public_state.get("experiment_status", "idle")
        time_remaining_sec = int(public_state.get("time_remaining", 0) or 0)
        
        # Log when this function is called for debugging
        self._log(f"📋 _build_hiddenprofiles_status_update called with experiment_status='{experiment_status}'")
        
        # Check if participant has already voted
        has_voted = self._has_voted(self.participant_code, self.session_code)
        current_vote = None
        if has_voted:
            try:
                import psycopg2
                import psycopg2.extras
                import json
                
                db_url = self.tools._engine.db_connection_string
                conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
                cur = conn.cursor()
                
                if self.session_code:
                    cur.execute("""
                        SELECT experiment_config FROM sessions WHERE session_code = %s
                    """, (self.session_code,))
                else:
                    cur.execute("""
                        SELECT s.experiment_config FROM sessions s
                        JOIN participants p ON s.session_id = p.session_id
                        WHERE p.participant_code = %s
                        ORDER BY p.last_activity_timestamp DESC NULLS LAST, p.created_at DESC
                        LIMIT 1
                    """, (self.participant_code,))
                
                result = cur.fetchone()
                cur.close()
                conn.close()
                
                if result:
                    experiment_config = result['experiment_config'] or {}
                    hidden_profiles_config = experiment_config.get('hiddenProfiles', {})
                    votes = hidden_profiles_config.get('votes', {})
                    current_vote = votes.get(self.participant_code)
            except Exception as e:
                print(f"Warning: Could not get current vote: {e}")
        
        # Get candidate names
        candidate_names = public_state.get("candidate_names", [])
        candidate_list_str = "\n".join([f"- {name}" for name in candidate_names]) if candidate_names else "(none)"
        
        # Determine phase and voting urgency
        # For Hidden Profiles: Agents are initialized after reading phase, so always prompt for initial vote if not voted
        # Also prompt when session ends - agents MUST submit a final vote after experiment completes, even if they already voted
        discussion_ending = time_remaining_min <= 2 or experiment_status == "completed"
        should_prompt_initial_vote = not has_voted  # Always prompt if not voted (agents initialized after reading)
        # For final vote: always prompt when experiment is completed, regardless of whether they've already voted
        # This ensures agents submit their final vote after the discussion ends
        should_prompt_final_vote = discussion_ending and experiment_status == "completed"
        
        # Log voting prompt decision for debugging
        self._log(f"📊 Voting prompt decision: has_voted={has_voted}, discussion_ending={discussion_ending}, experiment_status='{experiment_status}', should_prompt_final_vote={should_prompt_final_vote}")
        
        # Check if there are unread messages
        has_unread_messages = unread_messages_section and unread_messages_section != "(none)"
        
        # Build voting prompt section
        voting_prompt_section = ""
        if should_prompt_final_vote:
            self._log("✅ Building final vote prompt section")
            # Session ending or ended - final vote
            # Check if agent has already voted to customize the message
            if has_voted:
                voting_prompt_section = f"""
! DISCUSSION SESSION HAS ENDED - SUBMIT YOUR FINAL VOTE NOW:
- The experiment has completed. You MUST submit your FINAL VOTE NOW.
- This is your final opportunity to vote for the most suitable candidate.
- You may update your previous vote based on the discussion that occurred.
- Use the submit_vote action with the candidate_name from the candidate list.

AVAILABLE CANDIDATES:
{candidate_list_str}

INSTRUCTIONS:
1. Review the candidate list above
2. Consider all the information from your documents and the discussion
3. Choose ONE candidate (you may change from your initial vote if the discussion changed your mind)
4. Submit your FINAL vote using: {{"type": "submit_vote", "candidate_name": "Candidate Name Here"}}
5. Your response MUST be: {{"actions": [{{"type": "submit_vote", "candidate_name": "..."}}]}}

THIS IS MANDATORY - YOU MUST SUBMIT YOUR FINAL VOTE.
"""
            else:
                voting_prompt_section = """
! DISCUSSION SESSION HAS ENDED - SUBMIT YOUR VOTE NOW:
- The discussion timer has ended. You MUST submit your vote NOW.
- This is your final opportunity to vote for the most suitable candidate.
- Use the submit_vote action with the candidate_name from the candidate list.

AVAILABLE CANDIDATES:
""" + candidate_list_str + """

INSTRUCTIONS:
1. Review the candidate list above
2. Choose ONE candidate based on the information you read and the discussion
3. Submit your vote using: {"type": "submit_vote", "candidate_name": "Candidate Name Here"}
4. Your response MUST be: {"actions": [{"type": "submit_vote", "candidate_name": "..."}]}

THIS IS MANDATORY - YOU CANNOT PROCEED WITHOUT VOTING.
"""
        elif should_prompt_initial_vote:
            # Initial vote (agents are initialized after reading phase completes)
            # If there are unread messages, allow responding to them, but still prompt for vote
            if has_unread_messages:
                voting_prompt_section = f"""
! SUBMIT YOUR INITIAL VOTE NOW
You have finished reading your assigned documents and MUST submit your INITIAL VOTE.
However, you have received new messages from other participants. You may:
1. Respond to the messages first, then submit your vote, OR
2. Submit your vote immediately (recommended if you're ready)

AVAILABLE CANDIDATES:
{candidate_list_str}

INSTRUCTIONS:
1. Review the candidate list above
2. Choose ONE candidate based on the information you read
3. Submit your vote using: {{"type": "submit_vote", "candidate_name": "Candidate Name Here"}}
4. You can also send messages to discuss with other participants before or after voting
"""
            else:
                # No unread messages - focus on voting only
                voting_prompt_section = f"""
! SUBMIT YOUR INITIAL VOTE NOW:
- You have finished reading your assigned documents.
- YOU MUST submit your INITIAL VOTE immediately.
- DO NOT send messages. ONLY submit your vote.
- Your response MUST contain ONLY a submit_vote action - nothing else.

AVAILABLE CANDIDATES:
{candidate_list_str}

INSTRUCTIONS:
1. Review the candidate list above
2. Choose ONE candidate based on the information you read
3. Submit your vote using: {{"type": "submit_vote", "candidate_name": "Candidate Name Here"}}
4. Your response MUST be: {{"actions": [{{"type": "submit_vote", "candidate_name": "..."}}]}}

THIS IS MANDATORY - YOU CANNOT PROCEED WITHOUT VOTING.
"""
            self._log(f"✅ Added urgent voting prompt to status update for {self.participant_code} (has_unread_messages={has_unread_messages})")
        
        # Build status update
        # If agent has voted and has unread messages, encourage responding
        discussion_guidance = ""
        if has_voted and has_unread_messages:
            discussion_guidance = "\n- You have submitted your initial vote. You can now freely engage in discussion with other participants based on the messages you've received."
        elif has_voted:
            discussion_guidance = "\n- You have submitted your initial vote. Feel free to engage in discussion with other participants."
        
        status_update = f"""
CURRENT STATUS UPDATE (HIDDEN PROFILES):

- Experiment Status: {experiment_status.upper()}
- Time Remaining: {time_remaining_min} minutes ({time_remaining_sec} seconds)

- Candidate List:
{candidate_list_str}

{voting_prompt_section}

- Unread Messages:
{unread_messages_section}
{discussion_guidance}

- Recent Failed Actions:
{self._get_failure_summary()}

- Other Participants:
{self._format_participants(public_state)}

Instructions on Aligning with Human Behaviors:
- Engage in meaningful discussion about the candidates based on the information you have.
- Share insights from your candidate document to help the group make an informed decision.
- When you have finished reading and formed an opinion, submit your vote.
- If the discussion is ending or has ended, you MUST submit your vote immediately.
- Do not spam repetitive messages or vote submissions.
- Pay attention to the new messages you received, and do not forget to respond to others' messages.
- When responding, treat the conversation as a *continuous* communication with other participants.
- Do not share your voting preferences with the group (e.g., your initial choice or who you plan to vote for). Voting is an independent decision.
- You are not expected to respond to every message. Participate only when you feel your input is necessary.
- Base your discussion on the information available to you. Avoid repeating points that others have already made.
- During the discussion, do not express excessive agreement. Instead, you should stand your ground based on the information you received and perceived.
- If you believe there is nothing further to discuss, you may suggest ending the conversation and stop generating additional responses.
"""
        
        return status_update.strip()

    def _build_agent_decision_system_prompt(self, state: Dict[str, Any]) -> str:
        """Build the initial system prompt for memory-aware agents using agent decision prompt."""
        template = self._load_agent_decision_prompt_template()
        game = state.get("game_state", {})
        private_state = game.get("private_state", {})
        public_state = game.get("public_state", {})
        
        # Use MBTI profile if personality is an MBTI type, otherwise use basic agent profile
        if self.personality in MBTI_PROFILES:
            prof = MBTI_PROFILES[self.personality]
            print(f"[PROMPT] Using MBTI profile: {self.personality} - {prof['name']}")
        else:
            # Fallback to basic agent profile if personality is not in MBTI_PROFILES
            prof = PERSONALITY_PROFILES.get(self.personality, PERSONALITY_PROFILES["basic_agent"])
            print(f"[PROMPT] Using fallback profile: {self.personality} - {prof['name']}")
        
        # Handle wordguessing experiment differently
        if self.experiment_type == "wordguessing":
            return self._build_wordguessing_prompt(template, private_state, public_state, prof, 0, state.get("communication_level", "chat"))
        
        # Get basic info for other experiment types
        specialty_shape = private_state.get("specialty_shape", "circle")
        starting_money = public_state.get("experiment_config", {}).get("startingMoney", 300)
        current_orders = private_state.get("orders", [])
        
        # Get investment history for DayTrader
        investment_history = "(none)"
        if self.experiment_type == "daytrader":
            try:
                investment_result = self.tools.get_investment_history(self.participant_code, self.session_code)
                if investment_result.get("success") and investment_result.get("investment_history"):
                    investments = investment_result["investment_history"]
                    if investments:
                        investment_lines = []
                        for inv in investments[:10]:  # Show last 10 investments for system prompt
                            price = inv['invest_price']
                            decision_type = inv['invest_decision_type']
                            profit_loss = inv.get('profit_loss')
                            
                            if profit_loss is not None:
                                profit_str = f" (P/L: ${profit_loss:+.2f})"
                            else:
                                profit_str = " (Pending)"
                            
                            investment_lines.append(f"• {decision_type.title()} investment at ${price:.2f}{profit_str}")
                        
                        investment_history = "\n".join(investment_lines)
                    else:
                        investment_history = "(none)"
                else:
                    investment_history = "(none)"
            except Exception as e:
                print(f"Warning: Could not get investment history for DayTrader system prompt: {e}")
                investment_history = "(none)"
        
        # Get assigned essays for Essay Ranking
        assigned_essays = "(none)"
        if self.experiment_type == "essayranking":
            try:
                essays_result = self.tools.get_assigned_essays(self.participant_code, self.session_code)
                if essays_result.get("success") and essays_result.get("essays"):
                    essays = essays_result["essays"]
                    if essays:
                        essay_lines = []
                        for essay in essays:
                            content_info = ""
                            if essay.get('has_content'):
                                word_count = essay.get('word_count', 0)
                                reading_time = essay.get('estimated_reading_time_minutes', 1)
                                content_info = f" ({word_count} words, ~{reading_time}min read)"
                            else:
                                content_info = " (no content available)"
                            
                            essay_lines.append(f"• {essay['essay_id']}: {essay['title']}{content_info}")
                        assigned_essays = "\n".join(essay_lines)
                    else:
                        assigned_essays = "(none)"
                else:
                    assigned_essays = "(none)"
            except Exception as e:
                print(f"Warning: Could not get assigned essays for Essay Ranking system prompt: {e}")
                assigned_essays = "(none)"
        
        # Get assigned document for Hidden Profiles
        assigned_doc = "(none)"
        if self.experiment_type == "hiddenprofiles":
            try:
                docs_result = self.tools.get_assigned_documents(self.participant_code, self.session_code)
                if docs_result.get("candidate_document_text"):
                    # Use the extracted text content - format it nicely for the prompt
                    doc_text = docs_result["candidate_document_text"].strip()
                    if doc_text:
                        assigned_doc = f"Document Content:\n{doc_text}"
                    else:
                        assigned_doc = "(none)"
                elif docs_result.get("candidate_document"):
                    # If text not available, provide document metadata with instructions
                    doc = docs_result["candidate_document"]
                    doc_id = doc.get('doc_id', 'unknown')
                    doc_title = doc.get('title', 'Untitled')
                    assigned_doc = f"Document: {doc_title} (ID: {doc_id})\n\nNote: Document content is not available in the prompt. You can use the get_assigned_documents tool to retrieve the full document content."
                else:
                    assigned_doc = "(none)"
            except Exception as e:
                print(f"Warning: Could not get assigned document for Hidden Profiles system prompt: {e}")
                assigned_doc = "(none)"
        
        # Get configuration parameters
        experiment_config = public_state.get("experiment_config", {})
        price_min = experiment_config.get("minTradePrice", 15)
        price_max = experiment_config.get("maxTradePrice", 35)
        specialty_cost = experiment_config.get("specialtyCost", 10)
        regular_cost = experiment_config.get("regularCost", 25)
        production_time = experiment_config.get("productionTime", 5)
        max_production_num = experiment_config.get("maxProductionNum", 6)
        incentive_money = experiment_config.get("incentiveMoney", 50)
        shape_amount_per_order = experiment_config.get("shapesPerOrder", 3)
        
        # Get communication level
        communication_level = state.get("communication_level", "chat")
        
        # Get participants list
        participants_list = self._format_participants(public_state)
        
        # Get candidate list for Hidden Profiles
        candidate_list = "(none)"
        if self.experiment_type == "hiddenprofiles":
            try:
                candidate_names = public_state.get("candidate_names", [])
                if candidate_names and isinstance(candidate_names, list) and len(candidate_names) > 0:
                    # Format candidate names as a numbered list
                    candidate_lines = []
                    for idx, name in enumerate(candidate_names, 1):
                        candidate_lines.append(f"{idx}. {name}")
                    candidate_list = "\n".join(candidate_lines)
                else:
                    candidate_list = "(none)"
            except Exception as e:
                print(f"Warning: Could not get candidate list for Hidden Profiles system prompt: {e}")
                candidate_list = "(none)"
        
        # Build the system prompt
        system_prompt = template.format(
            participant_code=self.participant_code,
            personality_name=prof["name"],
            personality_description=prof["description"],
            behavior=prof["behavior"],
            communication=prof["communication"],
            mbti_type=self.personality if self.personality in MBTI_PROFILES else "N/A",
            specialty_shape=specialty_shape,
            specialty_cost=specialty_cost,
            regular_cost=regular_cost,
            production_time=production_time,
            max_production_num=max_production_num,
            price_min=price_min,
            price_max=price_max,
            min_trade_price=price_min,  # Add DayTrader-specific variable names
            max_trade_price=price_max,  # Add DayTrader-specific variable names
            starting_money=starting_money,
            participants_list=participants_list,
            communication_level=communication_level,
            incentive_money=incentive_money,
            shape_amount_per_order=shape_amount_per_order,
            current_orders=current_orders,
            investment_history=investment_history,
            assigned_essays=assigned_essays,
            assigned_doc=assigned_doc,
            candidate_list=candidate_list
        )
        
        # Modify the prompt based on communication level
        system_prompt = self._modify_agent_decision_prompt_for_communication_level(system_prompt, communication_level)
        
        return system_prompt

    def _get_fallback_actions(self, communication_level: str, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get fallback actions when LLM fails or returns no actions."""
        # Return empty list instead of sending generic messages
        # This prevents agents from sending unwanted "Hello! Ready to trade" messages
        return []

    def _apply_communication_filters(self, tool_calls: List[Dict[str, Any]], communication_level: str, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply communication level filters to tool calls."""
        if not tool_calls:
            return tool_calls
        
        # For Hidden Profiles, "group_chat" should be treated as broadcast mode
        effective_communication_level = communication_level
        if self.experiment_type == "hiddenprofiles" and communication_level == "group_chat":
            effective_communication_level = "broadcast"
        
        # Filter out messages if in no_chat mode
        if effective_communication_level == "no_chat":
            tool_calls = [call for call in tool_calls if call.get("name") != "send_message"]
        
        # Ensure broadcast mode only sends to "all"
        if effective_communication_level == "broadcast":
            for call in tool_calls:
                if call.get("name") == "send_message":
                    call["arguments"]["recipient"] = "all"
        
        return tool_calls

    async def perceive(self) -> Dict[str, Any]:
        # First, process any completed productions
        try:
            self.tools.process_completed_productions()
        except Exception as e:
            print(f"[WARNING] {self.participant_code} Failed to process completed productions: {e}")
        
        # Then get the current game state
        # CRITICAL FIX: Pass session_code to ensure session isolation
        state = self.tools.get_game_state(self.participant_code, self.session_code)
        
        # Override the timer state with the actual timer state from the API
        try:
            import requests
            # Use the session_code that was passed during agent initialization
            session_code = self.session_code
            
            # Use environment variables for the backend server URL
            backend_host = os.getenv('BACKEND_HOST', 'localhost')
            backend_port = os.getenv('BACKEND_PORT', '5002')
            url = f"http://{backend_host}:{backend_port}/api/experiment/timer-state"
            if session_code:
                url += f"?session_code={session_code}"
            
            timer_response = requests.get(url, timeout=5)
            if timer_response.status_code == 200:
                timer_data = timer_response.json()
                # Update the public state with the correct timer information
                if "game_state" in state and "public_state" in state["game_state"]:
                    old_status = state["game_state"]["public_state"].get("experiment_status", "idle")
                    new_status = timer_data.get("experiment_status", "idle")
                    state["game_state"]["public_state"]["time_remaining"] = timer_data.get("time_remaining", 0)
                    state["game_state"]["public_state"]["experiment_status"] = new_status
                    state["game_state"]["public_state"]["round_duration_minutes"] = timer_data.get("round_duration_minutes", 15)
                    # Log status change for debugging
                    if old_status != new_status:
                        print(f"[{self.participant_code}] ⚡ Status changed: {old_status} -> {new_status}")
                        self._log(f"⚡ Experiment status changed: {old_status} -> {new_status}")
        except Exception as e:
            print(f"[WARNING] {self.participant_code} Failed to get timer state: {e}")
        
        return state

    def _is_reading_phase_complete(self, state: Dict[str, Any]) -> bool:
        """Check if reading phase is complete for Hidden Profiles"""
        if self.experiment_type != "hiddenprofiles":
            return False
        
        game = state.get("game_state", {})
        private_state = game.get("private_state", {})
        public_state = game.get("public_state", {})
        
        # Try to get public_info from public_state first, then fallback to private_state (Hidden Profiles returns it there)
        public_info = public_state.get("public_info")
        if public_info is None:
            # Fallback: Hidden Profiles also returns public_info in participant state
            public_info = private_state.get("public_info")
        
        # public_info can be None, an empty dict, or an object with content
        has_public_info = False
        if public_info is not None:
            if isinstance(public_info, dict):
                # Check if it has content or is not empty
                has_public_info = bool(public_info.get("content")) or bool(public_info.get("doc_id")) or len(public_info) > 0
            elif isinstance(public_info, str):
                has_public_info = public_info != ""
            else:
                has_public_info = True  # Non-empty object
        
        candidate_doc = private_state.get("candidate_document")
        # candidate_doc can be None or an object
        has_candidate_doc = False
        if candidate_doc is not None:
            if isinstance(candidate_doc, dict):
                # Check if it has content or is not empty
                has_candidate_doc = bool(candidate_doc.get("content")) or bool(candidate_doc.get("doc_id")) or len(candidate_doc) > 0
            else:
                has_candidate_doc = True  # Non-empty object
        
        result = has_public_info and has_candidate_doc
        if result:
            self._log(f"✅ Reading phase complete detected: public_info={has_public_info}, candidate_doc={has_candidate_doc}")
        else:
            self._log(f"⏳ Reading phase not complete: public_info={has_public_info} (type: {type(public_info)}), candidate_doc={has_candidate_doc} (type: {type(candidate_doc)})")
        
        return result
    
    async def decide(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        
        # Get communication level from state
        communication_level = state.get("communication_level", "chat")
        
        # For Hidden Profiles: Agents are initialized after reading phase, so they should always vote
        # The status update will prompt them to vote if they haven't already
        
        try:
            # Handle memory-aware LLM policy
            if isinstance(self.policy, MemoryAwareLLMPolicy):
                
                # Initialize memory if not already done
                if not self.policy.is_initialized:
                    system_prompt = self._build_agent_decision_system_prompt(state)
                    self.policy.initialize_memory(system_prompt)
                    self._log_memory("INITIALIZATION", f"Memory initialized with system prompt length: {len(system_prompt)}")
                
                # Build status update and add to memory
                status_update = self._build_status_update(state)
                self.policy.add_status_update(status_update)
                self._log_memory("STATUS_UPDATE", status_update)
                
                # Log a preview of the status update to agent log for debugging
                status_preview = status_update[:200] + "..." if len(status_update) > 200 else status_update
                
                # Mark unread messages as read after agent has seen them
                unread_messages = self._get_unread_messages_for_agent()
                if unread_messages:
                    # In broadcast mode, don't mark broadcast messages as read
                    # Only mark direct messages as read
                    if communication_level == "broadcast":
                        # Mark broadcast messages as seen by this agent
                        broadcast_message_ids = [msg['message_id'] for msg in unread_messages if msg['type'] == "BROADCAST"]
                        for msg_id in broadcast_message_ids:
                            self._mark_broadcast_message_as_seen(msg_id)
                            self._check_and_mark_broadcast_as_read_if_all_seen(msg_id)
                        
                        # Mark direct messages as read (if any)
                        direct_message_ids = [msg['message_id'] for msg in unread_messages if msg['type'] != "BROADCAST"]
                        if direct_message_ids:
                            self._mark_messages_as_read(direct_message_ids)
                            self._log_memory("MESSAGES_MARKED_READ", f"Marked {len(direct_message_ids)} direct messages as read")
                        
                        if broadcast_message_ids:
                            self._log_memory("BROADCAST_MESSAGES_SEEN", f"Marked {len(broadcast_message_ids)} broadcast messages as seen by this agent")
                    else:
                        # In chat mode, mark all messages as read (current behavior)
                        message_ids = [msg['message_id'] for msg in unread_messages]
                        self._mark_messages_as_read(message_ids)
                        self._log_memory("MESSAGES_MARKED_READ", f"Marked {len(message_ids)} messages as read")
                
                # Make decision using memory-aware policy (JSON format)
                result = await self.policy.decide()
                
                if isinstance(result, dict) and "__llm_error__" in result:
                    self._log_memory("ERROR", result["__llm_error__"])
                    print(f"[ERROR] {self.participant_code} Memory-aware LLM failed: {result['__llm_error__']}")
                    # Return fallback actions
                    return self._get_fallback_actions(communication_level, state)
                
                # Handle JSON response
                response_text = result
                self._log_memory("JSON_RESPONSE", response_text or "")
                
                # Parse JSON plan
                plan = self._parse_plan_json(response_text or "") or {}
                try:
                    self._log_memory("PARSED_PLAN", json.dumps(plan, ensure_ascii=False, indent=2))
                except Exception:
                    self._log_memory("PARSED_PLAN", str(plan))
                
                if not plan or not isinstance(plan, dict):
                    # If JSON parsing fails, use fallback actions
                    tool_calls = self._get_fallback_actions(communication_level, state)
                else:
                    # Convert JSON plan to tool calls
                    public_state = state.get("game_state", {}).get("public_state", {})
                    tool_calls = self._map_plan_to_tool_calls(plan, public_state, communication_level)
                
                # Apply communication level filters
                tool_calls = self._apply_communication_filters(tool_calls, communication_level, state)
                
                # For Hidden Profiles: Log warning if agent hasn't voted (they should vote on initialization)
                if self.experiment_type == "hiddenprofiles":
                    has_voted = self._has_voted(self.participant_code, self.session_code)
                    
                    if not has_voted:
                        # Check if tool_calls already includes a submit_vote
                        has_vote_action = any(call.get("name") == "submit_vote" for call in tool_calls)
                        
                        if not has_vote_action:
                            self._log("⚠️ WARNING: Agent has not voted yet - should have received urgent prompt to vote")
                            self._log_memory("MISSING_VOTE_ACTION", "Agent did not include submit_vote despite urgent prompt")
                
                # Only use fallback if the LLM actually failed, not if it intentionally returned no actions
                # Check if the original plan had actions but they were filtered out
                original_actions = plan.get("actions", []) if isinstance(plan, dict) else []
                if not tool_calls and original_actions:
                    # LLM returned actions but they were filtered out - use fallback
                    tool_calls = self._get_fallback_actions(communication_level, state)
                    if tool_calls:
                        self._log_memory("FALLBACK_ACTIONS", f"Using fallback actions: {json.dumps(tool_calls)}")
                    else:
                        self._log_memory("NO_FALLBACK", "No fallback actions available")
                elif not tool_calls and not original_actions:
                    # LLM intentionally returned no actions - respect this decision
                    self._log_memory("INTENTIONAL_WAIT", "LLM chose to wait - no actions taken")
                    tool_calls = []
                
                self._log_memory("TOOL_CALLS", json.dumps(tool_calls, ensure_ascii=False, indent=2))
                return tool_calls
            
            elif isinstance(self.policy, LLMPolicy):
                prompt = self._build_prompt_from_state(state)
                print(f"[LLM_DECIDE] {self.participant_code} Current LLM mode: {self.llm_mode}")
                
                # Mark unread messages as read after agent has seen them (for non-memory-aware agents)
                unread_messages = self._get_unread_messages_for_agent()
                if unread_messages:
                    # In broadcast mode, don't mark broadcast messages as read
                    # Only mark direct messages as read
                    if communication_level == "broadcast":
                        # Mark broadcast messages as seen by this agent
                        broadcast_message_ids = [msg['message_id'] for msg in unread_messages if msg['type'] == "BROADCAST"]
                        for msg_id in broadcast_message_ids:
                            self._mark_broadcast_message_as_seen(msg_id)
                            self._check_and_mark_broadcast_as_read_if_all_seen(msg_id)
                        
                        # Mark direct messages as read (if any)
                        direct_message_ids = [msg['message_id'] for msg in unread_messages if msg['type'] != "BROADCAST"]
                        if direct_message_ids:
                            self._mark_messages_as_read(direct_message_ids)
                    else:
                        # In chat mode, mark all messages as read (current behavior)
                        message_ids = [msg['message_id'] for msg in unread_messages]
                        self._mark_messages_as_read(message_ids)
                
                if self.llm_mode == "function":
                    tools_spec = self.tools.get_tools_spec(self.policy.api_provider)
                    fc_system = "You are an autonomous trading agent. Use tools to act; no extra text."
                    self._log_llm("FN_CALLING_PROMPT", prompt)
                    
                    result = await self.policy.decide(fc_system, prompt, tools_spec=tools_spec)
                    
                    if isinstance(result, dict) and "__llm_error__" in result:
                        self._log_llm("FN_CALLING_ERROR", result["__llm_error__"])
                        print(f"[ERROR] {self.participant_code} LLM function calling failed: {result['__llm_error__']}")
                        # Return empty list instead of fallback actions
                        return []
                    
                    tool_calls = result
                    try:
                        self._log_llm("FN_CALLING_CALLS", json.dumps(tool_calls, ensure_ascii=False, indent=2))
                    except Exception:
                        self._log_llm("FN_CALLING_CALLS", str(tool_calls))
                    
                    
                    # Filter out messages if in no_chat mode
                    if communication_level == "no_chat" and tool_calls:
                        tool_calls = [call for call in tool_calls if call.get("name") != "send_message"]
                    
                    # Ensure broadcast mode only sends to "all"
                    if communication_level == "broadcast" and tool_calls:
                        for call in tool_calls:
                            if call.get("name") == "send_message":
                                call["arguments"]["recipient"] = "all"
                    
                    # For Hidden Profiles: Log warning if agent hasn't voted
                    if self.experiment_type == "hiddenprofiles":
                        has_voted = self._has_voted(self.participant_code, self.session_code)
                        
                        if not has_voted:
                            # Check if tool_calls already includes a submit_vote
                            has_vote_action = any(call.get("name") == "submit_vote" for call in tool_calls)
                            
                            if not has_vote_action:
                                self._log("⚠️ WARNING: Agent has not voted yet - should have received urgent prompt to vote")
                    
                    if not tool_calls:
                        # Return empty list instead of fallback actions
                        tool_calls = []
                    
                    return tool_calls
                else:  # self.llm_mode == "json"
                    system_prompt = (
                        "You are a decisive trading agent. Respond with strictly valid JSON only. "
                        "Do not include code fences, comments, or extra text."
                    )
                    self._log_llm("PROMPT", prompt)
                    result = await self.policy.decide(system_prompt, prompt, tools_spec=None)
                    if isinstance(result, dict) and "__llm_error__" in result:
                        self._log_llm("JSON_PLANNING_ERROR", result["__llm_error__"])
                        # Return empty list instead of fallback actions
                        return []
                    response_text = result
                    self._log_llm("RAW_OUTPUT", response_text or "")
                    plan = self._parse_plan_json(response_text or "") or {}
                    try:
                        self._log_llm("PARSED_PLAN", json.dumps(plan, ensure_ascii=False, indent=2))
                    except Exception:
                        self._log_llm("PARSED_PLAN", str(plan))
                    if not plan or not isinstance(plan, dict):
                        tools_spec = self.tools.get_tools_spec(self.policy.api_provider)
                        fc_system = "You are an autonomous trading agent. Use tools to act; no extra text."
                        self._log_llm("FALLBACK_FN_CALLING_PROMPT", prompt)
                        result = await self.policy.decide(fc_system, prompt, tools_spec=tools_spec)
                        if isinstance(result, dict) and "__llm_error__" in result:
                            self._log_llm("FALLBACK_FN_CALLING_ERROR", result["__llm_error__"])
                            # Return empty list instead of fallback actions
                            return []
                        tool_calls = result
                        try:
                            self._log_llm("FALLBACK_FN_CALLING_CALLS", json.dumps(tool_calls, ensure_ascii=False, indent=2))
                        except Exception:
                            self._log_llm("FALLBACK_FN_CALLING_CALLS", str(tool_calls))
                        if not tool_calls:
                            return SimplePolicy().decide(state)
                        return tool_calls
                    public_state = state.get("game_state", {}).get("public_state", {})
                    calls = self._map_plan_to_tool_calls(plan, public_state, communication_level)
                    
                    # Filter out messages if in no_chat mode
                    if communication_level == "no_chat" and calls:
                        calls = [call for call in calls if call.get("name") != "send_message"]
                    
                    # Ensure broadcast mode only sends to "all"
                    if communication_level == "broadcast" and calls:
                        for call in calls:
                            if call.get("name") == "send_message":
                                call["arguments"]["recipient"] = "all"
                    
                    # For Hidden Profiles: Log warning if agent hasn't voted
                    if self.experiment_type == "hiddenprofiles":
                        has_voted = self._has_voted(self.participant_code, self.session_code)
                        
                        if not has_voted:
                            # Check if calls already includes a submit_vote
                            has_vote_action = any(call.get("name") == "submit_vote" for call in calls)
                            
                            if not has_vote_action:
                                self._log("⚠️ WARNING: Agent has not voted yet - should have received urgent prompt to vote")
                    
                    if not calls:
                        # Return empty list instead of fallback actions
                        calls = []
                    return calls
            else:
                return self.policy.decide(state)
        except Exception as e:
            error_msg = f"decide() failed: {e} | Exception type: {type(e).__name__}"
            print(f"[CRITICAL ERROR] {self.participant_code} {error_msg}")
            print(f"[CRITICAL ERROR] Exception type: {type(e).__name__}")
            import traceback
            traceback_str = traceback.format_exc()
            print(f"[CRITICAL ERROR] Traceback: {traceback_str}")
            
            # Also log to file for persistence
            self._log(f"CRITICAL ERROR: {error_msg}")
            self._log(f"TRACEBACK: {traceback_str}")
            
            # Return empty list instead of fallback actions
            return []

    async def act(self, tool_calls: List[Dict[str, Any]]):
        for call in tool_calls:
            name = call.get("name")
            args = call.get("arguments", {}) if isinstance(call, dict) else {}
            if not name or not isinstance(args, dict):
                continue
            
            # Check if participant_code is incorrect and log it
            if args.get("participant_code") != self.participant_code:
                self._log(f"WARNING: Tool call had incorrect participant_code '{args.get('participant_code')}', correcting to '{self.participant_code}'")
            
            # Ensure participant_code is present and correct
            args["participant_code"] = self.participant_code
            
            # CRITICAL FIX: Add session_code to all tool calls for proper session isolation
            if self.session_code:
                args["session_code"] = self.session_code
            
            # Validate transaction_id for respond_to_trade_offer
            if name == "respond_to_trade_offer":
                transaction_id = args.get("transaction_id", "")
                if not transaction_id or transaction_id == "transaction_id_from_pending_offers" or "transaction_id_from_pending_offers" in transaction_id or transaction_id == "transaction_id":
                    self._log(f"ERROR: Invalid transaction_id '{transaction_id}' for respond_to_trade_offer. Must be a valid transaction ID from pending offers.")
                    continue
            
            try:
                # For Hidden Profiles submit_vote: Check if this is initial or final vote BEFORE submitting
                vote_type = None
                if name == 'submit_vote' and self.experiment_type == 'hiddenprofiles':
                    # Check if agent has voted before
                    had_voted_before = self._has_voted(self.participant_code, self.session_code)
                    
                    # Get experiment status to determine if it's final vote
                    # Use the timer-state API endpoint to get current experiment status
                    is_session_ending = False
                    try:
                        import requests
                        backend_host = os.getenv('BACKEND_HOST', 'localhost')
                        backend_port = os.getenv('BACKEND_PORT', '5002')
                        url = f"http://{backend_host}:{backend_port}/api/experiment/timer-state"
                        if self.session_code:
                            url += f"?session_code={self.session_code}"
                        timer_response = requests.get(url, timeout=2)
                        if timer_response.status_code == 200:
                            timer_data = timer_response.json()
                            experiment_status = timer_data.get("experiment_status", "idle")
                            time_remaining = timer_data.get("time_remaining", 0) or 0
                            is_session_ending = experiment_status == "completed" or int(time_remaining) <= 0
                    except Exception as e:
                        # If we can't check, assume it's not ending (safer for initial vote detection)
                        # Only log if it's not a connection error (which is expected in some test scenarios)
                        if "Connection" not in str(e) and "timeout" not in str(e).lower():
                            self._log(f"Warning: Could not check experiment status for vote type: {e}")
                        pass
                    
                    if had_voted_before or is_session_ending:
                        vote_type = "FINAL VOTE"
                    else:
                        vote_type = "INITIAL VOTE"
                
                result = self.tools.execute_tool_call(name, args)
                ok = result.get("success", False)
                error_message = result.get("message") or result.get("error") or "Unknown error"
                self._log(f"{name} -> {'ok' if ok else 'fail'} | {error_message}")
                
                # Record failed actions for feedback to the agent
                if not ok:
                    self._record_failure(name, args, error_message)
                    
                    # Add failed action to memory for MemoryAwareLLMPolicy
                    if isinstance(self.policy, MemoryAwareLLMPolicy):
                        failure_summary = f"FAILED ACTION: {name} - {error_message}"
                        self.policy.add_agent_response(failure_summary)
                        self._log_memory("FAILED_ACTION", f"{name}: {error_message}")
                
                # Add successful action to memory for MemoryAwareLLMPolicy
                if ok and isinstance(self.policy, MemoryAwareLLMPolicy):
                    success_summary = f"SUCCESSFUL ACTION: {name}"
                    self.policy.add_agent_response(success_summary)
                    self._log_memory("SUCCESSFUL_ACTION", f"{name}: {result.get('message', 'Success')}")
                
                # For Hidden Profiles: Log initial and final votes with detailed information
                if ok and name == 'submit_vote' and self.experiment_type == 'hiddenprofiles' and vote_type:
                    candidate_name = args.get('candidate_name', 'Unknown')
                    self._log(f"📊 {vote_type}: {self.participant_code} submitted vote for candidate: {candidate_name}")
                    self._log_memory(f"{vote_type}", f"Submitted vote for candidate: {candidate_name}")
                    
                    # Also log to LLM log for visibility
                    self._log_llm(f"{vote_type}", f"Agent {self.participant_code} voted for: {candidate_name}")
                
                # Emit WebSocket events for successful trade operations
                if ok and name in ['create_trade_offer', 'respond_to_trade_offer', 'cancel_trade_offer']:
                    try:
                        from app import socketio
                        from datetime import datetime
                        
                        if name == 'create_trade_offer':
                            socketio.emit('new_trade_offer', {
                                'sender': args.get('participant_code'),
                                'target': args.get('recipient'),
                                'offer_type': args.get('offer_type'),
                                'shape': args.get('shape'),
                                'quantity': args.get('quantity'),
                                'price_per_unit': args.get('price_per_unit'),
                                'transaction_id': result.get('transaction_id'),
                                'timestamp': datetime.now().isoformat()
                            }, room='researcher')
                        elif name == 'respond_to_trade_offer':
                            socketio.emit('trade_offer_response', {
                                'responder': args.get('participant_code'),
                                'transaction_id': args.get('transaction_id'),
                                'response': args.get('response'),
                                'timestamp': datetime.now().isoformat()
                            }, room='researcher')
                            
                            # If trade was accepted, also emit trade completion event
                            if args.get('response') == 'accept':
                                socketio.emit('trade_completed', {
                                    'transaction_id': args.get('transaction_id'),
                                    'accepted_by': args.get('participant_code'),
                                    'timestamp': datetime.now().isoformat()
                                }, room='researcher')
                        elif name == 'cancel_trade_offer':
                            socketio.emit('trade_offer_cancelled', {
                                'canceller': args.get('participant_code'),
                                'transaction_id': args.get('transaction_id'),
                                'timestamp': datetime.now().isoformat()
                            }, room='researcher')
                    except Exception as e:
                        self._log(f"Warning: Failed to emit WebSocket event for {name}: {e}")
                
                # Emit WebSocket events for successful message operations
                if ok and name == 'send_message':
                    try:
                        from app import socketio
                        from datetime import datetime
                        
                        message_data = {
                            'sender': args.get('participant_code'),
                            'recipient': args.get('recipient'),
                            'content': args.get('content'),
                            'message_id': result.get('message_id'),
                            'timestamp': datetime.now().isoformat()
                        }
                        # Send to participants room
                        socketio.emit('new_message', message_data, room='participants')
                        # Also send to researchers room so researcher dashboard gets updates
                        socketio.emit('new_message', message_data, room='researchers')
                    except Exception as e:
                        self._log(f"Warning: Failed to emit WebSocket event for {name}: {e}")
                        
            except Exception as e:
                                        self._log(f"Action error for {name}: {e}")

    def _get_proposer_code_for_transaction(self, transaction_id: str) -> str:
        """Get the proposer's participant_code for a given transaction_id"""
        try:
            import psycopg2
            import psycopg2.extras
            
            db_url = self.tools._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # First try to find by short_id
            cur.execute("""
                SELECT t.proposer_id, p.participant_code
                FROM transactions t
                JOIN participants p ON t.proposer_id = p.participant_id
                WHERE t.short_id = %s
            """, (transaction_id,))
            
            result = cur.fetchone()
            if result:
                cur.close()
                conn.close()
                return result['participant_code']
            
            # If not found by short_id, try by transaction_id (UUID)
            cur.execute("""
                SELECT t.proposer_id, p.participant_code
                FROM transactions t
                JOIN participants p ON t.proposer_id = p.participant_id
                WHERE t.transaction_id = %s
            """, (transaction_id,))
            
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if result:
                return result['participant_code']
            
            return None
            
        except Exception as e:
            print(f"Warning: Could not get proposer code for transaction {transaction_id}: {e}")
            return None

    def request_stop(self):
        """Signal the agent loop to stop early."""
        if not self._stop_event.is_set():
            self._stop_event.set()

    async def run_single_cycle(self):
        """Run a single perception-decision-action cycle (for passive agents triggered by messages)"""
        try:
            if self.is_passive:
                self._log(f"PASSIVE agent triggered - running single cycle (message received)")
            else:
                self._log(f"Triggered single cycle (message received)")
            state = await self.perceive()
            
            # Check experiment status - skip actions if not running
            experiment_status = state.get("game_state", {}).get("public_state", {}).get("experiment_status", "idle")
            if experiment_status == "completed":
                # For Hidden Profiles: Ensure final vote is submitted before stopping
                # Agents MUST submit a final vote after experiment completes, even if they already voted
                if self.experiment_type == "hiddenprofiles":
                    has_voted = self._has_voted(self.participant_code, self.session_code)
                    # Always prompt for final vote when experiment is completed
                    # This allows agents to update their vote based on the discussion
                    self._log("⚠️ EXPERIMENT COMPLETED - Agent must submit final vote.")
                    # Ensure state has the correct experiment_status for status update building
                    if "game_state" in state and "public_state" in state["game_state"]:
                        state["game_state"]["public_state"]["experiment_status"] = "completed"
                        self._log(f"✅ Updated state experiment_status to 'completed' for final vote prompt")
                    # Call decide() which will build the status update with final vote prompt
                    tool_calls = await self.decide(state)
                    if tool_calls:
                        await self.act(tool_calls)
                        # Check if a vote was submitted
                        has_vote_action = any(call.get("name") == "submit_vote" for call in tool_calls)
                        if has_vote_action:
                            self._log("✅ Final vote submitted")
                        else:
                            self._log("⚠️ WARNING: Agent did not submit final vote - may have already voted or chose not to update")
                    else:
                        self._log("⚠️ WARNING: Agent did not generate any actions")
                
                self._log(f"Experiment status is '{experiment_status}' - session completed. Skipping cycle.")
                return
            elif experiment_status != "running":
                self._log(f"Experiment status is '{experiment_status}', skipping actions. Waiting for 'running' status...")
                # Even if experiment is not running, we should still add status update for passive agents
                # so they can see new messages
                if self.is_passive:
                    self._log("⚠️ Experiment not running, but adding status update for passive agent to see new messages")
                    try:
                        if isinstance(self.policy, MemoryAwareLLMPolicy):
                            # Initialize memory if not already done
                            if not self.policy.is_initialized:
                                self._log("📋 Initializing memory for passive agent (experiment not running)")
                                system_prompt = self._build_agent_decision_system_prompt(state)
                                self.policy.initialize_memory(system_prompt)
                                self._log_memory("INITIALIZATION", f"Memory initialized with system prompt length: {len(system_prompt)}")
                                self._log("✅ Memory initialized for passive agent")
                            
                            # Now add status update
                            status_update = self._build_status_update(state)
                            self.policy.add_status_update(status_update)
                            self._log_memory("STATUS_UPDATE", status_update)
                            self._log(f"✅ Status update added for passive agent (experiment not running, length: {len(status_update)} chars)")
                    except Exception as e:
                        self._log(f"Error adding status update: {e}")
                        import traceback
                        self._log(f"Traceback: {traceback.format_exc()}")
                return
            
            # For Hidden Profiles: Agents should vote on initialization (they're initialized after reading phase)
            # Status update will prompt them to vote
            
            self._log("📊 Running decide() - status update will be added here")
            
            # Verify status update will be included
            if isinstance(self.policy, MemoryAwareLLMPolicy):
                history_length = len(self.policy.conversation_history)
                self._log(f"📊 Conversation history length before decide(): {history_length}")
                # Check if last entry is a status update
                if history_length > 0:
                    last_entry = self.policy.conversation_history[-1]
                    if last_entry.get("role") == "user" and "STATUS UPDATE" in last_entry.get("content", ""):
                        self._log("✅ Status update is in conversation history and will be sent to LLM")
                    else:
                        self._log(f"⚠️ Last conversation entry is not a status update: {last_entry.get('role')}")
            
            tool_calls = await self.decide(state)
            # Safer logging of tool_calls
            try:
                self._log(f"Tool calls: {json.dumps(tool_calls, ensure_ascii=False)}")
            except Exception as log_e:
                self._log(f"Tool calls (unparseable): {str(tool_calls)[:200]}... (log error: {log_e})")
            await self.act(tool_calls)
            self._log("✅ Single cycle completed")
        except Exception as e:
            self._log(f"Error in single cycle: {e}")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")

    async def run(self):
        """Main agent loop"""
        # Passive agents don't run on a timer - they only respond to external triggers
        if self.is_passive:
            self._log("Starting PASSIVE agent - will only respond to messages (no timer-based cycles)")
            self._log("Agent is waiting for external triggers via run_single_cycle()")
            
            # For Hidden Profiles: Only prompt passive agents to vote if experiment has started (status is 'running')
            # Passive agents should NOT vote before the human participant submits their first vote
            if self.experiment_type == "hiddenprofiles":
                try:
                    state = await self.perceive()
                    experiment_status = state.get("game_state", {}).get("public_state", {}).get("experiment_status", "idle")
                    has_voted = self._has_voted(self.participant_code, self.session_code)
                    
                    # Only prompt for initial vote if experiment is running AND agent hasn't voted yet
                    if experiment_status == "running" and not has_voted:
                        tool_calls = await self.decide(state)
                        if tool_calls:
                            await self.act(tool_calls)
                            self._log("Vote cycle completed during passive agent initialization")
                    elif experiment_status != "running":
                        self._log(f"ℹ️ PASSIVE AGENT INITIALIZATION: Experiment status is '{experiment_status}' - waiting for experiment to start before voting")
                    elif has_voted:
                        self._log("ℹ️ PASSIVE AGENT INITIALIZATION: Agent has already voted - skipping initial vote prompt")
                except Exception as e:
                    self._log(f"Error checking vote status on passive agent initialization: {e}")
            
            # Wait indefinitely until stopped, checking periodically for experiment completion
            check_interval = 30  # Check every 30 seconds if experiment is still running
            while not self._stop_event.is_set():
                try:
                    # Periodically check if experiment is completed
                    state = await self.perceive()
                    experiment_status = state.get("game_state", {}).get("public_state", {}).get("experiment_status", "idle")
                    if experiment_status == "completed":
                        # For Hidden Profiles: Ensure final vote is submitted before stopping
                        # Agents MUST submit a final vote after experiment completes, even if they already voted
                        if self.experiment_type == "hiddenprofiles":
                            has_voted = self._has_voted(self.participant_code, self.session_code)
                            # Always prompt for final vote when experiment is completed
                            # This allows agents to update their vote based on the discussion
                            self._log("⚠️ EXPERIMENT COMPLETED - Agent must submit final vote before stopping.")
                            # Ensure state has the correct experiment_status for status update building
                            if "game_state" in state and "public_state" in state["game_state"]:
                                state["game_state"]["public_state"]["experiment_status"] = "completed"
                                self._log(f"✅ Updated state experiment_status to 'completed' for final vote prompt")
                            # Call decide() which will build the status update with final vote prompt
                            tool_calls = await self.decide(state)
                            if tool_calls:
                                await self.act(tool_calls)
                                # Check if a vote was submitted
                                has_vote_action = any(call.get("name") == "submit_vote" for call in tool_calls)
                                if has_vote_action:
                                    self._log("✅ Final vote submitted before session end")
                                else:
                                    self._log("⚠️ WARNING: Agent did not submit final vote - may have already voted or chose not to update")
                            else:
                                self._log("⚠️ WARNING: Agent did not generate any actions before session end")
                        
                        self._log(f"Experiment status is '{experiment_status}' - session completed. Stopping passive agent.")
                        break
                except Exception as e:
                    self._log(f"Error checking experiment status: {e}")
                
                # Wait for check_interval seconds, checking stop event periodically
                waited = 0
                while waited < check_interval and not self._stop_event.is_set():
                    await asyncio.sleep(1)  # Check every second
                    waited += 1
                
                if self._stop_event.is_set():
                    break
            
            self._log("Passive agent loop finished - stopped by external request or experiment completed")
            return
        
        # Active agents run on a timer
        self._log(f"Starting ACTIVE agent loop with interval_seconds={self.interval_seconds}")
        
        # For Hidden Profiles: Only prompt agents to vote if experiment has started (status is 'running')
        # Agents should NOT vote before the human participant submits their first vote
        if self.experiment_type == "hiddenprofiles":
            try:
                state = await self.perceive()
                experiment_status = state.get("game_state", {}).get("public_state", {}).get("experiment_status", "idle")
                has_voted = self._has_voted(self.participant_code, self.session_code)
                
                # Only prompt for initial vote if experiment is running AND agent hasn't voted yet
                if experiment_status == "running" and not has_voted:
                    tool_calls = await self.decide(state)
                    if tool_calls:
                        await self.act(tool_calls)
                        self._log("Vote cycle completed during initialization")
                elif experiment_status != "running":
                    self._log(f"ℹ️ INITIALIZATION: Experiment status is '{experiment_status}' - waiting for experiment to start before voting")
                elif has_voted:
                    self._log("ℹ️ INITIALIZATION: Agent has already voted - skipping initial vote prompt")
            except Exception as e:
                self._log(f"Error checking vote status on initialization: {e}")
        
        # Add initial delay before first inference
        self._log(f"Waiting {self.interval_seconds} seconds before first inference...")
        await asyncio.sleep(self.interval_seconds)
        
        end_time = datetime.now() + timedelta(minutes=self.duration_minutes)
        iteration = 0
        while datetime.now() < end_time and not self._stop_event.is_set():
            iteration += 1
            self._current_cycle = iteration  # Track current cycle for failure recording
            try:
                self._log(f"Cycle #{iteration} (interval: {self.interval_seconds}s)")
                state = await self.perceive()
                
                # Check experiment status - stop if completed, skip actions if not running
                experiment_status = state.get("game_state", {}).get("public_state", {}).get("experiment_status", "idle")
                # Log status check for debugging
                if iteration % 4 == 0:  # Log every 4th cycle to avoid spam
                    self._log(f"Status check: experiment_status='{experiment_status}' (cycle #{iteration})")
                if experiment_status == "completed":
                    # For Hidden Profiles: Ensure final vote is submitted before stopping
                    # Agents MUST submit a final vote after experiment completes, even if they already voted
                    if self.experiment_type == "hiddenprofiles":
                        has_voted = self._has_voted(self.participant_code, self.session_code)
                        # Always prompt for final vote when experiment is completed
                        # This allows agents to update their vote based on the discussion
                        self._log("⚠️ EXPERIMENT COMPLETED - Agent must submit final vote before stopping.")
                        # Ensure state has the correct experiment_status for status update building
                        if "game_state" in state and "public_state" in state["game_state"]:
                            state["game_state"]["public_state"]["experiment_status"] = "completed"
                            self._log(f"✅ Updated state experiment_status to 'completed' for final vote prompt")
                        # Call decide() which will build the status update with final vote prompt
                        tool_calls = await self.decide(state)
                        if tool_calls:
                            await self.act(tool_calls)
                            # Check if a vote was submitted
                            has_vote_action = any(call.get("name") == "submit_vote" for call in tool_calls)
                            if has_vote_action:
                                self._log("✅ Final vote submitted before session end")
                            else:
                                self._log("⚠️ WARNING: Agent did not submit final vote - may have already voted or chose not to update")
                        else:
                            self._log("⚠️ WARNING: Agent did not generate any actions before session end")
                    
                    self._log(f"Experiment status is '{experiment_status}' - session completed. Stopping agent loop.")
                    break
                elif experiment_status != "running":
                    self._log(f"Experiment status is '{experiment_status}', skipping actions. Waiting for 'running' status...")
                    await asyncio.sleep(self.interval_seconds)
                    continue
                
                tool_calls = await self.decide(state)
                # Safer logging of tool_calls
                try:
                    self._log(f"Tool calls: {json.dumps(tool_calls, ensure_ascii=False)}")
                except Exception as log_e:
                    self._log(f"Tool calls (unparseable): {str(tool_calls)[:200]}... (log error: {log_e})")
                await self.act(tool_calls)
            except Exception as e:
                self._log(f"Error: {e}")
            await asyncio.sleep(self.interval_seconds)
        
        # Add final log entry with reason for stopping
        if self._stop_event.is_set():
            self._log("Agent loop finished - stopped by external request")
        elif datetime.now() >= end_time:
            self._log("Agent loop finished - reached maximum duration")
        else:
            self._log("Agent loop finished - session completed")


async def run_single_agent(
    participant_code: str,
    use_llm: bool = False,
    llm_model: str = "gpt-4o-mini",
    interval_seconds: int = 10,
    duration_minutes: int = 15,
    personality: str = "basic_agent",
    use_memory: bool = False,
    max_memory_length: int = 20,
    session_code: str = None,
    experiment_type: str = "shapefactory",
):
    controller = AgentController(
        participant_code=participant_code,
        use_llm=use_llm,
        llm_model=llm_model,
        interval_seconds=interval_seconds,
        duration_minutes=duration_minutes,
        personality=personality,
        use_memory=use_memory,
        max_memory_length=max_memory_length,
        session_code=session_code,
        experiment_type=experiment_type,
    )
    await controller.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a serverless experiment agent")
    parser.add_argument("--participant", required=True, help="Participant code (e.g., agent01)")
    parser.add_argument("--llm", action="store_true", help="Use OpenAI LLM for policy")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model name")
    parser.add_argument("--interval", type=int, default=10, help="Seconds between cycles")
    parser.add_argument("--minutes", type=int, default=15, help="Duration of the run")
    parser.add_argument("--personality", default="basic_agent", choices=list(PERSONALITY_PROFILES.keys()))
    parser.add_argument("--memory", action="store_true", help="Use memory-aware LLM policy")
    parser.add_argument("--max-memory", type=int, default=20, help="Maximum memory length for conversation history")
    parser.add_argument("--session-code", help="Session code for proper session isolation")
    parser.add_argument("--experiment-type", default="shapefactory", help="Experiment type (e.g., shapefactory, daytrader, essayranking, wordguessing)")
    args = parser.parse_args()

    asyncio.run(
        run_single_agent(
            participant_code=args.participant,
            use_llm=args.llm,
            llm_model=args.model,
            interval_seconds=args.interval,
            duration_minutes=args.minutes,
            personality=args.personality,
            use_memory=args.memory,
            max_memory_length=args.max_memory,
                session_code=args.session_code,
                experiment_type=args.experiment_type,
        )
    )
