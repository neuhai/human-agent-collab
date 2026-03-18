<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import Panel from '../components/Panel.vue'
import TradeFeed from '../components/trade_feed.vue'
import TradeForm from '../components/TradeForm.vue'
import BaseComponent from '../components/BaseComponent.vue'
import MeetingRoom from '../components/MeetingRoom.vue'
import { sendMessage as wsSendMessage, onMessageReceived, offMessageReceived } from '../services/websocket.js'
import { captureActionContext } from '../composables/useActionCapture.js'

const props = defineProps({
    config: {
        type: Object,
        default: () => ({
            id: '',
            label: 'Social Panel',
            description: '',
            visible_if: 'true',
            bindings: [],
            tabs: ['trade', 'messages']
        })
    },
    // Trade data
    pendingOffers: {
        type: Array,
        default: () => []
    },
    completedTrades: {
        type: Array,
        default: () => []
    },
    // Conversation data
    commLevel: {
        type: String,
        default: 'chat'
    },
    conversations: {
        type: Object,
        default: () => ({})
    },
    // Optional external selection (if parent wants to control it)
    selectedParticipant: { type: String, default: null },
    // Max word count for messages (when message length limit is enabled). Null = no limit.
    messageLengthLimit: { type: Number, default: null },
    // Communication media: array of 'text' | 'audio' | 'meeting_room'. Default ['text'].
    communicationMedia: {
        type: Array,
        default: () => ['text']
    },
    // Map of participants for feeds (id -> participant object), as expected by trade_feed / conversation_feed
    participants: {
        type: Object,
        default: () => ({})
    },
    // Array of participant objects for rendering the participant list
    participantsList: {
        type: Array,
        default: () => []
    }
})

const emit = defineEmits(['selectParticipant', 'update:selectedParticipant', 'submitTrade', 'offer-updated'])

const isVisible = computed(() => {
    return props.config.visible_if === 'true' || props.config.visible_if === true
})

// Get tabs from config, default to ['trade', 'messages']
// Filter out 'messages' tab if communication level is 'no_chat'
const tabs = computed(() => {
    const configTabs = props.config.tabs || ['trade', 'messages']
    const isNoChat = props.commLevel === 'no_chat' || props.commLevel === 'noChat'
    
    // If no_chat, remove messages tab
    const filteredTabs = isNoChat 
        ? configTabs.filter(tab => {
            const tabId = typeof tab === 'string' ? tab : tab.id
            return tabId !== 'messages'
          })
        : configTabs
    
    return filteredTabs.map(tab => {
        if (typeof tab === 'string') {
            return { id: tab, label: tab.charAt(0).toUpperCase() + tab.slice(1) }
        }
        return tab
    })
})

// Initialize activeTab: if trade tab exists, default to trade, otherwise default to messages
const getDefaultTab = () => {
    const tabIds = tabs.value.map(t => t.id)
    if (tabIds.includes('trade')) {
        return 'trade'
    } else if (tabIds.includes('messages')) {
        return 'messages'
    }
    return tabs.value[0]?.id || 'trade'
}

const activeTab = ref(getDefaultTab())

const setActiveTab = (tabId) => {
    activeTab.value = tabId
}

// Watch tabs changes and adjust activeTab if current tab is removed
watch(tabs, (newTabs) => {
    const tabIds = newTabs.map(t => t.id)
    if (!tabIds.includes(activeTab.value)) {
        // Current tab was removed (e.g., messages tab when commLevel becomes no_chat)
        activeTab.value = getDefaultTab()
    }
}, { immediate: false })

// ---- Participant list (real-time from participant.vue allParticipants) ----
const myParticipantId = computed(() => sessionStorage.getItem('participant_id'))
const sessionId = computed(() => {
    // Try to get session_id from sessionStorage
    const stored = sessionStorage.getItem('session_id')
    if (stored) return stored
    // Fallback: try to get from session object
    try {
        const sessionStr = sessionStorage.getItem('session')
        if (sessionStr) {
            const session = JSON.parse(sessionStr)
            return session.session_id || session.id
        }
    } catch (e) {
        // Ignore parse errors
    }
    return null
})

