<template>
  <div class="monitoring-column participants-column">
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
            <div class="participant-id">{{ getDisplayName(participant.id) }}</div>
            <div class="participant-specialty">{{ participant.specialty }}</div>
          </div>
          <div :class="['status-indicator', participant.status]"></div>
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
        <div class="tooltip-participant-id">{{ getDisplayName(tooltipData.id) }}</div>
        <div :class="['tooltip-status-indicator', tooltipData.status]"></div>
      </div>
      
      <div class="tooltip-section">
        <div class="tooltip-label">Type</div>
        <div class="tooltip-value">{{ tooltipData.type === 'ai' ? 'AI Agent' : 'Human' }}</div>
      </div>
      
      <div class="tooltip-section">
        <div class="tooltip-label">Specialty</div>
        <div class="tooltip-value">{{ tooltipData.specialty }}</div>
      </div>
      
      <div class="tooltip-section">
        <div class="tooltip-label">Money</div>
        <div class="tooltip-value money">${{ tooltipData.money }}</div>
      </div>
      
      <div class="tooltip-section">
        <div class="tooltip-label">Orders Completed</div>
        <div class="tooltip-value">{{ tooltipData.orders_completed }}/{{ totalOrders }} total</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Participant {
  id: string
  type: string
  specialty: string
  status: string
  money: number
  orders_completed: number
  trades_made: number
  shapes_bought: number
  shapes_sold: number
  login_time: string | null
  inventory?: Record<string, number>
  specialty_shapes_available?: number
  specialty_shapes_sold?: number
}

defineProps<{
  participants: Participant[]
  onlineCount: number
  totalOrders: number
}>()

// Utility function to extract display name from participant code
const getDisplayName = (participantCode: string): string => {
  if (!participantCode) return ''
  // Remove session ID suffix (everything after the last underscore)
  const parts = participantCode.split('_')
  if (parts.length > 1) {
    // Remove the last part (session ID) and join the rest
    return parts.slice(0, -1).join('_')
  }
  return participantCode
}

// Tooltip state
const tooltipVisible = ref(false)
const tooltipData = ref<Participant>({} as Participant)
const tooltipPosition = ref({ x: 0, y: 0 })
const tooltipTimeout = ref<number | null>(null)

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
}

.participant-id {
  font-weight: 600;
  color: #495057;
  font-size: 12px;
}

.participant-specialty {
  color: #6c757d;
  font-size: 10px;
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

.empty {
  text-align: center;
  color: #6c757d;
  font-style: italic;
  padding: 20px;
  font-size: 12px;
}
</style> 