<script setup>
import { computed } from 'vue'
import { captureActionContextSafe } from '../composables/useActionCapture.js'

const props = defineProps({
  pendingOffers: {
    type: Array,
    default: () => []
  },
  completedTrades: {
    type: Array,
    default: () => []
  },
  // If provided, filter trades/offers to only those involving this participant id
  selectedParticipant: {
    type: String,
    default: null
  },
  participants: {
    type: Object,
    default: () => ({})
  },
  maxRecentItems: {
    type: Number,
    default: 10
  },
  // Current user's participant ID
  myParticipantId: {
    type: String,
    default: null
  },
  // Session identifier for API calls
  sessionIdentifier: {
    type: String,
    default: null
  },
  // Whether session is active
  isSessionActive: {
    type: Boolean,
    default: true
  },
  // Control which sections to show
  showPendingOffers: {
    type: Boolean,
    default: true
  },
  showTradeHistory: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['offer-updated'])

// Get current user ID
const currentUserId = computed(() => {
  return props.myParticipantId || sessionStorage.getItem('participant_id')
})

// Filter offers/trades for current user or selected participant (with deduplication)
const pendingOffersFiltered = computed(() => {
  const list = Array.isArray(props.pendingOffers) ? props.pendingOffers : []
  const userId = props.selectedParticipant || currentUserId.value
  if (!userId) {
    // Deduplicate by id
    const seen = new Set()
    return list.filter(o => {
      const id = o?.id
      if (!id || seen.has(id)) return false
      seen.add(id)
      return true
    })
  }
  
  // Filter and deduplicate
  const seen = new Set()
  return list.filter(o => {
    const id = o?.id
    if (!id || seen.has(id)) return false
    if (o?.from === userId || o?.to === userId) {
      seen.add(id)
      return true
    }
    return false
  })
})

const completedTradesFiltered = computed(() => {
  const list = Array.isArray(props.completedTrades) ? props.completedTrades : []
  const userId = props.selectedParticipant || currentUserId.value
  if (!userId) {
    // Deduplicate by id
    const seen = new Set()
    return list.filter(t => {
      const id = t?.id
      if (!id || seen.has(id)) return false
      seen.add(id)
      return true
    })
  }
  
  // Filter and deduplicate
  const seen = new Set()
  return list.filter(t => {
    const id = t?.id
    if (!id || seen.has(id)) return false
    if (t?.from === userId || t?.to === userId) {
      seen.add(id)
      return true
    }
    return false
  })
})

const recentPendingOffers = computed(() => {
  return [...pendingOffersFiltered.value]
    .sort((a, b) => {
      const timeA = a.timestamp ? new Date(a.timestamp).getTime() : 0
      const timeB = b.timestamp ? new Date(b.timestamp).getTime() : 0
      return timeB - timeA
    })
    .slice(0, props.maxRecentItems)
})

const recentCompletedTrades = computed(() => {
  return [...completedTradesFiltered.value]
    .sort((a, b) => {
      const timeA = a.timestamp ? new Date(a.timestamp).getTime() : 0
      const timeB = b.timestamp ? new Date(b.timestamp).getTime() : 0
      return timeB - timeA
    })
    .slice(0, props.maxRecentItems)
})

const getDisplayName = (idOrName) => {
  // If it's already a name (string that doesn't match ID format), return it
  if (!idOrName) return 'Unknown'
  
  // Check if it's in participants map (ID lookup)
  if (props.participants && props.participants[idOrName]) {
    return props.participants[idOrName].name || idOrName
  }
  
  // Otherwise, assume it's already a name or return as-is
  return idOrName
}

const formatTime = (timestamp) => {
  if (!timestamp) return 'N/A'
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}

// Check if offer is outgoing (sent by current user)
const isOutgoingOffer = (offer) => {
  return offer?.from === currentUserId.value
}

// Get recipient display name
const getRecipientDisplay = (offer) => {
  return getDisplayName(offer?.to)
}

// Get offer sender display name
const getOfferSender = (offer) => {
  return getDisplayName(offer?.from)
}

// Get item display name - customizable based on item_type
const getItemDisplayName = (item, itemType) => {
  if (!item) return ''
  
  // If item is an object with display properties
  if (typeof item === 'object' && item !== null) {
    return item.display_name || item.name || item.value || String(item)
  }
  
  // For shape type, capitalize first letter
  if (itemType === 'shape') {
    return String(item).charAt(0).toUpperCase() + String(item).slice(1)
  }
  
  // Default: return string representation
  return String(item)
}

// Get shape display name (backward compatibility)
const getShapeDisplayName = (shape) => {
  return getItemDisplayName(shape, 'shape')
}

// Get trade item from offer/trade (supports both old and new format)
const getTradeItem = (offerOrTrade) => {
  return offerOrTrade?.trade_item || offerOrTrade?.shape || null
}

// Get item type from offer/trade
const getItemType = (offerOrTrade) => {
  return offerOrTrade?.item_type || (offerOrTrade?.shape ? 'shape' : 'price_only')
}

// Get price display
const getOfferPriceDisplay = (offer) => {
  return `$${offer?.price || 0}`
}

// Respond to offer (accept/decline)
const respondToOffer = async (offerId, response) => {
  if (!props.sessionIdentifier || !currentUserId.value) return
  
  try {
    const encodedSessionId = encodeURIComponent(props.sessionIdentifier)
    const url = `/api/sessions/${encodedSessionId}/participants/${currentUserId.value}/respond_to_offer`
    const ctx = await captureActionContextSafe()
    
    const response_data = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        offer_id: offerId,
        response: response,
        ...ctx
      })
    })
    
    const result = await response_data.json()
    if (result.success) {
      emit('offer-updated')
    } else {
      console.error('Failed to respond to offer:', result.error)
      alert(result.error || 'Failed to respond to offer')
    }
  } catch (error) {
    console.error('Error responding to offer:', error)
    alert('Error responding to offer')
  }
}

