from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
import random
import psycopg2
import psycopg2.extras
import psycopg2.pool
import os
from dotenv import load_dotenv
import secrets
import jwt
import asyncio
import threading
import time
import hashlib
import json
import logging
from itertools import combinations_with_replacement

# Import the working MCP system
from agent_runner import AgentController
import inspect as _inspect
print(f"[BOOT] AgentController loaded from: {_inspect.getfile(AgentController)}")

# Add GameEngine import
from game_engine import GameEngine
from game_engine_factory import GameEngineFactory

# Add Human Logger import
from human_logger import get_human_logger, cleanup_human_logs, stop_human_logging_for_session

# Import MTurk Service
from mturk_service import mturk_service

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)
# Configure Socket.IO with proper error handling
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',  # Use threading mode to avoid async issues
    logger=False,  # Disable Socket.IO internal logging to reduce noise
    engineio_logger=False,  # Disable Engine.IO logging
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e8  # Increase buffer size for large messages
)

# Note: Don't add Flask error handlers here as they can interfere with Socket.IO WebSocket connections
# Socket.IO has its own error handling mechanism

# Add global error handler for Socket.IO
@socketio.on_error_default
def default_error_handler(e):
    """Handle Socket.IO errors gracefully"""
    try:
        print(f"❌ Socket.IO error: {e}")
        import traceback
        traceback.print_exc()
        try:
            emit('error', {'message': str(e)})
        except:
            # If emit fails, just log - don't let it cause another error
            pass
    except Exception as handler_error:
        # If we can't emit an error, just log it
        print(f"❌ Error in error handler: {handler_error}")

# Set up logging
logger = logging.getLogger(__name__)

# JWT secret key for authentication
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key-change-in-production')
JWT_ALGORITHM = 'HS256'

# Database connection pool
db_pool = None

def initialize_db_pool():
    """Initialize the database connection pool"""
    global db_pool
    try:
        database_url = f"postgresql://{os.getenv('DATABASE_USER', '')}:{os.getenv('DATABASE_PASSWORD', '')}@{os.getenv('DATABASE_HOST', 'localhost')}:{os.getenv('DATABASE_PORT', '5432')}/{os.getenv('DATABASE_NAME', 'shape_factory_research')}"
        
        # Parse the URL to get connection parameters
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        
        db_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=5,      # Minimum connections in pool
            maxconn=50,     # Maximum connections in pool
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path[1:],  # Remove leading slash
            user=parsed.username,
            password=parsed.password,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        print(f"✅ Database connection pool initialized: minconn=5, maxconn=50")
    except Exception as e:
        print(f"❌ Failed to initialize database connection pool: {e}")
        db_pool = None

# Initialize the connection pool
initialize_db_pool()

# Track timer state globally - now session-specific
timer_states = {}  # Dictionary to store timer states for each session
timer_threads = {}  # Dictionary to store timer threads for each session

def cleanup_db_pool():
    """Clean up database connection pool on application shutdown"""
    global db_pool
    if db_pool is not None:
        try:
            db_pool.closeall()
            print("✅ Database connection pool closed")
        except Exception as e:
            print(f"❌ Error closing database connection pool: {e}")
        finally:
            db_pool = None

# Register cleanup function for application shutdown
import atexit
atexit.register(cleanup_db_pool)

def initialize_timer_state(session_code: str = None):
    """Initialize timer state with proper defaults for a specific session"""
    if session_code:
        timer_states[session_code] = {
            'experiment_status': 'idle',
            'time_remaining': 0,
            'round_duration_minutes': 15,
            'timer_active': False,
            'round_start_time': None
        }
        print(f"✅ Timer state initialized for session: {session_code}")
    else:
        # Initialize global default state (for backward compatibility)
        global timer_state
        timer_state = {
            'experiment_status': 'idle',
            'time_remaining': 0,
            'round_duration_minutes': 15,
            'timer_active': False,
            'round_start_time': None
        }
        print("✅ Global timer state initialized")

def get_timer_state(session_code: str = None):
    """Get timer state for a specific session or global state"""
    if session_code:
        # If session doesn't exist in timer_states, initialize it
        if session_code not in timer_states:
            initialize_timer_state(session_code)
        return timer_states[session_code]
    else:
        # Return global state for backward compatibility
        global timer_state
        if 'timer_state' not in globals():
            initialize_timer_state()
        return timer_state

def set_timer_state(session_code: str, state: dict):
    """Set timer state for a specific session"""
    timer_states[session_code] = state
    print(f"✅ Timer state updated for session: {session_code}")

# Initialize global timer state on startup
initialize_timer_state()

# Add global experiment config consistent with UI defaults
experiment_config_state = {
    'numRounds': 5,
    'roundDuration': 15,  # Now matches sessionDuration since we only use session time
    'startingMoney': 200,
    'specialtyCost': 15,
    'regularCost': 40,
    'minTradePrice': 15,
    'maxTradePrice': 100,
    'productionTime': 35,  # Changed from 5 to 30
    'maxProductionNum': 3,  # Changed from maxSpecialtyAmount to maxProductionNum
    'sessionDuration': 15,
    'sessionId': '',  # Empty by default - no active session
    'communicationLevel': 'chat',
    'awarenessDashboard': 'on',
    'shapesPerOrder': 4,  # Changed from 8 to 5
    'agentPerceptionTimeWindow': 15,  # Added default value
    'incentiveMoney': 60,  # Added incentive money
    'numShapeTypes': 3,  # Number of shape types available in the session
}

# Helper to load session config from DB (DEPRECATED - use get_session_config instead)
def load_session_config(session_code: str = None):
    if not session_code:
        return  # Don't load anything if no session code provided
    
    # This function is deprecated - use get_session_config instead
    # It no longer updates the global state to prevent session isolation issues
    print(f"⚠️ load_session_config is deprecated - use get_session_config instead for session {session_code}")
    return get_session_config(session_code)

# Helper to get session-specific config
def get_session_config(session_code: str = None):
    """Get configuration for a specific session"""
    if not session_code:
        # Return default config if no session code provided
        config = experiment_config_state.copy()
        config['experiment_type'] = 'shapefactory'  # Default experiment type
        config['session_status'] = 'idle'  # Default session status
        return config
    
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT experiment_config, experiment_type, session_status FROM sessions WHERE session_code = %s
            """, (session_code,))
            row = cur.fetchone()
            cur.close()
            
        if row and row.get('experiment_config'):
            config = row['experiment_config']
            # Add experiment_type and session_status to the config
            config['experiment_type'] = row.get('experiment_type', 'shapefactory')
            config['session_status'] = row.get('session_status', 'idle')
            return config
        else:
            # Return default config if session doesn't exist
            config = experiment_config_state.copy()
            config['experiment_type'] = 'shapefactory'  # Default experiment type
            config['session_status'] = 'idle'  # Default session status
            return config
    except Exception as e:
        print(f"Warning: failed to get session config: {e}")
        config = experiment_config_state.copy()
        config['experiment_type'] = 'shapefactory'  # Default experiment type
        config['session_status'] = 'idle'  # Default session status
        return config

# Load config at startup
# Deferred until after get_db_connection is defined
# load_session_config('DEMO001')

def broadcast_timer_update(session_code: str = None):
    """Broadcast current timer state to all connected clients"""
    timer_state = get_timer_state(session_code)
    
    # Get session_started_at from database for accurate time calculation
    session_started_at = None
    if session_code:
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT session_started_at 
                FROM sessions 
                WHERE session_code = %s
            """, (session_code,))
            result = cur.fetchone()
            if result and result.get('session_started_at'):
                session_started_at = result['session_started_at'].isoformat() if hasattr(result['session_started_at'], 'isoformat') else str(result['session_started_at'])
            cur.close()
            return_db_connection(conn)
        except Exception as e:
            # Silently fail - use timer_state round_start_time as fallback
            pass
    
    timer_update_data = {
        'experiment_status': timer_state['experiment_status'],
        'time_remaining': timer_state['time_remaining'],
        'round_duration_minutes': timer_state['round_duration_minutes'],
        'session_code': session_code,
        'session_started_at': session_started_at or timer_state.get('round_start_time'),
        'round_start_time': timer_state.get('round_start_time')
    }
    
    # Broadcast to all clients (for backward compatibility)
    socketio.emit('timer_update', timer_update_data)
    
    # Also broadcast to session-specific rooms if session_code is provided
    if session_code:
        socketio.emit('timer_update', timer_update_data, room=f'session_{session_code}')

def timer_worker(session_code: str = None):
    """Background timer that updates every second for a specific session"""
    import time
    
    print(f"🚀 Timer worker started for session: {session_code}")
    
    while True:
        # Get current timer state each iteration to ensure we have the latest state
        timer_state = get_timer_state(session_code)
        
        # Check if timer is still active
        if not timer_state.get('timer_active', False):
            print(f"Timer worker for session {session_code} stopping - timer_active is False")
            break
        
        # Always broadcast current state for synchronization
        broadcast_timer_update(session_code)
        
        # Only decrement timer when running
        if timer_state['experiment_status'] == 'running' and timer_state['time_remaining'] > 0:
            timer_state['time_remaining'] -= 1
            
            # Check if session is complete
            if timer_state['time_remaining'] <= 0:
                # End experiment
                timer_state['experiment_status'] = 'completed'
                timer_state['timer_active'] = False
                print(f"Timer for session {session_code} completed")
                
                # Automatically stop agents for this session
                try:
                    deactivate_result = deactivate_agents_for_session(session_code)
                    if deactivate_result.get('success'):
                        print(f"✅ Automatically stopped {deactivate_result.get('agents_stopped', 0)} agents for completed session {session_code}")
                    else:
                        print(f"⚠️ Failed to automatically stop agents for session {session_code}: {deactivate_result.get('error', 'Unknown error')}")
                except Exception as e:
                    print(f"⚠️ Error stopping agents for completed session {session_code}: {e}")
                
                break
        
        time.sleep(1)

def start_session_timer(session_code: str):
    """Start the timer thread for a specific session"""
    global timer_threads
    
    # Initialize timer state for this session if it doesn't exist
    if session_code not in timer_states:
        initialize_timer_state(session_code)
    
    # Stop existing timer for this session if it's running
    if session_code in timer_threads and timer_threads[session_code].is_alive():
        timer_states[session_code]['timer_active'] = False
        timer_threads[session_code].join(timeout=1)
    
    # Start new timer thread for this session
    timer_states[session_code]['timer_active'] = True
    timer_threads[session_code] = threading.Thread(target=timer_worker, args=(session_code,), daemon=True)
    timer_threads[session_code].start()
    print(f"✅ Timer started for session: {session_code}")

def stop_session_timer(session_code: str):
    """Stop the timer thread for a specific session"""
    global timer_threads
    
    if session_code in timer_states:
        timer_states[session_code]['timer_active'] = False
    
    if session_code in timer_threads and timer_threads[session_code].is_alive():
        timer_threads[session_code].join(timeout=1)
        print(f"✅ Timer stopped for session: {session_code}")

def start_global_timer():
    """Start the global timer thread (for backward compatibility)"""
    start_session_timer(None)

def stop_global_timer():
    """Stop all timer threads"""
    global timer_threads
    for session_code in list(timer_threads.keys()):
        stop_session_timer(session_code)

def get_unique_specialty_for_session(session_code, cursor):
    """
    Get a specialty shape for a session using cycling assignment.
    
    Algorithm:
    - Count existing participants in the session
    - Use modulo operation to cycle through available shapes
    - This ensures every N participants (where N = number of available shapes) 
      get the same specialty shape
    
    Example:
    - 3 shapes: ['circle', 'square', 'triangle']
    - 6 participants: circle, square, triangle, circle, square, triangle
    - Every 2 participants share the same specialty
    """
    # Get all existing specialties for this session
    cursor.execute("""
        SELECT specialty_shape 
        FROM participants 
        WHERE session_code = %s AND specialty_shape IS NOT NULL
    """, (session_code,))
    
    existing_specialties = [row[0] for row in cursor.fetchall()]
    
    # Get available shapes for this session based on configuration
    available_shapes = get_available_shapes_for_session(session_code)
    
    # Algorithm: Cycling specialty assignment
    # If we have no existing specialties, start with the first available shape
    if not existing_specialties:
        return available_shapes[0] if available_shapes else 'circle'
    
    # Count how many participants we have so far
    participant_count = len(existing_specialties)
    
    # Use modulo to cycle through available shapes
    # This ensures every N participants (where N = len(available_shapes)) get the same specialty
    shape_index = participant_count % len(available_shapes)
    assigned_specialty = available_shapes[shape_index]
    
    # Additional safety check
    if not assigned_specialty or assigned_specialty == '0':
        assigned_specialty = 'circle'
    
    return assigned_specialty


def get_participant_session_id(participant_code: str, session_code: str = None):
    """Get the session_id for a participant from the database"""
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # CRITICAL FIX: Use session_code for proper session isolation
            if session_code:
                cur.execute("""
                    SELECT session_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (participant_code, session_code))
            else:
                # Fallback to activity-based lookup if session_code not provided
                cur.execute("""
                    SELECT session_id FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            
            return result['session_id'] if result else None
            
    except Exception as e:
        print(f"Warning: Could not get session_id for {participant_code}: {e}")
        return None

def get_db_connection():
    """Get database connection from pool"""
    global db_pool
    if db_pool is None:
        # Fallback to direct connection if pool is not available
        database_url = f"postgresql://{os.getenv('DATABASE_USER', '')}:{os.getenv('DATABASE_PASSWORD', '')}@{os.getenv('DATABASE_HOST', 'localhost')}:{os.getenv('DATABASE_PORT', '5432')}/{os.getenv('DATABASE_NAME', 'shape_factory_research')}"
        return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        conn = db_pool.getconn()
        if conn is None:
            raise Exception("Failed to get connection from pool")
        return conn
    except Exception as e:
        print(f"❌ Error getting connection from pool: {e}")
        # Fallback to direct connection
        database_url = f"postgresql://{os.getenv('DATABASE_USER', '')}:{os.getenv('DATABASE_PASSWORD', '')}@{os.getenv('DATABASE_HOST', 'localhost')}:{os.getenv('DATABASE_PORT', '5432')}/{os.getenv('DATABASE_NAME', 'shape_factory_research')}"
        return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)

def return_db_connection(conn):
    """Return database connection to pool"""
    global db_pool
    if conn is None:
        return
    
    # Check if connection is closed
    try:
        if conn.closed:
            return  # Connection already closed, nothing to do
    except:
        pass
    
    if db_pool is not None:
        try:
            # Try to return to pool - this will only work if the connection came from the pool
            db_pool.putconn(conn)
            return
        except Exception as e:
            # Connection might not be from the pool (e.g., fallback direct connection)
            # or connection might be in a bad state
            # Just close it instead
            try:
                conn.close()
            except:
                pass
            # Only log if it's not the expected "unkeyed connection" error
            if "unkeyed" not in str(e).lower():
                print(f"❌ Error returning connection to pool: {e}")
    else:
        # No pool, just close the connection directly
        try:
            conn.close()
        except:
            pass

class DatabaseConnection:
    """Context manager for database connections using the connection pool"""
    
    def __init__(self):
        self.conn = None
    
    def __enter__(self):
        self.conn = get_db_connection()
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn is not None:
            return_db_connection(self.conn)

def run_migrations():
    """Run database migrations to fix known issues"""
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            
            # Check if the problematic trigger exists
            cur.execute("""
                SELECT trigger_name 
                FROM information_schema.triggers 
                WHERE trigger_name = 'trigger_complete_transaction'
            """)
            
            trigger_exists = cur.fetchone()
            
            if trigger_exists:
                print("🔧 [MIGRATION] Found problematic trigger_complete_transaction, disabling it...")
                
                # Drop the trigger
                cur.execute("DROP TRIGGER IF EXISTS trigger_complete_transaction ON transactions")
                
                # Add comment to the function
                cur.execute("""
                    COMMENT ON FUNCTION complete_transaction() IS 'DISABLED: This function was causing duplicate inventory updates. Inventory updates are now handled directly in game_engine.py'
                """)
                
                conn.commit()
                print("✅ [MIGRATION] Successfully disabled trigger_complete_transaction")
            else:
                print("✅ [MIGRATION] trigger_complete_transaction already disabled")
            
            # Update sessions_experiment_type_check constraint to include 'hiddenprofiles'
            print("🔧 [MIGRATION] Updating sessions experiment_type constraint to include 'hiddenprofiles'...")
            try:
                # Check if constraint already includes hiddenprofiles
                cur.execute("""
                    SELECT constraint_name, check_clause 
                    FROM information_schema.check_constraints 
                    WHERE constraint_name = 'sessions_experiment_type_check'
                """)
                constraint_info = cur.fetchone()
                
                if constraint_info:
                    check_clause = constraint_info[1] if constraint_info else ''
                    if 'hiddenprofiles' not in check_clause:
                        # Drop the old constraint
                        cur.execute("""
                            ALTER TABLE sessions 
                            DROP CONSTRAINT IF EXISTS sessions_experiment_type_check
                        """)
                        
                        # Add the new constraint with 'hiddenprofiles'
                        cur.execute("""
                            ALTER TABLE sessions 
                            ADD CONSTRAINT sessions_experiment_type_check 
                            CHECK (
                                (experiment_type::text = ANY (ARRAY['shapefactory'::character varying, 'daytrader'::character varying, 'essayranking'::character varying, 'wordguessing'::character varying, 'ecl_custom'::character varying, 'hiddenprofiles'::character varying])) 
                                OR (experiment_type::text ~~ 'custom_%'::text) 
                                OR (experiment_type IS NULL)
                            )
                        """)
                        
                        # Update the constraint comment
                        cur.execute("""
                            COMMENT ON CONSTRAINT sessions_experiment_type_check ON sessions IS 'Allows valid experiment types: shapefactory, daytrader, essayranking, wordguessing, ecl_custom, hiddenprofiles, or custom_* (can also be NULL)'
                        """)
                        
                        conn.commit()
                        print("✅ [MIGRATION] Successfully updated sessions_experiment_type_check constraint")
                    else:
                        print("✅ [MIGRATION] sessions_experiment_type_check already includes 'hiddenprofiles'")
                else:
                    print("⚠️ [MIGRATION] Could not find sessions_experiment_type_check constraint")
            except Exception as e:
                print(f"⚠️ [MIGRATION] Warning: Could not update constraint (may already be updated): {e}")
            
            cur.close()
        
    except Exception as e:
        print(f"❌ [MIGRATION] Error running migrations: {e}")

# Now that DB helper exists, load session config
# Don't load any session by default - let the frontend register sessions as needed
# try:
#     load_session_config('DEMO001')
# except Exception as _e:
#     print(f"Warning: failed to load session config (deferred): {_e}")

# -------- In-process Agent Manager (replaces MCP client manager) --------
AGENT_THREADS = {}

# Single basic agent type - no more different agent types
BASIC_AGENT_TYPE = 'basic_agent'

def _start_agent_thread(participant_code: str, agent_type: str = None, use_llm: bool = True,
                        interval_seconds: int = 10, duration_minutes: int = 60,
                        llm_model: str = 'gpt-4o-mini', use_memory: bool = True, max_memory_length: int = 20,
                        session_code: str = None, experiment_type: str = "shapefactory"):
    # Create a composite key for session-aware agent tracking
    agent_key = f"{session_code}:{participant_code}" if session_code else participant_code
    
    if agent_key in AGENT_THREADS and AGENT_THREADS[agent_key]['thread'].is_alive():
        return False
    
    # Get the agent perception time window from session-specific config
    # Use session-specific config instead of global state to get the correct interval
    session_config = get_session_config(session_code) if session_code else experiment_config_state
    agent_perception_time = session_config.get('agentPerceptionTimeWindow', 15)  # Default to 15 instead of 10
    print(f"🔧 Agent {participant_code}: Using agentPerceptionTimeWindow={agent_perception_time} from session config")
    
    # For Hidden Profiles: Check if agent is active or passive
    if experiment_type == 'hiddenprofiles':
        # Get initiative setting for this agent
        hidden_profiles_config = experiment_config_state.get('hiddenProfiles', {})
        participant_initiatives = hidden_profiles_config.get('participantInitiatives', {})
        initiative = participant_initiatives.get(participant_code, 'active')
        
        if initiative == 'passive':
            # Passive agents only respond to messages, not on a timer
            # Set a very long interval to effectively disable auto-trigger
            agent_perception_time = 999999  # Very long interval
            print(f"Starting PASSIVE agent {participant_code} - will only respond to messages (interval={agent_perception_time}s)")
        else:
            # Active agents use the configured perception window with ±2 second randomization
            # to avoid multiple agents sending messages at the same time
            base_interval = agent_perception_time
            random_offset = random.choice([-2, -1, 1, 2])  # Random integer offset from [-2, -1, 0, 1, 2] seconds
            agent_perception_time = max(1.0, base_interval + random_offset)  # Ensure minimum 1 second
            print(f"Starting ACTIVE agent {participant_code} with interval_seconds={agent_perception_time:.2f} (base={base_interval}s, randomized ±1s)")
    else:
        print(f"Starting agent {participant_code} with interval_seconds={agent_perception_time} (from config)")
    
    print(f"Memory management: use_memory={use_memory}, max_memory_length={max_memory_length}")
    
    stop_event = threading.Event()
    try:
        # Import the assign_random_mbti function
        from agent_runner import assign_random_mbti
        
        controller = AgentController(
            participant_code=participant_code,
            use_llm=use_llm,
            llm_model=llm_model,
            interval_seconds=agent_perception_time,
            duration_minutes=duration_minutes,
            stop_event=stop_event,
            personality=assign_random_mbti(),  # Assign random MBTI personality
            use_memory=use_memory,
            max_memory_length=max_memory_length,
            session_code=session_code,
            experiment_type=experiment_type
        )
    except Exception as e:
        print(f"Failed to initialize AgentController for {participant_code}: {e}")
        return False

    def _runner():
        try:
            asyncio.run(controller.run())
        except Exception as e:
            print(f"Agent {participant_code} loop error: {e}")

    th = threading.Thread(target=_runner, daemon=True)
    th.start()
    AGENT_THREADS[agent_key] = {
        'thread': th,
        'stop_event': stop_event,
        'controller': controller,
        'agent_type': agent_type,
        'use_llm': use_llm,
        'llm_model': llm_model,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'session_code': session_code,
        'participant_code': participant_code,
    }
    return True

def _stop_agent_thread(participant_code: str, session_code: str = None) -> bool:
    # Create a composite key for session-aware agent tracking
    agent_key = f"{session_code}:{participant_code}" if session_code else participant_code
    
    info = AGENT_THREADS.get(agent_key)
    if not info:
        return False
    try:
        info['controller'].request_stop()
        info['stop_event'].set()
        info['thread'].join(timeout=3)
    except Exception:
        pass
    finally:
        AGENT_THREADS.pop(agent_key, None)
    return True

def _trigger_passive_agent(participant_code: str, session_code: str = None):
    """Trigger a passive agent to run a single perception cycle (for Hidden Profiles)"""
    try:
        agent_key = f"{session_code}:{participant_code}" if session_code else participant_code
        print(f"[PASSIVE TRIGGER] Looking for agent with key: {agent_key}")
        print(f"[PASSIVE TRIGGER] Available agent keys: {list(AGENT_THREADS.keys())}")
        
        info = AGENT_THREADS.get(agent_key)
        
        if not info:
            print(f"[PASSIVE TRIGGER] Agent {agent_key} not found in AGENT_THREADS")
            return False
        
        if not info.get('thread') or not info['thread'].is_alive():
            print(f"[PASSIVE TRIGGER] Agent {agent_key} thread is not alive")
            return False
        
        controller = info.get('controller')
        if not controller:
            print(f"[PASSIVE TRIGGER] Agent {agent_key} has no controller")
            return False
        
        print(f"[PASSIVE TRIGGER] Successfully found agent {agent_key}, triggering cycle...")
        
        # Run a single cycle asynchronously in a new thread to avoid blocking
        def _run_cycle():
            try:
                asyncio.run(controller.run_single_cycle())
                print(f"[PASSIVE TRIGGER] Completed cycle for agent {participant_code}")
            except Exception as e:
                print(f"[PASSIVE TRIGGER ERROR] Error triggering passive agent {participant_code}: {e}")
                import traceback
                print(traceback.format_exc())
        
        trigger_thread = threading.Thread(target=_run_cycle, daemon=True)
        trigger_thread.start()
        print(f"[PASSIVE TRIGGER] Started trigger thread for agent {participant_code}")
        return True
    except Exception as e:
        print(f"[PASSIVE TRIGGER ERROR] Error in _trigger_passive_agent: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def _trigger_all_agents_in_session(session_code: str):
    """Trigger all agents (both active and passive) in a session to run a cycle immediately"""
    try:
        triggered_count = 0
        for agent_key, info in AGENT_THREADS.items():
            # Check if this agent belongs to the session
            if session_code and not agent_key.startswith(f"{session_code}:"):
                continue
            
            if not info or not info.get('thread') or not info['thread'].is_alive():
                continue
            
            controller = info.get('controller')
            if not controller:
                continue
            
            participant_code = info.get('participant_code')
            if not participant_code:
                continue
            
            # Trigger the agent (works for both active and passive)
            def _run_cycle():
                try:
                    asyncio.run(controller.run_single_cycle())
                except Exception as e:
                    print(f"Error triggering agent {participant_code}: {e}")
            
            trigger_thread = threading.Thread(target=_run_cycle, daemon=True)
            trigger_thread.start()
            triggered_count += 1
        
        if triggered_count > 0:
            print(f"Triggered {triggered_count} agent(s) in session {session_code} for reading phase completion check")
        return triggered_count
    except Exception as e:
        print(f"Error in _trigger_all_agents_in_session: {e}")
        import traceback
        print(traceback.format_exc())
        return 0

def _check_and_trigger_agents_for_reading_phase(session_code: str):
    """Check if reading phase is complete for all participants and trigger agents if so"""
    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get session config
            cur.execute("""
                SELECT experiment_config FROM sessions WHERE session_code = %s
            """, (session_code,))
            session_result = cur.fetchone()
            
            if not session_result:
                return False
            
            experiment_config = session_result['experiment_config'] or {}
            hidden_profiles_config = experiment_config.get('hiddenProfiles', {})
            
            # Check if public info exists
            public_info = hidden_profiles_config.get('publicInfo')
            has_public_info = public_info is not None and public_info != ""
            
            if not has_public_info:
                return False
            
            # Get all participants in the session
            cur.execute("""
                SELECT participant_code FROM participants 
                WHERE session_code = %s
            """, (session_code,))
            participants = cur.fetchall()
            
            if not participants:
                return False
            
            # Check if all participants have candidate documents assigned
            participant_candidate_docs = hidden_profiles_config.get('participantCandidateDocs', {})
            all_have_docs = True
            
            for participant in participants:
                participant_code = participant['participant_code']
                # Remove session suffix for lookup
                base_code = participant_code.rsplit('_', 1)[0] if '_' in participant_code else participant_code
                
                if base_code not in participant_candidate_docs:
                    all_have_docs = False
                    break
            
            if all_have_docs:
                # Reading phase is complete - trigger all agents
                print(f"Reading phase complete for session {session_code} - triggering all agents")
                _trigger_all_agents_in_session(session_code)
                return True
            
            return False
            
    except Exception as e:
        print(f"Error checking reading phase completion: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def activate_agents_for_session(session_code: str, use_llm: bool = True, llm_model: str = 'gpt-4o-mini', 
                               use_memory: bool = True, max_memory_length: int = 20) -> dict:
    try:
        # First, reload the session configuration to ensure we have the latest settings
        load_session_config(session_code)
        print(f"Loaded session config for {session_code}, agentPerceptionTimeWindow: {experiment_config_state.get('agentPerceptionTimeWindow', 10)}")
        print(f"Memory management: use_memory={use_memory}, max_memory_length={max_memory_length}")
        
        # Check if experiment is running before activating agents
        session_timer_state = get_timer_state(session_code)
        if session_timer_state['experiment_status'] != 'running':
            print(f"⚠️ Warning: Attempting to activate agents when experiment status is '{session_timer_state['experiment_status']}', not 'running'")
            print(f"   Agents will be started but will wait for experiment to begin before acting")
        
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT participant_code, COALESCE(agent_type, 'basic_agent') as agent_type 
                FROM participants 
                WHERE session_code = %s AND is_agent = true
            """, (session_code,))
            agents = cur.fetchall()
            cur.close()
        
        # Get experiment type from session config
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        print(f"🔍 Activating agents for experiment type: {experiment_type}")
        
        started = 0
        for a in agents:
            if _start_agent_thread(a['participant_code'], None, 
                                 use_llm=use_llm, llm_model=llm_model, 
                                 use_memory=use_memory, max_memory_length=max_memory_length,
                                 session_code=session_code, experiment_type=experiment_type):
                started += 1
        return {'success': True, 'agents_started': started, 'total_agents': len(agents), 
                'use_llm': use_llm, 'llm_model': llm_model, 'use_memory': use_memory, 'max_memory_length': max_memory_length}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def deactivate_agents_for_session(session_code: str) -> dict:
    try:
        # Determine which running agents belong to this session
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT participant_code 
            FROM participants 
            WHERE session_code = %s AND is_agent = true
        """, (session_code,))
        session_agents = {row[0] for row in cur.fetchall()}
        
        # For Hidden Profiles: Clean up participantInitiatives from experiment_config
        cur.execute("""
            SELECT experiment_type, experiment_config 
            FROM sessions 
            WHERE session_code = %s
        """, (session_code,))
        session_row = cur.fetchone()
        if session_row and session_row['experiment_type'] == 'hiddenprofiles':
            experiment_config = session_row['experiment_config'] or {}
            if 'hiddenProfiles' in experiment_config and 'participantInitiatives' in experiment_config['hiddenProfiles']:
                # Remove initiatives for agents being deactivated
                for agent_code in session_agents:
                    experiment_config['hiddenProfiles']['participantInitiatives'].pop(agent_code, None)
                    # Also try without session suffix
                    base_code = agent_code.rsplit('_', 1)[0] if '_' in agent_code else agent_code
                    experiment_config['hiddenProfiles']['participantInitiatives'].pop(base_code, None)
                
                # Update experiment_config
                cur.execute("""
                    UPDATE sessions 
                    SET experiment_config = %s 
                    WHERE session_code = %s
                """, (json.dumps(experiment_config), session_code))
                conn.commit()
                print(f"🧹 Cleaned up participantInitiatives for deactivated agents in session {session_code}")
        
        cur.close()
        return_db_connection(conn)
        stopped = 0
        for agent_key in list(AGENT_THREADS.keys()):
            info = AGENT_THREADS.get(agent_key)
            if info and info.get('session_code') == session_code:
                # For Hidden Profiles: Ensure agent submits final vote before deactivation
                if info.get('controller'):
                    try:
                        controller = info['controller']
                        # Check if this is a Hidden Profiles experiment
                        if controller.experiment_type == "hiddenprofiles":
                            # Check if agent has voted
                            has_voted = controller._has_voted(controller.participant_code, session_code)
                            if not has_voted:
                                print(f"[FINAL VOTE] Agent {info.get('participant_code')} has not voted - triggering final vote before deactivation")
                                try:
                                    # Trigger a final vote cycle
                                    import asyncio
                                    state = asyncio.run(controller.perceive())
                                    tool_calls = asyncio.run(controller.decide(state))
                                    if tool_calls:
                                        asyncio.run(controller.act(tool_calls))
                                        print(f"[FINAL VOTE] Final vote submitted for agent {info.get('participant_code')}")
                                    else:
                                        print(f"[FINAL VOTE WARNING] Agent {info.get('participant_code')} did not generate vote action")
                                except Exception as vote_error:
                                    print(f"[FINAL VOTE ERROR] Failed to trigger final vote for agent {info.get('participant_code')}: {vote_error}")
                        
                        # Add final log entry before stopping the agent
                        controller._log(f"Session {session_code} ended - agent logging stopped")
                        controller._log_llm("SESSION_END", f"Session {session_code} ended - LLM logging stopped")
                        controller._log_memory("SESSION_END", f"Session {session_code} ended - memory logging stopped")
                        print(f"[STOP] Added final log entries for agent: {info.get('participant_code')} (session: {session_code})")
                    except Exception as log_error:
                        print(f"[STOP ERROR] Failed to add final log entries for agent {info.get('participant_code')}: {log_error}")
                
                if _stop_agent_thread(info.get('participant_code'), session_code):
                    stopped += 1
        return {'success': True, 'agents_stopped': stopped}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def cleanup_agent_logs():
    """Delete agent-related log files (LLM and legacy) under backend/logs and session folders."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(base_dir, 'logs')
        if not os.path.isdir(logs_dir):
            return {'success': True, 'deleted': 0}
        deleted = 0
        # Delete top-level agent logs (legacy/no-session)
        for name in os.listdir(logs_dir):
            if name.startswith(('llm_', 'agent_', 'memory_')) and name.endswith('.log'):
                try:
                    os.remove(os.path.join(logs_dir, name))
                    deleted += 1
                except Exception as e:
                    print(f"Failed to remove log {name}: {e}")
        # Recurse into session folders
        for item in os.listdir(logs_dir):
            item_path = os.path.join(logs_dir, item)
            if os.path.isdir(item_path):
                for name in os.listdir(item_path):
                    if name.startswith(('llm_', 'agent_', 'memory_')) and name.endswith('.log'):
                        try:
                            os.remove(os.path.join(item_path, name))
                            deleted += 1
                        except Exception as e:
                            print(f"Failed to remove log {item}/{name}: {e}")
                # Remove empty session folder
                try:
                    if not os.listdir(item_path):
                        os.rmdir(item_path)
                except Exception as e:
                    print(f"Failed to remove empty session folder {item}: {e}")
        return {'success': True, 'deleted': deleted}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def cleanup_human_logs():
    """Delete human-related log files under backend/logs and session folders."""
    try:
        # Use the improved cleanup function from human_logger.py
        from human_logger import cleanup_human_logs as cleanup_human_logs_impl
        cleanup_human_logs_impl()
        return {'success': True, 'deleted': 'See console output for details'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def cleanup_all_logs():
    """Delete all log files (agent and human) under backend/logs."""
    try:
        agent_result = cleanup_agent_logs()
        human_result = cleanup_human_logs()
        
        total_deleted = agent_result.get('deleted', 0) + human_result.get('deleted', 0)
        
        if agent_result.get('success') and human_result.get('success'):
            return {'success': True, 'deleted': total_deleted}
        else:
            return {
                'success': False, 
                'error': f"Agent cleanup: {agent_result.get('error', 'success')}, Human cleanup: {human_result.get('error', 'success')}"
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_agents_status(session_code: str) -> dict:
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT participant_code, agent_type, is_agent
            FROM participants 
            WHERE session_code = %s AND is_agent = true
        """, (session_code,))
        agents = cur.fetchall()
        cur.close()
        return_db_connection(conn)
        active = {}
        for a in agents:
            code = a['participant_code']
            # Create the agent key to check if this agent is running
            agent_key = f"{session_code}:{code}"
            running = agent_key in AGENT_THREADS and AGENT_THREADS[agent_key]['thread'].is_alive()
            
            # Extract display name for agents (remove session code suffix)
            display_name = code
            if '_' in code:
                display_name = code.rsplit('_', 1)[0]
            
            active[display_name] = {
                'agent_type': a.get('agent_type'),
                'running': running,
                'use_llm': AGENT_THREADS.get(agent_key, {}).get('use_llm') if running else None,
                'llm_model': AGENT_THREADS.get(agent_key, {}).get('llm_model') if running else None,
                'started_at': AGENT_THREADS.get(agent_key, {}).get('started_at') if running else None,
                'internal_code': code,  # Keep internal code for reference
            }
        return {'success': True, 'total_agents': len(agents), 'active_agents': active}
    except Exception as e:
        return {'success': False, 'error': str(e), 'total_agents': 0, 'active_agents': {}}

