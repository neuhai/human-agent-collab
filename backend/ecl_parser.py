"""
Experiment Configuration Language (ECL) Parser

This module provides functionality to parse and validate ECL configuration files,
which allow researchers to define experimental paradigms declaratively.
"""

import yaml
import json
import re
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum


class ECLValidationError(Exception):
    """Raised when ECL configuration validation fails"""
    pass


class ECLTypeKind(Enum):
    SCALAR = "scalar"
    ENUM = "enum"
    REF = "ref"


@dataclass
class ECLType:
    """Represents an ECL type definition"""
    kind: ECLTypeKind
    base: Optional[str] = None
    values: Optional[List[str]] = None
    min_val: Optional[Union[int, float]] = None
    max_val: Optional[Union[int, float]] = None
    max_len: Optional[int] = None
    of: Optional[str] = None  # For ref types


@dataclass
class ECLObjectAttr:
    """Represents an object attribute definition"""
    type_name: str
    required: bool = False
    default: Any = None


@dataclass
class ECLObject:
    """Represents an ECL object definition"""
    key: str
    attrs: Dict[str, ECLObjectAttr]


@dataclass
class ECLAction:
    """Represents an ECL action definition"""
    input_schema: Dict[str, Any]
    preconditions: List[str]
    effects: List[Dict[str, Any]]


@dataclass
class ECLView:
    """Represents an ECL view definition"""
    id: str
    label: str
    visible_if: str
    bindings: List[Dict[str, Any]]
    communication_level: Optional[str] = None


@dataclass
class ECLConfig:
    """Represents a complete ECL configuration"""
    ecl_version: str
    experiment: Dict[str, Any]
    types: Dict[str, ECLType]
    objects: Dict[str, ECLObject]
    variables: Dict[str, Any]
    constraints: List[Dict[str, str]]
    policies: Dict[str, Any]
    actions: Dict[str, ECLAction]
    views: Dict[str, List[ECLView]]


