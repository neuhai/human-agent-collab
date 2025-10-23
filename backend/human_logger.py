import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor


def get_session_code_from_id(session_id: str) -> Optional[str]:
    """Get session_code from session_id for logging purposes"""
    try:
        # Import here to avoid circular imports
        from app import get_db_connection
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT session_code FROM sessions WHERE session_id = %s", (session_id,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return result[0] if result else None
    except Exception as e:
        print(f"[ERROR] Failed to get session_code from session_id {session_id}: {e}")
        return None


class HumanLogger:
    """Logger for human participant behaviors, similar to agent logging"""
    
    def __init__(self, participant_code: str, session_id: Optional[str] = None, session_code: Optional[str] = None):
        self.participant_code = participant_code
        self.session_id = session_id
        self.session_code = session_code
        
        # Set up logging directory with session-based organization
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(base_dir, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Use session_code for folder name (more readable than session_id)
        # If session_code is not provided but session_id is, try to get session_code
        if not self.session_code and self.session_id:
            self.session_code = get_session_code_from_id(self.session_id)
        
        # Always create session-specific folder
        # If session_code is available, use it; otherwise fall back to session_id or default
        if self.session_code:
            session_dir = os.path.join(logs_dir, self.session_code)
        elif self.session_id:
            session_dir = os.path.join(logs_dir, self.session_id)
        else:
            # Use a default session folder for cases where neither is provided
            session_dir = os.path.join(logs_dir, "unknown_session")
            print(f"[WARNING] No session_id or session_code provided for {participant_code}, using default session folder")
        
        # Create session directory
        os.makedirs(session_dir, exist_ok=True)
        
        # Format: logs/<session_code>/human_<participant_code>.log
        self._log_path = os.path.join(session_dir, f"human_{participant_code}.log")
        
        # Create/clear log file
        try:
            session_identifier = self.session_code or self.session_id or 'unknown'
            with open(self._log_path, "w") as f:
                f.write(f"Human {participant_code} (session: {session_identifier}) initialized at {datetime.now()}\n")
            print(f"[INIT] Human log: {self._log_path}")
        except Exception as e:
            print(f"[INIT ERROR] Failed to create human log file: {e}")
    
    def log(self, msg: str):
        """Write human activity to log file"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._log_path, "a") as f:
                f.write(f"[{timestamp}] {msg}\n")
        except Exception as e:
            print(f"[LOG ERROR] {self.participant_code}: {e}")
    
    def log_action(self, action: str, success: bool = True, error_message: str = None, details: Dict[str, Any] = None):
        """Log a specific action in the same format as agent logging"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Format the log entry to match agent format: action -> ok/fail | error_message
            status = "ok" if success else "fail"
            log_entry = f"[{timestamp}] {action} -> {status}"
            
            # Add error message if present
            if error_message:
                log_entry += f" | {error_message}"
            
            with open(self._log_path, "a") as f:
                f.write(log_entry + "\n")
            
            # If we have details, log them as a separate "Tool calls" entry like agents do
            if details:
                try:
                    details_str = json.dumps(details, ensure_ascii=False, default=str)
                    with open(self._log_path, "a") as f:
                        f.write(f"[{timestamp}] Tool calls: {details_str}\n")
                except Exception as e:
                    print(f"[LOG ERROR] {self.participant_code}: Failed to log details: {e}")
                
        except Exception as e:
            print(f"[LOG ERROR] {self.participant_code}: {e}")
    
    def log_production(self, shape: str, quantity: int, success: bool, error_message: str = None):
        """Log production action"""
        details = {
            "participant_code": self.participant_code,
            "shape": shape,
            "quantity": quantity
        }
        self.log_action("produce_shape", success, error_message, details)
    
    def log_order_fulfillment(self, order_indices: list, orders_fulfilled: int, score_gained: int, success: bool, error_message: str = None):
        """Log order fulfillment action"""
        details = {
            "participant_code": self.participant_code,
            "order_indices": order_indices,
            "orders_fulfilled": orders_fulfilled,
            "score_gained": score_gained
        }
        self.log_action("fulfill_orders", success, error_message, details)
    
    def log_trade_offer(self, recipient: str, offer_type: str, shape: str, quantity: int, price: float, success: bool, error_message: str = None):
        """Log trade offer creation"""
        details = {
            "participant_code": self.participant_code,
            "recipient": recipient,
            "offer_type": offer_type,
            "shape": shape,
            "quantity": quantity,
            "price_per_unit": price
        }
        self.log_action("create_trade_offer", success, error_message, details)
    
    def log_trade_response(self, transaction_id: str, response: str, success: bool, error_message: str = None):
        """Log trade offer response"""
        details = {
            "participant_code": self.participant_code,
            "transaction_id": transaction_id,
            "response": response
        }
        self.log_action("respond_to_trade_offer", success, error_message, details)
    
    def log_trade_cancellation(self, transaction_id: str, success: bool, error_message: str = None):
        """Log trade offer cancellation"""
        details = {
            "participant_code": self.participant_code,
            "transaction_id": transaction_id
        }
        self.log_action("cancel_trade_offer", success, error_message, details)
    
    def log_message(self, recipient: str, content: str, success: bool, error_message: str = None):
        """Log message sending"""
        details = {
            "participant_code": self.participant_code,
            "recipient": recipient,
            "content": content
        }
        self.log_action("send_message", success, error_message, details)
    
    def log_login(self, session_code: str):
        """Log participant login"""
        details = {
            "participant_code": self.participant_code,
            "session_code": session_code
        }
        self.log_action("login", True, None, details)
    
    def log_logout(self):
        """Log participant logout"""
        details = {
            "participant_code": self.participant_code
        }
        self.log_action("logout", True, None, details)
    
    def log_investment(self, invest_price: float, invest_decision_type: str, success: bool, error_message: str = None):
        """Log investment action for DayTrader"""
        details = {
            "participant_code": self.participant_code,
            "invest_price": invest_price,
            "invest_decision_type": invest_decision_type
        }
        self.log_action("make_investment", success, error_message, details)
    



# Global logger instances cache
_human_loggers = {}


def get_human_logger(participant_code: str, session_id: Optional[str] = None, session_code: Optional[str] = None) -> HumanLogger:
    """Get or create a human logger instance for the given participant"""
    # Use session_code if available, otherwise fall back to session_id
    # If neither is provided, use a default to prevent logs in main directory
    effective_session_id = session_id if session_id else "unknown_session"
    effective_session_code = session_code
    
    # Create a unique key that includes both session_id and session_code if available
    key = f"{participant_code}_{effective_session_code or effective_session_id}"
    
    if key not in _human_loggers:
        _human_loggers[key] = HumanLogger(participant_code, effective_session_id, effective_session_code)
    
    return _human_loggers[key]


def stop_human_logging_for_session(session_code: str) -> dict:
    """Stop logging for all human participants in a specific session"""
    try:
        stopped_count = 0
        
        # Find all human loggers for this session and add final log entry
        keys_to_remove = []
        for key, logger in _human_loggers.items():
            if logger.session_code == session_code:
                # Add final log entry indicating session end
                logger.log(f"Session {session_code} ended - logging stopped")
                keys_to_remove.append(key)
                stopped_count += 1
                print(f"[STOP] Stopped logging for human participant: {logger.participant_code} (session: {session_code})")
        
        # Remove the loggers from the cache to prevent further logging
        for key in keys_to_remove:
            del _human_loggers[key]
        
        return {'success': True, 'stopped_loggers': stopped_count}
        
    except Exception as e:
        print(f"[ERROR] Failed to stop human logging for session {session_code}: {e}")
        return {'success': False, 'error': str(e)}


def cleanup_human_logs():
    """Delete human-related log files under backend/logs and session folders."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(base_dir, 'logs')
        
        if not os.path.exists(logs_dir):
            return
        
        deleted_count = 0
        
        # Clean up logs in the main logs directory (legacy fallback logs without session)
        for name in os.listdir(logs_dir):
            if name.startswith('human_') and name.endswith('.log'):
                file_path = os.path.join(logs_dir, name)
                os.remove(file_path)
                print(f"Deleted human log: {name}")
                deleted_count += 1
        
        # Clean up logs in session folders (including unknown_session)
        for item in os.listdir(logs_dir):
            item_path = os.path.join(logs_dir, item)
            if os.path.isdir(item_path):
                # This is a session folder
                for name in os.listdir(item_path):
                    if name.startswith('human_') and name.endswith('.log'):
                        file_path = os.path.join(item_path, name)
                        os.remove(file_path)
                        print(f"Deleted human log: {item}/{name}")
                        deleted_count += 1
                
                # Remove empty session folders (but keep unknown_session for future use)
                if not os.listdir(item_path) and item != "unknown_session":
                    os.rmdir(item_path)
                    print(f"Removed empty session folder: {item}")
        
        if deleted_count == 0:
            print("No human logs found to clean up")
        else:
            print(f"Cleaned up {deleted_count} human log files")
                
    except Exception as e:
        print(f"Error cleaning up human logs: {e}")
