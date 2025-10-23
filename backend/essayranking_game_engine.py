"""
Essay Ranking Research Platform - Game Engine
Core game logic and session management for essay ranking experiments
"""

import uuid
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
import logging
import secrets
import string
import random
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EssayRankingGameEngine:
    """Core game engine for Essay Ranking research platform"""
    
    def __init__(self, db_connection_string: str):
        """
        Initialize game engine with database connection
        
        Args:
            db_connection_string: PostgreSQL connection string
        """
        self.db_connection_string = db_connection_string
        
    def _get_db_connection(self):
        """Get database connection (creates new connection each time)"""
        try:
            connection = psycopg2.connect(
                self.db_connection_string,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            connection.autocommit = False
            return connection
        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
            
    def close_connection(self):
        """No-op for compatibility (connections are closed in finally blocks)"""
        pass
        
    def __enter__(self):
        """Context manager entry"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - no-op since we don't maintain persistent connections"""
        pass
    
    def _generate_session_code(self) -> str:
        """Generate unique human-readable session code"""
        # Generate 8-character alphanumeric code (avoiding confusing characters)
        alphabet = string.ascii_uppercase + string.digits
        excluded_chars = {'0', 'O', '1', 'I', 'L'}
        clean_alphabet = ''.join(c for c in alphabet if c not in excluded_chars)
        
        return ''.join(secrets.choice(clean_alphabet) for _ in range(8))
    
    def create_session(self, researcher_id: str, experiment_type: str = "essayranking", config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new essay ranking experimental session
        
        Args:
            researcher_id: Unique identifier for the researcher
            experiment_type: Type of experiment (should be 'essayranking')
            config: Optional configuration parameters for the session
            
        Returns:
            Dictionary containing session details and status
        """
        # Default configuration for essay ranking
        default_config = {
            'total_rounds': 1,  # Essay ranking is typically a single session
            'round_duration_minutes': 30,  # Longer duration for reading and ranking
            'first_round_duration_minutes': 30,
            'max_participants': 20,
            'assigned_essays': [],  # Will be populated when essays are uploaded (essay_id and title only)
            'ranking_criteria': {
                'clarity': 'How clear and well-structured is the essay?',
                'argument': 'How strong and logical is the argument?',
                'evidence': 'How well-supported is the argument with evidence?',
                'writing': 'How well-written is the essay overall?'
            },
            'allow_revision': True,  # Allow participants to revise rankings (always true)
            'show_peer_rankings': False  # Whether to show other participants' rankings
        }
        
        # Merge with provided config
        if config:
            default_config.update(config)
        
        conn = None
        cursor = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            # Generate unique session code
            session_code = self._generate_session_code()
            
            # Ensure session code is unique (retry if collision)
            max_retries = 10
            for attempt in range(max_retries):
                cursor.execute(
                    "SELECT COUNT(*) FROM sessions WHERE session_code = %s",
                    (session_code,)
                )
                if cursor.fetchone()['count'] == 0:
                    break
                session_code = self._generate_session_code()
            else:
                raise RuntimeError("Failed to generate unique session code after multiple attempts")
            
            # Create session record
            session_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO sessions (
                    session_id, session_code, experiment_type, researcher_id,
                    total_rounds, round_duration_minutes, first_round_duration_minutes,
                    max_participants, experiment_config, session_status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING session_id, created_at
            """, (
                session_id,
                session_code,
                experiment_type,
                researcher_id,
                default_config['total_rounds'],
                default_config['round_duration_minutes'],
                default_config['first_round_duration_minutes'],
                default_config['max_participants'],
                psycopg2.extras.Json(default_config),
                'idle'
            ))
            
            result = cursor.fetchone()
            conn.commit()
            
            session_details = {
                'session_id': result['session_id'],
                'session_code': session_code,
                'experiment_type': experiment_type,
                'researcher_id': researcher_id,
                'status': 'idle',
                'created_at': result['created_at'].isoformat(),
                'configuration': default_config,
                'participant_url': f"https://shapefactory.research.edu/participant?session={session_code}",
                'researcher_url': f"https://shapefactory.research.edu/researcher/session/{session_code}"
            }
            
            logger.info(f"Essay ranking session created successfully: {session_code} for researcher {researcher_id}")
            return session_details
            
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error creating session: {e}")
            raise
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Unexpected error creating session: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def setup_participants(self, session_id: str) -> Dict[str, Any]:
        """
        Set up participant roles and assignments for an essay ranking session
        
        Args:
            session_id: UUID of the session to set up participants for
            
        Returns:
            Dictionary containing participant assignments and session status
        """
        conn = None
        cursor = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            # Get session details and validate
            cursor.execute("""
                SELECT session_id, session_code, experiment_type, session_status, 
                       max_participants, experiment_config
                FROM sessions 
                WHERE session_id = %s
            """, (session_id,))
            
            session = cursor.fetchone()
            if not session:
                raise ValueError(f"Session not found: {session_id}")
            
            if session['session_status'] != 'idle':
                raise ValueError(f"Session {session['session_code']} is not in idle state (current: {session['session_status']})")
            
            # Check if participants already set up
            cursor.execute("SELECT COUNT(*) FROM participants WHERE session_id = %s", (session_id,))
            if cursor.fetchone()['count'] > 0:
                raise ValueError(f"Participants already set up for session {session['session_code']}")
            
            # Get configuration
            config = session['experiment_config'] or {}
            max_participants = session['max_participants']
            experiment_type = session['experiment_type']
            
            # For essay ranking, participants don't need specialty shapes or colors
            # They just need to be registered for the ranking task
            
            logger.info(f"Session {session['session_code']} is now ready for participant registration")
            logger.info(f"Experiment type: {experiment_type}")
            logger.info(f"Max participants: {max_participants}")
            
            # Update session status to setup_complete
            cursor.execute("""
                UPDATE sessions 
                SET session_status = 'setup_complete', setup_started_at = CURRENT_TIMESTAMP
                WHERE session_id = %s
            """, (session_id,))
            
            conn.commit()
            
            setup_result = {
                'session_id': session_id,
                'session_code': session['session_code'],
                'experiment_type': experiment_type,
                'status': 'setup_complete',
                'participants': [],
                'human_participants': [],
                'ai_participants': [],
                'total_participants': 0,
                'message': 'Session ready for participant registration. Participants will be added individually via the API.'
            }
            
            logger.info(f"Session {session['session_code']} setup complete. Ready for participant registration.")
            return setup_result
            
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error setting up participants: {e}")
            raise
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Unexpected error setting up participants: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def add_participant(self, session_code: str, participant_code: str) -> Dict[str, Any]:
        """
        Handle participant login and add them to the active essay ranking session
        
        Args:
            session_code: Human-readable session identifier (e.g., "A1B2C3D4")
            participant_code: Participant identifier (e.g., "human01", "agent03")
            
        Returns:
            Dictionary containing participant session information and game state
        """
        conn = None
        cursor = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            # Get session details
            cursor.execute("""
                SELECT session_id, session_code, experiment_type, session_status, 
                       max_participants, experiment_config
                FROM sessions 
                WHERE session_code = %s
            """, (session_code,))
            
            session = cursor.fetchone()
            if not session:
                raise ValueError(f"Session not found: {session_code}")
            
            # Validate session is in correct state for participant login
            if session['session_status'] != 'setup_complete':
                if session['session_status'] == 'idle':
                    raise ValueError(f"Session {session_code} is not set up yet. Researcher must set up participants first.")
                elif session['session_status'] == 'session_active':
                    raise ValueError(f"Session {session_code} has already started. No mid-session joins allowed.")
                elif session['session_status'] in {'session_paused', 'session_completed'}:
                    raise ValueError(f"Session {session_code} is no longer accepting participants (status: {session['session_status']}).")
                else:
                    raise ValueError(f"Session {session_code} is not ready for participants (status: {session['session_status']}).")
            
            # Find and validate participant
            cursor.execute("""
                SELECT participant_id, participant_code, participant_type, 
                       login_status, login_timestamp, last_activity_timestamp
                FROM participants 
                WHERE session_id = %s AND participant_code = %s
            """, (session['session_id'], participant_code))
            
            participant = cursor.fetchone()
            if not participant:
                raise ValueError(f"Participant '{participant_code}' not found in session {session_code}")
            
            # Check if already logged in
            if participant['login_status'] in {'logged_in', 'active'}:
                if participant['participant_type'] == 'human':
                    raise ValueError(f"Participant {participant_code} is already logged in")
                else:
                    # AI agent reconnection - update activity timestamp
                    cursor.execute("""
                        UPDATE participants 
                        SET last_activity_timestamp = CURRENT_TIMESTAMP
                        WHERE participant_id = %s
                    """, (participant['participant_id'],))
                    conn.commit()
                    
                    logger.info(f"AI agent {participant_code} reconnected to session {session_code}")
            else:
                # First login - update status and timestamps
                cursor.execute("""
                    UPDATE participants 
                    SET login_status = 'logged_in',
                        login_timestamp = CURRENT_TIMESTAMP,
                        last_activity_timestamp = CURRENT_TIMESTAMP
                    WHERE participant_id = %s
                """, (participant['participant_id'],))
                
                logger.info(f"Participant {participant_code} ({participant['participant_type']}) logged into session {session_code}")
            
            # Get current session participant counts
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_participants,
                    SUM(CASE WHEN login_status IN ('logged_in', 'active') THEN 1 ELSE 0 END) as logged_in_count,
                    SUM(CASE WHEN participant_type = 'human' AND login_status IN ('logged_in', 'active') THEN 1 ELSE 0 END) as humans_logged_in,
                    SUM(CASE WHEN participant_type = 'ai_agent' AND login_status IN ('logged_in', 'active') THEN 1 ELSE 0 END) as agents_logged_in
                FROM participants 
                WHERE session_id = %s
            """, (session['session_id'],))
            
            counts = cursor.fetchone()
            
            # Game state is always None during setup phase (session not started yet)
            game_state = None
            
            # Get other participants (for potential collaboration awareness)
            cursor.execute("""
                SELECT participant_code, participant_type, login_status
                FROM participants 
                WHERE session_id = %s AND participant_id != %s
                ORDER BY participant_code
            """, (session['session_id'], participant['participant_id']))
            
            other_participants = cursor.fetchall()
            
            conn.commit()
            
            # Prepare response
            login_result = {
                'session_info': {
                    'session_id': session['session_id'],
                    'session_code': session_code,
                    'experiment_type': session['experiment_type'],
                    'session_status': session['session_status']
                },
                'participant_info': {
                    'participant_id': participant['participant_id'],
                    'participant_code': participant_code,
                    'participant_type': participant['participant_type'],
                    'login_status': 'logged_in',
                    'login_timestamp': datetime.now(timezone.utc).isoformat()
                },
                'session_status': {
                    'total_participants': counts['total_participants'],
                    'logged_in_count': counts['logged_in_count'],
                    'humans_logged_in': counts['humans_logged_in'],
                    'agents_logged_in': counts['agents_logged_in'],
                    'ready_to_start': counts['logged_in_count'] >= session['max_participants']
                },
                'other_participants': [
                    {
                        'participant_code': p['participant_code'],
                        'participant_type': p['participant_type'],
                        'is_online': p['login_status'] in {'logged_in', 'active'}
                    }
                    for p in other_participants
                ],
                'game_state': game_state,
                'configuration': session['experiment_config']
            }
            
            return login_result
            
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error adding participant: {e}")
            raise
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Unexpected error adding participant: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_participant_state(self, participant_code: str, session_code: str = None) -> Dict[str, Any]:
        """Get private state for a specific participant in essay ranking"""
        conn = None
        cur = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            if not session_code:
                logger.error(f"Session isolation error: get_participant_state called for {participant_code} without session_code")
                return {
                    "current_rankings": [],
                    "submitted_rankings_count": 0,
                    "error": "Session isolation error: session_code required"
                }
            
            logger.info(f"Getting participant state for {participant_code} in session {session_code}")
            cur.execute("""
                SELECT p.participant_id, p.participant_code, p.login_status, p.session_id, 
                       p.current_rankings, p.submitted_rankings_count,
                       s.experiment_type
                FROM participants p
                JOIN sessions s ON p.session_id = s.session_id
                WHERE p.participant_code = %s AND p.session_code = %s
            """, (participant_code, session_code))
            
            participant = cur.fetchone()
            if not participant:
                logger.warning(f"Participant {participant_code} not found in session {session_code}")
                return {
                    "current_rankings": [],
                    "submitted_rankings_count": 0
                }
            
            # Parse current rankings from JSONB
            current_rankings = []
            if participant['current_rankings']:
                try:
                    if isinstance(participant['current_rankings'], str):
                        current_rankings = json.loads(participant['current_rankings'])
                    elif isinstance(participant['current_rankings'], list):
                        current_rankings = participant['current_rankings']
                    else:
                        current_rankings = list(participant['current_rankings'])
                except (json.JSONDecodeError, TypeError):
                    current_rankings = []
            
            return {
                "current_rankings": current_rankings,
                "submitted_rankings_count": participant.get('submitted_rankings_count', 0) or 0,
                "experiment_type": participant.get('experiment_type')
            }
            
        except Exception as e:
            logger.error(f"Error getting participant state: {e}")
            return {
                "current_rankings": [],
                "submitted_rankings_count": 0
            }
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def get_public_state(self, session_code: str = None) -> Dict[str, Any]:
        """Get public game state for essay ranking"""
        if not session_code:
            return {
                "session_status": "inactive",
                "participants": [],
                "timer_info": {
                    "time_remaining": 0,
                    "experiment_status": "idle",
                    "round_duration_minutes": 30
                }
            }
        
        conn = None
        cur = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Get session config and experiment type
            cur.execute("""
                SELECT experiment_config, experiment_type FROM sessions WHERE session_code = %s
            """, (session_code,))
            session_row = cur.fetchone()
            session_config = session_row['experiment_config'] if session_row and session_row['experiment_config'] else {}
            experiment_type = session_row['experiment_type'] if session_row else None
            
            # Get other participants with basic info
            cur.execute("""
                SELECT participant_code, participant_type, login_status
                FROM participants 
                WHERE session_code = %s
            """, (session_code,))
            
            other_participants = cur.fetchall()
            
            # Format participant data
            participants_data = []
            for p in other_participants:
                # For AI agents, extract the original name (remove session code suffix)
                display_name = p['participant_code']
                if '_' in p['participant_code']:
                    display_name = p['participant_code'].rsplit('_', 1)[0]
                
                participant_data = {
                    "participant_code": display_name,
                    "internal_participant_code": p['participant_code'],
                    "status": p['login_status']
                }
                
                participants_data.append(participant_data)
            
            # Get timer state from session-specific timer_state
            try:
                import sys
                app_module = sys.modules.get('app')
                if app_module and hasattr(app_module, 'get_timer_state'):
                    get_timer_state_func = app_module.get_timer_state
                    session_timer_state = get_timer_state_func(session_code)
                    timer_info = {
                        "time_remaining": session_timer_state.get('time_remaining', 0),
                        "experiment_status": session_timer_state.get('experiment_status', 'idle'),
                        "round_duration_minutes": session_timer_state.get('round_duration_minutes', 30)
                    }
                else:
                    timer_info = {
                        "time_remaining": 0,
                        "experiment_status": "idle",
                        "round_duration_minutes": 30
                    }
            except Exception as e:
                timer_info = {
                    "time_remaining": 0,
                    "experiment_status": "idle",
                    "round_duration_minutes": 30
                }
            
            return {
                "session_status": "active",
                "session_code": session_code,
                "other_participants": participants_data,
                "experiment_config": session_config,
                "experiment_type": experiment_type,
                "experiment_status_description": "Rank essays consistently using rubric-aligned criteria.",
                **timer_info
            }
            
        except Exception as e:
            logger.error(f"Error getting public state: {e}")
            return {
                "session_status": "error",
                "other_participants": [],
                "time_remaining": 0,
                "experiment_status": "idle",
                "round_duration_minutes": 30
            }
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def submit_ranking(self, participant_code: str, rankings: List[Dict[str, Any]], session_code: str = None) -> Dict[str, Any]:
        """Submit essay rankings for a participant (ranking only, no scores required)"""
        conn = None
        cur = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            if not session_code:
                logger.error(f"Session isolation error: submit_ranking called for {participant_code} without session_code")
                return {
                    "success": False,
                    "error": "Session isolation error: session_code required"
                }
            
            # Validate rankings format first (ranking only - essay_id and rank required)
            if not isinstance(rankings, list):
                raise ValueError("Rankings must be a list")
            
            # Validate each ranking entry has required fields
            for ranking in rankings:
                if not isinstance(ranking, dict):
                    raise ValueError("Each ranking must be a dictionary")
                if 'essay_id' not in ranking:
                    raise ValueError("Each ranking must have an 'essay_id' field")
                if 'rank' not in ranking:
                    raise ValueError("Each ranking must have a 'rank' field")
                # Score is optional - not required
            
            # Get participant info with session filtering
            cur.execute("""
                SELECT participant_id, session_id, current_rankings, submitted_rankings_count
                FROM participants 
                WHERE participant_code = %s AND session_code = %s
            """, (participant_code, session_code))
            
            participant = cur.fetchone()
            if not participant:
                logger.warning(f"Participant {participant_code} not found in session {session_code}")
                return {
                    "success": False,
                    "error": f"Participant {participant_code} not found in session {session_code}"
                }
            
            # Store the ranking submission (allow multiple submissions for adjustments)
            submission_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO ranking_submissions (
                    submission_id, session_id, participant_id, essay_rankings,
                    submission_timestamp
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                submission_id, participant['session_id'], participant['participant_id'],
                json.dumps(rankings), datetime.now(timezone.utc)
            ))
            
            # Get current rankings and merge with new ones
            current_rankings = []
            if participant['current_rankings']:
                try:
                    if isinstance(participant['current_rankings'], str):
                        current_rankings = json.loads(participant['current_rankings'])
                    elif isinstance(participant['current_rankings'], list):
                        current_rankings = participant['current_rankings']
                    else:
                        current_rankings = list(participant['current_rankings'])
                except (json.JSONDecodeError, TypeError):
                    current_rankings = []
            
            # Merge new rankings with existing ones
            # Remove any existing rankings for essays that are being re-ranked
            essay_ids_to_update = {r['essay_id'] for r in rankings}
            updated_rankings = [r for r in current_rankings if r['essay_id'] not in essay_ids_to_update]
            
            # Add the new rankings
            updated_rankings.extend(rankings)
            
            # Update participant's current rankings and submission count
            cur.execute("""
                UPDATE participants 
                SET current_rankings = %s, submitted_rankings_count = submitted_rankings_count + 1
                WHERE participant_code = %s AND session_code = %s
            """, (json.dumps(updated_rankings), participant_code, session_code))
            
            conn.commit()
            
            logger.info(f"Ranking submitted by {participant_code}: {len(rankings)} essays ranked")
            
            return {
                "success": True,
                "message": f"Successfully submitted rankings for {len(rankings)} essays (ranking only)",
                "submission_id": submission_id,
                "rankings_count": len(rankings)
            }
            
        except Exception as e:
            logger.error(f"Error submitting ranking: {e}")
            if conn:
                conn.rollback()
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def get_assigned_essays(self, session_code: str) -> List[Dict[str, Any]]:
        """Get essays assigned to a session with content"""
        conn = None
        cur = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT essay_id, essay_title, essay_filename, essay_content, essay_metadata
                FROM essay_assignments 
                WHERE session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
                ORDER BY essay_id
            """, (session_code,))
            
            essays = cur.fetchall()
            
            result = []
            for essay in essays:
                essay_data = {
                    "essay_id": essay['essay_id'],
                    "title": essay['essay_title'],
                    "filename": essay['essay_filename'],
                    "content": essay['essay_content'],
                    "has_content": bool(essay['essay_content'] and essay['essay_content'].strip())
                }
                
                # Parse metadata if available
                if essay['essay_metadata']:
                    try:
                        metadata = json.loads(essay['essay_metadata']) if isinstance(essay['essay_metadata'], str) else essay['essay_metadata']
                        essay_data.update({
                            "word_count": metadata.get("word_count", 0),
                            "character_count": metadata.get("character_count", 0),
                            "estimated_reading_time_minutes": metadata.get("estimated_reading_time_minutes", 1),
                            "extraction_successful": metadata.get("extraction_successful", False)
                        })
                    except (json.JSONDecodeError, TypeError):
                        essay_data["extraction_successful"] = False
                else:
                    essay_data["extraction_successful"] = False
                
                result.append(essay_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting assigned essays: {e}")
            return []
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def assign_essays(self, session_code: str, essays: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assign essays to a session with PDF text extraction"""
        conn = None
        cur = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Get session_id
            cur.execute("SELECT session_id FROM sessions WHERE session_code = %s", (session_code,))
            session_result = cur.fetchone()
            if not session_result:
                raise ValueError(f"Session {session_code} not found")
            
            session_id = session_result['session_id']
            
            # Clear existing essays for this session
            cur.execute("DELETE FROM essay_assignments WHERE session_id = %s", (session_id,))
            
            # Import PDF utilities
            from pdf_utils import extract_text_from_pdf, validate_essay_content
            
            # Insert new essays with content extraction
            assigned_count = 0
            extraction_errors = []
            
            for essay in essays:
                essay_id = essay['essay_id']
                essay_title = essay.get('title', '')
                essay_filename = essay.get('filename', '')
                essay_file = essay.get('file')  # File object or bytes
                
                # Extract text content from PDF if available
                essay_content = None
                essay_metadata = {}
                
                if essay_file:
                    try:
                        # Extract text from PDF
                        essay_content = extract_text_from_pdf(essay_file)
                        
                        if essay_content:
                            # Validate and analyze content
                            validation_result = validate_essay_content(essay_content)
                            essay_metadata = {
                                "word_count": validation_result.get("word_count", 0),
                                "character_count": validation_result.get("character_count", 0),
                                "estimated_reading_time_minutes": validation_result.get("estimated_reading_time_minutes", 1),
                                "extraction_successful": True
                            }
                            
                            if not validation_result.get("valid", False):
                                extraction_errors.append(f"Essay {essay_id}: {validation_result.get('error', 'Validation failed')}")
                        else:
                            essay_content = None  # Ensure content is None if extraction failed
                            essay_metadata = {
                                "extraction_successful": False,
                                "error": "Failed to extract text from PDF"
                            }
                            extraction_errors.append(f"Essay {essay_id}: Failed to extract text from PDF")
                            
                    except Exception as e:
                        # Log the error but don't fail the entire operation
                        logger.error(f"PDF extraction failed for essay {essay_id}: {str(e)}")
                        essay_content = None  # Ensure content is None if extraction failed
                        essay_metadata = {
                            "extraction_successful": False,
                            "error": str(e)
                        }
                        extraction_errors.append(f"Essay {essay_id}: PDF extraction error - {str(e)}")
                else:
                    essay_content = None
                    essay_metadata = {
                        "extraction_successful": False,
                        "error": "No PDF file provided"
                    }
                    extraction_errors.append(f"Essay {essay_id}: No PDF file provided")
                
                # Insert essay with content
                cur.execute("""
                    INSERT INTO essay_assignments (
                        session_id, essay_id, essay_title, essay_filename, 
                        essay_content, essay_metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    session_id, essay_id, essay_title, essay_filename,
                    essay_content, json.dumps(essay_metadata) if essay_metadata else None
                ))
                assigned_count += 1
            
            conn.commit()
            
            logger.info(f"Assigned {assigned_count} essays to session {session_code}")
            if extraction_errors:
                logger.warning(f"PDF extraction errors: {extraction_errors}")
            
            result = {
                "success": True,
                "message": f"Successfully assigned {assigned_count} essays",
                "essays_assigned": assigned_count
            }
            
            if extraction_errors:
                result["warnings"] = extraction_errors
                result["message"] += f" (with {len(extraction_errors)} extraction warnings)"
            
            return result
            
        except Exception as e:
            logger.error(f"Error assigning essays: {e}")
            if conn:
                conn.rollback()
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def end_session(self, session_code: str) -> Dict[str, Any]:
        """End an essay ranking session and clean up data"""
        conn = None
        cur = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Get session_id
            cur.execute("SELECT session_id FROM sessions WHERE session_code = %s", (session_code,))
            session_result = cur.fetchone()
            if not session_result:
                return {
                    "success": False,
                    "error": f"Session {session_code} not found"
                }
            
            session_id = session_result['session_id']
            
            # Clear essay assignments
            cur.execute("DELETE FROM essay_assignments WHERE session_id = %s", (session_id,))
            
            # Clear ranking submissions
            cur.execute("DELETE FROM ranking_submissions WHERE session_id = %s", (session_id,))
            
            # Reset participant essay ranking data
            cur.execute("""
                UPDATE participants 
                SET current_rankings = NULL,
                    submitted_rankings_count = 0
                WHERE session_id = %s
            """, (session_id,))
            
            # Update session status to completed
            cur.execute("""
                UPDATE sessions 
                SET session_status = 'session_completed',
                    session_ended_at = CURRENT_TIMESTAMP
                WHERE session_id = %s
            """, (session_id,))
            
            conn.commit()
            
            logger.info(f"Essay ranking session {session_code} ended successfully")
            
            return {
                "success": True,
                "message": f"Session {session_code} ended successfully",
                "session_code": session_code
            }
            
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            if conn:
                conn.rollback()
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

# Example usage and testing
if __name__ == "__main__":
    # This section is for testing the function
    # In production, this would be called from the web API
    
    # Example database connection string (adjust for your setup)
    DB_CONNECTION = "postgresql://username:password@localhost:5432/shapefactory"
    
    # Use context manager to ensure proper resource cleanup
    try:
        with EssayRankingGameEngine(DB_CONNECTION) as engine:
            # Test session creation
            session = engine.create_session(
                researcher_id="test_researcher_001",
                experiment_type="essayranking",
                config={
                    'total_rounds': 1,
                    'round_duration_minutes': 30,
                    'max_participants': 10
                }
            )
            
            print("Essay ranking session created successfully:")
            print(f"Session Code: {session['session_code']}")
            print(f"Session ID: {session['session_id']}")
            print(f"Participant URL: {session['participant_url']}")
            print(f"Researcher URL: {session['researcher_url']}")
        # Connection automatically closed when exiting context manager
        
    except Exception as e:
        print(f"Error: {e}")
