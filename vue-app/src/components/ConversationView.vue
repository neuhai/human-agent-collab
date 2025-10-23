<template>
  <div class="monitoring-column messages-column">
    
    <div class="column-content">
      <div class="conversation-interface">
        <!-- Left: Participant List (only in chat mode) -->
        <div v-if="commLevel === 'chat'" class="participant-list-sidebar">
          <h4>Participants:</h4>
          <div class="participant-list-vertical">
            <div 
              v-for="participant in participants" 
              :key="participant.id"
              :class="[
                'participant-list-item',
                { 'has-messages': getMessagesForParticipant(participant.id).length > 0 },
                { 'active': selectedParticipant === participant.id }
              ]"
              @click="selectParticipant(participant.id)"
            >
              <div class="participant-id">{{ getDisplayName(participant.id) }}</div>
              <div class="message-count">{{ getMessagesForParticipant(participant.id).length }} msgs</div>
            </div>
          </div>
        </div>
        
        <!-- Right: Conversation View -->
        <div class="conversation-main">
          <div v-if="commLevel === 'no_chat'" class="no-conversation">
            <div>
              <p><strong>Messaging disabled</strong></p>
              <p>Conversations are unavailable in no-chat mode</p>
            </div>
          </div>
          
          <!-- Broadcast Mode -->
          <div v-else-if="commLevel === 'broadcast'" class="broadcast-mode">
            <div class="broadcast-info">
              <h4>📢 Public Message Pool</h4>
              <p>All participants can see messages posted here. No direct messaging allowed.</p>
            </div>
            
            <!-- Broadcast Message Thread -->
            <div class="message-thread">
              <div class="message-history" ref="messageHistory">
                <div 
                  v-for="message in broadcastMessages" 
                  :key="message.id" 
                  class="message-item broadcast-message"
                >
                  <div class="message-sender">{{ getDisplayName(message.sender) }}</div>
                  <div class="message-content">{{ message.content }}</div>
                  <div class="message-time">{{ formatTime(message.timestamp) }}</div>
                </div>
                <div v-if="!broadcastMessages.length" class="empty">No group chat messages yet</div>
              </div>
            </div>
          </div>
          
          <!-- Chat Mode -->
          <template v-else>
            <div v-if="!selectedParticipant" class="no-conversation">
              <div>
                <p><strong>No participant selected</strong></p>
                <p>Click on a participant from the left to view their conversations</p>
              </div>
            </div>
            
            <div v-else class="conversation-content">
              <div class="conversation-header">
                <span>
                  Conversations for: {{ getDisplayName(selectedParticipant) }} ({{ getParticipantType(selectedParticipant) }})
                  <span class="mode-indicator" :class="commLevel">{{ commLevel.toUpperCase() }} MODE</span>
                </span>
              </div>
              
              <div class="conversation-messages">
                <div v-if="Object.keys(conversations).length === 0" class="no-conversation">
                  <p>No conversations yet for {{ selectedParticipant }}</p>
                </div>
                
                <div v-for="(messages, threadKey) in conversations" :key="threadKey" class="conversation-thread">
                  <div class="thread-header">
                    <strong>{{ threadLabel(threadKey) }}</strong> ({{ messages.length }} messages)
                  </div>
                  
                  <div class="thread-messages">
                    <div v-for="(message, index) in messages" :key="index" 
                         :class="['conversation-message', message.from === selectedParticipant ? 'sent' : 'received']">
                      <div class="message-meta">
                        <strong>{{ getDisplayName(message.from) }}</strong> → <strong>{{ getDisplayName(message.to) }}</strong> | {{ formatTime(message.timestamp) }}
                      </div>
                      <div class="message-content">{{ message.content }}</div>
                    </div>
                  </div>
                </div>
              </div>
              
              <div class="conversation-stats">
                Total: {{ totalMessagesForParticipant }} messages | 
                Active conversations: {{ Object.keys(conversations).length }}
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'

interface Participant {
  id: string
  type: string
  specialty: string
  status: string
  money: number
  orders_completed: number
  trades_made: number
  login_time: string | null
}

interface Message {
  from: string
  to: string
  content: string
  timestamp: Date
}

const props = defineProps<{
  participants: Participant[]
  messages: Message[]
  totalMessages: number
  activeConversations: number
  communicationLevel: 'chat' | 'broadcast' | 'no_chat'
  selectedParticipant?: string | null
}>()

const selectedParticipant = ref<string | null>(props.selectedParticipant || null)
const commLevel = computed(() => props.communicationLevel)