# ============================================================================
# BASIC API ENDPOINTS
# ============================================================================

@app.route('/api/health')
def health():
    """Health check endpoint for Docker"""
    try:
        # Quick database health check
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return_db_connection(conn)
        
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 503

@app.route('/api/hello')
def hello():
    return jsonify({"message": "Hello from Shape Factory Backend!"})

@app.route('/api/check-api-keys')
def check_api_keys():
    """Check if API keys are present"""
    openai_key = os.getenv("OPENAI_API_KEY")
    claude_key = os.getenv("CLAUDE_API_KEY")
    keys_present = bool(openai_key or claude_key)
    return jsonify({"keys_present": keys_present})

@app.route('/api/data')
def get_data():
    """Get basic data for testing"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get session info
        cur.execute("SELECT session_id, session_code FROM sessions LIMIT 1")
        session_data = cur.fetchone()
        
        # Get participant count
        cur.execute("SELECT COUNT(*) FROM participants")
        participant_count = cur.fetchone()[0]
        
        cur.close()
        return_db_connection(conn)
        
        return jsonify({
            "session": session_data,
            "participant_count": participant_count,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# LOG CLEANUP API ENDPOINTS
# ============================================================================

@app.route('/api/cleanup/agent-logs', methods=['POST'])
def api_cleanup_agent_logs():
    """Clean up agent log files"""
    try:
        result = cleanup_agent_logs()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/cleanup/human-logs', methods=['POST'])
def api_cleanup_human_logs():
    """Clean up human log files"""
    try:
        result = cleanup_human_logs()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/cleanup/all-logs', methods=['POST'])
def api_cleanup_all_logs():
    """Clean up all log files (agent and human)"""
    try:
        result = cleanup_all_logs()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================================
# SOCKET.IO EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection with error handling"""
    try:
        print(f"Client connected: {request.sid}")
        return True
    except Exception as e:
        print(f"❌ Error during client connection: {e}")
        import traceback
        traceback.print_exc()
        return False

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection with error handling"""
    try:
        print(f"Client disconnected: {request.sid}")
    except Exception as e:
        print(f"❌ Error during client disconnection: {e}")
        import traceback
        traceback.print_exc()

@socketio.on('register_researcher')
def handle_researcher_register(data):
    """Handle researcher registration"""
    try:
        session_id = data.get('session_id', '')  # Empty by default
        print(f"🔬 Researcher registered for session: {session_id or 'none'}")
        
        # Join researcher room for targeted broadcasts
        join_room('researcher')
        # Join session-specific room if session_id is provided
        if session_id:
            join_room(f'researcher_session_{session_id}')
        
        # Send current timer state to the researcher
        timer_state = get_timer_state(session_id)
        socketio.emit('timer_update', {
            'experiment_status': timer_state['experiment_status'],
            'time_remaining': timer_state['time_remaining'],
            'round_duration_minutes': timer_state['round_duration_minutes'],
            'session_code': session_id
        }, room='researcher')
        
        print(f"✅ Researcher registered and timer state sent")
        
    except Exception as e:
        print(f"❌ Error in researcher registration: {e}")
        socketio.emit('error', {'message': 'Registration failed'})

@socketio.on('register_participant')
def handle_participant_register(data):
    """Handle participant registration"""
    try:
        participant_code = data.get('participant_code')
        participant_type = data.get('participant_type', 'human')
        session_code = data.get('session_code', '')  # Empty by default
        
        if not participant_code:
            socketio.emit('error', {'message': 'Participant code required'})
            return
        
        print(f"👤 Participant registered: {participant_code} ({participant_type}) for session: {session_code or 'none'}")
        
        # Join participant room for targeted broadcasts (include session code for isolation)
        join_room(f'participant_{participant_code}_{session_code}')
        # Also join a shared 'participants' room to receive group-wide events like new_message
        join_room('participants')
        # Join session-specific room for session isolation
        if session_code:
            join_room(f'session_{session_code}')
        
        # Send current timer state to the participant
        timer_state = get_timer_state(session_code)
        socketio.emit('timer_update', {
            'experiment_status': timer_state['experiment_status'],
            'time_remaining': timer_state['time_remaining'],
            'round_duration_minutes': timer_state['round_duration_minutes'],
            'session_code': session_code
        }, room=f'participant_{participant_code}_{session_code}')
        
        # Emit confirmation
        emit('participant_registered', {
            'participant_code': participant_code,
            'participant_type': participant_type,
            'session_code': session_code,
            'timestamp': datetime.now().isoformat()
        })
        
        print(f"✅ Participant {participant_code} registered and timer state sent")
        
    except Exception as e:
        print(f"❌ Error in participant registration: {e}")
        socketio.emit('error', {'message': 'Registration failed'})

@socketio.on('participant_heartbeat')
def handle_participant_heartbeat(data):
    """Handle participant heartbeat"""
    try:
        participant_code = data.get('participant_code')
        session_code = data.get('session_code')
        if participant_code:
            # Update last activity in database
            conn = get_db_connection()
            cur = conn.cursor()
            
            if session_code:
                # Session-scoped update
                cur.execute("""
                    UPDATE participants 
                    SET last_activity = %s
                    WHERE participant_code = %s AND session_code = %s
                """, (datetime.now(timezone.utc), participant_code, session_code))
            else:
                # Fallback: update most recent participant record for this code
                cur.execute("""
                    UPDATE participants 
                    SET last_activity = %s
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (datetime.now(timezone.utc), participant_code))
            
            conn.commit()
            cur.close()
            return_db_connection(conn)
            
    except Exception as e:
        print(f"Error updating participant heartbeat: {e}")

@socketio.on('subscribe_to_updates')
def handle_subscribe(data):
    """Handle subscription to updates"""
    room = data.get('room', 'general')
    join_room(room)

@socketio.on('join_researcher_room')
def handle_researcher_join():
    """Join researcher room"""
    join_room('researcher')

# ============================================================================
# EXPERIMENT MANAGEMENT
# ============================================================================

# Replace/update the existing config endpoint to read/write full config
@app.route('/api/experiment/config', methods=['GET', 'POST'])
def experiment_config_api():
    try:
        if request.method == 'GET':
            # Check if there's an active session and load its config
            session_code = request.args.get('session_code')
            if session_code:
                # Load session-specific configuration from database
                session_config = get_session_config(session_code)
                # Also set the sessionId in the config
                session_config['sessionId'] = session_code
                print(f"✅ Loaded session config for {session_code}")
                
                return jsonify({
                    'success': True,
                    'config': session_config
                })
            else:
                # Return global default config if no session specified
                return jsonify({
                    'success': True,
                    'config': experiment_config_state
                })
        else:
            data = request.get_json() or {}
            
            # Get session_code from query parameters or data
            session_code = request.args.get('session_code') or data.get('session_code')
            if not session_code:
                return jsonify({"error": "Session code required"}), 400
            
            # Load current session config from database
            current_session_config = get_session_config(session_code)
            
            # Check if agentPerceptionTimeWindow is being updated
            agent_perception_changed = False
            if 'agentPerceptionTimeWindow' in data and data['agentPerceptionTimeWindow'] != current_session_config.get('agentPerceptionTimeWindow', 10):
                agent_perception_changed = True
                print(f"Agent perception time window changed from {current_session_config.get('agentPerceptionTimeWindow', 10)} to {data['agentPerceptionTimeWindow']}")
            
            # Check if awarenessDashboard is being updated
            awareness_dashboard_changed = False
            if 'awarenessDashboard' in data and data['awarenessDashboard'] != current_session_config.get('awarenessDashboard', 'off'):
                awareness_dashboard_changed = True
                print(f"Awareness dashboard changed from {current_session_config.get('awarenessDashboard', 'off')} to {data['awarenessDashboard']}")
            
            # Check if communicationLevel is being updated
            communication_level_changed = False
            if 'communicationLevel' in data and data['communicationLevel'] != current_session_config.get('communicationLevel', 'chat'):
                communication_level_changed = True
                print(f"Communication level changed from {current_session_config.get('communicationLevel', 'chat')} to {data['communicationLevel']}")
            
            # Log configuration changes for debugging
            if communication_level_changed or awareness_dashboard_changed:
                print(f"🔄 Interaction variables updated for session {session_code}:")
                if communication_level_changed:
                    print(f"   - Communication Level: {data['communicationLevel']}")
                if awareness_dashboard_changed:
                    print(f"   - Awareness Dashboard: {data['awarenessDashboard']}")
            
            # Update session config with provided fields
            for k in ['numRounds', 'roundDuration', 'startingMoney', 'specialtyCost', 'regularCost', 'minTradePrice', 'maxTradePrice', 'productionTime', 'maxProductionNum', 'sessionDuration', 'sessionId', 'communicationLevel', 'awarenessDashboard', 'shapesPerOrder', 'agentPerceptionTimeWindow', 'incentiveMoney', 'numShapeTypes']:
                if k in data and isinstance(data[k], (int, float, str)):
                    current_session_config[k] = data[k]
            
            # Handle awareness dashboard configuration
            if 'awarenessDashboardConfig' in data and isinstance(data['awarenessDashboardConfig'], dict):
                current_session_config['awarenessDashboardConfig'] = data['awarenessDashboardConfig']
                print(f"🔧 Updated awareness dashboard config: {data['awarenessDashboardConfig']}")
            
            # Handle experiment interface configuration
            if 'experimentInterfaceConfig' in data and isinstance(data['experimentInterfaceConfig'], dict):
                current_session_config['experimentInterfaceConfig'] = data['experimentInterfaceConfig']
                print(f"🔧 Updated experiment interface config: {data['experimentInterfaceConfig']}")
            
            # Handle hiddenProfiles nested configuration
            if 'hiddenProfiles' in data and isinstance(data['hiddenProfiles'], dict):
                if 'hiddenProfiles' not in current_session_config:
                    current_session_config['hiddenProfiles'] = {}
                # Merge the hiddenProfiles config (don't replace entirely, merge to preserve other fields)
                current_session_config['hiddenProfiles'].update(data['hiddenProfiles'])
                print(f"🔧 Updated hiddenProfiles config: {data['hiddenProfiles']}")
            
            # Set sessionId in the config
            current_session_config['sessionId'] = session_code
            
            # Tie timer to sessionDuration (since we're only using session time now, no rounds)
            if 'sessionDuration' in data and data['sessionDuration'] is not None:
                try:
                    session_duration = int(data['sessionDuration'])
                    timer_state = get_timer_state(session_code)
                    timer_state['round_duration_minutes'] = session_duration
                    timer_state['time_remaining'] = session_duration * 60
                    print(f"✅ Timer state updated: sessionDuration={session_duration} minutes")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid sessionDuration value: {data['sessionDuration']}, error: {e}")
                    # Don't fail the entire request, just log the warning
            
            # Restart agents if agentPerceptionTimeWindow or awarenessDashboard changed
            if (agent_perception_changed or awareness_dashboard_changed):
                
                # Stop all agents for this session
                deactivate_result = deactivate_agents_for_session(session_code)
                print(f"   Deactivated agents: {deactivate_result}")
                
                # Reactivate agents with new configuration
                activate_result = activate_agents_for_session(session_code, use_memory=True)
                print(f"   Reactivated agents: {activate_result}")
            
            # Persist to database
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT session_code FROM sessions WHERE session_code = %s", (session_code,))
                session_exists = cur.fetchone()
                
                if session_exists:
                    try:
                        # Serialize config to JSON, handling any non-serializable objects
                        config_json = json.dumps(current_session_config, default=str)
                        cur.execute("""
                            UPDATE sessions 
                            SET experiment_config = %s
                            WHERE session_code = %s
                        """, (config_json, session_code))
                        conn.commit()
                        print(f"✅ Configuration updated for session {session_code}")
                    except (TypeError, ValueError) as json_error:
                        logger.error(f"Error serializing experiment_config to JSON: {json_error}")
                        logger.error(f"Config keys: {list(current_session_config.keys())}")
                        # Try to identify problematic fields
                        for key, value in current_session_config.items():
                            try:
                                json.dumps(value, default=str)
                            except Exception as e:
                                logger.error(f"Problematic field '{key}': {e}")
                        raise
                    
                    # Broadcast configuration changes to all connected clients
                    try:
                        socketio.emit('config_updated', {
                            'communicationLevel': current_session_config.get('communicationLevel', 'chat'),
                            'awarenessDashboard': current_session_config.get('awarenessDashboard', 'off'),
                            'sessionDuration': current_session_config.get('sessionDuration'),
                            'hiddenProfiles': current_session_config.get('hiddenProfiles'),
                            'session_code': session_code
                        }, room=f'session_{session_code}')
                        
                        # Also emit a full experiment_config update for participants
                        # Make sure config is JSON-serializable for WebSocket
                        config_for_ws = json.loads(json.dumps(current_session_config, default=str))
                        socketio.emit('experiment_config_updated', {
                            'session_code': session_code,
                            'config': config_for_ws
                        }, room=f'session_{session_code}')
                    except Exception as emit_error:
                        logger.warning(f"Error broadcasting config update: {emit_error}")
                        # Don't fail the request if broadcasting fails
                    
                    print(f"✅ Configuration broadcasted for session {session_code}")
                else:
                    print(f"⚠️ Session {session_code} not found, skipping configuration update")
                
                cur.close()
            
            return jsonify({
                'success': True,
                'config': current_session_config,
                'agents_restarted': agent_perception_changed or awareness_dashboard_changed
            })
    except Exception as e:
        logger.error(f"Error in experiment_config_api: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'error': str(e),
            'error_type': type(e).__name__
        }), 500

@app.route('/api/interaction/config', methods=['POST'])
def interaction_config_api():
    """Handle interaction configuration updates"""
    try:
        data = request.get_json() or {}
        
        # Get session_code from data
        session_code = data.get('session_code')
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # Load current session config from database
        current_session_config = get_session_config(session_code)
        
        # Update interaction-specific fields
        interaction_fields = ['communicationLevel', 'awarenessDashboard', 'negotiations', 'simultaneousActions', 'rationales']
        
        for field in interaction_fields:
            if field in data:
                current_session_config[field] = data[field]
                logger.info(f"Updated {field} for session {session_code}: {data[field]}")
        
        # Persist to database
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT session_code FROM sessions WHERE session_code = %s", (session_code,))
            session_exists = cur.fetchone()
            
            if session_exists:
                # Update existing session
                cur.execute("""
                    UPDATE sessions 
                    SET experiment_config = %s 
                    WHERE session_code = %s
                """, (json.dumps(current_session_config), session_code))
                conn.commit()
                logger.info(f"Updated interaction config for session {session_code}")
            else:
                logger.warning(f"Session {session_code} not found for interaction config update")
                return jsonify({"error": "Session not found"}), 404
        
        return jsonify({
            "success": True,
            "message": "Interaction config updated successfully"
        })
        
    except Exception as e:
        logger.error(f"Error in interaction config API: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/experiment/ecl/upload', methods=['POST'])
def upload_ecl_config():
    """Upload and parse an ECL configuration file"""
    try:
        from ecl_parser import ECLParser, ECLValidationError
        from ecl_validator import validate_ecl_config
        
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file extension
        if not file.filename.lower().endswith(('.yaml', '.yml')):
            return jsonify({'error': 'File must be a YAML file (.yaml or .yml)'}), 400
        
        # Read file content
        try:
            file_content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            return jsonify({'error': 'File must be UTF-8 encoded'}), 400
        
        # Parse ECL configuration
        parser = ECLParser()
        try:
            ecl_config = parser.parse_yaml(file_content)
        except ECLValidationError as e:
            return jsonify({
                'error': 'ECL parsing failed',
                'details': str(e)
            }), 400
        
        # Validate ECL configuration
        validation_result = validate_ecl_config(ecl_config)
        if not validation_result.is_valid:
            return jsonify({
                'error': 'ECL validation failed',
                'errors': validation_result.errors,
                'warnings': validation_result.warnings,
                'suggestions': validation_result.suggestions
            }), 400
        
        # Convert to experiment configuration format
        experiment_config = parser.to_experiment_config()
        ui_config = parser.get_ui_config()
        
        return jsonify({
            'success': True,
            'message': 'ECL configuration uploaded and validated successfully',
            'experiment_config': experiment_config,
            'ui_config': ui_config,
            'warnings': validation_result.warnings,
            'suggestions': validation_result.suggestions
        })
        
    except Exception as e:
        print(f"Error uploading ECL config: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/experiment/ecl/validate', methods=['POST'])
def validate_ecl_config_api():
    """Validate an ECL configuration without uploading"""
    try:
        from ecl_parser import ECLParser, ECLValidationError
        from ecl_validator import validate_ecl_config
        
        data = request.get_json()
        if not data or 'ecl_content' not in data:
            return jsonify({'error': 'ECL content required'}), 400
        
        ecl_content = data['ecl_content']
        if not isinstance(ecl_content, str):
            return jsonify({'error': 'ECL content must be a string'}), 400
        
        # Parse ECL configuration
        parser = ECLParser()
        try:
            ecl_config = parser.parse_yaml(ecl_content)
        except ECLValidationError as e:
            return jsonify({
                'error': 'ECL parsing failed',
                'details': str(e)
            }), 400
        
        # Validate ECL configuration
        validation_result = validate_ecl_config(ecl_config)
        
        response = {
            'success': True,
            'is_valid': validation_result.is_valid,
            'errors': validation_result.errors,
            'warnings': validation_result.warnings,
            'suggestions': validation_result.suggestions
        }
        
        if validation_result.is_valid:
            # Convert to experiment configuration format
            experiment_config = parser.to_experiment_config()
            ui_config = parser.get_ui_config()
            response['experiment_config'] = experiment_config
            response['ui_config'] = ui_config
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error validating ECL config: {str(e)}")
        return jsonify({'error': f'Validation failed: {str(e)}'}), 500

@app.route('/api/experiment/ecl/apply', methods=['POST'])
def apply_ecl_config():
    """Apply an ECL configuration to a session"""
    try:
        from ecl_parser import ECLParser, ECLValidationError
        from ecl_validator import validate_ecl_config
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request data required'}), 400
        
        session_code = data.get('session_code')
        if not session_code:
            return jsonify({'error': 'Session code required'}), 400
        
        ecl_content = data.get('ecl_content')
        if not ecl_content:
            return jsonify({'error': 'ECL content required'}), 400
        
        # Parse and validate ECL configuration
        parser = ECLParser()
        try:
            ecl_config = parser.parse_yaml(ecl_content)
        except ECLValidationError as e:
            return jsonify({
                'error': 'ECL parsing failed',
                'details': str(e)
            }), 400
        
        validation_result = validate_ecl_config(ecl_config)
        if not validation_result.is_valid:
            return jsonify({
                'error': 'ECL validation failed',
                'errors': validation_result.errors,
                'warnings': validation_result.warnings
            }), 400
        
        # Convert to experiment configuration format
        experiment_config = parser.to_experiment_config()
        ui_config = parser.get_ui_config()
        
        # Update session with ECL configuration
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Check if session exists
            cur.execute("""
                SELECT session_id FROM sessions WHERE session_code = %s
            """, (session_code,))
            session = cur.fetchone()
            
            if not session:
                return jsonify({'error': 'Session not found'}), 404
            
            # Update session with ECL configuration
            # Use 'custom_ecl' instead of 'ecl_custom' to match the constraint pattern
            cur.execute("""
                UPDATE sessions 
                SET experiment_config = %s,
                    experiment_type = %s
                WHERE session_code = %s
                RETURNING session_id, session_code, session_status
            """, (
                json.dumps(experiment_config),
                'custom_ecl',
                session_code
            ))
            
            updated_session = cur.fetchone()
            conn.commit()
            cur.close()
        
        # Broadcast configuration update to connected clients
        socketio.emit('experiment_config_updated', {
            'session_code': session_code,
            'config': experiment_config,
            'ui_config': ui_config
        }, room=f'session_{session_code}')
        
        return jsonify({
            'success': True,
            'message': 'ECL configuration applied successfully',
            'session_code': session_code,
            'experiment_config': experiment_config,
            'ui_config': ui_config,
            'warnings': validation_result.warnings
        })
        
    except Exception as e:
        print(f"Error applying ECL config: {str(e)}")
        return jsonify({'error': f'Apply failed: {str(e)}'}), 500

@app.route('/api/experiment/ecl/templates', methods=['GET'])
def get_ecl_templates():
    """Get available ECL template configurations"""
    try:
        templates = [
            {
                'id': 'daytrader_single_round',
                'name': 'DayTrader (Single Round)',
                'description': 'One-round individual vs. group investment experiment',
                'file': 'daytrader_single_round.yaml'
            },
            {
                'id': 'shape_factory_basic',
                'name': 'Shape Factory (Basic)',
                'description': 'Basic shape production and trading experiment',
                'file': 'shape_factory_basic.yaml'
            },
            {
                'id': 'public_goods_game',
                'name': 'Public Goods Game',
                'description': 'Classic public goods contribution experiment',
                'file': 'public_goods_game.yaml'
            }
        ]
        
        return jsonify({
            'success': True,
            'templates': templates
        })
        
    except Exception as e:
        print(f"Error getting ECL templates: {str(e)}")
        return jsonify({'error': f'Failed to get templates: {str(e)}'}), 500

@app.route('/api/experiment/ecl/template/<template_id>', methods=['GET'])
def get_ecl_template(template_id):
    """Get a specific ECL template configuration"""
    try:
        # For now, return the sample ECL configuration
        # In a real implementation, you would load from template files
        if template_id == 'daytrader_single_round':
            # Return the sample ECL content
            sample_ecl_path = '../sample_ecl.yaml'
            try:
                with open(sample_ecl_path, 'r', encoding='utf-8') as f:
                    ecl_content = f.read()
                
                return jsonify({
                    'success': True,
                    'template_id': template_id,
                    'ecl_content': ecl_content
                })
            except FileNotFoundError:
                return jsonify({'error': 'Template file not found'}), 404
        
        return jsonify({'error': 'Template not found'}), 404
        
    except Exception as e:
        print(f"Error getting ECL template: {str(e)}")
        return jsonify({'error': f'Failed to get template: {str(e)}'}), 500

@app.route('/api/experiment/ecl/action', methods=['POST'])
def execute_ecl_action():
    """Execute an ECL-defined action"""
    try:
        from ecl_parser import ECLParser, ECLValidationError
        from ecl_action_engine import ECLActionEngine
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request data required'}), 400
        
        session_code = data.get('session_code')
        action_name = data.get('action')
        inputs = data.get('inputs', {})
        participant_code = data.get('participant_code')
        
        if not session_code:
            return jsonify({'error': 'Session code required'}), 400
        
        if not action_name:
            return jsonify({'error': 'Action name required'}), 400
        
        if not participant_code:
            return jsonify({'error': 'Participant code required'}), 400
        
        # Get session configuration
        session_config = get_session_config(session_code)
        
        # Check if this is an ECL experiment
        if session_config.get('experiment_type') != 'custom_ecl':
            return jsonify({'error': 'Session is not configured for ECL actions'}), 400
        
        # Parse ECL configuration from session config
        # The full ECL configuration is stored at the top level of session_config
        if not session_config.get('types') or not session_config.get('objects'):
            return jsonify({'error': 'No ECL configuration found in session'}), 400
        
        # Reconstruct the proper ECL configuration format
        ecl_metadata = session_config.get('ecl_config', {})
        ecl_config_data = {
            'ecl_version': ecl_metadata.get('version', '1.0'),
            'experiment': {
                'id': ecl_metadata.get('experiment_id'),
                'title': ecl_metadata.get('title'),
                'description': ecl_metadata.get('description'),
                'timing': ecl_metadata.get('timing', {})
            },
            'types': session_config.get('types', {}),
            'objects': session_config.get('objects', {}),
            'variables': session_config.get('variables', {}),
            'constraints': session_config.get('constraints', []),
            'policies': session_config.get('policies', []),
            'actions': session_config.get('actions', {}),
            'views': session_config.get('views', [])
        }
        
        # Create ECL parser and parse the configuration
        parser = ECLParser()
        ecl_config = parser.parse_dict(ecl_config_data)
        
        # Create action engine
        action_engine = ECLActionEngine(ecl_config, get_db_connection())
        
        # Load or initialize state
        try:
            state = action_engine.load_state_from_db(session_code)
        except:
            state = action_engine.initialize_state(session_code)
        
        # Execute the action
        result = action_engine.execute_action(
            action_name=action_name,
            inputs=inputs,
            actor_id=participant_code,
            session_id=session_code
        )
        
        if result.success:
            # Broadcast state update to connected clients
            socketio.emit('ecl_state_updated', {
                'session_code': session_code,
                'action': action_name,
                'participant': participant_code,
                'effects': result.effects_applied
            }, room=f'session_{session_code}')
            
            return jsonify({
                'success': True,
                'message': result.message,
                'effects_applied': result.effects_applied,
                'warnings': result.warnings
            })
        else:
            return jsonify({
                'success': False,
                'error': result.message,
                'errors': result.errors,
                'warnings': result.warnings
            }), 400
        
    except Exception as e:
        print(f"Error executing ECL action: {str(e)}")
        return jsonify({'error': f'Action execution failed: {str(e)}'}), 500

@app.route('/api/experiment/ecl/state', methods=['GET'])
def get_ecl_state():
    """Get the current ECL state for a session"""
    try:
        from ecl_parser import ECLParser, ECLValidationError
        from ecl_action_engine import ECLActionEngine
        
        session_code = request.args.get('session_code')
        participant_code = request.args.get('participant_code')
        
        if not session_code:
            return jsonify({'error': 'Session code required'}), 400
        
        # Get session configuration
        session_config = get_session_config(session_code)
        
        # Check if this is an ECL experiment
        if session_config.get('experiment_type') != 'custom_ecl':
            return jsonify({'error': 'Session is not configured for ECL'}), 400
        
        # Parse ECL configuration from session config
        # The full ECL configuration is stored at the top level of session_config
        if not session_config.get('types') or not session_config.get('objects'):
            return jsonify({'error': 'No ECL configuration found in session'}), 400
        
        # Reconstruct the proper ECL configuration format
        ecl_metadata = session_config.get('ecl_config', {})
        ecl_config_data = {
            'ecl_version': ecl_metadata.get('version', '1.0'),
            'experiment': {
                'id': ecl_metadata.get('experiment_id'),
                'title': ecl_metadata.get('title'),
                'description': ecl_metadata.get('description'),
                'timing': ecl_metadata.get('timing', {})
            },
            'types': session_config.get('types', {}),
            'objects': session_config.get('objects', {}),
            'variables': session_config.get('variables', {}),
            'constraints': session_config.get('constraints', []),
            'policies': session_config.get('policies', []),
            'actions': session_config.get('actions', {}),
            'views': session_config.get('views', [])
        }
        
        # Create ECL parser and parse the configuration
        parser = ECLParser()
        ecl_config = parser.parse_dict(ecl_config_data)
        
        # Create action engine
        action_engine = ECLActionEngine(ecl_config, get_db_connection())
        
        # Load or initialize state
        try:
            state = action_engine.load_state_from_db(session_code)
        except:
            state = action_engine.initialize_state(session_code)
        
        # Get participant-specific state
        if participant_code:
            participant_state = action_engine.get_participant_state(participant_code)
        else:
            participant_state = {}
        
        return jsonify({
            'success': True,
            'state': {
                'objects': state.objects,
                'variables': state.variables,
                'session_id': state.session_id,
                'updated_at': state.updated_at.isoformat()
            },
            'participant_state': participant_state
        })
        
    except Exception as e:
        print(f"Error getting ECL state: {str(e)}")
        return jsonify({'error': f'Failed to get state: {str(e)}'}), 500

@app.route('/api/sessions/register', methods=['POST'])
def register_session():
    """Register a new session with the current experiment parameters"""
    try:
        data = request.get_json() or {}
        session_code = data.get('session_code')
        researcher_id = data.get('researcher_id', 'researcher')
        experiment_type = data.get('experiment_type')
        
        # If no experiment type is provided, set to NULL (allowed by constraint)
        if not experiment_type or experiment_type.strip() == '':
            experiment_type = None
        experiment_config = data.get('experiment_config', experiment_config_state)  # Use provided config or fallback to global
        
        # Require session code
        if not session_code:
            return jsonify({
                'success': False,
                'error': 'Session code is required'
            }), 400
        
        # Validate session code format
        if len(session_code) > 20:
            return jsonify({
                'success': False,
                'error': 'Session code must be between 1 and 20 characters'
            }), 400
        
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Check if session already exists
            cur.execute("""
                SELECT session_id, session_code, session_status 
                FROM sessions 
                WHERE UPPER(session_code) = UPPER(%s)
            """, (session_code,))
            
            existing_session = cur.fetchone()
            
            if existing_session:
                # Update existing session with new config
                cur.execute("""
                    UPDATE sessions 
                    SET experiment_config = %s,
                        experiment_type = %s,
                        total_rounds = %s,
                        round_duration_minutes = %s,
                        session_status = 'idle'
                    WHERE session_code = %s
                    RETURNING session_id, session_code, session_status
                """, (
                    json.dumps(experiment_config),
                    experiment_type,
                    experiment_config.get('numRounds', 5),
                    experiment_config.get('sessionDuration', 15),
                    session_code
                ))
                
                updated_session = cur.fetchone()
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': f'Session {session_code} updated with new parameters',
                    'session': {
                        'session_id': str(updated_session['session_id']),
                        'session_code': updated_session['session_code'],
                        'session_status': updated_session['session_status'],
                        'config': experiment_config
                    }
                })
            else:
                # Create new session
                cur.execute("""
                    INSERT INTO sessions (
                        session_code, 
                        experiment_type,
                        session_status, 
                        researcher_id,
                        total_rounds,
                        round_duration_minutes,
                        max_participants,
                        experiment_config
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING session_id, session_code, session_status
                """, (
                    session_code,
                    experiment_type,
                    'idle',
                    researcher_id,
                    experiment_config.get('numRounds', 5),
                    experiment_config.get('sessionDuration', 15),
                    20,  # Increased max participants to allow more agents
                    json.dumps(experiment_config)
                ))
                
                new_session = cur.fetchone()
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': f'Session {session_code} registered successfully',
                    'session': {
                        'session_id': str(new_session['session_id']),
                        'session_code': new_session['session_code'],
                        'session_status': new_session['session_status'],
                        'config': experiment_config
                    }
                })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to register session: {str(e)}'
        }), 500

@app.route('/api/sessions/update-experiment-type', methods=['POST'])
def update_session_experiment_type():
    """Update the experiment type for an existing session"""
    try:
        data = request.get_json() or {}
        session_code = data.get('session_code')
        experiment_type = data.get('experiment_type')
        
        print(f"🔧 Update experiment type request: session_code={session_code}, experiment_type={experiment_type}")
        
        # Require both session code and experiment type
        if not session_code:
            print("🔧 Error: Session code is required")
            return jsonify({
                'success': False,
                'error': 'Session code is required'
            }), 400
            
        if not experiment_type:
            print("🔧 Error: Experiment type is required")
            return jsonify({
                'success': False,
                'error': 'Experiment type is required'
            }), 400
        
        # Validate experiment type (only allow valid experiment types)
        valid_experiment_types = ['shapefactory', 'daytrader', 'essayranking', 'wordguessing', 'hiddenprofiles']
        if not experiment_type.startswith('custom_') and experiment_type not in valid_experiment_types:
            return jsonify({
                'success': False,
                'error': f'Invalid experiment type: {experiment_type}'
            }), 400
        
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Check if session exists
            print(f"🔧 Checking if session {session_code} exists...")
            cur.execute("""
                SELECT session_id, session_code 
                FROM sessions 
                WHERE UPPER(session_code) = UPPER(%s)
            """, (session_code,))
            
            existing_session = cur.fetchone()
            print(f"🔧 Session lookup result: {existing_session}")
            
            if not existing_session:
                print(f"🔧 Error: Session {session_code} not found")
                return jsonify({
                    'success': False,
                    'error': f'Session {session_code} not found'
                }), 404
            
            # Update the experiment type
            cur.execute("""
                UPDATE sessions 
                SET experiment_type = %s
                WHERE session_code = %s
                RETURNING session_id, session_code, experiment_type
            """, (experiment_type, session_code))
            
            updated_session = cur.fetchone()
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'Session {session_code} experiment type updated to {experiment_type}',
                'session': {
                    'session_id': str(updated_session['session_id']),
                    'session_code': updated_session['session_code'],
                    'experiment_type': updated_session['experiment_type']
                }
            })
            
    except Exception as e:
        print(f"🔧 Error updating session experiment type: {e}")
        print(f"🔧 Error type: {type(e)}")
        import traceback
        print(f"🔧 Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Failed to update session experiment type: {str(e)}'
        }), 500