const otherParticipants = computed(() => {
    if (!Array.isArray(props.participantsList)) return []
    return props.participantsList.filter(p => {
        const pId = p?.id || p?.participant_id
        return pId && pId !== myParticipantId.value
    })
})

// Helper function to get participant name by ID
const getParticipantName = (participantId) => {
    if (!participantId) return 'Unknown'
    // Try to find in participantsList
    const participant = props.participantsList.find(p => 
        (p?.id || p?.participant_id) === participantId
    )
    if (participant) {
        return participant.name || participant.id || participant.participant_id || participantId
    }
    // Fallback to ID
    return participantId
}

// Convert participantsList to map for easier lookup
const participantsMap = computed(() => {
    const map = {}
    props.participantsList.forEach(p => {
        const id = p?.id || p?.participant_id
        if (id) {
            map[id] = p
        }
    })
    return map
})

// Get current user's participant data
const myParticipantData = computed(() => {
    const myId = myParticipantId.value
    if (!myId) return null
    return props.participantsList.find(p => {
        const pId = p?.id || p?.participant_id
        return pId === myId
    }) || null
})

// Handle trade form submission
const handleTradeSubmit = async (data) => {
    console.log('[SocialPanel] Trade form submitted:', data)
    emit('submitTrade', data)
    
    // Also send to backend if needed
    const sId = sessionId.value
    const participantId = myParticipantId.value
    
    if (sId && participantId && data.action === 'submit_trade') {
        try {
            // Find participant ID from name if needed
            let toParticipantId = selectedParticipantId.value
            if (!toParticipantId && data.values.participant_name) {
                // Try to find participant by name
                const participant = props.participantsList.find(p => 
                    (p?.name || p?.id || p?.participant_id) === data.values.participant_name
                )
                if (participant) {
                    toParticipantId = participant.id || participant.participant_id
                }
            }
            
            if (!toParticipantId) {
                alert('Please select a participant first')
                return
            }
            
            const encodedSessionId = encodeURIComponent(sId)
            const url = `/api/sessions/${encodedSessionId}/participants/${participantId}/submit_trade`
            
            // Build trade request - support flexible item structure
            const tradeRequest = {
                trade_action: data.values.trade_action,
                to_participant: toParticipantId,
                trade_price: parseFloat(data.values.trade_price) || 20,
                quantity: parseInt(data.values.quantity) || 1
            }
            
            // Add item data if present (supports both shape_type and trade_item)
            if (data.values.shape_type) {
                tradeRequest.trade_item = data.values.shape_type
                tradeRequest.item_type = 'shape'
                tradeRequest.shape = data.values.shape_type  // Backward compatibility
            } else if (data.values.trade_item) {
                tradeRequest.trade_item = data.values.trade_item
                tradeRequest.item_type = data.values.item_type || 'shape'
            } else {
                // Price-only trade
                tradeRequest.item_type = 'price_only'
            }
            
            const ctx = await captureActionContext()
            Object.assign(tradeRequest, ctx)
            
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(tradeRequest)
            })
            
            const result = await response.json()
            if (result.success) {
                console.log('[SocialPanel] Trade submitted successfully')
                // Refresh trade data
                handleOfferUpdated()
            } else {
                console.error('[SocialPanel] Trade submission failed:', result.error)
                alert(result.error || 'Failed to submit trade')
            }
        } catch (error) {
            console.error('[SocialPanel] Error submitting trade:', error)
            alert('Error submitting trade')
        }
    }
}

// Handle offer update (refresh trade data)
const handleOfferUpdated = () => {
    emit('offer-updated')
}

const selectedParticipantInternal = ref(null)
const selectedParticipantId = computed(() => props.selectedParticipant || selectedParticipantInternal.value)

// ---- Chat box state (matches setup.vue look & feel) ----
const newMessage = ref('')
const localConversations = ref({})

// Communication media helpers
const hasTextMedia = computed(() => (props.communicationMedia || ['text']).includes('text'))
const hasAudioMedia = computed(() => (props.communicationMedia || []).includes('audio'))
const hasMeetingRoomMedia = computed(() => (props.communicationMedia || []).includes('meeting_room'))