// Watch for changes in the selectedParticipant prop
watch(() => props.selectedParticipant, (newValue) => {
  selectedParticipant.value = newValue || null
}, { immediate: true })

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

// Computed property for broadcast messages
const broadcastMessages = computed(() => {
  if (props.communicationLevel !== 'broadcast') {
    return []
  }
  // In broadcast mode, show all messages since they're all visible to everyone
  // Filter messages where recipient is 'all' or null (true broadcast messages)
  // OR show all messages if no true broadcast messages exist (fallback for mixed mode)
  const trueBroadcastMessages = props.messages.filter((msg: Message) => {
    const recipient = msg.to?.toLowerCase() || msg.to
    return recipient === 'all' || recipient === null
  })
  
  // If we have true broadcast messages, use them; otherwise show all messages
  const messagesToShow = trueBroadcastMessages.length > 0 ? trueBroadcastMessages : props.messages
  
  return messagesToShow
    .map((msg: Message) => ({
      id: `${msg.from}-${msg.timestamp.getTime()}`,
      sender: msg.from,
      content: msg.content,
      timestamp: msg.timestamp
    }))
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
})

const getMessagesForParticipant = (participantId: string) => {
  if (props.communicationLevel === 'no_chat') {
    return []
  }
  if (props.communicationLevel === 'broadcast') {
    // Include broadcasts to all (as received) and messages sent by the participant (broadcasts they sent)
    const broadcastMessages = props.messages.filter((msg: Message) => {
      const recipient = msg.to?.toLowerCase() || msg.to
      return msg.from === participantId || recipient === 'all' || recipient === null
    })
    return broadcastMessages
  }
  // chat mode: direct messages only
  const chatMessages = props.messages.filter((msg: Message) => msg.from === participantId || msg.to === participantId)
  return chatMessages
}

const getParticipantType = (participantId: string) => {
  const participant = props.participants.find((p: Participant) => p.id === participantId)
  return participant?.type || 'unknown'
}