// Cancel trade offer
const cancelTradeOffer = async (offerId) => {
  if (!props.sessionIdentifier || !currentUserId.value) return
  
  try {
    const encodedSessionId = encodeURIComponent(props.sessionIdentifier)
    const url = `/api/sessions/${encodedSessionId}/participants/${currentUserId.value}/cancel_offer`
    const ctx = await captureActionContextSafe()
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        offer_id: offerId,
        ...ctx
      })
    })
    
    const result = await response.json()
    if (result.success) {
      emit('offer-updated')
    } else {
      console.error('Failed to cancel offer:', result.error)
      alert(result.error || 'Failed to cancel offer')
    }
  } catch (error) {
    console.error('Error cancelling offer:', error)
    alert('Error cancelling offer')
  }
}
</script>

<template>
  <div class="monitoring-column trades-column">
    <div class="column-content">
      <!-- Pending Offers Section -->
      <div v-if="showPendingOffers" class="trade-section">
        <h4>Pending Trade Offers</h4>
        <div class="trades-list">
          <div 
            v-for="offer in recentPendingOffers" 
            :key="`pending-${offer.id || offer.transaction_id}-${offer.timestamp}`"
            class="trade-item pending-offer"
          >
            <div class="trade-header">
              <div class="trade-participants">{{ getDisplayName(offer.from) }} → {{ getDisplayName(offer.to) }}</div>
              <div class="trade-time">{{ formatTime(offer.timestamp) }}</div>
            </div>
            <div class="trade-details">
              <span class="offer-type">{{ offer.offer_type?.toUpperCase() || 'TRADE' }}</span>
              {{ offer.quantity || 1 }}x {{ getItemDisplayName(getTradeItem(offer), getItemType(offer)) }} @ ${{ offer.price }}
            </div>
            <div :class="['trade-status', offer.status || 'pending']">{{ (offer.status || 'pending').toUpperCase() }}</div>
          </div>
          <div v-if="!recentPendingOffers.length" class="empty">No pending offers</div>
        </div>
      </div>

      <!-- Trade History Section -->
      <div v-if="showTradeHistory" class="trade-section trade-history-section">
        <h4>Trade History</h4>
        <div class="trades-list">
          <div 
            v-for="trade in recentCompletedTrades" 
            :key="`completed-${trade.id || trade.transaction_id}-${trade.timestamp}`"
            class="trade-item completed-trade"
          >
            <div class="trade-header">
              <div class="trade-participants">{{ getDisplayName(trade.from) }} → {{ getDisplayName(trade.to) }}</div>
              <div class="trade-time">{{ formatTime(trade.timestamp) }}</div>
            </div>
            <div class="trade-details">
              <span class="offer-type">{{ trade.offer_type?.toUpperCase() || 'TRADE' }}</span>
              {{ trade.quantity || 1 }}x {{ getItemDisplayName(getTradeItem(trade), getItemType(trade)) }} @ ${{ trade.price }}
            </div>
            <div :class="['trade-status', trade.status || 'completed']">{{ (trade.status || 'completed').toUpperCase() }}</div>
          </div>
          <div v-if="!recentCompletedTrades.length" class="empty">No trade history</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.monitoring-column {
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.column-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.trade-section {
  margin-bottom: 24px;
}

.trade-section h4 {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid #e5e7eb;
}

.trades-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.trade-item {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 4px;
  transition: all 0.3s;
}

.trade-item:hover {
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.pending-offer {
  border-left: 3px solid #ffc107;
  background: #fffbf0;
}

.completed-trade {
  border-left: 3px solid #28a745;
  background: #f8fff9;
}

.trade-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.trade-participants {
  font-weight: 600;
  color: #495057;
  font-size: 12px;
}

.trade-time {
  color: #6c757d;
  font-size: 10px;
}

.trade-details {
  color: #495057;
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.offer-type {
  display: inline-block;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  background: #e9ecef;
  color: #495057;
  border: 1px solid #dee2e6;
}

.trade-status {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 9px;
  font-weight: 600;
  margin-top: 2px;
}

.trade-status.pending,
.trade-status.proposed {
  background: #fff3cd;
  color: #856404;
}

.trade-status.negotiating {
  background: #cce5ff;
  color: #0056b3;
}

.trade-status.completed {
  background: #d4edda;
  color: #155724;
}

.trade-status.declined,
.trade-status.cancelled {
  background: #f8d7da;
  color: #721c24;
}

.empty {
  padding: 12px;
  text-align: center;
  color: #6b7280;
  font-size: 12px;
  font-style: italic;
}
</style>

