"""
WebSocket handlers for real-time communication
"""
from flask import request
from flask_socketio import emit, join_room, leave_room
from datetime import datetime
import uuid

# Store active connections (session_id -> set of socket_ids)
active_connections = {}

# IMPORTANT:
# Do NOT import `socketio` from app.py here.
# When the backend is started with `python app.py`, the running module is `__main__`,
# and `import app` would create a second module instance with a different SocketIO object.
# That breaks emits from HTTP routes (they go to a SocketIO instance with no connected clients).
_socketio_instance = None

def get_socketio():
    """Return the single SocketIO instance registered in `register_handlers`."""
    global _socketio_instance
    if _socketio_instance is None:
        raise RuntimeError('SocketIO instance not registered yet. Call register_handlers(socketio) first.')
    return _socketio_instance

# Register handlers - these will be registered when app.py imports this module
# after socketio is initialized
def register_handlers(socketio):
    """Register all socketio handlers"""
    global _socketio_instance
    _socketio_instance = socketio
    print('[WebSocket] Registering handlers with socketio instance')

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        print(f'Client connected: {request.sid}')
        emit('connected', {'message': 'Connected to server', 'socket_id': request.sid})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        print(f'Client disconnected: {request.sid}')
        
        # Remove from all sessions
        for session_id, connections in active_connections.items():
            if request.sid in connections:
                connections.remove(request.sid)
                if not connections:
                    del active_connections[session_id]
                break

    @socketio.on('join_session')
    def handle_join_session(data):
        """Handle client joining a session room"""
        try:
            session_identifier = data.get('session_id')
            role = data.get('role', 'participant')
            
            if not session_identifier:
                emit('error', {'message': 'session_id is required'})
                return
            
            # Find session and get the actual session_id (UUID)
            import routes.session as session_module
            sessions = session_module.sessions
            
            found_session = None
            actual_session_id = None  # This will be the UUID we use as room identifier
            
            # Try to find session by session_id (UUID) or session_name
            for sid, session in sessions.items():
                # Check if provided identifier matches session_id (UUID) or dictionary key
                if session.get('session_id') == session_identifier or sid == session_identifier:
                    found_session = session
                    actual_session_id = session.get('session_id') or sid
                    break
                # Check if provided identifier matches session_name
                elif session.get('session_name') == session_identifier:
                    found_session = session
                    actual_session_id = session.get('session_id') or sid
                    break
            
            if not found_session or not actual_session_id:
                emit('error', {'message': f'Session not found: {session_identifier}'})
                return
            
            # Always use session_id (UUID) as the room identifier
            room_id = actual_session_id
            
            # Join the room using session_id (UUID) only
            join_room(room_id)
            
            # Track the connection
            if room_id not in active_connections:
                active_connections[room_id] = set()
            active_connections[room_id].add(request.sid)
            
            print(f'Client {request.sid} joined session room {room_id} (provided: {session_identifier}, role: {role})')
            
            # Notify the client
            emit('joined_session', {
                'session_id': actual_session_id,
                'role': role,
                'message': f'Successfully joined session {actual_session_id}'
            })

            # Notify others in the session
            emit('user_joined', {
                'socket_id': request.sid,
                'role': role
            }, room=room_id, include_self=False)
            
        except Exception as e:
            print(f'Error joining session: {e}')
            emit('error', {'message': str(e)})

    @socketio.on('leave_session')
    def handle_leave_session(data):
        """Handle client leaving a session room"""
        try:
            session_identifier = data.get('session_id')
            
            if not session_identifier:
                emit('error', {'message': 'session_id is required'})
                return
            
            # Find session and get the actual session_id (UUID)
            import routes.session as session_module
            sessions = session_module.sessions
            
            found_session = None
            actual_session_id = None  # This will be the UUID we use as room identifier
            
            # Try to find session by session_id (UUID) or session_name
            for sid, session in sessions.items():
                # Check if provided identifier matches session_id (UUID) or dictionary key
                if session.get('session_id') == session_identifier or sid == session_identifier:
                    found_session = session
                    actual_session_id = session.get('session_id') or sid
                    break
                # Check if provided identifier matches session_name
                elif session.get('session_name') == session_identifier:
                    found_session = session
                    actual_session_id = session.get('session_id') or sid
                    break
            
            if not found_session or not actual_session_id:
                # Session not found, but still try to leave the room with provided identifier
                # (in case client is using session_id directly)
                room_id = session_identifier
            else:
                # Always use session_id (UUID) as the room identifier
                room_id = actual_session_id
            
            # Leave the room using session_id (UUID) only
            leave_room(room_id)
            
            # Remove from tracking
            if room_id in active_connections:
                active_connections[room_id].discard(request.sid)
                if not active_connections[room_id]:
                    del active_connections[room_id]
            
            print(f'Client {request.sid} left session room {room_id} (provided: {session_identifier})')
            
            # Notify the client
            emit('left_session', {
                'session_id': room_id,
                'message': f'Successfully left session {room_id}'
            })
            
            # Notify others in the session
            emit('user_left', {
                'socket_id': request.sid
            }, room=room_id, include_self=False)
            
        except Exception as e:
            print(f'Error leaving session: {e}')
            emit('error', {'message': str(e)})

    @socketio.on('ping')
    def handle_ping(data=None):
        """Handle ping for connection testing"""
        print(f'[WebSocket] Received ping from {request.sid}, data: {data}')
        emit('pong', {'message': 'pong', 'timestamp': datetime.now().isoformat()})
        print(f'[WebSocket] Sent pong to {request.sid}')
    
    @socketio.on('vote_popup_shown')
    def handle_vote_popup_shown(data):
        """Handle vote popup shown event - trigger agent voting for HiddenProfile"""
        try:
            session_identifier = data.get('session_id')
            participant_id = data.get('participant_id')
            vote_type = data.get('vote_type')  # 'initial' or 'final'
            
            if not session_identifier or not participant_id or not vote_type:
                print(f'[WebSocket] vote_popup_shown: Missing required fields')
                return
            
            # Only handle for HiddenProfile experiment
            import routes.session as session_module
            from routes.participant import find_session_by_identifier
            session_key, session = find_session_by_identifier(session_identifier)
            if not session:
                print(f'[WebSocket] vote_popup_shown: Session {session_identifier} not found')
                return
            
            if session.get('experiment_type') != 'hiddenprofile':
                return  # Not a HiddenProfile experiment, ignore
            
            # Get the actual session_id (UUID) for agent runner lookup
            actual_session_id = session.get('session_id') or session_key
            
            # Find participant
            participant = None
            for p in session.get('participants', []):
                if p.get('id') == participant_id:
                    participant = p
                    break
            
            if not participant:
                print(f'[WebSocket] vote_popup_shown: Participant {participant_id} not found')
                return
            
            # If this is a human participant showing the vote popup, trigger all AI agents
            # If this is an AI agent, only trigger that specific agent
            participant_type = participant.get('type', '').lower()
            is_human = participant_type not in ['ai', 'ai_agent']
            
            if is_human:
                # Human participant showed vote popup - trigger all AI agents in the session
                participants_list = session.get('participants', [])
                ai_agents = [
                    p for p in participants_list 
                    if p.get('type', '').lower() in ['ai', 'ai_agent']
                ]
                
                print(f'[WebSocket] vote_popup_shown: Human participant {participant_id} showed {vote_type} vote popup, triggering {len(ai_agents)} AI agents')
                
                from agent.agent_runner import get_agent_runner
                for ai_participant in ai_agents:
                    ai_participant_id = ai_participant.get('id') or ai_participant.get('participant_id')
                    if ai_participant_id:
                        # Use actual_session_id (UUID) to find agent runner
                        runner = get_agent_runner(ai_participant_id, actual_session_id)
                        if runner:
                            print(f'[WebSocket] vote_popup_shown: Triggering {vote_type} vote for agent {ai_participant_id} in session {actual_session_id}')
                            runner._trigger_vote(vote_type, ai_participant, session, session_key)
                        else:
                            print(f'[WebSocket] vote_popup_shown: Agent runner not found for participant {ai_participant_id} in session {actual_session_id} (provided: {session_identifier})')
            else:
                # AI agent showing vote popup - trigger only that agent
                from agent.agent_runner import get_agent_runner
                # Use actual_session_id (UUID) to find agent runner
                runner = get_agent_runner(participant_id, actual_session_id)
                if runner:
                    print(f'[WebSocket] vote_popup_shown: Triggering {vote_type} vote for agent {participant_id} in session {actual_session_id}')
                    # Directly trigger voting
                    # Note: We need to re-fetch participant to ensure we have the latest state
                    runner._trigger_vote(vote_type, participant, session, session_key)
                else:
                    print(f'[WebSocket] vote_popup_shown: Agent runner not found for participant {participant_id} in session {actual_session_id} (provided: {session_identifier})')
                
        except Exception as e:
            print(f'[WebSocket] Error handling vote_popup_shown: {e}')
            import traceback
            traceback.print_exc()

    @socketio.on('send_message')
    def handle_send_message(data):
        """Handle sending a message between participants"""
        try:
            session_id = data.get('session_id')
            sender = data.get('sender')  # participant_id
            receiver = data.get('receiver')  # participant_id (None for group chat)
            content = (data.get('content') or '').strip()
            message_type = data.get('message_type', 'text')  # 'text' | 'audio'
            audio_url = data.get('audio_url', '')
            duration = data.get('duration', 0)  # seconds
            
            
            if not session_id:
                emit('error', {'message': 'session_id is required'})
                return
            
            if not sender:
                emit('error', {'message': 'sender is required'})
                return
            
            if message_type == 'audio':
                if not audio_url:
                    emit('error', {'message': 'audio_url is required for audio messages'})
                    return
            elif not content:
                emit('error', {'message': 'content cannot be empty'})
                return
            
            # Lazy import to avoid circular import
            import routes.session as session_module
            sessions = session_module.sessions
            
            # Find session and get the actual session_id (UUID)
            found_session = None
            actual_session_id = None  # This will be the UUID we use as room identifier
            session_key = None
            
            for sid, session in sessions.items():
                # Check if provided identifier matches session_id (UUID) or dictionary key
                if session.get('session_id') == session_id or sid == session_id:
                    found_session = session
                    actual_session_id = session.get('session_id') or sid
                    session_key = sid
                    break
                # Check if provided identifier matches session_name
                elif session.get('session_name') == session_id:
                    found_session = session
                    actual_session_id = session.get('session_id') or sid
                    session_key = sid
                    break
            
            if not found_session or not actual_session_id or not session_key:
                emit('error', {'message': 'Session not found'})
                return
            
            # Create message object
            message = {
                'id': str(uuid.uuid4()),
                'session_id': actual_session_id,
                'sender': sender,
                'receiver': receiver,  # None for group chat
                'content': content,
                'message_type': message_type,
                'timestamp': datetime.now().isoformat()
            }
            if message_type == 'audio':
                message['audio_url'] = audio_url
                message['duration'] = duration
            
            # Store message in session
            # Initialize messages list if it doesn't exist
            if 'messages' not in found_session:
                found_session['messages'] = []
            
            found_session['messages'].append(message)
            
            # Also store in participants' message history for easy lookup
            participants = found_session.get('participants', [])
            for participant in participants:
                p_id = participant.get('id') or participant.get('participant_id')
                if p_id == sender or p_id == receiver:
                    # Initialize messages list if it doesn't exist
                    if 'messages' not in participant:
                        participant['messages'] = []
                    participant['messages'].append(message)
            
            
            # Check if sender is human or agent
            sender_participant = None
            for p in participants:
                p_id = p.get('id') or p.get('participant_id')
                if p_id == sender:
                    sender_participant = p
                    break
            
            sender_type = sender_participant.get('type', 'unknown') if sender_participant else 'unknown'
            
            # Broadcast message to all participants in the session
            # Always use session_id (UUID) as the room identifier
            socketio = get_socketio()
            room_id = actual_session_id
            
            # Check how many clients are in the room
            room_connections = active_connections.get(room_id, set())
            
            if receiver is None:
                # Group chat: broadcast to all in session
                socketio.emit('message_received', message, room=room_id)
            else:
                # Private message: send to sender and receiver only
                socketio.emit('message_received', message, room=room_id)
            
            # Action log (human only gets screenshot/html_snapshot)
            is_human_sender = (sender_type or '').lower() not in ('ai', 'ai_agent')
            from services.action_logger import log_action
            log_action(
                session_id=actual_session_id,
                participant_id=sender,
                is_human=is_human_sender,
                action_type='send_message',
                action_content=content or f'[audio {duration}s]',
                result='success',
                metadata={'message_id': message['id'], 'receiver': receiver, 'message_type': message_type},
                page='social_panel',
                experiment_type=found_session.get('experiment_type', ''),
                screenshot=data.get('screenshot') if is_human_sender else None,
                html_snapshot=data.get('html_snapshot') if is_human_sender else None,
                audio_file_url=audio_url if message_type == 'audio' else None,
                session=found_session,
                participant=sender_participant,
            )

            # In-session annotation: trigger on message send when annotation enabled (human only)
            if is_human_sender:
                try:
                    from services.annotation_service import (
                        should_trigger_annotation,
                        trigger_annotation,
                    )
                    should_trigger, checkpoint = should_trigger_annotation(
                        session_key, found_session, sender, 'send_message'
                    )
                    if should_trigger and checkpoint is not None:
                        trigger_annotation(session_key, found_session, checkpoint, sessions)
                except Exception as ann_err:
                    print(f'[Annotation] Error checking/triggering after message: {ann_err}')

            # Confirm to sender (emit to the requesting client)
            emit('message_sent', {
                'message_id': message['id'],
                'status': 'success',
                'session_id': session_id,
                'sender': sender,
                'receiver': receiver
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                emit('error', {'message': str(e), 'type': 'send_message_error'})
            except Exception:
                pass

    # Meeting room: participant_id -> socket_id mapping per session
    meeting_participants = {}  # session_id -> { participant_id: socket_id }

    @socketio.on('meeting_join')
    def handle_meeting_join(data):
        """Handle participant joining meeting room - broadcast to others for WebRTC signaling"""
        try:
            session_identifier = data.get('session_id')
            participant_id = data.get('participant_id')
            if not session_identifier or not participant_id:
                emit('error', {'message': 'session_id and participant_id required'})
                return
            import routes.session as session_module
            sessions = session_module.sessions
            actual_session_id = None
            for sid, session in sessions.items():
                if session.get('session_id') == session_identifier or sid == session_identifier or session.get('session_name') == session_identifier:
                    actual_session_id = session.get('session_id') or sid
                    break
            if not actual_session_id:
                actual_session_id = session_identifier
            room_id = actual_session_id
            if room_id not in meeting_participants:
                meeting_participants[room_id] = {}
            meeting_participants[room_id][participant_id] = request.sid
            # Notify others in the session that this participant joined the meeting
            socket_inst = get_socketio()
            socket_inst.emit('meeting_peer_joined', {
                'participant_id': participant_id,
                'session_id': actual_session_id
            }, room=room_id, include_self=False)
        except Exception as e:
            print(f'[Meeting] Error: {e}')
            emit('error', {'message': str(e)})

    @socketio.on('meeting_leave')
    def handle_meeting_leave(data):
        """Handle participant leaving meeting room"""
        try:
            session_identifier = data.get('session_id')
            participant_id = data.get('participant_id')
            if not session_identifier or not participant_id:
                return
            import routes.session as session_module
            sessions = session_module.sessions
            actual_session_id = None
            for sid, session in sessions.items():
                if session.get('session_id') == session_identifier or sid == session_identifier or session.get('session_name') == session_identifier:
                    actual_session_id = session.get('session_id') or sid
                    break
            if not actual_session_id:
                actual_session_id = session_identifier
            if actual_session_id in meeting_participants and participant_id in meeting_participants[actual_session_id]:
                del meeting_participants[actual_session_id][participant_id]
                if not meeting_participants[actual_session_id]:
                    del meeting_participants[actual_session_id]
        except Exception as e:
            print(f'[Meeting] Leave error: {e}')

    @socketio.on('meeting_signal')
    def handle_meeting_signal(data):
        """Relay WebRTC signaling (offer/answer/ice) between participants"""
        try:
            session_identifier = data.get('session_id')
            from_participant = data.get('from_participant')
            to_participant = data.get('to_participant')
            sig_type = data.get('type')
            sig_data = data.get('data')
            if not all([session_identifier, from_participant, to_participant, sig_type, sig_data is not None]):
                return
            # Resolve session identifier to actual session_id (same as meeting_join)
            import routes.session as session_module
            sessions = session_module.sessions
            actual_session_id = None
            for sid, session in sessions.items():
                if session.get('session_id') == session_identifier or sid == session_identifier or session.get('session_name') == session_identifier:
                    actual_session_id = session.get('session_id') or sid
                    break
            if not actual_session_id:
                actual_session_id = session_identifier
            room_participants = meeting_participants.get(actual_session_id, {})
            target_socket = room_participants.get(to_participant)
            if target_socket:
                socket_inst = get_socketio()
                socket_inst.emit('meeting_signal', {
                    'from_participant': from_participant,
                    'to_participant': to_participant,
                    'type': sig_type,
                    'data': sig_data
                }, room=target_socket)
        except Exception as e:
            print(f'[Meeting] Signal error: {e}')


def broadcast_participant_update(session_id, participants, session_info=None, update_type='full'):
    """
    Broadcast participant update to all clients in a session room.
    
    Args:
        session_id: The session identifier (session_id UUID, session_name, or session key)
        participants: List of participant objects
        session_info: Optional session info to include
        update_type: Type of update ('full', 'partial', 'status', etc.) for future extensibility
    """
    try:
        # Lazy import to avoid circular import
        socketio = get_socketio()
        
        # Find session and get the actual session_id (UUID)
        import routes.session as session_module
        sessions = session_module.sessions
        
        found_session = None
        actual_session_id = None  # This will be the UUID we use as room identifier
        
        # Try to find session by session_id (UUID) or session_name
        for sid, session in sessions.items():
            # Check if provided identifier matches session_id (UUID) or dictionary key
            if session.get('session_id') == session_id or sid == session_id:
                found_session = session
                actual_session_id = session.get('session_id') or sid
                break
            # Check if provided identifier matches session_name
            elif session.get('session_name') == session_id:
                found_session = session
                actual_session_id = session.get('session_id') or sid
                break
        
        # If session_info is provided, use it to get session_id
        if not actual_session_id and session_info:
            actual_session_id = session_info.get('session_id')
        
        # If still no session_id found, use the provided identifier (might already be UUID)
        if not actual_session_id:
            actual_session_id = session_id
        
        # Get trades data from session if available
        pending_offers = []
        completed_trades = []
        if session_info:
            pending_offers = session_info.get('pending_offers', [])
            completed_trades = session_info.get('completed_trades', [])
        elif found_session:
            pending_offers = found_session.get('pending_offers', [])
            completed_trades = found_session.get('completed_trades', [])

        # Build payload
        payload = {
            'session_id': actual_session_id,
            'participants': participants,
            'session_info': session_info,
            'pending_offers': pending_offers,
            'completed_trades': completed_trades,
            'update_type': update_type,
            'timestamp': datetime.now().isoformat()
        }
        # Broadcast to all clients in the session room using session_id (UUID) only
        socketio.emit('participants_updated', payload, room=actual_session_id)

        print(f'Broadcasted participant update for session {actual_session_id} (provided: {session_id}, type: {update_type})')
    except Exception as e:
        print(f'Error broadcasting participant update: {e}')
        import traceback
        traceback.print_exc()

