<template>
  <div class="participants-column">
    <div class="column-content">
      <div class="participants-list">
        <div 
          v-for="participant in participants" 
          :key="participant.id"
          class="participant-item"
          @mouseenter="showTooltip(participant, $event)"
          @mouseleave="hideTooltip"
        >
          <div class="participant-info">
            <div class="participant-id">{{ getDisplayName(participant) }}</div>
            <div class="participant-specialty" v-if="participant.specialty">
              <span
                class="specialty-shape"
                :class="getShapeClass(participant.specialty)"
                :style="getShapeStyle(participant.specialty)"
              ></span>
              <span class="specialty-label">
                {{ getShapeLabel(participant.specialty) }}
              </span>
            </div>
          </div>
          <div :class="['status-indicator', getParticipantStatus(participant)]"></div>
        </div>
        <div v-if="participants.length === 0" class="empty">
          No participants yet
        </div>
      </div>
    </div>
    
    <!-- Participant Details Tooltip -->
    <div 
      v-if="tooltipVisible" 
      class="participant-tooltip"
      :style="tooltipStyle"
    >
      <div class="tooltip-header">
        <div class="tooltip-participant-id">{{ getDisplayName(tooltipData) }}</div>
        <div :class="['tooltip-status-indicator', getParticipantStatus(tooltipData)]"></div>
      </div>
      
      <div 
        v-for="field in tooltipFields" 
        :key="field.label"
        class="tooltip-section"
      >
        <div class="tooltip-label">{{ field.label }}</div>
        <div 
          :class="['tooltip-value', field.label.toLowerCase() === 'money' ? 'money' : '']"
        >
          <template v-if="field.control === 'progress'">
            <div class="progress-bar">
              <div 
                class="progress-fill" 
                :style="{ width: `${Math.min(100, Math.max(0, Number(field.value) || 0))}%` }"
              ></div>
              <span class="progress-text">{{ Math.round(Math.min(100, Math.max(0, Number(field.value) || 0))) }}%</span>
            </div>
          </template>
          <template v-else>
            {{ field.value }}
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, onMounted, onUnmounted, watch } from 'vue'
import { onParticipantsUpdate, offParticipantsUpdate } from '../services/websocket.js'

// Use a flexible type that matches backend response
type Participant = {
  id: string
  [key: string]: any // Allow any fields from backend - dynamically determined by experiment type
}

// Props (optional, for backward compatibility)
const props = defineProps<{
  participants?: Participant[]
  onlineCount?: number
  totalOrders?: number
}>()

// Inject session info from parent
const currentSessionName = inject<ReturnType<typeof ref<string>>>('currentSessionName', ref(''))
const currentSessionId = inject<ReturnType<typeof ref<string>>>('currentSessionId', ref(''))
const isSessionCreated = inject<ReturnType<typeof ref<boolean>>>('isSessionCreated', ref(false))
const selectedExperimentType = inject<ReturnType<typeof ref<string | null>>>('selectedExperimentType', ref(null))

// Session info and participant config
const sessionInfo = ref<any>(null)
const participantConfig = ref<any>(null)

// Internal state for participants fetched from backend
const participantsList = ref<Participant[]>([])
const onlineCountInternal = ref(0)
const totalOrdersInternal = ref(0)
const participantsUpdateHandler = ref<((data: any) => void) | null>(null)

// Use props if provided, otherwise use internal state
const participants = computed(() => props.participants || participantsList.value)
const onlineCount = computed(() => props.onlineCount !== undefined ? props.onlineCount : onlineCountInternal.value)
const totalOrders = computed(() => props.totalOrders !== undefined ? props.totalOrders : totalOrdersInternal.value)

// Determine participant status based on status field or login_time
const getParticipantStatus = (participant: Participant): 'online' | 'offline' => {
  // First, check the 'status' field (used for all participants including AI agents)
  if (participant.status === 'online' || participant.status === 'offline') {
    return participant.status
  }
  
  // Otherwise, determine status based on login_time
  // If login_time exists and is not null/empty, participant is online
  const loginTime = participant.login_time
  if (loginTime && typeof loginTime === 'string' && loginTime.trim() !== '') {
    return 'online'
  }
  
  return 'offline'
}

const getShapeClass = (value: string) => {
  const shape = (value || '').toLowerCase()
  if (shape === 'circle') return 'shape-circle'
  if (shape === 'triangle') return 'shape-triangle'
  if (shape === 'square') return 'shape-square'
  return 'shape-circle'
}