// Voice recording for audio media
const isRecording = ref(false)
const mediaRecorder = ref(null)
const audioChunks = ref([])
const isTranscribing = ref(false)
const showMeetingRoom = ref(false)
const chatUnfolded = ref(false)  // When meeting room enabled: false = chat folded, meeting full; true = chat 1/3, meeting 2/3
const recordStartTime = ref(0)

const toggleVoiceRecording = async () => {
    if (!hasAudioMedia.value) return
    if (isTranscribing.value) return

    if (isRecording.value) {
        // Stop recording and send
        if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
            mediaRecorder.value.stop()
        }
        return
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const recorder = new MediaRecorder(stream)
        audioChunks.value = []
        recordStartTime.value = Date.now()

        recorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.value.push(e.data)
        }
        recorder.onstop = async () => {
            isRecording.value = false
            mediaRecorder.value = null
            stream.getTracks().forEach(t => t.stop())
            if (audioChunks.value.length === 0) return
            isTranscribing.value = true
            try {
                const blob = new Blob(audioChunks.value, { type: 'audio/webm' })
                const durationSec = Math.round((Date.now() - recordStartTime.value) / 1000)

                const parseJsonOrThrow = async (res, label) => {
                    const text = await res.text()
                    if (res.headers.get('content-type')?.includes('application/json')) {
                        return JSON.parse(text)
                    }
                    if (text.trim().toLowerCase().startsWith('<!')) {
                        throw new Error(`${label} returned HTML instead of JSON (status ${res.status}). Is the backend running on port 5000?`)
                    }
                    throw new Error(`${label} failed: ${res.status} ${text.slice(0, 100)}`)
                }

                // 1. Upload audio
                const uploadForm = new FormData()
                uploadForm.append('audio', blob, 'recording.webm')
                const uploadRes = await fetch('/api/upload_audio', { method: 'POST', body: uploadForm })
                const uploadData = await parseJsonOrThrow(uploadRes, 'Upload')
                if (!uploadData.success || !uploadData.url) {
                    throw new Error(uploadData.error || 'Upload failed')
                }
                // 2. Transcribe
                const transcribeForm = new FormData()
                transcribeForm.append('audio', blob, 'recording.webm')
                const transcribeRes = await fetch('/api/transcribe', { method: 'POST', body: transcribeForm })
                const transcribeData = await parseJsonOrThrow(transcribeRes, 'Transcribe')
                const transcription = transcribeData.success && transcribeData.text ? transcribeData.text.trim() : ''
                // 3. Send audio message
                await sendAudioMessage(uploadData.url, durationSec, transcription)
            } catch (err) {
                console.error('[SocialPanel] Audio send error:', err)
                alert(err.message || 'Failed to send audio. Please try again.')
            } finally {
                isTranscribing.value = false
            }
        }
        recorder.start()
        mediaRecorder.value = recorder
        isRecording.value = true
    } catch (err) {
        console.error('[SocialPanel] Microphone access error:', err)
        alert('Microphone access denied. Please allow microphone access.')
    }
}


watch(
    () => props.conversations,
    (val) => {
        // Keep a local copy so sending can optimistically append messages without mutating props
        localConversations.value = val && typeof val === 'object' ? { ...val } : {}
    },
    { immediate: true, deep: false }
)

const formatMessageTime = (timestamp) => {
    if (!timestamp) return ''
    const d = typeof timestamp === 'number' ? new Date(timestamp) : new Date(timestamp)
    if (Number.isNaN(d.getTime())) return String(timestamp)
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

const formatAudioDuration = (seconds) => {
    if (seconds == null || seconds < 0) return '0"'
    return `${seconds}"`
}

const playAudio = (url) => {
    if (!url) return
    const fullUrl = url.startsWith('http') ? url : (window.location.origin + url)
    const audio = new Audio(fullUrl)
    audio.play().catch(e => console.error('[SocialPanel] Audio play error:', e))
}

const messagesForSelected = computed(() => {
    const myId = myParticipantId.value
    const otherId = selectedParticipantId.value
    const conv = localConversations.value || {}
    const all = []

    // Group chat: show all messages in one pool
    const isGroupChat = props.commLevel === 'groupChat' || props.commLevel === 'group_chat'
    if (isGroupChat) {
        for (const msgs of Object.values(conv)) {
            if (Array.isArray(msgs)) all.push(...msgs)
        }
        return all.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0))
    }

    // Private chat: show only messages between me and selected participant
    if (!myId || !otherId) return []

    for (const msgs of Object.values(conv)) {
        if (!Array.isArray(msgs)) continue
        for (const m of msgs) {
            const from = m?.from || m?.sender
            const to = m?.to || m?.receiver
            const isPair =
                (from === myId && to === otherId) ||
                (from === otherId && to === myId)
            if (isPair) all.push(m)
        }
    }

    return all.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0))
})