@app.route('/api/sessions/delete', methods=['DELETE'])
def delete_session():
    """Delete a session and all its associated data"""
    conn = None
    cur = None
    try:
        data = request.get_json() or {}
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({
                'success': False,
                'error': 'Session code is required'
            }), 400
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check if session exists
        cur.execute("""
            SELECT session_id FROM sessions 
            WHERE session_code = %s
        """, (session_code,))
        
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            return_db_connection(conn)
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404
        
        session_id = session_result['session_id']
        
        # Delete in correct order (respecting foreign key constraints)
        
        # 1. Delete transactions for this session
        cur.execute("DELETE FROM transactions WHERE session_id = %s", (session_id,))
        transactions_deleted = cur.rowcount
        print(f"🗑️ Deleted {transactions_deleted} transactions for session {session_code}")
        
        # 2. Delete messages for this session
        cur.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
        messages_deleted = cur.rowcount
        print(f"🗑️ Deleted {messages_deleted} messages for session {session_code}")
        
        # 3. Delete investments (for DayTrader experiments)
        cur.execute("DELETE FROM investments WHERE session_id = %s", (session_id,))
        investments_deleted = cur.rowcount
        print(f"🗑️ Deleted {investments_deleted} investments for session {session_code}")
        
        # 4. Delete essay assignments (for EssayRanking experiments)
        cur.execute("DELETE FROM essay_assignments WHERE session_id = %s", (session_id,))
        essays_deleted = cur.rowcount
        print(f"🗑️ Deleted {essays_deleted} essay assignments for session {session_code}")
        
        # 5. Delete ranking submissions (for EssayRanking experiments)
        cur.execute("DELETE FROM ranking_submissions WHERE session_id = %s", (session_id,))
        rankings_deleted = cur.rowcount
        print(f"🗑️ Deleted {rankings_deleted} ranking submissions for session {session_code}")
        
        # 6. Delete wordguessing chat history (for WordGuessing experiments)
        cur.execute("DELETE FROM wordguessing_chat_history WHERE session_id = %s", (session_id,))
        chat_deleted = cur.rowcount
        print(f"🗑️ Deleted {chat_deleted} wordguessing chat history entries for session {session_code}")
        
        # 7. Delete production queue entries for this session (before deleting participants)
        cur.execute("""
            DELETE FROM production_queue 
            WHERE participant_id IN (
                SELECT participant_id FROM participants WHERE session_id = %s
            )
        """, (session_id,))
        production_deleted = cur.rowcount
        print(f"🗑️ Deleted {production_deleted} production queue entries for session {session_code}")
        
        # 8. Delete participants for this session
        # For Hidden Profiles: Clean up participantInitiatives from experiment_config before deleting participants
        cur.execute("SELECT experiment_type, experiment_config FROM sessions WHERE session_id = %s", (session_id,))
        session_row = cur.fetchone()
        if session_row and session_row['experiment_type'] == 'hiddenprofiles':
            experiment_config = session_row['experiment_config'] or {}
            if 'hiddenProfiles' in experiment_config:
                # Get all participant codes that will be deleted
                cur.execute("SELECT participant_code FROM participants WHERE session_id = %s", (session_id,))
                participant_codes = [row['participant_code'] for row in cur.fetchall()]
                
                # Clean up participantInitiatives, participantCandidateDocs, and votes
                if 'participantInitiatives' in experiment_config['hiddenProfiles']:
                    for code in participant_codes:
                        experiment_config['hiddenProfiles']['participantInitiatives'].pop(code, None)
                        # Also try without session suffix
                        base_code = code.rsplit('_', 1)[0] if '_' in code else code
                        experiment_config['hiddenProfiles']['participantInitiatives'].pop(base_code, None)
                
                if 'participantCandidateDocs' in experiment_config['hiddenProfiles']:
                    for code in participant_codes:
                        experiment_config['hiddenProfiles']['participantCandidateDocs'].pop(code, None)
                        base_code = code.rsplit('_', 1)[0] if '_' in code else code
                        experiment_config['hiddenProfiles']['participantCandidateDocs'].pop(base_code, None)
                
                if 'votes' in experiment_config['hiddenProfiles']:
                    for code in participant_codes:
                        experiment_config['hiddenProfiles']['votes'].pop(code, None)
                        base_code = code.rsplit('_', 1)[0] if '_' in code else code
                        experiment_config['hiddenProfiles']['votes'].pop(base_code, None)
                
                # Update experiment_config
                cur.execute("""
                    UPDATE sessions 
                    SET experiment_config = %s 
                    WHERE session_id = %s
                """, (json.dumps(experiment_config), session_id))
                print(f"🧹 Cleaned up Hidden Profiles participant data from experiment_config for session {session_code}")
        
        # 9. Delete participant status log (before deleting participants to avoid any constraint issues)
        try:
            cur.execute("DELETE FROM participant_status_log WHERE session_id = %s", (session_id,))
            status_log_deleted = cur.rowcount
            print(f"🗑️ Deleted {status_log_deleted} participant status log entries for session {session_code}")
        except Exception as e:
            print(f"⚠️ Warning: Could not delete participant_status_log (may not exist or already deleted): {str(e)}")
            # Continue with deletion - this is not critical
        
        cur.execute("DELETE FROM participants WHERE session_id = %s", (session_id,))
        participants_deleted = cur.rowcount
        print(f"🗑️ Deleted {participants_deleted} participants for session {session_code}")
        
        # 10. Delete shape inventory for this session
        cur.execute("DELETE FROM shape_inventory WHERE session_id = %s", (session_id,))
        inventory_deleted = cur.rowcount
        print(f"🗑️ Deleted {inventory_deleted} shape inventory entries for session {session_code}")
        
        # 11. Delete participant orders for this session
        cur.execute("DELETE FROM participant_orders WHERE session_id = %s", (session_id,))
        orders_deleted = cur.rowcount
        print(f"🗑️ Deleted {orders_deleted} participant orders for session {session_code}")
        
        # 12. Delete AI agent logs for this session
        cur.execute("DELETE FROM ai_agent_logs WHERE session_id = %s", (session_id,))
        logs_deleted = cur.rowcount
        print(f"🗑️ Deleted {logs_deleted} AI agent logs for session {session_code}")
        
        # 13. Delete session analytics for this session
        cur.execute("DELETE FROM session_analytics WHERE session_id = %s", (session_id,))
        analytics_deleted = cur.rowcount
        print(f"🗑️ Deleted {analytics_deleted} session analytics for session {session_code}")
        
        # 14. Delete dashboard notifications for this session
        cur.execute("DELETE FROM dashboard_notifications WHERE session_id = %s", (session_id,))
        notifications_deleted = cur.rowcount
        print(f"🗑️ Deleted {notifications_deleted} dashboard notifications for session {session_code}")
        
        # 15. Delete session metrics realtime for this session
        cur.execute("DELETE FROM session_metrics_realtime WHERE session_id = %s", (session_id,))
        metrics_deleted = cur.rowcount
        print(f"🗑️ Deleted {metrics_deleted} session metrics for session {session_code}")
        
        # 16. Delete research observations for this session
        cur.execute("DELETE FROM research_observations WHERE session_id = %s", (session_id,))
        observations_deleted = cur.rowcount
        print(f"🗑️ Deleted {observations_deleted} research observations for session {session_code}")
        
        # 17. Finally delete the session itself
        cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
        session_deleted = cur.rowcount
        print(f"🗑️ Deleted {session_deleted} session: {session_code}")
        
        if session_deleted == 0:
            raise Exception(f"Failed to delete session {session_code}: Session not found or already deleted")
        
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        print(f"🗑️ Session {session_code} and all associated data deleted")
        
        return jsonify({
            'success': True,
            'message': f'Session {session_code} and all associated data deleted successfully'
        })
        
    except Exception as e:
        # Get more detailed error information
        error_details = str(e)
        error_type = type(e).__name__
        
        # Try to get PostgreSQL error details if available
        if hasattr(e, 'pgcode'):
            error_details = f"PostgreSQL Error [{e.pgcode}]: {e.pgerror or str(e)}"
        elif hasattr(e, 'args') and len(e.args) > 0:
            if isinstance(e.args[0], (int, float)):
                error_details = f"{error_type}: {e.args[0]}"
            else:
                error_details = f"{error_type}: {str(e)}"
        else:
            error_details = f"{error_type}: {str(e)}"
        
        # Rollback transaction on error
        if conn:
            try:
                conn.rollback()
                print(f"⚠️ Rolled back transaction due to error: {error_details}")
            except Exception as rollback_error:
                print(f"⚠️ Error during rollback: {str(rollback_error)}")
        
        # Close cursor and connection
        if cur:
            try:
                cur.close()
            except:
                pass
        if conn:
            try:
                return_db_connection(conn)
            except:
                pass
        
        session_code_for_error = 'unknown'
        try:
            if 'data' in locals() and data:
                session_code_for_error = data.get('session_code', 'unknown')
            elif 'session_code' in locals():
                session_code_for_error = session_code
        except:
            pass
        
        print(f"❌ Failed to delete session {session_code_for_error}: {error_details}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        
        return jsonify({
            'success': False,
            'error': f'Failed to delete session: {error_details}'
        }), 500

@app.route('/api/sessions/check', methods=['POST'])
def check_session():
    """Check if a session exists"""
    try:
        data = request.get_json() or {}
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({
                'success': False,
                'error': 'Session code is required'
            }), 400
        
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Check if session exists and get its configuration
            cur.execute("""
                SELECT session_id, session_code, session_status, experiment_type, experiment_config
                FROM sessions 
                WHERE UPPER(session_code) = UPPER(%s)
            """, (session_code,))
            
            session = cur.fetchone()
            
            cur.close()
        
        if session:
            # Load session config into memory
            if session.get('experiment_config'):
                try:
                    config = session['experiment_config']
                    if isinstance(config, str):
                        config = json.loads(config)
                    # Don't update global state - just return the session config
                    print(f"✅ Retrieved session config for {session_code}")
                except Exception as e:
                    print(f"Warning: failed to parse session config: {e}")
                    config = {}
            
            return jsonify({
                'success': True,
                'exists': True,
                'session': dict(session),
                'config': config,
                'message': f'Session {session_code} exists'
            })
        else:
            return jsonify({
                'success': True,
                'exists': False,
                'message': f'Session {session_code} does not exist'
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to check session: {str(e)}'
        }), 500

@app.route('/api/session/current', methods=['GET'])
def get_current_session():
    """Get current session information for authenticated participant or researcher"""
    try:
        session_code = None
        
        # Try to get session_code from query parameter (for researcher dashboard)
        session_code_param = request.args.get('session_code')
        if session_code_param:
            session_code = session_code_param
        else:
            # Try to get from Authorization header (for authenticated participants)
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                try:
                    # Decode token
                    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                    session_code = payload.get('session_code')
                except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                    # If token is invalid, fall through to check query param
                    pass
        
        if not session_code:
            return jsonify({'error': 'Session code required (either as query parameter or in auth token)'}), 400
        
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get session information including experiment type
            cur.execute("""
                SELECT session_id, session_code, experiment_type, session_status, experiment_config
                FROM sessions 
                WHERE UPPER(session_code) = UPPER(%s)
            """, (session_code,))
            
            session = cur.fetchone()
            cur.close()
        
        if session:
            return jsonify({
                'success': True,
                'session_code': session['session_code'],
                'experiment_type': session['experiment_type'],
                'session_status': session['session_status'],
                'config': session.get('experiment_config', {})
            })
        else:
            return jsonify({'error': 'Session not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# SESSION TEMPLATES MANAGEMENT
# ============================================================================

@app.route('/api/session-templates', methods=['GET'])
def get_session_templates():
    """Get all session templates for the current researcher"""
    try:
        researcher_id = request.args.get('researcher_id', 'researcher')
        
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cur.execute("""
                SELECT 
                    template_id,
                    session_id,
                    template_config,
                    created_at,
                    updated_at,
                    is_default
                FROM session_templates 
                WHERE researcher_id = %s
                ORDER BY is_default DESC, session_id ASC
            """, (researcher_id,))
            
            templates = cur.fetchall()
            cur.close()
        
        return jsonify({
            'success': True,
            'templates': [dict(template) for template in templates]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get session templates: {str(e)}'
        }), 500

@app.route('/api/session-templates', methods=['POST'])
def save_session_template():
    """Save current experiment configuration as a session template"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        researcher_id = data.get('researcher_id', 'researcher')
        template_config = data.get('template_config', {})
        
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Session ID is required'
            }), 400
        
        # Validate session ID length
        if len(session_id) > 20:
            return jsonify({
                'success': False,
                'error': 'Session ID must be 20 characters or less'
            }), 400
        
        # If no template_config provided, use the global experiment_config_state as fallback
        if not template_config:
            template_config = experiment_config_state
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check if session ID already exists
        cur.execute("""
            SELECT template_id FROM session_templates 
            WHERE session_id = %s AND researcher_id = %s
        """, (session_id, researcher_id))
        
        existing_template = cur.fetchone()
        
        if existing_template:
            # Update existing template
            cur.execute("""
                UPDATE session_templates 
                SET template_config = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE template_id = %s
                RETURNING template_id, session_id, template_config
            """, (json.dumps(template_config), existing_template['template_id']))
            
            updated_template = cur.fetchone()
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'Session "{session_id}" parameters updated successfully',
                'template': dict(updated_template)
            })
        else:
            # Create new template
            cur.execute("""
                INSERT INTO session_templates 
                (session_id, researcher_id, template_config)
                VALUES (%s, %s, %s)
                RETURNING template_id, session_id, template_config
            """, (session_id, researcher_id, json.dumps(template_config)))
            
            new_template = cur.fetchone()
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'Session "{session_id}" created successfully',
                'template': dict(new_template)
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to save session template: {str(e)}'
        }), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            return_db_connection(conn)

@app.route('/api/session-templates/<session_id>', methods=['GET'])
def get_session_template(session_id):
    """Get a specific session template by session ID"""
    try:
        researcher_id = request.args.get('researcher_id', 'researcher')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT 
                template_id,
                session_id,
                template_config,
                created_at,
                updated_at,
                is_default
            FROM session_templates 
            WHERE session_id = %s AND researcher_id = %s
        """, (session_id, researcher_id))
        
        template = cur.fetchone()
        cur.close()
        return_db_connection(conn)
        
        if not template:
            return jsonify({
                'success': False,
                'error': 'Session template not found'
            }), 404
        
        return jsonify({
            'success': True,
            'template': dict(template)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get session template: {str(e)}'
        }), 500

@app.route('/api/session-templates/<session_id>/load', methods=['POST'])
def load_session_template(session_id):
    """Load a session template configuration into the current experiment config"""
    try:
        researcher_id = request.args.get('researcher_id', 'researcher')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT template_config
            FROM session_templates 
            WHERE session_id = %s AND researcher_id = %s
        """, (session_id, researcher_id))
        
        template = cur.fetchone()
        cur.close()
        return_db_connection(conn)
        
        if not template:
            return jsonify({
                'success': False,
                'error': 'Session template not found'
            }), 404
        
        # Load the template configuration
        template_config = template['template_config']
        
        # Return the template config for the frontend to apply
        return jsonify({
            'success': True,
            'message': f'Session "{session_id}" configuration loaded successfully',
            'config': template_config
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to load session template: {str(e)}'
        }), 500

@app.route('/api/session-templates/<session_id>', methods=['DELETE'])
def delete_session_template(session_id):
    """Delete a session template"""
    try:
        researcher_id = request.args.get('researcher_id', 'researcher')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if template exists and belongs to the researcher
        cur.execute("""
            SELECT session_id, is_default FROM session_templates 
            WHERE session_id = %s AND researcher_id = %s
        """, (session_id, researcher_id))
        
        template = cur.fetchone()
        
        if not template:
            cur.close()
            return_db_connection(conn)
            return jsonify({
                'success': False,
                'error': 'Session template not found'
            }), 404
        
        template_session_id, is_default = template
        
        # Prevent deletion of default templates
        if is_default:
            cur.close()
            return_db_connection(conn)
            return jsonify({
                'success': False,
                'error': 'Cannot delete default session templates'
            }), 400
        
        # Delete the template
        cur.execute("""
            DELETE FROM session_templates 
            WHERE session_id = %s AND researcher_id = %s
        """, (session_id, researcher_id))
        
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        return jsonify({
            'success': True,
            'message': f'Session "{session_id}" template deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to delete session template: {str(e)}'
        }), 500

@app.route('/api/experiment/start', methods=['POST'])
def start_experiment():
    """Start the experiment"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        print(f"🔍 Start experiment request data: {data}")
        print(f"🔍 Session code from request: {session_code}")
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        print(f"🚀 Starting experiment for session: {session_code}")
        print(f"Current timer state before start: {get_timer_state(session_code)}")
        
        # Get session configuration for this specific session
        session_config = get_session_config(session_code)
        session_duration = session_config.get('sessionDuration', 15)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        from datetime import datetime, timezone
        session_start_time = datetime.now(timezone.utc)
        
        # For hiddenprofiles, also call start_session to ensure consistency
        if experiment_type == 'hiddenprofiles':
            # For hiddenprofiles, do NOT set session_started_at here - it will be set when the human submits their first vote
            # Just update the session status to active (but don't set session_started_at yet)
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE sessions 
                    SET session_status = 'session_active'
                    WHERE session_code = %s
                """, (session_code,))
                conn.commit()
                cur.close()
                return_db_connection(conn)
                print(f"✅ Hidden Profiles: Session status set to active (session_started_at will be set when human submits first vote)")
            except Exception as e:
                print(f"⚠️ Warning: Could not update session status: {e}")
            try:
                game_engine = get_game_engine(experiment_type)
                start_result = game_engine.start_session(session_code)
                if start_result.get('success'):
                    print(f"✅ Hidden Profiles session started: {start_result.get('session_code')}")
            except Exception as e:
                print(f"⚠️ Warning: Could not start hiddenprofiles session: {e}")
            
            # For hiddenprofiles, do NOT start the timer here - it will start when the human submits their first vote
            # Initialize timer state but keep it in 'idle' or 'waiting' status
            initialize_timer_state(session_code)
            timer_state = get_timer_state(session_code)
            
            # Set timer state to waiting - timer will start when human submits first vote
            timer_state['experiment_status'] = 'waiting'  # Changed from 'running' to 'waiting'
            timer_state['round_duration_minutes'] = session_duration
            timer_state['time_remaining'] = session_duration * 60
            timer_state['timer_active'] = False  # Do not activate timer yet
            timer_state['round_start_time'] = None  # Will be set when vote is submitted
            
            print(f"⏸️ Hidden Profiles: Timer initialized but NOT started. Will start when human submits first vote.")
            print(f"🔧 Timer state: {timer_state}")
            
            # Broadcast timer update (with waiting status)
            broadcast_timer_update(session_code)
            
            # Don't broadcast experiment_started event for hiddenprofiles here
            # It will be broadcast when the vote is submitted
        else:
            # For non-hiddenprofiles experiments, set session_started_at here
            # Set session_started_at in database BEFORE starting timer to ensure synchronization
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE sessions 
                    SET session_status = 'session_active',
                        session_started_at = %s
                    WHERE session_code = %s
                """, (session_start_time, session_code))
                conn.commit()
                cur.close()
                return_db_connection(conn)
                print(f"✅ Set session_started_at to {session_start_time.isoformat()} for session {session_code}")
            except Exception as e:
                print(f"⚠️ Warning: Could not set session_started_at: {e}")
                # Continue anyway - timer will still work
            # For other experiment types, start timer immediately
            # Initialize timer state for this session
            initialize_timer_state(session_code)
            timer_state = get_timer_state(session_code)
            
            # Update experiment status
            timer_state['experiment_status'] = 'running'
            timer_state['round_duration_minutes'] = session_duration
            timer_state['time_remaining'] = session_duration * 60
            timer_state['timer_active'] = True  # Make sure timer is marked as active
            timer_state['round_start_time'] = session_start_time.isoformat()  # Store start time for synchronization
            
            print(f"🔧 Timer state after initialization: {timer_state}")
            print(f"🔧 Timer active flag: {timer_state.get('timer_active', False)}")
            print(f"🔧 Round start time: {timer_state.get('round_start_time')}")
            
            print(f"✅ Timer state updated after start: {timer_state}")
            
            # Start session-specific timer
            start_session_timer(session_code)
            print(f"✅ Session timer started for session: {session_code}")
            
            # Immediately broadcast timer update to all clients
            broadcast_timer_update(session_code)
            print("✅ Timer state broadcasted to all clients")
            
            # Broadcast specific experiment_started event for researcher dashboard
            socketio.emit('experiment_started', {
                'experiment_status': 'running',
                'session_code': session_code,
                'timer_state': timer_state
            }, room=f'session_{session_code}')
            socketio.emit('experiment_started', {
                'experiment_status': 'running',
                'session_code': session_code,
                'timer_state': timer_state
            }, room='researcher')
            socketio.emit('experiment_started', {
                'experiment_status': 'running',
                'session_code': session_code,
                'timer_state': timer_state
            })
            print("✅ Experiment started event broadcasted to all clients")
        
        # Simple approach: just update participant money
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Get current experiment configuration for this session
            starting_money = session_config.get('startingMoney', 300)
            
            # Update participant money - initialize new participants and reset existing ones
            cur.execute("""
                UPDATE participants 
                SET money = %s
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s) 
                AND (money IS NULL OR money = 300 OR money = %s)
            """, (starting_money, session_code, starting_money))
            
            updated_count = cur.rowcount
            conn.commit()
            cur.close()
            return_db_connection(conn)
            
            print(f"✅ Updated {updated_count} participants with ${starting_money} from session config")
            
        except Exception as db_error:
            print(f"⚠️ Database operations failed: {db_error}")
            # Continue anyway - the experiment can still start
        
        # Auto-activate agents if configured
        # For Hidden Profiles: agents should only start after human submits initial vote
        # Skip agent activation here for hiddenprofiles experiments
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        if experiment_type != 'hiddenprofiles':
            try:
                conn = get_db_connection()
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # Get AI agents
                cur.execute("""
                    SELECT participant_code 
                    FROM participants 
                    WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s) 
                    AND participant_type = 'ai_agent'
                """, (session_code,))
                
                agents = cur.fetchall()
                cur.close()
                return_db_connection(conn)

                for agent in agents:
                    try:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute("""
                            UPDATE participants 
                            SET login_status = 'active', last_activity = %s
                            WHERE participant_code = %s AND session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
                        """, (datetime.now(timezone.utc), agent['participant_code'], session_code))
                        conn.commit()
                        cur.close()
                        return_db_connection(conn)
                        print(f"✅ Agent {agent['participant_code']} marked active")
                    except Exception as e:
                        print(f"❌ Error marking agent {agent['participant_code']} active: {e}")

                # Start agent loops locally
                print("🚀 Starting local agent loops...")
                # Double-check that experiment status is set to running before activating agents
                session_timer_state = get_timer_state(session_code)
                if session_timer_state['experiment_status'] == 'running':
                    activation_result = activate_agents_for_session(session_code, use_memory=True)
                    print(f"Local activation result: {activation_result}")
                else:
                    print(f"⚠️ Warning: Experiment status is '{session_timer_state['experiment_status']}', not 'running'. Skipping agent activation.")
                    activation_result = {'success': False, 'error': 'Experiment not in running state'}
            except Exception as e:
                print(f"Error auto-activating agents: {e}")
        else:
            print(f"⏸️ Hidden Profiles experiment: Agents will be activated after first human vote is submitted")
        
        print("✅ Experiment start completed successfully")
        return jsonify({
            "success": True,
            "message": "Experiment started",
            "timer_state": get_timer_state(session_code)
        })
        
    except Exception as e:
        print(f"❌ Error in start_experiment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/experiment/check-and-start', methods=['POST'])
def check_and_start_experiment():
    """Check if session is ready to start (does not actually start the session)"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        print(f"🔍 Check and start experiment request data: {data}")
        print(f"🔍 Session code from request: {session_code}")
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # Get current timer state
        timer_state = get_timer_state(session_code)
        current_status = timer_state.get('experiment_status', 'idle')
        
        print(f"🔍 Current experiment status: {current_status}")
        
        # If experiment is already running, return current state
        if current_status == 'running':
            return jsonify({
                "status": "already_running",
                "message": "Experiment is already running",
                "experiment_status": current_status,
                "time_remaining": timer_state.get('time_remaining', 0)
            })
        
        # If experiment is paused, don't auto-start
        if current_status == 'paused':
            return jsonify({
                "status": "paused",
                "message": "Experiment is paused and cannot be started automatically",
                "experiment_status": current_status,
                "time_remaining": timer_state.get('time_remaining', 0)
            })
        
        # Check if session is ready to start
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get session info
        cur.execute("""
            SELECT session_id, max_participants, experiment_config 
            FROM sessions 
            WHERE session_code = %s
        """, (session_code,))
        
        session = cur.fetchone()
        if not session:
            cur.close()
            return_db_connection(conn)
            return jsonify({"error": "Session not found"}), 404
        
        # Count logged in participants
        cur.execute("""
            SELECT 
                COUNT(*) as total_participants,
                COUNT(CASE WHEN login_status = 'active' THEN 1 END) as logged_in_count,
                COUNT(CASE WHEN login_status = 'active' AND participant_type = 'human' THEN 1 END) as humans_logged_in,
                COUNT(CASE WHEN login_status = 'active' AND participant_type = 'ai_agent' THEN 1 END) as agents_logged_in
            FROM participants 
            WHERE session_id = %s
        """, (session['session_id'],))
        
        counts = cur.fetchone()
        cur.close()
        return_db_connection(conn)
        
        print(f"🔍 Participant counts: {counts}")
        
        # Check if enough participants are logged in
        # For now, start with at least 1 participant (can be adjusted)
        min_participants = 1
        ready_to_start = counts['logged_in_count'] >= min_participants
        
        print(f"🔍 Ready to start: {ready_to_start} (logged_in: {counts['logged_in_count']}, min: {min_participants})")
        
        if not ready_to_start:
            return jsonify({
                "status": "not_ready",
                "message": f"Not enough participants logged in. Need at least {min_participants}, have {counts['logged_in_count']}",
                "logged_in_count": counts['logged_in_count'],
                "min_participants": min_participants,
                "experiment_status": current_status
            })
        
        # Session is ready to start - just return ready status
        print(f"✅ Session ready to start for session: {session_code}")
        
        return jsonify({
            "status": "ready_to_start",
            "message": "Session ready to start",
            "logged_in_count": counts['logged_in_count'],
            "min_participants": min_participants
        })
        
    except Exception as e:
        print(f"❌ Error in check_and_start_experiment: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/experiment/pause', methods=['POST'])
def pause_experiment():
    """Pause the experiment"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        print(f"⏸️ Pause request received for session: {session_code}")
        timer_state = get_timer_state(session_code)
        print(f"Current timer state before pause: {timer_state}")
        
        timer_state['experiment_status'] = 'paused'
        
        # Stop the timer thread when paused
        stop_session_timer(session_code)
        
        print(f"✅ Experiment paused. Timer state after pause: {timer_state}")
        
        # Emit specific pause event
        socketio.emit('experiment_paused', {
            'experiment_status': 'paused',
            'timer_state': timer_state,
            'session_code': session_code
        }, room='researcher')
        socketio.emit('experiment_paused', {
            'experiment_status': 'paused',
            'timer_state': timer_state,
            'session_code': session_code
        })
        
        return jsonify({
            "success": True,
            "message": "Experiment paused",
            "timer_state": timer_state
        })
        
    except Exception as e:
        print(f"❌ Error in pause_experiment: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/experiment/resume', methods=['POST'])
def resume_experiment():
    """Resume the experiment from paused state"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        print(f"▶️ Resume request received for session: {session_code}")
        timer_state = get_timer_state(session_code)
        print(f"Current timer state: {timer_state}")
        
        # Check if experiment is currently paused
        if timer_state['experiment_status'] != 'paused':
            print(f"❌ Cannot resume - experiment status is '{timer_state['experiment_status']}', not 'paused'")
            return jsonify({"error": f"Experiment is not paused (current status: {timer_state['experiment_status']})"}), 400
        
        print(f"▶️ Resuming experiment for session: {session_code}")
        print(f"Timer remaining before resume: {timer_state['time_remaining']}")
        
        # Resume the experiment without resetting the timer
        timer_state['experiment_status'] = 'running'
        
        # Start the timer again (it will continue from where it left off)
        start_session_timer(session_code)
        print(f"✅ Session timer resumed for session: {session_code}")
        
        # Immediately broadcast timer update to all clients
        broadcast_timer_update(session_code)
        print("✅ Timer state broadcasted to all clients")
        
        # Emit specific resume event
        socketio.emit('experiment_resumed', {
            'experiment_status': 'running',
            'timer_state': timer_state,
            'session_code': session_code
        }, room='researcher')
        socketio.emit('experiment_resumed', {
            'experiment_status': 'running',
            'timer_state': timer_state,
            'session_code': session_code
        })
        
        # Reactivate agents if they were active before
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get AI agents
            cur.execute("""
                SELECT participant_code 
                FROM participants 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s) 
                AND participant_type = 'ai_agent'
            """, (session_code,))
            
            agents = cur.fetchall()
            cur.close()
            return_db_connection(conn)

            # Reactivate agents
            if agents:
                print("🚀 Reactivating agent loops...")
                session_timer_state = get_timer_state(session_code)
                if session_timer_state['experiment_status'] == 'running':
                    activation_result = activate_agents_for_session(session_code, use_memory=True)
                    print(f"Agent reactivation result: {activation_result}")
                else:
                    print(f"⚠️ Warning: Experiment status is '{session_timer_state['experiment_status']}', not 'running'. Skipping agent reactivation.")
        except Exception as e:
            print(f"Error reactivating agents: {e}")
        
        print("✅ Experiment resume completed successfully")
        return jsonify({
            "success": True,
            "message": "Experiment resumed",
            "timer_state": get_timer_state(session_code)
        })
        
    except Exception as e:
        print(f"❌ Error in resume_experiment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/experiment/reset', methods=['POST'])
def reset_experiment():
    """Reset the experiment"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        print(f"🔄 Resetting experiment for session: {session_code}")
        
        # Stop the timer
        stop_session_timer(session_code)
        
        # Reset timer state
        initialize_timer_state(session_code)
        
        # Broadcast timer update to all clients
        broadcast_timer_update(session_code)
        
        # Reset participant money and clear production queues
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Get session config for starting money
            session_config = get_session_config(session_code)
            starting_money = session_config.get('startingMoney', 300)
            
            # Reset participant money and game state
            cur.execute("""
                UPDATE participants 
                SET money = %s,
                    orders_completed = 0,
                    shapes_bought = 0,
                    shapes_sold = 0,
                    total_score = 0,
                    specialty_production_used = 0,
                    orders = '[]'::jsonb
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (starting_money, session_code))
            
            # Clear production queues
            cur.execute("""
                DELETE FROM production_queue 
                WHERE participant_id IN (
                    SELECT participant_id FROM participants 
                    WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
                )
            """, (session_code,))
            
            # Clear shape inventory
            cur.execute("""
                DELETE FROM shape_inventory 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear participant orders (fulfilled orders)
            cur.execute("""
                DELETE FROM participant_orders 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear trade transactions
            cur.execute("""
                DELETE FROM transactions 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear messages
            cur.execute("""
                DELETE FROM messages 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear investments (for DayTrader experiments)
            cur.execute("""
                DELETE FROM investments 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear AI agent logs
            cur.execute("""
                DELETE FROM ai_agent_logs 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear session analytics
            cur.execute("""
                DELETE FROM session_analytics 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear dashboard notifications
            cur.execute("""
                DELETE FROM dashboard_notifications 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear session metrics realtime
            cur.execute("""
                DELETE FROM session_metrics_realtime 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear essay ranking data
            cur.execute("""
                DELETE FROM essay_assignments 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            cur.execute("""
                DELETE FROM ranking_submissions 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Reset participant essay ranking data
            cur.execute("""
                UPDATE participants 
                SET current_rankings = NULL,
                    submitted_rankings_count = 0
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # For Hidden Profiles: Clean up experiment_config before deleting session
            cur.execute("""
                SELECT experiment_type, experiment_config 
                FROM sessions 
                WHERE session_code = %s
            """, (session_code,))
            session_row = cur.fetchone()
            if session_row and session_row['experiment_type'] == 'hiddenprofiles':
                experiment_config = session_row['experiment_config'] or {}
                if 'hiddenProfiles' in experiment_config:
                    # Get all participant codes that will be deleted
                    cur.execute("""
                        SELECT participant_code 
                        FROM participants 
                        WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
                    """, (session_code,))
                    participant_codes = [row[0] for row in cur.fetchall()]
                    
                    # Clean up participantInitiatives, participantCandidateDocs, and votes
                    if 'participantInitiatives' in experiment_config['hiddenProfiles']:
                        for code in participant_codes:
                            experiment_config['hiddenProfiles']['participantInitiatives'].pop(code, None)
                            base_code = code.rsplit('_', 1)[0] if '_' in code else code
                            experiment_config['hiddenProfiles']['participantInitiatives'].pop(base_code, None)
                    
                    if 'participantCandidateDocs' in experiment_config['hiddenProfiles']:
                        for code in participant_codes:
                            experiment_config['hiddenProfiles']['participantCandidateDocs'].pop(code, None)
                            base_code = code.rsplit('_', 1)[0] if '_' in code else code
                            experiment_config['hiddenProfiles']['participantCandidateDocs'].pop(base_code, None)
                    
                    if 'votes' in experiment_config['hiddenProfiles']:
                        for code in participant_codes:
                            experiment_config['hiddenProfiles']['votes'].pop(code, None)
                            base_code = code.rsplit('_', 1)[0] if '_' in code else code
                            experiment_config['hiddenProfiles']['votes'].pop(base_code, None)
                    
                    # Clear candidate names, candidate docs, and public info for this session
                    # This ensures each session starts fresh
                    experiment_config['hiddenProfiles'].pop('candidateNames', None)
                    experiment_config['hiddenProfiles'].pop('candidateDocs', None)
                    experiment_config['hiddenProfiles'].pop('publicInfo', None)
                    experiment_config['hiddenProfiles'].pop('candidateDocsUpdatedAt', None)
                    
                    # Update experiment_config before deleting session
                    cur.execute("""
                        UPDATE sessions 
                        SET experiment_config = %s 
                        WHERE session_code = %s
                    """, (json.dumps(experiment_config), session_code))
                    print(f"🧹 Cleaned up Hidden Profiles data from experiment_config for session {session_code}")
            
            # Delete the session itself
            cur.execute("""
                DELETE FROM sessions 
                WHERE session_code = %s
            """, (session_code,))
            
            conn.commit()
            cur.close()
            return_db_connection(conn)
            
            print(f"✅ Reset {session_code} - cleared all game data and deleted session")
            
        except Exception as db_error:
            print(f"⚠️ Database reset operations failed: {db_error}")
        
        # Stop all agent threads (also stops agent logging)
        try:
            deactivation_result = deactivate_agents_for_session(session_code)
            print(f"Agent deactivation result: {deactivation_result}")
        except Exception as e:
            print(f"Error deactivating agents: {e}")
        
        # Stop human logging for this session
        try:
            human_logging_result = stop_human_logging_for_session(session_code)
            print(f"Human logging stop result: {human_logging_result}")
        except Exception as e:
            print(f"Error stopping human logging: {e}")
        
        # Emit WebSocket event to notify all clients of reset
        socketio.emit('experiment_reset', {
            'session_code': session_code,
            'timestamp': datetime.now().isoformat(),
            'message': 'Experiment has been reset'
        })
        
        print("✅ Experiment reset completed successfully")
        return jsonify({
            "success": True,
            "message": "Experiment reset successfully",
            "timer_state": get_timer_state(session_code)
        })
        
    except Exception as e:
        print(f"❌ Error in reset_experiment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/experiment/timer-reset', methods=['POST'])
def timer_reset():
    """Reset timer and clear game data without deleting session"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        print(f"⏰ Resetting timer for session: {session_code}")
        
        # Stop the timer
        stop_session_timer(session_code)
        
        # Reset timer state
        initialize_timer_state(session_code)
        
        # Broadcast timer update to all clients
        broadcast_timer_update(session_code)
        
        # Reset participant money and clear game data
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Get session config for starting money
            session_config = get_session_config(session_code)
            starting_money = session_config.get('startingMoney', 300)
            
            # Reset participant money and game state
            cur.execute("""
                UPDATE participants 
                SET money = %s,
                    orders_completed = 0,
                    shapes_bought = 0,
                    shapes_sold = 0,
                    total_score = 0,
                    specialty_production_used = 0,
                    orders = '[]'::jsonb
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (starting_money, session_code))
            
            # Clear production queues
            cur.execute("""
                DELETE FROM production_queue 
                WHERE participant_id IN (
                    SELECT participant_id FROM participants 
                    WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
                )
            """, (session_code,))
            
            # Clear shape inventory
            cur.execute("""
                DELETE FROM shape_inventory 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear participant orders (fulfilled orders)
            cur.execute("""
                DELETE FROM participant_orders 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear trade transactions
            cur.execute("""
                DELETE FROM transactions 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear messages
            cur.execute("""
                DELETE FROM messages 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear investments (for DayTrader experiments)
            cur.execute("""
                DELETE FROM investments 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear AI agent logs
            cur.execute("""
                DELETE FROM ai_agent_logs 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear session analytics
            cur.execute("""
                DELETE FROM session_analytics 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear dashboard notifications
            cur.execute("""
                DELETE FROM dashboard_notifications 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear session metrics realtime
            cur.execute("""
                DELETE FROM session_metrics_realtime 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Clear essay ranking data
            cur.execute("""
                DELETE FROM essay_assignments 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            cur.execute("""
                DELETE FROM ranking_submissions 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # Reset participant essay ranking data
            cur.execute("""
                UPDATE participants 
                SET current_rankings = NULL,
                    submitted_rankings_count = 0
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
            """, (session_code,))
            
            # For Hidden Profiles: Clean up participantInitiatives, participantCandidateDocs, and votes
            cur.execute("""
                SELECT experiment_type, experiment_config 
                FROM sessions 
                WHERE session_code = %s
            """, (session_code,))
            session_row = cur.fetchone()
            if session_row and session_row['experiment_type'] == 'hiddenprofiles':
                experiment_config = session_row['experiment_config'] or {}
                if 'hiddenProfiles' in experiment_config:
                    # Get all participant codes in this session
                    cur.execute("""
                        SELECT participant_code 
                        FROM participants 
                        WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
                    """, (session_code,))
                    participant_codes = [row[0] for row in cur.fetchall()]
                    
                    # Clean up participantInitiatives, participantCandidateDocs, and votes
                    if 'participantInitiatives' in experiment_config['hiddenProfiles']:
                        for code in participant_codes:
                            experiment_config['hiddenProfiles']['participantInitiatives'].pop(code, None)
                            base_code = code.rsplit('_', 1)[0] if '_' in code else code
                            experiment_config['hiddenProfiles']['participantInitiatives'].pop(base_code, None)
                    
                    if 'participantCandidateDocs' in experiment_config['hiddenProfiles']:
                        for code in participant_codes:
                            experiment_config['hiddenProfiles']['participantCandidateDocs'].pop(code, None)
                            base_code = code.rsplit('_', 1)[0] if '_' in code else code
                            experiment_config['hiddenProfiles']['participantCandidateDocs'].pop(base_code, None)
                    
                    if 'votes' in experiment_config['hiddenProfiles']:
                        for code in participant_codes:
                            experiment_config['hiddenProfiles']['votes'].pop(code, None)
                            base_code = code.rsplit('_', 1)[0] if '_' in code else code
                            experiment_config['hiddenProfiles']['votes'].pop(base_code, None)
                    
                    # Update experiment_config
                    cur.execute("""
                        UPDATE sessions 
                        SET experiment_config = %s 
                        WHERE session_code = %s
                    """, (json.dumps(experiment_config), session_code))
                    print(f"🧹 Cleaned up Hidden Profiles participant data from experiment_config for session {session_code}")
            
            conn.commit()
            cur.close()
            return_db_connection(conn)
            
            print(f"✅ Timer reset {session_code} - cleared all game data")
            
        except Exception as db_error:
            print(f"⚠️ Database reset operations failed: {db_error}")
            return jsonify({"error": f"Database reset failed: {db_error}"}), 500
        
        # Emit WebSocket event to notify all clients of timer reset
        socketio.emit('timer_reset', {
            'session_code': session_code,
            'timestamp': datetime.now().isoformat(),
            'message': 'Timer has been reset'
        })
        
        print("✅ Timer reset completed successfully")
        return jsonify({
            "success": True,
            "message": "Timer reset successfully",
            "timer_state": get_timer_state(session_code)
        })
        
    except Exception as e:
        print(f"❌ Error in timer_reset: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/experiment/timer-state')
def get_timer_state_api():
    """Get current timer state for a specific session"""
    session_code = request.args.get('session_code')
    timer_state = get_timer_state(session_code)
    
    # Get session_started_at from database for accurate time calculation
    session_started_at = None
    if session_code:
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT session_started_at 
                FROM sessions 
                WHERE session_code = %s
            """, (session_code,))
            result = cur.fetchone()
            if result and result.get('session_started_at'):
                session_started_at = result['session_started_at'].isoformat() if hasattr(result['session_started_at'], 'isoformat') else str(result['session_started_at'])
            cur.close()
            return_db_connection(conn)
        except Exception as e:
            print(f"⚠️ Warning: Could not get session_started_at: {e}")
    
    response_data = {
        'experiment_status': timer_state['experiment_status'],
        'time_remaining': timer_state['time_remaining'],
        'round_duration_minutes': timer_state['round_duration_minutes'],
        'session_code': session_code,
        'session_started_at': session_started_at or timer_state.get('round_start_time'),
        'round_start_time': timer_state.get('round_start_time')
    }
    return jsonify(response_data)

# ============================================================================
# PARTICIPANT MANAGEMENT
# ============================================================================

@app.route('/api/participants')
def get_participants():
    """Get all participants for researcher dashboard"""
    try:
        # Get session_code filter from query parameters
        session_code = request.args.get('session_code')
        
        # If no session code provided, return empty list
        if not session_code:
            return jsonify([])
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check if the tag column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'participants' AND column_name = 'tag'
        """)
        has_tag = cur.fetchone() is not None
        
        # Build query based on available columns
        if has_tag:
            cur.execute("""
                SELECT 
                    p.participant_id,
                    p.participant_code,
                    p.participant_type,
                    p.specialty_shape,
                    p.login_status,
                    COALESCE(p.money, 300) as money,
                    COALESCE(p.is_agent, p.participant_type = 'ai_agent') as is_agent,
                    p.agent_type,
                    COALESCE(p.agent_status, 'inactive') as agent_status,
                    COALESCE(p.last_activity, p.last_activity_timestamp) as last_activity,
                    COALESCE(p.session_code, '') as session_code,
                    p.tag,
                    p.orders,
                    p.orders_completed,
                    p.role,
                    p.current_round,
                    p.score
                FROM participants p
                WHERE UPPER(COALESCE(p.session_code, '')) = UPPER(%s)
                ORDER BY p.participant_code
            """, (session_code,))
        else:
            cur.execute("""
                SELECT 
                    p.participant_id,
                    p.participant_code,
                    p.participant_type,
                    p.specialty_shape,
                    p.login_status,
                    COALESCE(p.money, 300) as money,
                    (p.participant_type = 'ai_agent') as is_agent,
                    NULL as agent_type,
                    'inactive' as agent_status,
                    p.last_activity_timestamp as last_activity,
                    '' as session_code,
                    NULL as tag,
                    p.orders,
                    p.orders_completed,
                    p.role,
                    p.current_round,
                    p.score
                FROM participants p
                WHERE UPPER(COALESCE(p.session_code, '')) = UPPER(%s)
                ORDER BY p.participant_code
            """, (session_code,))
        
        rows = cur.fetchall()
        
        # Get experiment configuration for total orders
        cur.execute("""
            SELECT experiment_config FROM sessions 
            WHERE session_code = %s
        """, (session_code,))
        session_result = cur.fetchone()
        
        cur.close()
        return_db_connection(conn)
        
        # Get total orders from experiment config, default to 3
        total_orders = 3  # Default value
        if session_result and session_result.get('experiment_config'):
            try:
                config = session_result['experiment_config']
                if isinstance(config, str):
                    config = json.loads(config)
                total_orders = config.get('shapesPerOrder', 3)
            except (json.JSONDecodeError, TypeError):
                total_orders = 3
        
        # Map to frontend expected fields
        mapped = []
        for p in rows:
            # Determine participant type correctly
            participant_type = 'ai' if p['participant_type'] == 'ai_agent' else 'human'
            
            # For AI agents, extract the original name (remove session code suffix)
            display_name = p['participant_code']
            if participant_type == 'ai' and '_' in p['participant_code']:
                # Extract original name by removing the session code suffix
                # Format is: original_name_session_code
                display_name = p['participant_code'].rsplit('_', 1)[0]
            
            
            mapped.append({
                'id': display_name,  # Use display name (original name for agents)
                'internal_id': p['participant_code'],  # Keep internal ID for backend operations
                'type': participant_type,
                'specialty': p['specialty_shape'],
                'status': 'online' if p['login_status'] == 'active' else 'offline',
                'money': p['money'],
                'orders_completed': p.get('orders_completed', 0),  # Use actual orders_completed from database
                'total_orders': total_orders,  # Use fixed total orders from experiment config
                'trades_made': 0,  # TODO: Calculate from transactions table
                'shapes_bought': 0,  # TODO: Calculate from transactions table
                'shapes_sold': 0,  # TODO: Calculate from transactions table
                'login_time': p['last_activity'].strftime('%H:%M:%S') if p['last_activity'] else None,
                'tag': p['tag'],
                'session_code': p['session_code'],  # Include session code
                # Wordguessing fields (present for that experiment type)
                'role': p.get('role'),
                'current_round': p.get('current_round'),
                'score': p.get('score')
            })
        
        return jsonify(mapped)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/participants/register-daytrader', methods=['POST'])
def register_daytrader_participant():
    """Register a human participant for DayTrader experiment"""
    try:
        data = request.get_json()
        participant_code = data.get('participant_code')
        session_code = data.get('session_code')
        
        if not participant_code:
            return jsonify({"error": "Participant code required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # Use DayTrader game engine
        game_engine = get_game_engine("daytrader")
        result = game_engine.add_participant(session_code, participant_code)
        
        if result.get('success'):
            return jsonify({
                "success": True,
                "message": result.get('message', 'Participant registered successfully'),
                "participant_id": result.get('participant_id')
            })
        else:
            return jsonify({"error": result.get('message', 'Failed to register participant')}), 400
            
    except Exception as e:
        return jsonify({"error": f"Failed to register participant: {str(e)}"}), 500

@app.route('/api/daytrader/make-investment', methods=['POST'])
def make_daytrader_investment():
    """Make an investment in DayTrader experiment"""
    try:
        data = request.get_json()
        participant_code = data.get('participant_code')
        session_code = data.get('session_code')
        invest_price = data.get('invest_price')
        invest_decision_type = data.get('invest_decision_type', 'individual')
        
        if not all([participant_code, session_code, invest_price]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Get logger for this participant
        session_id = get_participant_session_id(participant_code, session_code)
        logger = get_human_logger(participant_code, session_id, session_code)
        
        # Use DayTrader game engine
        game_engine = get_game_engine("daytrader")
        result = game_engine.make_investment(
            participant_code, invest_price, invest_decision_type, session_code
        )
        
        # Log the investment action
        success = result.get('success', False)
        error_message = result.get('message') if not success else None
        logger.log_investment(invest_price, invest_decision_type, success, error_message)
        
        if result.get('success'):
            return jsonify({
                "success": True,
                "message": result.get('message', 'Investment recorded successfully'),
                "invest_id": result.get('invest_id')
            })
        else:
            return jsonify({"error": result.get('message', 'Failed to make investment')}), 400
            
    except Exception as e:
        # Log error if possible
        try:
            session_id = get_participant_session_id(participant_code, session_code)
            logger = get_human_logger(participant_code, session_id, session_code)
            logger.log_investment(invest_price, invest_decision_type, False, str(e))
        except:
            pass
        return jsonify({"error": f"Failed to make investment: {str(e)}"}), 500

@app.route('/api/daytrader/session-status/<session_code>')
def get_daytrader_session_status(session_code):
    """Get DayTrader session status"""
    try:
        game_engine = get_game_engine("daytrader")
        result = game_engine.get_session_status(session_code)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify({"error": result.get('message', 'Failed to get session status')}), 404
            
    except Exception as e:
        return jsonify({"error": f"Failed to get session status: {str(e)}"}), 500

@app.route('/api/daytrader/start-session', methods=['POST'])
def start_daytrader_session():
    """Start a DayTrader session"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        game_engine = get_game_engine("daytrader")
        result = game_engine.start_session(session_code)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify({"error": result.get('message', 'Failed to start session')}), 400
            
    except Exception as e:
        return jsonify({"error": f"Failed to start session: {str(e)}"}), 500

@app.route('/api/daytrader/end-session', methods=['POST'])
def end_daytrader_session():
    """End a DayTrader session"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        game_engine = get_game_engine("daytrader")
        result = game_engine.end_session(session_code)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify({"error": result.get('message', 'Failed to end session')}), 400
            
    except Exception as e:
        return jsonify({"error": f"Failed to end session: {str(e)}"}), 500

@app.route('/api/essayranking/end-session', methods=['POST'])
def end_essayranking_session():
    """End an Essay Ranking session"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        game_engine = get_game_engine("essayranking")
        result = game_engine.end_session(session_code)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify({"error": result.get('message', 'Failed to end session')}), 400
            
    except Exception as e:
        return jsonify({"error": f"Failed to end session: {str(e)}"}), 500

@app.route('/api/daytrader/investment-history')
def get_daytrader_investment_history():
    """Get investment history for a DayTrader session"""
    try:
        
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = request.args.get('session_code')
        
        if not session_code:
            return jsonify({'error': 'Session code required'}), 400
        
        # Get participant info
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT participant_id, session_id FROM participants 
            WHERE participant_code = %s AND session_code = %s
        """, (participant_code, session_code))
        
        participant = cur.fetchone()
        if not participant:
            cur.close()
            return_db_connection(conn)
            return jsonify({"error": "Participant not found"}), 404
        
        # Get investment history
        cur.execute("""
            SELECT invest_price, invest_decision_type, invest_timestamp
            FROM investments 
            WHERE participant_id = %s AND session_id = %s
            ORDER BY invest_timestamp DESC
        """, (participant['participant_id'], participant['session_id']))
        
        investments = cur.fetchall()
        
        cur.close()
        return_db_connection(conn)
        
        # Format investments for frontend
        formatted_investments = []
        for investment in investments:
            formatted_investments.append({
                'price': float(investment['invest_price']),
                'decision_type': investment['invest_decision_type'],
                'timestamp': investment['invest_timestamp'].isoformat() if investment['invest_timestamp'] else None
            })
        
        return jsonify({
            'success': True,
            'investments': formatted_investments
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/daytrader/clear-investments', methods=['POST'])
def clear_daytrader_investments():
    """Clear investment history for a DayTrader session"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({'error': 'Session code required'}), 400
        
        # Use DayTrader game engine
        game_engine = get_game_engine('daytrader')
        result = game_engine.clear_investments(session_code)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify({"error": result.get('message', 'Failed to clear investments')}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/participants/register', methods=['POST'])
def register_human_participant():
    """Register a human participant, handles normal and mTurk registration."""
    try:
        data = request.get_json()
        
        # mTurk parameters from URL query string
        mturk_worker_id = request.args.get('workerId')
        mturk_assignment_id = request.args.get('assignmentId')
        mturk_hit_id = request.args.get('hitId')
        is_mturk_preview = mturk_assignment_id == 'ASSIGNMENT_ID_NOT_AVAILABLE'

        # If it's an mTurk worker, use their workerId as the participant_code
        if mturk_worker_id:
            participant_code = mturk_worker_id
        else:
            participant_code = data.get('participant_code')

        session_code = data.get('session_code')
        specialty_override = data.get('specialty_shape')  # Optional override
        tag = data.get('tag')  # Optional tag
        wordguessing_role = data.get('wordguessingRole')  # WordGuessing role

        
        if not participant_code:
            return jsonify({"error": "Participant code required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
        except Exception as conn_error:
            print(f"[ERROR] Database connection failed: {conn_error}")
            return jsonify({"error": f"Database connection failed: {str(conn_error)}"}), 500
        
        # Check if participant already exists
        cur.execute("""
            SELECT participant_id FROM participants 
            WHERE participant_code = %s AND session_code = %s
        """, (participant_code, session_code))
        
        if cur.fetchone():
            cur.close()
            return_db_connection(conn)
            return jsonify({"error": "Participant already exists"}), 400
        
        # Get session ID
        cur.execute("SELECT session_id FROM sessions WHERE session_code = %s", (session_code,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            return_db_connection(conn)
            return jsonify({"error": "Session not found"}), 404
        
        session_id = session_result['session_id']
        
        # Get session config to check experiment type
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        # Use game engine factory to get the appropriate game engine
        try:
            game_engine = get_game_engine(experiment_type)
        except Exception as e:
            print(f"[ERROR] Failed to get game engine for {experiment_type}: {e}")
            # Fallback to shapefactory for backward compatibility
            game_engine = get_game_engine('shapefactory')
            experiment_type = 'shapefactory'
        
        # Determine specialty and orders based on experiment type
        specialty_shape = None
        orders_json = None
        color_shape_combination = None
        
        if experiment_type == 'shapefactory':
            # Only call shape-related functions for ShapeFactory experiments
            specialty_shape = specialty_override or get_unique_specialty_for_session(session_code, cur)
            if specialty_shape:
                orders_json = generate_deterministic_orders(specialty_shape, session_code)
                color_shape_combination = f"{participant_code} {specialty_shape.title()}"
        elif experiment_type == 'essayranking':
            # For essay ranking, no specialty shapes or orders needed
            specialty_shape = "essay_ranker"
            color_shape_combination = participant_code
            orders_json = None
        elif experiment_type == 'wordguessing':
            # For wordguessing, use simple defaults
            specialty_shape = "N/A"
            color_shape_combination = participant_code
            orders_json = None
        else:
            # For other experiments (DayTrader, etc.), use simple defaults
            specialty_shape = "default"
            color_shape_combination = participant_code
            orders_json = None
        
        # Insert participant
        # Use experiment-specific fields based on experiment type
        if experiment_type == 'shapefactory':
            cur.execute("""
                INSERT INTO participants 
                (participant_id, session_id, participant_code, participant_type, 
                 color_shape_combination, specialty_shape, login_status, money, 
                 is_agent, agent_type, agent_status, last_activity, session_code, tag, orders,
                 mturk_worker_id, mturk_assignment_id, mturk_hit_id, is_preview)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), session_id, participant_code, 'human',
                color_shape_combination, specialty_shape, 'not_logged_in', get_session_config(session_code).get('startingMoney', 300),
                False, None, 'inactive', datetime.now(timezone.utc), session_code, tag, orders_json,
                mturk_worker_id, mturk_assignment_id, mturk_hit_id, is_mturk_preview
            ))
        elif experiment_type == 'essayranking':
            # For essay ranking experiments, use essay-specific fields
            cur.execute("""
                INSERT INTO participants 
                (participant_id, session_id, participant_code, participant_type, 
                 color_shape_combination, specialty_shape, login_status, money, 
                 is_agent, agent_type, agent_status, last_activity, session_code, tag, orders,
                 current_rankings, submitted_rankings_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), session_id, participant_code, 'human',
                color_shape_combination, specialty_shape, 'not_logged_in', 0,  # No money for essay ranking
                False, None, 'inactive', datetime.now(timezone.utc), session_code, tag, None,
                '[]', 0  # Initialize empty rankings and count
            ))
        elif experiment_type == 'wordguessing':
            # For wordguessing experiments, use wordguessing-specific fields
            assigned_role = wordguessing_role if wordguessing_role else None
            cur.execute("""
                INSERT INTO participants 
                (participant_id, session_id, participant_code, participant_type, 
                 color_shape_combination, specialty_shape, login_status, money, 
                 is_agent, agent_type, agent_status, last_activity, session_code, tag, orders,
                 role, current_round, score, assigned_words)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), session_id, participant_code, 'human',
                color_shape_combination, specialty_shape, 'not_logged_in', 0,  # No money for wordguessing
                False, None, 'inactive', datetime.now(timezone.utc), session_code, tag, None,
                assigned_role, 1, 0, '[]'  # Use assigned role or None for auto-assignment, round 1, score 0, empty words
            ))
        else:
            # For other experiments (DayTrader, etc.), use minimal fields
            cur.execute("""
                INSERT INTO participants 
                (participant_id, session_id, participant_code, participant_type, 
                 color_shape_combination, specialty_shape, login_status, money, 
                 is_agent, agent_type, agent_status, last_activity, session_code, tag, orders)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), session_id, participant_code, 'human',
                color_shape_combination, specialty_shape, 'not_logged_in', get_session_config(session_code).get('startingMoney', 300),
                False, None, 'inactive', datetime.now(timezone.utc), session_code, tag, None
            ))
        
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        return jsonify({
            "success": True,
            "message": "Participant registered successfully",
            "participant_code": participant_code,
            "specialty_shape": specialty_shape,
            "tag": tag,
            "experiment_type": experiment_type,
            "role": wordguessing_role if experiment_type == 'wordguessing' else None
        })
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"[ERROR] Human participant registration failed: {str(e)}")
        print(f"[ERROR] Traceback: {error_traceback}")
        
        # Try to cleanup database connection if it exists
        try:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                return_db_connection(conn)
        except:
            pass
            
        return jsonify({"error": str(e), "traceback": error_traceback}), 500

@app.route('/api/participants/update', methods=['PUT'])
def update_participant():
    """Update an existing participant"""
    try:
        data = request.get_json()
        participant_code = data.get('participant_code')
        session_code = data.get('session_code', 'DEMO001')
        update_data = data.get('update_data')

        if not participant_code or not update_data:
            return jsonify({"error": "Participant code and update data required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Get current participant info
        cur.execute("""
            SELECT participant_id, login_status, money, agent_status
            FROM participants 
            WHERE participant_code = %s AND session_code = %s
        """, (participant_code, session_code))
        participant = cur.fetchone()

        if not participant:
            cur.close()
            return_db_connection(conn)
            return jsonify({"error": "Participant not found"}), 404

        # Prepare update fields
        update_fields = []
        update_values = []
        update_params = []

        for key, value in update_data.items():
            if key == 'login_status':
                update_fields.append(f"{key} = %s")
                update_values.append(value)
                update_params.append(value)
            elif key == 'money':
                update_fields.append(f"{key} = %s")
                update_values.append(value)
                update_params.append(value)
            elif key == 'agent_status':
                update_fields.append(f"{key} = %s")
                update_values.append(value)
                update_params.append(value)
            elif key == 'specialty_shape':
                update_fields.append(f"{key} = %s")
                update_values.append(value)
                update_params.append(value)
            elif key == 'agent_type':
                update_fields.append(f"{key} = %s")
                update_values.append(value)
                update_params.append(value)
            elif key == 'last_activity':
                update_fields.append(f"{key} = %s")
                update_values.append(value)
                update_params.append(value)

        if not update_fields:
            cur.close()
            return_db_connection(conn)
            return jsonify({"error": "No valid fields to update"}), 400

        update_fields_str = ", ".join(update_fields)
        update_params.append(participant_code)
        update_params.append(session_code)

        cur.execute(f"""
            UPDATE participants 
            SET {update_fields_str}
            WHERE participant_code = %s AND session_code = %s
        """, update_params)

        conn.commit()
        cur.close()
        return_db_connection(conn)

        return jsonify({
            "success": True,
            "message": "Participant updated successfully",
            "participant_code": participant_code,
            "updated_data": update_data
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/participants/delete', methods=['DELETE'])
def delete_participant():
    """Delete a participant"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        participant_id = data.get('participant_id')  # internal UUID/id
        participant_code = data.get('participant_code')  # may be session-aware or display-only
        display_name = data.get('display_name')  # UI-friendly name (e.g., without session suffix)
        session_code = data.get('session_code')

        if not session_code:
            return jsonify({"error": "Session code required"}), 400

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Attempt to resolve participant using multiple strategies
        resolved = None

        # 1) By explicit participant_id + session
        if participant_id:
            cur.execute(
                """
                SELECT participant_id, participant_code FROM participants
                WHERE participant_id = %s AND UPPER(COALESCE(session_code, '')) = UPPER(%s)
                LIMIT 1
                """,
                (participant_id, session_code),
            )
            resolved = cur.fetchone()

        # 2) By provided participant_code (as-is)
        if not resolved and participant_code:
            cur.execute(
                """
                SELECT participant_id, participant_code FROM participants
                WHERE participant_code = %s AND UPPER(COALESCE(session_code, '')) = UPPER(%s)
                LIMIT 1
                """,
                (participant_code, session_code),
            )
            resolved = cur.fetchone()

            # 2b) If not found and code seems like display code (no suffix), try appending _<session_code>
            if not resolved and '_' not in participant_code:
                derived_code = f"{participant_code}_{session_code}"
                cur.execute(
                    """
                    SELECT participant_id, participant_code FROM participants
                    WHERE participant_code = %s AND UPPER(COALESCE(session_code, '')) = UPPER(%s)
                    LIMIT 1
                    """,
                    (derived_code, session_code),
                )
                resolved = cur.fetchone()

        # 3) By display_name (derive session-aware code)
        if not resolved and display_name:
            derived_code = (
                display_name if '_' in display_name else f"{display_name}_{session_code}"
            )
            cur.execute(
                """
                SELECT participant_id, participant_code FROM participants
                WHERE participant_code = %s AND UPPER(COALESCE(session_code, '')) = UPPER(%s)
                LIMIT 1
                """,
                (derived_code, session_code),
            )
            resolved = cur.fetchone()

        if not resolved:
            cur.close()
            return_db_connection(conn)
            tried = {
                "participant_id": participant_id,
                "participant_code": participant_code,
                "display_name": display_name,
            }
            return jsonify({"error": "Participant not found", "tried": tried}), 404

        # Delete by participant_id to be precise
        cur.execute(
            """
            DELETE FROM participants
            WHERE participant_id = %s
            """,
            (resolved['participant_id'],),
        )

        conn.commit()
        cur.close()
        return_db_connection(conn)

        return jsonify({
            "success": True,
            "message": "Participant deleted successfully",
            "participant_code": resolved['participant_code'],
            "participant_id": resolved['participant_id'],
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# AUTHENTICATION
# ============================================================================

@app.route('/api/auth/login', methods=['POST'])
def participant_login():
    """Login a participant"""
    try:
        data = request.get_json()
        participant_code = data.get('participant_code')
        session_code = data.get('session_code')
        
        if not participant_code:
            return jsonify({"error": "Participant code required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get participant
        cur.execute("""
            SELECT * FROM participants 
            WHERE participant_code = %s AND session_code = %s
        """, (participant_code, session_code))
        
        participant = cur.fetchone()
        
        if not participant:
            cur.close()
            return_db_connection(conn)
            return jsonify({
                "success": False,
                "message": f"Participant '{participant_code}' not found in session '{session_code}'. Please register first or check your credentials."
            }), 404
        
        # Get session ID for logging
        session_id = participant['session_id']
        logger = get_human_logger(participant_code, session_id, session_code)
        
        # Generate JWT token
        token_payload = {
            'participant_code': participant_code,
            'session_code': session_code,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        
        token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        # Update login status
        cur.execute("""
            UPDATE participants 
            SET login_status = 'active', last_activity = %s
            WHERE participant_code = %s AND session_code = %s
        """, (datetime.now(timezone.utc), participant_code, session_code))
        
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        # Log successful login
        logger.log_login(session_code)
        
        return jsonify({
            "success": True,
            "token": token,
            "participant": dict(participant),
            "session": {
                "session_code": session_code,
                "session_id": str(participant['session_id'])
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/auth/verify', methods=['POST'])
def verify_token():
    """Verify JWT token"""
    try:
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return jsonify({"error": "Token required"}), 400
        
        # Decode token
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        return jsonify({
            "valid": True,
            "payload": payload
        })
        
    except jwt.ExpiredSignatureError:
        return jsonify({"valid": False, "error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"valid": False, "error": "Invalid token"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def participant_logout():
    """Logout a participant"""
    try:
        data = request.get_json()
        participant_code = data.get('participant_code')
        session_code = data.get('session_code')
        
        if not participant_code:
            return jsonify({"error": "Participant code required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # Get session ID for logging
        session_id = get_participant_session_id(participant_code, session_code)
        logger = get_human_logger(participant_code, session_id, session_code)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Update logout status
        cur.execute("""
            UPDATE participants 
            SET login_status = 'not_logged_in', last_activity = %s
            WHERE participant_code = %s AND session_code = %s
        """, (datetime.now(timezone.utc), participant_code, session_code))
        
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        # Log successful logout
        logger.log_logout()
        
        return jsonify({
            "success": True,
            "message": "Logged out successfully"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# GAME API ENDPOINTS
# ============================================================================

def verify_participant_token(request):
    """Verify participant token from request"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except:
        return None

def get_current_participant_id(participant_code, session_code=None):
    """Get current participant ID from database (session-isolated)"""
    try:
        if not session_code:
            return None
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT participant_id FROM participants 
            WHERE participant_code = %s AND session_code = %s
        """, (participant_code, session_code))
        
        result = cur.fetchone()
        cur.close()
        return_db_connection(conn)
        
        return result['participant_id'] if result else None
    except Exception as e:
        print(f"Error getting participant ID: {e}")
        return None

@app.route('/api/game-state')
def get_game_state():
    """Get game state for a participant"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # Get session ID for logging
        session_id = get_participant_session_id(participant_code, session_code)
        logger = get_human_logger(participant_code, session_id, session_code)
        
        # Get participant info
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cur.execute("""
                SELECT * FROM participants 
                WHERE participant_code = %s AND session_code = %s
            """, (participant_code, session_code))
            
            participant = cur.fetchone()
            if not participant:
                return jsonify({"error": "Participant not found"}), 404
            
            # Get experiment type from session first
            session_config = get_session_config(session_code)
            experiment_type = session_config.get('experiment_type', 'shapefactory')
            
            # Get other participants - use experiment-specific fields
            if experiment_type == 'wordguessing':
                cur.execute("""
                    SELECT participant_code, role, login_status, current_round, score
                    FROM participants 
                    WHERE session_code = %s AND participant_code != %s
                """, (session_code, participant_code))
            else:
                cur.execute("""
                    SELECT participant_code, specialty_shape, login_status, money, 
                           COALESCE(specialty_production_used, 0) as specialty_production_used
                    FROM participants 
                    WHERE session_code = %s AND participant_code != %s
                """, (session_code, participant_code))
            
            other_participants = cur.fetchall()
        
        # Get game engine state using appropriate engine
        game_engine = get_game_engine(experiment_type)
        private_state = game_engine.get_participant_state(participant_code, session_code)
        
        public_state = game_engine.get_public_state(session_code)
        
        # Extract display names for agents
        def extract_display_name(participant_code):
            if participant_code and '_' in participant_code:
                return participant_code.rsplit('_', 1)[0]
            return participant_code
        
        # Add other participants to public state with experiment-specific data
        other_participants_with_data = []
        
        for p in other_participants:
            participant_dict = dict(p)
            # Extract display name for agents
            participant_dict['participant_code'] = extract_display_name(participant_dict['participant_code'])
            
            # Add experiment-specific fields
            if experiment_type == 'wordguessing':
                # For wordguessing, use participant_code as display name
                participant_dict['display_name'] = participant_dict['participant_code']
            else:
                # For other experiments, add production data
                participant_dict['max_production_num'] = session_config.get('maxProductionNum', 6)
            
            other_participants_with_data.append(participant_dict)
        
        public_state['other_participants'] = other_participants_with_data
        
        # Add experiment configuration to public state
        public_state['experiment_config'] = session_config
        
        # Process other participants for the response
        processed_other_participants = []
        for p in other_participants:
            p_dict = dict(p)
            p_dict['participant_code'] = extract_display_name(p_dict['participant_code'])
            processed_other_participants.append(p_dict)
        
        return jsonify({
            "game_state": {
                "private_state": private_state,
                "public_state": public_state
            },
            "participant": dict(participant),
            "other_participants": processed_other_participants,
            "communication_level": session_config.get('communicationLevel', 'chat'),
            "awareness_dashboard_enabled": session_config.get('awarenessDashboard', 'off') == 'on',
            "awareness_dashboard_config": session_config.get('awarenessDashboardConfig', {
                'showMoney': True,
                'showProductionCount': True,
                'showOrderProgress': True
            }),
            "experiment_interface_config": session_config.get('experimentInterfaceConfig', {})
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/trades')
def get_trades():
    """Get all trades for researcher dashboard"""
    try:
        # Get session_code from query parameters
        session_code = request.args.get('session_code')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get all transactions with participant information, filtered by session
        if session_code:
            cur.execute("""
                SELECT 
                    t.transaction_id as id,
                    t.session_id,
                    t.seller_id,
                    t.buyer_id,
                    t.proposer_id,
                    t.recipient_id,
                    t.offer_type,
                    t.shape_type as shape,
                    t.shape_color,
                    t.quantity,
                    t.agreed_price as price,
                    t.transaction_status as status,
                    t.proposed_timestamp as timestamp,
                    t.agreed_timestamp,
                    t.completed_timestamp,
                    t.transaction_data,
                    proposer.participant_code as from,
                    recipient.participant_code as to
                FROM transactions t
                LEFT JOIN participants proposer ON t.proposer_id = proposer.participant_id
                LEFT JOIN participants recipient ON t.recipient_id = recipient.participant_id
                WHERE t.session_id = (SELECT session_id FROM sessions WHERE UPPER(session_code) = UPPER(%s))
                ORDER BY t.proposed_timestamp DESC
            """, (session_code,))
        else:
            # If no session code provided, return empty results
            cur.execute("""
                SELECT 
                    t.transaction_id as id,
                    t.session_id,
                    t.seller_id,
                    t.buyer_id,
                    t.proposer_id,
                    t.recipient_id,
                    t.offer_type,
                    t.shape_type as shape,
                    t.shape_color,
                    t.quantity,
                    t.agreed_price as price,
                    t.transaction_status as status,
                    t.proposed_timestamp as timestamp,
                    t.agreed_timestamp,
                    t.completed_timestamp,
                    t.transaction_data,
                    proposer.participant_code as from,
                    recipient.participant_code as to
                FROM transactions t
                LEFT JOIN participants proposer ON t.proposer_id = proposer.participant_id
                LEFT JOIN participants recipient ON t.recipient_id = recipient.participant_id
                WHERE 1=0  -- Return no results if no session code
                ORDER BY t.proposed_timestamp DESC
            """)
        
        trades = cur.fetchall()
        cur.close()
        return_db_connection(conn)
        
        # Separate trades into pending and completed
        pending_offers = []
        completed_trades = []
        
        for trade in trades:
            trade_dict = dict(trade)
            
            # Extract display names for agents (remove session code suffix)
            from_name = trade_dict['from']
            to_name = trade_dict['to']
            
            if from_name and '_' in from_name:
                from_name = from_name.rsplit('_', 1)[0]
            if to_name and '_' in to_name:
                to_name = to_name.rsplit('_', 1)[0]
            
            trade_dict['from'] = from_name
            trade_dict['to'] = to_name
            
            if trade['status'] == 'proposed':
                pending_offers.append(trade_dict)
            elif trade['status'] in ['completed', 'agreed', 'cancelled']:
                completed_trades.append(trade_dict)
        
        return jsonify({
            'pending_offers': pending_offers,
            'completed_trades': completed_trades
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/messages')
def get_messages():
    """Get all messages for researcher dashboard"""
    try:
        # Get session_code from query parameters
        session_code = request.args.get('session_code')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get all messages with participant information, filtered by session
        if session_code:
            cur.execute("""
                SELECT 
                    m.message_id,
                    m.sender_id,
                    m.recipient_id,
                    m.message_content as content,
                    m.message_timestamp as timestamp,
                    m.message_type,
                    sender.participant_code as sender,
                    COALESCE(recipient.participant_code, 'all') as recipient
                FROM messages m
                LEFT JOIN participants sender ON m.sender_id = sender.participant_id
                LEFT JOIN participants recipient ON m.recipient_id = recipient.participant_id
                WHERE m.session_id = (SELECT session_id FROM sessions WHERE UPPER(session_code) = UPPER(%s))
                ORDER BY m.message_timestamp DESC
            """, (session_code,))
        else:
            # If no session code provided, return empty results
            cur.execute("""
                SELECT 
                    m.message_id,
                    m.sender_id,
                    m.recipient_id,
                    m.message_content as content,
                    m.message_timestamp as timestamp,
                    m.message_type,
                    sender.participant_code as sender,
                    COALESCE(recipient.participant_code, 'all') as recipient
                FROM messages m
                LEFT JOIN participants sender ON m.sender_id = sender.participant_id
                LEFT JOIN participants recipient ON m.recipient_id = recipient.participant_id
                WHERE 1=0  -- Return no results if no session code
                ORDER BY m.message_timestamp DESC
            """)
        
        messages = cur.fetchall()
        cur.close()
        return_db_connection(conn)
        
        # Extract display names for agents in the results
        def extract_display_name(participant_code):
            if participant_code and '_' in participant_code:
                return participant_code.rsplit('_', 1)[0]
            return participant_code
        
        # Process messages to extract display names
        processed_messages = []
        for msg in messages:
            msg_dict = dict(msg)
            msg_dict['sender'] = extract_display_name(msg_dict['sender'])
            if msg_dict['recipient'] != 'all':
                msg_dict['recipient'] = extract_display_name(msg_dict['recipient'])
            processed_messages.append(msg_dict)
        
        return jsonify(processed_messages)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/participant-trades')
def get_participant_trades():
    """Get trade data for a specific participant pair or all trades for the current participant"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')
        target_participant = request.args.get('target')
        all_trades = request.args.get('all') == 'true'
        
        if not all_trades and not target_participant:
            return jsonify({"error": "Target participant required or all=true parameter"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get current participant ID
        cur.execute("""
            SELECT participant_id FROM participants 
            WHERE participant_code = %s AND session_code = %s
        """, (participant_code, session_code))
        current_participant = cur.fetchone()
        
        if not current_participant:
            cur.close()
            return_db_connection(conn)
            return jsonify({"error": "Current participant not found"}), 404
        
        current_id = current_participant['participant_id']
        
        # If all_trades is True, get all trades for the current participant
        if all_trades:
            # Get all pending trade offers involving the current participant
            cur.execute("""
                SELECT 
                    t.transaction_id,
                    t.proposer_id,
                    t.recipient_id,
                    t.offer_type,
                    t.shape_type as shape,
                    t.quantity,
                    t.agreed_price as price,
                    t.transaction_status,
                    t.proposed_timestamp,
                    t.agreed_timestamp,
                    proposer.participant_code as proposer_code,
                    recipient.participant_code as recipient_code,
                    CASE 
                        WHEN t.proposer_id = %s THEN t.offer_type
                        WHEN t.recipient_id = %s THEN t.offer_type
                    END as participant_role,
                    CASE 
                        WHEN t.proposer_id = %s THEN true
                        ELSE false
                    END as is_outgoing
                FROM transactions t
                LEFT JOIN participants proposer ON t.proposer_id = proposer.participant_id
                LEFT JOIN participants recipient ON t.recipient_id = recipient.participant_id
                WHERE t.transaction_status = 'proposed'
                AND (t.proposer_id = %s OR t.recipient_id = %s)
                ORDER BY t.proposed_timestamp DESC
            """, (current_id, current_id, current_id, current_id, current_id))
            
            pending_offers = cur.fetchall()
            
            # Also return completed trade history involving the current participant
            # Include 'agreed' as part of completed so UI reflects immediately
            cur.execute("""
                SELECT 
                    t.transaction_id,
                    t.proposer_id,
                    t.recipient_id,
                    t.offer_type,
                    t.shape_type as shape,
                    t.quantity,
                    t.agreed_price as price,
                    t.transaction_status,
                    t.completed_timestamp,
                    proposer.participant_code as proposer_code,
                    recipient.participant_code as recipient_code,
                    CASE 
                        WHEN t.transaction_status IN ('completed','agreed') THEN
                            CASE 
                                WHEN t.proposer_id = %s THEN 
                                    CASE WHEN t.offer_type = 'sell' THEN 'sold' ELSE 'bought' END
                                WHEN t.recipient_id = %s THEN 
                                    CASE WHEN t.offer_type = 'buy' THEN 'sold' ELSE 'bought' END
                            END
                        WHEN t.transaction_status = 'cancelled' THEN 'cancelled'
                    END as type
                FROM transactions t
                LEFT JOIN participants proposer ON t.proposer_id = proposer.participant_id
                LEFT JOIN participants recipient ON t.recipient_id = recipient.participant_id
                WHERE t.transaction_status IN ('completed','cancelled','agreed')
                AND (t.proposer_id = %s OR t.recipient_id = %s)
                ORDER BY COALESCE(t.completed_timestamp, t.agreed_timestamp) DESC
            """, (current_id, current_id, current_id, current_id))
            
            completed_trades = cur.fetchall()
            
        else:
            # Get target participant ID for specific pair - handle both human and agent participant codes
            cur.execute("""
                SELECT participant_id FROM participants 
                WHERE participant_code = %s AND session_code = %s
            """, (target_participant, session_code))
            target_participant_data = cur.fetchone()
            
            # If not found, try with session code suffix (for agent lookup by display name)
            if not target_participant_data:
                agent_code_with_session = f"{target_participant}_{session_code}"
                cur.execute("""
                    SELECT participant_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                """, (agent_code_with_session, session_code))
                target_participant_data = cur.fetchone()
            
            if not target_participant_data:
                cur.close()
                return_db_connection(conn)
                return jsonify({"error": "Target participant not found"}), 404
            
            target_id = target_participant_data['participant_id']
            
            # Get session ID for logging
            session_id = get_participant_session_id(participant_code)
            logger = get_human_logger(participant_code, session_id, session_code)
        
        # Get pending trade offers between these participants (only for specific pair)
        if not all_trades:
            cur.execute("""
                SELECT 
                    t.transaction_id,
                    t.proposer_id,
                    t.recipient_id,
                    t.offer_type,
                    t.shape_type as shape,
                    t.quantity,
                    t.agreed_price as price,
                    t.transaction_status,
                    t.proposed_timestamp,
                    t.agreed_timestamp,
                    proposer.participant_code as proposer_code,
                    recipient.participant_code as recipient_code,
                    CASE 
                        WHEN t.proposer_id = %s THEN t.offer_type
                        WHEN t.recipient_id = %s THEN t.offer_type
                    END as participant_role,
                    CASE 
                        WHEN t.proposer_id = %s THEN true
                        ELSE false
                    END as is_outgoing
                FROM transactions t
                LEFT JOIN participants proposer ON t.proposer_id = proposer.participant_id
                LEFT JOIN participants recipient ON t.recipient_id = recipient.participant_id
                WHERE t.transaction_status = 'proposed'
                AND ((t.proposer_id = %s AND t.recipient_id = %s) OR (t.proposer_id = %s AND t.recipient_id = %s))
                ORDER BY t.proposed_timestamp DESC
            """, (current_id, current_id, current_id, target_id, target_id, current_id))
            
            pending_offers = cur.fetchall()
            
            # Get completed trades between these participants
            cur.execute("""
                SELECT 
                    t.transaction_id,
                    t.proposer_id,
                    t.recipient_id,
                    t.offer_type,
                    t.shape_type as shape,
                    t.quantity,
                    t.agreed_price as price,
                    t.transaction_status,
                    t.completed_timestamp,
                    proposer.participant_code as proposer_code,
                    recipient.participant_code as recipient_code,
                    CASE 
                        WHEN t.transaction_status = 'completed' THEN
                            CASE 
                                WHEN t.proposer_id = %s THEN 
                                    CASE WHEN t.offer_type = 'sell' THEN 'sold' ELSE 'bought' END
                                WHEN t.recipient_id = %s THEN 
                                    CASE WHEN t.offer_type = 'buy' THEN 'sold' ELSE 'bought' END
                            END
                        WHEN t.transaction_status = 'cancelled' THEN
                            CASE 
                                WHEN t.proposer_id = %s THEN 'declined'
                                WHEN t.recipient_id = %s THEN 'declined'
                            END
                    END as type
                FROM transactions t
                LEFT JOIN participants proposer ON t.proposer_id = proposer.participant_id
                LEFT JOIN participants recipient ON t.recipient_id = recipient.participant_id
                WHERE t.transaction_status IN ('completed', 'cancelled')
                AND ((t.proposer_id = %s AND t.recipient_id = %s) OR (t.proposer_id = %s AND t.recipient_id = %s))
                ORDER BY COALESCE(t.completed_timestamp, t.agreed_timestamp) DESC
            """, (current_id, current_id, current_id, current_id, current_id, target_id, target_id, current_id))
            
            completed_trades = cur.fetchall()
        
        cur.close()
        return_db_connection(conn)
        
        # Extract display names for agents in the results
        def extract_display_name(participant_code):
            if participant_code and '_' in participant_code:
                return participant_code.rsplit('_', 1)[0]
            return participant_code
        
        # Process pending offers
        processed_pending_offers = []
        for offer in pending_offers:
            offer_dict = dict(offer)
            offer_dict['proposer_code'] = extract_display_name(offer_dict['proposer_code'])
            offer_dict['recipient_code'] = extract_display_name(offer_dict['recipient_code'])
            processed_pending_offers.append(offer_dict)
        
        # Process completed trades
        processed_completed_trades = []
        for trade in completed_trades:
            trade_dict = dict(trade)
            trade_dict['proposer_code'] = extract_display_name(trade_dict['proposer_code'])
            trade_dict['recipient_code'] = extract_display_name(trade_dict['recipient_code'])
            processed_completed_trades.append(trade_dict)
        
        return jsonify({
            "pending_offers": processed_pending_offers,
            "completed_trades": processed_completed_trades
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/participant-messages')
def get_participant_messages():
    """Get message data for a specific participant pair"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')
        target_participant = request.args.get('target')
        
        if not target_participant:
            return jsonify({"error": "Target participant required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get participant IDs - handle both human and agent participant codes
        # For current participant (from token), use the exact code
        cur.execute("""
            SELECT participant_id FROM participants 
            WHERE participant_code = %s AND session_code = %s
        """, (participant_code, session_code))
        current_participant = cur.fetchone()
        
        # For target participant, try exact match first, then try with session code suffix for agents
        cur.execute("""
            SELECT participant_id FROM participants 
            WHERE participant_code = %s AND session_code = %s
        """, (target_participant, session_code))
        target_participant_data = cur.fetchone()
        
        # If not found, try with session code suffix (for agent lookup by display name)
        if not target_participant_data:
            agent_code_with_session = f"{target_participant}_{session_code}"
            cur.execute("""
                SELECT participant_id FROM participants 
                WHERE participant_code = %s AND session_code = %s
            """, (agent_code_with_session, session_code))
            target_participant_data = cur.fetchone()
        
        if not current_participant or not target_participant_data:
            cur.close()
            return_db_connection(conn)
            return jsonify({"error": "Participant not found"}), 404
        
        # Get session ID for logging
        session_id = get_participant_session_id(participant_code)
        logger = get_human_logger(participant_code, session_id, session_code)
        
        current_id = current_participant['participant_id']
        target_id = target_participant_data['participant_id']
        
        # Get messages between these participants
        cur.execute("""
            SELECT 
                m.message_id,
                m.sender_id,
                m.recipient_id,
                m.message_content as content,
                m.message_timestamp as timestamp,
                m.message_type,
                sender.participant_code as sender,
                COALESCE(recipient.participant_code, 'all') as recipient
            FROM messages m
            LEFT JOIN participants sender ON m.sender_id = sender.participant_id
            LEFT JOIN participants recipient ON m.recipient_id = recipient.participant_id
            WHERE ((m.sender_id = %s AND m.recipient_id = %s) OR (m.sender_id = %s AND m.recipient_id = %s))
            ORDER BY m.message_timestamp ASC
        """, (current_id, target_id, target_id, current_id))
        
        messages = cur.fetchall()
        cur.close()
        return_db_connection(conn)
        
        # Extract display names for agents in the results
        def extract_display_name(participant_code):
            if participant_code and '_' in participant_code:
                return participant_code.rsplit('_', 1)[0]
            return participant_code
        
        # Process messages to extract display names
        processed_messages = []
        for msg in messages:
            msg_dict = dict(msg)
            msg_dict['sender'] = extract_display_name(msg_dict['sender'])
            if msg_dict['recipient'] != 'all':
                msg_dict['recipient'] = extract_display_name(msg_dict['recipient'])
            processed_messages.append(msg_dict)
        
        return jsonify({
            "messages": processed_messages
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/participants/status')
def get_participants_status():
    """Get participants status for researcher dashboard"""
    try:
        # Get session_code from query parameters
        session_code = request.args.get('session_code')
        if not session_code:
            return jsonify({"error": "session_code parameter required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT 
                p.participant_id,
                p.participant_code,
                p.participant_type,
                p.specialty_shape,
                p.login_status,
                COALESCE(p.money, 300) as money,
                COALESCE(p.is_agent, p.participant_type = 'ai_agent') as is_agent,
                p.agent_type,
                p.agent_status,
                p.last_activity,
                p.session_code,
                p.orders,
                p.orders_completed,
                COALESCE(p.specialty_production_used, 0) as specialty_production_used
            FROM participants p
            WHERE p.session_code = %s
            ORDER BY p.participant_code
        """, (session_code,))
        
        participants = cur.fetchall()
        
        # Get experiment configuration for total orders using the session_code parameter
        total_orders = 3  # Default value
        cur.execute("""
            SELECT experiment_config FROM sessions 
            WHERE session_code = %s
        """, (session_code,))
        session_result = cur.fetchone()
        if session_result and session_result.get('experiment_config'):
            try:
                config = session_result['experiment_config']
                if isinstance(config, str):
                    config = json.loads(config)
                total_orders = config.get('shapesPerOrder', 3)
            except (json.JSONDecodeError, TypeError):
                total_orders = 3
        
        cur.close()
        return_db_connection(conn)
        
        # Map to frontend expected format with proper participant type and orders data
        mapped = []
        for p in participants:
            # Calculate completion percentage
            completion_percentage = 0
            if total_orders > 0:
                completion_percentage = round((p.get('orders_completed', 0) / total_orders) * 100)
            
            # Determine participant type correctly
            participant_type = 'ai' if p['participant_type'] == 'ai_agent' else 'human'
            
            # For AI agents, extract the original name (remove session code suffix)
            display_name = p['participant_code']
            if participant_type == 'ai' and '_' in p['participant_code']:
                # Extract original name by removing the session code suffix
                # Format is: original_name_session_code
                display_name = p['participant_code'].rsplit('_', 1)[0]
            
            mapped.append({
                'participant_code': display_name,  # Use display name (original name for agents)
                'internal_participant_code': p['participant_code'],  # Keep internal ID for backend operations
                'participant_type': participant_type,
                'specialty_shape': p['specialty_shape'],
                'money': p['money'],
                'orders_completed': p.get('orders_completed', 0),
                'total_orders': total_orders,  # Use fixed total orders from experiment config
                'completion_percentage': completion_percentage,
                'specialty_production_used': p.get('specialty_production_used', 0),
                'login_status': 'active' if p['login_status'] == 'active' else 'inactive'
            })
        
        return jsonify(mapped)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/produce-shape', methods=['POST'])
def produce_shape():
    """Produce shapes"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')
        data = request.get_json()
        shape = data.get('shape')
        quantity = data.get('quantity', 1)
        
        if not shape:
            return jsonify({"error": "Shape required"}), 400

        
        # Get session ID for logging
        session_id = get_participant_session_id(participant_code, session_code)
        logger = get_human_logger(participant_code, session_id, session_code)
        
        # Get experiment type from session
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        # Get game engine
        game_engine = get_game_engine(experiment_type)
        result = game_engine.produce_shape(participant_code, shape, quantity, session_code)
        
        # Log the production action
        success = result.get('success', False)
        error_message = result.get('error') if not success else None
        logger.log_production(shape, quantity, success, error_message)
        
        # Emit production started event
        if result.get('success'):
            # Get updated participant data to include production count
            try:
                game_engine = get_game_engine(experiment_type)
                participant_state = game_engine.get_participant_state(participant_code, session_code)
                production_count = participant_state.get('specialty_production_used', 0)
            except Exception as e:
                print(f"Warning: Could not get updated production count: {e}")
                production_count = None
            
            socketio.emit('production_started', {
                'participant_code': participant_code,
                'session_code': session_code,
                'shape': shape,
                'quantity': quantity,
                'new_production_count': production_count,
                'timestamp': datetime.now().isoformat()
            })
        
        return jsonify(result)
        
    except Exception as e:
        # Log the error if we have a logger
        try:
            participant_code = verify_participant_token(request).get('participant_code') if verify_participant_token(request) else None
            session_code = verify_participant_token(request).get('session_code') if verify_participant_token(request) else None
            if participant_code:
                session_id = get_participant_session_id(participant_code, session_code)
                logger = get_human_logger(participant_code, session_id, session_code)
                logger.log_production(shape, 1, False, str(e))
        except:
            pass
        return jsonify({"error": str(e)}), 500

@app.route('/api/process-completed-productions', methods=['POST'])
def process_completed_productions():
    """Process completed production items and move them to inventory"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')
        
        # Get experiment type from session (default to shapefactory for this operation)
        experiment_type = 'shapefactory'  # process_completed_productions is primarily for ShapeFactory
        
        # Get game engine
        game_engine = get_game_engine(experiment_type)
        result = game_engine.process_completed_productions()
        
        # Emit production completed events for each participant
        if result.get('success') and result.get('processed_items'):
            for item in result['processed_items']:
                socketio.emit('production_completed', {
                    'participant_code': item.get('participant_code'),
                    'session_code': session_code,
                    'shape': item.get('shape'),
                    'quantity': item.get('quantity', 1),
                    'timestamp': datetime.now().isoformat()
                })
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/fix-inventory', methods=['POST'])
def fix_inventory():
    """Fix duplicate inventory by removing duplicates"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        data = request.get_json()
        target_participant = data.get('participant_code', participant_code)
        
        # Get experiment type from session
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        # Get game engine
        game_engine = get_game_engine(experiment_type)
        result = game_engine.fix_duplicate_inventory(target_participant)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/send-message', methods=['POST'])
def send_message():
    """Send a message"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')
        data = request.get_json()
        recipient = data.get('recipient')
        content = data.get('content')
        
        if not recipient or not content:
            return jsonify({"error": "Recipient and content required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # Check communication level restrictions
        communication_level = get_session_config(session_code).get('communicationLevel', 'chat')
        
        if communication_level == 'no_chat':
            return jsonify({
                "success": False,
                "error": "Chat is disabled in this session"
            }), 403
        
        if communication_level == 'chat':
            # In chat mode, only allow messages to individual participants
            if recipient == "all":
                return jsonify({
                    "success": False,
                    "error": "Broadcast messaging is disabled in chat mode. Please send messages to individual participants."
                }), 403
        
        if communication_level == 'broadcast':
            # In broadcast mode, only allow messages to "all"
            if recipient != "all":
                return jsonify({
                    "success": False,
                    "error": "Direct messaging is disabled. Only broadcast messages to 'all' are allowed."
                }), 403

        
        # Get session ID for logging
        session_id = get_participant_session_id(participant_code, session_code)
        logger = get_human_logger(participant_code, session_id, session_code)
        
        # Get experiment type from session
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        # Get game engine
        game_engine = get_game_engine(experiment_type)
        result = game_engine.send_message(participant_code, recipient, content, session_code)
        
        # Log the message action
        success = result.get('success', False)
        error_message = result.get('error') if not success else None
        logger.log_message(recipient, content, success, error_message)
        
        # Emit WebSocket event to notify participants and researchers of new message
        if result.get('success'):
            message_data = {
                'sender': participant_code,
                'recipient': recipient,
                'content': content,
                'message_id': result.get('message_id'),
                'timestamp': datetime.now().isoformat()
            }
            
            # Add wordguessing guess verification result if present (only for wordguessing experiments)
            if experiment_type == 'wordguessing':
                if result.get('is_correct_guess') is not None:
                    message_data['is_correct_guess'] = result.get('is_correct_guess')
                if result.get('word_guessed'):
                    message_data['word_guessed'] = True
                    message_data['session_code'] = session_code
            
            # Send to participants room
            socketio.emit('new_message', message_data, room='participants')
            # Also send to researchers room so researcher dashboard gets updates
            socketio.emit('new_message', message_data, room='researchers')
            
            # If word was guessed correctly, emit a special event (only for wordguessing experiments)
            if experiment_type == 'wordguessing' and result.get('word_guessed'):
                socketio.emit('word_guessed', {
                    'session_code': session_code,
                    'guesser': participant_code,
                    'word': content,
                    'timestamp': datetime.now().isoformat()
                }, room='participants')
                socketio.emit('word_guessed', {
                    'session_code': session_code,
                    'guesser': participant_code,
                    'word': content,
                    'timestamp': datetime.now().isoformat()
                }, room='researchers')
            
            # For Hidden Profiles: Trigger passive agents when they receive a message
            if experiment_type == 'hiddenprofiles':
                print(f"[PASSIVE TRIGGER] Hidden Profiles message received from {participant_code} to {recipient} in session {session_code}")
                try:
                    with DatabaseConnection() as conn:
                        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                        
                        experiment_config = session_config.get('experiment_config', {})
                        hidden_profiles_config = experiment_config.get('hiddenProfiles', {})
                        participant_initiatives = hidden_profiles_config.get('participantInitiatives', {})
                        
                        # If initiatives dict is empty, try reading directly from database
                        if not participant_initiatives:
                            print(f"[PASSIVE TRIGGER] Participant initiatives empty in session_config, reading from database...")
                            cur.execute("SELECT experiment_config FROM sessions WHERE session_code = %s", (session_code,))
                            db_result = cur.fetchone()
                            if db_result and db_result.get('experiment_config'):
                                db_config = db_result['experiment_config']
                                if isinstance(db_config, str):
                                    import json
                                    db_config = json.loads(db_config)
                                db_hidden_profiles = db_config.get('hiddenProfiles', {})
                                participant_initiatives = db_hidden_profiles.get('participantInitiatives', {})
                                print(f"[PASSIVE TRIGGER] Loaded from database: {participant_initiatives}")
                        
                        print(f"[PASSIVE TRIGGER] Participant initiatives: {participant_initiatives}")
                        
                        # Get all passive agents in the session
                        cur.execute("""
                            SELECT participant_code, is_agent
                            FROM participants 
                            WHERE session_code = %s AND is_agent = true
                        """, (session_code,))
                        
                        all_agents = cur.fetchall()
                        print(f"[PASSIVE TRIGGER] Found {len(all_agents)} agent(s) in session {session_code}: {[a['participant_code'] for a in all_agents]}")
                        
                        # Check if agents are started - if not, start them now
                        agents_to_start = []
                        for agent in all_agents:
                            agent_code = agent['participant_code']
                            agent_key = f"{session_code}:{agent_code}" if session_code else agent_code
                            if agent_key not in AGENT_THREADS or not AGENT_THREADS[agent_key].get('thread') or not AGENT_THREADS[agent_key]['thread'].is_alive():
                                agents_to_start.append(agent_code)
                        
                        if agents_to_start:
                            print(f"[PASSIVE TRIGGER] Agents not started yet: {agents_to_start}. Starting them now...")
                            # Start agents that aren't running
                            for agent_code in agents_to_start:
                                try:
                                    if _start_agent_thread(agent_code, None, use_llm=True, llm_model='gpt-4o-mini',
                                                          use_memory=True, max_memory_length=20,
                                                          session_code=session_code, experiment_type=experiment_type):
                                        print(f"[PASSIVE TRIGGER] ✅ Started agent {agent_code}")
                                    else:
                                        print(f"[PASSIVE TRIGGER] ⚠️ Failed to start agent {agent_code} (may already be starting)")
                                except Exception as e:
                                    print(f"[PASSIVE TRIGGER] ❌ Error starting agent {agent_code}: {e}")
                        
                        print(f"[PASSIVE TRIGGER] Available agent keys after starting: {list(AGENT_THREADS.keys())}")
                        
                        # For group_chat/broadcast: Trigger all passive agents when ANY message is sent
                        # For direct messages: Trigger the recipient if they're a passive agent
                        communication_level = session_config.get('communicationLevel', 'chat')
                        print(f"[PASSIVE TRIGGER] Communication level: {communication_level}, recipient: {recipient}")
                        
                        if recipient == "all":
                            # Broadcast message - trigger all passive agents
                            print(f"[PASSIVE TRIGGER] Broadcast message detected - triggering all passive agents")
                            for agent in all_agents:
                                agent_code = agent['participant_code']
                                agent_key = f"{session_code}:{agent_code}" if session_code else agent_code
                                agent_info = AGENT_THREADS.get(agent_key)
                                
                                # Use database/config as source of truth for initiative
                                initiative = participant_initiatives.get(agent_code)
                                if not initiative:
                                    base_code = agent_code.rsplit('_', 1)[0] if '_' in agent_code else agent_code
                                    initiative = participant_initiatives.get(base_code)
                                
                                # Default to 'active' if not found
                                if not initiative:
                                    initiative = 'active'
                                
                                is_passive = (initiative == 'passive')
                                
                                # Update controller's is_passive to match database/config
                                if agent_info and agent_info.get('controller'):
                                    old_is_passive = getattr(agent_info['controller'], 'is_passive', False)
                                    agent_info['controller'].is_passive = is_passive
                                    if old_is_passive != is_passive:
                                        print(f"[PASSIVE TRIGGER] Updated controller.is_passive from {old_is_passive} to {is_passive} for {agent_code}")
                                
                                print(f"[PASSIVE TRIGGER] Agent {agent_code}: initiative={initiative}, is_passive={is_passive}")
                                if is_passive:
                                    print(f"[PASSIVE TRIGGER] Triggering passive agent {agent_code} due to broadcast message from {participant_code}")
                                    triggered = _trigger_passive_agent(agent_code, session_code)
                                    if not triggered:
                                        print(f"[PASSIVE TRIGGER WARNING] Failed to trigger passive agent {agent_code}")
                                    else:
                                        print(f"[PASSIVE TRIGGER] Successfully triggered passive agent {agent_code}")
                        else:
                            # Direct message - check if recipient is a passive agent
                            # Also trigger all passive agents in group_chat mode (they should see all messages)
                            print(f"[PASSIVE TRIGGER] Direct message detected - checking communication level: {communication_level}")
                            
                            if communication_level == 'group_chat':
                                # In group_chat, all agents should see all messages, so trigger all passive agents
                                for agent in all_agents:
                                    agent_code = agent['participant_code']
                                    # Skip the sender
                                    if agent_code == participant_code:
                                        continue
                                    
                                    agent_key = f"{session_code}:{agent_code}" if session_code else agent_code
                                    agent_info = AGENT_THREADS.get(agent_key)
                                    
                                    # Use database/config as source of truth for initiative
                                    initiative = participant_initiatives.get(agent_code)
                                    if not initiative:
                                        base_code = agent_code.rsplit('_', 1)[0] if '_' in agent_code else agent_code
                                        initiative = participant_initiatives.get(base_code)
                                    
                                    # Default to 'active' if not found
                                    if not initiative:
                                        initiative = 'active'
                                    
                                    is_passive = (initiative == 'passive')
                                    
                                    # Update controller's is_passive to match database/config
                                    if agent_info and agent_info.get('controller'):
                                        old_is_passive = getattr(agent_info['controller'], 'is_passive', False)
                                        agent_info['controller'].is_passive = is_passive
                                        if old_is_passive != is_passive:
                                            print(f"[PASSIVE TRIGGER] Updated controller.is_passive from {old_is_passive} to {is_passive} for {agent_code}")
                                    
                                    if is_passive:
                                        print(f"[PASSIVE TRIGGER] Triggering passive agent {agent_code} due to group_chat message from {participant_code}")
                                        triggered = _trigger_passive_agent(agent_code, session_code)
                                        if not triggered:
                                            print(f"[PASSIVE TRIGGER WARNING] Failed to trigger passive agent {agent_code}")
                            else:
                                # In chat mode, only trigger the specific recipient if they're a passive agent
                                cur.execute("""
                                    SELECT participant_code, participant_type, is_agent
                                    FROM participants 
                                    WHERE (participant_code = %s OR participant_code = %s)
                                    AND session_code = %s
                                """, (recipient, f"{recipient}_{session_code}", session_code))
                                
                                recipient_participant = cur.fetchone()
                                
                                if recipient_participant and recipient_participant.get('is_agent'):
                                    # Check if this agent is passive
                                    agent_code = recipient_participant['participant_code']
                                    agent_key = f"{session_code}:{agent_code}" if session_code else agent_code
                                    agent_info = AGENT_THREADS.get(agent_key)
                                    
                                    # Use database/config as source of truth for initiative
                                    initiative = participant_initiatives.get(agent_code) or participant_initiatives.get(recipient)
                                    if not initiative:
                                        base_code = agent_code.rsplit('_', 1)[0] if '_' in agent_code else agent_code
                                        initiative = participant_initiatives.get(base_code)
                                    
                                    # Default to 'active' if not found
                                    if not initiative:
                                        initiative = 'active'
                                    
                                    is_passive = (initiative == 'passive')
                                    
                                    # Update controller's is_passive to match database/config
                                    if agent_info and agent_info.get('controller'):
                                        old_is_passive = getattr(agent_info['controller'], 'is_passive', False)
                                        agent_info['controller'].is_passive = is_passive
                                        if old_is_passive != is_passive:
                                            print(f"[PASSIVE TRIGGER] Updated controller.is_passive from {old_is_passive} to {is_passive} for {agent_code}")
                                    
                                    if is_passive:
                                        print(f"[PASSIVE TRIGGER] Triggering passive agent {agent_code} due to direct message from {participant_code}")
                                        triggered = _trigger_passive_agent(agent_code, session_code)
                                        if not triggered:
                                            print(f"[PASSIVE TRIGGER WARNING] Failed to trigger passive agent {agent_code}")
                                            
                                            # Also try with session suffix if different
                                            if agent_code != f"{recipient}_{session_code}":
                                                triggered = _trigger_passive_agent(f"{recipient}_{session_code}", session_code)
                                                if triggered:
                                                    print(f"[PASSIVE TRIGGER] Successfully triggered with session suffix: {recipient}_{session_code}")
                        
                        cur.close()
                except Exception as e:
                    print(f"[PASSIVE TRIGGER ERROR] Error triggering passive agent: {e}")
                    import traceback
                    print(traceback.format_exc())
                    # Don't fail the message send if triggering fails
        
        return jsonify(result)
        
    except Exception as e:
        # Log the error if we have a logger
        try:
            participant_code = verify_participant_token(request).get('participant_code') if verify_participant_token(request) else None
            session_code = verify_participant_token(request).get('session_code') if verify_participant_token(request) else None
            if participant_code:
                session_id = get_participant_session_id(participant_code, session_code)
                logger = get_human_logger(participant_code, session_id, session_code)
                logger.log_message("unknown", "unknown", False, str(e))
        except:
            pass
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-trade-offer', methods=['POST'])
def create_trade_offer():
    """Create a trade offer"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')
        data = request.get_json()
        
        # Get session ID for logging
        session_id = get_participant_session_id(participant_code, session_code)
        logger = get_human_logger(participant_code, session_id, session_code)
        
        # Get game engine
        game_engine = get_game_engine()
        result = game_engine.create_trade_offer(
            participant_code,
            data.get('recipient'),
            data.get('offer_type'),
            data.get('shape'),
            data.get('quantity'),
            data.get('price_per_unit'),
            session_code
        )
        
        # Log the trade offer action
        success = result.get('success', False)
        error_message = result.get('error') if not success else None
        logger.log_trade_offer(
            data.get('recipient'),
            data.get('offer_type'),
            data.get('shape'),
            data.get('quantity', 1),
            data.get('price_per_unit'),
            success,
            error_message
        )
        
        # Emit WebSocket event to notify participants of new trade offer
        if result.get('success'):
            socketio.emit('new_trade_offer', {
                'sender': participant_code,
                'target': data.get('recipient'),
                'offer_type': data.get('offer_type'),
                'shape': data.get('shape'),
                'quantity': data.get('quantity'),
                'price_per_unit': data.get('price_per_unit'),
                'transaction_id': result.get('transaction_id'),
                'timestamp': datetime.now().isoformat()
            }, room=f'session_{session_code}')
        
        return jsonify(result)
        
    except Exception as e:
        # Log the error if we have a logger
        try:
            participant_code = verify_participant_token(request).get('participant_code') if verify_participant_token(request) else None
            session_code = verify_participant_token(request).get('session_code') if verify_participant_token(request) else None
            if participant_code:
                session_id = get_participant_session_id(participant_code, session_code)
                logger = get_human_logger(participant_code, session_id, session_code)
                logger.log_trade_offer("unknown", "unknown", "unknown", 1, 0.0, False, str(e))
        except:
            pass
        return jsonify({"error": str(e)}), 500

@app.route('/api/respond-trade-offer', methods=['POST'])
def respond_trade_offer():
    """Respond to a trade offer"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')  # CRITICAL FIX: Use session_code from JWT token
        data = request.get_json()
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # CRITICAL FIX: No need to query for session_code - use it from JWT token
        # This prevents cross-session data leakage
        
        # Get session ID for logging
        session_id = get_participant_session_id(participant_code)
        logger = get_human_logger(participant_code, session_id, session_code)
        
        # Get game engine
        game_engine = get_game_engine()
        result = game_engine.respond_to_trade_offer(
            participant_code,
            data.get('transaction_id'),
            data.get('response'),
            session_code
        )
        
        # Log the trade response action
        success = result.get('success', False)
        error_message = result.get('error') if not success else None
        logger.log_trade_response(
            data.get('transaction_id'),
            data.get('response'),
            success,
            error_message
        )
        
        # Emit WebSocket event to notify participants of trade offer response
        if result.get('success'):
            socketio.emit('trade_offer_response', {
                'responder': participant_code,
                'transaction_id': data.get('transaction_id'),
                'response': data.get('response'),
                'timestamp': datetime.now().isoformat()
            }, room=f'session_{session_code}')
            
            # If trade was accepted, also emit trade completion event
            if data.get('response') == 'accept':
                # Get transaction details to include seller and buyer info
                conn = get_db_connection()
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT 
                        t.proposer_id, t.recipient_id, t.offer_type,
                        proposer.participant_code as seller,
                        recipient.participant_code as buyer
                    FROM transactions t
                    LEFT JOIN participants proposer ON t.proposer_id = proposer.participant_id
                    LEFT JOIN participants recipient ON t.recipient_id = recipient.participant_id
                    WHERE t.transaction_id = %s
                """, (data.get('transaction_id'),))
                transaction_info = cur.fetchone()
                cur.close()
                return_db_connection(conn)
                
                if transaction_info:
                    # Determine seller and buyer based on offer type
                    if transaction_info['offer_type'] == 'sell':
                        seller = transaction_info['seller']
                        buyer = transaction_info['buyer']
                    else:  # buy offer
                        seller = transaction_info['buyer']
                        buyer = transaction_info['seller']
                    
                    socketio.emit('trade_completed', {
                        'transaction_id': data.get('transaction_id'),
                        'accepted_by': participant_code,
                        'seller': seller,
                        'buyer': buyer,
                        'timestamp': datetime.now().isoformat()
                    }, room=f'session_{session_code}')
                    
                    # Emit money update for both participants
                    socketio.emit('money_updated', {
                        'participant_code': seller,
                        'session_code': session_code,
                        'timestamp': datetime.now().isoformat()
                    }, room=f'session_{session_code}')
                    socketio.emit('money_updated', {
                        'participant_code': buyer,
                        'session_code': session_code,
                        'timestamp': datetime.now().isoformat()
                    }, room=f'session_{session_code}')
                else:
                    # Fallback if transaction info not found
                    socketio.emit('trade_completed', {
                        'transaction_id': data.get('transaction_id'),
                        'accepted_by': participant_code,
                        'timestamp': datetime.now().isoformat()
                    }, room=f'session_{session_code}')
                    
                    # Emit general money update for the accepting participant
                    socketio.emit('money_updated', {
                        'participant_code': participant_code,
                        'session_code': session_code,
                        'timestamp': datetime.now().isoformat()
                    }, room=f'session_{session_code}')
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/fulfill-orders', methods=['POST'])
def fulfill_orders():
    """Fulfill orders"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')  # CRITICAL FIX: Use session_code from JWT token
        data = request.get_json()
        order_indices = data.get('order_indices', [])
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # CRITICAL FIX: No need to query for session_code - use it from JWT token
        # This prevents cross-session data leakage
        
        # Get session ID for logging
        session_id = get_participant_session_id(participant_code)
        logger = get_human_logger(participant_code, session_id, session_code)
        
        # Get game engine
        game_engine = get_game_engine()
        result = game_engine.fulfill_orders(participant_code, order_indices, session_code)
        
        # Log the order fulfillment action
        success = result.get('success', False)
        orders_fulfilled = result.get('orders_fulfilled', 0)
        score_gained = result.get('score_gained', 0)
        error_message = result.get('error') if not success else None
        logger.log_order_fulfillment(order_indices, orders_fulfilled, score_gained, success, error_message)
        
        # Emit participant status update if orders were fulfilled successfully
        if result.get('success') and result.get('orders_fulfilled', 0) > 0:
            socketio.emit('participant_status_update', {
                'participant_code': participant_code,
                'session_code': session_code,
                'orders_fulfilled': result.get('orders_fulfilled', 0),
                'score_gained': result.get('score_gained', 0),
                'timestamp': datetime.now().isoformat()
            }, room=f'session_{session_code}')
            
            # Also emit an orders fulfilled event to trigger inventory updates
            socketio.emit('orders_fulfilled', {
                'participant_code': participant_code,
                'session_code': session_code,
                'orders_fulfilled': result.get('orders_fulfilled', 0),
                'score_gained': result.get('score_gained', 0),
                'new_money': result.get('new_money'),
                'new_orders_completed': result.get('new_orders_completed'),
                'new_orders': result.get('new_orders', []),  # Include updated orders array
                'new_inventory': result.get('new_inventory', []),  # Include updated inventory array
                'timestamp': datetime.now().isoformat()
            }, room=f'session_{session_code}')
        
        return jsonify(result)
        
    except Exception as e:
        # Log the error if we have a logger
        try:
            participant_code = verify_participant_token(request).get('participant_code') if verify_participant_token(request) else None
            session_code = verify_participant_token(request).get('session_code') if verify_participant_token(request) else None
            if participant_code:
                session_id = get_participant_session_id(participant_code, session_code)
                logger = get_human_logger(participant_code, session_id, session_code)
                logger.log_order_fulfillment([], 0, 0, False, str(e))
        except:
            pass
        return jsonify({"error": str(e)}), 500

# ============================================================================
# MCP AGENT MANAGEMENT
# ============================================================================

@app.route('/api/agents/register', methods=['POST'])
def register_agent():
    """Register a new MCP agent"""
    try:
        data = request.get_json()
        
        agent_type = 'basic_agent'  # Always use basic agent type
        session_code = data.get('session_code')
        participant_code = data.get('participant_code')  # Use the provided participant_code
        specialty_override = data.get('specialty_shape')  # Optional
        tag = data.get('tag')  # Optional tag
        wordguessing_role = data.get('wordguessingRole')  # Optional wordguessing role

        
        if not participant_code:
            return jsonify({"error": "Participant code required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # Create session-isolated agent name: original_name + session_code
        isolated_participant_code = f"{participant_code}_{session_code}"
        
        # Get session ID
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if participant already exists (using isolated name)
        cur.execute("""
            SELECT participant_id FROM participants 
            WHERE participant_code = %s AND session_code = %s
        """, (isolated_participant_code, session_code))
        
        if cur.fetchone():
            cur.close()
            return_db_connection(conn)
            return jsonify({"error": "Agent already exists in this session"}), 400
        
        cur.execute("SELECT session_id FROM sessions WHERE session_code = %s", (session_code,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            return_db_connection(conn)
            return jsonify({"error": "Session not found"}), 404
        
        session_id = session_result['session_id']
        
        # Get session config to check experiment type
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        is_shape_factory = experiment_type == 'shapefactory' or (
            experiment_type.startswith('custom_') and 
            session_config.get('specialtyCost') is not None
        )
        is_wordguessing = experiment_type == 'wordguessing'
        
        # Determine specialty and orders based on experiment type
        specialty_shape = None
        orders_json = None
        assigned_role = None
        
        if is_shape_factory:
            # Only call shape-related functions for ShapeFactory experiments
            specialty_shape = specialty_override or get_unique_specialty_for_session(session_code, cur)
            if specialty_shape:
                orders_json = generate_deterministic_orders(specialty_shape, session_code)
        elif is_wordguessing:
            # For wordguessing experiments, use wordguessing-specific defaults
            specialty_shape = "N/A"  # Required field but not used
            orders_json = None
            assigned_role = wordguessing_role if wordguessing_role else None
        else:
            # For non-ShapeFactory experiments (DayTrader, etc.), use simple defaults
            specialty_shape = "default"
            orders_json = None
        
        # Insert agent into database with isolated name
        if is_shape_factory:
            color_shape_combination = f"{participant_code} {specialty_shape.title()}" if specialty_shape else participant_code
            cur.execute("""
                INSERT INTO participants 
                (participant_id, session_id, participant_code, participant_type, 
                 color_shape_combination, specialty_shape, login_status, money, 
                 is_agent, agent_type, agent_status, last_activity, session_code, tag, orders)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), session_id, isolated_participant_code, 'ai_agent',
                color_shape_combination, specialty_shape, 'not_logged_in', get_session_config(session_code).get('startingMoney', 300),
                True, 'basic_agent', 'created', datetime.now(timezone.utc), session_code, tag, orders_json
            ))
        elif is_wordguessing:
            # For wordguessing experiments, use wordguessing-specific fields
            cur.execute("""
                INSERT INTO participants 
                (participant_id, session_id, participant_code, participant_type, 
                 color_shape_combination, specialty_shape, login_status, money, 
                 is_agent, agent_type, agent_status, last_activity, session_code, tag, orders,
                 role, current_round, score, assigned_words)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), session_id, isolated_participant_code, 'ai_agent',
                participant_code, specialty_shape, 'not_logged_in', 0,  # No money for wordguessing
                True, 'basic_agent', 'created', datetime.now(timezone.utc), session_code, tag, None,
                assigned_role, 1, 0, '[]'  # role, round 1, score 0, empty words
            ))
        else:
            # For other experiments, use minimal fields
            cur.execute("""
                INSERT INTO participants 
                (participant_id, session_id, participant_code, participant_type, 
                 color_shape_combination, specialty_shape, login_status, money, 
                 is_agent, agent_type, agent_status, last_activity, session_code, tag, orders)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), session_id, isolated_participant_code, 'ai_agent',
                participant_code, 'default', 'not_logged_in', get_session_config(session_code).get('startingMoney', 300),
                True, 'basic_agent', 'created', datetime.now(timezone.utc), session_code, tag, None
            ))
        
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        # For Hidden Profiles: Automatically start PASSIVE agents after registration
        # (Active agents will be started when experiment begins)
        if experiment_type == 'hiddenprofiles':
            print(f"[AGENT REGISTRATION] Hidden Profiles agent registered. Checking if agent {isolated_participant_code} should be started...")
            try:
                # Get initiative to determine if agent should be passive
                session_config = get_session_config(session_code)
                experiment_config = session_config.get('experiment_config', {})
                hidden_profiles_config = experiment_config.get('hiddenProfiles', {})
                participant_initiatives = hidden_profiles_config.get('participantInitiatives', {})
                initiative = participant_initiatives.get(isolated_participant_code) or participant_initiatives.get(participant_code, 'active')
                
                # Only start passive agents during registration
                # Active agents will be started when the experiment begins
                if initiative == 'passive':
                    print(f"[AGENT REGISTRATION] Agent {isolated_participant_code} is passive - starting now...")
                    if _start_agent_thread(isolated_participant_code, None, use_llm=True, llm_model='gpt-4o-mini',
                                          use_memory=True, max_memory_length=20,
                                          session_code=session_code, experiment_type=experiment_type):
                        print(f"[AGENT REGISTRATION] ✅ Passive agent {isolated_participant_code} started successfully")
                    else:
                        print(f"[AGENT REGISTRATION] ⚠️ Passive agent {isolated_participant_code} may already be running")
                else:
                    print(f"[AGENT REGISTRATION] Agent {isolated_participant_code} is active (initiative={initiative}) - will be started when experiment begins")
            except Exception as e:
                print(f"[AGENT REGISTRATION] ❌ Error checking/starting agent {isolated_participant_code}: {e}")
                import traceback
                print(traceback.format_exc())
        
        response_data = {
            "success": True,
            "message": "Agent registered successfully",
            "agent_code": participant_code,  # Return the original name for display
            "isolated_agent_code": isolated_participant_code,  # Return the isolated name for internal use
            "agent_type": "basic_agent",
            "specialty_shape": specialty_shape,
            "session_code": session_code,
            "tag": tag
        }
        
        # Add wordguessing-specific fields to response
        if is_wordguessing:
            response_data["role"] = assigned_role
            
        return jsonify(response_data)
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"[ERROR] Agent registration failed: {str(e)}")
        print(f"[ERROR] Traceback: {error_traceback}")
        return jsonify({"error": str(e), "traceback": error_traceback}), 500

@app.route('/api/agents/setup', methods=['POST'])
def setup_agents():
    """Setup agents for a session (no-op for serverless runner)."""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        agent_types = data.get('agent_types', ['basic_agent'])
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        status = get_agents_status(session_code)
        return jsonify({"success": True, "status": status, "note": "Setup is implicit for serverless agents."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/agents/activate', methods=['POST'])
def activate_agents():
    """Activate agents for a session (serverless runner)"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        use_llm = data.get('use_llm', True) # Default to True
        llm_model = data.get('llm_model', 'gpt-4o-mini') # Default to 'gpt-4o-mini'
        use_memory = data.get('use_memory', True) # Default to True
        max_memory_length = data.get('max_memory_length', 20) # Default to 20
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # Check if experiment is running
        session_timer_state = get_timer_state(session_code)
        if session_timer_state['experiment_status'] != 'running':
            return jsonify({
                "success": False,
                "error": f"Cannot activate agents when experiment status is '{session_timer_state['experiment_status']}'. Start the experiment first."
            }), 400
        
        result = activate_agents_for_session(session_code, use_llm=use_llm, llm_model=llm_model, 
                                           use_memory=use_memory, max_memory_length=max_memory_length)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/agents/deactivate', methods=['POST'])
def deactivate_agents():
    """Deactivate agents for a session (serverless runner)"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        result = deactivate_agents_for_session(session_code)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/agents/status/<session_code>')
def get_agent_status(session_code):
    """Get agent status for a session"""
    try:
        result = get_agents_status(session_code)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/agents/config-check', methods=['GET'])
def agents_config_check():
    """Check current agent configuration and running status"""
    try:
        session_code = request.args.get('session_code')
        if not session_code:
            return jsonify({'error': 'session_code parameter required'}), 400
        
        # Get current config
        config = get_session_config(session_code)
        
        # Get agent status
        agent_status = get_agents_status(session_code)
        
        return jsonify({
            'success': True,
            'session_code': session_code,
            'config': config,
            'agent_status': agent_status,
            'global_config': experiment_config_state
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/agents/regenerate-orders', methods=['POST'])
def regenerate_agent_orders():
    """Regenerate orders for existing agents to fix duplication issues"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get all agents in the session
        cur.execute("""
            SELECT participant_code, specialty_shape, orders
            FROM participants 
            WHERE session_code = %s AND is_agent = true
        """, (session_code,))
        
        agents = cur.fetchall()
        
        if not agents:
            cur.close()
            return_db_connection(conn)
            return jsonify({"error": "No agents found in session"}), 404
        
        updated_count = 0
        for agent in agents:
            # Check if the agent has duplicate orders
            orders = []
            if agent['orders']:
                try:
                    if isinstance(agent['orders'], str):
                        orders = json.loads(agent['orders'])
                    elif isinstance(agent['orders'], list):
                        orders = list(agent['orders'])
                    else:
                        orders = list(agent['orders'])
                except (json.JSONDecodeError, TypeError):
                    orders = []
            
            # Check for duplicates
            if len(orders) != len(set(orders)):
                # Regenerate orders for this agent
                new_orders_json = generate_deterministic_orders(agent['specialty_shape'], session_code)
                
                cur.execute("""
                    UPDATE participants 
                    SET orders = %s
                    WHERE participant_code = %s AND session_code = %s
                """, (new_orders_json, agent['participant_code'], session_code))
                
                updated_count += 1
        
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        return jsonify({
            "success": True,
            "message": f"Regenerated orders for {updated_count} agents",
            "agents_updated": updated_count,
            "total_agents": len(agents)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_game_engine(experiment_type: str = "shapefactory"):
    """Get game engine instance for the specified experiment type"""
    database_url = f"postgresql://{os.getenv('DATABASE_USER', '')}:{os.getenv('DATABASE_PASSWORD', '')}@{os.getenv('DATABASE_HOST', 'localhost')}:{os.getenv('DATABASE_PORT', '5432')}/{os.getenv('DATABASE_NAME', 'shape_factory_research')}"
    engine = GameEngineFactory.create_game_engine(experiment_type, database_url)
    # Pass timer state to the game engine
    engine._timer_state = get_timer_state()
    return engine

@app.route('/api/test-connection')
def test_connection():
    """Test database connection and basic functionality"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Test basic query
        cur.execute("SELECT COUNT(*) FROM sessions")
        session_count = cur.fetchone()[0]
        
        # Test participants table
        cur.execute("SELECT COUNT(*) FROM participants")
        participant_count = cur.fetchone()[0]
        
        # Test if session_code column exists
        try:
            cur.execute("SELECT session_code FROM participants LIMIT 1")
            session_code_exists = True
        except Exception:
            session_code_exists = False
        
        # Test if is_agent column exists
        try:
            cur.execute("SELECT is_agent FROM participants LIMIT 1")
            is_agent_exists = True
        except Exception:
            is_agent_exists = False
        
        cur.close()
        return_db_connection(conn)
        
        return jsonify({
            "success": True,
            "database_connected": True,
            "session_count": session_count,
            "participant_count": participant_count,
            "session_code_column_exists": session_code_exists,
            "is_agent_column_exists": is_agent_exists,
            "experiment_config": experiment_config_state
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "database_connected": False
        }), 500

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def get_available_shapes_for_session(session_code: str) -> list:
    """Get available shapes for a session based on numShapeTypes configuration"""
    try:
        # Get session config to determine number of shape types
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        # For non-ShapeFactory experiments, return a default shape list
        if experiment_type != 'shapefactory':
            return ['circle', 'square', 'triangle', 'diamond', 'pentagon']
        
        num_shape_types = session_config.get('numShapeTypes', 5)
        
        # All possible shapes
        all_shapes = ['circle', 'square', 'triangle', 'diamond', 'pentagon']
        
        # Return only the first num_shape_types shapes
        return all_shapes[:num_shape_types]
        
    except Exception as e:
        print(f"Error getting available shapes for session {session_code}: {e}")
        # Fallback to default shapes if there's an error
        return ['circle', 'square', 'triangle', 'diamond', 'pentagon']

def get_current_specialties_in_session(session_code: str) -> list:
    """Get all current specialties in a session"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DISTINCT specialty_shape 
            FROM participants 
            WHERE session_code = %s AND specialty_shape IS NOT NULL
        """, (session_code,))
        
        specialties = [row[0] for row in cur.fetchall()]
        cur.close()
        return_db_connection(conn)
        
        return specialties
        
    except Exception as e:
        print(f"Error getting specialties for session {session_code}: {e}")
        # Fallback to default shapes if database query fails
        return ['circle', 'square', 'triangle', 'diamond', 'pentagon']

def generate_deterministic_orders(specialty_shape: str, session_code: str) -> str:
    """Generate deterministic orders for a participant based on their specialty shape using the new algorithm:
    1. Generate potential order lists with different combinations of shapes
    2. Randomly pick one potential order list for the participant
    """
    import hashlib
    import random
    import json
    from itertools import combinations_with_replacement
    
    # Get session config to determine number of orders
    session_config = get_session_config(session_code)
    total_orders = session_config.get('shapesPerOrder', 3)  # This is actually the number of orders
    num_shape_types = session_config.get('numShapeTypes', 5)
    
    print(f"🔍 Generating orders for {specialty_shape} in session {session_code}")
    print(f"   total_orders: {total_orders}, numShapeTypes: {num_shape_types}")
    
    # Get available shapes for this session (respecting user-defined numShapeTypes)
    available_shapes = get_available_shapes_for_session(session_code)
    print(f"   Available shapes: {available_shapes}")
    
    # Get current specialties in the session (only those that are in available shapes)
    current_specialties = get_current_specialties_in_session(session_code)
    valid_specialties = [s for s in current_specialties if s in available_shapes]
    print(f"   Valid specialties: {valid_specialties}")
    
    # Algorithm: Remove own_specialty from specialty_shapes
    specialty_shapes = [s for s in valid_specialties if s != specialty_shape]
    print(f"   Specialty shapes (excluding {specialty_shape}): {specialty_shapes}")
    
    # If no valid shapes available (edge case), fall back to available shapes excluding own specialty
    if not specialty_shapes:
        print(f"Warning: No valid shapes available for orders for {specialty_shape} in session {session_code}, using fallback")
        specialty_shapes = [s for s in available_shapes if s != specialty_shape]
        print(f"   Fallback specialty shapes: {specialty_shapes}")
    
    # Ensure we have at least one shape in the pool
    if not specialty_shapes:
        print(f"Error: No shapes available for orders for {specialty_shape} in session {session_code}")
        return json.dumps([])
    
    # NEW ALGORITHM: Generate potential order lists
    print(f"   🎲 Generating potential order lists for {total_orders} orders using {len(specialty_shapes)} shapes")
    
    # Step 1: Generate all possible combinations that sum to total_orders
    potential_order_lists = []
    
    if len(specialty_shapes) == 1:
        # If only one shape available, all orders must be that shape
        potential_order_lists = [[specialty_shapes[0]] * total_orders]
    elif len(specialty_shapes) == 2:
        # For two shapes, generate combinations like [4,0], [3,1], [2,2], [1,3], [0,4]
        shape1, shape2 = specialty_shapes[0], specialty_shapes[1]
        for i in range(total_orders + 1):
            count1 = i
            count2 = total_orders - i
            order_list = [shape1] * count1 + [shape2] * count2
            potential_order_lists.append(order_list)
    else:
        # For more than 2 shapes, use combinations_with_replacement
        # This generates all possible combinations of shapes that sum to total_orders
        for combo in combinations_with_replacement(specialty_shapes, total_orders):
            potential_order_lists.append(list(combo))
    
    print(f"   📋 Generated {len(potential_order_lists)} potential order lists")
    
    # Step 2: Randomly pick one potential order list
    # Create a more varied seed by including session_code to ensure different orders per session
    seed_string = f"{specialty_shape}_{session_code}"
    seed_value = int(hashlib.md5(seed_string.encode()).hexdigest(), 16) % (2**32)
    random.seed(seed_value)
    
    # Pick a random order list
    selected_orders = random.choice(potential_order_lists)
    
    print(f"   🎯 Selected order list: {selected_orders}")
    
    # Validate that all orders are within the user-defined shape types
    invalid_shapes = [shape for shape in selected_orders if shape not in available_shapes]
    if invalid_shapes:
        print(f"   ❌ Error: Invalid shapes in orders: {invalid_shapes}")
        # Filter out invalid shapes
        selected_orders = [shape for shape in selected_orders if shape in available_shapes]
        print(f"   ✅ Filtered orders: {selected_orders}")
    
    # Reset random seed to avoid affecting other parts of the application
    random.seed()
    
    print(f"   ✅ Final orders: {selected_orders}")
    return json.dumps(selected_orders)

@app.route('/api/debug-transaction-status')
def debug_transaction_status():
    """Debug endpoint to check transaction status"""
    try:
        transaction_id = request.args.get('transaction_id')
        if not transaction_id:
            return jsonify({"error": "transaction_id parameter required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT transaction_id, transaction_status, proposer_id, recipient_id, 
                   agreed_price, proposed_timestamp, agreed_timestamp, completed_timestamp
            FROM transactions 
            WHERE transaction_id = %s
        """, (transaction_id,))
        
        transaction = cur.fetchone()
        cur.close()
        return_db_connection(conn)
        
        if transaction:
            return jsonify({
                "transaction_id": transaction['transaction_id'],
                "transaction_status": transaction['transaction_status'],
                "proposer_id": transaction['proposer_id'],
                "recipient_id": transaction['recipient_id'],
                "agreed_price": float(transaction['agreed_price']) if transaction['agreed_price'] else None,
                "proposed_timestamp": transaction['proposed_timestamp'].isoformat() if transaction['proposed_timestamp'] else None,
                "agreed_timestamp": transaction['agreed_timestamp'].isoformat() if transaction['agreed_timestamp'] else None,
                "completed_timestamp": transaction['completed_timestamp'].isoformat() if transaction['completed_timestamp'] else None
            })
        else:
            return jsonify({"error": "Transaction not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/export/session-logs', methods=['POST'])
def export_session_logs():
    """Export all logs for a session including JSON summary and raw log files"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        import zipfile
        import io
        import os
        from datetime import datetime
        
        # Create a memory buffer for the zip file
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Create JSON summary
            print(f"📊 Creating session summary for: {session_code}")
            summary_data = create_session_summary(session_code)
            
            if 'error' in summary_data:
                print(f"❌ Error creating summary: {summary_data['error']}")
                return jsonify({"error": summary_data['error']}), 400
            
            print(f"✅ Summary created with {len(summary_data.get('participants', []))} participants, {len(summary_data.get('trades', []))} trades, {len(summary_data.get('messages', []))} messages")
            
            summary_json = json.dumps(summary_data, indent=2, default=str)
            zip_file.writestr('session_summary.json', summary_json)
            
            # 2. Get session_id to find the correct logs directory
            session_id = None
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT session_id FROM sessions WHERE session_code = %s", (session_code,))
                result = cur.fetchone()
                if result:
                    session_id = result['session_id']
                    print(f"🔍 Found session_id: {session_id} for session_code: {session_code}")
                else:
                    print(f"⚠️ No session found for session_code: {session_code}")
                cur.close()
                return_db_connection(conn)
            except Exception as e:
                print(f"❌ Error getting session_id for {session_code}: {e}")
            
            # 3. Add raw log files
            logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
            print(f"📁 Looking for logs in: {logs_dir}")
            
            # Try to find logs by session_id first (UUID format)
            if session_id:
                session_logs_dir = os.path.join(logs_dir, str(session_id))
                if os.path.exists(session_logs_dir):
                    print(f"✅ Found logs directory by session_id: {session_logs_dir}")
                    # Add all files from session logs directory
                    for root, dirs, files in os.walk(session_logs_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            # Create relative path within zip
                            relative_path = os.path.relpath(file_path, logs_dir)
                            zip_file.write(file_path, f'logs/{relative_path}')
                            print(f"📄 Added log file: {relative_path}")
                else:
                    print(f"⚠️ No logs directory found for session_id: {session_id}")
            else:
                print("⚠️ No session_id available, skipping session_id log search")
            
            # 4. Also try session_code directory (for backward compatibility)
            session_code_logs_dir = os.path.join(logs_dir, session_code)
            if os.path.exists(session_code_logs_dir):
                print(f"✅ Found logs directory by session_code: {session_code_logs_dir}")
                # Add all files from session logs directory
                for root, dirs, files in os.walk(session_code_logs_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Create relative path within zip
                        relative_path = os.path.relpath(file_path, logs_dir)
                        zip_file.write(file_path, f'logs/{relative_path}')
                        print(f"📄 Added log file: {relative_path}")
            else:
                print(f"⚠️ No logs directory found for session_code: {session_code}")
            
            # 5. Add any top-level logs that might be related to this session
            # (for backward compatibility with logs not in session folders)
            if os.path.exists(logs_dir):
                for file in os.listdir(logs_dir):
                    file_path = os.path.join(logs_dir, file)
                    if os.path.isfile(file_path) and file.endswith('.log'):
                        # Check if this log file might be related to the session
                        # by looking for participant codes from this session
                        try:
                            with open(file_path, 'r') as f:
                                content = f.read()
                                # If file contains any participant from this session, include it
                                participant_codes = [p.get('participant_code', p.get('id', '')) for p in summary_data.get('participants', [])]
                                if any(participant in content for participant in participant_codes if participant):
                                    zip_file.write(file_path, f'logs/{file}')
                        except:
                            pass  # Skip files that can't be read
        
        # Prepare response
        zip_buffer.seek(0)
        zip_size = len(zip_buffer.getvalue())
        print(f"📦 Created zip file with size: {zip_size} bytes")
        
        if zip_size == 0:
            print("⚠️ Warning: Zip file is empty!")
        
        response = app.response_class(
            zip_buffer.getvalue(),
            mimetype='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename=shape_factory_session_{session_code}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
            }
        )
        
        print(f"✅ Export completed successfully for session: {session_code}")
        return response
        
    except Exception as e:
        print(f"Error exporting session logs: {e}")
        return jsonify({"error": str(e)}), 500

def create_session_summary(session_code):
    """Create a comprehensive summary of session data"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # First, get the session_id for this session_code
        cur.execute("""
            SELECT session_id FROM sessions WHERE session_code = %s
        """, (session_code,))
        session_result = cur.fetchone()
        
        if not session_result:
            print(f"Session not found: {session_code}")
            return {'error': f'Session not found: {session_code}'}
        
        session_id = session_result['session_id']
        
        # Get participants - use session_code (participants table has session_code field)
        cur.execute("""
            SELECT * FROM participants WHERE session_code = %s
        """, (session_code,))
        participants = [dict(row) for row in cur.fetchall()]
        
        # Get trades - use session_id (trades table uses session_id foreign key)
        cur.execute("""
            SELECT 
                t.transaction_id as id,
                t.session_id,
                t.seller_id,
                t.buyer_id,
                t.proposer_id,
                t.recipient_id,
                t.offer_type,
                t.shape_type as shape,
                t.shape_color,
                t.quantity,
                t.agreed_price as price,
                t.transaction_status as status,
                t.proposed_timestamp as timestamp,
                t.agreed_timestamp,
                t.completed_timestamp,
                t.transaction_data,
                proposer.participant_code as from,
                recipient.participant_code as to
            FROM transactions t
            LEFT JOIN participants proposer ON t.proposer_id = proposer.participant_id
            LEFT JOIN participants recipient ON t.recipient_id = recipient.participant_id
            WHERE t.session_id = %s
            ORDER BY t.proposed_timestamp DESC
        """, (session_id,))
        trades = [dict(row) for row in cur.fetchall()]
        
        # Get messages - use session_id (messages table uses session_id foreign key)
        cur.execute("""
            SELECT 
                m.message_id,
                m.sender_id,
                m.recipient_id,
                m.message_content as content,
                m.message_timestamp as timestamp,
                m.message_type,
                sender.participant_code as sender,
                COALESCE(recipient.participant_code, 'all') as recipient
            FROM messages m
            LEFT JOIN participants sender ON m.sender_id = sender.participant_id
            LEFT JOIN participants recipient ON m.recipient_id = recipient.participant_id
            WHERE m.session_id = %s
            ORDER BY m.message_timestamp DESC
        """, (session_id,))
        messages = [dict(row) for row in cur.fetchall()]
        
        # Get session info
        cur.execute("""
            SELECT * FROM sessions WHERE session_code = %s
        """, (session_code,))
        session_info = cur.fetchone()
        
        cur.close()
        return_db_connection(conn)
        
        # Create summary
        summary = {
            'sessionInfo': {
                'sessionCode': session_code,
                'sessionId': str(session_id),
                'exportTimestamp': datetime.now().isoformat(),
                'exportDate': datetime.now().strftime('%Y-%m-%d'),
                'exportTime': datetime.now().strftime('%H:%M:%S')
            },
            'sessionData': dict(session_info) if session_info else {},
            'participants': participants,
            'trades': trades,
            'messages': messages,
            'sessionMetrics': {
                'totalParticipants': len(participants),
                'onlineParticipants': len([p for p in participants if p.get('status') == 'online']),
                'totalTrades': len(trades),
                'totalMessages': len(messages)
            }
        }
        
        return summary
        
    except Exception as e:
        print(f"Error creating session summary: {e}")
        return {'error': str(e)}

@app.route('/api/cancel-trade-offer', methods=['POST'])
def cancel_trade_offer():
    """Cancel a trade offer"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')  # CRITICAL FIX: Use session_code from JWT token
        data = request.get_json()
        transaction_id = data.get('transaction_id')
        
        if not transaction_id:
            return jsonify({"error": "Transaction ID required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # CRITICAL FIX: No need to query for session_code - use it from JWT token
        # This prevents cross-session data leakage
        
        # Get session ID for logging
        session_id = get_participant_session_id(participant_code)
        logger = get_human_logger(participant_code, session_id, session_code)
        
        # Get game engine
        game_engine = get_game_engine()
        result = game_engine.cancel_trade_offer(
            participant_code,
            transaction_id,
            session_code
        )
        
        # Log the trade cancellation action
        success = result.get('success', False)
        error_message = result.get('error') if not success else None
        logger.log_trade_cancellation(transaction_id, success, error_message)
        
        # Emit WebSocket event to notify participants of cancelled trade offer
        if result.get('success'):
            socketio.emit('trade_offer_cancelled', {
                'canceller': participant_code,
                'transaction_id': transaction_id,
                'timestamp': datetime.now().isoformat()
            }, room=f'session_{session_code}')
        
        return jsonify(result)
        
    except Exception as e:
        # Log the error if we have a logger
        try:
            participant_code = verify_participant_token(request).get('participant_code') if verify_participant_token(request) else None
            session_code = verify_participant_token(request).get('session_code') if verify_participant_token(request) else None
            if participant_code:
                session_id = get_participant_session_id(participant_code, session_code)
                logger = get_human_logger(participant_code, session_id, session_code)
                logger.log_trade_cancellation("unknown", False, str(e))
        except:
            pass
        return jsonify({"error": str(e)}), 500

@app.route('/api/essayranking/assign-essays', methods=['POST'])
def assign_essays():
    """Assign essays to an essay ranking session with PDF file upload and text extraction"""
    try:
        # Check if this is a file upload (FormData) or JSON request
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file upload
            session_code = request.form.get('session_code')
            essays_metadata_json = request.form.get('essays_metadata')
            
            if not session_code:
                return jsonify({"error": "Session code required"}), 400
            
            if not essays_metadata_json:
                return jsonify({"error": "Essays metadata required"}), 400
            
            try:
                essays_metadata = json.loads(essays_metadata_json)
            except json.JSONDecodeError:
                return jsonify({"error": "Invalid essays metadata JSON"}), 400
            
            # Process uploaded files
            essays = []
            file_index = 0
            
            for essay_meta in essays_metadata:
                essay_data = {
                    'essay_id': essay_meta['essay_id'],
                    'title': essay_meta['title'],
                    'filename': essay_meta['filename']
                }
                
                # Look for corresponding file
                file_key = f'essay_file_{file_index}'
                if file_key in request.files:
                    essay_file = request.files[file_key]
                    if essay_file and essay_file.filename:
                        # Read file content
                        essay_file.seek(0)
                        file_content = essay_file.read()
                        essay_data['file'] = file_content
                        essay_file.seek(0)  # Reset for potential re-reading
                
                essays.append(essay_data)
                file_index += 1
            
        else:
            # Handle JSON request (backward compatibility)
            data = request.get_json()
            session_code = data.get('session_code')
            essays = data.get('essays', [])
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        if not essays:
            return jsonify({"error": "Essays list required"}), 400
        
        # Get the appropriate game engine
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        if experiment_type != 'essayranking':
            return jsonify({"error": "This endpoint is only for essay ranking experiments"}), 400
        
        logger.info(f"Assigning {len(essays)} essays to session {session_code}")
        game_engine = get_game_engine(experiment_type)
        result = game_engine.assign_essays(session_code, essays)
        
        logger.info(f"Essay assignment result: {result}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error assigning essays: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/essayranking/get-essays', methods=['GET'])
def get_assigned_essays():
    """Get essays assigned to a session"""
    try:
        session_code = request.args.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # Get the appropriate game engine
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        if experiment_type != 'essayranking':
            return jsonify({"error": "This endpoint is only for essay ranking experiments"}), 400
        
        game_engine = get_game_engine(experiment_type)
        essays = game_engine.get_assigned_essays(session_code)
        
        return jsonify({
            "success": True,
            "essays": essays
        })
        
    except Exception as e:
        logger.error(f"Error getting assigned essays: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/essayranking/submit-ranking', methods=['POST'])
def submit_essay_ranking():
    """Submit essay rankings for a participant (ranking only, no scores required, allows multiple submissions for adjustments)"""
    try:
        data = request.get_json()
        participant_code = data.get('participant_code')
        session_code = data.get('session_code')
        rankings = data.get('rankings', [])
        
        if not participant_code:
            return jsonify({"error": "Participant code required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        if not rankings:
            return jsonify({"error": "Rankings required"}), 400
        
        # Get the appropriate game engine
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        if experiment_type != 'essayranking':
            return jsonify({"error": "This endpoint is only for essay ranking experiments"}), 400
        
        game_engine = get_game_engine(experiment_type)
        result = game_engine.submit_ranking(participant_code, rankings, session_code)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error submitting essay ranking: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/session-statistics', methods=['GET'])
def get_session_statistics():
    """Get comprehensive session statistics for behavioral logs"""
    try:
        session_code = request.args.get('session_code')
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # Import the session statistics extractor
        from session_statistics import SessionStatisticsExtractor
        
        # Initialize extractor
        extractor = SessionStatisticsExtractor()
        
        try:
            # Connect to database
            extractor.connect()
            
            # Extract statistics
            stats = extractor.extract_session_statistics(session_code)
            
            # Convert to JSON-serializable format
            def datetime_converter(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                return str(obj)
            
            # Convert to dictionary
            from dataclasses import asdict
            stats_dict = asdict(stats)
            
            return jsonify({
                "success": True,
                "statistics": stats_dict
            })
            
        finally:
            extractor.disconnect()
            
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        print(f"Error getting session statistics: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/wordguessing/submit-guess', methods=['POST'])
def submit_wordguessing_guess():
    """Submit a guess in wordguessing experiment"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')
        data = request.get_json()
        guess_text = data.get('guess_text')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        if not guess_text:
            return jsonify({"error": "Guess text required"}), 400
        
        # Get experiment type and validate
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        if experiment_type != 'wordguessing':
            return jsonify({"error": "This endpoint is only for wordguessing experiments"}), 400
        
        # Get game engine and submit guess
        game_engine = get_game_engine(experiment_type)
        result = game_engine.submit_guess(participant_code, guess_text, session_code)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/wordguessing/assign-words', methods=['POST'])
def assign_wordguessing_words():
    """Assign words to a hinter in wordguessing experiment"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        participant_code = payload.get('participant_code')
        session_code = payload.get('session_code')
        data = request.get_json()
        words = data.get('words', [])
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        if not words:
            return jsonify({"error": "Words list required"}), 400
        
        # Get experiment type and validate
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        if experiment_type != 'wordguessing':
            return jsonify({"error": "This endpoint is only for wordguessing experiments"}), 400
        
        # Use game engine to assign words
        game_engine = get_game_engine(experiment_type)
        result = game_engine.assign_words_to_hinter(participant_code, words, session_code)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/wordguessing/researcher/assign-words', methods=['POST'])
def researcher_assign_wordguessing_words():
    """Researcher endpoint to assign words to a hinter participant"""
    try:
        data = request.get_json()
        participant_code = data.get('participant_code')
        session_code = data.get('session_code')
        words = data.get('words', [])
        
        if not participant_code:
            return jsonify({"error": "Participant code is required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code is required"}), 400
        
        if not words:
            return jsonify({"error": "Words list is required"}), 400
        
        # Check if this is a wordguessing experiment
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type')
        
        if experiment_type != 'wordguessing':
            return jsonify({"error": "This endpoint is only for wordguessing experiments"}), 400
        
        # Use game engine to assign words
        game_engine = get_game_engine(experiment_type)
        result = game_engine.assign_words_to_hinter(participant_code, words, session_code)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/wordguessing/assign-roles', methods=['POST'])
def assign_wordguessing_roles():
    """Assign roles to participants in wordguessing experiment"""
    try:
        # Verify token
        payload = verify_participant_token(request)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401
        
        session_code = payload.get('session_code')
        data = request.get_json()
        role_assignments = data.get('role_assignments', {})
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        if not role_assignments:
            return jsonify({"error": "Role assignments required"}), 400
        
        # Get experiment type and validate
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        if experiment_type != 'wordguessing':
            return jsonify({"error": "This endpoint is only for wordguessing experiments"}), 400
        
        # Use game engine to assign roles
        game_engine = get_game_engine(experiment_type)
        result = game_engine.assign_roles_to_participants(role_assignments, session_code)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# MTURK INTEGRATION API ENDPOINTS
# ============================================================================

@app.route('/api/mturk/sessions/<session_code>/associate', methods=['POST'])
def associate_mturk_hit(session_code):
    """Associate an external mTurk HIT with a session."""
    data = request.get_json()
    hit_id = data.get('hit_id')
    environment = data.get('environment')

    if not hit_id or not environment:
        return jsonify({'error': 'hit_id and environment are required'}), 400

    try:
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                # Check if mturk_tasks table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'mturk_tasks'
                    )
                """)
                table_exists = cur.fetchone()[0]
                
                if not table_exists:
                    logger.warning("mturk_tasks table does not exist. mTurk functionality may not be available.")
                    return jsonify({
                        'error': 'mTurk tasks table not found. Please ensure the database schema is up to date.',
                        'success': False
                    }), 503
                
                cur.execute("SELECT session_id FROM sessions WHERE session_code = %s", (session_code,))
                session = cur.fetchone()
                if not session:
                    return jsonify({'error': 'Session not found'}), 404
                
                session_id = session['session_id']
                
                cur.execute(
                    """
                    INSERT INTO mturk_tasks (hit_id, session_id, environment)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (hit_id) DO UPDATE SET session_id = EXCLUDED.session_id;
                    """,
                    (hit_id, session_id, environment)
                )
                conn.commit()
        return jsonify({'success': True, 'message': f'HIT {hit_id} associated with session {session_code}.'})
    except Exception as e:
        error_msg = str(e)
        if 'does not exist' in error_msg or 'relation' in error_msg.lower():
            logger.error(f"Database table error: {e}")
            return jsonify({
                'error': 'mTurk tasks table not found. Please ensure the database schema is up to date.',
                'success': False
            }), 503
        logger.error(f"Error associating HIT: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/mturk/sessions/<session_code>/assignments', methods=['GET'])
def get_mturk_assignments(session_code):
    """Get all assignments for a session's associated HIT."""
    try:
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                # Check if mturk_tasks table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'mturk_tasks'
                    )
                """)
                table_exists = cur.fetchone()[0]
                
                if not table_exists:
                    logger.warning("mturk_tasks table does not exist. mTurk functionality may not be available.")
                    return jsonify({
                        'error': 'mTurk tasks table not found. Please ensure the database schema is up to date.',
                        'success': False
                    }), 503
                
                cur.execute("SELECT hit_id FROM mturk_tasks WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)", (session_code,))
                task = cur.fetchone()
                if not task:
                    return jsonify({'error': 'No mTurk HIT associated with this session'}), 404
                hit_id = task['hit_id']

        assignments = mturk_service.list_assignments_for_hit(hit_id)
        # Here you could enrich the assignments with data from your local `participants` table
        return jsonify({'success': True, 'assignments': assignments})
    except Exception as e:
        error_msg = str(e)
        if 'does not exist' in error_msg or 'relation' in error_msg.lower():
            logger.error(f"Database table error: {e}")
            return jsonify({
                'error': 'mTurk tasks table not found. Please ensure the database schema is up to date.',
                'success': False
            }), 503
        logger.error(f"Error getting assignments: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/mturk/assignments/<assignment_id>/approve', methods=['POST'])
def approve_mturk_assignment(assignment_id):
    """Approve an mTurk assignment."""
    data = request.get_json() or {}
    feedback = data.get('feedback', 'Thank you for your work!')
    
    success = mturk_service.approve_assignment(assignment_id, feedback)
    if success:
        return jsonify({'success': True, 'message': f'Assignment {assignment_id} approved.'})
    else:
        return jsonify({'error': f'Failed to approve assignment {assignment_id}.'}), 500

@app.route('/api/mturk/assignments/<assignment_id>/reject', methods=['POST'])
def reject_mturk_assignment(assignment_id):
    """Reject an mTurk assignment."""
    data = request.get_json()
    reason = data.get('reason')
    if not reason:
        return jsonify({'error': 'A reason is required to reject an assignment.'}), 400

    success = mturk_service.reject_assignment(assignment_id, reason)
    if success:
        return jsonify({'success': True, 'message': f'Assignment {assignment_id} rejected.'})
    else:
        return jsonify({'error': f'Failed to reject assignment {assignment_id}.'}), 500

@app.route('/api/mturk/assign-hiddenprofile', methods=['POST'])
def assign_hiddenprofile_for_mturk():
    """
    assign registered hiddenprofiles session and participant
    """
    try:
        data = request.get_json() or {}
        worker_id = data.get('workerId') or request.args.get('workerId')
        assignment_id = data.get('assignmentId') or request.args.get('assignmentId')
        hit_id = data.get('hitId') or request.args.get('hitId')
        
        logger.info(f"[MTURK] Received assignment request: workerId={worker_id}, assignmentId={assignment_id}, hitId={hit_id}")
        
        if not worker_id or not assignment_id:
            logger.warning(f"[MTURK] Missing required parameters: workerId={worker_id}, assignmentId={assignment_id}")
            return jsonify({
                'success': False,
                'error': 'workerId and assignmentId are required'
            }), 400
        
        # preview mode?
        is_preview = assignment_id == 'ASSIGNMENT_ID_NOT_AVAILABLE'
        if is_preview:
            return jsonify({
                'success': False,
                'error': 'This is a preview. Please accept the HIT first.',
                'is_preview': True
            }), 400
        
        with DatabaseConnection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 1. if the worker has already been assigned, return the existing information
                cur.execute("""
                    SELECT p.session_code, p.participant_code, p.participant_id, s.session_id, s.experiment_type
                    FROM participants p
                    JOIN sessions s ON p.session_id = s.session_id
                    WHERE p.mturk_worker_id = %s
                    AND p.mturk_assignment_id = %s
                    AND s.experiment_type = 'hiddenprofiles'
                """, (worker_id, assignment_id))
                
                existing = cur.fetchone()
                if existing:
                    # already assigned, return the existing information
                    return jsonify({
                        'success': True,
                        'session_code': existing['session_code'],
                        'participant_code': existing['participant_code'],
                        'participant_id': str(existing['participant_id']),
                        'session_id': str(existing['session_id']),
                        'already_assigned': True,
                        'message': 'Already assigned to a session'
                    })
                
                # 2. find an unassigned session + participant
                # First, check what sessions exist and why they might not match
                cur.execute("""
                    SELECT 
                        s.session_id, 
                        s.session_code,
                        s.experiment_type,
                        s.session_status,
                        COUNT(p.participant_id) as participant_count
                    FROM sessions s
                    LEFT JOIN participants p ON p.session_id = s.session_id
                    WHERE s.experiment_type = 'hiddenprofiles' OR s.experiment_type IS NULL
                    GROUP BY s.session_id, s.session_code, s.experiment_type, s.session_status
                """)
                
                all_sessions = cur.fetchall()
                logger.info(f"[MTURK] Found {len(all_sessions)} session(s) with experiment_type='hiddenprofiles' or NULL")
                
                # Check available sessions with detailed diagnostics
                cur.execute("""
                    SELECT 
                        s.session_id, 
                        s.session_code,
                        s.experiment_type,
                        s.session_status,
                        p.participant_id,
                        p.participant_code,
                        p.is_agent,
                        p.participant_type,
                        p.mturk_worker_id
                    FROM sessions s
                    LEFT JOIN participants p ON p.session_id = s.session_id AND p.is_agent = false AND p.participant_type = 'human'
                    WHERE s.experiment_type = 'hiddenprofiles' OR s.experiment_type IS NULL
                """)
                
                all_sessions_with_participants = cur.fetchall()
                
                # Log diagnostic information
                logger.info(f"[MTURK] Diagnostic: Checking {len(all_sessions_with_participants)} session+participant combinations")
                
                for row in all_sessions_with_participants:
                    issues = []
                    if row['experiment_type'] != 'hiddenprofiles':
                        issues.append(f"experiment_type='{row['experiment_type']}' (needs 'hiddenprofiles')")
                    if row['session_status'] != 'idle':
                        issues.append(f"session_status='{row['session_status']}' (needs 'idle')")
                    if row['participant_id'] is None:
                        issues.append("no human participant found")
                    elif row['is_agent']:
                        issues.append(f"participant is_agent={row['is_agent']} (needs false)")
                    elif row['participant_type'] != 'human':
                        issues.append(f"participant_type='{row['participant_type']}' (needs 'human')")
                    elif row['mturk_worker_id'] is not None:
                        issues.append(f"already assigned to worker '{row['mturk_worker_id']}'")
                    
                    if issues:
                        logger.info(f"[MTURK] Session {row['session_code']}: ❌ {'; '.join(issues)}")
                    else:
                        logger.info(f"[MTURK] Session {row['session_code']}: ✅ Ready for assignment")
                
                # Now try to find an available session
                cur.execute("""
                    SELECT 
                        s.session_id, 
                        s.session_code,
                        p.participant_id,
                        p.participant_code
                    FROM sessions s
                    INNER JOIN participants p ON p.session_id = s.session_id
                    WHERE s.experiment_type = 'hiddenprofiles'
                      AND s.session_status = 'idle'
                      AND p.is_agent = false
                      AND p.participant_type = 'human'
                      AND p.mturk_worker_id IS NULL
                    ORDER BY RANDOM()
                    LIMIT 1
                    FOR UPDATE OF p SKIP LOCKED
                """)
                
                assignment = cur.fetchone()
                
                if not assignment:
                    # Build detailed error message with diagnostics
                    logger.warning(f"[MTURK] No available sessions found. Running diagnostics...")
                    
                    error_details = {
                        'error': 'No available hiddenprofiles sessions with unassigned participants.',
                        'diagnostics': {
                            'total_sessions_checked': len(all_sessions),
                            'sessions': []
                        }
                    }
                    
                    # Get detailed information about all sessions and their participants
                    cur.execute("""
                        SELECT 
                            s.session_code,
                            s.experiment_type,
                            s.session_status,
                            p.participant_code,
                            p.participant_type,
                            p.is_agent,
                            p.mturk_worker_id,
                            p.mturk_assignment_id
                        FROM sessions s
                        LEFT JOIN participants p ON p.session_id = s.session_id
                        ORDER BY s.session_code, p.participant_code
                    """)
                    
                    all_data = cur.fetchall()
                    
                    # Group by session
                    sessions_dict = {}
                    for row in all_data:
                        session_code = row['session_code']
                        if session_code not in sessions_dict:
                            sessions_dict[session_code] = {
                                'session_code': session_code,
                                'experiment_type': row['experiment_type'],
                                'session_status': row['session_status'],
                                'participants': [],
                                'issues': []
                            }
                        
                        if row['participant_code']:
                            sessions_dict[session_code]['participants'].append({
                                'participant_code': row['participant_code'],
                                'participant_type': row['participant_type'],
                                'is_agent': row['is_agent'],
                                'mturk_worker_id': row['mturk_worker_id'],
                                'mturk_assignment_id': row['mturk_assignment_id']
                            })
                    
                    # Check each session for issues
                    for session_code, session_data in sessions_dict.items():
                        session_issues = []
                        
                        # Check session-level issues
                        if session_data['experiment_type'] != 'hiddenprofiles':
                            session_issues.append(f"experiment_type='{session_data['experiment_type']}' (needs 'hiddenprofiles')")
                        
                        if session_data['session_status'] != 'idle':
                            session_issues.append(f"session_status='{session_data['session_status']}' (needs 'idle')")
                        
                        # Check participants
                        human_participants = [p for p in session_data['participants'] 
                                            if p['participant_type'] == 'human' and not p['is_agent']]
                        
                        if not human_participants:
                            session_issues.append("no human participant found (needs participant_type='human' AND is_agent=false)")
                        else:
                            unassigned_humans = [p for p in human_participants if p['mturk_worker_id'] is None]
                            if not unassigned_humans:
                                session_issues.append(f"all human participants already assigned to MTurk workers")
                                for p in human_participants:
                                    if p['mturk_worker_id']:
                                        session_issues.append(f"  - {p['participant_code']} assigned to worker '{p['mturk_worker_id']}'")
                        
                        session_data['issues'] = session_issues
                        error_details['diagnostics']['sessions'].append(session_data)
                        
                        # Log issues for this session
                        if session_issues:
                            logger.warning(f"[MTURK] Session '{session_code}' issues: {'; '.join(session_issues)}")
                        else:
                            logger.info(f"[MTURK] Session '{session_code}' appears ready but was not selected")
                    
                    logger.error(f"[MTURK] Assignment failed for worker {worker_id}. Details: {len(sessions_dict)} sessions checked")
                    return jsonify(error_details), 404
                
                session_id = assignment['session_id']
                session_code = assignment['session_code']
                participant_id = assignment['participant_id']
                participant_code = assignment['participant_code']
                
                # 3. update the participant's MTurk information
                cur.execute("""
                    UPDATE participants 
                    SET mturk_worker_id = %s,
                        mturk_assignment_id = %s,
                        mturk_hit_id = %s,
                        is_preview = %s
                    WHERE participant_id = %s
                    RETURNING participant_id
                """, (
                    worker_id,
                    assignment_id,
                    hit_id,
                    False,  # is_preview
                    participant_id
                ))
                
                updated = cur.fetchone()
                if not updated:
                    conn.rollback()
                    return jsonify({
                        'success': False,
                        'error': 'Failed to update participant MTurk information'
                    }), 500
                
                conn.commit()
                
                logger.info(f"MTurk worker {worker_id} assigned to hiddenprofiles session {session_code}, participant {participant_code}")
                
                return jsonify({
                    'success': True,
                    'session_code': session_code,
                    'session_id': str(session_id),
                    'participant_code': participant_code,
                    'participant_id': str(participant_id),
                    'already_assigned': False,
                    'message': 'Successfully assigned to session'
                })
                
    except Exception as e:
        logger.error(f"Error in assign_hiddenprofile_for_mturk: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': error_traceback
        }), 500

@app.route('/api/mturk/auto-login-hiddenprofile', methods=['POST'])
def auto_login_hiddenprofile_for_mturk():
    """
    auto login for an assigned mTurk worker
    """
    try:
        data = request.get_json() or {}
        worker_id = data.get('workerId') or request.args.get('workerId')
        assignment_id = data.get('assignmentId') or request.args.get('assignmentId')
        
        if not worker_id or not assignment_id:
            return jsonify({
                'success': False,
                'error': 'workerId and assignmentId are required'
            }), 400
        
        # find the participant
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT p.*, s.session_code
            FROM participants p
            JOIN sessions s ON p.session_id = s.session_id
            WHERE p.mturk_worker_id = %s
            AND p.mturk_assignment_id = %s
            AND s.experiment_type = 'hiddenprofiles'
        """, (worker_id, assignment_id))
        
        participant = cur.fetchone()
        
        if not participant:
            cur.close()
            return_db_connection(conn)
            return jsonify({
                'success': False,
                'error': 'Participant not found. Please assign first.'
            }), 404
        
        session_code = participant['session_code']
        participant_code = participant['participant_code']
        
        # generate JWT token
        token_payload = {
            'participant_code': participant_code,
            'session_code': session_code,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        
        token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        # update the login status
        cur.execute("""
            UPDATE participants 
            SET login_status = 'active', last_activity = %s
            WHERE participant_code = %s AND session_code = %s
        """, (datetime.now(timezone.utc), participant_code, session_code))
        
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        # log the login
        session_id = participant['session_id']
        logger_obj = get_human_logger(participant_code, session_id, session_code)
        logger_obj.log_login(session_code)
        
        return jsonify({
            'success': True,
            'token': token,
            'participant': dict(participant),
            'session': {
                'session_code': session_code,
                'session_id': str(participant['session_id'])
            }
        })
        
    except Exception as e:
        logger.error(f"Error in auto_login_hiddenprofile_for_mturk: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# PROLIFIC INTEGRATION API ENDPOINTS
# ============================================================================

@app.route('/api/prolific/assign-hiddenprofile', methods=['POST'])
def assign_hiddenprofile_for_prolific():
    """
    assign registered hiddenprofiles session and participant for Prolific
    """
    try:
        data = request.get_json() or {}
        prolific_pid = data.get('prolificPid') or request.args.get('PROLIFIC_PID')
        study_id = data.get('studyId') or request.args.get('STUDY_ID')
        prolific_session_id = data.get('prolificSessionId') or request.args.get('SESSION_ID')
        
        logger.info(f"[PROLIFIC] Received assignment request: prolificPid={prolific_pid}, studyId={study_id}, prolificSessionId={prolific_session_id}")
        
        if not prolific_pid or not study_id or not prolific_session_id:
            logger.warning(f"[PROLIFIC] Missing required parameters: prolificPid={prolific_pid}, studyId={study_id}, prolificSessionId={prolific_session_id}")
            return jsonify({
                'success': False,
                'error': 'PROLIFIC_PID, STUDY_ID, and SESSION_ID are required'
            }), 400
        
        with DatabaseConnection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 1. if the participant has already been assigned, return the existing information
                cur.execute("""
                    SELECT p.session_code, p.participant_code, p.participant_id, s.session_id, s.experiment_type
                    FROM participants p
                    JOIN sessions s ON p.session_id = s.session_id
                    WHERE p.prolific_pid = %s
                    AND p.prolific_study_id = %s
                    AND p.prolific_session_id = %s
                    AND s.experiment_type = 'hiddenprofiles'
                """, (prolific_pid, study_id, prolific_session_id))
                
                existing = cur.fetchone()
                if existing:
                    # already assigned, return the existing information
                    return jsonify({
                        'success': True,
                        'session_code': existing['session_code'],
                        'participant_code': existing['participant_code'],
                        'participant_id': str(existing['participant_id']),
                        'session_id': str(existing['session_id']),
                        'already_assigned': True,
                        'message': 'Already assigned to a session'
                    })
                
                # 2. find an unassigned session + participant
                # First, check what sessions exist and why they might not match
                cur.execute("""
                    SELECT 
                        s.session_id, 
                        s.session_code,
                        s.experiment_type,
                        s.session_status,
                        COUNT(p.participant_id) as participant_count
                    FROM sessions s
                    LEFT JOIN participants p ON p.session_id = s.session_id
                    WHERE s.experiment_type = 'hiddenprofiles' OR s.experiment_type IS NULL
                    GROUP BY s.session_id, s.session_code, s.experiment_type, s.session_status
                """)
                
                all_sessions = cur.fetchall()
                logger.info(f"[PROLIFIC] Found {len(all_sessions)} session(s) with experiment_type='hiddenprofiles' or NULL")
                
                # Check available sessions with detailed diagnostics
                cur.execute("""
                    SELECT 
                        s.session_id, 
                        s.session_code,
                        s.experiment_type,
                        s.session_status,
                        p.participant_id,
                        p.participant_code,
                        p.is_agent,
                        p.participant_type,
                        p.prolific_pid
                    FROM sessions s
                    LEFT JOIN participants p ON p.session_id = s.session_id AND p.is_agent = false AND p.participant_type = 'human'
                    WHERE s.experiment_type = 'hiddenprofiles' OR s.experiment_type IS NULL
                """)
                
                all_sessions_with_participants = cur.fetchall()
                
                # Log diagnostic information
                logger.info(f"[PROLIFIC] Diagnostic: Checking {len(all_sessions_with_participants)} session+participant combinations")
                
                for row in all_sessions_with_participants:
                    issues = []
                    if row['experiment_type'] != 'hiddenprofiles':
                        issues.append(f"experiment_type='{row['experiment_type']}' (needs 'hiddenprofiles')")
                    if row['session_status'] != 'idle':
                        issues.append(f"session_status='{row['session_status']}' (needs 'idle')")
                    if row['participant_id'] is None:
                        issues.append("no human participant found")
                    elif row['is_agent']:
                        issues.append(f"participant is_agent={row['is_agent']} (needs false)")
                    elif row['participant_type'] != 'human':
                        issues.append(f"participant_type='{row['participant_type']}' (needs 'human')")
                    elif row['prolific_pid'] is not None:
                        issues.append(f"already assigned to prolific_pid '{row['prolific_pid']}'")
                    
                    if issues:
                        logger.info(f"[PROLIFIC] Session {row['session_code']}: ❌ {'; '.join(issues)}")
                    else:
                        logger.info(f"[PROLIFIC] Session {row['session_code']}: ✅ Ready for assignment")
                
                # Now try to find an available session
                cur.execute("""
                    SELECT 
                        s.session_id, 
                        s.session_code,
                        p.participant_id,
                        p.participant_code
                    FROM sessions s
                    INNER JOIN participants p ON p.session_id = s.session_id
                    WHERE s.experiment_type = 'hiddenprofiles'
                      AND s.session_status = 'idle'
                      AND p.is_agent = false
                      AND p.participant_type = 'human'
                      AND p.prolific_pid IS NULL
                    ORDER BY RANDOM()
                    LIMIT 1
                    FOR UPDATE OF p SKIP LOCKED
                """)
                
                assignment = cur.fetchone()
                
                if not assignment:
                    # Build detailed error message with diagnostics
                    logger.warning(f"[PROLIFIC] No available sessions found. Running diagnostics...")
                    
                    error_details = {
                        'error': 'No available hiddenprofiles sessions with unassigned participants.',
                        'diagnostics': {
                            'total_sessions_checked': len(all_sessions),
                            'sessions': []
                        }
                    }
                    
                    # Get detailed information about all sessions and their participants
                    cur.execute("""
                        SELECT 
                            s.session_code,
                            s.experiment_type,
                            s.session_status,
                            p.participant_code,
                            p.participant_type,
                            p.is_agent,
                            p.prolific_pid,
                            p.prolific_study_id,
                            p.prolific_session_id
                        FROM sessions s
                        LEFT JOIN participants p ON p.session_id = s.session_id
                        ORDER BY s.session_code, p.participant_code
                    """)
                    
                    all_data = cur.fetchall()
                    
                    # Group by session
                    sessions_dict = {}
                    for row in all_data:
                        session_code = row['session_code']
                        if session_code not in sessions_dict:
                            sessions_dict[session_code] = {
                                'session_code': session_code,
                                'experiment_type': row['experiment_type'],
                                'session_status': row['session_status'],
                                'participants': [],
                                'issues': []
                            }
                        
                        if row['participant_code']:
                            sessions_dict[session_code]['participants'].append({
                                'participant_code': row['participant_code'],
                                'participant_type': row['participant_type'],
                                'is_agent': row['is_agent'],
                                'prolific_pid': row['prolific_pid'],
                                'prolific_study_id': row['prolific_study_id'],
                                'prolific_session_id': row['prolific_session_id']
                            })
                    
                    # Check each session for issues
                    for session_code, session_data in sessions_dict.items():
                        session_issues = []
                        
                        # Check session-level issues
                        if session_data['experiment_type'] != 'hiddenprofiles':
                            session_issues.append(f"experiment_type='{session_data['experiment_type']}' (needs 'hiddenprofiles')")
                        
                        if session_data['session_status'] != 'idle':
                            session_issues.append(f"session_status='{session_data['session_status']}' (needs 'idle')")
                        
                        # Check participants
                        human_participants = [p for p in session_data['participants'] 
                                            if p['participant_type'] == 'human' and not p['is_agent']]
                        
                        if not human_participants:
                            session_issues.append("no human participant found (needs participant_type='human' AND is_agent=false)")
                        else:
                            unassigned_humans = [p for p in human_participants if p['prolific_pid'] is None]
                            if not unassigned_humans:
                                session_issues.append(f"all human participants already assigned to Prolific participants")
                                for p in human_participants:
                                    if p['prolific_pid']:
                                        session_issues.append(f"  - {p['participant_code']} assigned to prolific_pid '{p['prolific_pid']}'")
                        
                        session_data['issues'] = session_issues
                        error_details['diagnostics']['sessions'].append(session_data)
                        
                        # Log issues for this session
                        if session_issues:
                            logger.warning(f"[PROLIFIC] Session '{session_code}' issues: {'; '.join(session_issues)}")
                        else:
                            logger.info(f"[PROLIFIC] Session '{session_code}' appears ready but was not selected")
                    
                    logger.error(f"[PROLIFIC] Assignment failed for prolific_pid {prolific_pid}. Details: {len(sessions_dict)} sessions checked")
                    return jsonify(error_details), 404
                
                session_id = assignment['session_id']
                session_code = assignment['session_code']
                participant_id = assignment['participant_id']
                participant_code = assignment['participant_code']
                
                # 3. update the participant's Prolific information
                cur.execute("""
                    UPDATE participants 
                    SET prolific_pid = %s,
                        prolific_study_id = %s,
                        prolific_session_id = %s
                    WHERE participant_id = %s
                    RETURNING participant_id
                """, (
                    prolific_pid,
                    study_id,
                    prolific_session_id,
                    participant_id
                ))
                
                updated = cur.fetchone()
                if not updated:
                    conn.rollback()
                    return jsonify({
                        'success': False,
                        'error': 'Failed to update participant Prolific information'
                    }), 500
                
                conn.commit()
                
                logger.info(f"Prolific participant {prolific_pid} assigned to hiddenprofiles session {session_code}, participant {participant_code}")
                
                return jsonify({
                    'success': True,
                    'session_code': session_code,
                    'session_id': str(session_id),
                    'participant_code': participant_code,
                    'participant_id': str(participant_id),
                    'already_assigned': False,
                    'message': 'Successfully assigned to session'
                })
                
    except Exception as e:
        logger.error(f"Error in assign_hiddenprofile_for_prolific: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': error_traceback
        }), 500

@app.route('/api/prolific/auto-login-hiddenprofile', methods=['POST'])
def auto_login_hiddenprofile_for_prolific():
    """
    auto login for an assigned Prolific participant
    """
    try:
        data = request.get_json() or {}
        prolific_pid = data.get('prolificPid') or request.args.get('PROLIFIC_PID')
        study_id = data.get('studyId') or request.args.get('STUDY_ID')
        prolific_session_id = data.get('prolificSessionId') or request.args.get('SESSION_ID')
        
        if not prolific_pid or not study_id or not prolific_session_id:
            return jsonify({
                'success': False,
                'error': 'PROLIFIC_PID, STUDY_ID, and SESSION_ID are required'
            }), 400
        
        # find the participant
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT p.*, s.session_code
            FROM participants p
            JOIN sessions s ON p.session_id = s.session_id
            WHERE p.prolific_pid = %s
            AND p.prolific_study_id = %s
            AND p.prolific_session_id = %s
            AND s.experiment_type = 'hiddenprofiles'
        """, (prolific_pid, study_id, prolific_session_id))
        
        participant = cur.fetchone()
        
        if not participant:
            cur.close()
            return_db_connection(conn)
            return jsonify({
                'success': False,
                'error': 'Participant not found. Please assign first.'
            }), 404
        
        session_code = participant['session_code']
        participant_code = participant['participant_code']
        
        # generate JWT token
        token_payload = {
            'participant_code': participant_code,
            'session_code': session_code,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        
        token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        # update the login status
        cur.execute("""
            UPDATE participants 
            SET login_status = 'active', last_activity = %s
            WHERE participant_code = %s AND session_code = %s
        """, (datetime.now(timezone.utc), participant_code, session_code))
        
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        # log the login
        session_id = participant['session_id']
        logger_obj = get_human_logger(participant_code, session_id, session_code)
        logger_obj.log_login(session_code)
        
        return jsonify({
            'success': True,
            'token': token,
            'participant': dict(participant),
            'session': {
                'session_code': session_code,
                'session_id': str(participant['session_id'])
            }
        })
        
    except Exception as e:
        logger.error(f"Error in auto_login_hiddenprofile_for_prolific: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# HIDDEN PROFILES API ENDPOINTS
# ============================================================================

@app.route('/api/hiddenprofiles/assign-public-info', methods=['POST'])
def assign_public_info():
    """Assign public information document to a Hidden Profiles session"""
    try:
        from pdf_utils import extract_text_from_pdf
        
        # Check if this is a file upload (FormData) or JSON request
        if request.content_type and 'multipart/form-data' in request.content_type:
            session_code = request.form.get('session_code')
            public_info_metadata_json = request.form.get('public_info_metadata')
            public_info_file = request.files.get('public_info_file')
            
            if not session_code:
                return jsonify({"error": "Session code required"}), 400
            
            # Get session_id
            with DatabaseConnection() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT session_id, experiment_config FROM sessions WHERE session_code = %s", (session_code,))
                session_result = cur.fetchone()
                
                if not session_result:
                    return jsonify({"error": "Session not found"}), 404
                
                session_id = session_result['session_id']
                experiment_config = session_result['experiment_config'] or {}
                
                # Check experiment type
                cur.execute("SELECT experiment_type FROM sessions WHERE session_code = %s", (session_code,))
                exp_type_result = cur.fetchone()
                if not exp_type_result or exp_type_result['experiment_type'] != 'hiddenprofiles':
                    return jsonify({"error": "This endpoint is only for Hidden Profiles experiments"}), 400
                
                # Process public info if provided
                if public_info_metadata_json and public_info_file:
                    try:
                        public_info_metadata = json.loads(public_info_metadata_json)
                    except json.JSONDecodeError:
                        return jsonify({"error": "Invalid public info metadata JSON"}), 400
                    
                    # Save PDF file to disk
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    uploads_dir = os.path.join(base_dir, 'uploads', 'hiddenprofiles', session_code)
                    os.makedirs(uploads_dir, exist_ok=True)
                    
                    # Generate unique filename
                    doc_id = public_info_metadata.get('doc_id', str(uuid.uuid4()))
                    original_filename = public_info_metadata.get('filename', 'document.pdf')
                    file_extension = os.path.splitext(original_filename)[1] or '.pdf'
                    saved_filename = f"{doc_id}{file_extension}"
                    file_path = os.path.join(uploads_dir, saved_filename)
                    
                    # Save the file
                    public_info_file.seek(0)
                    public_info_file.save(file_path)
                    
                    # Extract text from PDF
                    public_info_file.seek(0)
                    extracted_text = extract_text_from_pdf(public_info_file)
                    
                    # Store in experiment_config with file URL
                    if 'hiddenProfiles' not in experiment_config:
                        experiment_config['hiddenProfiles'] = {}
                    
                    experiment_config['hiddenProfiles']['publicInfo'] = {
                        'doc_id': doc_id,
                        'title': public_info_metadata.get('title'),
                        'filename': original_filename,
                        'content': extracted_text or '',
                        'file_url': f'/api/hiddenprofiles/get-document/{session_code}/{doc_id}',
                        'saved_filename': saved_filename,
                        'uploaded_at': datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Update experiment_config in database
                    cur.execute("""
                        UPDATE sessions 
                        SET experiment_config = %s 
                        WHERE session_code = %s
                    """, (json.dumps(experiment_config), session_code))
                    conn.commit()
                    
                    # Check if reading phase is now complete and trigger agents
                    _check_and_trigger_agents_for_reading_phase(session_code)
                    
                    return jsonify({
                        "success": True,
                        "message": "Public information assigned successfully",
                        "public_info": experiment_config['hiddenProfiles']['publicInfo']
                    })
                else:
                    # Clear public info if no file provided
                    if 'hiddenProfiles' in experiment_config:
                        experiment_config['hiddenProfiles'].pop('publicInfo', None)
                        cur.execute("""
                            UPDATE sessions 
                            SET experiment_config = %s 
                            WHERE session_code = %s
                        """, (json.dumps(experiment_config), session_code))
                        conn.commit()
                    
                    return jsonify({
                        "success": True,
                        "message": "Public information cleared"
                    })
        else:
            return jsonify({"error": "FormData with file upload required"}), 400
            
    except Exception as e:
        logger.error(f"Error assigning public information: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/hiddenprofiles/assign-candidate-docs', methods=['POST'])
def assign_candidate_docs():
    """Assign candidate documents to a Hidden Profiles session"""
    try:
        from pdf_utils import extract_text_from_pdf
        
        # Check if this is a file upload (FormData) or JSON request
        if request.content_type and 'multipart/form-data' in request.content_type:
            session_code = request.form.get('session_code')
            candidate_docs_metadata_json = request.form.get('candidate_docs_metadata')
            
            if not session_code:
                return jsonify({"error": "Session code required"}), 400
            
            # Get session_id
            with DatabaseConnection() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT session_id, experiment_config FROM sessions WHERE session_code = %s", (session_code,))
                session_result = cur.fetchone()
                
                if not session_result:
                    return jsonify({"error": "Session not found"}), 404
                
                session_id = session_result['session_id']
                experiment_config = session_result['experiment_config'] or {}
                
                # Check experiment type
                cur.execute("SELECT experiment_type FROM sessions WHERE session_code = %s", (session_code,))
                exp_type_result = cur.fetchone()
                if not exp_type_result or exp_type_result['experiment_type'] != 'hiddenprofiles':
                    return jsonify({"error": "This endpoint is only for Hidden Profiles experiments"}), 400
                
                if not candidate_docs_metadata_json:
                    return jsonify({"error": "Candidate docs metadata required"}), 400
                
                try:
                    candidate_docs_metadata = json.loads(candidate_docs_metadata_json)
                except json.JSONDecodeError:
                    return jsonify({"error": "Invalid candidate docs metadata JSON"}), 400
                
                # Get existing candidate docs to preserve file data
                existing_candidate_docs = experiment_config.get('hiddenProfiles', {}).get('candidateDocs', [])
                existing_docs_map = {doc.get('doc_id'): doc for doc in existing_candidate_docs}
                
                # Process uploaded files
                candidate_docs = []
                file_index = 0
                
                # Create uploads directory for this session
                base_dir = os.path.dirname(os.path.abspath(__file__))
                uploads_dir = os.path.join(base_dir, 'uploads', 'hiddenprofiles', session_code)
                os.makedirs(uploads_dir, exist_ok=True)
                
                for doc_meta in candidate_docs_metadata:
                    doc_id = doc_meta['doc_id']
                    doc_data = {
                        'doc_id': doc_id,
                        'title': doc_meta['title'],
                        'filename': doc_meta['filename']
                    }
                    
                    # Check if this document already exists - preserve existing file data
                    existing_doc = existing_docs_map.get(doc_id)
                    if existing_doc:
                        # Preserve existing file information
                        if existing_doc.get('saved_filename'):
                            doc_data['saved_filename'] = existing_doc['saved_filename']
                        if existing_doc.get('file_url'):
                            doc_data['file_url'] = existing_doc['file_url']
                        if existing_doc.get('content'):
                            doc_data['content'] = existing_doc['content']
                    
                    # Look for corresponding file (new upload)
                    file_key = f'candidate_doc_file_{file_index}'
                    if file_key in request.files:
                        doc_file = request.files[file_key]
                        if doc_file and doc_file.filename:
                            # Save PDF file to disk
                            original_filename = doc_meta['filename']
                            file_extension = os.path.splitext(original_filename)[1] or '.pdf'
                            saved_filename = f"{doc_id}{file_extension}"
                            file_path = os.path.join(uploads_dir, saved_filename)
                            
                            # Save the file
                            doc_file.seek(0)
                            doc_file.save(file_path)
                            
                            # Extract text from PDF
                            doc_file.seek(0)
                            extracted_text = extract_text_from_pdf(doc_file)
                            
                            # Overwrite with new file data
                            doc_data['content'] = extracted_text or ''
                            doc_data['file_url'] = f'/api/hiddenprofiles/get-document/{session_code}/{doc_id}'
                            doc_data['saved_filename'] = saved_filename
                    elif not existing_doc:
                        # New document without file - set default file_url
                        doc_data['file_url'] = f'/api/hiddenprofiles/get-document/{session_code}/{doc_id}'
                    
                    candidate_docs.append(doc_data)
                    file_index += 1
                
                # Store in experiment_config
                if 'hiddenProfiles' not in experiment_config:
                    experiment_config['hiddenProfiles'] = {}
                
                experiment_config['hiddenProfiles']['candidateDocs'] = candidate_docs
                experiment_config['hiddenProfiles']['candidateDocsUpdatedAt'] = datetime.now(timezone.utc).isoformat()
                
                # Update experiment_config in database
                cur.execute("""
                    UPDATE sessions 
                    SET experiment_config = %s 
                    WHERE session_code = %s
                """, (json.dumps(experiment_config), session_code))
                conn.commit()
                
                # Check if reading phase is now complete and trigger agents
                _check_and_trigger_agents_for_reading_phase(session_code)
                
                return jsonify({
                    "success": True,
                    "message": f"Successfully assigned {len(candidate_docs)} candidate documents",
                    "docs_assigned": len(candidate_docs),
                    "candidate_docs": candidate_docs
                })
        else:
            return jsonify({"error": "FormData with file upload required"}), 400
            
    except Exception as e:
        logger.error(f"Error assigning candidate documents: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/hiddenprofiles/get-candidate-names', methods=['GET'])
def get_hiddenprofiles_candidate_names():
    """Get candidate display names for a Hidden Profiles session"""
    try:
        session_code = request.args.get('session_code')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cur.execute("SELECT experiment_type, experiment_config FROM sessions WHERE session_code = %s", (session_code,))
            session_row = cur.fetchone()
            if not session_row:
                return jsonify({"error": "Session not found"}), 404
            
            if session_row['experiment_type'] != 'hiddenprofiles':
                return jsonify({"error": "This endpoint is only for Hidden Profiles experiments"}), 400
            
            experiment_config = session_row['experiment_config'] or {}
            candidate_names = experiment_config.get('hiddenProfiles', {}).get('candidateNames', [])
            
            logger.info(f"Retrieved candidate names for session {session_code}: {candidate_names}")
            
        return jsonify({
            "success": True,
            "candidate_names": candidate_names,
            "session_code": session_code
        })
        
    except Exception as e:
        logger.error(f"Error getting candidate names: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/hiddenprofiles/set-candidate-names', methods=['POST'])
def set_hiddenprofiles_candidate_names():
    """Set candidate display names for a Hidden Profiles session"""
    try:
        data = request.get_json() or {}
        session_code = data.get('session_code')
        candidate_names = data.get('candidate_names', [])

        if not session_code:
            return jsonify({"error": "Session code required"}), 400

        if not isinstance(candidate_names, list):
            return jsonify({"error": "candidate_names must be a list of strings"}), 400

        # Normalize and filter names
        normalized_names = [str(name).strip() for name in candidate_names if str(name).strip()]

        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cur.execute("SELECT experiment_type, experiment_config FROM sessions WHERE session_code = %s", (session_code,))
            session_row = cur.fetchone()
            if not session_row:
                return jsonify({"error": "Session not found"}), 404

            if session_row['experiment_type'] != 'hiddenprofiles':
                return jsonify({"error": "This endpoint is only for Hidden Profiles experiments"}), 400

            experiment_config = session_row['experiment_config'] or {}
            if 'hiddenProfiles' not in experiment_config:
                experiment_config['hiddenProfiles'] = {}

            # Verify we're updating the correct session
            logger.info(f"Setting candidate names for session {session_code}: {normalized_names}")
            
            experiment_config['hiddenProfiles']['candidateNames'] = normalized_names

            cur.execute(
                """
                UPDATE sessions
                SET experiment_config = %s
                WHERE session_code = %s
                """,
                (json.dumps(experiment_config), session_code)
            )
            conn.commit()
            
            # Verify the update
            cur.execute("SELECT experiment_config->'hiddenProfiles'->>'candidateNames' as names FROM sessions WHERE session_code = %s", (session_code,))
            verify_row = cur.fetchone()
            logger.info(f"Verified candidate names for session {session_code}: {verify_row.get('names') if verify_row else 'None'}")

        return jsonify({
            "success": True,
            "candidate_names": normalized_names,
            "session_code": session_code
        })

    except Exception as e:
        logger.error(f"Error setting candidate names: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/hiddenprofiles/update-participant-initiative', methods=['POST'])
def update_participant_initiative():
    """Update participant initiative (Active/Passive) for Hidden Profiles experiment"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        participant_id = data.get('participant_id')
        initiative = data.get('initiative')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        if not participant_id:
            return jsonify({"error": "Participant ID required"}), 400
        
        if not initiative or initiative not in ['active', 'passive']:
            return jsonify({"error": "Initiative must be 'active' or 'passive'"}), 400
        
        # Check experiment type
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT experiment_type FROM sessions WHERE session_code = %s", (session_code,))
            exp_type_result = cur.fetchone()
            if not exp_type_result or exp_type_result['experiment_type'] != 'hiddenprofiles':
                return jsonify({"error": "This endpoint is only for Hidden Profiles experiments"}), 400
            
            # Get participant by participant_code (since participant_id might be the code)
            logger.info(f"Looking up participant: participant_id={participant_id}, session_code={session_code}")
            cur.execute("""
                SELECT participant_id, participant_code FROM participants 
                WHERE (participant_code = %s OR participant_id::text = %s) 
                AND session_code = %s
            """, (participant_id, participant_id, session_code))
            
            participant = cur.fetchone()
            if not participant:
                # Log available participants for debugging
                cur.execute("""
                    SELECT participant_id, participant_code FROM participants 
                    WHERE session_code = %s
                """, (session_code,))
                all_participants = cur.fetchall()
                logger.warning(f"Participant not found. Available participants in session {session_code}: {[p['participant_code'] for p in all_participants]}")
                return jsonify({
                    "error": f"Participant '{participant_id}' not found in session '{session_code}'",
                    "available_participants": [p['participant_code'] for p in all_participants] if all_participants else []
                }), 404
            
            # Store initiative in experiment_config or as a JSONB field
            # For now, we'll store it in a JSONB field on participants table if it exists
            # Otherwise, we'll store it in the session's experiment_config
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'participants' AND column_name = 'initiative'
            """)
            has_initiative_column = cur.fetchone() is not None
            
            if has_initiative_column:
                cur.execute("""
                    UPDATE participants 
                    SET initiative = %s 
                    WHERE participant_id = %s
                """, (initiative, participant['participant_id']))
            else:
                # Store in experiment_config as fallback
                cur.execute("SELECT experiment_config FROM sessions WHERE session_code = %s", (session_code,))
                session_result = cur.fetchone()
                experiment_config = session_result['experiment_config'] or {} if session_result else {}
                
                if 'hiddenProfiles' not in experiment_config:
                    experiment_config['hiddenProfiles'] = {}
                if 'participantInitiatives' not in experiment_config['hiddenProfiles']:
                    experiment_config['hiddenProfiles']['participantInitiatives'] = {}
                
                # Save initiative with both isolated name and base name for reliable lookup
                participant_code = participant['participant_code']
                experiment_config['hiddenProfiles']['participantInitiatives'][participant_code] = initiative
                
                # Also save with base name (without session suffix) as fallback
                base_code = participant_code.rsplit('_', 1)[0] if '_' in participant_code else participant_code
                if base_code != participant_code:
                    experiment_config['hiddenProfiles']['participantInitiatives'][base_code] = initiative
                
                cur.execute("""
                    UPDATE sessions 
                    SET experiment_config = %s 
                    WHERE session_code = %s
                """, (json.dumps(experiment_config), session_code))
                
                # Update running agent's is_passive flag if agent is already running
                agent_key = f"{session_code}:{participant_code}" if session_code else participant_code
                agent_info = AGENT_THREADS.get(agent_key)
                if agent_info and agent_info.get('controller'):
                    agent_info['controller'].is_passive = (initiative == 'passive')
                    print(f"[INITIATIVE UPDATE] Updated running agent {participant_code} is_passive to {agent_info['controller'].is_passive}")
            
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": f"Participant initiative updated to {initiative}",
                "participant_code": participant['participant_code'],
                "initiative": initiative
            })
            
    except Exception as e:
        logger.error(f"Error updating participant initiative: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/hiddenprofiles/update-participant-candidate-doc', methods=['POST'])
def update_participant_candidate_doc():
    """Update participant candidate document assignment for Hidden Profiles experiment"""
    try:
        data = request.get_json()
        session_code = data.get('session_code')
        participant_id = data.get('participant_id')
        candidate_document_id = data.get('candidate_document_id')
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        if not participant_id:
            return jsonify({"error": "Participant ID required"}), 400
        
        if not candidate_document_id:
            return jsonify({"error": "Candidate document ID required"}), 400
        
        # Check experiment type
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT experiment_type FROM sessions WHERE session_code = %s", (session_code,))
            exp_type_result = cur.fetchone()
            if not exp_type_result or exp_type_result['experiment_type'] != 'hiddenprofiles':
                return jsonify({"error": "This endpoint is only for Hidden Profiles experiments"}), 400
            
            # Get participant
            logger.info(f"Looking up participant for candidate doc: participant_id={participant_id}, session_code={session_code}")
            cur.execute("""
                SELECT participant_id, participant_code FROM participants 
                WHERE (participant_code = %s OR participant_id::text = %s) 
                AND session_code = %s
            """, (participant_id, participant_id, session_code))
            
            participant = cur.fetchone()
            if not participant:
                # Log available participants for debugging
                cur.execute("""
                    SELECT participant_id, participant_code FROM participants 
                    WHERE session_code = %s
                """, (session_code,))
                all_participants = cur.fetchall()
                logger.warning(f"Participant not found. Available participants in session {session_code}: {[p['participant_code'] for p in all_participants]}")
                return jsonify({
                    "error": f"Participant '{participant_id}' not found in session '{session_code}'",
                    "available_participants": [p['participant_code'] for p in all_participants] if all_participants else []
                }), 404
            
            # Check if candidate_document_id exists in session's candidate docs
            cur.execute("SELECT experiment_config FROM sessions WHERE session_code = %s", (session_code,))
            session_result = cur.fetchone()
            if not session_result:
                logger.error(f"Session {session_code} not found")
                return jsonify({"error": f"Session '{session_code}' not found"}), 404
            
            experiment_config = session_result['experiment_config'] or {}
            
            # Ensure hiddenProfiles config exists
            if 'hiddenProfiles' not in experiment_config:
                experiment_config['hiddenProfiles'] = {}
            
            candidate_docs = experiment_config.get('hiddenProfiles', {}).get('candidateDocs', [])
            
            # Log for debugging
            logger.info(f"Checking candidate document: candidate_document_id={candidate_document_id}, "
                       f"total_candidate_docs={len(candidate_docs)}, session_code={session_code}")
            
            if not candidate_docs or len(candidate_docs) == 0:
                logger.warning(f"No candidate documents found in session {session_code}. "
                              f"hiddenProfiles config keys: {list(experiment_config.get('hiddenProfiles', {}).keys())}")
                return jsonify({
                    "error": "No candidate documents found in session. Please upload candidate documents first.",
                    "candidate_document_id": candidate_document_id,
                    "session_code": session_code,
                    "hint": "Use the 'Assign Candidate Documents' button to upload documents first."
                }), 404
            
            # Log available doc IDs for debugging
            available_doc_ids = [doc.get('doc_id') for doc in candidate_docs if doc.get('doc_id')]
            logger.info(f"Available candidate doc IDs: {available_doc_ids}")
            
            # Check if document exists (handle both string and numeric comparisons)
            doc_exists = False
            matching_doc = None
            for doc in candidate_docs:
                doc_id = doc.get('doc_id')
                if not doc_id:
                    continue
                # Try both string and numeric comparison
                if str(doc_id) == str(candidate_document_id) or doc_id == candidate_document_id:
                    doc_exists = True
                    matching_doc = doc
                    logger.info(f"Found matching candidate document: doc_id={doc_id}, title={doc.get('title', 'N/A')}")
                    break
            
            if not doc_exists:
                logger.error(f"Candidate document '{candidate_document_id}' not found in session '{session_code}'. "
                           f"Available doc IDs: {available_doc_ids}, "
                           f"Requested ID type: {type(candidate_document_id).__name__}")
                return jsonify({
                    "error": "Candidate document not found in session",
                    "candidate_document_id": candidate_document_id,
                    "available_doc_ids": available_doc_ids,
                    "total_docs": len(candidate_docs),
                    "hint": f"Make sure the document ID matches one of the uploaded candidate documents."
                }), 404
            
            # Store assignment in experiment_config
            if 'hiddenProfiles' not in experiment_config:
                experiment_config['hiddenProfiles'] = {}
            if 'participantCandidateDocs' not in experiment_config['hiddenProfiles']:
                experiment_config['hiddenProfiles']['participantCandidateDocs'] = {}
            
            experiment_config['hiddenProfiles']['participantCandidateDocs'][participant['participant_code']] = candidate_document_id
            
            cur.execute("""
                UPDATE sessions 
                SET experiment_config = %s 
                WHERE session_code = %s
            """, (json.dumps(experiment_config), session_code))
            
            conn.commit()
            
            # Check if reading phase is now complete and trigger agents
            _check_and_trigger_agents_for_reading_phase(session_code)
            
            return jsonify({
                "success": True,
                "message": "Participant candidate document assigned successfully",
                "participant_code": participant['participant_code'],
                "candidate_document_id": candidate_document_id
            })
            
    except Exception as e:
        logger.error(f"Error updating participant candidate document: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/hiddenprofiles/submit-vote', methods=['POST'])
def submit_hiddenprofiles_vote():
    """Submit a vote for a candidate name in Hidden Profiles experiment"""
    try:
        data = request.get_json()
        participant_code = data.get('participant_code')
        session_code = data.get('session_code')
        candidate_name = data.get('candidate_name')
        
        if not participant_code:
            return jsonify({"error": "Participant code required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        if not candidate_name:
            return jsonify({"error": "Candidate name required"}), 400
        
        # Get the appropriate game engine
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        if experiment_type != 'hiddenprofiles':
            return jsonify({"error": "This endpoint is only for Hidden Profiles experiments"}), 400
        
        # Check if this is a human participant
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT participant_type 
            FROM participants 
            WHERE participant_code = %s AND session_code = %s
        """, (participant_code, session_code))
        participant = cur.fetchone()
        cur.close()
        return_db_connection(conn)
        
        is_human = participant and participant.get('participant_type') == 'human'
        
        # Determine if this is initial or final vote BEFORE submitting
        vote_type = "INITIAL"
        if is_human:
            try:
                # Check if participant has voted before
                conn = get_db_connection()
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT experiment_config FROM sessions WHERE session_code = %s
                """, (session_code,))
                session_result = cur.fetchone()
                
                if session_result and session_result.get('experiment_config'):
                    import json
                    experiment_config = session_result['experiment_config']
                    if isinstance(experiment_config, str):
                        experiment_config = json.loads(experiment_config)
                    hidden_profiles_config = experiment_config.get('hiddenProfiles', {})
                    votes = hidden_profiles_config.get('votes', {})
                    # Check if this participant has already voted
                    if participant_code in votes:
                        vote_type = "FINAL"
                
                cur.close()
                return_db_connection(conn)
            except Exception as e:
                print(f"⚠️ Warning: Could not determine vote type for {participant_code}: {e}")
        
        game_engine = get_game_engine(experiment_type)
        result = game_engine.submit_vote(participant_code, candidate_name, session_code)
        
        # Log vote for human participants
        if is_human:
            try:
                # Get session_id for logging
                session_id = get_participant_session_id(participant_code, session_code)
                logger = get_human_logger(participant_code, session_id, session_code)
                
                # Log the vote
                details = {
                    "participant_code": participant_code,
                    "candidate_name": candidate_name,
                    "vote_type": vote_type,
                    "session_code": session_code
                }
                logger.log_action("submit_vote", result.get('success', False), 
                                result.get('error') if not result.get('success') else None, 
                                details)
                
                if result.get('success'):
                    logger.log(f"📊 {vote_type} VOTE: {participant_code} submitted vote for candidate: {candidate_name}")
            except Exception as e:
                print(f"⚠️ Warning: Could not log vote for human participant {participant_code}: {e}")
                import traceback
                print(traceback.format_exc())
        
        # If this is the first human vote, activate agents
        if is_human and result.get('success'):
            try:
                # Check if any agents have been activated yet
                conn = get_db_connection()
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # Check if there are any active agent threads for this session
                # AGENT_THREADS is defined in this file (app.py)
                agents_activated = False
                cur.execute("""
                    SELECT participant_code 
                    FROM participants 
                    WHERE session_code = %s AND participant_type = 'ai_agent'
                """, (session_code,))
                agents = cur.fetchall()
                cur.close()
                return_db_connection(conn)
                
                # Check if any agents are already running
                for agent in agents:
                    agent_key = f"{session_code}:{agent['participant_code']}"
                    if agent_key in AGENT_THREADS and AGENT_THREADS[agent_key]['thread'].is_alive():
                        agents_activated = True
                        break
                
                # If no agents are running yet, activate them now
                if not agents_activated and len(agents) > 0:
                    print(f"🚀 First human vote submitted by {participant_code}. Starting experiment and activating agents for session {session_code}...")
                    
                    # First, ensure the experiment is started (for Hidden Profiles, it might not be started yet)
                    session_timer_state = get_timer_state(session_code)
                    if session_timer_state['experiment_status'] != 'running':
                        print(f"📋 Experiment status is '{session_timer_state['experiment_status']}'. Starting experiment now...")
                        
                        # Set session_started_at in database when first vote is submitted
                        from datetime import datetime, timezone
                        vote_submit_time = datetime.now(timezone.utc)
                        
                        try:
                            conn = get_db_connection()
                            cur = conn.cursor()
                            cur.execute("""
                                UPDATE sessions 
                                SET session_status = 'session_active',
                                    session_started_at = %s
                                WHERE session_code = %s
                            """, (vote_submit_time, session_code))
                            conn.commit()
                            cur.close()
                            return_db_connection(conn)
                            print(f"✅ Set session_started_at to {vote_submit_time.isoformat()} for session {session_code} (when first vote was submitted)")
                        except Exception as e:
                            print(f"⚠️ Warning: Could not set session_started_at: {e}")
                        
                        # Get session configuration
                        session_config = get_session_config(session_code)
                        session_duration = session_config.get('sessionDuration', 15)
                        
                        # Initialize timer state for this session
                        initialize_timer_state(session_code)
                        timer_state = get_timer_state(session_code)
                        
                        # Update experiment status to running
                        timer_state['experiment_status'] = 'running'
                        timer_state['round_duration_minutes'] = session_duration
                        timer_state['time_remaining'] = session_duration * 60
                        timer_state['timer_active'] = True
                        timer_state['round_start_time'] = vote_submit_time.isoformat()  # Store start time when vote was submitted
                        
                        print(f"✅ Timer state updated: status=running, time_remaining={timer_state['time_remaining']}, round_start_time={timer_state['round_start_time']}")
                        
                        # Start session-specific timer
                        start_session_timer(session_code)
                        print(f"✅ Experiment started with {session_duration} minutes duration (timer started when human submitted first vote)")
                        
                        # Broadcast timer update to all clients
                        broadcast_timer_update(session_code)
                        
                        # Broadcast experiment_started event
                        socketio.emit('experiment_started', {
                            'experiment_status': 'running',
                            'session_code': session_code,
                            'timer_state': timer_state
                        }, room=f'session_{session_code}')
                        socketio.emit('experiment_started', {
                            'experiment_status': 'running',
                            'session_code': session_code,
                            'timer_state': timer_state
                        }, room='researcher')
                        socketio.emit('experiment_started', {
                            'experiment_status': 'running',
                            'session_code': session_code,
                            'timer_state': timer_state
                        })
                        print("✅ Experiment started event broadcasted to all clients")
                    
                    # Mark agents as active
                    for agent in agents:
                        try:
                            conn = get_db_connection()
                            cur = conn.cursor()
                            cur.execute("""
                                UPDATE participants 
                                SET login_status = 'active', last_activity = %s
                                WHERE participant_code = %s AND session_code = %s
                            """, (datetime.now(timezone.utc), agent['participant_code'], session_code))
                            conn.commit()
                            cur.close()
                            return_db_connection(conn)
                            print(f"✅ Agent {agent['participant_code']} marked active")
                        except Exception as e:
                            print(f"❌ Error marking agent {agent['participant_code']} active: {e}")
                    
                    # Start agent loops (experiment should be running now)
                    session_timer_state = get_timer_state(session_code)
                    if session_timer_state['experiment_status'] == 'running':
                        activation_result = activate_agents_for_session(session_code, use_memory=True)
                        print(f"✅ Agents activated: {activation_result}")
                    else:
                        print(f"⚠️ Warning: Experiment status is '{session_timer_state['experiment_status']}', not 'running'. Agents may not work correctly.")
                elif agents_activated:
                    print(f"ℹ️ Agents already activated for session {session_code}")
                    
            except Exception as e:
                print(f"⚠️ Error activating agents after first human vote: {e}")
                # Don't fail the vote submission if agent activation fails
                import traceback
                traceback.print_exc()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error submitting vote: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/hiddenprofiles/get-assigned-documents', methods=['GET'])
def get_hiddenprofiles_assigned_documents():
    """Get assigned documents (public info + candidate doc) for a participant"""
    try:
        participant_code = request.args.get('participant_code')
        session_code = request.args.get('session_code')
        
        if not participant_code:
            return jsonify({"error": "Participant code required"}), 400
        
        if not session_code:
            return jsonify({"error": "Session code required"}), 400
        
        # Get the appropriate game engine
        session_config = get_session_config(session_code)
        experiment_type = session_config.get('experiment_type', 'shapefactory')
        
        if experiment_type != 'hiddenprofiles':
            return jsonify({"error": "This endpoint is only for Hidden Profiles experiments"}), 400
        
        game_engine = get_game_engine(experiment_type)
        result = game_engine.get_assigned_documents(participant_code, session_code)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting assigned documents: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/hiddenprofiles/get-document/<session_code>/<doc_id>', methods=['GET'])
def get_hiddenprofiles_document(session_code, doc_id):
    """Serve a PDF document file for Hidden Profiles experiment"""
    try:
        # Verify session exists and is hiddenprofiles type
        with DatabaseConnection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT experiment_type FROM sessions WHERE session_code = %s", (session_code,))
            session_result = cur.fetchone()
            
            if not session_result:
                return jsonify({"error": "Session not found"}), 404
            
            if session_result['experiment_type'] != 'hiddenprofiles':
                return jsonify({"error": "This endpoint is only for Hidden Profiles experiments"}), 400
            
            # Get document info from experiment_config
            cur.execute("SELECT experiment_config FROM sessions WHERE session_code = %s", (session_code,))
            session_row = cur.fetchone()
            experiment_config = session_row['experiment_config'] or {} if session_row else {}
            hidden_profiles_config = experiment_config.get('hiddenProfiles', {})
            
            # Check if it's public info
            public_info = hidden_profiles_config.get('publicInfo')
            if public_info and public_info.get('doc_id') == doc_id:
                saved_filename = public_info.get('saved_filename')
                if saved_filename:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    file_path = os.path.join(base_dir, 'uploads', 'hiddenprofiles', session_code, saved_filename)
                    if os.path.exists(file_path):
                        return send_from_directory(
                            os.path.dirname(file_path),
                            saved_filename,
                            as_attachment=False,
                            mimetype='application/pdf'
                        )
            
            # Check if it's a candidate doc
            candidate_docs = hidden_profiles_config.get('candidateDocs', [])
            for doc in candidate_docs:
                if doc.get('doc_id') == doc_id:
                    saved_filename = doc.get('saved_filename')
                    if saved_filename:
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        file_path = os.path.join(base_dir, 'uploads', 'hiddenprofiles', session_code, saved_filename)
                        if os.path.exists(file_path):
                            return send_from_directory(
                                os.path.dirname(file_path),
                                saved_filename,
                                as_attachment=False,
                                mimetype='application/pdf'
                            )
            
            return jsonify({"error": "Document not found"}), 404
            
    except Exception as e:
        logger.error(f"Error serving document: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Shape Factory Backend...")
    print("📡 MCP System: Integrated")
    print("🎮 Game Engine: Ready")
    print("=" * 50)
    
    # Run migrations to fix known issues
    print("🔧 Running database migrations...")
    run_migrations()
    print("=" * 50)
    
    socketio.run(app, host='0.0.0.0', port=5002, debug=True, allow_unsafe_werkzeug=True)
