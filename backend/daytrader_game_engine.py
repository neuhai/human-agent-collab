#!/usr/bin/env python3
"""
DayTrader Game Engine
- Specialized game engine for DayTrader experiments
- Handles investment decisions, market data, and participant state
- Uses simplified trading model compared to ShapeFactory
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import psycopg2
import psycopg2.extras


class DayTraderGameEngine:
    """Core game engine for DayTrader research platform"""
    
    def __init__(self, db_connection_string: str):
        self.db_connection_string = db_connection_string
        self._connection = None
    
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
    
    def create_session(self, researcher_id: str, experiment_type: str = "daytrader", config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new DayTrader session"""
        from app import DatabaseConnection
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                # Generate session code
                session_code = self._generate_session_code()
                
                # Default DayTrader configuration
                default_config = {
                    "startingMoney": 1000,
                    "minTradePrice": 10,
                    "maxTradePrice": 100,
                    "roundDuration": 15,
                    "maxParticipants": 8
                }
                
                if config:
                    default_config.update(config)
                
                # Insert session
                cur.execute("""
                    INSERT INTO sessions (
                        session_code, experiment_type, researcher_id, 
                        total_rounds, round_duration_minutes, max_participants,
                        experiment_config, session_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING session_id
                """, (
                    session_code, experiment_type, researcher_id,
                    1, default_config["roundDuration"], default_config["maxParticipants"],
                    json.dumps(default_config), "idle"
                ))
                
                session_id = cur.fetchone()["session_id"]
                conn.commit()
                
                return {
                    "success": True,
                    "session_id": str(session_id),
                    "session_code": session_code,
                    "message": f"DayTrader session {session_code} created successfully"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create DayTrader session: {str(e)}"
            }
    
    def _generate_session_code(self) -> str:
        """Generate a unique session code"""
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    def add_participant(self, session_code: str, participant_code: str) -> Dict[str, Any]:
        """Add a participant to a DayTrader session"""
        from app import DatabaseConnection
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                # Get session info
                cur.execute("""
                    SELECT session_id, experiment_config, max_participants
                    FROM sessions 
                    WHERE session_code = %s AND experiment_type = 'daytrader'
                """, (session_code,))
                
                session_row = cur.fetchone()
                if not session_row:
                    return {
                        "success": False,
                        "message": f"DayTrader session {session_code} not found"
                    }
                
                session_id = session_row["session_id"]
                experiment_config = session_row["experiment_config"] or {}
                max_participants = session_row["max_participants"]
                
                # Check current participant count
                cur.execute("""
                    SELECT COUNT(*) as count FROM participants 
                    WHERE session_id = %s
                """, (session_id,))
                
                current_count = cur.fetchone()["count"]
                if current_count >= max_participants:
                    return {
                        "success": False,
                        "message": f"Session {session_code} is full (max {max_participants} participants)"
                    }
                
                # Check if participant already exists
                cur.execute("""
                    SELECT participant_id FROM participants 
                    WHERE session_code = %s AND participant_code = %s
                """, (session_code, participant_code))
                
                if cur.fetchone():
                    return {
                        "success": False,
                        "message": f"Participant {participant_code} already exists in session {session_code}"
                    }
            
            # Generate unique color/shape combination (simplified for DayTrader)
            color_shape = f"trader_{current_count + 1}"
            
            # Insert participant
            starting_money = experiment_config.get("startingMoney", 1000)
            cur.execute("""
                INSERT INTO participants (
                    session_id, participant_code, participant_type,
                    color_shape_combination, specialty_shape, money,
                    session_code, is_agent, agent_type, agent_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING participant_id
            """, (
                session_id, participant_code, "human",
                color_shape, "trader", starting_money,
                session_code, False, None, "inactive"
            ))
            
            participant_id = cur.fetchone()["participant_id"]
            conn.commit()
            
            return {
                "success": True,
                "participant_id": str(participant_id),
                "message": f"Participant {participant_code} added to DayTrader session {session_code}"
            }
            
        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "message": f"Failed to add participant: {str(e)}"
            }
        finally:
            cur.close()
    
    def get_participant_state(self, participant_code: str, session_code: str = None) -> Dict[str, Any]:
        """Get DayTrader participant state"""
        print(f"🔍 DayTrader: Getting participant state for {participant_code} in session {session_code}")
        from app import DatabaseConnection
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                # Get participant and session info
                cur.execute("""
                    SELECT p.participant_id, p.participant_code, p.money, p.login_status, p.session_id,
                           s.experiment_type, s.experiment_config
                    FROM participants p
                    JOIN sessions s ON p.session_id = s.session_id
                    WHERE p.participant_code = %s AND p.session_code = %s
                """, (participant_code, session_code))
                
                participant = cur.fetchone()
                if not participant:
                    return {
                        "success": False,
                        "message": f"Participant {participant_code} not found in session {session_code}"
                    }
                
                # Get recent investments
                cur.execute("""
                    SELECT invest_id, invest_price, invest_decision_type, invest_timestamp
                    FROM investments
                    WHERE participant_id = %s
                    ORDER BY invest_timestamp DESC
                    LIMIT 10
                """, (participant["participant_id"],))
                
                recent_investments = cur.fetchall()
                
                # Get session config
                session_config = participant["experiment_config"] or {}
                
                return {
                    "success": True,
                    "money": participant["money"] if participant["money"] is not None else session_config.get("startingMoney", 1000),
                    "recent_investments": [
                        {
                            "invest_id": str(inv["invest_id"]),
                            "invest_price": float(inv["invest_price"]),
                            "invest_decision_type": inv["invest_decision_type"],
                            "invest_timestamp": inv["invest_timestamp"].isoformat()
                        }
                        for inv in recent_investments
                    ],
                    "experiment_type": participant["experiment_type"]
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to get participant state: {str(e)}"
            }
    
    def get_public_state(self, session_code: str = None) -> Dict[str, Any]:
        """Get DayTrader public state"""
        print(f"🔍 DayTrader: Getting public state for session {session_code}")
        from app import DatabaseConnection
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                # Get session info
                cur.execute("""
                    SELECT session_id, experiment_config, experiment_type, session_status
                    FROM sessions 
                    WHERE session_code = %s AND experiment_type = 'daytrader'
                """, (session_code,))
                
                session_row = cur.fetchone()
                if not session_row:
                    return {
                        "success": False,
                        "message": f"DayTrader session {session_code} not found"
                    }
                
                session_id = session_row["session_id"]
                session_config = session_row["experiment_config"] or {}
                experiment_type = session_row["experiment_type"]
                session_status = session_row["session_status"]
                
                # Get participants
                cur.execute("""
                    SELECT participant_code, participant_type, login_status, money
                    FROM participants
                    WHERE session_id = %s
                    ORDER BY participant_code
                """, (session_id,))
                
                participants = cur.fetchall()
                participants_data = [
                    {
                        "participant_code": p["participant_code"],
                        "participant_type": p["participant_type"],
                        "status": p["login_status"],
                        "money": p["money"]
                    }
                    for p in participants
                ]
                
                # Get recent market activity (investments)
                cur.execute("""
                    SELECT i.invest_price, i.invest_timestamp, p.participant_code
                    FROM investments i
                    JOIN participants p ON i.participant_id = p.participant_id
                    WHERE i.session_id = %s
                    ORDER BY i.invest_timestamp DESC
                    LIMIT 20
                """, (session_id,))
                
                recent_investments = cur.fetchall()
                market_activity = [
                    {
                        "participant_code": inv["participant_code"],
                        "invest_price": float(inv["invest_price"]),
                        "invest_timestamp": inv["invest_timestamp"].isoformat()
                    }
                    for inv in recent_investments
                ]
                
                # Calculate market metrics
                if recent_investments:
                    prices = [float(inv["invest_price"]) for inv in recent_investments]
                    avg_price = sum(prices) / len(prices)
                    min_price = min(prices)
                    max_price = max(prices)
                else:
                    avg_price = session_config.get("minTradePrice", 10)
                    min_price = session_config.get("minTradePrice", 10)
                    max_price = session_config.get("maxTradePrice", 100)
                
                return {
                    "success": True,
                    "session_status": session_status,
                    "session_code": session_code,
                    "experiment_type": experiment_type,
                    "experiment_status_description": "Trade quickly within price bounds; manage cash and risk.",
                    "other_participants": participants_data,
                    "experiment_config": session_config,
                    "market_activity": market_activity,
                    "market_metrics": {
                        "average_price": avg_price,
                        "min_price": min_price,
                        "max_price": max_price,
                        "total_trades": len(recent_investments)
                    }
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to get public state: {str(e)}"
            }
    
    def make_investment(self, participant_code: str, invest_price: float,
                       invest_decision_type: str = "individual", session_code: str = None) -> Dict[str, Any]:
        """Make an investment in DayTrader"""
        print(f"🔍 DayTrader: Making investment for {participant_code} at price {invest_price} (type: {invest_decision_type})")
        from app import DatabaseConnection
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                # Get participant and session info
                cur.execute("""
                    SELECT p.participant_id, p.money, p.session_id, s.experiment_config
                    FROM participants p
                    JOIN sessions s ON p.session_id = s.session_id
                    WHERE p.participant_code = %s AND p.session_code = %s
                """, (participant_code, session_code))
                
                participant = cur.fetchone()
                if not participant:
                    return {
                        "success": False,
                        "message": f"Participant {participant_code} not found in session {session_code}"
                    }
                
                session_config = participant["experiment_config"] or {}
                min_price = session_config.get("minTradePrice", 10)
                max_price = session_config.get("maxTradePrice", 100)
                
                # Validate investment parameters
                if invest_price < min_price or invest_price > max_price:
                    return {
                        "success": False,
                        "message": f"Investment price {invest_price} is outside allowed range ({min_price}-{max_price})"
                    }
                
                if invest_decision_type not in ["individual", "group"]:
                    return {
                        "success": False,
                        "message": f"Invalid decision type: {invest_decision_type}. Must be 'individual' or 'group'"
                    }
                
                # No trading fee/cost deduction for DayTrader baseline
                
                # Insert investment record
                cur.execute("""
                    INSERT INTO investments (
                        session_id, participant_id, invest_price,
                        invest_decision_type, invest_data
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING invest_id
                """, (
                    participant["session_id"], participant["participant_id"],
                    invest_price, invest_decision_type,
                    json.dumps({})
                ))
                
                invest_id = cur.fetchone()["invest_id"]
                
                # Deduct investment amount from participant's money
                cur.execute("""
                    UPDATE participants 
                    SET money = money - %s
                    WHERE participant_id = %s
                """, (invest_price, participant["participant_id"]))
                
                conn.commit()
                
                return {
                    "success": True,
                    "invest_id": str(invest_id),
                    "message": f"Investment recorded at ${invest_price:.2f} (decision: {invest_decision_type})"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to make investment: {str(e)}"
            }
    
    def send_message(self, participant_code: str, recipient: str, content: str, session_code: str = None) -> Dict[str, Any]:
        """Send a message in DayTrader session"""
        from app import DatabaseConnection
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                # Get sender info
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                """, (participant_code, session_code))
                
                sender = cur.fetchone()
                if not sender:
                    return {
                        "success": False,
                        "message": f"Sender {participant_code} not found in session {session_code}"
                    }
                
                # Handle recipient
                recipient_id = None
                if recipient != "all":
                    cur.execute("""
                        SELECT participant_id FROM participants 
                        WHERE participant_code = %s AND session_code = %s
                    """, (recipient, session_code))
                    
                    recipient_row = cur.fetchone()
                    if not recipient_row:
                        return {
                            "success": False,
                            "message": f"Recipient {recipient} not found in session {session_code}"
                        }
                    recipient_id = recipient_row["participant_id"]
                
                # Insert message
                cur.execute("""
                    INSERT INTO messages (
                        session_id, sender_id, recipient_id, message_content, message_type
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING message_id
                """, (
                    sender["session_id"], sender["participant_id"], 
                    recipient_id, content, "chat"
                ))
                
                message_id = cur.fetchone()["message_id"]
                conn.commit()
                
                return {
                    "success": True,
                    "message_id": str(message_id),
                    "message": f"Message sent to {recipient}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to send message: {str(e)}"
            }
    
    def get_session_status(self, session_code: str) -> Dict[str, Any]:
        """Get DayTrader session status"""
        from app import DatabaseConnection
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT s.session_id, s.session_code, s.session_status, s.experiment_type,
                           s.experiment_config, s.created_at, s.session_started_at,
                           COUNT(p.participant_id) as participant_count
                    FROM sessions s
                    LEFT JOIN participants p ON s.session_id = p.session_id
                    WHERE s.session_code = %s AND s.experiment_type = 'daytrader'
                    GROUP BY s.session_id, s.session_code, s.session_status, s.experiment_type,
                             s.experiment_config, s.created_at, s.session_started_at
                """, (session_code,))
                
                session = cur.fetchone()
                if not session:
                    return {
                        "success": False,
                        "message": f"DayTrader session {session_code} not found"
                    }
                
                return {
                    "success": True,
                    "session_id": str(session["session_id"]),
                    "session_code": session["session_code"],
                    "session_status": session["session_status"],
                    "experiment_type": session["experiment_type"],
                    "experiment_config": session["experiment_config"],
                    "participant_count": session["participant_count"],
                    "created_at": session["created_at"].isoformat() if session["created_at"] else None,
                    "session_started_at": session["session_started_at"].isoformat() if session["session_started_at"] else None
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to get session status: {str(e)}"
            }
    
    def start_session(self, session_code: str) -> Dict[str, Any]:
        """Start a DayTrader session"""
        from app import DatabaseConnection
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    UPDATE sessions 
                    SET session_status = 'session_active', session_started_at = CURRENT_TIMESTAMP
                    WHERE session_code = %s AND experiment_type = 'daytrader'
                    RETURNING session_id
                """, (session_code,))
                
                result = cur.fetchone()
                if not result:
                    return {
                        "success": False,
                        "message": f"DayTrader session {session_code} not found or already started"
                    }
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": f"DayTrader session {session_code} started successfully"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to start session: {str(e)}"
            }
    
    def end_session(self, session_code: str) -> Dict[str, Any]:
        """End a DayTrader session"""
        from app import DatabaseConnection
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    UPDATE sessions 
                    SET session_status = 'session_completed', session_completed_at = CURRENT_TIMESTAMP
                    WHERE session_code = %s AND experiment_type = 'daytrader'
                    RETURNING session_id
                """, (session_code,))
                
                result = cur.fetchone()
                if not result:
                    return {
                        "success": False,
                        "message": f"DayTrader session {session_code} not found"
                    }
                
                # Clear investment history when ending session
                cur.execute("""
                    DELETE FROM investments 
                    WHERE session_id = %s
                """, (result['session_id'],))
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": f"DayTrader session {session_code} ended successfully and investment history cleared"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to end session: {str(e)}"
            }
    
    def clear_investments(self, session_code: str) -> Dict[str, Any]:
        """Clear investment history for a DayTrader session (used during reset)"""
        from app import DatabaseConnection
        try:
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                
                # Get session_id
                cur.execute("""
                    SELECT session_id FROM sessions 
                    WHERE session_code = %s AND experiment_type = 'daytrader'
                """, (session_code,))
                
                result = cur.fetchone()
                if not result:
                    return {
                        "success": False,
                        "message": f"DayTrader session {session_code} not found"
                    }
                
                # Clear investment history
                cur.execute("""
                    DELETE FROM investments 
                    WHERE session_id = %s
                """, (result['session_id'],))
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": f"Investment history cleared for DayTrader session {session_code}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to clear investments: {str(e)}"
            }