const sendAudioMessage = async (audioUrl, duration, content) => {
    const myId = myParticipantId.value
    const otherId = selectedParticipantId.value
    const sId = sessionId.value
    const isGroupChat = props.commLevel === 'groupChat' || props.commLevel === 'group_chat'
    if (!myId || (!otherId && !isGroupChat)) return
    const receiverForMessage = isGroupChat ? null : (otherId || null)

    const optimisticId = `temp_${Date.now()}_${Math.random()}`
    const msg = {
        id: optimisticId,
        from: myId,
        to: receiverForMessage,
        sender: myId,
        receiver: receiverForMessage,
        content: content || '',
        message_type: 'audio',
        audio_url: audioUrl,
        duration,
        timestamp: Date.now(),
        _isOptimistic: true
    }
    appendMessageToLocal(msg, isGroupChat, myId, otherId)

    if (sId) {
        try {
            const ctx = await captureActionContext()
            await wsSendMessage(sId, myId, receiverForMessage, content || '', {
                messageType: 'audio',
                audioUrl,
                duration,
                ...ctx
            })
            console.log('[SocialPanel] Audio message sent via WebSocket')
        } catch (error) {
            console.error('[SocialPanel] Error sending audio message:', error)
        }
    }
}

const appendMessageToLocal = (msg, isGroupChat, myId, otherId) => {
    if (isGroupChat) {
        const key = 'group'
        const existing = localConversations.value[key] || []
        localConversations.value = { ...localConversations.value, [key]: [...existing, msg] }
    } else {
        const key = `${myId}_${otherId}`
        const existing = localConversations.value[key] || []
        localConversations.value = { ...localConversations.value, [key]: [...existing, msg] }
    }
}

const sendMessage = async () => {
    const myId = myParticipantId.value
    const otherId = selectedParticipantId.value
    let sId = sessionId.value
    
    const isGroupChat = props.commLevel === 'groupChat' || props.commLevel === 'group_chat'
    if (!myId || (!otherId && !isGroupChat)) return

    const content = (newMessage.value || '').trim()
    if (!content) return

    if (props.messageLengthLimit != null && props.messageLengthLimit > 0) {
        const wordCount = content.split(/\s+/).filter(Boolean).length
        if (wordCount > props.messageLengthLimit) {
            alert(`Message exceeds the maximum length of ${props.messageLengthLimit} words. Your message has ${wordCount} words. Please shorten it.`)
            return
        }
    }
    
    const receiverForMessage = isGroupChat ? null : (otherId || null)
    const optimisticId = `temp_${Date.now()}_${Math.random()}`
    const msg = {
        id: optimisticId,
        from: myId,
        to: receiverForMessage,
        sender: myId,
        receiver: receiverForMessage,
        content,
        message_type: 'text',
        timestamp: Date.now(),
        _isOptimistic: true
    }
    appendMessageToLocal(msg, isGroupChat, myId, otherId)
    newMessage.value = ''

    if (sId) {
        try {
            const ctx = await captureActionContext()
            await wsSendMessage(sId, myId, receiverForMessage, content, ctx)
            console.log('[SocialPanel] Message sent successfully via WebSocket')
        } catch (error) {
            console.error('[SocialPanel] Error sending message via WebSocket:', error)
        }
    } else {
        console.warn('[SocialPanel] Cannot send message: session_id not found')
    }
}

const selectParticipant = (participant, isAutoSelect = false) => {
    const id = participant?.id || participant?.participant_id
    if (!id) return

    selectedParticipantInternal.value = id
    emit('selectParticipant', id)
    emit('update:selectedParticipant', id)

    // Only change tab when user manually clicks a participant (not during auto-select)
    if (!isAutoSelect) {
        // If user clicks a participant, default to messages tab (if present)
        const hasMessagesTab = tabs.value.some(t => t.id === 'messages')
        if (hasMessagesTab) {
            activeTab.value = 'messages'
        }
    }
}

