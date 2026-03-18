<script setup>
import { computed, watch } from 'vue'

const props = defineProps({
  commLevel: {
    type: String,
    default: 'chat'
  },
  conversations: {
    type: Object,
    default: () => ({})
  },
  selectedParticipant: {
    type: String,
    default: null
  },
  participants: {
    type: Object,
    default: () => ({})
  }
})

// Filter conversations to only those involving the selected participant (chat mode)
const filteredConversations = computed(() => {
  // If no participant is selected, show all conversations
  if (!props.selectedParticipant) {
    return props.conversations || {}
  }
  
  // Filter to only conversations involving the selected participant
  const out = {}
  const selectedId = String(props.selectedParticipant)
  
  for (const [threadKey, messages] of Object.entries(props.conversations || {})) {
    // threadKey is "from_to" or "group"
    if (threadKey === 'group') {
      // Group chat: include all messages
      out[threadKey] = messages
      continue
    }
    
    const [from, to] = String(threadKey).split('_')
    // Match by participant ID (normalize to string for comparison)
    if (String(from) === selectedId || String(to) === selectedId) {
      out[threadKey] = messages
    }
  }
  
  return out
})

// Get all messages from all conversations, sorted by timestamp
// For group chat, prioritize messages from 'group' key
const allMessages = computed(() => {
  const messages = []
  
  // For group chat, use messages from 'group' key if available
  if (isGroupChat.value) {
    if (props.conversations && props.conversations['group']) {
      const groupMessages = props.conversations['group']
      // Ensure it's an array
      if (Array.isArray(groupMessages)) {
        console.log('[ConversationFeed] Group chat: found', groupMessages.length, 'messages in group key')
        messages.push(...groupMessages)
      } else {
        console.warn('[ConversationFeed] Group chat: group key is not an array:', typeof groupMessages, groupMessages)
      }
    } else {
      console.log('[ConversationFeed] Group chat: no messages in group key, conversations:', props.conversations)
    }
  } else {
    // For private chat, get all messages from all conversations
    if (props.conversations) {
      Object.values(props.conversations).forEach(threadMessages => {
        if (Array.isArray(threadMessages)) {
          messages.push(...threadMessages)
        }
      })
    }
  }
  
  // Remove duplicates based on id or content + sender + timestamp
  const uniqueMessages = []
  const seen = new Set()
  messages.forEach(msg => {
    const key = msg.id || `${msg.content}_${msg.sender || msg.from}_${msg.timestamp}`
    if (!seen.has(key)) {
      seen.add(key)
      uniqueMessages.push(msg)
    }
  })
  
  const sorted = uniqueMessages.sort((a, b) => {
    const timeA = a.timestamp || (typeof a.timestamp === 'string' ? new Date(a.timestamp).getTime() : 0)
    const timeB = b.timestamp || (typeof b.timestamp === 'string' ? new Date(b.timestamp).getTime() : 0)
    return timeA - timeB
  })
  
  if (isGroupChat.value && sorted.length === 0) {
    console.log('[ConversationFeed] Group chat mode but no messages found. conversations:', props.conversations)
  }
  
  return sorted
})

const totalMessagesForParticipant = computed(() => {
  if (!props.selectedParticipant) return 0
  return Object.values(filteredConversations.value).reduce((total, messages) => total + (messages?.length || 0), 0)
})

const isGroupChat = computed(() => {
  const level = String(props.commLevel || '').trim()
  const levelLower = level.toLowerCase()
  const result = levelLower === 'groupchat' || 
         levelLower === 'group_chat' || 
         level === 'Group Chat' ||
         levelLower.includes('group')
  console.log('[ConversationFeed] commLevel:', level, 'isGroupChat:', result)
  return result
})

const getDisplayName = (id) => {
  return props.participants[id]?.name || id || 'Unknown'
}

