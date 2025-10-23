"""
WordGuessing Research Platform - Game Engine
Core game logic and session management for wordguessing experiments
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

class WordGuessingGameEngine:
    """Core game engine for WordGuessing research platform"""
    
    def __init__(self, db_connection_string: str):
        """
        Initialize game engine with database connection
        
        Args:
            db_connection_string: PostgreSQL connection string
        """
        self.db_connection_string = db_connection_string
        
    def _get_db_connection(self):
        """Get database connection using the connection pool"""
        # Import here to avoid circular imports
        from app import get_db_connection
        return get_db_connection()
        
    def close_connection(self):
        """Close database connection - not needed with connection pool"""
        pass  # Connection pool handles connection lifecycle
        
    def __enter__(self):
        """Context manager entry"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed"""
        self.close_connection()
    
    def _generate_session_code(self) -> str:
        """Generate unique human-readable session code"""
        # Generate 8-character alphanumeric code (avoiding confusing characters)
        alphabet = string.ascii_uppercase + string.digits
        excluded_chars = {'0', 'O', '1', 'I', 'L'}
        clean_alphabet = ''.join(c for c in alphabet if c not in excluded_chars)
        
        return ''.join(secrets.choice(clean_alphabet) for _ in range(8))
    
    def create_session(self, researcher_id: str, experiment_type: str = "wordguessing", config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new wordguessing experimental session
        
        Args:
            researcher_id: Unique identifier for the researcher
            experiment_type: Type of experiment (should be 'wordguessing')
            config: Optional configuration parameters for the session
            
        Returns:
            Dictionary containing session details and status
        """
        # Default configuration for wordguessing
        default_config = {
            'total_rounds': 5,  # Number of guessing rounds
            'round_duration_minutes': 10,  # Duration per round
            'first_round_duration_minutes': 10,
            'max_participants': 8,
            'word_list': [],  # Will be populated when words are uploaded
            'max_guesses_per_round': 10,  # Maximum guesses per round
            'hint_provided': False,  # Whether hints are provided
            'show_previous_rounds': True  # Whether to show results from previous rounds
        }
        
        # Merge with provided config
        if config:
            default_config.update(config)
        
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Generate session code
            session_code = self._generate_session_code()
            
            # Insert session
            cur.execute("""
                INSERT INTO sessions (
                    session_code, experiment_type, researcher_id, 
                    total_rounds, round_duration_minutes, first_round_duration_minutes,
                    max_participants, experiment_config, session_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING session_id
            """, (
                session_code, experiment_type, researcher_id,
                default_config["total_rounds"], 
                default_config["round_duration_minutes"],
                default_config["first_round_duration_minutes"],
                default_config["max_participants"],
                json.dumps(default_config), "idle"
            ))
            
            session_id = cur.fetchone()["session_id"]
            conn.commit()
            
            logger.info(f"Created wordguessing session {session_code} with ID {session_id}")
            
            return {
                "success": True,
                "session_id": str(session_id),
                "session_code": session_code,
                "message": f"WordGuessing session {session_code} created successfully"
            }
                
        except Exception as e:
            logger.error(f"Failed to create wordguessing session: {e}")
            return {
                "success": False,
                "message": f"Failed to create WordGuessing session: {str(e)}"
            }
        finally:
            # Ensure proper cleanup
            try:
                if 'cur' in locals():
                    cur.close()
                if 'conn' in locals():
                    conn.close()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
    
    def add_participant(self, session_code: str, participant_code: str, participant_type: str = "human", 
                       role: str = None, assigned_words: List[str] = None) -> Dict[str, Any]:
        """
        Add a participant to the wordguessing session
        
        Args:
            session_code: Session code to add participant to
            participant_code: Unique participant identifier
            participant_type: Type of participant (human/ai_agent)
            role: Role in the game (guesser/hinter)
            assigned_words: Words assigned to hinter (if role is hinter)
            
        Returns:
            Dictionary containing participant details and status
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Get session details
            cur.execute("""
                SELECT session_id, max_participants, experiment_config
                FROM sessions 
                WHERE session_code = %s
            """, (session_code,))
            
            session_data = cur.fetchone()
            if not session_data:
                return {"success": False, "message": "Session not found"}
            
            session_id = session_data["session_id"]
            max_participants = session_data["max_participants"]
            experiment_config = session_data["experiment_config"]
            
            # Check current participant count
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM participants 
                WHERE session_code = %s
            """, (session_code,))
            
            current_count = cur.fetchone()["count"]
            if current_count >= max_participants:
                return {"success": False, "message": "Session is full"}
            
            # Check if participant already exists
            cur.execute("""
                SELECT participant_id 
                FROM participants 
                WHERE session_code = %s AND participant_code = %s
            """, (session_code, participant_code))
            
            if cur.fetchone():
                return {"success": False, "message": "Participant already exists"}
            
            # For wordguessing, use simple participant code as display name
            color_shape_combination = participant_code
            
            # Auto-assign role if not specified
            if not role:
                # Count existing roles to balance
                cur.execute("""
                    SELECT role, COUNT(*) as count 
                    FROM participants 
                    WHERE session_code = %s AND role IS NOT NULL
                    GROUP BY role
                """, (session_code,))
                
                role_counts = {row["role"]: row["count"] for row in cur.fetchall()}
                guesser_count = role_counts.get("guesser", 0)
                hinter_count = role_counts.get("hinter", 0)
                
                if hinter_count < guesser_count:
                    role = "hinter"
                else:
                    role = "guesser"
            
            # Insert participant
            cur.execute("""
                INSERT INTO participants (
                    session_id, session_code, participant_code, participant_type,
                    color_shape_combination, specialty_shape, role, current_round, score,
                    assigned_words, login_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING participant_id
            """, (
                session_id, session_code, participant_code, participant_type,
                color_shape_combination, "N/A", role, 1, 0,
                json.dumps(assigned_words or []), "not_logged_in"
            ))
            
            participant_id = cur.fetchone()["participant_id"]
            conn.commit()
            
            logger.info(f"Added participant {participant_code} to session {session_code} with role {role}")
            
            return {
                "success": True,
                "participant_id": str(participant_id),
                "participant_code": participant_code,
                "role": role,
                "color_shape_combination": color_shape_combination,
                "message": f"Participant {participant_code} added successfully"
            }
                
        except Exception as e:
            logger.error(f"Failed to add participant to wordguessing session: {e}")
            return {
                "success": False,
                "message": f"Failed to add participant: {str(e)}"
            }
        finally:
            # Ensure proper cleanup
            try:
                if 'cur' in locals():
                    cur.close()
                if 'conn' in locals():
                    conn.close()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
    
    def get_participant_state(self, participant_code: str, session_code: str = None) -> Dict[str, Any]:
        """
        Get current state for a wordguessing participant
        
        Args:
            participant_code: Participant identifier
            session_code: Session code (optional)
            
        Returns:
            Dictionary containing participant state
        """
        try:
            import psycopg2.extras
            conn = self._get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Build query based on whether session_code is provided
            if session_code:
                cur.execute("""
                    SELECT p.*, s.session_status, s.experiment_config, s.round_duration_minutes
                    FROM participants p
                    JOIN sessions s ON p.session_id = s.session_id
                    WHERE p.participant_code = %s AND p.session_code = %s
                """, (participant_code, session_code))
            else:
                cur.execute("""
                    SELECT p.*, s.session_status, s.experiment_config, s.round_duration_minutes
                    FROM participants p
                    JOIN sessions s ON p.session_id = s.session_id
                    WHERE p.participant_code = %s
                """, (participant_code,))
            
            participant_data = cur.fetchone()
            if not participant_data:
                return {"success": False, "message": "Participant not found"}
            
            # Get chat history for the participant
            cur.execute("""
                SELECT guess_text, is_correct, timestamp, round_number
                FROM wordguessing_chat_history
                WHERE participant_id = %s
                ORDER BY timestamp DESC
                LIMIT 50
            """, (participant_data["participant_id"],))
            
            chat_history = []
            for row in cur.fetchall():
                chat_history.append({
                    "guess": row["guess_text"],
                    "correct": row["is_correct"],
                    "timestamp": row["timestamp"].isoformat(),
                    "round": row["round_number"]
                })
            
            # Get other participants in the session
            cur.execute("""
                SELECT participant_code, role, 
                       login_status, current_round, score
                FROM participants
                WHERE session_code = %s AND participant_code != %s
                ORDER BY participant_code
            """, (participant_data["session_code"], participant_code))
            
            other_participants = []
            for row in cur.fetchall():
                other_participants.append({
                    "participant_code": row["participant_code"],
                    "display_name": row["participant_code"],  # Use participant_code as display name
                    "role": row["role"],
                    "status": row["login_status"],
                    "current_round": row["current_round"],
                    "score": row["score"]
                })
            
            # Get unread messages
            cur.execute("""
                SELECT m.message_id, m.sender_id, m.recipient_id, m.message_content,
                       m.message_timestamp, m.delivered_status, p.participant_code as sender_code
                FROM messages m
                JOIN participants p ON m.sender_id = p.participant_id
                WHERE m.recipient_id = %s AND m.delivered_status != 'read'
                ORDER BY m.message_timestamp DESC
            """, (participant_data["participant_id"],))
            
            unread_messages = []
            for row in cur.fetchall():
                unread_messages.append({
                    "message_id": str(row["message_id"]),
                    "sender_code": row["sender_code"],
                    "recipient_code": participant_code,
                    "content": row["message_content"],
                    "timestamp": row["message_timestamp"].isoformat(),
                    "delivered_status": row["delivered_status"],
                    "message_type": "chat"
                })
            
            # Parse experiment config
            experiment_config = participant_data["experiment_config"] or {}
            if isinstance(experiment_config, str):
                experiment_config = json.loads(experiment_config)
            
            # Parse assigned_words if it's a JSON string
            assigned_words = participant_data["assigned_words"] or []
            if isinstance(assigned_words, str):
                try:
                    assigned_words = json.loads(assigned_words)
                except (json.JSONDecodeError, TypeError):
                    assigned_words = []
            
            return {
                    "success": True,
                    "participant": {
                        "participant_code": participant_data["participant_code"],
                        "role": participant_data["role"],
                        "current_round": participant_data["current_round"],
                        "score": participant_data["score"],
                        "assigned_words": assigned_words
                    },
                    "session": {
                        "session_code": participant_data["session_code"],
                        "experiment_status": participant_data["session_status"],
                        "time_remaining": experiment_config.get("round_duration_minutes", 10),
                        "round_duration_minutes": participant_data["round_duration_minutes"],
                        "experiment_config": experiment_config
                    },
                    "chat_history": chat_history,
                    "other_participants": other_participants,
                    "unread_messages": unread_messages
                }
                
        except Exception as e:
            logger.error(f"Failed to get wordguessing participant state: {e}")
            return {
                "success": False,
                "message": f"Failed to get participant state: {str(e)}"
            }
        finally:
            # Ensure proper cleanup
            try:
                if 'cur' in locals():
                    cur.close()
                if 'conn' in locals():
                    conn.close()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
    
    def get_public_state(self, session_code: str = None) -> Dict[str, Any]:
        """
        Get public state for wordguessing session
        
        Args:
            session_code: Session code
            
        Returns:
            Dictionary containing public session state
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT s.*, COUNT(p.participant_id) as participant_count
                FROM sessions s
                LEFT JOIN participants p ON s.session_id = p.session_id
                WHERE s.session_code = %s
                GROUP BY s.session_id
            """, (session_code,))
            
            session_data = cur.fetchone()
            if not session_data:
                return {"success": False, "message": "Session not found"}
            
            # Parse experiment config
            experiment_config = session_data["experiment_config"] or {}
            if isinstance(experiment_config, str):
                experiment_config = json.loads(experiment_config)
            
            # Get all participants
            cur.execute("""
                SELECT participant_code, role, 
                       login_status, current_round, score
                FROM participants
                WHERE session_code = %s
                ORDER BY participant_code
            """, (session_code,))
            
            participants = []
            for row in cur.fetchall():
                participants.append({
                    "participant_code": row["participant_code"],
                    "display_name": row["participant_code"],  # Use participant_code as display name
                    "role": row["role"],
                    "status": row["login_status"],
                    "current_round": row["current_round"],
                    "score": row["score"]
                })
            
            return {
                "success": True,
                "session": {
                    "session_code": session_data["session_code"],
                    "experiment_status": session_data["session_status"],
                    "time_remaining": experiment_config.get("round_duration_minutes", 10),
                    "round_duration_minutes": session_data["round_duration_minutes"],
                    "experiment_config": experiment_config,
                    "participant_count": session_data["participant_count"]
                },
                "other_participants": participants
            }
                
        except Exception as e:
            logger.error(f"Failed to get wordguessing public state: {e}")
            return {
                "success": False,
                "message": f"Failed to get public state: {str(e)}"
            }
        finally:
            # Ensure proper cleanup
            try:
                if 'cur' in locals():
                    cur.close()
                if 'conn' in locals():
                    conn.close()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
    
    def submit_guess(self, participant_code: str, guess_text: str, session_code: str = None) -> Dict[str, Any]:
        """
        Submit a guess in the wordguessing game
        
        Args:
            participant_code: Participant making the guess
            guess_text: The guess text
            session_code: Session code
            
        Returns:
            Dictionary containing guess result
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Get participant data
            if session_code:
                cur.execute("""
                    SELECT participant_id, role, current_round, assigned_words, session_code
                    FROM participants
                    WHERE participant_code = %s AND session_code = %s
                """, (participant_code, session_code))
            else:
                cur.execute("""
                    SELECT participant_id, role, current_round, assigned_words, session_code
                    FROM participants
                    WHERE participant_code = %s
                """, (participant_code,))
            
            participant_data = cur.fetchone()
            if not participant_data:
                return {"success": False, "message": "Participant not found"}
            
            # Only guessers can submit guesses
            if participant_data["role"] != "guesser":
                return {"success": False, "message": "Only guessers can submit guesses"}
            
            # Get current word for the round (from hinters' assigned words)
            cur.execute("""
                SELECT assigned_words
                FROM participants
                WHERE session_code = %s AND role = 'hinter'
                LIMIT 1
            """, (participant_data["session_code"],))
            
            hinter_data = cur.fetchone()
            if not hinter_data:
                return {"success": False, "message": "No hinter found for current round"}
            
            assigned_words = hinter_data["assigned_words"]
            if isinstance(assigned_words, str):
                assigned_words = json.loads(assigned_words)
            
            # Check if guess is correct (simple text matching for now)
            current_word = assigned_words[participant_data["current_round"] - 1] if assigned_words else ""
            is_correct = guess_text.lower().strip() == current_word.lower().strip()
            
            # Insert guess into chat history
            cur.execute("""
                INSERT INTO wordguessing_chat_history (
                    session_id, participant_id, guess_text, is_correct, round_number
                ) VALUES (
                    (SELECT session_id FROM participants WHERE participant_code = %s AND session_code = %s),
                    %s, %s, %s, %s
                )
            """, (participant_code, participant_data["session_code"], participant_data["participant_id"], 
                 guess_text, is_correct, participant_data["current_round"]))
            
            # Update score if correct
            if is_correct:
                cur.execute("""
                    UPDATE participants 
                    SET score = score + 1
                    WHERE participant_code = %s
                """, (participant_code,))
            
            conn.commit()
            
            # Get updated score
            cur.execute("""
                SELECT score FROM participants 
                WHERE participant_code = %s
            """, (participant_code,))
            
            updated_score = cur.fetchone()["score"]
            
            return {
                "success": True,
                "guess": guess_text,
                "correct": is_correct,
                "score": updated_score,
                "message": "Guess submitted successfully"
            }
                
        except Exception as e:
            logger.error(f"Failed to submit wordguessing guess: {e}")
            return {
                "success": False,
                "message": f"Failed to submit guess: {str(e)}"
            }
        finally:
            # Ensure proper cleanup
            try:
                if 'cur' in locals():
                    cur.close()
                if 'conn' in locals():
                    conn.close()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
    
    def send_message(self, participant_code: str, recipient_code: str, content: str, session_code: str = None) -> Dict[str, Any]:
        """
        Send a message in wordguessing session
        
        Args:
            participant_code: Sender participant code
            recipient_code: Recipient participant code (or None for broadcast)
            content: Message content
            session_code: Session code
            
        Returns:
            Dictionary containing message status
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Get sender participant
            if session_code:
                cur.execute("""
                    SELECT participant_id, session_id, session_code
                    FROM participants
                    WHERE participant_code = %s AND session_code = %s
                """, (participant_code, session_code))
            else:
                cur.execute("""
                    SELECT participant_id, session_id, session_code
                    FROM participants
                    WHERE participant_code = %s
                """, (participant_code,))
            
            sender_data = cur.fetchone()
            if not sender_data:
                return {"success": False, "message": "Sender not found"}
            
            recipient_id = None
            if recipient_code:
                cur.execute("""
                    SELECT participant_id
                    FROM participants
                    WHERE participant_code = %s AND session_code = %s
                """, (recipient_code, sender_data["session_code"]))
                
                recipient_data = cur.fetchone()
                if recipient_data:
                    recipient_id = recipient_data["participant_id"]
            
            # Insert message
            cur.execute("""
                INSERT INTO messages (
                    session_id, sender_id, recipient_id, message_type,
                    message_content, delivered_status
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING message_id
            """, (
                sender_data["session_id"], sender_data["participant_id"],
                recipient_id, "chat", content, "sent"
            ))
            
            message_id = cur.fetchone()["message_id"]
            conn.commit()
            
            return {
                "success": True,
                "message_id": str(message_id),
                "message": "Message sent successfully"
            }
                
        except Exception as e:
            logger.error(f"Failed to send wordguessing message: {e}")
            return {
                "success": False,
                "message": f"Failed to send message: {str(e)}"
            }
        finally:
            # Ensure proper cleanup
            try:
                if 'cur' in locals():
                    cur.close()
                if 'conn' in locals():
                    conn.close()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
    
    def start_session(self, session_code: str) -> Dict[str, Any]:
        """
        Start the wordguessing session
        
        Args:
            session_code: Session code to start
            
        Returns:
            Dictionary containing session status
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Update session status
            cur.execute("""
                UPDATE sessions 
                SET session_status = 'session_active',
                    session_started_at = CURRENT_TIMESTAMP
                WHERE session_code = %s
                RETURNING session_id
            """, (session_code,))
            
            session_data = cur.fetchone()
            if not session_data:
                return {"success": False, "message": "Session not found"}
            
            conn.commit()
            
            return {
                "success": True,
                "message": f"WordGuessing session {session_code} started successfully"
            }
                
        except Exception as e:
            logger.error(f"Failed to start wordguessing session: {e}")
            return {
                "success": False,
                "message": f"Failed to start session: {str(e)}"
            }
        finally:
            # Ensure proper cleanup
            try:
                if 'cur' in locals():
                    cur.close()
                if 'conn' in locals():
                    conn.close()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
    
    def end_session(self, session_code: str) -> Dict[str, Any]:
        """
        End the wordguessing session
        
        Args:
            session_code: Session code to end
            
        Returns:
            Dictionary containing session status
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Update session status
            cur.execute("""
                UPDATE sessions 
                SET session_status = 'session_completed',
                    session_completed_at = CURRENT_TIMESTAMP
                WHERE session_code = %s
                RETURNING session_id
            """, (session_code,))
            
            session_data = cur.fetchone()
            if not session_data:
                return {"success": False, "message": "Session not found"}
            
            conn.commit()
            
            return {
                "success": True,
                "message": f"WordGuessing session {session_code} ended successfully"
            }
                
        except Exception as e:
            logger.error(f"Failed to end wordguessing session: {e}")
            return {
                "success": False,
                "message": f"Failed to end session: {str(e)}"
            }
        finally:
            # Ensure proper cleanup
            try:
                if 'cur' in locals():
                    cur.close()
                if 'conn' in locals():
                    conn.close()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
    
    def assign_words_to_hinter(self, participant_code: str, words: List[str], session_code: str = None) -> Dict[str, Any]:
        """
        Assign words to a hinter participant
        
        Args:
            participant_code: Hinter participant code
            words: List of words to assign
            session_code: Session code
            
        Returns:
            Dictionary containing assignment result
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Check if participant is a hinter
            if session_code:
                cur.execute("""
                    SELECT role FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                """, (participant_code, session_code))
            else:
                cur.execute("""
                    SELECT role FROM participants 
                    WHERE participant_code = %s
                """, (participant_code,))
            
            participant_data = cur.fetchone()
            if not participant_data:
                return {"success": False, "message": "Participant not found"}
            
            if participant_data['role'] != 'hinter':
                return {"success": False, "message": "Only hinters can be assigned words"}
            
            # Update assigned words
            if session_code:
                cur.execute("""
                    UPDATE participants 
                    SET assigned_words = %s
                    WHERE participant_code = %s AND session_code = %s
                """, (json.dumps(words), participant_code, session_code))
            else:
                cur.execute("""
                    UPDATE participants 
                    SET assigned_words = %s
                    WHERE participant_code = %s
                """, (json.dumps(words), participant_code))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return {
                "success": True,
                "message": f"Assigned {len(words)} words to hinter {participant_code}",
                "words": words
            }
                
        except Exception as e:
            logger.error(f"Failed to assign words to hinter: {e}")
            return {
                "success": False,
                "message": f"Failed to assign words: {str(e)}"
            }
    
    def assign_roles_to_participants(self, role_assignments: Dict[str, str], session_code: str) -> Dict[str, Any]:
        """
        Assign roles to participants in the session
        
        Args:
            role_assignments: Dictionary mapping participant_code to role
            session_code: Session code
            
        Returns:
            Dictionary containing assignment result
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            updated_count = 0
            for participant_code, role in role_assignments.items():
                if role not in ['guesser', 'hinter']:
                    continue
                
                cur.execute("""
                    UPDATE participants 
                    SET role = %s
                    WHERE participant_code = %s AND session_code = %s
                """, (role, participant_code, session_code))
                
                if cur.rowcount > 0:
                    updated_count += 1
            
            conn.commit()
            cur.close()
            conn.close()
            
            return {
                "success": True,
                "message": f"Updated roles for {updated_count} participants",
                "role_assignments": role_assignments
            }
                
        except Exception as e:
            logger.error(f"Failed to assign roles to participants: {e}")
            return {
                "success": False,
                "message": f"Failed to assign roles: {str(e)}"
            }
