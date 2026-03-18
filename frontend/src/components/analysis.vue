<script setup>
import { inject, ref, computed, watch, onMounted, onUnmounted } from 'vue'

// Inject selected experiment config from researcher.vue
const selectedExperimentType = inject('selectedExperimentType')
const selectedExperimentConfig = inject('selectedExperimentConfig')
// Note: isSessionCreated should be provided from researcher.vue
// Using default value if not provided
const isSessionCreated = inject('isSessionCreated', ref(false))
const currentSessionId = inject('currentSessionId', ref(''))
const currentSessionName = inject('currentSessionName', ref(''))

// Computed: Check if trade column should be shown (same logic as monitor.vue)
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

// Computed: Check if conversation/message column should be shown (same logic as monitor.vue)
const showConversationColumn = computed(() => {
  if (!selectedExperimentConfig.value || !selectedExperimentConfig.value.interaction) return false
  
  const informationFlow = selectedExperimentConfig.value.interaction['Information Flow']
  if (!informationFlow) return false
  
  return informationFlow.some(item => item.label === 'Communication Level')
})

// Behavioral Logs Form
const behavioralLogsForm = ref({
  showTrades: false,
  showMessages: false
})

// Initialize form based on available features
watch([showTradeColumn, showConversationColumn], ([hasTrades, hasMessages]) => {
  if (hasTrades) behavioralLogsForm.value.showTrades = true
  if (hasMessages) behavioralLogsForm.value.showMessages = true
}, { immediate: true })

// Participants dropdown
const showParticipantsDropdown = ref(false)
const selectedParticipants = ref([]) // Array of participant codes, empty means all

// Session statistics
const isLoadingSessionStatistics = ref(false)
const sessionStatisticsData = ref(null)

// Helper: get participant id (supports both id and participant_id)
const getParticipantId = (p) => p?.id ?? p?.participant_id ?? ''

// Computed: Filtered participants based on selection
const filteredParticipants = computed(() => {
  if (!sessionStatisticsData.value?.participants) return []
  const participants = sessionStatisticsData.value.participants
  if (selectedParticipants.value.length === 0) return participants
  return participants.filter(p => selectedParticipants.value.includes(getParticipantId(p)))
})

// Default empty stats
const emptyStats = () => ({
  averageMoney: 0,
  highestWealth: 0,
  highestWealthParticipant: '',
  lowestWealth: 0,
  lowestWealthParticipant: '',
  totalTrades: 0,
  averageTrades: 0,
  averageTradePrice: 0,
  minTradePrice: 0,
  maxTradePrice: 0,
  totalMessages: 0,
  averageMessages: 0,
  averageMessageLength: 0,
  averageMessageLengthPerHuman: 0,
  averageMessagesPerTrade: 0,
  averageMessageResponseLatency: 0
})

