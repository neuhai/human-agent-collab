"""
Timer Service: Manages countdown timers for experiment sessions.
"""
import threading
import time
from datetime import datetime
from typing import Dict, Optional

# Global timer storage: session_id -> TimerService instance
_timers: Dict[str, 'TimerService'] = {}
_timers_lock = threading.Lock()


class TimerService:
    """Manages countdown timer for a session"""
    
    def __init__(self, session_id: str, duration_seconds: int):
        self.session_id = session_id
        self.initial_duration = duration_seconds
        self.remaining_seconds = duration_seconds
        self.is_running = False
        self.is_paused = False
        self.timer_thread: Optional[threading.Thread] = None
        self.paused_at: Optional[float] = None  # Timestamp when paused
        self.started_at: Optional[float] = None  # Timestamp when started
        self.elapsed_while_paused = 0  # Total time paused
    
    def start(self):
        """Start the timer"""
        if self.is_running:
            return
        
        now = time.time()
        
        # If resuming from pause, adjust elapsed time
        if self.is_paused and self.paused_at:
            self.elapsed_while_paused += (now - self.paused_at)
            self.paused_at = None
        
        # If starting fresh, set started_at
        if self.started_at is None:
            self.started_at = now
        
        self.is_running = True
        self.is_paused = False
        
        # Start countdown thread if not already running
        if self.timer_thread is None or not self.timer_thread.is_alive():
            self.timer_thread = threading.Thread(target=self._countdown, daemon=True)
            self.timer_thread.start()
            print(f'[TimerService] Started timer for session {self.session_id}, duration: {self.initial_duration}s')
    
    def pause(self):
        """Pause the timer"""
        if not self.is_running or self.is_paused:
            return
        
        self.is_paused = True
        self.paused_at = time.time()
        print(f'[TimerService] Paused timer for session {self.session_id}')
    
    def resume(self):
        """Resume the timer"""
        if not self.is_paused:
            # If not paused but not running, start it
            if not self.is_running:
                self.start()
            return
        
        self.is_paused = False
        self.is_running = True  # Ensure is_running is True when resuming
        if self.paused_at:
            # Calculate elapsed time while paused
            now = time.time()
            self.elapsed_while_paused += (now - self.paused_at)
            self.paused_at = None
        
        # Ensure timer thread is running
        if self.timer_thread is None or not self.timer_thread.is_alive():
            self.timer_thread = threading.Thread(target=self._countdown, daemon=True)
            self.timer_thread.start()
        
        print(f'[TimerService] Resumed timer for session {self.session_id}, is_running={self.is_running}, is_paused={self.is_paused}')
    
    def reset(self, new_duration: Optional[int] = None):
        """Reset the timer"""
        self.is_running = False
        self.is_paused = False
        self.paused_at = None
        self.started_at = None
        self.elapsed_while_paused = 0
        
        if new_duration is not None:
            self.initial_duration = new_duration
            self.remaining_seconds = new_duration
        else:
            self.remaining_seconds = self.initial_duration
        
        print(f'[TimerService] Reset timer for session {self.session_id}, duration: {self.remaining_seconds}s')
    
    def stop(self):
        """Stop the timer completely"""
        self.is_running = False
        self.is_paused = False
        print(f'[TimerService] Stopped timer for session {self.session_id}')
    
    def _countdown(self):
        """Countdown loop"""
        last_broadcast_time = time.time()
        broadcast_interval = 1.0  # Broadcast every second
        
        while self.is_running:
            try:
                # If paused, wait and continue
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                
                # Calculate elapsed time
                now = time.time()
                if self.started_at:
                    elapsed = (now - self.started_at) - self.elapsed_while_paused
                    self.remaining_seconds = max(0, int(self.initial_duration - elapsed))
                else:
                    # Fallback: decrement by 1 each second
                    time.sleep(1)
                    self.remaining_seconds = max(0, self.remaining_seconds - 1)
                
                # Broadcast update every second
                if now - last_broadcast_time >= broadcast_interval:
                    self._broadcast_update()
                    last_broadcast_time = now
                
                # Check if timer expired
                if self.remaining_seconds <= 0:
                    self.remaining_seconds = 0
                    self._on_timeout()
                    break
                
                # Sleep for a short interval to avoid busy waiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f'[TimerService] Error in countdown loop for session {self.session_id}: {e}')
                import traceback
                traceback.print_exc()
                time.sleep(1)
    
    def _broadcast_update(self):
        """Broadcast timer update via WebSocket"""
        try:
            from websocket.handlers import get_socketio
            from routes.session import sessions
            
            socketio = get_socketio()
            
            # Update session's remaining_seconds
            session_key = None
            found_session = None
            
            # Try to find session by session_id
            for sid, session in sessions.items():
                if session.get('session_id') == self.session_id or sid == self.session_id:
                    found_session = session
                    session_key = sid
                    break
            
            if found_session:
                found_session['remaining_seconds'] = self.remaining_seconds
                sessions[session_key] = found_session
            
            # Broadcast timer update
            socketio.emit('timer_update', {
                'session_id': self.session_id,
                'remaining_seconds': self.remaining_seconds,
                'formatted': self._format_time(self.remaining_seconds),
                'is_running': self.is_running and not self.is_paused,
                'is_paused': self.is_paused
            }, room=self.session_id)
            
        except Exception as e:
            print(f'[TimerService] Error broadcasting timer update: {e}')
    
    def _format_time(self, seconds: int) -> str:
        """Format seconds as MM:SS"""
        minutes = seconds // 60
        secs = seconds % 60
        return f'{minutes:02d}:{secs:02d}'
    
    def _on_timeout(self):
        """Called when timer reaches zero"""
        try:
            from routes.session import sessions
            from websocket.handlers import broadcast_participant_update, get_socketio
            
            # Emit final timer_update with remaining_seconds=0 so frontend receives it
            # (the countdown loop breaks before _broadcast_update, so we'd otherwise never send 0)
            try:
                socketio = get_socketio()
                socketio.emit('timer_update', {
                    'session_id': self.session_id,
                    'remaining_seconds': 0,
                    'formatted': '00:00',
                    'is_running': False,
                    'is_paused': True
                }, room=self.session_id)
            except Exception as e:
                print(f'[TimerService] Error emitting final timer_update: {e}')
            
            # Find and update session status
            session_key = None
            found_session = None
            
            for sid, session in sessions.items():
                if session.get('session_id') == self.session_id or sid == self.session_id:
                    found_session = session
                    session_key = sid
                    break
            
            if found_session:
                # Auto-pause session when timer expires
                found_session['status'] = 'paused'
                found_session['remaining_seconds'] = 0
                sessions[session_key] = found_session
                
                # For hiddenprofile experiment, if no human participants, trigger final vote for all agents
                experiment_type = found_session.get('experiment_type')
                if experiment_type == 'hiddenprofile':
                    participants = found_session.get('participants', [])
                    has_human_participant = any(
                        p.get('type', '').lower() not in ['ai', 'ai_agent'] 
                        for p in participants
                    )
                    
                    if not has_human_participant:
                        from agent.agent_runner import get_agent_runner
                        import threading
                        import time
                        
                        def trigger_final_votes():
                            time.sleep(0.5)  # Small delay to ensure session status is updated
                            for participant in participants:
                                participant_type = participant.get('type', '').lower()
                                if participant_type == 'ai':
                                    runner = get_agent_runner(participant.get('id'), self.session_id)
                                    if runner:
                                        runner._trigger_vote('final', participant, found_session, session_key)
                                        print(f'[TimerService] Triggered final vote for agent {participant.get("id")} (no human participants)')
                        
                        threading.Thread(target=trigger_final_votes, daemon=True).start()
                
                # Broadcast status change
                broadcast_participant_update(
                    session_id=self.session_id,
                    participants=found_session.get('participants', []),
                    session_info=found_session,
                    update_type='timer_expired'
                )
                
                print(f'[TimerService] Timer expired for session {self.session_id}, auto-paused')
            
            self.is_running = False
            
        except Exception as e:
            print(f'[TimerService] Error handling timeout: {e}')
            import traceback
            traceback.print_exc()
    
    def get_remaining_seconds(self) -> int:
        """Get current remaining seconds"""
        return self.remaining_seconds


