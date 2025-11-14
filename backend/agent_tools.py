#!/usr/bin/env python3
"""
Agent Tools (serverless) for Shape Factory Game
- Direct wrappers on top of GameEngine methods
- No MCP server; callable locally by agent controllers
- Provides OpenAI-style tool specifications for LLM function calling
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
import os
import json

from game_engine import GameEngine
from game_engine_factory import GameEngineFactory


def build_database_url() -> str:
    return (
        f"postgresql://{os.getenv('DATABASE_USER', '')}:{os.getenv('DATABASE_PASSWORD', '')}"
        f"@{os.getenv('DATABASE_HOST', 'localhost')}:{os.getenv('DATABASE_PORT', '5432')}"
        f"/{os.getenv('DATABASE_NAME', 'shape_factory_research')}"
    )


class AgentTools:
    """Serverless toolset exposing game actions/state for agents."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or build_database_url()
        self._engine = GameEngine(self.database_url)
    
    def _get_game_engine(self, participant_code: str, session_code: str = None) -> GameEngine:
        """Get the appropriate game engine based on experiment type"""
        try:
            import psycopg2
            import psycopg2.extras
            
            # Use a fresh connection to avoid transaction issues
            db_url = self._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            if session_code:
                cur.execute("""
                    SELECT experiment_type FROM sessions 
                    WHERE session_code = %s
                    LIMIT 1
                """, (session_code,))
            else:
                cur.execute("""
                    SELECT s.experiment_type FROM sessions s
                    JOIN participants p ON s.session_id = p.session_id
                    WHERE p.participant_code = %s
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            experiment_type = "shapefactory"  # Default
            if result and result.get('experiment_type'):
                experiment_type = result['experiment_type']
            
            # Use GameEngineFactory to get the correct game engine
            engine = GameEngineFactory.create_game_engine(experiment_type, self.database_url)
            return engine
            
        except Exception as e:
            print(f"[WARNING] Failed to get experiment-specific game engine: {e}")
            # Fallback to base GameEngine
            return self._engine

    # --------- Core tool implementations (direct GameEngine calls) ---------

    def get_game_state(self, participant_code: str, session_code: str = None) -> Dict[str, Any]:
        # Get session code for this participant if not provided
        if not session_code:
            try:
                import psycopg2
                import psycopg2.extras
                
                # Use a fresh connection to avoid transaction issues
                db_url = self._engine.db_connection_string
                conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
                cur = conn.cursor()
                
                # CRITICAL FIX: Use session_code from the agent's context instead of querying by participant_code only
                # This prevents cross-session data leakage
                cur.execute("""
                    SELECT session_code FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (participant_code,))
                result = cur.fetchone()
                session_code = result['session_code'] if result else None
                
                cur.close()
                conn.close()
                
            except Exception as e:
                print(f"Warning: Could not get session code/config for {participant_code}: {e}")
                session_code = None
        
        # Default values
        communication_level = 'chat'
        awareness_enabled = False
        
        # Fetch session configuration for communication level and awareness dashboard
        if session_code:
            try:
                import psycopg2
                import psycopg2.extras
                
                db_url = self._engine.db_connection_string
                conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT 
                        experiment_config->>'communicationLevel' AS communication_level,
                        experiment_config->>'awarenessDashboard' AS awareness_dashboard
                    FROM sessions 
                    WHERE session_code = %s
                    LIMIT 1
                """, (session_code,))
                cfg = cur.fetchone()
                if cfg:
                    communication_level = (cfg.get('communication_level') or 'chat').lower()
                    awareness_enabled = (cfg.get('awareness_dashboard') or 'off').lower() == 'on'
                
                cur.close()
                conn.close()
            except Exception as e:
                print(f"Warning: Could not get session config for {session_code}: {e}")
        
        # CRITICAL FIX: Always pass session_code to ensure session isolation
        # Get the appropriate game engine based on experiment type
        game_engine = self._get_game_engine(participant_code, session_code)
        participant_state_result = game_engine.get_participant_state(participant_code, session_code)
        public_state = game_engine.get_public_state(session_code)
        
        # Extract the participant data from the result for private_state
        if participant_state_result.get('success'):
            private_state = participant_state_result.get('participant', {})
        else:
            private_state = {}
        
        # Attach awareness flag to public state for downstream consumers
        if isinstance(public_state, dict):
            public_state['awareness_dashboard_enabled'] = awareness_enabled
        
        return {
            "success": True,
            "game_state": {
                "private_state": private_state,
                "public_state": public_state,
                "session_code": session_code,  # Include session code for agent access
            },
            "communication_level": communication_level,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def send_message(self, participant_code: str, recipient: str, content: str, session_code: str = None) -> Dict[str, Any]:
        # Get current communication level from database
        try:
            import psycopg2
            import psycopg2.extras
            import os
            
            # Use a fresh connection to avoid transaction issues
            db_url = self._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # CRITICAL FIX: Use session_code for proper session isolation
            if session_code:
                cur.execute("""
                    SELECT s.experiment_config->>'communicationLevel' as communication_level
                    FROM sessions s
                    WHERE s.session_code = %s
                    LIMIT 1
                """, (session_code,))
            else:
                # Fallback to participant-based lookup if session_code not provided
                cur.execute("""
                    SELECT s.experiment_config->>'communicationLevel' as communication_level
                    FROM sessions s
                    JOIN participants p ON s.session_id = p.session_id
                    WHERE p.participant_code = %s
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            # result is a dict (RealDictRow); access by key, not index
            communication_level = (result.get('communication_level') if result else None) or 'chat'
            communication_level = communication_level.lower()
            
        except Exception as e:
            # If we can't get the communication level, default to 'chat' for testing
            print(f"Warning: Could not get communication level for {participant_code}: {e}")
            communication_level = 'chat'  # Default to chat mode
        
        # Check communication level restrictions
        if communication_level == 'no_chat':
            return {
                "success": False,
                "error": "Chat is disabled in this session"
            }
        
        if communication_level == 'chat':
            # In chat mode, only allow messages to individual participants
            if recipient == "all":
                return {
                    "success": False,
                    "error": "Broadcast messaging is disabled in chat mode. Please send messages to individual participants."
                }
        
        if communication_level == 'broadcast':
            # In broadcast mode, only allow messages to "all"
            if recipient != "all":
                return {
                    "success": False,
                    "error": "Direct messaging is disabled. Only broadcast messages to 'all' are allowed."
                }
        
        # Get the appropriate game engine based on experiment type
        game_engine = self._get_game_engine(participant_code, session_code)
        return game_engine.send_message(participant_code, recipient, content, session_code)

    def create_trade_offer(
        self,
        participant_code: str,
        recipient: str,
        offer_type: str,
        shape: str,
        price_per_unit: int,
        session_code: str = None,
    ) -> Dict[str, Any]:
        result = self._engine.create_trade_offer(
            participant_code=participant_code,
            recipient=recipient,
            offer_type=offer_type,
            shape=shape,
            quantity=1,
            price_per_unit=price_per_unit,
            session_code=session_code,
        )
        
        # Note: WebSocket events will be emitted from the main app
        # to avoid circular import issues
        
        return result

    def respond_to_trade_offer(self, participant_code: str, transaction_id: str, response: str, session_code: str = None) -> Dict[str, Any]:
        result = self._engine.respond_to_trade_offer(participant_code, transaction_id, response, session_code)
        
        # Note: WebSocket events will be emitted from the main app
        # to avoid circular import issues
        
        return result



    def cancel_trade_offer(self, participant_code: str, transaction_id: str, session_code: str = None) -> Dict[str, Any]:
        result = self._engine.cancel_trade_offer(participant_code, transaction_id, session_code)
        
        # Note: WebSocket events will be emitted from the main app
        # to avoid circular import issues
        
        return result

    def produce_shape(self, participant_code: str, shape: str, quantity: int = 1, session_code: str = None) -> Dict[str, Any]:
        # Get the appropriate game engine based on experiment type
        game_engine = self._get_game_engine(participant_code, session_code)
        return game_engine.produce_shape(participant_code, shape, quantity, session_code)

    def fulfill_orders(self, participant_code: str, order_indices: List[int], session_code: str = None) -> Dict[str, Any]:
        # Get the appropriate game engine based on experiment type
        game_engine = self._get_game_engine(participant_code, session_code)
        return game_engine.fulfill_orders(participant_code, order_indices, session_code)

    def process_completed_productions(self) -> Dict[str, Any]:
        """Process completed production items and move them to inventory"""
        # Note: This method doesn't have participant_code, so we'll use the base engine
        # This is typically used for system-wide operations
        return self._engine.process_completed_productions()

    # --------- WordGuessing-specific methods ---------

    def get_assigned_words(self, participant_code: str, session_code: str = None) -> Dict[str, Any]:
        """Get assigned words for a hinter participant in WordGuessing experiment"""
        try:
            # Get the appropriate game engine based on experiment type
            game_engine = self._get_game_engine(participant_code, session_code)
            
            # Check if this is a wordguessing experiment
            import psycopg2
            import psycopg2.extras
            
            db_url = self._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            if session_code:
                cur.execute("""
                    SELECT experiment_type FROM sessions 
                    WHERE session_code = %s
                    LIMIT 1
                """, (session_code,))
            else:
                cur.execute("""
                    SELECT s.experiment_type FROM sessions s
                    JOIN participants p ON s.session_id = p.session_id
                    WHERE p.participant_code = %s
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if not result or result.get('experiment_type') != 'wordguessing':
                return {
                    "success": False,
                    "error": "get_assigned_words is only available in WordGuessing experiments"
                }
            
            # Get participant data to check role and assigned words
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT role, assigned_words FROM participants 
                WHERE participant_code = %s
                LIMIT 1
            """, (participant_code,))
            
            participant = cur.fetchone()
            cur.close()
            conn.close()
            
            if not participant:
                return {"success": False, "error": "Participant not found"}
            
            if participant['role'] != 'hinter':
                return {
                    "success": False,
                    "error": "Only hinter participants can access assigned words"
                }
            
            # Parse assigned words
            assigned_words = participant['assigned_words']
            if isinstance(assigned_words, str):
                import json
                try:
                    assigned_words = json.loads(assigned_words)
                except:
                    assigned_words = []
            
            return {
                "success": True,
                "assigned_words": assigned_words
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --------- DayTrader-specific methods ---------

    def make_investment(self, participant_code: str, invest_price: float, invest_decision_type: str = "individual", session_code: str = None) -> Dict[str, Any]:
        """Make an investment decision in the DayTrader experiment"""
        # Check if this is a DayTrader session by looking at the experiment type
        try:
            import psycopg2
            import psycopg2.extras
            
            db_url = self._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            if session_code:
                cur.execute("""
                    SELECT experiment_type FROM sessions 
                    WHERE session_code = %s
                    LIMIT 1
                """, (session_code,))
            else:
                cur.execute("""
                    SELECT s.experiment_type FROM sessions s
                    JOIN participants p ON s.session_id = p.session_id
                    WHERE p.participant_code = %s
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if result and result.get('experiment_type') == 'daytrader':
                # Use DayTrader game engine
                from daytrader_game_engine import DayTraderGameEngine
                daytrader_engine = DayTraderGameEngine(self._engine.db_connection_string)
                return daytrader_engine.make_investment(participant_code, invest_price, invest_decision_type, session_code)
            else:
                return {
                    "success": False,
                    "error": "Investment functionality is only available in DayTrader experiments"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to make investment: {str(e)}"
            }

    def get_investment_history(self, participant_code: str, session_code: str = None) -> Dict[str, Any]:
        """Get investment history for a participant in DayTrader experiment"""
        try:
            import psycopg2
            import psycopg2.extras
            
            db_url = self._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Get participant_id and session_id
            if session_code:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (participant_code, session_code))
            else:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            if not result:
                return {
                    "success": False,
                    "error": f"Participant {participant_code} not found"
                }
            
            participant_id = result['participant_id']
            session_id = result['session_id']
            
            # Get investment history
            cur.execute("""
                SELECT 
                    investment_id,
                    invest_price,
                    invest_decision_type,
                    investment_timestamp,
                    return_amount,
                    profit_loss
                FROM investments 
                WHERE participant_id = %s AND session_id = %s
                ORDER BY investment_timestamp DESC
            """, (participant_id, session_id))
            
            investments = cur.fetchall()
            
            cur.close()
            conn.close()
            
            # Format investment history
            investment_list = []
            for inv in investments:
                investment_list.append({
                    'investment_id': inv['investment_id'],
                    'invest_price': float(inv['invest_price']),
                    'invest_decision_type': inv['invest_decision_type'],
                    'investment_timestamp': inv['investment_timestamp'].isoformat() if inv['investment_timestamp'] else None,
                    'return_amount': float(inv['return_amount']) if inv['return_amount'] else None,
                    'profit_loss': float(inv['profit_loss']) if inv['profit_loss'] else None
                })
            
            return {
                "success": True,
                "investment_history": investment_list,
                "total_investments": len(investment_list)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get investment history: {str(e)}"
            }

    # --------- Essay Ranking-specific methods ---------

    def submit_ranking(self, participant_code: str, rankings: List[Dict[str, Any]], session_code: str = None) -> Dict[str, Any]:
        """Submit essay rankings for a participant in Essay Ranking experiment"""
        try:
            import psycopg2
            import psycopg2.extras
            
            db_url = self._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Get participant_id and session_id
            if session_code:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (participant_code, session_code))
            else:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            if not result:
                return {
                    "success": False,
                    "error": f"Participant {participant_code} not found"
                }
            
            participant_id = result['participant_id']
            session_id = result['session_id']
            
            # Validate rankings
            if not rankings or not isinstance(rankings, list):
                return {
                    "success": False,
                    "error": "Rankings must be a non-empty list"
                }
            
            # Check if all essays are assigned to this session
            essay_ids = [r.get('essay_id') for r in rankings if r.get('essay_id')]
            if not essay_ids:
                return {
                    "success": False,
                    "error": "No valid essay IDs found in rankings"
                }
            
            # Verify essays are assigned to this session
            placeholders = ','.join(['%s'] * len(essay_ids))
            cur.execute(f"""
                SELECT essay_id FROM essay_assignments 
                WHERE session_id = %s AND essay_id IN ({placeholders})
            """, [session_id] + essay_ids)
            
            assigned_essays = cur.fetchall()
            assigned_essay_ids = [e['essay_id'] for e in assigned_essays]
            
            if len(assigned_essay_ids) != len(essay_ids):
                missing_essays = set(essay_ids) - set(assigned_essay_ids)
                return {
                    "success": False,
                    "error": f"Some essays are not assigned to this session: {missing_essays}"
                }
            
            # Validate ranking format and uniqueness
            ranks = [r.get('rank') for r in rankings if r.get('rank') is not None]
            if len(ranks) != len(set(ranks)):
                return {
                    "success": False,
                    "error": "Rank numbers must be unique"
                }
            
            # Use EssayRankingGameEngine to submit rankings
            from essayranking_game_engine import EssayRankingGameEngine
            essay_engine = EssayRankingGameEngine(self._engine.db_connection_string)
            
            # Format rankings for the game engine
            formatted_rankings = []
            for ranking in rankings:
                formatted_rankings.append({
                    'essay_id': ranking.get('essay_id'),
                    'rank': int(ranking.get('rank', 0)),
                    'reasoning': ranking.get('reasoning', '')
                })
            
            result = essay_engine.submit_ranking(participant_code, formatted_rankings, session_code)
            
            cur.close()
            conn.close()
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to submit ranking: {str(e)}"
            }

    def get_assigned_essays(self, participant_code: str, session_code: str = None) -> Dict[str, Any]:
        """Get essays assigned to a participant in Essay Ranking experiment"""
        try:
            import psycopg2
            import psycopg2.extras
            
            db_url = self._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Get participant_id and session_id
            if session_code:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (participant_code, session_code))
            else:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            if not result:
                return {
                    "success": False,
                    "error": f"Participant {participant_code} not found"
                }
            
            session_id = result['session_id']
            
            # Get assigned essays for this session with content
            cur.execute("""
                SELECT 
                    ea.essay_id,
                    ea.essay_title,
                    ea.essay_filename,
                    ea.essay_content,
                    ea.essay_metadata,
                    ea.created_at
                FROM essay_assignments ea
                WHERE ea.session_id = %s
                ORDER BY ea.created_at ASC
            """, (session_id,))
            
            essays = cur.fetchall()
            
            cur.close()
            conn.close()
            
            # Format essay list with content
            essay_list = []
            for essay in essays:
                essay_data = {
                    'essay_id': essay['essay_id'],
                    'title': essay['essay_title'],
                    'filename': essay['essay_filename'],
                    'content': essay['essay_content'],
                    'has_content': bool(essay['essay_content'] and essay['essay_content'].strip()),
                    'assigned_at': essay['created_at'].isoformat() if essay['created_at'] else None
                }
                
                # Parse metadata if available
                if essay['essay_metadata']:
                    try:
                        import json
                        metadata = json.loads(essay['essay_metadata']) if isinstance(essay['essay_metadata'], str) else essay['essay_metadata']
                        essay_data.update({
                            'word_count': metadata.get('word_count', 0),
                            'character_count': metadata.get('character_count', 0),
                            'estimated_reading_time_minutes': metadata.get('estimated_reading_time_minutes', 1),
                            'extraction_successful': metadata.get('extraction_successful', False)
                        })
                    except (json.JSONDecodeError, TypeError):
                        essay_data['extraction_successful'] = False
                else:
                    essay_data['extraction_successful'] = False
                
                essay_list.append(essay_data)
            
            return {
                "success": True,
                "essays": essay_list,
                "total_essays": len(essay_list)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get assigned essays: {str(e)}"
            }

    def get_essay_content(self, participant_code: str, essay_id: str, session_code: str = None) -> Dict[str, Any]:
        """Get the full content of a specific essay for a participant in Essay Ranking experiment"""
        try:
            import psycopg2
            import psycopg2.extras
            
            db_url = self._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Get participant_id and session_id
            if session_code:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (participant_code, session_code))
            else:
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            if not result:
                return {
                    "success": False,
                    "error": f"Participant {participant_code} not found"
                }
            
            session_id = result['session_id']
            
            # Get the specific essay content
            cur.execute("""
                SELECT 
                    ea.essay_id,
                    ea.essay_title,
                    ea.essay_filename,
                    ea.essay_content,
                    ea.essay_metadata
                FROM essay_assignments ea
                WHERE ea.session_id = %s AND ea.essay_id = %s
            """, (session_id, essay_id))
            
            essay = cur.fetchone()
            
            cur.close()
            conn.close()
            
            if not essay:
                return {
                    "success": False,
                    "error": f"Essay {essay_id} not found in this session"
                }
            
            # Format essay data
            essay_data = {
                'essay_id': essay['essay_id'],
                'title': essay['essay_title'],
                'filename': essay['essay_filename'],
                'content': essay['essay_content'],
                'has_content': bool(essay['essay_content'] and essay['essay_content'].strip())
            }
            
            # Parse metadata if available
            if essay['essay_metadata']:
                try:
                    import json
                    metadata = json.loads(essay['essay_metadata']) if isinstance(essay['essay_metadata'], str) else essay['essay_metadata']
                    essay_data.update({
                        'word_count': metadata.get('word_count', 0),
                        'character_count': metadata.get('character_count', 0),
                        'estimated_reading_time_minutes': metadata.get('estimated_reading_time_minutes', 1),
                        'extraction_successful': metadata.get('extraction_successful', False)
                    })
                except (json.JSONDecodeError, TypeError):
                    essay_data['extraction_successful'] = False
            else:
                essay_data['extraction_successful'] = False
            
            return {
                "success": True,
                "essay": essay_data
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get essay content: {str(e)}"
            }

    # --------- WordGuessing-specific methods ---------


    def get_assigned_words(self, participant_code: str, session_code: str = None) -> Dict[str, Any]:
        """Get assigned words for a hinter participant in WordGuessing experiment"""
        try:
            import psycopg2
            import psycopg2.extras
            
            db_url = self._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # Get participant data including role and assigned_words
            if session_code:
                cur.execute("""
                    SELECT participant_id, session_id, role, assigned_words FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (participant_code, session_code))
            else:
                cur.execute("""
                    SELECT participant_id, session_id, role, assigned_words FROM participants 
                    WHERE participant_code = %s
                    ORDER BY last_activity_timestamp DESC NULLS LAST, created_at DESC
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            if not result:
                return {
                    "success": False,
                    "error": f"Participant {participant_code} not found"
                }
            
            # Only hinters have assigned words
            if result['role'] != 'hinter':
                return {
                    "success": False,
                    "error": f"Only hinters have assigned words. Participant {participant_code} is a {result['role']}"
                }
            
            # Parse assigned words
            assigned_words = result['assigned_words'] or []
            if isinstance(assigned_words, str):
                try:
                    import json
                    assigned_words = json.loads(assigned_words)
                except (json.JSONDecodeError, TypeError):
                    assigned_words = []
            
            cur.close()
            conn.close()
            
            return {
                "success": True,
                "assigned_words": assigned_words,
                "total_words": len(assigned_words),
                "participant_role": result['role']
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get assigned words: {str(e)}"
            }

    def mark_messages_as_read(self, participant_code: str, message_ids: List[str] = None, session_code: str = None) -> Dict[str, Any]:
        """Mark unread messages as read for this agent."""
        try:
            import psycopg2
            import psycopg2.extras
            
            db_url = self._engine.db_connection_string
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            
            # CRITICAL FIX: Use session_code for proper session isolation
            if session_code:
                # Get participant_id for this agent in the specific session
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s AND session_code = %s
                    LIMIT 1
                """, (participant_code, session_code))
            else:
                # Fallback to participant-based lookup if session_code not provided
                cur.execute("""
                    SELECT participant_id, session_id FROM participants 
                    WHERE participant_code = %s
                    LIMIT 1
                """, (participant_code,))
            
            result = cur.fetchone()
            
            if not result:
                return {
                    "success": False,
                    "error": f"Participant {participant_code} not found"
                }
            
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
            
            rows_updated = cur.rowcount
            conn.commit()
            
            cur.close()
            conn.close()
            
            return {
                "success": True,
                "message": f"Marked {rows_updated} messages as read",
                "messages_marked": rows_updated
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to mark messages as read: {str(e)}"
            }

    # --------- Tool schema generation for LLMs ---------

    def get_tools_spec(self, api_provider: str = 'openai') -> List[Dict[str, Any]]:
        """Return tool specification in the format required by the specified API provider."""
        base_tools = [
            {
                "name": "get_game_state",
                "description": "Get current game state including private (money, inventory, orders) and public (round, time, others).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"}
                    },
                    "required": ["participant_code"],
                },
            },
            {
                "name": "send_message",
                "description": "Send a chat message to another participant or 'all'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                        "recipient": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["participant_code", "recipient", "content"],
                },
            },
            {
                "name": "create_trade_offer",
                "description": "Create a trade offer (buy or sell) for a specific recipient.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                        "recipient": {"type": "string"},
                        "offer_type": {"type": "string", "enum": ["buy", "sell"]},
                        "shape": {"type": "string", "enum": ["circle", "square", "triangle", "diamond", "pentagon"]},
                        "price_per_unit": {"type": "integer", "minimum": 1},
                    },
                    "required": [
                        "participant_code",
                        "recipient",
                        "offer_type",
                        "shape",
                        "price_per_unit",
                    ],
                },
            },
            {
                "name": "respond_to_trade_offer",
                "description": "Respond to a trade offer by transaction_id (accept or reject). Use the simplified ID format (e.g., S123-001) from pending offers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                        "transaction_id": {"type": "string", "description": "Transaction ID in simplified format (e.g., S123-001) from pending offers"},
                        "response": {"type": "string", "enum": ["accept", "reject"]},
                    },
                    "required": ["participant_code", "transaction_id", "response"],
                },
            },
            {
                "name": "cancel_trade_offer",
                "description": "Cancel a trade offer that you proposed. Use the simplified ID format (e.g., S123-001) from pending offers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                        "transaction_id": {"type": "string", "description": "Transaction ID in simplified format (e.g., S123-001) from pending offers"},
                    },
                    "required": ["participant_code", "transaction_id"],
                },
            },
            {
                "name": "produce_shape",
                "description": "Produce shapes. Specialty shapes cost less than regular shapes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                        "shape": {"type": "string", "enum": ["circle", "square", "triangle", "diamond", "pentagon"]},
                        "quantity": {"type": "integer", "minimum": 1},
                    },
                    "required": ["participant_code", "shape"],
                },
            },
            {
                "name": "fulfill_orders",
                "description": "Fulfill orders using shapes from inventory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                        "order_indices": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["participant_code", "order_indices"],
                },
            },
            {
                "name": "process_completed_productions",
                "description": "Process completed production items and move them to inventory.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "mark_messages_as_read",
                "description": "Mark unread messages as read for this agent. Use this when you want to acknowledge that you have seen and processed the messages.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                        "message_ids": {"type": "array", "items": {"type": "string"}, "description": "Optional: specific message IDs to mark as read. If not provided, marks all unread messages as read."},
                    },
                    "required": ["participant_code"],
                },
            },
            {
                "name": "make_investment",
                "description": "Make an investment decision in the DayTrader experiment. Only available in DayTrader sessions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                        "invest_price": {"type": "number", "description": "The price at which to make the investment"},
                        "invest_decision_type": {"type": "string", "enum": ["individual", "group"], "description": "Whether this is an individual or group investment decision"},
                    },
                    "required": ["participant_code", "invest_price", "invest_decision_type"],
                },
            },
            {
                "name": "get_investment_history",
                "description": "Get investment history for a participant in DayTrader experiment. Only available in DayTrader sessions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                    },
                    "required": ["participant_code"],
                },
            },
            {
                "name": "submit_ranking",
                "description": "Submit essay rankings for a participant in Essay Ranking experiment. Only available in Essay Ranking sessions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                        "rankings": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "essay_id": {"type": "string", "description": "ID of the essay being ranked"},
                                    "rank": {"type": "integer", "description": "Rank number (1 = best, higher numbers = worse)"},
                                    "reasoning": {"type": "string", "description": "Reasoning for this ranking"}
                                },
                                "required": ["essay_id", "rank"]
                            },
                            "description": "List of essay rankings with essay_id, rank, and reasoning"
                        },
                    },
                    "required": ["participant_code", "rankings"],
                },
            },
            {
                "name": "get_assigned_essays",
                "description": "Get essays assigned to a participant in Essay Ranking experiment. Only available in Essay Ranking sessions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                    },
                    "required": ["participant_code"],
                },
            },
            {
                "name": "get_essay_content",
                "description": "Get the full content of a specific essay for reading and evaluation. Only available in Essay Ranking sessions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                        "essay_id": {"type": "string", "description": "ID of the essay to get content for"},
                    },
                    "required": ["participant_code", "essay_id"],
                },
            },
            {
                "name": "get_assigned_words",
                "description": "Get the words assigned to you as a hinter. Only available in WordGuessing sessions and only for hinter role.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_code": {"type": "string"},
                    },
                    "required": ["participant_code"],
                },
            },
        ]

        if api_provider == 'anthropic':
            # Convert to Anthropic/Claude format
            return [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool["parameters"],
                }
                for tool in base_tools
            ]
        
        # Default to OpenAI format
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                }
            }
            for tool in base_tools
        ]
    
    def get_openai_tools_spec(self) -> List[Dict[str, Any]]:
        """Return OpenAI function-calling tool specification for these tools."""
        return self.get_tools_spec(api_provider='openai')

    # --------- Generic dispatcher to execute a tool call dict ---------

    def execute_tool_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool by name with provided arguments."""
        if name == "get_game_state":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.get_game_state(arguments["participant_code"], session_code)
        if name == "send_message":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.send_message(arguments["participant_code"], arguments["recipient"], arguments["content"], session_code)
        if name == "create_trade_offer":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.create_trade_offer(
                arguments["participant_code"],
                arguments["recipient"],
                arguments["offer_type"],
                arguments["shape"],
                int(arguments["price_per_unit"]),
                session_code,
            )
        if name == "respond_to_trade_offer":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.respond_to_trade_offer(
                arguments["participant_code"], arguments["transaction_id"], arguments["response"], session_code
            )

        if name == "cancel_trade_offer":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.cancel_trade_offer(
                arguments["participant_code"], arguments["transaction_id"], session_code
            )
        if name == "produce_shape":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.produce_shape(
                arguments["participant_code"], arguments["shape"], int(arguments.get("quantity", 1)), session_code
            )
        if name == "fulfill_orders":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            order_indices = arguments.get("order_indices") or []
            return self.fulfill_orders(arguments["participant_code"], [int(i) for i in order_indices], session_code)
        elif name == "process_completed_productions":
            return self.process_completed_productions()
        elif name == "mark_messages_as_read":
            message_ids = arguments.get("message_ids")
            session_code = arguments.get("session_code") # Extract session_code from arguments
            return self.mark_messages_as_read(arguments["participant_code"], message_ids, session_code)
        elif name == "make_investment":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.make_investment(
                arguments["participant_code"], 
                float(arguments["invest_price"]), 
                arguments["invest_decision_type"], 
                session_code
            )
        elif name == "get_investment_history":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.get_investment_history(arguments["participant_code"], session_code)
        elif name == "submit_ranking":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.submit_ranking(arguments["participant_code"], arguments["rankings"], session_code)
        elif name == "get_assigned_essays":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.get_assigned_essays(arguments["participant_code"], session_code)
        elif name == "get_essay_content":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.get_essay_content(arguments["participant_code"], arguments["essay_id"], session_code)
        elif name == "get_assigned_words":
            # CRITICAL FIX: Extract session_code from arguments if available for proper session isolation
            session_code = arguments.get("session_code")
            return self.get_assigned_words(arguments["participant_code"], session_code)
        else:
            return {
                "success": False,
                "error": f"Unknown tool: {name}"
            }


# Convenience factory

def create_tools(database_url: Optional[str] = None) -> AgentTools:
    return AgentTools(database_url)
