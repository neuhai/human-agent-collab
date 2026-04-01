<script setup>
import { inject, computed, ref } from 'vue'
import ParticipantsList from './participants_status.vue'
import ConversationView from './conversation_feed.vue'
import TradesFeed from './trade_feed.vue'

// Inject selected experiment config from researcher.vue
const selectedExperimentConfig = inject('selectedExperimentConfig')

// Real-time data injected from researcher.vue
// Note: participants are now managed by ParticipantsList component itself
const conversations = inject('conversations', ref({}))
const messages = inject('messages', ref([]))
const activeConversations = inject('activeConversations', computed(() => 0))
const interactionConfig = inject('interactionConfig', ref({}))
const liveTypingBySender = inject('liveTypingBySender', ref({}))
const allParticipants = inject('allParticipants', ref([]))
const participantsMap = inject('participantsMap', computed(() => ({})))

// Selected participant for conversation view
const selectedParticipant = ref(null)
const pendingOffers = inject('pendingOffers', ref([]))
const completedTrades = inject('completedTrades', ref([]))
const totalTrades = inject('totalTrades', ref(0))
const pendingTrades = inject('pendingTrades', ref(0))

// Computed: Check if conversation column should be shown
const showConversationColumn = computed(() => {
  if (!selectedExperimentConfig.value || !selectedExperimentConfig.value.interaction) return false
  
  const informationFlow = selectedExperimentConfig.value.interaction['Information Flow']
  if (!informationFlow) return false
  
  return informationFlow.some(item => item.label === 'Communication Level')
})

// Computed: Check if trade column should be shown
const showTradeColumn = computed(() => {
  if (!selectedExperimentConfig.value) return false
  
  // Show trade column if experiment type is shapefactory
  if (selectedExperimentConfig.value.id === 'shapefactory') return true
  
  // Or if interaction has negotiations
  if (selectedExperimentConfig.value.interaction) {
    const actionStructures = selectedExperimentConfig.value.interaction['Action Structures']
    if (actionStructures) {
      return actionStructures.some(item => item.label === 'Negotiations')
    }
  }
  
  return false
})

// Computed: Check if investment history column should be shown (for daytrader)
const showInvestmentHistoryColumn = computed(() => {
  if (!selectedExperimentConfig.value) return false
  return selectedExperimentConfig.value.id === 'daytrader'
})

// Selected participant for investment history view
const selectedParticipantForInvestment = ref(null)

// Helper function to select participant for investment history
const selectParticipantForInvestment = (participant) => {
  const pId = participant.id || participant.participant_id
  if (pId) {
    selectedParticipantForInvestment.value = String(pId)
  }
}

// Get investment history for selected participant
const selectedParticipantInvestmentHistory = computed(() => {
  if (!selectedParticipantForInvestment.value) return []
  
  const participant = allParticipants.value.find(
    p => (p.id || p.participant_id) === selectedParticipantForInvestment.value
  )
  
  if (!participant) return []
  
  // Try to get investment_history from interface bindings first
  if (participant.interface) {
    const myTasks = participant.interface['My Tasks'] || []
    for (const task of myTasks) {
      if (task.bindings) {
        for (const binding of task.bindings) {
          if (binding.path?.includes('investment_history') || 
              binding.control === 'investment_history' ||
              binding.label?.toLowerCase() === 'investment history') {
            return Array.isArray(binding.value) ? binding.value : []
          }
        }
      }
    }
  }
  
  // Fallback to experiment_params
  if (participant.experiment_params?.investment_history) {
    return Array.isArray(participant.experiment_params.investment_history) 
      ? participant.experiment_params.investment_history 
      : []
  }
  
  return []
})

// Format investment time
const formatInvestmentTime = (timestamp) => {
  if (!timestamp) return 'N/A'
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    })
  } catch (e) {
    return timestamp
  }
}

// Computed: Check if experiment has orders/trades feature (for total-orders prop)
const hasOrdersFeature = computed(() => {
  if (!selectedExperimentConfig.value) return false
  
  // Check if experiment has trade-related features
  // This includes experiments with trade column or experiments that track orders
  return showTradeColumn.value || selectedExperimentConfig.value.id === 'shapefactory'
})

// Computed: Calculate total orders (only when relevant)
// Note: totalOrders is now calculated by ParticipantsList component itself
const totalOrders = computed(() => {
  return 0 // ParticipantsList will calculate this internally
})

// Helper function to get participant status
const getParticipantStatus = (participant) => {
  const loginTime = participant?.login_time
  if (loginTime && typeof loginTime === 'string' && loginTime.trim() !== '') return 'online'
  return 'offline'
}

