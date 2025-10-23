"""
ECL UI Generator

This module generates dynamic participant interfaces based on ECL view definitions.
It creates Vue.js components and configurations that can be used to render
the participant interface according to the ECL specification.
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from ecl_parser import ECLConfig, ECLView


@dataclass
class UIComponent:
    """Represents a UI component generated from ECL"""
    type: str
    props: Dict[str, Any]
    children: List['UIComponent'] = None
    bindings: Dict[str, str] = None
    actions: List[Dict[str, Any]] = None


@dataclass
class UIModule:
    """Represents a UI module generated from ECL view"""
    id: str
    label: str
    visible_if: str
    components: List[UIComponent]
    communication_level: Optional[str] = None


class ECLUIGenerator:
    """Generates dynamic UI from ECL view definitions"""
    
    def __init__(self):
        self.generated_modules: Dict[str, UIModule] = {}
        self.component_counter = 0
    
    def generate_ui(self, ecl_config: ECLConfig) -> Dict[str, Any]:
        """Generate complete UI configuration from ECL config"""
        self.generated_modules = {}
        self.component_counter = 0
        
        # Process each view module
        for module_name, views in ecl_config.views.items():
            if not views:
                continue
            
            view = views[0]  # Take the first view if multiple exist
            module = self._generate_module(module_name, view, ecl_config)
            self.generated_modules[module_name] = module
        
        # Generate Vue.js component structure
        vue_components = self._generate_vue_components()
        
        # Generate interface configuration
        interface_config = self._generate_interface_config()
        
        return {
            'modules': self.generated_modules,
            'vue_components': vue_components,
            'interface_config': interface_config,
            'metadata': {
                'generated_from': 'ecl',
                'ecl_version': ecl_config.ecl_version,
                'experiment_id': ecl_config.experiment.get('id'),
                'module_count': len(self.generated_modules)
            }
        }
    
    def _generate_module(self, module_name: str, view: ECLView, ecl_config: ECLConfig) -> UIModule:
        """Generate a UI module from an ECL view"""
        components = []
        
        # Process bindings to create components
        for binding in view.bindings:
            component = self._generate_component_from_binding(binding, ecl_config)
            if component:
                components.append(component)
        
        return UIModule(
            id=view.id,
            label=view.label,
            visible_if=view.visible_if,
            components=components,
            communication_level=view.communication_level
        )
    
    def _generate_component_from_binding(self, binding: Dict[str, Any], ecl_config: ECLConfig) -> Optional[UIComponent]:
        """Generate a UI component from an ECL binding"""
        if not isinstance(binding, dict):
            return None
        
        label = binding.get('label', '')
        control = binding.get('control', 'text')
        path = binding.get('path', '')
        bind_to = binding.get('bind_to', '')
        action = binding.get('action', '')
        inputs = binding.get('inputs', [])
        
        # Determine component type based on control
        component_type = self._map_control_to_component_type(control)
        
        # Generate component props
        props = {
            'label': label,
            'path': path,
            'bind_to': bind_to
        }
        
        # Add control-specific props
        if control == 'select':
            props['options'] = binding.get('options', [])
        elif control == 'segmented':
            props['options'] = binding.get('options', [])
        elif control == 'number':
            props.update({
                'min': binding.get('min', 0),
                'max': binding.get('max', 100),
                'step': binding.get('step', 1)
            })
        elif control == 'button':
            props['action'] = action
            props['inputs'] = inputs
        
        # Generate actions if present
        actions = []
        if action:
            actions.append({
                'name': action,
                'inputs': inputs
            })
        
        return UIComponent(
            type=component_type,
            props=props,
            bindings={bind_to: path} if bind_to and path else {},
            actions=actions
        )
    
    def _map_control_to_component_type(self, control: str) -> str:
        """Map ECL control types to Vue component types"""
        mapping = {
            'text': 'text-display',
            'number': 'number-input',
            'select': 'select-input',
            'segmented': 'segmented-control',
            'button': 'action-button',
            'list': 'data-list',
            'table': 'data-table'
        }
        return mapping.get(control, 'text-display')
    
    def _generate_vue_components(self) -> Dict[str, str]:
        """Generate Vue.js component templates"""
        components = {}
        
        for module_name, module in self.generated_modules.items():
            template = self._generate_vue_template(module)
            components[f'{module_name}Module'] = template
        
        return components
    
    def _generate_vue_template(self, module: UIModule) -> str:
        """Generate Vue template for a module"""
        template_parts = [
            f'<template>',
            f'  <div class="ecl-module" :class="module-{module.id}">',
            f'    <h3 class="module-header">{{{{ "{module.label}" }}}}</h3>',
            f'    <div class="module-content">'
        ]
        
        for component in module.components:
            component_template = self._generate_component_template(component)
            template_parts.append(f'      {component_template}')
        
        template_parts.extend([
            f'    </div>',
            f'  </div>',
            f'</template>'
        ])
        
        return '\n'.join(template_parts)
    
    def _generate_component_template(self, component: UIComponent) -> str:
        """Generate Vue template for a component"""
        if component.type == 'text-display':
            return f'<div class="text-display">{{{{ {component.props.get("path", "null")} }}}}</div>'
        
        elif component.type == 'number-input':
            min_val = component.props.get('min', 0)
            max_val = component.props.get('max', 100)
            step_val = component.props.get('step', 1)
            bind_to = component.props.get('bind_to', '')
            
            return f'''<div class="number-input">
              <label>{{{{ "{component.props.get('label', '')}" }}}}</label>
              <input 
                type="number" 
                v-model="{bind_to}"
                min="{min_val}" 
                max="{max_val}" 
                step="{step_val}"
                class="form-control"
              />
            </div>'''
        
        elif component.type == 'select-input':
            options = component.props.get('options', [])
            bind_to = component.props.get('bind_to', '')
            options_html = '\n'.join([f'                <option value="{opt}">{opt}</option>' for opt in options])
            
            return f'''<div class="select-input">
              <label>{{{{ "{component.props.get('label', '')}" }}}}</label>
              <select v-model="{bind_to}" class="form-control">
                {options_html}
              </select>
            </div>'''
        
        elif component.type == 'segmented-control':
            options = component.props.get('options', [])
            bind_to = component.props.get('bind_to', '')
            options_html = '\n'.join([f'                <button type="button" :class="{{active: {bind_to} === \'{opt}\'}}" @click="{bind_to} = \'{opt}\'">{opt}</button>' for opt in options])
            
            return f'''<div class="segmented-control">
              <label>{{{{ "{component.props.get('label', '')}" }}}}</label>
              <div class="segmented-buttons">
                {options_html}
              </div>
            </div>'''
        
        elif component.type == 'action-button':
            action = component.props.get('action', '')
            inputs = component.props.get('inputs', [])
            input_bindings = ', '.join([f'{inp["name"]}: {inp["from"]}' for inp in inputs])
            
            return f'''<div class="action-button">
              <button 
                type="button" 
                @click="executeAction('{action}', {{{input_bindings}}})"
                class="btn btn-primary"
              >
                {{{{ "{component.props.get('label', '')}" }}}}
              </button>
            </div>'''
        
        elif component.type == 'data-list':
            path = component.props.get('path', '[]')
            
            return f'''<div class="data-list">
              <h4>{{{{ "{component.props.get('label', '')}" }}}}</h4>
              <ul>
                <li v-for="(item, index) in {path}" :key="index">
                  {{{{ item }}}}
                </li>
              </ul>
            </div>'''
        
        else:
            return f'<div class="unknown-component">{{{{ "{component.props.get("label", "Unknown Component")}" }}}}</div>'
    
    def _generate_interface_config(self) -> Dict[str, Any]:
        """Generate interface configuration for the frontend"""
        config = {
            'modules': {},
            'interface_elements': {},
            'communication': {},
            'visibility_rules': {}
        }
        
        for module_name, module in self.generated_modules.items():
            # Module configuration
            config['modules'][module_name] = {
                'label': module.label,
                'visible_if': module.visible_if,
                'components': [
                    {
                        'type': comp.type,
                        'props': comp.props,
                        'bindings': comp.bindings,
                        'actions': comp.actions
                    }
                    for comp in module.components
                ]
            }
            
            # Communication configuration
            if module.communication_level:
                config['communication'][module_name] = {
                    'level': module.communication_level
                }
            
            # Visibility rules
            config['visibility_rules'][module_name] = module.visible_if
        
        return config
    
    def generate_css_styles(self) -> str:
        """Generate CSS styles for ECL-generated components"""
        css = """