// Computed: Session statistics (computed from raw data)
const sessionStatistics = computed(() => {
  if (!sessionStatisticsData.value) return emptyStats()
  const participants = filteredParticipants.value
  if (participants.length === 0) return emptyStats()
  const messages = sessionStatisticsData.value.messages || []
  const completedTrades = sessionStatisticsData.value.completed_trades || []
  const participantIds = new Set(participants.map(getParticipantId))

  // Filter trades/messages to selected participants only
  const tradesFiltered = completedTrades.filter(t =>
    participantIds.has(t.from) && participantIds.has(t.to)
  )
  const completedTradesOnly = tradesFiltered.filter(t => t.status === 'completed')
  const messagesFiltered = messages.filter(m =>
    participantIds.has(m.sender) || (m.receiver && participantIds.has(m.receiver))
  )

  // Human participants (for human-only stats)
  const humanParticipants = participants.filter(p => (p.type || '').toLowerCase() !== 'agent')
  const humanIds = new Set(humanParticipants.map(getParticipantId))
  const messagesFromHuman = messagesFiltered.filter(m => humanIds.has(m.sender))

  // Money stats (trade-related, only when showTradeColumn)
  const moneyValues = participants
    .map(p => (p.experiment_params?.money ?? p.money ?? 0) * 1)
    .filter(v => !isNaN(v))
  const totalMoney = moneyValues.reduce((a, b) => a + b, 0)
  const avgMoney = moneyValues.length ? Math.round(totalMoney / moneyValues.length) : 0
  const maxMoney = moneyValues.length ? Math.max(...moneyValues) : 0
  const minMoney = moneyValues.length ? Math.min(...moneyValues) : 0
  const highestParticipant = participants.find(p =>
    (p.experiment_params?.money ?? p.money ?? 0) === maxMoney
  )
  const lowestParticipant = participants.find(p =>
    (p.experiment_params?.money ?? p.money ?? 0) === minMoney
  )

  // Trade stats
  const totalTrades = completedTradesOnly.length
  const prices = completedTradesOnly.map(t => (t.price ?? 0) * 1).filter(v => !isNaN(v))
  const avgTradePrice = prices.length ? Math.round(prices.reduce((a, b) => a + b, 0) / prices.length) : 0
  const minTradePrice = prices.length ? Math.min(...prices) : 0
  const maxTradePrice = prices.length ? Math.max(...prices) : 0
  const avgTrades = participants.length ? (totalTrades / participants.length).toFixed(1) : 0

  // Message stats
  const totalMessages = messagesFiltered.length
  const lengths = messagesFiltered.map(m => (m.content || '').length)
  const avgMsgLen = lengths.length ? Math.round(lengths.reduce((a, b) => a + b, 0) / lengths.length) : 0
  const humanLengths = messagesFromHuman.map(m => (m.content || '').length)
  const avgMsgLenHuman = humanLengths.length
    ? Math.round(humanLengths.reduce((a, b) => a + b, 0) / humanLengths.length)
    : 0
  const avgMessages = participants.length ? (totalMessages / participants.length).toFixed(1) : 0
  const avgMessagesPerTrade = totalTrades > 0 ? (totalMessages / totalTrades).toFixed(1) : 0

  // Response latency: time between consecutive messages in same conversation
  let latencies = []
  const sortedByTime = [...messagesFiltered].sort((a, b) =>
    (a.timestamp || '').localeCompare(b.timestamp || '')
  )
  for (let i = 1; i < sortedByTime.length; i++) {
    const prev = new Date(sortedByTime[i - 1].timestamp).getTime()
    const curr = new Date(sortedByTime[i].timestamp).getTime()
    if (!isNaN(prev) && !isNaN(curr)) latencies.push((curr - prev) / 1000)
  }
  const avgLatency = latencies.length
    ? (latencies.reduce((a, b) => a + b, 0) / latencies.length).toFixed(1)
    : 0

  return {
    averageMoney: avgMoney,
    highestWealth: maxMoney,
    highestWealthParticipant: highestParticipant ? (highestParticipant.name || getParticipantId(highestParticipant)) : '',
    lowestWealth: minMoney,
    lowestWealthParticipant: lowestParticipant ? (lowestParticipant.name || getParticipantId(lowestParticipant)) : '',
    totalTrades,
    averageTrades: avgTrades,
    averageTradePrice: avgTradePrice,
    minTradePrice,
    maxTradePrice,
    totalMessages,
    averageMessages: avgMessages,
    averageMessageLength: avgMsgLen,
    averageMessageLengthPerHuman: avgMsgLenHuman,
    averageMessagesPerTrade: avgMessagesPerTrade,
    averageMessageResponseLatency: avgLatency
  }
})

// Chart data
const chartData = ref({
  participantChartData: []
})

// Timeline data
const timelineDataByParticipant = ref([])

// Methods
const toggleParticipantsDropdown = () => {
  showParticipantsDropdown.value = !showParticipantsDropdown.value
}

const selectAllParticipants = () => {
  selectedParticipants.value = []
  showParticipantsDropdown.value = false
}

const toggleParticipantSelection = (participantCode) => {
  const index = selectedParticipants.value.indexOf(participantCode)
  if (index > -1) {
    selectedParticipants.value.splice(index, 1)
  } else {
    selectedParticipants.value.push(participantCode)
  }
}

const isParticipantSelected = (participantCode) => {
  return selectedParticipants.value.length === 0 || selectedParticipants.value.includes(participantCode)
}

const getParticipantsDropdownLabel = () => {
  if (selectedParticipants.value.length === 0) return 'All Participants'
  if (selectedParticipants.value.length === 1) {
    return getDisplayName(selectedParticipants.value[0])
  }
  return `${selectedParticipants.value.length} participants selected`
}

const getDisplayName = (participantCode) => {
  const participants = sessionStatisticsData.value?.participants || []
  const p = participants.find(x => getParticipantId(x) === participantCode)
  return p ? (p.name || p.participant_name || participantCode) : participantCode
}

