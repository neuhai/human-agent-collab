"""
Production service to handle completion of shape production.
Periodically checks in_production items and moves completed items to inventory.
"""
import threading
import time
from datetime import datetime
from websocket.handlers import broadcast_participant_update
import routes.session as session_module


class ProductionService:
    """Service to monitor and complete shape production"""
    
    def __init__(self, check_interval=1.0):
        """
        Initialize production service.
        
        Args:
            check_interval: How often to check for completed productions (in seconds)
        """
        self.check_interval = check_interval
        self.is_running = False
        self.thread = None
    
    def start(self):
        """Start the production monitoring thread"""
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._monitor_productions, daemon=True)
        self.thread.start()
        print('[ProductionService] Started production monitoring')
    
    def stop(self):
        """Stop the production monitoring thread"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print('[ProductionService] Stopped production monitoring')
    
    def _monitor_productions(self):
        """Monitor all sessions for completed productions"""
        while self.is_running:
            try:
                self._check_all_sessions()
            except Exception as e:
                print(f'[ProductionService] Error checking productions: {e}')
            
            time.sleep(self.check_interval)
    
    def _check_all_sessions(self):
        """Check all sessions for completed productions"""
        sessions = session_module.sessions
        
        # Import here to avoid circular import
        from routes.participant import update_participant_experiment_params
        
        for session_key, session in sessions.items():
            participants = session.get('participants', [])
            updated = False
            
            for participant in participants:
                if self._check_participant_productions(participant):
                    # Recalculate interface config after updating experiment_params
                    # This ensures frontend gets updated values for money, inventory, etc.
                    update_participant_experiment_params(participant, session)
                    updated = True
            
            # Update session storage after modifications
            if updated:
                sessions[session_key] = session
                session_id = session.get('session_id') or session_key
                broadcast_participant_update(
                    session_id=session_id,
                    participants=participants,
                    session_info=session,
                    update_type='partial'
                )
    
    def _check_participant_productions(self, participant):
        """
        Check and complete productions for a single participant.
        
        Returns:
            True if participant was updated, False otherwise
        """
        exp_params = participant.get('experiment_params', {})
        in_production = exp_params.get('in_production', [])
        inventory = exp_params.get('inventory', [])
        
        if not isinstance(in_production, list) or len(in_production) == 0:
            return False
        
        now = datetime.now()
        completed_items = []
        remaining_items = []
        
        # Check each production item
        for item in in_production:
            if not isinstance(item, dict):
                continue
            
            completion_time_str = item.get('completion_time')
            if not completion_time_str:
                # Skip items without completion time
                remaining_items.append(item)
                continue
            
            try:
                completion_time = datetime.fromisoformat(completion_time_str)
                if now >= completion_time:
                    # Production is complete
                    completed_items.append(item)
                else:
                    # Still in production
                    remaining_items.append(item)
            except (ValueError, TypeError) as e:
                print(f'[ProductionService] Error parsing completion_time: {e}')
                remaining_items.append(item)
        
        # If any items completed, update participant
        if completed_items:
            # Move completed shapes to inventory
            if not isinstance(inventory, list):
                inventory = []
            
            for item in completed_items:
                shape = item.get('shape')
                if shape:
                    inventory.append(shape)
            
            # Increment production_number (total completed count)
            production_number = exp_params.get('production_number', 0)
            exp_params['production_number'] = production_number + len(completed_items)
            
            # Update participant
            exp_params['in_production'] = remaining_items
            exp_params['inventory'] = inventory
            participant['experiment_params'] = exp_params
            
            print(f'[ProductionService] Completed {len(completed_items)} production(s) for participant {participant.get("id")}')
            return True
        
        return False


# Global instance
_production_service = None


def get_production_service():
    """Get the global production service instance"""
    global _production_service
    if _production_service is None:
        _production_service = ProductionService()
    return _production_service


def start_production_service():
    """Start the production service"""
    service = get_production_service()
    service.start()


def stop_production_service():
    """Stop the production service"""
    global _production_service
    if _production_service:
        _production_service.stop()