const getShapeStyle = (value: string) => {
  const colorMap: Record<string, string> = {
    circle: '#ef4444',
    triangle: '#3b82f6',
    square: '#10b981'
  }
  const shape = (value || '').toLowerCase()
  const color = colorMap[shape] || '#6b7280'

  if (shape === 'triangle') {
    return { borderBottomColor: color }
  }
  return { backgroundColor: color }
}

const getShapeLabel = (value: string) => {
  if (!value) return ''
  const v = String(value)
  return v.charAt(0).toUpperCase() + v.slice(1).toLowerCase()
}

// Fetch session info to get experiment_type
const fetchSessionInfo = async () => {
  const sessionIdentifier = currentSessionName.value || currentSessionId.value
  
  if (!sessionIdentifier || !isSessionCreated.value) {
    sessionInfo.value = null
    participantConfig.value = null
    return
  }

  try {
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    const response = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      console.error('Failed to fetch session info:', response.statusText)
      return
    }

    const data = await response.json()
    sessionInfo.value = data
    
    // Fetch participant config based on experiment_type
    const experimentType = data.experiment_type || selectedExperimentType.value
    if (experimentType) {
      await fetchParticipantConfig(experimentType, data)
    } else {
      participantConfig.value = null
    }
  } catch (error) {
    console.error('Error fetching session info:', error)
  }
}

// Fetch participant config from backend
const fetchParticipantConfig = async (experimentType: string, session?: any) => {
  try {
    const sessionIdentifier = currentSessionName.value || currentSessionId.value
    if (!sessionIdentifier) return

    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    
    // Try to get participant config from backend
    // First, try to get it from the session's participant config if available
    // Otherwise, we'll build it from the known structure
    
    // For now, we'll use the participant config structure from backend
    // We need to call get_participant_config equivalent
    // Since there's no direct API, we'll construct it based on experiment type
    const config = await getParticipantConfigForExperiment(experimentType, session)
    participantConfig.value = config
  } catch (error) {
    console.error('Error fetching participant config:', error)
    participantConfig.value = null
  }
}

// Get participant config structure for a given experiment type
const getParticipantConfigForExperiment = async (experimentType: string, session?: any): Promise<any> => {
  // This maps to the PARTICIPANTS structure in backend/config/experiments.py
  const configs: Record<string, any> = {
    shapefactory: {
      baseFields: ['id', 'name', 'type', 'specialty', 'mbti'],
      experimentParams: {
        money: { type: 'number', label: 'Money', format: (v: any) => `$${v}` },
        production_number: { type: 'number', label: 'Production Number' },
        order_progress: { type: 'number', label: 'Order Progress', control: 'progress' },
        inventory: { type: 'list', label: 'Inventory' },
        shapes: { type: 'list', label: 'Shapes' },
        in_production: { type: 'list', label: 'In Production' },
        tasks: { type: 'list', label: 'Tasks' }
      }
    },
    daytrader: {
      baseFields: ['id', 'name', 'type', 'mbti'],
      experimentParams: {
        money: { type: 'number', label: 'Money', format: (v: any) => `$${v}` }
      }
    },
    essayranking: {
      baseFields: ['id', 'name', 'type', 'mbti'],
      experimentParams: {}
    },
    wordguessing: {
      baseFields: ['id', 'name', 'type', 'role', 'mbti'],
      experimentParams: {}
    }
  }

  return configs[experimentType] || { baseFields: ['id', 'name', 'type'], experimentParams: {} }
}

// Fetch participants from backend
const fetchParticipants = async () => {
  // Determine session identifier (prefer name over id)
  const sessionIdentifier = currentSessionName.value || currentSessionId.value
  
  if (!sessionIdentifier || !isSessionCreated.value) {
    participantsList.value = []
    onlineCountInternal.value = 0
    totalOrdersInternal.value = 0
    return
  }

  try {
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    const response = await fetch(`/api/sessions/${encodedSessionName}/participants`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      console.error('Failed to fetch participants:', response.statusText)
      return
    }

    const data = await response.json()
    const fetchedParticipants = data.participants || []
    
    // Store participants (status will be computed dynamically)
    participantsList.value = fetchedParticipants
    
    // Calculate online count using getParticipantStatus
    onlineCountInternal.value = fetchedParticipants.filter(p => getParticipantStatus(p) === 'online').length
    
    // Calculate total orders (if applicable)
    totalOrdersInternal.value = fetchedParticipants.reduce((sum: number, p: Participant) => {
      return sum + (p.orders_completed || 0)
    }, 0)
  } catch (error) {
    console.error('Error fetching participants:', error)
  }
}

