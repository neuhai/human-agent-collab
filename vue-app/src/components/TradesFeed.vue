<template>
  <div class="monitoring-column trades-column">
    <div class="column-content">
      <!-- Pending Offers Section -->
      <div v-if="pendingOffers.length > 0" class="trades-section">
        <h4 class="section-title">Pending Offers</h4>
        <div class="trades-list">
          <div 
            v-for="offer in recentPendingOffers" 
            :key="`pending-${offer.id}-${offer.timestamp}`"
            class="trade-item pending-offer"
          >
            <div class="trade-header">
              <div class="trade-participants">{{ getDisplayName(offer.from) }} → {{ getDisplayName(offer.to) }}</div>
              <div class="trade-time">{{ formatTime(offer.timestamp) }}</div>
            </div>
            <div class="trade-details">
              <span class="offer-type">{{ offer.offer_type?.toUpperCase() || 'TRADE' }}</span>
              {{ offer.quantity }}x {{ offer.shape }} @ ${{ offer.price }}
            </div>
            <div :class="['trade-status', offer.status]">{{ offer.status.toUpperCase() }}</div>
          </div>
        </div>
      </div>

      <!-- Completed Trades Section -->
      <div v-if="completedTrades.length > 0" class="trades-section">
        <h4 class="section-title">Completed Trades</h4>
        <div class="trades-list">
          <div 
            v-for="trade in recentCompletedTrades" 
            :key="`completed-${trade.id}-${trade.timestamp}`"
            class="trade-item completed-trade"
          >
            <div class="trade-header">
              <div class="trade-participants">{{ getDisplayName(trade.from) }} → {{ getDisplayName(trade.to) }}</div>
              <div class="trade-time">{{ formatTime(trade.timestamp) }}</div>
            </div>
            <div class="trade-details">
              <span class="offer-type">{{ trade.offer_type?.toUpperCase() || 'TRADE' }}</span>
              {{ trade.quantity }}x {{ trade.shape }} @ ${{ trade.price }}
            </div>
            <div :class="['trade-status', trade.status]">{{ trade.status.toUpperCase() }}</div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-if="pendingOffers.length === 0 && completedTrades.length === 0" class="empty">
        No trades or offers yet
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Trade {
  id?: string
  from: string
  to: string
  shape: string
  quantity: number
  price: number
  status: string
  timestamp: Date
  offer_type?: string
}

const props = defineProps<{
  pendingOffers: Trade[]
  completedTrades: Trade[]
  totalTrades: number
  pendingTrades: number
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

const recentPendingOffers = computed(() => {
  // Show newest pending offers first (already sorted from API)
  return props.pendingOffers.slice(0, 10)
})

const recentCompletedTrades = computed(() => {
  // Show newest completed trades first (already sorted from API)
  return props.completedTrades.slice(0, 10)
})

const formatTime = (timestamp: Date) => {
  return new Date(timestamp).toLocaleTimeString()
}
</script>

<style scoped>
.trades-feed {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.trades-section {
  margin-bottom: 16px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #495057;
  margin: 0 0 8px 0;
  padding: 4px 8px;
  background: #f8f9fa;
  border-radius: 4px;
  border-left: 3px solid #6c757d;
}

.trades-section:first-child .section-title {
  border-left-color: #ffc107; /* Yellow for pending */
}

.trades-section:last-child .section-title {
  border-left-color: #28a745; /* Green for completed */
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
  text-align: center;
  color: #6c757d;
  font-style: italic;
  padding: 20px;
}
</style> 