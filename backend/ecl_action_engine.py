"""
ECL Action Execution Engine

This module provides functionality to execute ECL-defined actions and effects.
It handles the evaluation of preconditions, execution of effects, and state management
according to the ECL specification.
"""

import json
import uuid
import time
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timezone
from ecl_parser import ECLConfig, ECLAction, ECLType, ECLTypeKind


@dataclass
class ECLState:
    """Represents the current state of an ECL experiment"""
    objects: Dict[str, Dict[str, Any]]  # object_type -> {id -> attributes}
    variables: Dict[str, Any]
    session_id: str
    created_at: datetime
    updated_at: datetime


@dataclass
class ActionResult:
    """Result of executing an ECL action"""
    success: bool
    message: str
    effects_applied: List[Dict[str, Any]]
    errors: List[str]
    warnings: List[str]


class ECLExpressionEvaluator:
    """Evaluates ECL expressions and conditions"""
    
    def __init__(self, state: ECLState, config: ECLConfig):
        self.state = state
        self.config = config
        self.context = {}
    
    def evaluate_expression(self, expression: str, context: Dict[str, Any] = None) -> Any:
        """Evaluate an ECL expression"""
        if context:
            self.context.update(context)
        
        try:
            # Replace ECL-specific functions and references
            processed_expr = self._process_expression(expression)
            
            # Evaluate the expression safely
            return self._safe_eval(processed_expr)
        except Exception as e:
            raise ValueError(f"Failed to evaluate expression '{expression}': {str(e)}")
    
    def _process_expression(self, expression: str) -> str:
        """Process ECL expression to make it evaluable"""
        # Replace ECL function calls
        expression = expression.replace('uuid()', f'"{str(uuid.uuid4())}"')
        expression = expression.replace('now()', f'{int(time.time())}')
        
        # Replace object references (e.g., Participant.endowment(actor.id))
        import re
        
        # Pattern for object.attribute(id) calls
        obj_attr_pattern = r'(\w+)\.(\w+)\(([^)]+)\)'
        matches = re.findall(obj_attr_pattern, expression)
        
        for obj_name, attr_name, obj_id in matches:
            if obj_name in self.state.objects:
                # Get the actual object ID
                actual_id = self._resolve_object_id(obj_id)
                if actual_id in self.state.objects[obj_name]:
                    value = self.state.objects[obj_name][actual_id].get(attr_name)
                    if value is not None:
                        expression = expression.replace(f'{obj_name}.{attr_name}({obj_id})', str(value))
        
        # Replace variable references
        for var_name, var_value in self.state.variables.items():
            expression = expression.replace(f'variables.{var_name}', str(var_value))
        
        # Replace context variables
        for var_name, var_value in self.context.items():
            expression = expression.replace(f'$local.{var_name}', str(var_value))
            expression = expression.replace(f'actor.{var_name}', str(var_value))
        
        return expression
    
    def _resolve_object_id(self, obj_id: str) -> str:
        """Resolve object ID reference"""
        # Handle actor.id
        if obj_id == 'actor.id' and 'actor' in self.context:
            return self.context['actor'].get('id', obj_id)
        
        # Handle quoted strings
        if obj_id.startswith('"') and obj_id.endswith('"'):
            return obj_id[1:-1]
        
        return obj_id
    
    def _safe_eval(self, expression: str) -> Any:
        """Safely evaluate a Python expression"""
        # Only allow safe operations
        allowed_names = {
            'True': True, 'False': False, 'None': None,
            'len': len, 'sum': sum, 'min': min, 'max': max,
            'abs': abs, 'round': round, 'int': int, 'float': float,
            'str': str, 'bool': bool, 'list': list, 'dict': dict,
            'filter': filter, 'map': map, 'count': lambda x: len(x) if hasattr(x, '__len__') else 1
        }
        
        try:
            return eval(expression, {"__builtins__": {}}, allowed_names)
        except Exception as e:
            raise ValueError(f"Expression evaluation failed: {str(e)}")