// Utility function to extract display name from participant code
const getDisplayName = (participant: Participant | string): string => {
  // If participant is a string (id), try to find the participant
  if (typeof participant === 'string') {
    const p = participants.value.find(p => p.id === participant)
    if (p) {
      return p.name || getDisplayNameFromId(p.id)
    }
    return getDisplayNameFromId(participant)
  }
  
  // If participant object has name, use it
  if (participant.name) {
    return participant.name
  }
  
  // Otherwise, extract from id
  return getDisplayNameFromId(participant.id)
}

const getDisplayNameFromId = (participantCode: string): string => {
  if (!participantCode) return ''
  // Remove session ID suffix (everything after the last underscore)
  const parts = participantCode.split('_')
  if (parts.length > 1) {
    // Remove the last part (session ID) and join the rest
    return parts.slice(0, -1).join('_')
  }
  return participantCode
}

// Handle WebSocket participant updates
const handleParticipantsUpdate = (data: any) => {
  // Check if this update is for the current session
  const sessionIdentifier = currentSessionName.value || currentSessionId.value
  if (data.session_id) {
    // Compare session_id with current session
    const updateSessionId = data.session_id
    const currentSessionIdValue = currentSessionId.value
    
    // If we have session_id, compare directly
    if (currentSessionIdValue && updateSessionId !== currentSessionIdValue) {
      return
    }
    
    // If we only have session_name, try to match
    if (!currentSessionIdValue && currentSessionName.value) {
      // We can't directly compare, but we'll accept it if session_name matches
      // This is a fallback - ideally we should have session_id
    }
  }
  
  if (data.participants) {
    participantsList.value = data.participants
    // Recalculate online count
    onlineCountInternal.value = data.participants.filter((p: Participant) => getParticipantStatus(p) === 'online').length
    // Recalculate total orders
    totalOrdersInternal.value = data.participants.reduce((sum: number, p: Participant) => {
      return sum + (p.orders_completed || 0)
    }, 0)
  }
  
  // Update session info if provided
  if (data.session_info) {
    sessionInfo.value = data.session_info
    // Fetch participant config if experiment type is available
    const experimentType = data.session_info.experiment_type || selectedExperimentType.value
    if (experimentType) {
      fetchParticipantConfig(experimentType, data.session_info)
    }
  }
}

// Watch for session changes and fetch session info and participants
// Note: WebSocket join/leave is now managed at researcher.vue level
watch([currentSessionName, currentSessionId, isSessionCreated, selectedExperimentType], () => {
  // Initial fetch
  fetchSessionInfo()
  fetchParticipants()
  
  // Set up WebSocket listener if session exists
  // The session is already joined at researcher.vue level, we just need to listen
  if (isSessionCreated.value && (currentSessionId.value || currentSessionName.value)) {
    // Set up listener if not already set
    if (!participantsUpdateHandler.value) {
      participantsUpdateHandler.value = handleParticipantsUpdate
      onParticipantsUpdate(handleParticipantsUpdate)
    }
  } else {
    // Clean up listener if session is no longer valid
    if (participantsUpdateHandler.value) {
      offParticipantsUpdate(participantsUpdateHandler.value)
      participantsUpdateHandler.value = null
    }
  }
}, { immediate: true })

// Set up WebSocket listener on mount
onMounted(() => {
  // Initial fetch
  fetchSessionInfo()
  fetchParticipants()
  
  // Set up WebSocket listener if session exists
  // The session is already joined at researcher.vue level, we just need to listen
  if (isSessionCreated.value && (currentSessionId.value || currentSessionName.value)) {
    if (!participantsUpdateHandler.value) {
      participantsUpdateHandler.value = handleParticipantsUpdate
      onParticipantsUpdate(handleParticipantsUpdate)
    }
  }
})

onUnmounted(() => {
  // Clean up WebSocket listener
  // Note: We don't leave session here - that's managed at researcher.vue level
  if (participantsUpdateHandler.value) {
    offParticipantsUpdate(participantsUpdateHandler.value)
    participantsUpdateHandler.value = null
  }
})