const conversations = computed(() => {
  if (!selectedParticipant.value) return {}
  if (props.communicationLevel === 'no_chat') return {}
  
  const participantMessages = getMessagesForParticipant(selectedParticipant.value)
  
  const convos: Record<string, Message[]> = {}
  
  participantMessages.forEach((msg: Message) => {
    let threadKey: string
    if (props.communicationLevel === 'broadcast') {
      threadKey = 'all'
    } else {
      // chat mode: pair threads
      threadKey = msg.from === selectedParticipant.value ? msg.to : msg.from
    }
    if (!convos[threadKey]) {
      convos[threadKey] = []
    }
    convos[threadKey].push(msg)
  })
  
  // Sort messages in each conversation by timestamp
  Object.keys(convos).forEach(partnerId => {
    convos[partnerId].sort((a: Message, b: Message) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  })
  
  return convos
})

const totalMessagesForParticipant = computed(() => {
  if (!selectedParticipant.value) return 0
  return (Object.values(conversations.value) as Message[][]).reduce((sum: number, msgs: Message[]) => sum + msgs.length, 0)
})

const lastMessageTime = computed(() => {
  if (!selectedParticipant.value) return null
  
  let lastTime: Date | null = null
  
  const allConversations = Object.values(conversations.value) as Message[][]
  allConversations.forEach((messages: Message[] | null) => {
    if (messages) {
      messages.forEach((msg: Message) => {
        const msgTime = new Date(msg.timestamp)
        if (!lastTime || msgTime > lastTime) {
          lastTime = msgTime
        }
      })
    }
  })
  
  return lastTime
})

const threadLabel = (threadKey: string) => {
  if (props.communicationLevel === 'broadcast' && threadKey === 'all') {
    return `Broadcasts (All participants)`
  }
  return `${getDisplayName(selectedParticipant.value)} ↔ ${getDisplayName(threadKey)}`
}

const selectParticipant = (participantId: string) => {
  selectedParticipant.value = participantId
  
  // Scroll to bottom after messages are rendered
  nextTick(() => {
    const messagesContainer = document.querySelector('.conversation-messages')
    if (messagesContainer) {
      (messagesContainer as HTMLElement).scrollTop = (messagesContainer as HTMLElement).scrollHeight
    }
  })
}

const formatTime = (timestamp: Date) => {
  return new Date(timestamp).toLocaleTimeString()
}
</script>

<style scoped>
.conversation-interface {
  display: flex;
  height: 100%;
  overflow: hidden;
  flex: 1;
  /* When no sidebar (broadcast mode), main takes full width */
  width: 100%;
}

.participant-list-sidebar {
  flex: 0 0 120px;
  border-right: 1px solid #e9ecef;
  background: #f8f9fa;
  padding: 8px;
  overflow-y: auto;
  height: 100%;
}

.participant-list-sidebar h4 {
  margin: 0 0 8px 0;
  font-size: 11px;
  font-weight: 600;
  color: #495057;
}

.participant-list-vertical {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.participant-list-item {
  padding: 6px 8px;
  border: 1px solid #dee2e6;
  background: white;
  border-radius: 3px;
  font-size: 10px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.participant-list-item:hover {
  background: #e9ecef;
}

.participant-list-item.active {
  background: #007bff;
  color: white;
  border-color: #007bff;
}

.participant-list-item.has-messages {
  border-left: 3px solid #28a745;
}

.participant-list-item .participant-id {
  font-weight: 600;
  margin-bottom: 2px;
}

.participant-list-item .message-count {
  font-size: 9px;
  color: #6c757d;
}

.participant-list-item.active .message-count {
  color: rgba(255, 255, 255, 0.8);
}

.conversation-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  /* Full width when in broadcast mode (no sidebar) */
  width: 100%;
}

.conversation-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  flex: 1;
}

.conversation-header {
  padding: 8px;
  border-bottom: 1px solid #e9ecef;
  background: #f8f9fa;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mode-indicator {
  padding: 2px 6px;
  border-radius: 8px;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.mode-indicator.chat {
  background: #dbeafe;
  color: #1e40af;
}

.mode-indicator.broadcast {
  background: #fef3c7;
  color: #d97706;
}

.mode-indicator.no_chat {
  background: #f3f4f6;
  color: #374151;
}

.conversation-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px;
  background: white;
  min-height: 0;
  height: 0;
  scrollbar-width: thin;
  scrollbar-color: #ccc #f1f1f1;
}

.conversation-messages::-webkit-scrollbar {
  width: 6px;
}

.conversation-messages::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.conversation-messages::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

.conversation-messages::-webkit-scrollbar-thumb:hover {
  background: #999;
}

.conversation-section-header {
  font-weight: 600;
  font-size: 12px;
  margin: 12px 0 8px 0;
  padding: 4px 8px;
  background: #e9ecef;
  border-radius: 3px;
}

.conversation-message {
  margin-bottom: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 11px;
  line-height: 1.4;
  word-wrap: break-word;
  max-width: 100%;
}

.conversation-message.sent {
  background: #e3f2fd;
  margin-left: 20px;
  border-left: 3px solid #2196f3;
}

.conversation-message.received {
  background: #f1f8e9;
  margin-right: 20px;
  border-left: 3px solid #4caf50;
}

.message-meta {
  font-size: 9px;
  color: #6c757d;
  margin-bottom: 2px;
}

.message-content {
  color: #212529;
}

.no-conversation {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6c757d;
  font-size: 11px;
  text-align: center;
}

.conversation-stats {
  padding: 6px 8px;
  border-top: 1px solid #e9ecef;
  background: #f8f9fa;
  font-size: 10px;
  color: #6c757d;
  flex-shrink: 0;
}

/* New styles for broadcast mode */
.broadcast-mode {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.broadcast-info {
  padding: 8px;
  border-bottom: 1px solid #e9ecef;
  background: #f8f9fa;
  font-size: 11px;
  font-weight: 600;
  color: #495057;
  flex-shrink: 0;
}

.broadcast-info h4 {
  margin: 0 0 4px 0;
  font-size: 12px;
  color: #343a40;
}

.broadcast-info p {
  margin: 0;
  font-size: 10px;
  color: #6c757d;
}

.message-thread {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 8px;
  background: #f8f9fa;
  min-height: 0;
  height: 0;
  scrollbar-width: thin;
  scrollbar-color: #ccc #f1f1f1;
}

.message-thread::-webkit-scrollbar {
  width: 6px;
}

.message-thread::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.message-thread::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

.message-thread::-webkit-scrollbar-thumb:hover {
  background: #999;
}

.message-history {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 11px;
  line-height: 1.4;
  word-wrap: break-word;
  max-width: 100%;
}

.broadcast-message {
  background: #e3f2fd;
  /* margin-left: 20px; */
  border-left: 3px solid #2196f3;
}

.message-sender {
  font-weight: 600;
  font-size: 9px;
  color: #495057;
}

.message-content {
  flex: 1;
  color: #212529;
}

.message-time {
  font-size: 8px;
  color: #6c757d;
  margin-left: 8px;
}

.empty {
  text-align: center;
  color: #6c757d;
  font-size: 10px;
  padding: 10px 0;
}
</style> 