def get_timer(session_id: str) -> Optional[TimerService]:
    """Get timer service for a session"""
    with _timers_lock:
        return _timers.get(session_id)


def create_timer(session_id: str, duration_seconds: int) -> TimerService:
    """Create a new timer service for a session"""
    with _timers_lock:
        if session_id in _timers:
            # Stop existing timer if any
            _timers[session_id].stop()
        
        timer = TimerService(session_id, duration_seconds)
        _timers[session_id] = timer
        return timer


def start_timer(session_id: str):
    """Start timer for a session"""
    with _timers_lock:
        timer = _timers.get(session_id)
        if timer:
            timer.start()


def pause_timer(session_id: str):
    """Pause timer for a session"""
    with _timers_lock:
        timer = _timers.get(session_id)
        if timer:
            timer.pause()


def resume_timer(session_id: str):
    """Resume timer for a session"""
    with _timers_lock:
        timer = _timers.get(session_id)
        if timer:
            timer.resume()


def reset_timer(session_id: str, new_duration: Optional[int] = None):
    """Reset timer for a session"""
    with _timers_lock:
        timer = _timers.get(session_id)
        if timer:
            timer.reset(new_duration)


def stop_timer(session_id: str):
    """Stop timer for a session"""
    with _timers_lock:
        timer = _timers.get(session_id)
        if timer:
            timer.stop()
            del _timers[session_id]