// Generate tooltip fields based on participant config and participant data
const getTooltipFields = (participant: Participant) => {
  if (!participant) {
    return []
  }

  const config = participantConfig.value
  const fields: Array<{ label: string; value: any; control?: string }> = []

  // If config is available, use it to determine fields
  if (config) {
    // Add base fields
    if (config.baseFields) {
      for (const fieldName of config.baseFields) {
        if (fieldName === 'id') continue // Skip id, we show it in header
        
        const value = participant[fieldName]
        if (value !== undefined && value !== null && value !== '') {
          let label = fieldName.charAt(0).toUpperCase() + fieldName.slice(1).replace(/_/g, ' ')
          let displayValue: any = value
          let control: string | undefined = undefined

          // Special handling for specific fields
          if (fieldName === 'type') {
            displayValue = (value === 'ai' || value === 'ai_agent') ? 'AI Agent' : 'Human'
          } else if (fieldName === 'specialty') {
            // Keep as is, could be shape
            displayValue = value
          } else if (fieldName === 'name') {
            displayValue = value
          } else if (fieldName === 'role') {
            displayValue = value
          } else if (fieldName === 'mbti') {
            displayValue = value
          }

          fields.push({ label, value: displayValue, control })
        }
      }
    }

    // Add experiment_params fields
    if (config.experimentParams && participant.experiment_params) {
      for (const [paramName, paramConfig] of Object.entries(config.experimentParams)) {
        const paramValue = participant.experiment_params[paramName]
        if (paramValue !== undefined && paramValue !== null) {
          const paramConfigTyped = paramConfig as any

          // 对于 list 类型：如果是空数组，直接跳过，不显示这一行
          if (paramConfigTyped.type === 'list' && Array.isArray(paramValue) && paramValue.length === 0) {
            continue
          }

          let displayValue: any = paramValue

          // Format based on type
          if (paramConfigTyped.format && typeof paramConfigTyped.format === 'function') {
            displayValue = paramConfigTyped.format(paramValue)
          } else if (paramConfigTyped.type === 'number') {
            // For progress control, keep as number; otherwise convert to string
            if (paramConfigTyped.control === 'progress') {
              displayValue = Number(paramValue)
            } else {
              displayValue = String(paramValue)
            }
          } else if (paramConfigTyped.type === 'list' && Array.isArray(paramValue)) {
            // 非空数组时显示长度
            displayValue = String(paramValue.length)
          }

          fields.push({
            label: paramConfigTyped.label || paramName.charAt(0).toUpperCase() + paramName.slice(1).replace(/_/g, ' '),
            value: displayValue,
            control: paramConfigTyped.control
          })
        }
      }
    }
  } else {
    // Fallback: show common fields if config is not available
    if (participant.type !== undefined) {
      fields.push({ 
        label: 'Type', 
        value: (participant.type === 'ai' || participant.type === 'ai_agent') ? 'AI Agent' : 'Human' 
      })
    }
    if (participant.name !== undefined && participant.name) {
      fields.push({ label: 'Name', value: participant.name })
    }
    if (participant.specialty !== undefined && participant.specialty) {
      fields.push({ label: 'Specialty', value: participant.specialty })
    }
  }

  // Add common fields that might not be in config but are present
  if (participant.money !== undefined && !fields.find(f => f.label.toLowerCase() === 'money')) {
    fields.push({ label: 'Money', value: `$${participant.money}` })
  }

  if (participant.orders_completed !== undefined && totalOrders.value > 0) {
    fields.push({ 
      label: 'Orders Completed', 
      value: `${participant.orders_completed || 0}/${totalOrders.value} total` 
    })
  }

  return fields
}

// Tooltip state
const tooltipVisible = ref(false)
const tooltipData = ref<Participant>({} as Participant)
const tooltipPosition = ref({ x: 0, y: 0 })
const tooltipTimeout = ref<number | null>(null)

// Computed tooltip fields
const tooltipFields = computed(() => {
  if (!tooltipData.value || !tooltipData.value.id) {
    return []
  }
  return getTooltipFields(tooltipData.value)
})

// Computed tooltip style
const tooltipStyle = computed(() => ({
  left: `${tooltipPosition.value.x}px`,
  top: `${tooltipPosition.value.y}px`
}))

