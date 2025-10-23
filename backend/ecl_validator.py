"""
ECL Schema Validator

This module provides comprehensive validation for ECL configurations,
including type checking, constraint validation, and semantic analysis.
"""

import re
import math
from typing import Dict, List, Any, Optional, Union, Set
from dataclasses import dataclass
from ecl_parser import ECLConfig, ECLType, ECLTypeKind, ECLValidationError


@dataclass
class ValidationResult:
    """Result of ECL validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]


class ECLValidator:
    """Comprehensive validator for ECL configurations"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.suggestions: List[str] = []
        self.validated_types: Set[str] = set()
        self.validated_objects: Set[str] = set()
    
    def validate(self, config: ECLConfig) -> ValidationResult:
        """Validate a complete ECL configuration"""
        self.errors = []
        self.warnings = []
        self.suggestions = []
        self.validated_types = set()
        self.validated_objects = set()
        
        try:
            # Validate each section
            self._validate_experiment_metadata(config)
            self._validate_types(config)
            self._validate_objects(config)
            self._validate_variables(config)
            self._validate_constraints(config)
            self._validate_policies(config)
            self._validate_actions(config)
            self._validate_views(config)
            
            # Cross-section validation
            self._validate_references(config)
            self._validate_semantic_consistency(config)
            
        except Exception as e:
            self.errors.append(f"Validation failed with exception: {str(e)}")
        
        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
            suggestions=self.suggestions
        )
    
    def _validate_experiment_metadata(self, config: ECLConfig):
        """Validate experiment metadata section"""
        experiment = config.experiment
        
        # Check required fields
        required_fields = ['id', 'title', 'description']
        for field in required_fields:
            if field not in experiment:
                self.errors.append(f"Experiment missing required field: {field}")
        
        # Validate experiment ID format
        if 'id' in experiment:
            exp_id = experiment['id']
            if not isinstance(exp_id, str) or not re.match(r'^[a-zA-Z0-9_]+$', exp_id):
                self.errors.append("Experiment ID must be alphanumeric with underscores only")
        
        # Validate timing configuration
        if 'timing' in experiment:
            timing = experiment['timing']
            if 'session_duration_minutes' in timing:
                duration = timing['session_duration_minutes']
                if not isinstance(duration, (int, float)) or duration <= 0:
                    self.errors.append("Session duration must be a positive number")
                elif duration > 1440:  # 24 hours
                    self.warnings.append("Session duration is very long (>24 hours)")
    
    def _validate_types(self, config: ECLConfig):
        """Validate type definitions"""
        for type_name, type_def in config.types.items():
            self._validate_type_definition(type_name, type_def, config)
            self.validated_types.add(type_name)
    
    def _validate_type_definition(self, type_name: str, type_def: ECLType, config: ECLConfig):
        """Validate a single type definition"""
        # Check type name format
        if not re.match(r'^[A-Z][a-zA-Z0-9_]*$', type_name):
            self.errors.append(f"Type name '{type_name}' should start with uppercase letter and contain only alphanumeric characters and underscores")
        
        if type_def.kind == ECLTypeKind.SCALAR:
            # Validate scalar type
            if not type_def.base:
                self.errors.append(f"Scalar type '{type_name}' missing base type")
            elif type_def.base not in ['string', 'number', 'boolean', 'integer']:
                self.errors.append(f"Scalar type '{type_name}' has invalid base type '{type_def.base}'")
            
            # Validate constraints
            if type_def.min_val is not None and type_def.max_val is not None:
                if type_def.min_val > type_def.max_val:
                    self.errors.append(f"Type '{type_name}' has min > max")
            
            if type_def.max_len is not None and type_def.max_len <= 0:
                self.errors.append(f"Type '{type_name}' has invalid max_len")
        
        elif type_def.kind == ECLTypeKind.ENUM:
            # Validate enum type
            if not type_def.values:
                self.errors.append(f"Enum type '{type_name}' missing values")
            elif len(type_def.values) == 0:
                self.errors.append(f"Enum type '{type_name}' has empty values list")
            else:
                # Check for duplicate values
                if len(type_def.values) != len(set(type_def.values)):
                    self.errors.append(f"Enum type '{type_name}' has duplicate values")
                
                # Check value format
                for value in type_def.values:
                    if not isinstance(value, str):
                        self.errors.append(f"Enum type '{type_name}' has non-string value: {value}")
                    elif not re.match(r'^[a-zA-Z0-9_]+$', value):
                        self.warnings.append(f"Enum type '{type_name}' has value '{value}' with non-standard characters")
        
        elif type_def.kind == ECLTypeKind.REF:
            # Validate ref type
            if not type_def.of:
                self.errors.append(f"Ref type '{type_name}' missing 'of' field")
            elif type_def.of not in config.objects:
                self.errors.append(f"Ref type '{type_name}' references unknown object '{type_def.of}'")
    
    def _validate_objects(self, config: ECLConfig):
        """Validate object definitions"""
        for obj_name, obj_def in config.objects.items():
            self._validate_object_definition(obj_name, obj_def, config)
            self.validated_objects.add(obj_name)
    
    def _validate_object_definition(self, obj_name: str, obj_def, config: ECLConfig):
        """Validate a single object definition"""
        # Check object name format
        if not re.match(r'^[A-Z][a-zA-Z0-9_]*$', obj_name):
            self.errors.append(f"Object name '{obj_name}' should start with uppercase letter and contain only alphanumeric characters and underscores")
        
        # Validate key field
        if not obj_def.key:
            self.errors.append(f"Object '{obj_name}' missing key field")
        elif not isinstance(obj_def.key, str):
            self.errors.append(f"Object '{obj_name}' key must be a string")
        
        # Validate attributes
        if not obj_def.attrs:
            self.warnings.append(f"Object '{obj_name}' has no attributes")
        else:
            for attr_name, attr_def in obj_def.attrs.items():
                self._validate_object_attribute(obj_name, attr_name, attr_def, config)
    
    def _validate_object_attribute(self, obj_name: str, attr_name: str, attr_def, config: ECLConfig):
        """Validate a single object attribute"""
        # Check attribute name format
        if not re.match(r'^[a-z][a-zA-Z0-9_]*$', attr_name):
            self.errors.append(f"Attribute '{obj_name}.{attr_name}' should start with lowercase letter and contain only alphanumeric characters and underscores")
        
        # Validate type reference
        if attr_def.type_name not in config.types:
            self.errors.append(f"Attribute '{obj_name}.{attr_name}' references unknown type '{attr_def.type_name}'")
        
        # Validate default value
        if attr_def.default is not None:
            self._validate_default_value(obj_name, attr_name, attr_def, config)
    
    def _validate_default_value(self, obj_name: str, attr_name: str, attr_def, config: ECLConfig):
        """Validate default value for an attribute"""
        type_def = config.types.get(attr_def.type_name)
        if not type_def:
            return  # Already handled in type reference validation
        
        default = attr_def.default
        
        if type_def.kind == ECLTypeKind.SCALAR:
            if type_def.base == 'string':
                if not isinstance(default, str):
                    self.errors.append(f"Attribute '{obj_name}.{attr_name}' default value must be a string")
                elif type_def.max_len and len(default) > type_def.max_len:
                    self.errors.append(f"Attribute '{obj_name}.{attr_name}' default value exceeds max_len")
            elif type_def.base in ['number', 'integer']:
                if not isinstance(default, (int, float)):
                    self.errors.append(f"Attribute '{obj_name}.{attr_name}' default value must be a number")
                if type_def.min_val is not None and default < type_def.min_val:
                    self.errors.append(f"Attribute '{obj_name}.{attr_name}' default value below minimum")
                if type_def.max_val is not None and default > type_def.max_val:
                    self.errors.append(f"Attribute '{obj_name}.{attr_name}' default value above maximum")
            elif type_def.base == 'boolean':
                if not isinstance(default, bool):
                    self.errors.append(f"Attribute '{obj_name}.{attr_name}' default value must be a boolean")
        
        elif type_def.kind == ECLTypeKind.ENUM:
            if default not in type_def.values:
                self.errors.append(f"Attribute '{obj_name}.{attr_name}' default value '{default}' not in enum values")
    
    def _validate_variables(self, config: ECLConfig):
        """Validate variable definitions"""
        for var_name, var_value in config.variables.items():
            # Check variable name format
            if not re.match(r'^[a-z][a-zA-Z0-9_]*$', var_name):
                self.errors.append(f"Variable name '{var_name}' should start with lowercase letter and contain only alphanumeric characters and underscores")
            
            # Validate variable value
            if not isinstance(var_value, (str, int, float, bool)):
                self.errors.append(f"Variable '{var_name}' has invalid value type")
            elif isinstance(var_value, (int, float)) and var_value < 0:
                self.warnings.append(f"Variable '{var_name}' has negative value")
    
    def _validate_constraints(self, config: ECLConfig):
        """Validate constraint definitions"""
        for i, constraint in enumerate(config.constraints):
            if not isinstance(constraint, dict):
                self.errors.append(f"Constraint {i} must be a dictionary")
                continue
            
            if 'on' not in constraint:
                self.errors.append(f"Constraint {i} missing 'on' field")
                continue
            
            if 'rule' not in constraint:
                self.errors.append(f"Constraint {i} missing 'rule' field")
                continue
            
            # Validate constraint target
            on_field = constraint['on']
            if '.' not in on_field:
                self.errors.append(f"Constraint {i} 'on' field must be in format 'Object.attribute'")
                continue
            
            obj_name, attr_name = on_field.split('.', 1)
            if obj_name not in config.objects:
                self.errors.append(f"Constraint {i} references unknown object '{obj_name}'")
            elif attr_name not in config.objects[obj_name].attrs:
                self.errors.append(f"Constraint {i} references unknown attribute '{obj_name}.{attr_name}'")
            
            # Validate rule syntax (basic check)
            rule = constraint['rule']
            if not isinstance(rule, str) or len(rule.strip()) == 0:
                self.errors.append(f"Constraint {i} has empty rule")
    
    def _validate_policies(self, config: ECLConfig):
        """Validate policy definitions"""
        if not config.policies:
            return
        
        # Validate actions policies
        if 'actions' in config.policies:
            actions_policy = config.policies['actions']
            if not isinstance(actions_policy, dict):
                self.errors.append("Actions policy must be a dictionary")
            else:
                for action_name, policy in actions_policy.items():
                    if action_name not in config.actions:
                        self.errors.append(f"Action policy references unknown action '{action_name}'")
        
        # Validate visibility policies
        if 'visibility' in config.policies:
            visibility_policy = config.policies['visibility']
            if not isinstance(visibility_policy, dict):
                self.errors.append("Visibility policy must be a dictionary")
    
    def _validate_actions(self, config: ECLConfig):
        """Validate action definitions"""
        for action_name, action_def in config.actions.items():
            self._validate_action_definition(action_name, action_def, config)
    
    def _validate_action_definition(self, action_name: str, action_def, config: ECLConfig):
        """Validate a single action definition"""
        # Check action name format
        if not re.match(r'^[A-Z][a-zA-Z0-9_]*$', action_name):
            self.errors.append(f"Action name '{action_name}' should start with uppercase letter and contain only alphanumeric characters and underscores")
        
        # Validate input schema
        if not isinstance(action_def.input_schema, dict):
            self.errors.append(f"Action '{action_name}' input schema must be a dictionary")
        else:
            for input_name, input_def in action_def.input_schema.items():
                self._validate_action_input(action_name, input_name, input_def, config)
        
        # Validate preconditions
        if not isinstance(action_def.preconditions, list):
            self.errors.append(f"Action '{action_name}' preconditions must be a list")
        
        # Validate effects
        if not isinstance(action_def.effects, list):
            self.errors.append(f"Action '{action_name}' effects must be a list")
        else:
            for i, effect in enumerate(action_def.effects):
                self._validate_action_effect(action_name, i, effect, config)
    
    def _validate_action_input(self, action_name: str, input_name: str, input_def, config: ECLConfig):
        """Validate an action input definition"""
        if not isinstance(input_def, dict):
            self.errors.append(f"Action '{action_name}' input '{input_name}' must be a dictionary")
            return
        
        if 'type' in input_def:
            type_name = input_def['type']
            if type_name not in config.types:
                self.errors.append(f"Action '{action_name}' input '{input_name}' references unknown type '{type_name}'")
    
    def _validate_action_effect(self, action_name: str, effect_index: int, effect, config: ECLConfig):
        """Validate an action effect definition"""
        if not isinstance(effect, dict):
            self.errors.append(f"Action '{action_name}' effect {effect_index} must be a dictionary")
            return
        
        # Check for valid effect types
        valid_effect_types = ['create', 'set', 'inc', 'dec', 'compute', 'foreach', 'choose']
        effect_type = None
        for key in effect.keys():
            if key in valid_effect_types:
                effect_type = key
                break
        
        if not effect_type:
            self.errors.append(f"Action '{action_name}' effect {effect_index} has no valid effect type")
    
    def _validate_views(self, config: ECLConfig):
        """Validate view definitions"""
        for module_name, views in config.views.items():
            if not isinstance(views, list):
                self.errors.append(f"View module '{module_name}' must be a list")
                continue
            
            for view in views:
                self._validate_view_definition(module_name, view, config)
    
    def _validate_view_definition(self, module_name: str, view, config: ECLConfig):
        """Validate a single view definition"""
        # Check required fields
        if not hasattr(view, 'id') or not view.id:
            self.errors.append(f"View in module '{module_name}' missing id")
        
        if not hasattr(view, 'label') or not view.label:
            self.errors.append(f"View in module '{module_name}' missing label")
        
        # Validate bindings
        if hasattr(view, 'bindings') and view.bindings:
            for i, binding in enumerate(view.bindings):
                self._validate_view_binding(module_name, i, binding, config)
    
    def _validate_view_binding(self, module_name: str, binding_index: int, binding, config: ECLConfig):
        """Validate a view binding definition"""
        if not isinstance(binding, dict):
            self.errors.append(f"View module '{module_name}' binding {binding_index} must be a dictionary")
            return
        
        # Check for required fields
        if 'label' not in binding:
            self.errors.append(f"View module '{module_name}' binding {binding_index} missing label")
        
        # Validate path references
        if 'path' in binding:
            path = binding['path']
            if isinstance(path, str):
                self._validate_path_reference(module_name, binding_index, path, config)
    
    def _validate_path_reference(self, module_name: str, binding_index: int, path: str, config: ECLConfig):
        """Validate a path reference in a view binding"""
        # Basic path validation - check for object references
        if '.' in path:
            parts = path.split('.')
            if len(parts) >= 2:
                obj_name = parts[0]
                if obj_name in config.objects:
                    attr_name = parts[1]
                    if attr_name not in config.objects[obj_name].attrs:
                        self.warnings.append(f"View module '{module_name}' binding {binding_index} references unknown attribute '{obj_name}.{attr_name}'")
    
    def _validate_references(self, config: ECLConfig):
        """Validate cross-references between sections"""
        # Check that all referenced types exist
        for obj_name, obj_def in config.objects.items():
            for attr_name, attr_def in obj_def.attrs.items():
                if attr_def.type_name not in config.types:
                    self.errors.append(f"Object '{obj_name}' attribute '{attr_name}' references unknown type '{attr_def.type_name}'")
        
        # Check that all referenced objects exist in ref types
        for type_name, type_def in config.types.items():
            if type_def.kind == ECLTypeKind.REF and type_def.of not in config.objects:
                self.errors.append(f"Type '{type_name}' references unknown object '{type_def.of}'")
    
    def _validate_semantic_consistency(self, config: ECLConfig):
        """Validate semantic consistency of the configuration"""
        # Check for unused types
        used_types = set()
        for obj_def in config.objects.values():
            for attr_def in obj_def.attrs.values():
                used_types.add(attr_def.type_name)
        
        for action_def in config.actions.values():
            for input_def in action_def.input_schema.values():
                if isinstance(input_def, dict) and 'type' in input_def:
                    used_types.add(input_def['type'])
        
        unused_types = set(config.types.keys()) - used_types
        if unused_types:
            self.warnings.append(f"Unused types: {', '.join(unused_types)}")
        
        # Check for potential naming conflicts
        all_names = set()
        for section_name, section_items in [
            ('types', config.types.keys()),
            ('objects', config.objects.keys()),
            ('actions', config.actions.keys()),
            ('variables', config.variables.keys())
        ]:
            for name in section_items:
                if name in all_names:
                    self.warnings.append(f"Name '{name}' used in multiple sections")
                all_names.add(name)


def validate_ecl_config(config: ECLConfig) -> ValidationResult:
    """Convenience function to validate an ECL configuration"""
    validator = ECLValidator()
    return validator.validate(config)


def validate_ecl_file(file_path: str) -> ValidationResult:
    """Convenience function to validate an ECL file"""
    from ecl_parser import parse_ecl_file
    
    try:
        config = parse_ecl_file(file_path)
        return validate_ecl_config(config)
    except ECLValidationError as e:
        return ValidationResult(
            is_valid=False,
            errors=[str(e)],
            warnings=[],
            suggestions=[]
        )
