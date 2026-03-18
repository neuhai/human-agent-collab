"""
Agent Runner: Manages agent perception and action execution.

This module is responsible for:
1. Periodically perceiving the experiment environment
2. Calling LLM to generate actions based on prompt and perception
3. Executing actions through AgentContextProtocol
"""

import threading
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime
import routes.session as session_module
from routes.participant import (
    find_session_by_identifier, 
    get_value_from_session_params,
    update_participant_experiment_params
)
from agent.agent_context_protocol import AgentContextProtocol
from agent.llm_client import create_llm_client, LLMClient


class AgentRunner:
    """Manages agent perception and action execution"""
    
    def __init__(
        self, 
        participant_id: str, 
        session_id: str,
        experiment_type: str,
        llm_client: Optional[LLMClient] = None,
        participant_role: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize agent runner.
        
        Args:
            participant_id: The ID of the agent participant
            session_id: The ID of the session
            experiment_type: The experiment type (e.g., 'shapefactory')
            llm_client: Optional LLM client (if None, will try to create one from config/env)
            participant_role: Optional participant role (e.g., 'guesser', 'hinter' for wordguessing)
            llm_config: Optional LLM configuration dict (overrides environment variables)
        """
        self.participant_id = participant_id
        self.session_id = session_id
        self.experiment_type = experiment_type
        self.participant_role = participant_role
        self.sessions = session_module.sessions
        
        # Initialize LLM client
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            self.llm_client = create_llm_client(config=llm_config)
        
        # Agent state
        self.is_running = False
        self.perception_thread = None
        self.protocol = AgentContextProtocol(participant_id, session_id, experiment_type)
        
        # Load prompt template (will be loaded later when we have participant info)
        self.prompt_template = None
    
    def start(self):
        """Start the agent perception loop"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # For hiddenprofile experiment, check if initial vote is needed before starting perception loop
        if self.experiment_type == 'hiddenprofile':
            try:
                session_key, session = find_session_by_identifier(self.session_id)
                if session:
                    participant = self._find_participant(session)
                    if participant:
                        exp_params = participant.get('experiment_params', {})
                        initial_vote = exp_params.get('initial_vote')
                        # Check if initial vote is needed (not already voted)
                        if not initial_vote or initial_vote == 'none':
                            # Check if there are human participants
                            participants_list = session.get('participants', [])
                            has_human_participant = any(
                                p.get('type', '').lower() not in ['ai', 'ai_agent'] 
                                for p in participants_list
                            )
                            # Only auto-trigger initial vote if no human participants
                            if not has_human_participant:
                                print(f'[AgentRunner] HiddenProfile: Auto-triggering initial vote for agent {self.participant_id} (no human participants)')
                                # Trigger initial vote in a separate thread to avoid blocking
                                def trigger_vote():
                                    import time
                                    time.sleep(2)  # Small delay to ensure everything is initialized
                                    session_key_latest, session_latest = find_session_by_identifier(self.session_id)
                                    if session_latest:
                                        participant_latest = self._find_participant(session_latest)
                                        if participant_latest:
                                            self._trigger_vote('initial', participant_latest, session_latest, session_key_latest)
                                threading.Thread(target=trigger_vote, daemon=True).start()
            except Exception as e:
                print(f'[AgentRunner] Error checking initial vote on start: {e}')
                import traceback
                traceback.print_exc()
        
        self.perception_thread = threading.Thread(target=self._perception_loop, daemon=True)
        self.perception_thread.start()
        print(f'[AgentRunner] Started agent {self.participant_id} for session {self.session_id}')
    
    def stop(self):
        """Stop the agent perception loop"""
        self.is_running = False
        if self.perception_thread:
            self.perception_thread.join(timeout=2.0)
        print(f'[AgentRunner] Stopped agent {self.participant_id}')
    
    def _perception_loop(self):
        """Main perception loop that runs periodically"""
        while self.is_running:
            try:
                # Check if session is still running
                session_key, session = find_session_by_identifier(self.session_id)
                if not session:
                    print(f'[AgentRunner] Session {self.session_id} not found. Stopping agent.')
                    self.is_running = False
                    break
                
                # Only run if session status is 'running'
                if session.get('status') != 'running':
                    # Wait a bit before checking again
                    time.sleep(5)
                    continue
                
                # Get perception time window
                perception_window = get_value_from_session_params(
                    session, 
                    'Session.Interaction.agentPerceptionTimeWindow'
                )
                perception_window = float(perception_window) if perception_window is not None else 15.0
                
                # Perceive and act
                self._perceive_and_act(session, session_key)
                
                # Wait for next perception window
                time.sleep(perception_window)
                
            except Exception as e:
                print(f'[AgentRunner] Error in perception loop: {e}')
                import traceback
                traceback.print_exc()
                # Wait a bit before retrying
                time.sleep(5)
    
    def _perceive_and_act(self, session: Dict[str, Any], session_key: str):
        """Perceive environment and generate/execute actions"""
        try:
            # Get participant
            participant = self._find_participant(session)
            if not participant:
                print(f'[AgentRunner] Participant {self.participant_id} not found')
                return
            
            # For hiddenprofile, check if initial vote is needed before proceeding
            if self.experiment_type == 'hiddenprofile':
                exp_params = participant.get('experiment_params', {})
                initial_vote = exp_params.get('initial_vote')
                # If initial vote is not done yet, skip this perception cycle
                if not initial_vote or initial_vote == 'none':
                    return
            
            # Update participant role if needed (for wordguessing)
            if self.experiment_type == 'wordguessing' and not self.participant_role:
                self.participant_role = participant.get('role')
            
            # Load prompt template if not loaded yet
            if not self.prompt_template:
                self.prompt_template = self._load_prompt_template(participant)
            
            # Build perception context (this will update participant interface, but preserve read_essays)
            perception = self._build_perception(participant, session)
            
            # Re-fetch participant from session to ensure we have the latest data including read_essays
            # This is important because actions may have updated the participant
            participant = self._find_participant(session)
            if not participant:
                print(f'[AgentRunner] Participant {self.participant_id} not found after perception build')
                return
            
            # Generate prompt
            prompt = self._build_prompt(participant, session, perception)
            
            # Debug: Print prompt
            participant_name = participant.get("name") or participant.get("participant_name")
            # print(f'\n{"="*80}')
            # print(f'[AgentRunner] DEBUG - PROMPT')
            # print(f'{"="*80}')
            # print(f'Participant: {participant_name} ({self.participant_id})')
            # print(f'Experiment: {self.experiment_type}')
            # print(f'Prompt Length: {len(prompt)} characters')
            # print(f'\n--- Full Prompt ---')
            # print(prompt)
            # print(f'--- End Prompt ---')
            # print(f'{"="*80}\n')
            
            # Call LLM to generate actions
            response = self._call_llm(prompt)
            
            if not response:
                print(f'[AgentRunner] No response from LLM for participant {self.participant_id}')
                return
            
            # Debug: Print LLM response
            participant_name = participant.get("name") or participant.get("participant_name")
            print(f'\n{"="*80}')
            print(f'[AgentRunner] DEBUG - LLM RESPONSE')
            print(f'{"="*80}')
            print(f'Participant: {participant_name} ({self.participant_id})')
            print(f'Response Length: {len(response)} characters')
            print(f'\n--- Full LLM Response ---')
            print(response)
            print(f'--- End LLM Response ---')
            print(f'{"="*80}\n')
            
            # Parse response
            actions = self._parse_response(response)
            
            # Debug: Print parsed actions
            if actions:
                print(f'\n{"="*80}')
                print(f'[AgentRunner] DEBUG - PARSED ACTIONS')
                print(f'{"="*80}')
                print(f'Participant: {participant_name} ({self.participant_id})')
                print(f'Total Actions: {len(actions)}')
                print(f'\n--- Actions List ---')
                for i, action in enumerate(actions):
                    print(f'\nAction {i+1}:')
                    print(json.dumps(action, indent=2, ensure_ascii=False))
                print(f'\n--- End Actions List ---')
                print(f'{"="*80}\n')
            else:
                print(f'\n{"="*80}')
                print(f'[AgentRunner] DEBUG - No actions parsed from response')
                print(f'{"="*80}\n')
            
            if not actions:
                print(f'[AgentRunner] No actions generated for participant {self.participant_id}')
                return
            
            # Execute actions
            results = self.protocol.execute_actions(actions)
            
            # After actions are executed, re-fetch participant to get updated state (including read_essays)
            # This ensures the next perception cycle has the latest data
            updated_participant = self._find_participant(session)
            if updated_participant:
                read_essays_count = len(updated_participant.get('read_essays', {}))
                if read_essays_count > 0:
                    read_essay_names = [e.get('title', '') for e in updated_participant.get('read_essays', {}).values() if e.get('title')]
                    print(f'[AgentRunner] Participant {self.participant_id} has read {read_essays_count} essays: {read_essay_names}')
            
            # Log results
            successful_count = len(results.get('successful', []))
            failed_count = len(results.get('failed', []))
            if successful_count > 0 or failed_count > 0:
                print(f'[AgentRunner] Participant {self.participant_id}: {successful_count} successful, {failed_count} failed actions')
            
            if results.get('errors'):
                for error in results['errors']:
                    print(f'[AgentRunner] Error: {error}')
            
        except Exception as e:
            print(f'[AgentRunner] Error in perceive_and_act: {e}')
            import traceback
            traceback.print_exc()
    
    def _trigger_vote(self, vote_type: str, participant: Dict[str, Any], session: Dict[str, Any], session_key: str) -> bool:
        """
        Directly trigger voting for HiddenProfile agent.
        Called when vote popup is shown (via WebSocket event).
        
        Args:
            vote_type: 'initial' or 'final'
            participant: Participant object
            session: Session object
            session_key: Session key in storage
        
        Returns:
            True if vote was successfully submitted, False otherwise
        """
        if self.experiment_type != 'hiddenprofile':
            return False
        
        exp_params = participant.get('experiment_params', {})
        
        # Check if already voted
        if vote_type == 'initial':
            current_vote = exp_params.get('initial_vote')
            if current_vote and current_vote != 'none':
                print(f'[AgentRunner] HiddenProfile: Initial vote already submitted: {current_vote}')
                return False
        elif vote_type == 'final':
            current_vote = exp_params.get('final_vote')
            if current_vote and current_vote != 'none':
                print(f'[AgentRunner] HiddenProfile: Final vote already submitted: {current_vote}')
                return False
        else:
            print(f'[AgentRunner] HiddenProfile: Invalid vote_type: {vote_type}')
            return False
        
        # Get candidate names
        candidate_names = get_value_from_session_params(session, 'Session.Params.candidateNames')
        if not candidate_names:
            print(f'[AgentRunner] HiddenProfile: Candidate names not found')
            return False
        
        # Handle different formats
        if isinstance(candidate_names, list):
            names = candidate_names
        elif isinstance(candidate_names, str):
            if ',' in candidate_names:
                names = [name.strip() for name in candidate_names.split(',') if name.strip()]
            else:
                names = [candidate_names.strip()] if candidate_names.strip() else []
        else:
            names = []
        
        if not names:
            print(f'[AgentRunner] HiddenProfile: No valid candidate names found')
            return False
        
        # Build vote prompt and get LLM response
        vote_prompt = self._build_vote_prompt(participant, session, names, vote_type)
        if not vote_prompt:
            print(f'[AgentRunner] HiddenProfile: Could not build vote prompt')
            return False
        
        print(f'[AgentRunner] HiddenProfile: Calling LLM for {vote_type} vote decision')
        print(f'[AgentRunner] HiddenProfile: Vote prompt:\n{vote_prompt}')
        
        # Call LLM
        response = self._call_llm(vote_prompt)
        if not response:
            print(f'[AgentRunner] HiddenProfile: LLM returned no response')
            return False
        
        print(f'[AgentRunner] HiddenProfile: LLM response for {vote_type} vote: {response}')
        
        # Parse response using standard action parser
        actions = self._parse_response(response)
        if not actions:
            print(f'[AgentRunner] HiddenProfile: No actions parsed from vote response')
            return False
        
        # Execute actions using standard executor
        result = self.protocol.execute_actions(actions)
        if result.get('successful'):
            # Extract candidate name from successful action for logging
            successful_actions = result.get('successful', [])
            if successful_actions:
                action = successful_actions[0]
                candidate_name = action.get('candidate_name', 'unknown')
                print(f'[AgentRunner] HiddenProfile: Successfully submitted {vote_type} vote: {candidate_name}')
            else:
                print(f'[AgentRunner] HiddenProfile: Successfully submitted {vote_type} vote')
            return True
        else:
            print(f'[AgentRunner] HiddenProfile: Failed to submit {vote_type} vote: {result.get("failed", [])}')
            return False
    
    def _build_vote_prompt(self, participant: Dict[str, Any], session: Dict[str, Any], candidate_names: list, vote_type: str) -> Optional[str]:
        """
        Build vote prompt for HiddenProfile experiment.
        Returns the prompt string, or None if prompt cannot be built.
        """
        try:
            # Build a focused prompt for voting decision
            participant_name = participant.get('name') or participant.get('participant_name', 'Agent')
            exp_params = participant.get('experiment_params', {})
            candidate_doc_obj = exp_params.get('candidate_document')
            initial_vote = exp_params.get('initial_vote')
            
            # Read the assigned document content
            assigned_doc_content = 'No document assigned'
            if candidate_doc_obj:
                if isinstance(candidate_doc_obj, dict):
                    filename = candidate_doc_obj.get('filename')
                    if filename:
                        content = self._read_document_content(filename)
                        if content:
                            assigned_doc_content = content
                elif isinstance(candidate_doc_obj, str):
                    content = self._read_document_content(candidate_doc_obj)
                    if content:
                        assigned_doc_content = content
            
            # Build context about what the agent has seen
            context_parts = []
            if vote_type == 'initial':
                context_parts.append(f"You have just read the following candidate document:\n\n{assigned_doc_content}")
            elif vote_type == 'final':
                context_parts.append(f"You have read the candidate document:\n\n{assigned_doc_content}")
                if initial_vote and initial_vote != 'none':
                    context_parts.append(f"Your initial vote was: {initial_vote}")
            
            context = "\n".join(context_parts) if context_parts else "You have reviewed the available information."
            
            # Build vote prompt with proper format (matching hiddenprofile_agent_prompt.txt)
            first_sentence = "Now, you need to make your initial vote based on the document you just read." if vote_type == 'initial' else "Now, you need to make your final vote based on the discussion."
            action_type = "submit_initial_vote" if vote_type == 'initial' else "submit_final_vote"
            
            # Format candidate names for display (with quotes to show exact format)
            candidate_list_display = ', '.join([f'"{name}"' for name in candidate_names])
            
            vote_prompt = f"""{first_sentence}

{context}

Available candidates: {candidate_list_display}

IMPORTANT: You must use the EXACT candidate name as shown above (including spaces and capitalization).

Your response format must follow:
{{
    "planning": "Explanation of your thinking",
    "actions": [
        {{
            "type": "{action_type}",
            "candidate_name": "candidate_name",
            "reasoning": "Your reasoning for this vote"
        }}
    ]
}}

Based on the information you have, which candidate do you choose? Respond with ONLY a valid JSON object following the format above, nothing else.

Response:"""
            
            return vote_prompt
            
        except Exception as e:
            print(f'[AgentRunner] Error building vote prompt: {e}')
            import traceback
            traceback.print_exc()
            return None
    
    def _build_perception(self, participant: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build perception context from current game state.
        Perception is structured to match what human participants can see.
        """
        # Ensure participant interface is up-to-date
        # Preserve read_essays and other custom fields before updating
        read_essays_backup = participant.get('read_essays', {})
        from routes.participant import update_participant_experiment_params
        participant = update_participant_experiment_params(participant, session)
        # Restore read_essays if it was lost
        if 'read_essays' not in participant and read_essays_backup:
            participant['read_essays'] = read_essays_backup
        
        perception = {
            'public_state': self._get_public_state(session),
            'private_state': self._get_private_state(participant),
            'agent_actions': self._get_agent_actions(participant, session),
            'interactions': self._get_interactions(participant, session),
            'other_participants': self._get_other_participants_state(participant, session)
        }
        
        return perception
    
    def _get_public_state(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Get public state visible to all participants"""
        return {
            'session_status': session.get('status', 'waiting'),
            'remaining_seconds': session.get('remaining_seconds'),
            'current_time': datetime.now().isoformat()
        }
    
    def _get_private_state(self, participant: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get private state of the agent participant based on participant interface.
        This extracts all visible fields from the participant's interface configuration.
        """
        private_state = {}
        
        # Get participant interface (contains all visible fields)
        interface = participant.get('interface', {})
        
        # Extract values from interface bindings
        # Interface structure: { 'My Status': [...], 'My Actions': [...], etc. }
        for panel_group, panels in interface.items():
            if not isinstance(panels, list):
                continue
            
            for panel in panels:
                if not isinstance(panel, dict):
                    continue
                
                bindings = panel.get('bindings', [])
                if not isinstance(bindings, list):
                    continue
                
                for binding in bindings:
                    if not isinstance(binding, dict):
                        continue
                    
                    # Get the path and value
                    path = binding.get('path')
                    value = binding.get('value')
                    
                    if path and path.startswith('Participant.'):
                        # Extract field name from path (e.g., 'Participant.money' -> 'money')
                        field_name = path.split('.', 1)[1]
                        private_state[field_name] = value
        
        # Also include top-level participant fields that might not be in interface
        # but are part of participant config
        if 'name' not in private_state:
            private_state['name'] = participant.get('name') or participant.get('participant_name')
        
        # Include experiment_params directly (as fallback for fields not in interface)
        exp_params = participant.get('experiment_params', {})
        for key, value in exp_params.items():
            if key not in private_state:
                private_state[key] = value
        
        return private_state
    
    def _get_agent_actions(self, participant: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get agent-specific action states (e.g., production progress with remaining time).
        """
        agent_actions = {}
        
        exp_params = participant.get('experiment_params', {})
        
        # Check for in_production (ShapeFactory)
        if self.experiment_type == 'shapefactory':
            in_production = exp_params.get('in_production', [])
            if isinstance(in_production, list) and len(in_production) > 0:
                production_items = []
                now = datetime.now()
                
                for item in in_production:
                    if not isinstance(item, dict):
                        continue
                    
                    completion_time_str = item.get('completion_time')
                    if not completion_time_str:
                        continue
                    
                    try:
                        completion_time = datetime.fromisoformat(completion_time_str)
                        remaining_seconds = max(0, int((completion_time - now).total_seconds()))
                        
                        production_items.append({
                            'shape': item.get('shape'),
                            'remaining_seconds': remaining_seconds,
                            'started_at': item.get('started_at')
                        })
                    except (ValueError, TypeError):
                        continue
                
                if production_items:
                    agent_actions['in_production'] = production_items
        
        return agent_actions
    
    def _get_interactions(self, participant: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get interaction-related content for this participant:
        - Unread messages
        - Pending trade offers (if applicable)
        - Other interaction items based on experiment type
        """
        interactions = {
            'unread_messages': self._get_unread_messages(participant, session),
        }
        
        # Add experiment-specific interactions
        if self.experiment_type == 'shapefactory':
            interactions['pending_trade_offers'] = self._get_pending_offers(participant, session)
            interactions['recent_trades'] = self._get_recent_trades(participant, session)
        elif self.experiment_type == 'daytrader':
            interactions['pending_offers'] = self._get_pending_offers(participant, session)
        elif self.experiment_type == 'essayranking':
            interactions['other_rankings'] = self._get_other_rankings(participant, session)
        
        return interactions
    
    def _get_unread_messages(self, participant: Dict[str, Any], session: Dict[str, Any]) -> list:
        """Get unread messages for this participant (using names, not IDs)"""
        # Get all messages from session
        all_messages = session.get('messages', [])
        participants = session.get('participants', [])
        
        # Build participant ID to name mapping
        participant_names = {}
        for p in participants:
            p_id = p.get('id')
            p_name = p.get('name') or p.get('participant_name')
            if p_id:
                participant_names[p_id] = p_name
        
        # Get messages where this participant is the receiver
        unread_messages = []
        for msg in all_messages:
            receiver_id = msg.get('receiver')
            sender_id = msg.get('sender')
            
            # Include if participant is receiver, or if it's a group message (receiver is None)
            if receiver_id == self.participant_id or (receiver_id is None and sender_id != self.participant_id):
                # Get sender name
                sender_name = participant_names.get(sender_id, 'Unknown')
                
                # Get receiver name if it's a private message
                receiver_name = None
                if receiver_id:
                    receiver_name = participant_names.get(receiver_id)
                
                unread_messages.append({
                    'sender': sender_name,
                    'receiver': receiver_name,  # None for group messages
                    'content': msg.get('content'),
                    'timestamp': msg.get('timestamp')
                })
        
        # Sort by timestamp (most recent first) and return last 10
        unread_messages.sort(key=lambda m: m.get('timestamp', ''), reverse=True)
        return unread_messages[:10]
    
    def _get_other_participants_state(
        self, 
        participant: Dict[str, Any], 
        session: Dict[str, Any]
    ) -> list:
        """
        Get state of other participants based on awareness dashboard settings.
        Only includes information that is enabled in the awareness dashboard.
        """
        participants = session.get('participants', [])
        awareness_dashboard = get_value_from_session_params(
            session,
            'Session.Interaction.awarenessDashboard'
        )
        
        # Debug: Print awareness dashboard config
        print(f'\n[AgentRunner] DEBUG - Awareness Dashboard Config:')
        print(f'  Raw value from get_value_from_session_params: {awareness_dashboard}')
        print(f'  Type: {type(awareness_dashboard)}')
        if isinstance(awareness_dashboard, dict):
            print(f'  Enabled: {awareness_dashboard.get("enabled")}')
            print(f'  Items: {awareness_dashboard.get("items")}')
        
        # Also check session.interaction directly
        session_interaction = session.get('interaction', {})
        print(f'  Session.interaction structure: {json.dumps(session_interaction, indent=2, default=str)}')
        
        # Check if awareness dashboard is enabled
        if not isinstance(awareness_dashboard, dict) or not awareness_dashboard.get('enabled'):
            # If not enabled, return empty list (no information about others)
            print(f'[AgentRunner] Awareness Dashboard is DISABLED or invalid config')
            return []
        
        print(f'[AgentRunner] Awareness Dashboard is ENABLED with items: {awareness_dashboard.get("items")}')
        
        # Get enabled items (can be indices or paths)
        items = awareness_dashboard.get('items', [])
        if not items:
            return []
        
        # Get the awareness dashboard options to map indices to paths
        from config.experiments import get_experiment_by_id
        exp_cfg = get_experiment_by_id(self.experiment_type) or {}
        interaction_cfg = exp_cfg.get('interaction', {})
        
        # Find awareness dashboard config
        awareness_config = None
        if isinstance(interaction_cfg, dict):
            for category, settings in interaction_cfg.items():
                if isinstance(settings, list):
                    for setting in settings:
                        if isinstance(setting, dict) and setting.get('path') == 'Session.Interaction.awarenessDashboard':
                            awareness_config = setting
                            break
        
        options = awareness_config.get('options', []) if awareness_config else []
        
        # Map items (indices or paths) to actual paths
        enabled_paths = []
        for item in items:
            if isinstance(item, int) and 0 <= item < len(options):
                # Index into options
                opt = options[item]
                if isinstance(opt, dict) and opt.get('path'):
                    enabled_paths.append(opt['path'])
            elif isinstance(item, str) and item.startswith('Participant.'):
                # Direct path
                enabled_paths.append(item)
        
        if not enabled_paths:
            return []
        
        # Build other participants state
        other_states = []
        for p in participants:
            if p.get('id') == self.participant_id:
                continue
            
            # Ensure participant interface is up-to-date
            from routes.participant import update_participant_experiment_params
            p = update_participant_experiment_params(p, session)
            
            p_state = {}
            
            # Extract only enabled fields from participant
            for path in enabled_paths:
                if not path.startswith('Participant.'):
                    continue
                
                field_name = path.split('.', 1)[1]
                
                # Try to get from participant interface first
                interface = p.get('interface', {})
                value = None
                
                # Search through interface bindings
                for panel_group, panels in interface.items():
                    if not isinstance(panels, list):
                        continue
                    for panel in panels:
                        if not isinstance(panel, dict):
                            continue
                        bindings = panel.get('bindings', [])
                        if not isinstance(bindings, list):
                            continue
                        for binding in bindings:
                            if binding.get('path') == path:
                                value = binding.get('value')
                                break
                        if value is not None:
                            break
                    if value is not None:
                        break
                
                # Fallback to direct access
                if value is None:
                    if field_name in p:
                        value = p[field_name]
                    elif field_name in p.get('experiment_params', {}):
                        value = p['experiment_params'][field_name]
                
                if value is not None:
                    p_state[field_name] = value
            
            # Always include name and id for identification
            p_state['name'] = p.get('name') or p.get('participant_name')
            p_state['id'] = p.get('id')
            
            other_states.append(p_state)
        
        return other_states
    
    def _get_pending_offers(
        self, 
        participant: Dict[str, Any], 
        session: Dict[str, Any]
    ) -> list:
        """Get pending trade offers relevant to this participant (using names, not IDs)"""
        pending_offers = session.get('pending_offers', [])
        participants = session.get('participants', [])
        
        # Build participant ID to name mapping
        participant_names = {}
        for p in participants:
            p_id = p.get('id')
            p_name = p.get('name') or p.get('participant_name')
            if p_id:
                participant_names[p_id] = p_name
        
        relevant_offers = []
        for offer in pending_offers:
            if offer.get('status') != 'pending':
                continue
            
            from_id = offer.get('from')
            to_id = offer.get('to')
            
            # Include offers where participant is sender or recipient
            if from_id == self.participant_id or to_id == self.participant_id:
                from_name = participant_names.get(from_id, 'Unknown')
                to_name = participant_names.get(to_id, 'Unknown')
                
                relevant_offers.append({
                    'transaction_id': offer.get('transaction_id') or offer.get('id'),  # Include transaction_id for agent actions
                    'from': from_name,
                    'to': to_name,
                    'offer_type': offer.get('offer_type'),
                    'shape': offer.get('shape') or offer.get('trade_item'),
                    'item_type': offer.get('item_type', 'shape'),
                    'price': offer.get('price'),
                    'quantity': offer.get('quantity', 1),
                    'timestamp': offer.get('timestamp')
                })
        
        return relevant_offers
    
    def _get_recent_trades(
        self, 
        participant: Dict[str, Any], 
        session: Dict[str, Any]
    ) -> list:
        """Get recent completed trades relevant to this participant (using names, not IDs)"""
        completed_trades = session.get('completed_trades', [])
        participants = session.get('participants', [])
        
        # Build participant ID to name mapping
        participant_names = {}
        for p in participants:
            p_id = p.get('id')
            p_name = p.get('name') or p.get('participant_name')
            if p_id:
                participant_names[p_id] = p_name
        
        relevant_trades = []
        for trade in completed_trades[-10:]:  # Last 10 trades
            from_id = trade.get('from')
            to_id = trade.get('to')
            
            if from_id == self.participant_id or to_id == self.participant_id:
                from_name = participant_names.get(from_id, 'Unknown')
                to_name = participant_names.get(to_id, 'Unknown')
                
                relevant_trades.append({
                    'from': from_name,
                    'to': to_name,
                    'offer_type': trade.get('offer_type'),
                    'shape': trade.get('shape') or trade.get('trade_item'),
                    'item_type': trade.get('item_type', 'shape'),
                    'price': trade.get('price'),
                    'quantity': trade.get('quantity', 1),
                    'status': trade.get('status'),
                    'timestamp': trade.get('timestamp')
                })
        
        return relevant_trades
    
    def _get_recent_trades(
        self, 
        participant: Dict[str, Any], 
        session: Dict[str, Any]
    ) -> list:
        """Get recent completed trades relevant to this participant"""
        completed_trades = session.get('completed_trades', [])
        
        relevant_trades = []
        for trade in completed_trades[-10:]:  # Last 10 trades
            if (trade.get('from') == self.participant_id or 
                trade.get('to') == self.participant_id):
                relevant_trades.append({
                    'from': trade.get('from'),
                    'to': trade.get('to'),
                    'offer_type': trade.get('offer_type'),
                    'shape': trade.get('shape') or trade.get('trade_item'),
                    'price': trade.get('price'),
                    'status': trade.get('status'),
                    'timestamp': trade.get('timestamp')
                })
        
        return relevant_trades
    
    def _build_prompt(
        self, 
        participant: Dict[str, Any], 
        session: Dict[str, Any],
        perception: Dict[str, Any]
    ) -> str:
        """Build the prompt for LLM based on template and current state (experiment-specific)"""
        if not self.prompt_template:
            return ""
        
        # Get common parameters
        communication_level = get_value_from_session_params(session, 'Session.Interaction.communicationLevel') or 'Private Messaging'
        
        # Get participant info
        participant_name = participant.get('name') or participant.get('participant_name')
        mbti = participant.get('mbti', 'unknown')
        
        # Build participants list (experiment-specific)
        participants_list_str = self._build_participants_list(participant, session)
        
        # Format perception data
        perception_str = self._format_perception(perception)
        
        # Replace common placeholders
        prompt = self.prompt_template
        prompt = prompt.replace('{participant_code}', participant_name)
        prompt = prompt.replace('{personality_name}', mbti)
        prompt = prompt.replace('{mbti_type}', mbti)
        prompt = prompt.replace('{personality_description}', f'You have {mbti} personality traits.')
        prompt = prompt.replace('{participants_list}', participants_list_str)
        prompt = prompt.replace('{communication_level}', communication_level)
        
        # Replace experiment-specific placeholders
        if self.experiment_type == 'shapefactory':
            prompt = self._replace_shapefactory_placeholders(prompt, participant, session)
        elif self.experiment_type == 'daytrader':
            prompt = self._replace_daytrader_placeholders(prompt, participant, session)
        elif self.experiment_type == 'essayranking':
            prompt = self._replace_essayranking_placeholders(prompt, participant, session)
        elif self.experiment_type == 'wordguessing':
            prompt = self._replace_wordguessing_placeholders(prompt, participant, session)
        elif self.experiment_type == 'hiddenprofile':
            prompt = self._replace_hiddenprofile_placeholders(prompt, participant, session)
        
        # Add perception section
        prompt += f"\n\n<CURRENT GAME STATE>\n{perception_str}\n"
        
        return prompt
    
    def _build_participants_list(self, participant: Dict[str, Any], session: Dict[str, Any]) -> str:
        """Build participants list string (experiment-specific)"""
        participants_list = []
        all_participants = session.get('participants', [])
        
        for p in all_participants:
            p_name = p.get('name') or p.get('participant_name')
            
            if self.experiment_type == 'shapefactory':
                p_specialty = p.get('specialty', '')
                participants_list.append(f"- {p_name}: Specialty = {p_specialty}")
            elif self.experiment_type == 'wordguessing':
                p_role = p.get('role', '')
                participants_list.append(f"- {p_name}: Role = {p_role}")
            else:
                # For other experiments (including daytrader), just show name
                # Detailed information (like investment_history) will be shown in perception
                # via _get_other_participants_state if awareness dashboard is enabled
                participants_list.append(f"- {p_name}")
        
        return '\n'.join(participants_list)
    
    def _replace_shapefactory_placeholders(self, prompt: str, participant: Dict[str, Any], session: Dict[str, Any]) -> str:
        """Replace ShapeFactory-specific placeholders"""
        starting_money = get_value_from_session_params(session, 'Session.Params.startingMoney') or 200
        specialty_cost = get_value_from_session_params(session, 'Session.Params.specialtyCost') or 15
        regular_cost = get_value_from_session_params(session, 'Session.Params.regularCost') or 40
        production_time = get_value_from_session_params(session, 'Session.Params.productionTime') or 30
        max_production_num = get_value_from_session_params(session, 'Session.Params.maxProductionNum') or 3
        price_min = get_value_from_session_params(session, 'Session.Params.minTradePrice') or 15
        price_max = get_value_from_session_params(session, 'Session.Params.maxTradePrice') or 100
        incentive_money = get_value_from_session_params(session, 'Session.Params.incentiveMoney') or 60
        shapes_order = get_value_from_session_params(session, 'Session.Params.shapesOrder') or 4
        
        specialty = participant.get('specialty', '')
        exp_params = participant.get('experiment_params', {})
        tasks = exp_params.get('tasks', [])
        
        prompt = prompt.replace('{shape_amount_per_order}', str(shapes_order))
        prompt = prompt.replace('{incentive_money}', str(incentive_money))
        prompt = prompt.replace('{starting_money}', str(starting_money))
        prompt = prompt.replace('{specialty_shape}', specialty)
        prompt = prompt.replace('{specialty_cost}', str(specialty_cost))
        prompt = prompt.replace('{regular_cost}', str(regular_cost))
        prompt = prompt.replace('{production_time}', str(production_time))
        prompt = prompt.replace('{max_production_num}', str(max_production_num))
        prompt = prompt.replace('{price_min}', str(price_min))
        prompt = prompt.replace('{price_max}', str(price_max))
        prompt = prompt.replace('{current_orders}', str(tasks))
        
        return prompt
    
    def _replace_daytrader_placeholders(self, prompt: str, participant: Dict[str, Any], session: Dict[str, Any]) -> str:
        """Replace DayTrader-specific placeholders"""
        starting_money = get_value_from_session_params(session, 'Session.Params.startingMoney') or 200
        min_trade_price = get_value_from_session_params(session, 'Session.Params.minTradePrice') or 15
        max_trade_price = get_value_from_session_params(session, 'Session.Params.maxTradePrice') or 100
        
        exp_params = participant.get('experiment_params', {})
        investment_history_list = exp_params.get('investment_history', [])
        investment_history = json.dumps(investment_history_list) if investment_history_list else "[]"
        
        prompt = prompt.replace('{starting_money}', str(starting_money))
        prompt = prompt.replace('{min_trade_price}', str(min_trade_price))
        prompt = prompt.replace('{max_trade_price}', str(max_trade_price))
        prompt = prompt.replace('{investment_history}', investment_history)
        
        return prompt
    
    def _replace_essayranking_placeholders(self, prompt: str, participant: Dict[str, Any], session: Dict[str, Any]) -> str:
        """Replace EssayRanking-specific placeholders"""
        # Get assigned essays (this might be stored in session or participant)
        assigned_essays = session.get('essays', []) or participant.get('experiment_params', {}).get('essays', [])
        
        # Extract only essay names (titles) for the prompt
        essay_names = []
        if assigned_essays:
            for essay in assigned_essays:
                if isinstance(essay, dict):
                    essay_name = essay.get('title') or essay.get('original_filename') or essay.get('filename', '').replace('.pdf', '')
                    if essay_name:
                        essay_names.append(essay_name)
                elif isinstance(essay, str):
                    essay_names.append(essay)
        
        # Format as a simple list of names
        if essay_names:
            assigned_essays_str = ', '.join(essay_names)
        else:
            assigned_essays_str = "No essays assigned"
        
        prompt = prompt.replace('{assigned_essays}', assigned_essays_str)
        
        # Include read essay contents if available
        # Append read essays info to the prompt so agent can use the content for evaluation
        read_essays = participant.get('read_essays', {})
        if read_essays:
            read_essays_info = []
            for essay_id, essay_data in read_essays.items():
                read_essays_info.append({
                    'essay_name': essay_data.get('title', ''),
                    'content': essay_data.get('content', ''),  # Include full content, not preview
                    'read_at': essay_data.get('read_at', '')
                })
            read_essays_str = json.dumps(read_essays_info, indent=2)
            
            # Get list of read essay names for clarity
            read_essay_names = [essay_data.get('title', '') for essay_data in read_essays.values() if essay_data.get('title')]
            read_names_str = ', '.join(read_essay_names) if read_essay_names else 'None'
            
            # Debug logging
            print(f'[AgentRunner] Including {len(read_essays)} read essays in prompt: {read_names_str}')
            
            # Append read essays section to the prompt
            read_essays_section = f"\n\n<READ ESSAYS CONTENT>\nYou have already read the following essays: {read_names_str}. The full content is provided below. You do NOT need to read them again with get_essay_content action.\n\n{read_essays_str}\n</READ ESSAYS CONTENT>\n"
            prompt = prompt + read_essays_section
        else:
            print(f'[AgentRunner] No read essays found for participant {participant.get("id")} (participant keys: {list(participant.keys())})')
        
        return prompt
    
    def _replace_wordguessing_placeholders(self, prompt: str, participant: Dict[str, Any], session: Dict[str, Any]) -> str:
        """Replace WordGuessing-specific placeholders"""
        role = participant.get('role', '')
        all_participants = session.get('participants', [])
        
        if role == 'guesser':
            # Find hinter
            hinter = None
            for p in all_participants:
                if p.get('role') == 'hinter':
                    hinter = p
                    break
            hinter_name = (hinter.get('name') or hinter.get('participant_name')) if hinter else 'Unknown'
            prompt = prompt.replace('{hinter_participant}', hinter_name)
        elif role == 'hinter':
            # Find guesser
            guesser = None
            for p in all_participants:
                if p.get('role') == 'guesser':
                    guesser = p
                    break
            guesser_name = (guesser.get('name') or guesser.get('participant_name')) if guesser else 'Unknown'
            prompt = prompt.replace('{guesser_participant}', guesser_name)
            
            # Get assigned words
            exp_params = participant.get('experiment_params', {})
            assigned_words = exp_params.get('assigned_words', [])
            assigned_words_str = ', '.join(assigned_words) if assigned_words else 'None'
            prompt = prompt.replace('{assigned_words}', assigned_words_str)
        
        return prompt
    
    def _replace_hiddenprofile_placeholders(self, prompt: str, participant: Dict[str, Any], session: Dict[str, Any]) -> str:
        """Replace HiddenProfile-specific placeholders"""
        # Get assigned document
        exp_params = participant.get('experiment_params', {})
        assigned_doc = exp_params.get('candidate_document')
        
        # Read document content
        assigned_doc_str = 'No document assigned'
        if assigned_doc:
            if isinstance(assigned_doc, dict):
                # Get filename from the document object
                filename = assigned_doc.get('filename') or assigned_doc.get('essay_id')
                if filename:
                    # Read PDF content
                    doc_content = self._read_document_content(filename)
                    if doc_content:
                        assigned_doc_str = doc_content
                    else:
                        # Fallback to document title if content cannot be read
                        doc_title = assigned_doc.get('title') or assigned_doc.get('original_filename') or 'Unknown Document'
                        assigned_doc_str = f"Document: {doc_title} (Content could not be read)"
                else:
                    doc_title = assigned_doc.get('title') or assigned_doc.get('original_filename') or 'Unknown Document'
                    assigned_doc_str = f"Document: {doc_title} (File not found)"
            elif isinstance(assigned_doc, str):
                # If it's just a string (filename), try to read it
                doc_content = self._read_document_content(assigned_doc)
                if doc_content:
                    assigned_doc_str = doc_content
                else:
                    assigned_doc_str = f"Document: {assigned_doc} (Content could not be read)"
            else:
                assigned_doc_str = 'No document assigned'
        
        # Get candidate names from session params
        candidate_names = get_value_from_session_params(session, 'Session.Params.candidateNames')
        
        # Format candidate list
        if candidate_names:
            if isinstance(candidate_names, list):
                candidate_list_str = ', '.join(candidate_names)
            elif isinstance(candidate_names, str):
                # Handle comma-separated string
                if ',' in candidate_names:
                    names = [name.strip() for name in candidate_names.split(',') if name.strip()]
                    candidate_list_str = ', '.join(names)
                else:
                    candidate_list_str = candidate_names.strip()
            else:
                candidate_list_str = str(candidate_names)
        else:
            candidate_list_str = 'No candidates available'
        
        # Replace placeholders
        prompt = prompt.replace('{assigned_doc}', assigned_doc_str)
        prompt = prompt.replace('{candidate_list}', candidate_list_str)
        
        return prompt
    
    def _read_document_content(self, filename: str) -> Optional[str]:
        """Read PDF document content"""
        try:
            import os
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'essays')
            file_path = os.path.join(upload_dir, filename)
            
            if not os.path.exists(file_path):
                return None
            
            # Try to read PDF content
            try:
                # Try PyPDF2 first
                try:
                    import PyPDF2
                    with open(file_path, 'rb') as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        content = []
                        for page_num, page in enumerate(pdf_reader.pages):
                            text = page.extract_text()
                            if text.strip():
                                content.append(f"--- Page {page_num + 1} ---\n{text}")
                        return '\n\n'.join(content) if content else None
                except ImportError:
                    # Fallback to pdfplumber
                    try:
                        import pdfplumber
                        with pdfplumber.open(file_path) as pdf:
                            content = []
                            for page_num, page in enumerate(pdf.pages):
                                text = page.extract_text()
                                if text:
                                    content.append(f"--- Page {page_num + 1} ---\n{text}")
                            return '\n\n'.join(content) if content else None
                    except ImportError:
                        return None
            except Exception as e:
                print(f'[AgentRunner] Error reading PDF {filename}: {e}')
                return None
        except Exception as e:
            print(f'[AgentRunner] Error reading document {filename}: {e}')
            return None
    
    def _format_perception(self, perception: Dict[str, Any]) -> str:
        """Format perception data as a readable string"""
        # Get session and participant for name lookup
        session_key, session = find_session_by_identifier(self.session_id)
        participant = self._find_participant(session) if session else None
        our_name = (participant.get('name') or participant.get('participant_name')) if participant else None
        
        lines = []
        
        # Public state
        public_state = perception.get('public_state', {})
        lines.append("=== Public State ===")
        lines.append(f"Session Status: {public_state.get('session_status', 'unknown')}")
        remaining = public_state.get('remaining_seconds')
        if remaining is not None:
            minutes = remaining // 60
            seconds = remaining % 60
            lines.append(f"Remaining Time: {minutes}m {seconds}s")
        lines.append(f"Current Time: {public_state.get('current_time', 'unknown')}")
        
        # Private state
        private_state = perception.get('private_state', {})
        if private_state:
            lines.append("\n=== Your Private State ===")
            # Format private state in a readable way
            for key, value in sorted(private_state.items()):
                if value is not None:
                    if key == 'investment_history' and isinstance(value, list):
                        # Special formatting for investment_history
                        if value:
                            lines.append(f"{key}:")
                            for inv in value:
                                inv_type = inv.get('investment_type', 'N/A')
                                inv_amount = inv.get('investment_amount', 0)
                                money_before = inv.get('money_before', 0)
                                money_after = inv.get('money_after', 0)
                                timestamp = inv.get('timestamp', 'N/A')
                                lines.append(f"  - {inv_type}: ${inv_amount} (Money: ${money_before} → ${money_after}) at {timestamp}")
                        else:
                            lines.append(f"{key}: []")
                    elif isinstance(value, list):
                        if value:
                            lines.append(f"{key}: {value}")
                        else:
                            lines.append(f"{key}: []")
                    elif isinstance(value, dict):
                        lines.append(f"{key}: {json.dumps(value, indent=2)}")
                    else:
                        lines.append(f"{key}: {value}")
        
        # Agent actions (e.g., production progress)
        agent_actions = perception.get('agent_actions', {})
        if agent_actions:
            lines.append("\n=== Your Active Actions ===")
            in_production = agent_actions.get('in_production', [])
            if in_production:
                lines.append("Items in Production:")
                for item in in_production:
                    shape = item.get('shape')
                    remaining = item.get('remaining_seconds', 0)
                    lines.append(f"  - {shape}: {remaining}s remaining")
        
        # Interactions
        interactions = perception.get('interactions', {})
        if interactions:
            lines.append("\n=== Interactions ===")
            
            # Unread messages
            unread_messages = interactions.get('unread_messages', [])
            if unread_messages:
                lines.append(f"Unread Messages ({len(unread_messages)}):")
                for msg in unread_messages[:5]:  # Last 5
                    sender = msg.get('sender', 'Unknown')
                    content = msg.get('content', '')
                    lines.append(f"  - {sender}: {content}")
            
            # Pending trade offers
            pending_offers = interactions.get('pending_trade_offers', []) or interactions.get('pending_offers', [])
            if pending_offers:
                lines.append(f"\nPending Trade Offers ({len(pending_offers)}):")
                for offer in pending_offers:
                    transaction_id = offer.get('transaction_id', 'N/A')
                    offer_type = offer.get('offer_type')
                    shape = offer.get('shape') or offer.get('trade_item', 'N/A')
                    price = offer.get('price')
                    from_name = offer.get('from', 'Unknown')
                    to_name = offer.get('to', 'Unknown')
                    # Determine if this is our offer or someone else's
                    if our_name and from_name == our_name:
                        lines.append(f"  - Transaction ID: {transaction_id} | You offered to {offer_type} {shape} to {to_name} at ${price}")
                    elif our_name and to_name == our_name:
                        lines.append(f"  - Transaction ID: {transaction_id} | {from_name} offers to {offer_type} {shape} at ${price}")
                    else:
                        # Group offer or other scenario
                        lines.append(f"  - Transaction ID: {transaction_id} | {from_name} offers to {offer_type} {shape} to {to_name} at ${price}")
            
            # Recent trades
            recent_trades = interactions.get('recent_trades', [])
            if recent_trades:
                lines.append(f"\nRecent Trades ({len(recent_trades)}):")
                for trade in recent_trades[:3]:
                    from_name = trade.get('from', 'Unknown')
                    to_name = trade.get('to', 'Unknown')
                    offer_type = trade.get('offer_type')
                    shape = trade.get('shape', 'N/A')
                    price = trade.get('price')
                    status = trade.get('status')
                    if our_name and from_name == our_name:
                        lines.append(f"  - You {offer_type} {shape} to {to_name} at ${price} ({status})")
                    elif our_name and to_name == our_name:
                        lines.append(f"  - {from_name} {offer_type} {shape} to you at ${price} ({status})")
                    else:
                        lines.append(f"  - {from_name} {offer_type} {shape} to {to_name} at ${price} ({status})")
            
            # Other rankings (EssayRanking)
            other_rankings = interactions.get('other_rankings', {})
            if other_rankings:
                lines.append("\nOther Participants' Rankings:")
                for p_name, rankings in other_rankings.items():
                    lines.append(f"  - {p_name}: {len(rankings)} ranked")
        
        # Other participants (based on awareness dashboard)
        other_participants = perception.get('other_participants', [])
        if other_participants:
            lines.append("\n=== Other Participants (Awareness Dashboard) ===")
            for p in other_participants:
                p_name = p.get('name', 'Unknown')
                lines.append(f"\n{p_name}:")
                # Add all visible fields (excluding 'id')
                for key, value in sorted(p.items()):
                    if key in ['name', 'id']:
                        continue
                    if value is not None:
                        if key == 'investment_history' and isinstance(value, list):
                            # Special formatting for investment_history
                            if value:
                                lines.append(f"  {key}:")
                                for inv in value:
                                    inv_type = inv.get('investment_type', 'N/A')
                                    inv_amount = inv.get('investment_amount', 0)
                                    money_before = inv.get('money_before', 0)
                                    money_after = inv.get('money_after', 0)
                                    timestamp = inv.get('timestamp', 'N/A')
                                    lines.append(f"    - {inv_type}: ${inv_amount} (Money: ${money_before} → ${money_after}) at {timestamp}")
                            else:
                                lines.append(f"  {key}: []")
                        elif isinstance(value, list):
                            if value:
                                lines.append(f"  {key}: {value}")
                            else:
                                lines.append(f"  {key}: []")
                        elif isinstance(value, dict):
                            lines.append(f"  {key}: {json.dumps(value, indent=4)}")
                        else:
                            lines.append(f"  {key}: {value}")
        else:
            lines.append("\n=== Other Participants ===")
            lines.append("  (Awareness Dashboard is disabled - no information available)")
        
        return '\n'.join(lines)
    
    def _get_other_rankings(self, participant: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, list]:
        """Get other participants' rankings for EssayRanking"""
        participants = session.get('participants', [])
        other_rankings = {}
        
        for p in participants:
            if p.get('id') == self.participant_id:
                continue
            
            p_name = p.get('name') or p.get('participant_name')
            exp_params = p.get('experiment_params', {})
            rankings = exp_params.get('rankings', [])
            if rankings:
                other_rankings[p_name] = rankings
        
        return other_rankings
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM to generate actions"""
        if not self.llm_client:
            # Mock response for testing
            print(f'[AgentRunner] Mock LLM called (no LLM client)')
            return self._mock_llm_response()
        
        try:
            # Use unified LLM client interface
            # Note: response_format is handled by the client implementation
            response = self.llm_client.chat_completions_create(
                messages=[
                    {"role": "system", "content": "You are an AI agent participating in an economic experiment. Follow the instructions carefully and respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4096,
                response_format={"type": "json_object"}  # Request JSON response
            )
            
            return response
            
        except Exception as e:
            print(f'[AgentRunner] Error calling LLM: {e}')
            import traceback
            traceback.print_exc()
            return None
    
    def _mock_llm_response(self) -> str:
        """Mock LLM response for testing"""
        return json.dumps({
            "planning": "Mock planning: I will wait and observe.",
            "actions": []
        })
    
    def _parse_response(self, response: str) -> list:
        """Parse LLM response to extract actions"""
        try:
            data = json.loads(response)
            actions = data.get('actions', [])
            
            if not isinstance(actions, list):
                return []
            
            return actions
            
        except json.JSONDecodeError as e:
            print(f'[AgentRunner] Error parsing LLM response: {e}')
            print(f'[AgentRunner] Response: {response[:200]}...')
            return []
    
    def _load_prompt_template(self, participant: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Load prompt template for the experiment type (supports role-specific prompts)"""
        import os
        
        # Determine prompt file name based on experiment type and role
        if self.experiment_type == 'wordguessing':
            role = self.participant_role or (participant.get('role') if participant else None)
            if role == 'hinter':
                prompt_name = 'wordguessing_hinter'
            else:
                prompt_name = 'wordguessing_guesser'
        else:
            prompt_name = f'{self.experiment_type}_agent'
        
        # Try relative to this file (most reliable)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_file = os.path.join(current_dir, 'prompts', f'{prompt_name}_prompt.txt')
        
        if os.path.exists(prompt_file):
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f'[AgentRunner] Error reading prompt file: {e}')
        
        # Try relative to current working directory
        cwd = os.getcwd()
        prompt_file_abs = os.path.join(cwd, 'backend', 'agent', 'prompts', f'{prompt_name}_prompt.txt')
        if os.path.exists(prompt_file_abs):
            try:
                with open(prompt_file_abs, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f'[AgentRunner] Error reading prompt file: {e}')
        
        print(f'[AgentRunner] Warning: Prompt template not found for {self.experiment_type} (role: {self.participant_role})')
        return None
    
    def _find_participant(self, session: Dict[str, Any]):
        """Find participant by participant_id"""
        participants = session.get('participants', [])
        for p in participants:
            if p.get('id') == self.participant_id:
                return p
        return None


# Global registry of agent runners
_agent_runners: Dict[str, AgentRunner] = {}


def get_agent_runner(participant_id: str, session_id: str) -> Optional[AgentRunner]:
    """Get agent runner for a participant"""
    key = f"{session_id}:{participant_id}"
    return _agent_runners.get(key)


def register_agent_runner(
    participant_id: str, 
    session_id: str, 
    experiment_type: str, 
    participant_role: Optional[str] = None,
    llm_config: Optional[Dict[str, Any]] = None
) -> AgentRunner:
    """
    Register and start an agent runner
    
    Args:
        participant_id: The ID of the agent participant
        session_id: The ID of the session
        experiment_type: The experiment type (e.g., 'shapefactory')
        participant_role: Optional participant role (e.g., 'guesser', 'hinter' for wordguessing)
        llm_config: Optional LLM configuration dict (overrides environment variables)
    
    Returns:
        AgentRunner instance
    """
    key = f"{session_id}:{participant_id}"
    
    if key in _agent_runners:
        # Already registered - ensure it's started (idempotent)
        runner = _agent_runners[key]
        runner.start()
        return runner
    
    runner = AgentRunner(
        participant_id, 
        session_id, 
        experiment_type, 
        participant_role=participant_role,
        llm_config=llm_config
    )
    _agent_runners[key] = runner
    
    # Start immediately - perception loop will wait until session status is 'running'
    # before taking actions (see _perception_loop)
    runner.start()
    
    return runner


def start_agent_runner(participant_id: str, session_id: str):
    """Start agent runner for a participant and mark as online"""
    runner = get_agent_runner(participant_id, session_id)
    if runner:
        runner.start()
        print(f'[AgentRunner] Started agent runner for participant {participant_id}')
        
        # Mark participant as online and broadcast update
        try:
            sessions = session_module.sessions
            session_key, session = find_session_by_identifier(session_id)
            if not session:
                print(f'[AgentRunner] Warning: Session {session_id} not found when updating online status')
                return
            
            participants = session.get('participants', [])
            updated = False
            participant_name = None
            
            for participant in participants:
                if participant.get('id') == participant_id:
                    old_status = participant.get('status', 'offline')
                    participant['status'] = 'online'
                    participant_name = participant.get('name') or participant.get('participant_name')
                    updated = True
                    print(f'[AgentRunner] Updated status for participant {participant_id} ({participant_name}): {old_status} -> online')
                    break
            
            if updated:
                session['participants'] = participants
                sessions[session_key] = session
                
                # Broadcast update
                from websocket.handlers import broadcast_participant_update
                broadcast_participant_update(
                    session_id=session_id,
                    participants=participants,
                    session_info=session,
                    update_type='partial'
                )
                print(f'[AgentRunner] Broadcasted online status update for participant {participant_id} ({participant_name})')
            else:
                print(f'[AgentRunner] Warning: Participant {participant_id} not found in session when updating online status')
        except Exception as e:
            print(f'[AgentRunner] Error updating online status: {e}')
            import traceback
            traceback.print_exc()
    else:
        print(f'[AgentRunner] Warning: Runner not found for participant {participant_id} in session {session_id}. Make sure agent is registered first.')


def stop_agent_runner(participant_id: str, session_id: str):
    """Stop agent runner for a participant and mark as offline"""
    runner = get_agent_runner(participant_id, session_id)
    if runner:
        runner.stop()
        key = f"{session_id}:{participant_id}"
        del _agent_runners[key]
        
        # Mark participant as offline and broadcast update
        try:
            sessions = session_module.sessions
            session_key, session = find_session_by_identifier(session_id)
            if session:
                participants = session.get('participants', [])
                updated = False
                
                for participant in participants:
                    if participant.get('id') == participant_id:
                        old_status = participant.get('status', 'online')
                        participant['status'] = 'offline'
                        updated = True
                        print(f'[AgentRunner] Updated status for participant {participant_id}: {old_status} -> offline')
                        break
                
                if updated:
                    session['participants'] = participants
                    sessions[session_key] = session
                    
                    # Broadcast update
                    from websocket.handlers import broadcast_participant_update
                    broadcast_participant_update(
                        session_id=session_id,
                        participants=participants,
                        session_info=session,
                        update_type='partial'
                    )
                    print(f'[AgentRunner] Marked participant {participant_id} as offline')
        except Exception as e:
            print(f'[AgentRunner] Error updating offline status: {e}')


def stop_all_agent_runners():
    """Stop all agent runners"""
    for runner in _agent_runners.values():
        runner.stop()
    _agent_runners.clear()