// Handle incoming messages from WebSocket
const handleMessageReceived = (message) => {
    console.log('[SocialPanel] Received message:', message)
    
    const myId = myParticipantId.value
    const sender = message.sender
    const receiver = message.receiver
    const isGroupChat = props.commLevel === 'groupChat' || props.commLevel === 'group_chat'
    
    // Convert backend message format to frontend format
    const msg = {
        id: message.id || `msg_${Date.now()}`,
        from: sender,
        to: receiver,
        sender: sender,
        receiver: receiver,
        content: message.content,
        message_type: message.message_type || 'text',
        audio_url: message.audio_url,
        duration: message.duration || 0,
        timestamp: message.timestamp ? new Date(message.timestamp).getTime() : Date.now()
    }
    
    // Update local conversations
    if (isGroupChat) {
        // Group chat: add to group key
        const key = 'group'
        const existing = localConversations.value[key] || []
        
        // Check for duplicates: match by content + sender + receiver + timestamp (within 5 seconds)
        const exists = existing.some(m => {
            // If same id, definitely duplicate
            if (m.id === msg.id) return true
            // If same content, sender, receiver, and timestamp within 5 seconds, it's a duplicate
            const timeDiff = Math.abs((m.timestamp || 0) - (msg.timestamp || 0))
            return m.content === msg.content && 
                   (m.sender || m.from) === sender && 
                   (m.receiver || m.to) === receiver &&
                   timeDiff < 5000
        })
        
        if (!exists) {
            // Replace optimistic message if exists (same content, sender, receiver, recent timestamp)
            const optimisticIndex = existing.findIndex(m => 
                m._isOptimistic && 
                m.content === msg.content && 
                (m.sender || m.from) === sender && 
                (m.receiver || m.to) === receiver &&
                Math.abs((m.timestamp || 0) - (msg.timestamp || 0)) < 5000
            )
            
            if (optimisticIndex >= 0) {
                // Replace optimistic message with real one
                const updated = [...existing]
                updated[optimisticIndex] = msg
                localConversations.value = {
                    ...localConversations.value,
                    [key]: updated
                }
            } else {
                // Add new message
                localConversations.value = {
                    ...localConversations.value,
                    [key]: [...existing, msg]
                }
            }
        }
    } else {
        // Private chat: add to the appropriate conversation thread
        // Determine the conversation key (sender_receiver or receiver_sender)
        const key1 = `${sender}_${receiver}`
        const key2 = `${receiver}_${sender}`
        const key = localConversations.value[key1] ? key1 : (localConversations.value[key2] ? key2 : key1)
        
        const existing = localConversations.value[key] || []
        
        // Check for duplicates: match by content + sender + receiver + timestamp (within 5 seconds)
        const exists = existing.some(m => {
            // If same id, definitely duplicate
            if (m.id === msg.id) return true
            // If same content, sender, receiver, and timestamp within 5 seconds, it's a duplicate
            const timeDiff = Math.abs((m.timestamp || 0) - (msg.timestamp || 0))
            return m.content === msg.content && 
                   (m.sender || m.from) === sender && 
                   (m.receiver || m.to) === receiver &&
                   timeDiff < 5000
        })
        
        if (!exists) {
            // Replace optimistic message if exists (same content, sender, receiver, recent timestamp)
            const optimisticIndex = existing.findIndex(m => 
                m._isOptimistic && 
                m.content === msg.content && 
                (m.sender || m.from) === sender && 
                (m.receiver || m.to) === receiver &&
                Math.abs((m.timestamp || 0) - (msg.timestamp || 0)) < 5000
            )
            
            if (optimisticIndex >= 0) {
                // Replace optimistic message with real one
                const updated = [...existing]
                updated[optimisticIndex] = msg
                localConversations.value = {
                    ...localConversations.value,
                    [key]: updated
                }
            } else {
                // Add new message
                localConversations.value = {
                    ...localConversations.value,
                    [key]: [...existing, msg]
                }
            }
        }
    }
}