class ECLActionEngine:
    """Executes ECL actions and manages state changes"""
    
    def __init__(self, config: ECLConfig, db_connection=None):
        self.config = config
        self.db_connection = db_connection
        self.state: Optional[ECLState] = None
        self.evaluator: Optional[ECLExpressionEvaluator] = None
    
    def initialize_state(self, session_id: str) -> ECLState:
        """Initialize the ECL state for a session"""
        # Initialize objects
        objects = {}
        for obj_name, obj_def in self.config.objects.items():
            objects[obj_name] = {}
        
        # Create default session object if it exists
        if 'Session' in self.config.objects:
            session_obj = self._create_default_object('Session', {'id': session_id})
            objects['Session'][session_id] = session_obj
        
        state = ECLState(
            objects=objects,
            variables=self.config.variables.copy(),
            session_id=session_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        self.state = state
        self.evaluator = ECLExpressionEvaluator(state, self.config)
        
        return state
    
    def load_state_from_db(self, session_id: str) -> ECLState:
        """Load ECL state from database"""
        if not self.db_connection:
            raise ValueError("Database connection required to load state")
        
        # This would load the state from the database
        # For now, initialize a new state
        return self.initialize_state(session_id)
    
    def save_state_to_db(self, state: ECLState):
        """Save ECL state to database"""
        if not self.db_connection:
            return  # No database connection, state is in-memory only
        
        # This would save the state to the database
        # For now, just update the timestamp
        state.updated_at = datetime.now(timezone.utc)
    
    def execute_action(self, action_name: str, inputs: Dict[str, Any], 
                      actor_id: str, session_id: str) -> ActionResult:
        """Execute an ECL action"""
        if action_name not in self.config.actions:
            return ActionResult(
                success=False,
                message=f"Unknown action: {action_name}",
                effects_applied=[],
                errors=[f"Action '{action_name}' not found"],
                warnings=[]
            )
        
        action = self.config.actions[action_name]
        
        # Set up evaluation context
        context = {
            'actor': {'id': actor_id},
            'input': inputs,
            'session_id': session_id
        }
        
        # Evaluate preconditions
        preconditions_met, precondition_errors = self._evaluate_preconditions(
            action.preconditions, context
        )
        
        if not preconditions_met:
            return ActionResult(
                success=False,
                message="Preconditions not met",
                effects_applied=[],
                errors=precondition_errors,
                warnings=[]
            )
        
        # Execute effects
        effects_applied = []
        effect_errors = []
        effect_warnings = []
        
        try:
            for effect in action.effects:
                effect_result = self._execute_effect(effect, context)
                if effect_result['success']:
                    effects_applied.append(effect_result)
                else:
                    effect_errors.append(effect_result.get('error', 'Unknown effect error'))
        except Exception as e:
            effect_errors.append(f"Effect execution failed: {str(e)}")
        
        # Save state if no errors
        if not effect_errors:
            self.save_state_to_db(self.state)
        
        return ActionResult(
            success=len(effect_errors) == 0,
            message="Action executed successfully" if not effect_errors else "Action failed",
            effects_applied=effects_applied,
            errors=effect_errors,
            warnings=effect_warnings
        )
    
    def _evaluate_preconditions(self, preconditions: List[str], context: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Evaluate action preconditions"""
        errors = []
        
        for precondition in preconditions:
            try:
                result = self.evaluator.evaluate_expression(precondition, context)
                if not result:
                    errors.append(f"Precondition failed: {precondition}")
            except Exception as e:
                errors.append(f"Precondition evaluation error: {str(e)}")
        
        return len(errors) == 0, errors
    
    def _execute_effect(self, effect: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single effect"""
        try:
            if 'create' in effect:
                return self._execute_create_effect(effect['create'], context)
            elif 'set' in effect:
                return self._execute_set_effect(effect['set'], context)
            elif 'inc' in effect:
                return self._execute_inc_effect(effect['inc'], context)
            elif 'dec' in effect:
                return self._execute_dec_effect(effect['dec'], context)
            elif 'compute' in effect:
                return self._execute_compute_effect(effect['compute'], context)
            elif 'foreach' in effect:
                return self._execute_foreach_effect(effect['foreach'], context)
            elif 'choose' in effect:
                return self._execute_choose_effect(effect['choose'], context)
            else:
                return {'success': False, 'error': 'Unknown effect type'}
        except Exception as e:
            return {'success': False, 'error': f'Effect execution error: {str(e)}'}
    
    def _execute_create_effect(self, create_effect: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a create effect"""
        obj_type = create_effect.get('type')
        if not obj_type or obj_type not in self.config.objects:
            return {'success': False, 'error': f'Unknown object type: {obj_type}'}
        
        # Generate object values
        values = {}
        for attr_name, attr_value in create_effect.get('value', {}).items():
            if isinstance(attr_value, str) and attr_value.startswith('"') and attr_value.endswith('"'):
                values[attr_name] = attr_value[1:-1]  # Remove quotes
            else:
                values[attr_name] = self.evaluator.evaluate_expression(str(attr_value), context)
        
        # Create the object
        obj_id = values.get('id', str(uuid.uuid4()))
        self.state.objects[obj_type][obj_id] = values
        
        return {'success': True, 'created': {obj_type: obj_id}, 'values': values}
    
    def _execute_set_effect(self, set_effect: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a set effect"""
        target = set_effect.get('target')
        value = set_effect.get('to')
        
        if not target or value is None:
            return {'success': False, 'error': 'Set effect missing target or value'}
        
        # Parse target (e.g., "Session.settled('S')")
        import re
        match = re.match(r'(\w+)\.(\w+)\(([^)]+)\)', target)
        if not match:
            return {'success': False, 'error': f'Invalid set target: {target}'}
        
        obj_type, attr_name, obj_id = match.groups()
        actual_id = self.evaluator._resolve_object_id(obj_id)
        
        if obj_type not in self.state.objects or actual_id not in self.state.objects[obj_type]:
            return {'success': False, 'error': f'Object not found: {obj_type}.{actual_id}'}
        
        # Set the value
        evaluated_value = self.evaluator.evaluate_expression(str(value), context)
        self.state.objects[obj_type][actual_id][attr_name] = evaluated_value
        
        return {'success': True, 'set': {target: evaluated_value}}
    
    def _execute_inc_effect(self, inc_effect: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an increment effect"""
        target = inc_effect.get('target')
        by_value = inc_effect.get('by', 1)
        
        if not target:
            return {'success': False, 'error': 'Inc effect missing target'}
        
        # Parse target and increment
        import re
        match = re.match(r'(\w+)\.(\w+)\(([^)]+)\)', target)
        if not match:
            return {'success': False, 'error': f'Invalid inc target: {target}'}
        
        obj_type, attr_name, obj_id = match.groups()
        actual_id = self.evaluator._resolve_object_id(obj_id)
        
        if obj_type not in self.state.objects or actual_id not in self.state.objects[obj_type]:
            return {'success': False, 'error': f'Object not found: {obj_type}.{actual_id}'}
        
        # Increment the value
        current_value = self.state.objects[obj_type][actual_id].get(attr_name, 0)
        increment = self.evaluator.evaluate_expression(str(by_value), context)
        new_value = current_value + increment
        self.state.objects[obj_type][actual_id][attr_name] = new_value
        
        return {'success': True, 'incremented': {target: new_value}}
    
    def _execute_dec_effect(self, dec_effect: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a decrement effect"""
        target = dec_effect.get('target')
        by_value = dec_effect.get('by', 1)
        
        if not target:
            return {'success': False, 'error': 'Dec effect missing target'}
        
        # Parse target and decrement
        import re
        match = re.match(r'(\w+)\.(\w+)\(([^)]+)\)', target)
        if not match:
            return {'success': False, 'error': f'Invalid dec target: {target}'}
        
        obj_type, attr_name, obj_id = match.groups()
        actual_id = self.evaluator._resolve_object_id(obj_id)
        
        if obj_type not in self.state.objects or actual_id not in self.state.objects[obj_type]:
            return {'success': False, 'error': f'Object not found: {obj_type}.{actual_id}'}
        
        # Decrement the value
        current_value = self.state.objects[obj_type][actual_id].get(attr_name, 0)
        decrement = self.evaluator.evaluate_expression(str(by_value), context)
        new_value = current_value - decrement
        self.state.objects[obj_type][actual_id][attr_name] = new_value
        
        return {'success': True, 'decremented': {target: new_value}}
    
    def _execute_compute_effect(self, compute_effect: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a compute effect"""
        variable_name = compute_effect.get('variable')
        expression = compute_effect.get('expr')
        
        if not variable_name or not expression:
            return {'success': False, 'error': 'Compute effect missing variable or expression'}
        
        # Evaluate the expression and store the result
        result = self.evaluator.evaluate_expression(expression, context)
        context[variable_name] = result
        
        return {'success': True, 'computed': {variable_name: result}}
    
    def _execute_foreach_effect(self, foreach_effect: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a foreach effect"""
        collection = foreach_effect.get('in')
        effects = foreach_effect.get('do', [])
        
        if not collection or not effects:
            return {'success': False, 'error': 'Foreach effect missing collection or effects'}
        
        # Evaluate the collection
        collection_result = self.evaluator.evaluate_expression(collection, context)
        
        if not hasattr(collection_result, '__iter__'):
            return {'success': False, 'error': 'Foreach collection is not iterable'}
        
        # Execute effects for each item
        results = []
        for item in collection_result:
            item_context = context.copy()
            item_context['it'] = item
            item_context['item'] = item
            
            for effect in effects:
                effect_result = self._execute_effect(effect, item_context)
                results.append(effect_result)
        
        return {'success': True, 'foreach_results': results}
    
    def _execute_choose_effect(self, choose_effect: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a choose effect"""
        when_condition = choose_effect.get('when')
        then_effects = choose_effect.get('then', [])
        else_effects = choose_effect.get('else', [])
        
        if not when_condition:
            return {'success': False, 'error': 'Choose effect missing when condition'}
        
        # Evaluate the condition
        condition_result = self.evaluator.evaluate_expression(when_condition, context)
        
        # Execute appropriate effects
        effects_to_execute = then_effects if condition_result else else_effects
        results = []
        
        for effect in effects_to_execute:
            effect_result = self._execute_effect(effect, context)
            results.append(effect_result)
        
        return {'success': True, 'choose_results': results, 'condition_met': condition_result}
    
    def _create_default_object(self, obj_type: str, overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a default object with default values"""
        if obj_type not in self.config.objects:
            return {}
        
        obj_def = self.config.objects[obj_type]
        obj = {}
        
        # Set default values for all attributes
        for attr_name, attr_def in obj_def.attrs.items():
            if attr_def.default is not None:
                obj[attr_name] = attr_def.default
            elif attr_def.type_name in self.config.types:
                type_def = self.config.types[attr_def.type_name]
                if type_def.kind == ECLTypeKind.SCALAR:
                    if type_def.base == 'string':
                        obj[attr_name] = ''
                    elif type_def.base in ['number', 'integer']:
                        obj[attr_name] = 0
                    elif type_def.base == 'boolean':
                        obj[attr_name] = False
                elif type_def.kind == ECLTypeKind.ENUM:
                    obj[attr_name] = type_def.values[0] if type_def.values else None
        
        # Apply overrides
        if overrides:
            obj.update(overrides)
        
        return obj
    
    def get_object_value(self, obj_type: str, obj_id: str, attr_name: str) -> Any:
        """Get a value from an object"""
        if obj_type not in self.state.objects:
            return None
        
        if obj_id not in self.state.objects[obj_type]:
            return None
        
        return self.state.objects[obj_type][obj_id].get(attr_name)
    
    def get_participant_state(self, participant_id: str) -> Dict[str, Any]:
        """Get the current state for a participant"""
        if not self.state:
            return {}
        
        participant_state = {}
        
        # Get participant object if it exists
        if 'Participant' in self.state.objects and participant_id in self.state.objects['Participant']:
            participant_state.update(self.state.objects['Participant'][participant_id])
        
        # Get session state
        if 'Session' in self.state.objects and self.state.session_id in self.state.objects['Session']:
            participant_state['session'] = self.state.objects['Session'][self.state.session_id]
        
        # Get variables
        participant_state['variables'] = self.state.variables.copy()
        
        return participant_state


def create_action_engine(ecl_config: ECLConfig, db_connection=None) -> ECLActionEngine:
    """Convenience function to create an ECL action engine"""
    return ECLActionEngine(ecl_config, db_connection)