// Helper function to select participant (normalize ID)
const selectParticipant = (participant) => {
  // Use id first, fallback to participant_id
  const pId = participant.id || participant.participant_id
  if (pId) {
    selectedParticipant.value = String(pId)
    console.log('[Monitor] Selected participant:', selectedParticipant.value, 'from participant:', participant)
  }
}

const monitorCommIsGroup = computed(() => {
  const level = String(interactionConfig.value?.communicationLevel || '').toLowerCase()
  return level.includes('group')
})

const typeIndicatorEnabledMonitor = computed(() => interactionConfig.value?.typeIndicator === 'enabled')

const typingSenderIdsForConversation = computed(() => {
  if (!typeIndicatorEnabledMonitor.value) return []
  const raw = liveTypingBySender.value || {}
  const entries = Object.entries(raw).filter(([, v]) => v && typeof v === 'object')
  const isGroup = monitorCommIsGroup.value
  const sel = selectedParticipant.value

  return entries
    .filter(([senderId, v]) => {
      const R = v.receiver
      if (isGroup) return R == null || R === ''
      if (!sel) return false
      if (R == null || R === '') return false
      const s = String(senderId)
      const r = String(R)
      const a = String(sel)
      return s === a || r === a
    })
    .map(([senderId]) => String(senderId))
})
</script>

<template>
  <div class="tab-col monitor-tab">
    <div class="subtab-container">
      <!-- Placeholder when no experiment is selected -->
      <div v-if="!selectedExperimentConfig" class="subtab-item placeholder">
        <p>Please select an experiment in Setup tab</p>
      </div>
      
      <template v-else>
        <!-- Column 1: Participants Status (always shown when experiment is selected) -->
        <div class="subtab-item">
          <div class="block-title">
              Participants
          </div>
          <ParticipantsList
                :total-orders="hasOrdersFeature ? totalOrders : 0"
          />
        </div>
        
        <!-- Column 2: Conversation (shown if communication level exists) -->
        <div v-if="showConversationColumn" class="subtab-item conversation-subtab">
          <div class="block-title">
            Conversations
            <div class="indicators">
              <span class="online-indicator">{{ messages.length }} messages</span>
              <span class="online-indicator">{{ activeConversations }} conversations</span>
            </div>
          </div>
          <div class="conversation-layout">
            <!-- Left: Participant List -->
            <div class="participant-list-sidebar">
              <div class="participant-list-content">
                <div
                  v-for="participant in allParticipants"
                  :key="participant.id || participant.participant_id"
                  :class="['participant-list-item', { selected: selectedParticipant === (participant.id || participant.participant_id) }]"
                  @click="selectParticipant(participant)"
                >
                  <div class="participant-list-name">{{ participant.name || participant.id || participant.participant_id }}</div>
                </div>
                <div v-if="allParticipants.length === 0" class="empty">
                  No participants yet
                </div>
              </div>
            </div>
            <!-- Right: Conversation View -->
            <div class="conversation-view-container">
              <ConversationView
                  :conversations="conversations"
                  :commLevel="interactionConfig.communicationLevel || 'chat'"
                  :selected-participant="selectedParticipant"
                  :participants="participantsMap"
                  :type-indicator-enabled="typeIndicatorEnabledMonitor"
                  :typing-sender-ids="typingSenderIdsForConversation"
              />
            </div>
          </div>
        </div>
        
        <!-- Column 3: Investment History (shown if daytrader) -->
        <div v-if="showInvestmentHistoryColumn" class="subtab-item investment-history-subtab">
          <div class="block-title">
            Investment History
            <div class="indicators">
              <span class="online-indicator">{{ allParticipants.length }} participants</span>
            </div>
          </div>
          <div class="investment-history-layout">
            <!-- Left: Participant List -->
            <div class="participant-list-sidebar">
              <div class="participant-list-content">
                <div
                  v-for="participant in allParticipants"
                  :key="participant.id || participant.participant_id"
                  :class="['participant-list-item', { selected: selectedParticipantForInvestment === (participant.id || participant.participant_id) }]"
                  @click="selectParticipantForInvestment(participant)"
                >
                  <div class="participant-list-name">{{ participant.name || participant.id || participant.participant_id }}</div>
                </div>
                <div v-if="allParticipants.length === 0" class="empty">
                  No participants yet
                </div>
              </div>
            </div>
            <!-- Right: Investment History View -->
            <div class="investment-history-view-container">
              <div v-if="!selectedParticipantForInvestment" class="investment-history-placeholder">
                <p>Select a participant to view their investment history</p>
              </div>
              <div v-else class="investment-history-content">
                <div class="investment-history-header">
                  <h3>{{ allParticipants.find(p => (p.id || p.participant_id) === selectedParticipantForInvestment)?.name || selectedParticipantForInvestment }}'s Investment History</h3>
                </div>
                <div
                  v-if="selectedParticipantInvestmentHistory.length === 0"
                  class="investment-history-empty"
                >
                  No investment history
                </div>
                <div
                  v-else
                  class="investment-history-items"
                >
                  <div
                    v-for="(investment, index) in selectedParticipantInvestmentHistory"
                    :key="investment.id || index"
                    class="investment-history-item"
                  >
                    <div class="investment-header">
                      <span class="investment-type">{{ investment.investment_type || 'N/A' }}</span>
                      <span class="investment-amount">${{ investment.investment_amount || 0 }}</span>
                    </div>
                    <div class="investment-details">
                      <span class="investment-timestamp">{{ formatInvestmentTime(investment.timestamp) }}</span>
                      <span class="investment-money">Money: ${{ investment.money_before }} → ${{ investment.money_after }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Column 4: Trade (shown if shapefactory or negotiations exist) -->
        <div v-if="showTradeColumn" class="subtab-item">
          <div class="block-title">
            Trades
            <div class="indicators">
              <span class="online-indicator">{{ totalTrades }} completed</span>
              <span class="online-indicator pending">{{ pendingTrades }} pending</span>
            </div>
          </div>
          <TradesFeed
                :pending-offers="pendingOffers"
                :completed-trades="completedTrades"
                :total-trades="totalTrades"
                :pending-trades="pendingTrades"
                :participants="participantsMap"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.monitor-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.subtab-container {
  display: flex;
  gap: 16px;
  height: 100%;
  overflow: hidden;
}

.subtab-item {
  flex: 1;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  overflow-y: auto;
  background: white;
}

.subtab-item h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  border-bottom: 2px solid #e5e7eb;
  padding-bottom: 8px;
}