// Show tooltip
const showTooltip = (participant: Participant, event: MouseEvent) => {
  // Clear any existing timeout
  if (tooltipTimeout.value) {
    clearTimeout(tooltipTimeout.value)
  }
  
  // Set a small delay before showing the tooltip
  tooltipTimeout.value = window.setTimeout(() => {
    tooltipData.value = participant
    
    // Calculate initial position
    let x = event.clientX + 10
    let y = event.clientY - 10
    
    // Get viewport dimensions
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight
    
    // Tooltip dimensions (smaller now with fewer fields)
    const tooltipWidth = 200
    const tooltipHeight = 120
    
    // Adjust horizontal position if tooltip would go off-screen
    if (x + tooltipWidth > viewportWidth) {
      x = event.clientX - tooltipWidth - 10
    }
    
    // Adjust vertical position if tooltip would go off-screen
    if (y + tooltipHeight > viewportHeight) {
      y = event.clientY - tooltipHeight - 10
    }
    
    // Ensure tooltip doesn't go above the top of the screen
    if (y < 10) {
      y = 10
    }
    
    // Ensure tooltip doesn't go left of the screen
    if (x < 10) {
      x = 10
    }
    
    // Ensure tooltip doesn't go below the bottom of the interface
    // Leave at least 20px margin from the bottom
    if (y + tooltipHeight > viewportHeight - 20) {
      y = viewportHeight - tooltipHeight - 20
    }
    
    tooltipPosition.value = { x, y }
    tooltipVisible.value = true
  }, 300) // 300ms delay
}

// Hide tooltip
const hideTooltip = () => {
  // Clear any existing timeout
  if (tooltipTimeout.value) {
    clearTimeout(tooltipTimeout.value)
    tooltipTimeout.value = null
  }
  
  tooltipVisible.value = false
}
</script>

<style scoped>
.participants-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.participant-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  margin-bottom: 2px;
  border-radius: 4px;
  transition: background-color 0.3s;
  cursor: pointer;
}

.participant-item:hover {
  background: #f8f9fa;
}

.participant-info {
  display: flex;
  flex-direction: column;
  text-align: left;
}

.participant-id {
  font-weight: 600;
  color: #495057;
  font-size: 12px;
}

.participant-specialty {
  color: #6c757d;
  font-size: 10px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.specialty-shape {
  width: 10px;
  height: 10px;
  display: inline-block;
}

.specialty-shape.shape-circle {
  border-radius: 50%;
}

.specialty-shape.shape-square {
  border-radius: 2px;
}

.specialty-shape.shape-triangle {
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-bottom: 9px solid;
  background-color: transparent !important;
  border-radius: 0;
}

.specialty-label {
  text-transform: capitalize;
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid #ffffff;
  box-shadow: 0 0 0 1px #e9ecef;
}

.status-indicator.online {
  background: #28a745;
}

.status-indicator.offline {
  background: #dc3545;
}

/* Tooltip Styles */
.participant-tooltip {
  position: fixed;
  z-index: 1000;
  background: #ffffff;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 12px;
  min-width: 230px;
  max-width: 350px;
  font-size: 12px;
  pointer-events: none;
  animation: tooltipFadeIn 0.2s ease-out;
  backdrop-filter: blur(4px);
}

@keyframes tooltipFadeIn {
  from {
    opacity: 0;
    transform: translateY(-8px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.tooltip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #f8f9fa;
}

.tooltip-participant-id {
  font-weight: 700;
  color: #495057;
  font-size: 14px;
  text-transform: capitalize;
}

.tooltip-status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid #ffffff;
  box-shadow: 0 0 0 1px #e9ecef;
}

.tooltip-status-indicator.online {
  background: #28a745;
  box-shadow: 0 0 0 1px #28a745, 0 0 6px rgba(40, 167, 69, 0.3);
}

.tooltip-status-indicator.offline {
  background: #dc3545;
  box-shadow: 0 0 0 1px #dc3545, 0 0 6px rgba(220, 53, 69, 0.3);
}

.tooltip-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  padding: 3px 0;
}

.tooltip-section:last-child {
  margin-bottom: 0;
}

.tooltip-label {
  color: #6c757d;
  font-weight: 500;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tooltip-value {
  color: #495057;
  font-weight: 600;
  font-size: 11px;
  text-align: right;
}

.tooltip-value.money {
  color: #28a745;
  font-weight: 700;
}

.progress-bar {
  position: relative;
  width: 100px;
  height: 16px;
  background: #e9ecef;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.progress-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: linear-gradient(90deg, #28a745, #20c997);
  transition: width 0.3s ease;
  border-radius: 8px;
}

.progress-text {
  position: relative;
  z-index: 1;
  font-size: 10px;
  font-weight: 600;
  color: #495057;
}
</style> 