const getParticipantType = (id) => {
  return props.participants[id]?.type || 'participant'
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

const threadLabel = (threadKey) => {
  const [from, to] = threadKey.split('_')
  return `${getDisplayName(from)} ↔ ${getDisplayName(to)}`
}

// Check if message is from the selected participant (in researcher view) or current user (in participant view)
const isMyMessage = (message) => {
  const messageSender = message.from || message.sender
  
  // If selectedParticipant is provided (researcher monitor view), check if message is from selected participant
  if (props.selectedParticipant) {
    return String(messageSender) === String(props.selectedParticipant)
  }
  
  // Otherwise, check if message is from current logged-in user (participant view)
  const currentUserId = sessionStorage.getItem('participant_id')
  if (!currentUserId) return false
  return String(messageSender) === String(currentUserId)
}

const formatAudioDuration = (seconds) => {
  if (seconds == null || seconds < 0) return '0"'
  return `${seconds}"`
}

const playAudio = (url) => {
  if (!url) return
  const fullUrl = url.startsWith('http') ? url : (window.location.origin + url)
  const audio = new Audio(fullUrl)
  audio.play().catch(e => console.error('[ConversationFeed] Audio play error:', e))
}
</script>

<template>
  <div class="conversation-main">
    <!-- No Chat Mode -->
    <div v-if="commLevel === 'no_chat'" class="no-conversation">
      <div>
        <p><strong>Messaging disabled</strong></p>
        <p>Conversations are unavailable in no-chat mode</p>
      </div>
    </div>
    
    <!-- Group Chat Mode -->
    <div v-else-if="isGroupChat" class="group-chat-mode">
      <div class="group-chat-info">
        <h4>📢 Public Message Pool</h4>
        <p>All participants can see messages posted here. No direct messaging allowed.</p>
      </div>
      
      <!-- Group Chat Message Thread -->
      <div class="message-thread">
        <div class="message-history" ref="messageHistory">
          <template v-for="(message, index) in allMessages" :key="`group-${message.id || index}-${message.timestamp}`">
            <div v-if="(message.message_type || 'text') === 'text'" class="message-item group-chat-message">
              <div class="message-sender">{{ getDisplayName(message.from || message.sender) }}</div>
              <div class="message-content">{{ message.content }}</div>
              <div class="message-time">{{ formatTime(message.timestamp) }}</div>
            </div>
                <div v-else-if="message.message_type === 'audio'" class="message-item group-chat-message audio-message-wrapper">
              <div class="message-sender">{{ getDisplayName(message.from || message.sender) }}</div>
              <div class="audio-message-bubbles">
                <div class="audio-player-bubble">
                  <button type="button" class="audio-play-btn" @click="playAudio(message.audio_url)" title="Click to play">
                    <span class="audio-icon"><i class="fa-regular fa-circle-play"></i></span>
                    <span class="audio-duration">{{ formatAudioDuration(message.duration) }}</span>
                  </button>
                </div>
                <div class="audio-transcription-bubble">
                  {{ message.content || '' }}
                </div>
              </div>
              <div class="message-time">{{ formatTime(message.timestamp) }}</div>
            </div>
          </template>
          <div v-if="!allMessages.length" class="empty">
            <p>No group chat messages yet</p>
            <p v-if="conversations" style="font-size: 11px; color: #9ca3af; margin-top: 8px;">
              Conversations object: {{ Object.keys(conversations).length }} keys
              <span v-if="conversations['group']">, group key has {{ conversations['group'].length }} messages</span>
            </p>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Chat Mode -->
    <template v-else>
      <div v-if="!selectedParticipant && Object.keys(conversations).length === 0" class="empty">
        <div >
          <p><strong>No participant selected</strong></p>
          <p>Click on a participant from the left to view their conversations</p>
        </div>
      </div>
      
      <div v-else class="conversation-content">
        <div v-if="!selectedParticipant" class="conversation-header">
          <span>
              All Conversations
          </span>
        </div>
        
        <div class="conversation-messages">
          <div v-if="Object.keys(filteredConversations).length === 0" class="no-conversation">
            <p v-if="selectedParticipant">No conversations yet for {{ getDisplayName(selectedParticipant) }}</p>
            <p v-else>No conversations yet</p>
          </div>
          
          <div v-for="(messages, threadKey) in filteredConversations" :key="threadKey" class="conversation-thread">
            <div class="thread-header">
              <strong>{{ threadLabel(threadKey) }}</strong> ({{ messages.length }} messages)
            </div>
            
            <div class="thread-messages">
              <template v-for="(message, index) in messages" :key="index">
                <div v-if="(message.message_type || 'text') === 'text'" 
                     :class="['message-item', isMyMessage(message) ? 'my-message' : 'other-message']">
                  <div class="message-sender">{{ getDisplayName(message.from || message.sender) }}</div>
                  <div class="message-content">{{ message.content }}</div>
                  <div class="message-time">{{ formatTime(message.timestamp) }}</div>
                </div>
                <div v-else-if="message.message_type === 'audio'" 
                     :class="['message-item', 'audio-message-wrapper', isMyMessage(message) ? 'my-message' : 'other-message']">
                  <div class="message-sender">{{ getDisplayName(message.from || message.sender) }}</div>
                  <div class="audio-message-bubbles">
                    <div class="audio-player-bubble">
                      <button type="button" class="audio-play-btn" @click="playAudio(message.audio_url)" title="Click to play">
                        <span class="audio-icon"><i class="fa-regular fa-circle-play"></i></span>
                        <span class="audio-duration">{{ formatAudioDuration(message.duration) }}</span>
                      </button>
                    </div>
                    <div class="audio-transcription-bubble">
                      {{ message.content || '' }}
                    </div>
                  </div>
                  <div class="message-time">{{ formatTime(message.timestamp) }}</div>
                </div>
              </template>
            </div>
          </div>
        </div>
        
        <div class="conversation-stats">
          Total: {{ totalMessagesForParticipant }} messages | 
          Active conversations: {{ Object.keys(filteredConversations).length }}
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.conversation-main {
  width: 100%;
  height: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.no-conversation {
  display: flex;
  height: 100%;
  text-align: center;
  color: #6b7280;
  padding: 40px;
}

.no-conversation p {
  margin: 8px 0;
}

.no-conversation strong {
  color: #374151;
  font-size: 16px;
}

.group-chat-mode {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.group-chat-info {
  padding: 16px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}

.group-chat-info h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #1f2937;
}

.group-chat-info p {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
}

.message-thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
}

.message-history {
  display: flex;
  flex-direction: column;
  gap: 12px;
}


.group-chat-message {
  background: #f9fafb;
  text-align: left;
}

.message-sender {
  color: #667eea;
  font-weight: 600;
  font-size: 11px;
  margin-bottom: 4px;
}

.my-message .message-sender {
  color: rgba(255, 255, 255, 0.9);
}

.message-content {
  font-size: 13px;
  color: #374151;
}

.my-message .message-content {
  color: white;
  text-align: left;
}

.message-time {
  font-size: 10px;
  color: #666;
  align-self: flex-end;
  opacity: 0.7;
  text-align: right;
}

.my-message .message-time {
  color: rgba(255, 255, 255, 0.7);
}

/* Audio message bubbles */
.audio-message-wrapper .audio-message-bubbles {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.audio-player-bubble {
  display: inline-flex;
  align-items: center;
  padding: 8px 14px;
  background: rgba(102, 126, 234, 0.15);
  border-radius: 12px;
  border: 1px solid rgba(102, 126, 234, 0.3);
}
.my-message .audio-player-bubble {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.4);
}
.audio-play-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  font-size: 13px;
  color: inherit;
}
.audio-icon {
  font-size: 18px;
}
.audio-duration {
  font-weight: 500;
  opacity: 0.9;
}
.audio-transcription-bubble {
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 8px;
  font-size: 13px;
  color: #374151;
  border: 1px solid #e5e7eb;
}
.audio-transcription-bubble .transcription-label {
  font-weight: 600;
  color: #6b7280;
  margin-right: 4px;
}
.my-message .audio-transcription-bubble {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.4);
  color: white;
}