// Auto-select first participant when participants list becomes available
watch(otherParticipants, (newParticipants) => {
    // Only auto-select if:
    // 1. Social panel is visible
    // 2. There are other participants
    // 3. No participant is currently selected
    if (isVisible.value && newParticipants.length > 0 && !selectedParticipantId.value) {
        const firstParticipant = newParticipants[0]
        selectParticipant(firstParticipant, true) // true = isAutoSelect
        console.log('[SocialPanel] Auto-selected first participant:', firstParticipant?.id || firstParticipant?.participant_id)
    }
}, { immediate: true })

// Register WebSocket message listener on mount
let cleanupMessageListener = null
onMounted(() => {
    cleanupMessageListener = onMessageReceived(handleMessageReceived)
    
    // Auto-select first participant on mount if available
    if (isVisible.value && otherParticipants.value.length > 0 && !selectedParticipantId.value) {
        const firstParticipant = otherParticipants.value[0]
        selectParticipant(firstParticipant, true) // true = isAutoSelect
        console.log('[SocialPanel] Auto-selected first participant on mount:', firstParticipant?.id || firstParticipant?.participant_id)
    }
})

onUnmounted(() => {
    if (cleanupMessageListener) {
        cleanupMessageListener()
    }
})
</script>

<template>
    <Panel v-if="isVisible" :header="'Participants'" :description="config.description || 'View and interact with other participants.'" class="participant-list">
        <div class="participants-list">
            <div
                v-for="p in otherParticipants"
                :key="p?.id || p?.participant_id"
                :class="['participant-item', { selected: (p?.id || p?.participant_id) === selectedParticipantId }]"
                @click="selectParticipant(p)"
            >
                <div class="participant-info">
                    <div class="participant-name">{{ p?.name || (p?.id || p?.participant_id) }}</div>
                </div>
            </div>

            <div v-if="otherParticipants.length === 0" class="empty">
                No other participants
            </div>
        </div>
    </Panel>
    <div class="interaction-box">
        <div class="tab-header">
            <button
                v-for="tab in tabs"
                :key="tab.id"
                :class="['tab-button', { active: activeTab === tab.id }]"
                @click="setActiveTab(tab.id)"
            >
                {{ tab.label }}
            </button>
        </div>
        <div class="tab-content">
            <!-- Trade Tab: Render based on config -->
            <div v-if="activeTab === 'trade'" class="trade-tab-content">
                <template v-if="config.trade_panel && config.trade_panel.bindings">
                    <div
                        v-for="(binding, index) in config.trade_panel.bindings"
                        :key="index"
                        class="trade-binding-item"
                    >
                        <!-- Trade Form -->
                        <TradeForm
                            v-if="binding.control === 'trade_form'"
                            :config="binding"
                            :selected-participant="selectedParticipantId"
                            :participants="participantsMap"
                            :my-participant="myParticipantData"
                            @submit="handleTradeSubmit"
                        />
                        <!-- Trade Offers List -->
                        <div
                            v-else-if="binding.control === 'trade_offers_list'"
                            class="trade-list-container"
                        >
                            <TradeFeed
                                :pending-offers="pendingOffers"
                                :completed-trades="[]"
                                :participants="participants"
                                :selected-participant="selectedParticipantId"
                                :my-participant-id="myParticipantId"
                                :session-identifier="sessionId"
                                :is-session-active="true"
                                :show-pending-offers="true"
                                :show-trade-history="false"
                                @offer-updated="handleOfferUpdated"
                            />
                        </div>
                        <!-- Trade History List -->
                        <div
                            v-else-if="binding.control === 'trade_history_list'"
                            class="trade-list-container"
                        >
                            <TradeFeed
                                :pending-offers="[]"
                                :completed-trades="completedTrades"
                                :participants="participants"
                                :selected-participant="selectedParticipantId"
                                :my-participant-id="myParticipantId"
                                :session-identifier="sessionId"
                                :is-session-active="true"
                                :show-pending-offers="false"
                                :show-trade-history="true"
                                @offer-updated="handleOfferUpdated"
                            />
                        </div>
                        <!-- Generic binding (fallback) -->
                        <BaseComponent
                            v-else
                            :title="binding.label"
                            :binding="binding"
                        />
                    </div>
                </template>
                <!-- Fallback to old TradeFeed if no config -->
                <TradeFeed
                    v-else
                    :pending-offers="pendingOffers"
                    :completed-trades="completedTrades"
                    :participants="participants"
                    :selected-participant="selectedParticipantId"
                    :my-participant-id="myParticipantId"
                    :session-identifier="sessionId"
                    :is-session-active="true"
                    @offer-updated="handleOfferUpdated"
                />
            </div>
            <!-- Messages tab: render chat box UI (match setup.vue styles) -->
            <div v-else class="tab-content" data-tab="message">
                <div v-if="commLevel === 'no_chat'" class="empty">
                    Messaging disabled
                </div>

                <div
                    v-else-if="!selectedParticipantId && !(commLevel === 'groupChat' || commLevel === 'group_chat')"
                    class="empty"
                >
                    No participant selected
                </div>

                <div v-else :class="['chat-mode', { 'meeting-room-layout': hasMeetingRoomMedia }]">
                    <!-- When meeting room: collapsible chat. Default = meeting full, click to unfold chat -->
                    <div v-if="hasMeetingRoomMedia" class="chat-toggle-bar">
                        <button type="button" class="chat-toggle-btn" :class="{ active: chatUnfolded }" @click="chatUnfolded = !chatUnfolded">
                            {{ chatUnfolded ? '▼ Collapse Chat' : '▲ Open Chat' }}
                        </button>
                    </div>
                    <div v-if="!hasMeetingRoomMedia || chatUnfolded" class="chat-section" :class="{ 'chat-one-third': hasMeetingRoomMedia && chatUnfolded }">
                    <div class="message-history">
                        <template v-for="message in messagesForSelected" :key="message.id">
                            <!-- Text message -->
                            <div
                                v-if="(message.message_type || 'text') === 'text'"
                                class="message-item"
                                :class="{
                                    'my-message': (message.sender || message.from) === myParticipantId,
                                    'other-message': (message.sender || message.from) !== myParticipantId
                                }"
                            >
                                <div class="message-sender">{{ getParticipantName(message.sender || message.from) }}</div>
                                <div class="message-content">{{ message.content }}</div>
                                <div class="message-time">{{ formatMessageTime(message.timestamp) }}</div>
                            </div>
                            <!-- Audio message: voice player + transcription -->
                            <div
                                v-else-if="message.message_type === 'audio'"
                                class="message-item audio-message-wrapper"
                                :class="{
                                    'my-message': (message.sender || message.from) === myParticipantId,
                                    'other-message': (message.sender || message.from) !== myParticipantId
                                }"
                            >
                                <div class="message-sender">{{ getParticipantName(message.sender || message.from) }}</div>
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
                                <div class="message-time">{{ formatMessageTime(message.timestamp) }}</div>
                            </div>
                        </template>

                        <div v-if="!messagesForSelected.length" class="empty">
                            No messages yet
                        </div>
                    </div>

                    <div class="message-input-area">
                        <input
                            v-if="hasTextMedia"
                            v-model="newMessage"
                            @keyup.enter="sendMessage"
                            placeholder="Type your message..."
                            class="message-input"
                        />
                        <button
                            v-if="hasAudioMedia"
                            type="button"
                            :class="['voice-btn', { recording: isRecording, transcribing: isTranscribing }]"
                            :title="isRecording ? 'Click to stop and send' : 'Click to start voice input'"
                            @click="toggleVoiceRecording"
                        >
                            <template v-if="isTranscribing">...</template>
                            <template v-else-if="isRecording">⏹</template>
                            <template v-else><i class="fa-solid fa-microphone"></i></template>
                        </button>
                        <button @click="sendMessage" class="send-btn">Send</button>
                    </div>
                    </div>
                    <div v-if="hasMeetingRoomMedia" class="meeting-section" :class="{ 'meeting-two-thirds': chatUnfolded }">
                        <MeetingRoom
                            :session-id="sessionId"
                            :participant-id="myParticipantId"
                            :participants-list="participantsList"
                        />
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.interaction-box {
    width: 100%;
    background-color: #ffffff;
    display: flex;
    flex-direction: column;
    flex: 2;
    height: 100%;
    min-height: 0;
    overflow: hidden;
    border-radius: 10px;
    border: 1px solid #e5e7eb;
    margin-bottom: 0;
}