.subtab-item.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 14px;
}

.block-title {
  font-weight: 700;
  color: #111827;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.online-indicator {
  font-size: 12px;
  font-weight: 500;
  color: #059669;
  background: #d1fae5;
  padding: 2px 8px;
  border-radius: 12px;
  border: 1px solid #a7f3d0;
}

.indicators {
  display: flex;
  gap: 6px;
  align-items: center;
}

.online-indicator.pending {
  color: #d97706;
  background: #fef3c7;
  border-color: #fbbf24;
}

/* Conversation subtab layout */
.conversation-subtab {
  display: flex;
  flex: 2;
  flex-direction: column;
  padding: 16px;
}

.conversation-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.participant-list-sidebar {
  width: 108px;
  min-width: 108px;
  max-width: 108px;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  background: #f9fafb;
}

.participant-list-header {
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
  color: #374151;
  border-bottom: 1px solid #e5e7eb;
  background: white;
}

.participant-list-content {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

.participant-list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 6px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
  background: white;
  border: 1px solid #e5e7eb;
}

.participant-list-item:hover {
  background: #f3f4f6;
}

.participant-list-item.selected {
  background: #dbeafe;
  border-color: #3b82f6;
}

.participant-list-name {
  font-size: 11px;
  font-weight: 500;
  color: #1f2937;
  flex: 1;
  overflow: hidden;
  line-height: 1.25;
  word-break: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.participant-list-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-left: 8px;
  flex-shrink: 0;
}

.participant-list-status.online {
  background-color: #10b981;
}

.participant-list-status.offline {
  background-color: #9ca3af;
}

.conversation-view-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}

/* Investment History subtab layout */
.investment-history-subtab {
  display: flex;
  flex: 2;
  flex-direction: column;
  padding: 16px;
}

.investment-history-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.investment-history-view-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding-left: 16px;
}

.investment-history-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #9ca3af;
  font-size: 14px;
}

.investment-history-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.investment-history-header {
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.investment-history-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.investment-history-empty {
  color: #6b7280;
  font-size: 13px;
  font-style: italic;
  padding: 16px;
  text-align: center;
}

.investment-history-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.investment-history-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.investment-history-item:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.investment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.investment-type {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  text-transform: capitalize;
  padding: 4px 10px;
  background: #e5e7eb;
  border-radius: 4px;
}

.investment-amount {
  font-size: 16px;
  font-weight: 600;
  color: #0066cc;
}

.investment-details {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
}

.investment-timestamp {
  font-family: 'Courier New', monospace;
}

.investment-money {
  color: #059669;
  font-weight: 500;
}
</style>