.conversation-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.conversation-header {
  padding: 12px 16px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  font-size: 14px;
  color: #374151;
}

.mode-indicator {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  margin-left: 8px;
}

.mode-indicator.chat {
  background: #dbeafe;
  color: #1e40af;
}

.mode-indicator.groupChat,
.mode-indicator.group_chat {
  background: #fef3c7;
  color: #92400e;
}

.conversation-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.conversation-thread {
  padding: 12px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  /* Remove fixed height, let it grow naturally */
}

.thread-header {
  font-size: 13px;
  color: #374151;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.thread-messages {
  /* Remove fixed height and overflow, let parent handle scrolling */
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid #dee2e6;
  border-radius: 3px;
  background: #f8f9fa;
  /* Remove min-height: 0 to allow natural growth */
}

.message-item {
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 8px;
  max-width: 80%;
  word-wrap: break-word;
  border: 1px solid #e1e5e9;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  position: relative;
}

.other-message {
  background: #f8f9fa;
  color: #333;
  align-self: flex-start;
  margin-right: 20px;
  margin-left: 0;
  border-left: 4px solid #667eea;
  text-align: left;
}

.my-message {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  align-self: flex-end;
  margin-left: 20px;
  margin-right: 0;
  box-shadow: 0 2px 6px rgba(102, 126, 234, 0.3);
  text-align: right;
}

.conversation-stats {
  padding: 12px 16px;
  background: #f9fafb;
  border-top: 1px solid #e5e7eb;
  font-size: 12px;
  color: #6b7280;
  text-align: center;
}

.empty {
  text-align: center;
  padding: 40px 20px;
  color: #9ca3af;
  font-size: 14px;
}
</style>