/* ECL Generated Styles */
.ecl-module {
    margin-bottom: 20px;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 15px;
    background: #f9f9f9;
}

.module-header {
    margin: 0 0 15px 0;
    font-size: 1.2em;
    font-weight: bold;
    color: #333;
    border-bottom: 2px solid #007bff;
    padding-bottom: 5px;
}

.module-content {
    display: flex;
    flex-direction: column;
    gap: 15px;
}

.text-display {
    padding: 10px;
    background: white;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-family: monospace;
}

.number-input, .select-input {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.number-input label, .select-input label {
    font-weight: bold;
    color: #555;
}

.form-control {
    padding: 8px 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 14px;
}

.segmented-control {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.segmented-control label {
    font-weight: bold;
    color: #555;
}

.segmented-buttons {
    display: flex;
    gap: 2px;
}

.segmented-buttons button {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid #ccc;
    background: white;
    cursor: pointer;
    transition: all 0.2s;
}

.segmented-buttons button:first-child {
    border-top-left-radius: 4px;
    border-bottom-left-radius: 4px;
}

.segmented-buttons button:last-child {
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}

.segmented-buttons button.active {
    background: #007bff;
    color: white;
    border-color: #007bff;
}

.action-button {
    margin-top: 10px;
}

.btn {
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
}

.btn-primary {
    background: #007bff;
    color: white;
}

.btn-primary:hover {
    background: #0056b3;
}

.data-list {
    background: white;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 15px;
}

.data-list h4 {
    margin: 0 0 10px 0;
    color: #333;
}

.data-list ul {
    margin: 0;
    padding-left: 20px;
}

.data-list li {
    margin-bottom: 5px;
    color: #555;
}

.unknown-component {
    padding: 10px;
    background: #fff3cd;
    border: 1px solid #ffeaa7;
    border-radius: 4px;
    color: #856404;
}
"""
        return css
    
    def generate_javascript_logic(self) -> str:
        """Generate JavaScript logic for ECL-generated components"""
        js = """
// ECL Generated JavaScript Logic
export default {
    data() {
        return {
            // Local state for form inputs
            $local: {
                action_kind: '',
                invest_type: '',
                amount: 0
            }
        }
    },
    
    methods: {
        executeAction(actionName, inputs) {
            console.log('Executing action:', actionName, inputs);
            
            // Send action to backend
            this.$http.post('/api/experiment/ecl/action', {
                action: actionName,
                inputs: inputs,
                session_code: this.sessionId
            }).then(response => {
                if (response.data.success) {
                    console.log('Action executed successfully:', response.data);
                    // Refresh game state
                    this.refreshGameState();
                } else {
                    console.error('Action failed:', response.data.error);
                    alert('Action failed: ' + response.data.error);
                }
            }).catch(error => {
                console.error('Action error:', error);
                alert('Action error: ' + error.message);
            });
        },
        
        refreshGameState() {
            // Refresh the game state from backend
            this.$http.get('/api/game-state?session_code=' + this.sessionId)
                .then(response => {
                    if (response.data.success) {
                        this.gameState = response.data.gameState;
                    }
                })
                .catch(error => {
                    console.error('Failed to refresh game state:', error);
                });
        },
        
        evaluateVisibility(condition) {
            // Simple visibility condition evaluator
            // This is a basic implementation - in production, you'd want a more robust evaluator
            try {
                // Replace common ECL expressions with JavaScript equivalents
                let jsCondition = condition
                    .replace(/Session\.settled\('S'\)/g, 'this.gameState.session?.settled || false')
                    .replace(/Participant\.endowment\(actor\.id\)/g, 'this.gameState.participant?.endowment || 0')
                    .replace(/==/g, '===')
                    .replace(/!=/g, '!==');
                
                return eval(jsCondition);
            } catch (error) {
                console.warn('Failed to evaluate visibility condition:', condition, error);
                return true; // Default to visible
            }
        }
    },
    
    computed: {
        visibleModules() {
            const visible = {};
            for (const [moduleName, module] of Object.entries(this.eclModules)) {
                visible[moduleName] = this.evaluateVisibility(module.visible_if);
            }
            return visible;
        }
    }
}
"""
        return js


def generate_ui_from_ecl(ecl_config: ECLConfig) -> Dict[str, Any]:
    """Convenience function to generate UI from ECL configuration"""
    generator = ECLUIGenerator()
    return generator.generate_ui(ecl_config)


def generate_ecl_interface_files(ecl_config: ECLConfig, output_dir: str):
    """Generate complete interface files from ECL configuration"""
    import os
    
    generator = ECLUIGenerator()
    ui_config = generator.generate_ui(ecl_config)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate Vue components
    for component_name, template in ui_config['vue_components'].items():
        component_file = os.path.join(output_dir, f'{component_name}.vue')
        with open(component_file, 'w', encoding='utf-8') as f:
            f.write(template)
    
    # Generate CSS styles
    css_file = os.path.join(output_dir, 'ecl-styles.css')
    with open(css_file, 'w', encoding='utf-8') as f:
        f.write(generator.generate_css_styles())
    
    # Generate JavaScript logic
    js_file = os.path.join(output_dir, 'ecl-logic.js')
    with open(js_file, 'w', encoding='utf-8') as f:
        f.write(generator.generate_javascript_logic())
    
    # Generate interface configuration
    config_file = os.path.join(output_dir, 'interface-config.json')
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(ui_config['interface_config'], f, indent=2)
    
    return {
        'components': list(ui_config['vue_components'].keys()),
        'css_file': css_file,
        'js_file': js_file,
        'config_file': config_file
    }