class ECLParser:
    """Parser for ECL configuration files"""
    
    def __init__(self):
        self.config: Optional[ECLConfig] = None
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def parse_file(self, file_path: str) -> ECLConfig:
        """Parse an ECL configuration file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.parse_yaml(content)
        except Exception as e:
            raise ECLValidationError(f"Failed to read file {file_path}: {str(e)}")
    
    def parse_yaml(self, yaml_content: str) -> ECLConfig:
        """Parse ECL configuration from YAML content"""
        try:
            data = yaml.safe_load(yaml_content)
            return self.parse_dict(data)
        except yaml.YAMLError as e:
            raise ECLValidationError(f"Invalid YAML: {str(e)}")
    
    def parse_dict(self, data: Dict[str, Any]) -> ECLConfig:
        """Parse ECL configuration from dictionary"""
        self.errors = []
        self.warnings = []
        
        # Validate required top-level sections
        required_sections = ['ecl_version', 'experiment', 'types', 'objects']
        for section in required_sections:
            if section not in data:
                self.errors.append(f"Missing required section: {section}")
        
        if self.errors:
            raise ECLValidationError(f"Validation errors: {'; '.join(self.errors)}")
        
        # Parse each section
        types = self._parse_types(data.get('types', {}))
        objects = self._parse_objects(data.get('objects', {}), types)
        actions = self._parse_actions(data.get('actions', {}), types)
        views = self._parse_views(data.get('views', {}), types)
        
        self.config = ECLConfig(
            ecl_version=data['ecl_version'],
            experiment=data['experiment'],
            types=types,
            objects=objects,
            variables=data.get('variables', {}),
            constraints=data.get('constraints', []),
            policies=data.get('policies', {}),
            actions=actions,
            views=views
        )
        
        # Validate the complete configuration
        self._validate_config()
        
        if self.errors:
            raise ECLValidationError(f"Validation errors: {'; '.join(self.errors)}")
        
        return self.config
    
    def _parse_types(self, types_data: Dict[str, Any]) -> Dict[str, ECLType]:
        """Parse type definitions"""
        types = {}
        
        for type_name, type_def in types_data.items():
            if not isinstance(type_def, dict):
                self.errors.append(f"Type {type_name} must be a dictionary")
                continue
            
            kind_str = type_def.get('kind')
            if not kind_str:
                self.errors.append(f"Type {type_name} missing 'kind' field")
                continue
            
            try:
                kind = ECLTypeKind(kind_str)
            except ValueError:
                self.errors.append(f"Invalid type kind '{kind_str}' for type {type_name}")
                continue
            
            if kind == ECLTypeKind.SCALAR:
                base = type_def.get('base')
                if not base:
                    self.errors.append(f"Scalar type {type_name} missing 'base' field")
                    continue
                
                types[type_name] = ECLType(
                    kind=kind,
                    base=base,
                    min_val=type_def.get('min'),
                    max_val=type_def.get('max'),
                    max_len=type_def.get('max_len')
                )
            
            elif kind == ECLTypeKind.ENUM:
                values = type_def.get('values')
                if not values or not isinstance(values, list):
                    self.errors.append(f"Enum type {type_name} missing or invalid 'values' field")
                    continue
                
                types[type_name] = ECLType(
                    kind=kind,
                    values=values
                )
            
            elif kind == ECLTypeKind.REF:
                of = type_def.get('of')
                if not of:
                    self.errors.append(f"Ref type {type_name} missing 'of' field")
                    continue
                
                types[type_name] = ECLType(
                    kind=kind,
                    of=of
                )
        
        return types
    
    def _parse_objects(self, objects_data: Dict[str, Any], types: Dict[str, ECLType]) -> Dict[str, ECLObject]:
        """Parse object definitions"""
        objects = {}
        
        for obj_name, obj_def in objects_data.items():
            if not isinstance(obj_def, dict):
                self.errors.append(f"Object {obj_name} must be a dictionary")
                continue
            
            key = obj_def.get('key')
            if not key:
                self.errors.append(f"Object {obj_name} missing 'key' field")
                continue
            
            attrs_data = obj_def.get('attrs', {})
            attrs = {}
            
            for attr_name, attr_def in attrs_data.items():
                if not isinstance(attr_def, dict):
                    self.errors.append(f"Attribute {obj_name}.{attr_name} must be a dictionary")
                    continue
                
                type_name = attr_def.get('type')
                if not type_name:
                    self.errors.append(f"Attribute {obj_name}.{attr_name} missing 'type' field")
                    continue
                
                if type_name not in types:
                    self.errors.append(f"Attribute {obj_name}.{attr_name} references unknown type {type_name}")
                    continue
                
                attrs[attr_name] = ECLObjectAttr(
                    type_name=type_name,
                    required=attr_def.get('required', False),
                    default=attr_def.get('default')
                )
            
            objects[obj_name] = ECLObject(
                key=key,
                attrs=attrs
            )
        
        return objects
    
    def _parse_actions(self, actions_data: Dict[str, Any], types: Dict[str, ECLType]) -> Dict[str, ECLAction]:
        """Parse action definitions"""
        actions = {}
        
        for action_name, action_def in actions_data.items():
            if not isinstance(action_def, dict):
                self.errors.append(f"Action {action_name} must be a dictionary")
                continue
            
            input_schema = action_def.get('input', {})
            preconditions = action_def.get('preconditions', [])
            effects = action_def.get('effects', [])
            
            actions[action_name] = ECLAction(
                input_schema=input_schema,
                preconditions=preconditions,
                effects=effects
            )
        
        return actions
    
    def _parse_views(self, views_data: Dict[str, Any], types: Dict[str, ECLType]) -> Dict[str, List[ECLView]]:
        """Parse view definitions"""
        views = {}
        
        modules = views_data.get('modules', [])
        if not isinstance(modules, list):
            self.errors.append("Views modules must be a list")
            return views
        
        for module_def in modules:
            if not isinstance(module_def, dict):
                self.errors.append("View module must be a dictionary")
                continue
            
            module_id = module_def.get('id')
            if not module_id:
                self.errors.append("View module missing 'id' field")
                continue
            
            view = ECLView(
                id=module_id,
                label=module_def.get('label', module_id),
                visible_if=module_def.get('visible_if', 'true'),
                bindings=module_def.get('bindings', []),
                communication_level=module_def.get('communication_level')
            )
            
            if module_id not in views:
                views[module_id] = []
            views[module_id].append(view)
        
        return views
    
    def _validate_config(self):
        """Validate the complete ECL configuration"""
        if not self.config:
            return
        
        # Validate that all referenced types exist
        for obj_name, obj in self.config.objects.items():
            for attr_name, attr in obj.attrs.items():
                if attr.type_name not in self.config.types:
                    self.errors.append(f"Object {obj_name}.{attr_name} references unknown type {attr.type_name}")
        
        # Validate that all referenced objects exist in ref types
        for type_name, type_def in self.config.types.items():
            if type_def.kind == ECLTypeKind.REF and type_def.of not in self.config.objects:
                self.errors.append(f"Ref type {type_name} references unknown object {type_def.of}")
        
        # Validate action input schemas
        for action_name, action in self.config.actions.items():
            for input_name, input_def in action.input_schema.items():
                if isinstance(input_def, dict) and 'type' in input_def:
                    type_name = input_def['type']
                    if type_name not in self.config.types:
                        self.errors.append(f"Action {action_name} input {input_name} references unknown type {type_name}")
    
    def to_experiment_config(self) -> Dict[str, Any]:
        """Convert ECL configuration to experiment configuration format"""
        if not self.config:
            raise ECLValidationError("No configuration loaded")
        
        # Extract experiment metadata
        experiment = self.config.experiment
        
        # Convert to experiment configuration format
        config = {
            'experiment_type': 'custom_ecl',
            'ecl_config': {
                'version': self.config.ecl_version,
                'experiment_id': experiment.get('id'),
                'title': experiment.get('title'),
                'description': experiment.get('description'),
                'timing': experiment.get('timing', {})
            },
            'types': {name: {
                'kind': type_def.kind.value,
                'base': type_def.base,
                'values': type_def.values,
                'min': type_def.min_val,
                'max': type_def.max_val,
                'max_len': type_def.max_len,
                'of': type_def.of
            } for name, type_def in self.config.types.items()},
            'objects': {name: {
                'key': obj.key,
                'attrs': {attr_name: {
                    'type': attr.type_name,
                    'required': attr.required,
                    'default': attr.default
                } for attr_name, attr in obj.attrs.items()}
            } for name, obj in self.config.objects.items()},
            'variables': self.config.variables,
            'constraints': self.config.constraints,
            'policies': self.config.policies,
            'actions': {name: {
                'input': action.input_schema,
                'preconditions': action.preconditions,
                'effects': action.effects
            } for name, action in self.config.actions.items()},
            'views': {name: [{
                'id': view.id,
                'label': view.label,
                'visible_if': view.visible_if,
                'bindings': view.bindings,
                'communication_level': view.communication_level
            } for view in views] for name, views in self.config.views.items()}
        }
        
        return config
    
    def get_ui_config(self) -> Dict[str, Any]:
        """Extract UI configuration from ECL views"""
        if not self.config:
            raise ECLValidationError("No configuration loaded")
        
        ui_config = {
            'modules': {},
            'interface_elements': {}
        }
        
        # Process views to create UI configuration
        for module_name, views in self.config.views.items():
            if not views:
                continue
            
            view = views[0]  # Take the first view if multiple exist
            
            # Determine module type based on view properties
            module_config = {
                'label': view.label,
                'visible_if': view.visible_if,
                'bindings': view.bindings
            }
            
            if view.communication_level:
                module_config['communication_level'] = view.communication_level
            
            ui_config['modules'][module_name] = module_config
        
        return ui_config


def parse_ecl_file(file_path: str) -> ECLConfig:
    """Convenience function to parse an ECL file"""
    parser = ECLParser()
    return parser.parse_file(file_path)


def parse_ecl_yaml(yaml_content: str) -> ECLConfig:
    """Convenience function to parse ECL from YAML content"""
    parser = ECLParser()
    return parser.parse_yaml(yaml_content)


def ecl_to_experiment_config(ecl_config: ECLConfig) -> Dict[str, Any]:
    """Convert ECL configuration to experiment configuration format"""
    parser = ECLParser()
    parser.config = ecl_config
    return parser.to_experiment_config()


def ecl_to_ui_config(ecl_config: ECLConfig) -> Dict[str, Any]:
    """Extract UI configuration from ECL configuration"""
    parser = ECLParser()
    parser.config = ecl_config
    return parser.get_ui_config()