.tab-header {
    display: flex;
    border-bottom: 2px solid #e5e7eb;
    background: #f9fafb;
}

.tab-button {
    flex: 1;
    padding: 9px 12px 8px 12px;
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 14px;
    font-weight: 400;
    color: #6b7280;
    transition: all 0.2s ease;
    border-bottom: 3px solid transparent;
}

.tab-button:hover {
    color: #374151;
    background: #f3f4f6;
}

.tab-button.active {
    color: #1f2937;
    border-bottom-color: #5caff7;
    background: #ffffff;
}

.tab-content {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-height: 0;
}

/* ----- Chat box styles (copied to match setup.vue) ----- */
.chat-mode,
.group-chat-mode {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* Meeting room layout: collapsible chat */
.chat-mode.meeting-room-layout {
  flex-direction: column;
  gap: 0;
}
.chat-toggle-bar {
  flex-shrink: 0;
  padding: 6px 12px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}
.chat-toggle-btn {
  padding: 4px 10px;
  font-size: 12px;
  background: #e5e7eb;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  cursor: pointer;
  color: #374151;
}
.chat-toggle-btn:hover {
  background: #d1d5db;
}
.chat-toggle-btn.active {
  background: #667eea;
  border-color: #667eea;
  color: white;
}
.chat-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.chat-section.chat-one-third {
  flex: 0 0 50%;
  min-height: 120px;
}
.meeting-section {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.meeting-section.meeting-two-thirds {
  flex: 0 0 50%;
  min-height: 200px;
}

.message-thread {
  max-height: 200px;
  overflow-y: auto;
}

.message-history {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 8px 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    border: 1px solid #dee2e6;
    border-radius: 3px;
    background: #f8f9fa;
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

.message-sender {
  color: #667eea;
  font-weight: 600;
  font-size: 11px;
  margin-bottom: 4px;
}

.message-content {
  font-size: 13px;
  color: #374151;
}

.my-message .message-sender {
  color: rgba(255, 255, 255, 0.9);
}

.my-message .message-content {
  color: white;
  text-align: left;
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

.my-message .message-time {
  color: rgba(255, 255, 255, 0.9);
}

.message-time {
  font-size: 10px;
  color: #666;
  align-self: flex-end;
  opacity: 0.7;
  text-align: right;
}

.message-input-area {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.message-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 13px;
}

.send-btn {
  background: #667eea;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.voice-btn {
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.voice-btn:hover {
  background: #e5e7eb;
}
.voice-btn.recording {
  background: #fef2f2;
  border-color: #ef4444;
  animation: pulse-recording 1.5s infinite;
}
.voice-btn.transcribing {
  opacity: 0.7;
  cursor: wait;
}
@keyframes pulse-recording {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.meeting-btn {
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.meeting-btn:hover {
  background: #e5e7eb;
}
.meeting-btn.active {
  background: #dbeafe;
  border-color: #3b82f6;
}

.participant-list {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
}

.participant-list :deep(.panel-container) {
    height: 100%;
    margin-bottom: 0;
}

.participants-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.participant-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    background: #ffffff;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease;
}

.participant-item:hover {
    background: #f9fafb;
}

.participant-item.selected {
    border-color: #5caff7;
    background: #eff6ff;
}

.participant-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.participant-name {
    font-size: 12px;
    font-weight: 600;
    color: #374151;
}

.status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 2px solid #ffffff;
    box-shadow: 0 0 0 1px #e5e7eb;
}

.status-indicator.online {
    background: #22c55e;
}

.status-indicator.offline {
    background: #ef4444;
}

.empty {
    padding: 6px 0;
    text-align: center;
    color: #6b7280;
    font-size: 12px;
}

.trade-tab-content {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 12px;
    overflow-y: auto;
    height: 100%;
}

.trade-binding-item {
    display: flex;
    flex-direction: column;
}

.trade-list-container {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.trade-list-title {
    font-size: 14px;
    font-weight: 600;
    color: #374151;
    margin: 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #e5e7eb;
}
</style>