// Polling interval for real-time updates (ms)
const POLL_INTERVAL = 5000
let pollTimer = null

const loadSessionStatistics = async () => {
  const sessionIdentifier = currentSessionId.value || currentSessionName.value
  if (!sessionIdentifier) {
    sessionStatisticsData.value = null
    return
  }
  isLoadingSessionStatistics.value = true
  try {
    const encoded = encodeURIComponent(sessionIdentifier)
    const response = await fetch(`/api/sessions/${encoded}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    if (!response.ok) {
      sessionStatisticsData.value = null
      return
    }
    const session = await response.json()
    sessionStatisticsData.value = {
      participants: session.participants || [],
      messages: session.messages || [],
      completed_trades: session.completed_trades || [],
      started_at: session.started_at
    }
    // Update chart and timeline data
    computeChartAndTimelineData()
  } catch (error) {
    console.error('Failed to load session statistics:', error)
    sessionStatisticsData.value = null
  } finally {
    isLoadingSessionStatistics.value = false
  }
}

// Compute chart data (trades per participant, messages per participant)
const computeChartAndTimelineData = () => {
  const data = sessionStatisticsData.value
  if (!data) return
  const participants = data.participants || []
  const completedTrades = (data.completed_trades || []).filter(t => t.status === 'completed')
  const messages = data.messages || []

  const participantIds = participants.map(getParticipantId)
  const tradesByParticipant = {}
  const messagesByParticipant = {}
  participantIds.forEach(id => {
    tradesByParticipant[id] = 0
    messagesByParticipant[id] = 0
  })
  completedTrades.forEach(t => {
    if (t.from) tradesByParticipant[t.from] = (tradesByParticipant[t.from] || 0) + 1
    if (t.to) tradesByParticipant[t.to] = (tradesByParticipant[t.to] || 0) + 1
  })
  messages.forEach(m => {
    if (m.sender) messagesByParticipant[m.sender] = (messagesByParticipant[m.sender] || 0) + 1
  })

  const participantsFiltered = selectedParticipants.value.length
    ? participants.filter(p => selectedParticipants.value.includes(getParticipantId(p)))
    : participants
  const ids = participantsFiltered.map(getParticipantId)

  chartData.value.participantChartData = ids.map(id => {
    const p = participants.find(x => getParticipantId(x) === id)
    const name = p ? (p.name || p.participant_name || id) : id
    return {
      participantId: id,
      participantName: name,
      trades: tradesByParticipant[id] || 0,
      messages: messagesByParticipant[id] || 0
    }
  })

  // Timeline: group trades by participant, each trade has firstTradeTime, lastTradeTime
  const sessionStart = data.started_at ? new Date(data.started_at).getTime() : null
  const tradesWithTime = completedTrades.map(t => {
    const ts = new Date(t.timestamp || 0).getTime()
    return { ...t, participantId: t.from, timestamp: ts }
  })
  const tradesByParticipantList = {}
  completedTrades.forEach(t => {
    const pid = t.from
    if (!tradesByParticipantList[pid]) tradesByParticipantList[pid] = []
    tradesByParticipantList[pid].push(t)
  })
  const participantIdsForTimeline = selectedParticipants.value.length
    ? selectedParticipants.value
    : participantIds
  timelineDataByParticipant.value = participantIdsForTimeline.map(pid => {
    const trades = (tradesByParticipantList[pid] || []).sort((a, b) =>
      (a.timestamp || '').localeCompare(b.timestamp || '')
    )
    return [
      pid,
      trades.map(t => ({
        ...t,
        firstTradeTime: t.timestamp,
        lastTradeTime: t.timestamp,
        isCompleted: t.status === 'completed'
      }))
    ]
  }).filter(([, trades]) => trades.length > 0)
}

// Timeline time range (from session start or first trade)
const timelineTimeRange = computed(() => {
  const data = sessionStatisticsData.value
  if (!data) return { start: 0, end: 0 }
  const trades = data.completed_trades || []
  const startStr = data.started_at
  let start = startStr ? new Date(startStr).getTime() : 0
  let end = start
  trades.forEach(t => {
    const ts = new Date(t.timestamp || 0).getTime()
    if (ts > 0) {
      if (start === 0 || ts < start) start = ts
      if (ts > end) end = ts
    }
  })
  if (start === 0) start = Date.now()
  if (end < start) end = start + 60 * 60 * 1000
  return { start, end }
})

const getTimelinePosition = (time) => {
  const { start, end } = timelineTimeRange.value
  if (!time || end <= start) return 0
  const t = typeof time === 'string' ? new Date(time).getTime() : time
  return Math.max(0, Math.min(100, ((t - start) / (end - start)) * 100))
}

const getTimelineWidth = (firstTradeTime, lastTradeTime) => {
  const { start, end } = timelineTimeRange.value
  if (!firstTradeTime || !lastTradeTime || end <= start) return 2
  const f = typeof firstTradeTime === 'string' ? new Date(firstTradeTime).getTime() : firstTradeTime
  const l = typeof lastTradeTime === 'string' ? new Date(lastTradeTime).getTime() : lastTradeTime
  return Math.max(2, ((l - f) / (end - start)) * 100)
}

const formatTimeLabel = (ms) => {
  const d = new Date(ms)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const getStartTimeLabel = () => {
  return formatTimeLabel(timelineTimeRange.value.start)
}

const getMiddleTimeLabel = () => {
  const { start, end } = timelineTimeRange.value
  return formatTimeLabel(start + (end - start) / 2)
}

const getEndTimeLabel = () => {
  return formatTimeLabel(timelineTimeRange.value.end)
}

const showTimelineTooltip = (event, trade, participant, index) => {
  // Placeholder - show tooltip
}

const hideTooltip = () => {
  // Placeholder - hide tooltip
}

// Bar chart width: max 100%, scale relative to max value in dataset
const getBarWidth = (value, type) => {
  const data = chartData.value.participantChartData || []
  const maxVal = Math.max(1, ...data.map(d => (type === 'trades' ? d.trades : d.messages)))
  return value > 0 ? Math.max(5, (value / maxVal) * 100) : 0
}

// Export form
const exportForm = ref({
  dataType: 'all',
  fileFormat: 'json'
})

// Watch for experiment config changes and reset export type if needed
watch([showTradeColumn, showConversationColumn], ([hasTrades, hasMessages]) => {
  // If current selection is trades but trades are not available, reset to 'all'
  if (exportForm.value.dataType === 'trades' && !hasTrades) {
    exportForm.value.dataType = 'all'
  }
  // If current selection is messages but messages are not available, reset to 'all'
  if (exportForm.value.dataType === 'messages' && !hasMessages) {
    exportForm.value.dataType = 'all'
  }
})

const exportData = () => {
  // Validate that selected data type is available in current experiment config
  if (exportForm.value.dataType === 'trades' && !showTradeColumn.value) {
    alert('Trades data is not available for the current experiment configuration.')
    return
  }
  
  if (exportForm.value.dataType === 'messages' && !showConversationColumn.value) {
    alert('Messages data is not available for the current experiment configuration.')
    return
  }
  
  // TODO: Implement actual data export API call
  console.log('Exporting data:', exportForm.value)
  
  // Placeholder: This should call the backend API to export data
  // Example:
  // try {
  //   const response = await fetch('/api/export', {
  //     method: 'POST',
  //     headers: { 'Content-Type': 'application/json' },
  //     body: JSON.stringify(exportForm.value)
  //   })
  //   // Handle response (download file, etc.)
  // } catch (error) {
  //   console.error('Export failed:', error)
  //   alert('Failed to export data. Please try again.')
  // }
}

// Poll for real-time updates when session is active
const startPolling = () => {
  stopPolling()
  pollTimer = setInterval(() => {
    if (isSessionCreated.value && (currentSessionId.value || currentSessionName.value)) {
      loadSessionStatistics()
    }
  }, POLL_INTERVAL)
}
const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// Load statistics on mount if session is registered
onMounted(() => {
  if (isSessionCreated.value) {
    loadSessionStatistics()
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})

watch(isSessionCreated, (newVal) => {
  if (newVal) {
    loadSessionStatistics()
    startPolling()
  } else {
    stopPolling()
    sessionStatisticsData.value = null
  }
})

watch([currentSessionId, currentSessionName], () => {
  if (isSessionCreated.value && (currentSessionId.value || currentSessionName.value)) {
    loadSessionStatistics()
  }
})

watch(selectedParticipants, () => {
  if (sessionStatisticsData.value) computeChartAndTimelineData()
}, { deep: true })
</script>

<template>
  <div class="tab-col analysis-tab">
    <div class="subtab-container">
      <!-- Column 1: Behavioral Logs -->
      <div class="subtab-item behavioral-logs">
        <div class="block-title">
          Behavioral Logs
        </div>
        
        <div class="behavioral-logs-content">
          <!-- Left Column: Controls and Statistics -->
          <div class="left-column">
            <!-- Controls Section -->
            <div class="controls-section">
              <!-- Participants Dropdown -->
              <div class="control-group">
                <label>Participants</label>
                <div class="custom-select-wrapper">
                  <div class="custom-select-trigger" @click="toggleParticipantsDropdown">
                    <div class="selected-content">
                      <span class="selected-option">{{ getParticipantsDropdownLabel() }}</span>
                    </div>
                    <span class="dropdown-arrow">▼</span>
                  </div>
                  <div class="custom-dropdown-menu" v-if="showParticipantsDropdown">
                    <div class="dropdown-item" @click="selectAllParticipants">
                      <div class="option-content">
                        <span class="option-tag">All Participants</span>
                      </div>
                    </div>
                    <div 
                      class="dropdown-item" 
                      v-for="participant in sessionStatisticsData?.participants || []" 
                      :key="getParticipantId(participant)"
                      @click="toggleParticipantSelection(getParticipantId(participant))"
                    >
                      <div class="option-content">
                        <input 
                          type="checkbox" 
                          :checked="isParticipantSelected(getParticipantId(participant))"
                          @click.stop
                          @change="toggleParticipantSelection(getParticipantId(participant))"
                          class="participant-checkbox"
                        />
                        <span class="participant-name">{{ getDisplayName(getParticipantId(participant)) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Checkboxes - Only show if the feature is available in experiment config -->
              <div class="control-group" v-if="showTradeColumn || showConversationColumn">
                <label>Data Types</label>
                <div class="checkbox-group">
                  <label v-if="showTradeColumn" class="checkbox-label">
                    <input 
                      type="checkbox" 
                      v-model="behavioralLogsForm.showTrades"
                      class="checkbox-input"
                    />
                    <span class="checkbox-text">Trades</span>
                  </label>
                  <label v-if="showConversationColumn" class="checkbox-label">
                    <input 
                      type="checkbox" 
                      v-model="behavioralLogsForm.showMessages"
                      class="checkbox-input"
                    />
                    <span class="checkbox-text">Messages</span>
                  </label>
                </div>
              </div>
            </div>

            <!-- Statistics Section -->
            <div class="statistics-section">
              <div class="section-title">
                Session Statistics
                <button 
                  class="refresh-btn" 
                  @click="loadSessionStatistics"
                  :disabled="isLoadingSessionStatistics"
                  title="Refresh statistics"
                >
                  <span v-if="isLoadingSessionStatistics">⟳</span>
                  <span v-else>⟳</span>
                </button>
              </div>
              <div v-if="isLoadingSessionStatistics" class="loading-message">
                Loading session statistics...
              </div>
              <div v-else-if="!sessionStatisticsData" class="no-data-message">
                No session statistics available. Please ensure a session is loaded.
              </div>
              <div v-else class="stats-container">
                <!-- General Statistics (trade-related: only show when experiment has trade) -->
                <div v-if="showTradeColumn" class="stats-category">
                  <div class="category-header">General</div>
                  <div class="stats-list">
                    <div class="stat-item">
                      <span class="stat-label">Average Money Balance</span>
                      <span class="stat-value">${{ sessionStatistics.averageMoney }}</span>
                    </div>
                    <div v-if="filteredParticipants.length > 1" class="stat-item">
                      <span class="stat-label">Highest Wealth</span>
                      <span class="stat-value">${{ sessionStatistics.highestWealth }} ({{ sessionStatistics.highestWealthParticipant }})</span>
                    </div>
                    <div v-if="filteredParticipants.length > 1" class="stat-item">
                      <span class="stat-label">Lowest Wealth</span>
                      <span class="stat-value">${{ sessionStatistics.lowestWealth }} ({{ sessionStatistics.lowestWealthParticipant }})</span>
                    </div>
                  </div>
                </div>
                
                <!-- Trade Statistics - Only show if trades are enabled in config -->
                <div v-if="showTradeColumn && behavioralLogsForm.showTrades" class="stats-category">
                  <div class="category-header">Trade</div>
                  <div class="stats-list">
                    <div class="stat-item">
                      <span class="stat-label">Total Successful Trades</span>
                      <span class="stat-value">{{ sessionStatistics.totalTrades }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Avg Successful Trades</span>
                      <span class="stat-value">{{ sessionStatistics.averageTrades }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Average Trade Price</span>
                      <span class="stat-value">${{ sessionStatistics.averageTradePrice }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Price Range</span>
                      <span class="stat-value">${{ sessionStatistics.minTradePrice }} - ${{ sessionStatistics.maxTradePrice }}</span>
                    </div>
                  </div>
                </div>
                
                <!-- Message Statistics - Only show if messages are enabled in config -->
                <div v-if="showConversationColumn && behavioralLogsForm.showMessages" class="stats-category">
                  <div class="category-header">Message</div>
                  <div class="stats-list">
                    <div class="stat-item">
                      <span class="stat-label">Total Messages</span>
                      <span class="stat-value">{{ sessionStatistics.totalMessages }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Avg Messages per User</span>
                      <span class="stat-value">{{ sessionStatistics.averageMessages }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Avg Message Length (All)</span>
                      <span class="stat-value">{{ sessionStatistics.averageMessageLength }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Avg Message Length (Human)</span>
                      <span class="stat-value">{{ sessionStatistics.averageMessageLengthPerHuman }}</span>
                    </div>
                    <div v-if="showTradeColumn" class="stat-item">
                      <span class="stat-label">Messages per Trade</span>
                      <span class="stat-value">{{ sessionStatistics.averageMessagesPerTrade }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Avg Response Latency</span>
                      <span class="stat-value">{{ sessionStatistics.averageMessageResponseLatency }}s</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Right Column: Charts -->
          <div class="right-column">
            <div class="charts-section">
              <div class="section-title">Charts</div>
              <div class="charts-grid">
                <!-- Chart 1: Trade Timeline (when trades are selected and available) -->
                <div v-if="showTradeColumn && behavioralLogsForm.showTrades" class="chart-container">
                  <div class="chart-title">
                    <span class="chart-title-text">Trade Timeline</span>
                    <div class="chart-legend">
                      <span class="legend-item">
                        <span class="legend-color completed"></span>
                        Completed Trades
                      </span>
                      <span class="legend-item">
                        <span class="legend-color pending"></span>
                        Pending Offers
                      </span>
                    </div>
                  </div>
                  <div class="chart-placeholder">
                    <div v-if="timelineDataByParticipant.length === 0" class="chart-no-data">
                      <div class="no-data-message">
                        <div class="no-data-icon">Chart</div>
                        <div class="no-data-text">No trade data available for selected participants</div>
                      </div>
                    </div>
                    <div v-else class="timeline-container">
                      <!-- Y-axis label -->
                      <div class="y-axis-label">Participants</div>
                      
                      <!-- Timeline rows -->
                      <div class="timeline-rows">
                        <div 
                          v-for="[participantId, trades] in timelineDataByParticipant" 
                          :key="participantId"
                          class="timeline-row"
                        >
                          <div class="participant-label">{{ getDisplayName(participantId) }}</div>
                          <div class="timeline-bars">
                            <div 
                              v-for="(trade, index) in trades" 
                              :key="`${participant}-${index}`"
                              class="timeline-bar"
                              :style="{ 
                                left: getTimelinePosition(trade.firstTradeTime) + '%',
                                width: trade.isCompleted ? getTimelineWidth(trade.firstTradeTime, trade.lastTradeTime) + '%' : '2px'
                              }"
                              :class="{ 
                                completed: trade.isCompleted,
                                pending: !trade.isCompleted
                              }"
                              @mouseenter="showTimelineTooltip($event, trade, participantId, index)"
                              @mouseleave="hideTooltip"
                            >
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      <!-- X-axis with time labels and label below -->
                      <div class="timeline-x-axis">
                        <div class="x-axis-labels">
                          <span class="x-label start">{{ getStartTimeLabel() }}</span>
                          <span class="x-label middle">{{ getMiddleTimeLabel() }}</span>
                          <span class="x-label end">{{ getEndTimeLabel() }}</span>
                        </div>
                        <div class="x-axis-label">Time</div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Chart 2: Trade Numbers (when trades are selected and available) -->
                <div v-if="showTradeColumn && behavioralLogsForm.showTrades" class="chart-container">
                  <div class="chart-title">
                    Trade Numbers by Participant
                  </div>
                  <div class="chart-placeholder">
                    <div v-if="chartData.participantChartData.length === 0" class="chart-no-data">
                      <div class="no-data-message">
                        <div class="no-data-icon">Chart</div>
                        <div class="no-data-text">No trade data available for selected participants</div>
                      </div>
                    </div>
                    <div v-else class="bar-chart-container">
                      <div
                        v-for="item in chartData.participantChartData"
                        :key="item.participantId"
                        class="bar-chart-row"
                      >
                        <span class="bar-label">{{ item.participantName }}</span>
                        <div class="bar-track">
                          <div
                            class="bar-fill trades"
                            :style="{ width: getBarWidth(item.trades, 'trades') + '%' }"
                          ></div>
                        </div>
                        <span class="bar-value">{{ item.trades }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                
                <!-- Chart 3: Number of Sent Messages (when messages are selected and available) -->
                <div v-if="showConversationColumn && behavioralLogsForm.showMessages" class="chart-container">
                  <div class="chart-title">
                    Number of Sent Messages by Participant
                  </div>
                  <div class="chart-placeholder">
                    <div v-if="chartData.participantChartData.length === 0" class="chart-no-data">
                      <div class="no-data-message">
                        <div class="no-data-icon">Chart</div>
                        <div class="no-data-text">No message data available for selected participants</div>
                      </div>
                    </div>
                    <div v-else class="bar-chart-container">
                      <div
                        v-for="item in chartData.participantChartData"
                        :key="item.participantId"
                        class="bar-chart-row"
                      >
                        <span class="bar-label">{{ item.participantName }}</span>
                        <div class="bar-track">
                          <div
                            class="bar-fill messages"
                            :style="{ width: getBarWidth(item.messages, 'messages') + '%' }"
                          ></div>
                        </div>
                        <span class="bar-value">{{ item.messages }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                
                <!-- No data selected message -->
                <div v-if="(!showTradeColumn || !behavioralLogsForm.showTrades) && (!showConversationColumn || !behavioralLogsForm.showMessages)" class="no-data-selected">
                  <div class="no-data-message">
                    <div class="no-data-icon">Chart</div>
                    <div class="no-data-text">Please select at least one data type to view charts</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- Column 2: Data Export -->
      <div class="subtab-item data-export">
        <div class="block-title">
          Data Export
        </div>
        <div class="export-form">
          <div class="form-group">
            <label for="data-type">Data to Export</label>
            <select 
              class="select" 
              v-model="exportForm.dataType"
              id="data-type"
            >
              <option value="all">All Data (Complete session export)</option>
              <option value="participants">Participants Data</option>
              <option v-if="showTradeColumn" value="trades">Trades Data</option>
              <option v-if="showConversationColumn" value="messages">Messages Data</option>
              <option value="logs">System Logs</option>
            </select>
          </div>
                
          <div class="form-group">
            <label for="file-format">File Format</label>
            <select 
              class="select" 
              v-model="exportForm.fileFormat"
              id="file-format"
            >
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
              <option value="excel">Excel (.xlsx)</option>
            </select>
          </div>
                
          <div class="form-actions">
            <button 
              class="btn primary" 
              @click="exportData"
              :disabled="!isSessionCreated"
            >
              Export Data
            </button>
          </div>
          
          <div v-if="!isSessionCreated" class="form-helper">
            ⚠️ Create or load a session first to enable data export
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.analysis-tab {
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

.block-title {
  font-weight: 700;
  color: #111827;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.behavioral-logs {
  flex: 2;
  overflow-y: unset;
}

.data-export {
  flex: 1;
}

/* Behavioral Logs Content */
.behavioral-logs-content {
  display: flex;
  gap: 16px;
  height: calc(100% - 40px);
  min-height: 0;
}

.left-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.right-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* Controls Section */
.controls-section {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  text-align: left;
}

.control-group {
  margin-bottom: 16px;
}

/* Remove margin from last control-group */
.control-group:last-child {
  margin-bottom: 0;
}

.control-group label {
  font-weight: 600;
  color: #374151;
  font-size: 14px;
}

/* Custom Select */
.custom-select-wrapper {
  position: relative;
}

.custom-select-trigger {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.custom-select-trigger:hover {
  border-color: #9ca3af;
}

.dropdown-arrow {
  color: #6b7280;
  font-size: 12px;
}

.custom-dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  z-index: 100;
  max-height: 200px;
  overflow-y: auto;
}

.dropdown-item {
  padding: 8px 12px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.dropdown-item:hover {
  background-color: #f3f4f6;
}

.option-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.participant-checkbox {
  margin: 0;
}

.participant-name {
  font-size: 14px;
  color: #374151;
}

/* Checkbox Group */
.checkbox-group {
  display: flex;
  flex-direction: row;
  gap: 8px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-weight: normal;
  font-weight: 400 !important;
}

.checkbox-input {
  margin: 0;
}

.checkbox-text {
  font-size: 14px;
  color: #374151;
}

/* Statistics Section */
.statistics-section {
  flex: 1;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  overflow-y: auto;
  min-height: 0;
}

.section-title {
  font-weight: 800;
  color: #1f2937a6;
  font-size: 14px;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}


.refresh-btn {
  background: transparent;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: #f3f4f6;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-message,
.no-data-message {
  padding: 16px;
  text-align: center;
  color: #6b7280;
  font-size: 14px;
}

.stats-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-category {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
}

.category-header {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  background: #f0f5fe;
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 8px;
  border-left: 3px solid #3b82f6;
}

.stats-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #f3f4f6;
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
}

.stat-value {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
}

/* Charts Section */
.charts-section {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.charts-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 16px;
  overflow-y: auto;
  padding: 6px 0;
}

.chart-container {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  min-height: 200px;
}

.chart-title {
  font-weight: 600;
  color: #111827;
  margin-bottom: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.chart-title-text {
  flex: 1;
}

.chart-legend {
  display: flex;
  gap: 16px;
  font-size: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #6b7280;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.legend-color.completed {
  background-color: #3b82f6;
}

.legend-color.pending {
  background-color: #f59e0b;
}

.chart-placeholder {
  height: calc(100% - 40px);
  min-height: 250px;
}

.chart-no-data,
.no-data-selected {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.no-data-icon {
  font-size: 48px;
  color: #d1d5db;
  margin-bottom: 8px;
}

.no-data-text {
  color: #6b7280;
  font-size: 14px;
}

/* Timeline Chart */
.timeline-container {
  position: relative;
  height: 100%;
  padding: 20px 40px 40px 60px;
}

.y-axis-label {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%) rotate(-90deg);
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
}

.timeline-rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 30px;
}

.timeline-row {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 30px;
}

.participant-label {
  min-width: 100px;
  font-size: 12px;
  color: #374151;
  text-align: right;
}

.timeline-bars {
  flex: 1;
  position: relative;
  height: 20px;
  background: #f3f4f6;
  border-radius: 4px;
}

.timeline-bar {
  position: absolute;
  height: 100%;
  border-radius: 4px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.timeline-bar.completed {
  background-color: #3b82f6;
}

.timeline-bar.pending {
  background-color: #f59e0b;
}

.timeline-bar:hover {
  opacity: 0.8;
}

.timeline-x-axis {
  position: absolute;
  bottom: 0;
  left: 60px;
  right: 0;
}

.x-axis-labels {
  display: flex;
  justify-content: space-between;
  padding: 0 20px;
  margin-bottom: 4px;
}

.x-label {
  font-size: 11px;
  color: #6b7280;
}

.x-axis-label {
  text-align: center;
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}

.bar-chart-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 0;
  min-height: 200px;
}

.bar-chart-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bar-label {
  min-width: 100px;
  font-size: 13px;
  color: #374151;
}

.bar-track {
  flex: 1;
  height: 24px;
  background: #f3f4f6;
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.bar-fill.trades {
  background: #3b82f6;
}

.bar-fill.messages {
  background: #10b981;
}

.bar-value {
  min-width: 32px;
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  text-align: right;
}

.google-chart-container {
  height: 100%;
  min-height: 250px;
}

.google-chart {
  height: 100%;
  width: 100%;
}

/* Export Form */
.export-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-weight: 600;
  color: #374151;
  font-size: 14px;
}

.select {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  background: white;
}

.form-actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.btn.primary {
  background: #3b82f6;
  color: white;
}

.btn.primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-helper {
  padding: 12px;
  background: #fef3c7;
  border: 1px solid #fbbf24;
  border-radius: 6px;
  color: #92400e;
  font-size: 13px;
}
</style>