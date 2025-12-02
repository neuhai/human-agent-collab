"""
Hidden Profiles Research Platform - Game Engine
Core game logic and session management for Hidden Profiles experiments
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

class HiddenProfileGameEngine:
    """Core game engine for Hidden Profiles research platform"""
    
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
    
    def _return_db_connection(self, conn):
        """Return database connection to pool"""
        # Import here to avoid circular imports
        from app import return_db_connection
        return_db_connection(conn)
        
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
    
    def create_session(self, researcher_id: str, experiment_type: str = "hiddenprofiles", config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new Hidden Profiles experimental session
        
        Args:
            researcher_id: Unique identifier for the researcher
            experiment_type: Type of experiment (should be 'hiddenprofiles')
            config: Optional configuration parameters for the session
            
        Returns:
            Dictionary containing session details and status
        """
        # Default configuration for Hidden Profiles
        # Structure: experiment_config contains hiddenProfiles with all Hidden Profiles-specific data
        experiment_config = {
            'total_rounds': 1,  # Hidden Profiles is typically a single session
            'round_duration_minutes': 15,  # Duration for discussion (after reading phase)
            'first_round_duration_minutes': 15,
            'max_participants': 20,
            'sessionDuration': 15,  # Session duration in minutes (discussion time)
            'hiddenProfiles': {
                'publicInfo': None,  # Will be populated when public info is uploaded
                'candidateDocs': [],  # Will be populated when candidate docs are uploaded
                'candidateNames': [],  # Will be populated when candidate names are set
                'participantInitiatives': {},  # Map of participant_code -> initiative (active/passive)
                'participantCandidateDocs': {},  # Map of participant_code -> candidate_document_id
                'votes': {},  # Map of participant_code -> candidate_name (their vote)
                'readingTimeMinutes': 5  # Default reading phase duration in minutes
            }
        }
        
        # Merge with provided config
        if config:
            # If config has hiddenProfiles, merge it properly
            if 'hiddenProfiles' in config:
                experiment_config['hiddenProfiles'].update(config['hiddenProfiles'])
            # Merge top-level config
            for key, value in config.items():
                if key != 'hiddenProfiles':
                    experiment_config[key] = value
        
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
                experiment_config["total_rounds"], 
                experiment_config["round_duration_minutes"],
                experiment_config["first_round_duration_minutes"],
                experiment_config["max_participants"],
                json.dumps(experiment_config), "idle"
            ))
            
            session_id = cur.fetchone()["session_id"]
            conn.commit()
            
            logger.info(f"Created Hidden Profiles session {session_code} with ID {session_id}")
            
            return {
                "success": True,
                "session_id": str(session_id),
                "session_code": session_code,
                "message": f"Hidden Profiles session {session_code} created successfully"
            }
                
        except Exception as e:
            logger.error(f"Failed to create Hidden Profiles session: {e}")
            return {
                "success": False,
                "message": f"Failed to create Hidden Profiles session: {str(e)}"
            }
        finally:
            # Ensure proper cleanup
            try:
                if 'cur' in locals():
                    cur.close()
                if 'conn' in locals():
                    self._return_db_connection(conn)
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
    
    def get_participant_state(self, participant_code: str, session_code: str = None) -> Dict[str, Any]:
        """Get private state for a specific participant"""
        conn = None
        cur = None
        try:
            conn = self._get_db_connection()
            # Check if connection is valid
            if conn is None:
                logger.error("Failed to get database connection")
                return {"error": "Database connection failed"}
            
            # Check if connection is closed
            try:
                if conn.closed:
                    logger.error("Received closed connection from pool")
                    # Get a new connection
                    conn = self._get_db_connection()
                    if conn is None or conn.closed:
                        return {"error": "Database connection unavailable"}
            except AttributeError:
                # Some connection types might not have 'closed' attribute
                pass
            
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            if not session_code:
                logger.error(f"Session isolation error: get_participant_state called for {participant_code} without session_code")
                # Clean up before early return
                if cur is not None:
                    try:
                        cur.close()
                    except:
                        pass
                if conn is not None:
                    try:
                        self._return_db_connection(conn)
                    except:
                        pass
                return {
                    "error": "Session isolation error: session_code required"
                }
            
            logger.info(f"Getting participant state for {participant_code} in session {session_code}")
            
            # Get participant info
            cur.execute("""
                SELECT p.participant_id, p.participant_code, p.session_id, p.login_status
                FROM participants p
                JOIN sessions s ON p.session_id = s.session_id
                WHERE p.participant_code = %s AND p.session_code = %s
            """, (participant_code, session_code))
            
            participant = cur.fetchone()
            if not participant:
                logger.warning(f"Participant {participant_code} not found in session {session_code}")
                # Clean up before early return
                if cur is not None:
                    try:
                        cur.close()
                    except:
                        pass
                if conn is not None:
                    try:
                        self._return_db_connection(conn)
                    except:
                        pass
                return {
                    "error": f"Participant {participant_code} not found in session {session_code}"
                }
            
            # Get session config
            cur.execute("""
                SELECT experiment_config FROM sessions WHERE session_code = %s
            """, (session_code,))
            session_result = cur.fetchone()
            experiment_config = session_result['experiment_config'] or {} if session_result else {}
            hidden_profiles_config = experiment_config.get('hiddenProfiles', {})
            
            # Get assigned documents
            public_info = hidden_profiles_config.get('publicInfo')
            candidate_doc_id = hidden_profiles_config.get('participantCandidateDocs', {}).get(participant_code)
            candidate_doc = None
            
            if candidate_doc_id:
                candidate_docs = hidden_profiles_config.get('candidateDocs', [])
                candidate_doc = next((doc for doc in candidate_docs if doc.get('doc_id') == candidate_doc_id), None)
                # Ensure file_url is included if available
                if candidate_doc and not candidate_doc.get('file_url') and candidate_doc.get('doc_id'):
                    # Construct file_url if not present
                    candidate_doc['file_url'] = f'/api/hiddenprofiles/get-document/{session_code}/{candidate_doc.get("doc_id")}'
            
            # Get participant's vote
            vote = hidden_profiles_config.get('votes', {}).get(participant_code)
            
            # Get initiative for agents
            initiative = hidden_profiles_config.get('participantInitiatives', {}).get(participant_code)
            
            # Close cursor before returning
            cur.close()
            cur = None  # Mark as closed so finally block doesn't try again
            
            result = {
                "public_info": public_info,
                "candidate_document": candidate_doc,
                "vote": vote,
                "initiative": initiative,
                "session_code": session_code,
                "participant_code": participant_code
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting participant state: {e}")
            return {
                "error": str(e)
            }
        finally:
            # Always clean up cursor and connection
            if cur is not None:
                try:
                    cur.close()
                except Exception as e:
                    logger.debug(f"Error closing cursor: {e}")
            if conn is not None:
                try:
                    self._return_db_connection(conn)
                except Exception as e:
                    logger.debug(f"Error returning connection: {e}")
    
    def get_public_state(self, session_code: str = None) -> Dict[str, Any]:
        """Get public game state"""
        if not session_code:
            return {
                "session_status": "inactive",
                "participants": [],
                "messages": [],
                "public_info": None,
                "candidate_docs": []
            }
        
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get session config
            cur.execute("""
                SELECT experiment_config, experiment_type, session_status FROM sessions WHERE session_code = %s
            """, (session_code,))
            session_row = cur.fetchone()
            experiment_config = session_row['experiment_config'] or {} if session_row else {}
            hidden_profiles_config = experiment_config.get('hiddenProfiles', {})
            
            # Get public info
            public_info = hidden_profiles_config.get('publicInfo')
            
            # Get candidate docs (without content, just metadata)
            candidate_docs = hidden_profiles_config.get('candidateDocs', [])
            candidate_docs_metadata = [
                {
                    'doc_id': doc.get('doc_id'),
                    'title': doc.get('title'),
                    'filename': doc.get('filename')
                }
                for doc in candidate_docs
            ]
            
            # Get candidate display names (optional)
            candidate_names = hidden_profiles_config.get('candidateNames', [])
            
            # Get participants
            cur.execute("""
                SELECT participant_code, participant_type, login_status
                FROM participants 
                WHERE session_code = %s
            """, (session_code,))
            
            participants = cur.fetchall()
            participants_data = []
            for p in participants:
                # For AI agents, extract the original name (remove session code suffix)
                display_name = p['participant_code']
                if '_' in p['participant_code']:
                    display_name = p['participant_code'].rsplit('_', 1)[0]
                
                participants_data.append({
                    "participant_code": display_name,
                    "internal_participant_code": p['participant_code'],
                    "participant_type": p['participant_type'],
                    "status": p['login_status']
                })
            
            # Get recent messages (last 50)
            cur.execute("""
                SELECT 
                    m.message_id,
                    m.message_content,
                    m.message_timestamp,
                    sender.participant_code as sender_code,
                    recipient.participant_code as recipient_code
                FROM messages m
                JOIN participants sender ON m.sender_id = sender.participant_id
                LEFT JOIN participants recipient ON m.recipient_id = recipient.participant_id
                WHERE m.session_id = (SELECT session_id FROM sessions WHERE session_code = %s)
                AND m.message_type = 'chat'
                ORDER BY m.message_timestamp DESC
                LIMIT 50
            """, (session_code,))
            
            messages = cur.fetchall()
            messages_data = []
            for msg in messages:
                # Extract display names for agents
                sender_display = msg['sender_code']
                if '_' in sender_display:
                    sender_display = sender_display.rsplit('_', 1)[0]
                
                recipient_display = msg['recipient_code'] if msg['recipient_code'] else 'all'
                if recipient_display != 'all' and '_' in recipient_display:
                    recipient_display = recipient_display.rsplit('_', 1)[0]
                
                messages_data.append({
                    "message_id": str(msg['message_id']),
                    "sender": sender_display,
                    "recipient": recipient_display,
                    "content": msg['message_content'],
                    "timestamp": msg['message_timestamp'].isoformat() if msg['message_timestamp'] else None
                })
            
            # Reverse messages to show oldest first
            messages_data.reverse()
            
            # Get votes (public - show who voted for what candidate name)
            votes = hidden_profiles_config.get('votes', {})
            votes_data = {}
            for participant_code, voted_candidate_name in votes.items():
                # Extract display name
                display_name = participant_code
                if '_' in participant_code:
                    display_name = participant_code.rsplit('_', 1)[0]
                votes_data[display_name] = voted_candidate_name
            
            cur.close()
            self._return_db_connection(conn)
            
            return {
                "session_status": session_row['session_status'] if session_row else 'idle',
                "session_code": session_code,
                "public_info": public_info,
                "candidate_docs": candidate_docs_metadata,
                "candidate_names": candidate_names,
                "participants": participants_data,
                "messages": messages_data,
                "votes": votes_data
            }
            
        except Exception as e:
            logger.error(f"Error getting public state: {e}")
            return {
                "session_status": "error",
                "participants": [],
                "messages": [],
                "public_info": None,
                "candidate_docs": []
            }
        finally:
            if 'cur' in locals():
                try:
                    cur.close()
                except:
                    pass
            if 'conn' in locals():
                try:
                    self._return_db_connection(conn)
                except:
                    pass
    
    def send_message(self, participant_code: str, recipient: str, content: str, session_code: str = None) -> Dict[str, Any]:
        """Send a message from one participant to another"""
        conn = None
        cur = None
        try:
            conn = self._get_db_connection()
            
            # Check if connection is valid
            if conn is None:
                logger.error("Failed to get database connection")
                return {
                    "success": False,
                    "error": "Failed to get database connection"
                }
            
            # Check if connection is closed
            if conn.closed:
                logger.error("Got a closed connection from pool")
                # Try to get a new connection
                try:
                    self._return_db_connection(conn)
                except:
                    pass
                conn = self._get_db_connection()
                if conn is None or conn.closed:
                    logger.error("Failed to get valid database connection after retry")
                    return {
                        "success": False,
                        "error": "Database connection is closed"
                    }
            
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            if not session_code:
                logger.error(f"Session isolation error: send_message called for {participant_code} without session_code")
                return {
                    "success": False,
                    "error": "Session isolation error: session_code required"
                }
            
            # Get sender info with session filtering
            cur.execute("""
                SELECT participant_id, session_id
                FROM participants 
                WHERE participant_code = %s AND session_code = %s
            """, (participant_code, session_code))
            
            sender = cur.fetchone()
            if not sender:
                logger.warning(f"Sender {participant_code} not found in session {session_code}")
                return {
                    "success": False,
                    "error": f"Sender {participant_code} not found in session {session_code}"
                }
            
            # Get recipient info (if not "all")
            recipient_id = None
            if recipient != "all":
                # Try exact match first (for human participants)
                cur.execute("""
                    SELECT participant_id
                    FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                """, (recipient, session_code))
                
                recipient_result = cur.fetchone()
                
                # If not found, try with session code suffix (for agent lookup by display name)
                if not recipient_result:
                    agent_code_with_session = f"{recipient}_{session_code}"
                    cur.execute("""
                        SELECT participant_id
                        FROM participants 
                        WHERE participant_code = %s AND session_code = %s
                    """, (agent_code_with_session, session_code))
                    recipient_result = cur.fetchone()
                
                if not recipient_result:
                    raise ValueError(f"Recipient {recipient} not found")
                recipient_id = recipient_result['participant_id']
            
            # Insert message using schema message_type 'chat'
            message_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO messages (
                    message_id, session_id, sender_id, recipient_id,
                    message_type, message_content, message_timestamp, message_data, delivered_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                message_id, sender['session_id'], sender['participant_id'], recipient_id,
                'chat', content, datetime.now(timezone.utc), None, 'sent'
            ))
            
            conn.commit()
            
            logger.info(f"Message sent from {participant_code} to {recipient}: {content[:50]}...")
            
            result = {
                "success": True,
                "message": "Message sent successfully",
                "message_id": message_id
            }
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            import traceback
            logger.error(traceback.format_exc())
            if 'conn' in locals() and conn:
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.error(f"Error rolling back transaction: {rollback_error}")
            result = {
                "success": False,
                "error": str(e)
            }
        finally:
            # Always clean up cursor and connection
            if 'cur' in locals():
                try:
                    cur.close()
                except Exception as e:
                    logger.debug(f"Error closing cursor: {e}")
            if 'conn' in locals():
                try:
                    self._return_db_connection(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
        
        return result
    
    def submit_vote(self, participant_code: str, candidate_name: str, session_code: str = None) -> Dict[str, Any]:
        """Submit a vote for a candidate name"""
        conn = None
        cur = None
        try:
            conn = self._get_db_connection()
            if conn is None:
                logger.error("Failed to get database connection")
                return {"success": False, "error": "Database connection failed"}
            
            # Check if connection is closed
            try:
                if conn.closed:
                    logger.error("Received closed connection from pool")
                    conn = self._get_db_connection()
                    if conn is None or conn.closed:
                        return {"success": False, "error": "Database connection unavailable"}
            except AttributeError:
                # Some connection types might not have 'closed' attribute
                pass
            
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            if not session_code:
                logger.error(f"Session isolation error: submit_vote called for {participant_code} without session_code")
                return {
                    "success": False,
                    "error": "Session isolation error: session_code required"
                }
            
            # Get participant info
            cur.execute("""
                SELECT participant_id, session_id
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
            
            # Get session config
            cur.execute("""
                SELECT experiment_config FROM sessions WHERE session_code = %s
            """, (session_code,))
            session_result = cur.fetchone()
            experiment_config = session_result['experiment_config'] or {} if session_result else {}
            
            if 'hiddenProfiles' not in experiment_config:
                experiment_config['hiddenProfiles'] = {}
            
            hidden_profiles_config = experiment_config['hiddenProfiles']
            
            # Validate candidate name exists in the list
            candidate_names = hidden_profiles_config.get('candidateNames', [])
            if not candidate_name or candidate_name not in candidate_names:
                return {
                    "success": False,
                    "error": f"Candidate name '{candidate_name}' not found in session candidate list"
                }
            
            # Store vote by candidate name
            if 'votes' not in hidden_profiles_config:
                hidden_profiles_config['votes'] = {}
            
            hidden_profiles_config['votes'][participant_code] = candidate_name
            
            # Update experiment_config in database
            cur.execute("""
                UPDATE sessions 
                SET experiment_config = %s 
                WHERE session_code = %s
            """, (json.dumps(experiment_config), session_code))
            
            conn.commit()
            cur.close()
            cur = None  # Mark as closed so finally block doesn't try again
            
            logger.info(f"Vote submitted by {participant_code} for candidate name {candidate_name}")
            
            return {
                "success": True,
                "message": "Vote submitted successfully",
                "candidate_name": candidate_name
            }
            
        except Exception as e:
            logger.error(f"Error submitting vote: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.error(f"Error during rollback: {rollback_error}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            # Always clean up cursor and connection
            if cur is not None:
                try:
                    cur.close()
                except Exception as e:
                    logger.debug(f"Error closing cursor: {e}")
            if conn is not None:
                try:
                    self._return_db_connection(conn)
                except Exception as e:
                    logger.debug(f"Error returning connection: {e}")
    
    def get_assigned_documents(self, participant_code: str, session_code: str = None) -> Dict[str, Any]:
        """Get assigned documents for a participant (public info + their candidate doc)"""
        conn = None
        cur = None
        try:
            # Get connection and validate it's open
            max_retries = 2  # Reduced retries to prevent pool exhaustion
            for attempt in range(max_retries):
                conn = None
                try:
                    conn = self._get_db_connection()
                    if conn is None:
                        raise Exception("Failed to get database connection")
                    
                    # Check if connection is closed and get a new one if needed
                    try:
                        if hasattr(conn, 'closed') and conn.closed:
                            logger.warning(f"Received closed connection from pool (attempt {attempt + 1}), getting new one")
                            if conn is not None:
                                try:
                                    self._return_db_connection(conn)
                                except:
                                    pass
                            conn = self._get_db_connection()
                            if conn is None:
                                raise Exception("Failed to get database connection")
                    except AttributeError:
                        # Connection might not have 'closed' attribute, try to use it anyway
                        pass
                    
                    # Test the connection by creating a cursor
                    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    # If we get here, connection is valid
                    break
                    
                except (psycopg2.InterfaceError, psycopg2.OperationalError, psycopg2.pool.PoolError) as e:
                    logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
                    if conn is not None:
                        try:
                            self._return_db_connection(conn)
                        except:
                            pass
                    conn = None
                    if attempt == max_retries - 1:
                        raise Exception(f"Failed to get valid database connection after {max_retries} attempts: {e}")
                    # Wait a bit before retrying
                    import time
                    time.sleep(0.2)  # Slightly longer wait
                except Exception as e:
                    # For any other exception, return the connection and re-raise
                    if conn is not None:
                        try:
                            self._return_db_connection(conn)
                        except:
                            pass
                    raise
            
            if not session_code:
                logger.error(f"Session isolation error: get_assigned_documents called for {participant_code} without session_code")
                # Return connection before early return
                if cur is not None:
                    try:
                        cur.close()
                    except:
                        pass
                if conn is not None:
                    try:
                        self._return_db_connection(conn)
                    except:
                        pass
                return {
                    "error": "Session isolation error: session_code required"
                }
            
            # Get participant info
            cur.execute("""
                SELECT participant_id, session_id
                FROM participants 
                WHERE participant_code = %s AND session_code = %s
            """, (participant_code, session_code))
            
            participant = cur.fetchone()
            if not participant:
                # Return connection before early return
                if cur is not None:
                    try:
                        cur.close()
                    except:
                        pass
                if conn is not None:
                    try:
                        self._return_db_connection(conn)
                    except:
                        pass
                return {
                    "error": f"Participant {participant_code} not found in session {session_code}"
                }
            
            # Get session config
            cur.execute("""
                SELECT experiment_config FROM sessions WHERE session_code = %s
            """, (session_code,))
            session_result = cur.fetchone()
            experiment_config = session_result['experiment_config'] or {} if session_result else {}
            hidden_profiles_config = experiment_config.get('hiddenProfiles', {})
            
            # Get public info
            public_info = hidden_profiles_config.get('publicInfo')
            
            # Get assigned candidate document
            candidate_doc_id = hidden_profiles_config.get('participantCandidateDocs', {}).get(participant_code)
            candidate_doc = None
            candidate_doc_text = None
            
            if candidate_doc_id:
                candidate_docs = hidden_profiles_config.get('candidateDocs', [])
                candidate_doc = next((doc for doc in candidate_docs if doc.get('doc_id') == candidate_doc_id), None)
                
                # Extract text content from candidate document if available
                if candidate_doc:
                    # First try to get content directly from doc
                    if candidate_doc.get('content'):
                        candidate_doc_text = candidate_doc.get('content')
                    else:
                        # Try to extract text from file (saved_filename or file_url)
                        candidate_doc_text = self._get_document_text_content(candidate_doc, session_code)
            
            # Build result before closing cursor
            result = {
                "public_info": public_info,
                "candidate_document": candidate_doc,
                "candidate_document_text": candidate_doc_text  # Add text content for agent prompt
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting assigned documents: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "error": str(e)
            }
        finally:
            # Always close cursor and return connection to pool
            if cur is not None:
                try:
                    cur.close()
                except Exception as e:
                    logger.warning(f"Error closing cursor: {e}")
            if conn is not None:
                try:
                    self._return_db_connection(conn)
                except Exception as e:
                    logger.warning(f"Error returning connection to pool: {e}")
    
    def _get_document_text_content(self, doc: Dict[str, Any], session_code: str) -> Optional[str]:
        """Extract text content from a document file"""
        try:
            from pdf_utils import extract_text_from_pdf_file_path
            import os
            
            # First check if content is already in doc (this should be the primary source)
            if doc.get('content'):
                content = doc.get('content')
                if content and content.strip():
                    logger.info(f"Found content in doc metadata for doc_id: {doc.get('doc_id')}")
                    return content.strip()
            
            # Try to get file path from doc metadata
            if doc.get('saved_filename'):
                # Construct absolute file path (same as in app.py)
                base_dir = os.path.dirname(os.path.abspath(__file__))
                file_path = os.path.join(base_dir, 'uploads', 'hiddenprofiles', session_code, doc['saved_filename'])
                if os.path.exists(file_path):
                    logger.info(f"Extracting text from file: {file_path}")
                    extracted_text = extract_text_from_pdf_file_path(file_path)
                    if extracted_text:
                        logger.info(f"Successfully extracted {len(extracted_text)} characters from file")
                        return extracted_text
                else:
                    logger.warning(f"File not found at path: {file_path}")
            
            # Try file_url if saved_filename didn't work
            if doc.get('file_url'):
                # Try to extract from file_url path
                file_url = doc.get('file_url')
                if isinstance(file_url, str) and file_url.startswith('/'):
                    # Relative path - construct absolute path
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    file_path = os.path.join(base_dir, file_url.lstrip('/'))
                    if os.path.exists(file_path):
                        logger.info(f"Extracting text from file_url: {file_path}")
                        extracted_text = extract_text_from_pdf_file_path(file_path)
                        if extracted_text:
                            logger.info(f"Successfully extracted {len(extracted_text)} characters from file_url")
                            return extracted_text
            
            logger.warning(f"Could not extract text from document {doc.get('doc_id')}: no content found in doc metadata and file extraction failed")
            return None
        except Exception as e:
            logger.error(f"Error extracting text from document {doc.get('doc_id', 'unknown')}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def start_session(self, session_code: str) -> Dict[str, Any]:
        """Start the Hidden Profiles session"""
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Update session to active status
            cur.execute("""
                UPDATE sessions 
                SET session_status = 'session_active',
                    session_started_at = CURRENT_TIMESTAMP
                WHERE session_code = %s
                RETURNING session_id, session_code
            """, (session_code,))
            
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Session {session_code} not found")
            
            conn.commit()
            cur.close()
            
            logger.info(f"Started Hidden Profiles session {session_code}")
            
            return {
                "success": True,
                "session_id": str(result['session_id']),
                "session_code": result['session_code'],
                "status": "session_active",
                "started_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error starting session: {e}")
            if conn:
                conn.rollback()
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if 'cur' in locals():
                try:
                    cur.close()
                except:
                    pass
            if 'conn' in locals():
                try:
                    self._return_db_connection(conn)
                except:
                    pass
    
    def end_session(self, session_code: str) -> Dict[str, Any]:
        """End the Hidden Profiles session"""
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Update session to completed status
            cur.execute("""
                UPDATE sessions 
                SET session_status = 'session_completed',
                    session_completed_at = CURRENT_TIMESTAMP
                WHERE session_code = %s
                RETURNING session_id, session_code
            """, (session_code,))
            
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Session {session_code} not found")
            
            conn.commit()
            cur.close()
            
            logger.info(f"Ended Hidden Profiles session {session_code}")
            
            return {
                "success": True,
                "session_id": str(result['session_id']),
                "session_code": result['session_code'],
                "status": "session_completed",
                "ended_at": datetime.now(timezone.utc).isoformat()
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
            if 'cur' in locals():
                try:
                    cur.close()
                except:
                    pass
            if 'conn' in locals():
                try:
                    self._return_db_connection(conn)
                except:
                    pass

