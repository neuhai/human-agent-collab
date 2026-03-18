<script setup>
import { ref, computed, watch, onMounted } from 'vue'

const props = defineProps({
  config: {
    type: Object,
    required: true
  },
  selectedParticipant: {
    type: String,
    default: null
  },
  participants: {
    type: Object,
    default: () => ({})
  },
  // Current user's participant data (for getting shapes)
  myParticipant: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['submit'])

// Form field values
const formValues = ref({})

// Get available shapes from config or participant data
const availableShapes = computed(() => {
  const shapeField = props.config.fields?.shape_type
  if (!shapeField) return []
  
  // If options is an array, use it directly
  if (Array.isArray(shapeField.options)) {
    return shapeField.options
  }
  
  // If options is a string path like "Participant.shapes", try to resolve it
  if (typeof shapeField.options === 'string') {
    if (shapeField.options === 'Participant.shapes' || shapeField.options.includes('Participant.shapes')) {
      // Get shapes from current user's participant data
      if (props.myParticipant) {
        const expParams = props.myParticipant.experiment_params || {}
        const shapes = expParams.shapes || []
        if (Array.isArray(shapes) && shapes.length > 0) {
          console.log('[TradeForm] Found shapes from myParticipant:', shapes)
          return shapes
        }
        // Also check if shapes are in inventory (for backward compatibility)
        const inventory = expParams.inventory || []
        if (Array.isArray(inventory) && inventory.length > 0) {
          // Extract unique shapes from inventory
          const uniqueShapes = [...new Set(inventory.filter(item => typeof item === 'string'))]
          if (uniqueShapes.length > 0) {
            console.log('[TradeForm] Found shapes from inventory:', uniqueShapes)
            return uniqueShapes
          }
        }
      }
      
      // Fallback: try to get from sessionStorage participant interface
      try {
        const participantInterface = sessionStorage.getItem('participant_interface')
        if (participantInterface) {
          const interfaceData = JSON.parse(participantInterface)
          // Try to find shapes in interface data - check My Actions
          const myActions = interfaceData?.['My Actions']?.[0]
          if (myActions) {
            const shapesBinding = myActions.bindings?.find(b => 
              b.path === 'Participant.shapes' || b.path?.includes('shapes')
            )
            if (shapesBinding?.value && Array.isArray(shapesBinding.value)) {
              console.log('[TradeForm] Found shapes from participant interface:', shapesBinding.value)
              return shapesBinding.value
            }
          }
        }
      } catch (e) {
        console.warn('[TradeForm] Failed to parse participant interface:', e)
      }
      
      // Another fallback: try to get from participants prop
      const myId = sessionStorage.getItem('participant_id')
      if (myId && props.participants[myId]) {
        const expParams = props.participants[myId].experiment_params || {}
        const shapes = expParams.shapes || []
        if (Array.isArray(shapes) && shapes.length > 0) {
          console.log('[TradeForm] Found shapes from participants prop:', shapes)
          return shapes
        }
        // Also check inventory
        const inventory = expParams.inventory || []
        if (Array.isArray(inventory) && inventory.length > 0) {
          const uniqueShapes = [...new Set(inventory.filter(item => typeof item === 'string'))]
          if (uniqueShapes.length > 0) {
            console.log('[TradeForm] Found shapes from participants prop inventory:', uniqueShapes)
            return uniqueShapes
          }
        }
      }
      
      console.warn('[TradeForm] No shapes found. myParticipant:', props.myParticipant, 'participants:', props.participants)
    }
  }
  
  return []
})

// Initialize form values from config defaults
const initializeForm = () => {
  if (props.config.fields) {
    Object.keys(props.config.fields).forEach(key => {
      const field = props.config.fields[key]
      if (field.default !== undefined) {
        formValues.value[key] = field.default
      } else {
        formValues.value[key] = ''
      }
    })
  }
}

// Watch for selectedParticipant changes and update participant_name
watch(() => props.selectedParticipant, (newVal) => {
  if (newVal && props.config.fields?.participant_name) {
    const participantName = props.participants[newVal]?.name || newVal || 'No participant selected'
    formValues.value.participant_name = participantName
  } else if (!newVal && props.config.fields?.participant_name) {
    formValues.value.participant_name = 'No participant selected'
  }
}, { immediate: true })

// Watch for myParticipant changes to update available shapes
watch(() => props.myParticipant, () => {
  // Trigger recomputation of availableShapes
}, { deep: true })

// Initialize on mount
onMounted(() => {
  initializeForm()
})

// Parse template string into segments (text and variable placeholders)
// Also handle dynamic from/to based on trade_action
const parsedTemplate = computed(() => {
  let template = props.config.label || ''
  
  // Get current trade_action value - watch formValues to trigger recomputation
  const tradeAction = formValues.value.trade_action || 'sell'
  
  // Replace from/to dynamically based on trade_action
  // If sell: "from/to" -> "to", if buy: "from/to" -> "from"
  if (tradeAction === 'sell') {
    template = template.replace(/from\/to/g, 'to')
  } else if (tradeAction === 'buy') {
    template = template.replace(/from\/to/g, 'from')
  }
  
  const segments = []
  let currentIndex = 0
  
  // Match both {variable} and ${variable} patterns
  const regex = /\{(\w+)\}|\$\{(\w+)\}/g
  let match
  
  while ((match = regex.exec(template)) !== null) {
    // Add text before the match
    if (match.index > currentIndex) {
      const text = template.substring(currentIndex, match.index)
      if (text) {
        segments.push({ type: 'text', content: text })
      }
    }
    
    // Add the variable placeholder
    const varName = match[1] || match[2] // Either from {var} or ${var}
    segments.push({ type: 'variable', name: varName })
    
    currentIndex = match.index + match[0].length
  }
  
  // Add remaining text
  if (currentIndex < template.length) {
    const text = template.substring(currentIndex)
    if (text) {
      segments.push({ type: 'text', content: text })
    }
  }
  
  // If no variables found, return the whole template as text
  if (segments.length === 0) {
    segments.push({ type: 'text', content: template })
  }
  
  return segments
})

// Handle field value changes
const updateFieldValue = (fieldKey, value) => {
  formValues.value[fieldKey] = value
  // If trade_action changes, trigger template re-computation
  if (fieldKey === 'trade_action') {
    // Force reactivity update
    formValues.value = { ...formValues.value }
  }
}

// Handle form submission
const handleSubmit = async () => {
  if (props.config.on_submit) {
    emit('submit', {
      action: props.config.on_submit,
      values: { ...formValues.value }
    })
  }
}

// Get participant name for display
const getParticipantName = (participantId) => {
  if (!participantId) return 'No participant selected'
  return props.participants[participantId]?.name || participantId
}

// Format shape name
const formatShapeName = (shape) => {
  if (!shape) return ''
  return shape.charAt(0).toUpperCase() + shape.slice(1)
}

// Get field config by variable name
const getFieldConfig = (varName) => {
  return props.config.fields?.[varName] || null
}
</script>

<template>
  <div class="trade-form">
    <div class="trade-sentence">
      <p class="sentence-builder">
        <template v-for="(segment, index) in parsedTemplate" :key="index">
          <!-- Text segment -->
          <span v-if="segment.type === 'text'">{{ segment.content }}</span>
          
          <!-- Variable segment - render inline control -->
          <template v-else-if="segment.type === 'variable'">
            <template v-if="getFieldConfig(segment.name)">
              <!-- Segmented Control (for trade_action) -->
              <select
                v-if="getFieldConfig(segment.name).control === 'segmented'"
                :value="formValues[segment.name]"
                @change="updateFieldValue(segment.name, $event.target.value)"
                class="inline-select"
              >
                <option
                  v-for="option in getFieldConfig(segment.name).options"
                  :key="option"
                  :value="option"
                >
                  {{ option }}
                </option>
              </select>
              
              <!-- Shape Production Control (for shape_type) -->
              <select
                v-else-if="getFieldConfig(segment.name).control === 'shape_production'"
                :value="formValues[segment.name]"
                @change="updateFieldValue(segment.name, $event.target.value)"
                class="inline-select"
              >
                <option value="">{{ segment.name.replace('_', ' ') }}</option>
                <option
                  v-for="shape in availableShapes"
                  :key="shape"
                  :value="shape"
                >
                  {{ formatShapeName(shape) }}
                </option>
              </select>
              
              <!-- Read-only Text (for participant_name) -->
              <strong
                v-else-if="getFieldConfig(segment.name).control === 'text' && getFieldConfig(segment.name).readonly"
                class="inline-text"
              >
                {{ formValues[segment.name] || getParticipantName(selectedParticipant) }}
              </strong>
              
              <!-- Number/Text Input (for trade_price) -->
              <template v-else-if="getFieldConfig(segment.name).control === 'text'">
                <span v-if="segment.name.includes('price') || segment.name.includes('Price')">$</span>
                <input
                  :type="getFieldConfig(segment.name).type || 'number'"
                  :value="formValues[segment.name]"
                  @input="updateFieldValue(segment.name, $event.target.value)"
                  :placeholder="getFieldConfig(segment.name).placeholder || getFieldConfig(segment.name).default || ''"
                  :min="getFieldConfig(segment.name).min"
                  :max="getFieldConfig(segment.name).max"
                  class="inline-input"
                />
              </template>
              
              <!-- Fallback: display value as text -->
              <span v-else class="inline-text">
                {{ formValues[segment.name] || segment.name }}
              </span>
            </template>
            
            <!-- If no field config found, show variable name -->
            <span v-else class="inline-text">{{ segment.name }}</span>
          </template>
        </template>
      </p>
    </div>
    <button
      v-if="config.on_submit"
      @click="handleSubmit"
      class="propose-btn"
    >
      {{ config.submit_label || 'Send Trade Offer' }}
    </button>
  </div>
</template>

<style scoped>
.trade-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.trade-sentence {
  padding: 12px;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  text-align: left;
}

.sentence-builder {
  font-size: 14px;
  color: #374151;
  font-weight: 400;
  line-height: 1.8;
  margin: 0;
  display: inline;
}

.inline-select {
  display: inline-block;
  padding: 4px 8px;
  margin: 0 4px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 14px;
  color: #374151;
  background: white;
  cursor: pointer;
  min-width: 80px;
  vertical-align: middle;
}

.inline-select:focus {
  outline: none;
  border-color: #5caff7;
  box-shadow: 0 0 0 2px rgba(92, 175, 247, 0.2);
}

.inline-input {
  display: inline-block;
  padding: 4px 8px;
  margin: 0 4px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 14px;
  color: #374151;
  background: white;
  width: 80px;
  vertical-align: middle;
}

.inline-input:focus {
  outline: none;
  border-color: #5caff7;
  box-shadow: 0 0 0 2px rgba(92, 175, 247, 0.2);
}

.inline-text {
  display: inline-block;
  margin: 0 4px;
  font-weight: 600;
  color: #1f2937;
  vertical-align: middle;
}

.propose-btn {
  padding: 10px 16px;
  background: #5caff7;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease;
  align-self: flex-start;
  margin: auto;
}

.propose-btn:hover {
  background: #4a9de6;
}

.propose-btn:active {
  background: #3a8dd4;
}

.propose-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}
</style>

