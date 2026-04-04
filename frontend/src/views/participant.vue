<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { initWebSocket, getSocket, joinSession, onParticipantsUpdate, onMessageReceived, offMessageReceived } from '../services/websocket.js'
import InfoDashboard from '../components/info_dashboard.vue'
import SocialPanel from '../components/social_panel.vue'
import myStatus from '../components/my_status.vue'
import myActions from '../components/my_action.vue'
import myTasks from '../components/my_task.vue'
import DocPreview from '../components/doc_preview.vue'
import ActionDialog from '../components/ActionDialog.vue'
import AnnotationPopup from '../components/AnnotationPopup.vue'
import { captureActionContext } from '../composables/useActionCapture.js'


defineProps({
  msg: String,
})

const router = useRouter()

// Header placeholders (this file previously referenced undefined vars)
const sessionId = ref(sessionStorage.getItem('session_id') || '')
const sessionName = ref(sessionStorage.getItem('session_code') || sessionStorage.getItem('session_name') || '')
const timerDisplay = ref('--:--')
const sessionStatus = ref('waiting')
const sessionStatusMessage = ref('Waiting')

// Tooltip state
const activeTooltip = ref(null)
const tooltipPosition = ref({ x: 0, y: 0 })

const tooltipContent = {
  rules: 'View the experiment rules and instructions.',
  sessionStatus: 'Current status of the experiment session: Waiting, Running, or Paused.',
  role: 'Your assigned role in this session (e.g. Guider or Follower in the Map Task).',
}

const showTooltip = (tooltipId, event) => {
  activeTooltip.value = tooltipId
  tooltipPosition.value = { x: event.clientX + 10, y: event.clientY + 10 }
}

const hideTooltip = () => {
  activeTooltip.value = null
}

const updateTooltipPosition = (event) => {
  tooltipPosition.value = { x: event.clientX + 10, y: event.clientY + 10 }
}

const showRulesPopup = () => {}

const logout = () => {
  sessionStorage.removeItem('auth_token')
  sessionStorage.removeItem('participant_id')
  sessionStorage.removeItem('session_code')
  sessionStorage.removeItem('session_id')
  sessionStorage.removeItem('participant_interface')
  sessionStorage.removeItem('participant_role')
  router.push('/login')
}

// Navigate to post-session annotation if enabled (called when session ends)
const navigateToPostAnnotationIfNeeded = async () => {
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    const pid = sessionStorage.getItem('participant_id')
    if (!sessionIdentifier || !pid) return
    const encoded = encodeURIComponent(sessionIdentifier)
    const res = await fetch(`/api/sessions/${encoded}`, { headers: { 'Content-Type': 'application/json' } })
    if (!res.ok) return
    const session = await res.json()
    const ann = session.experiment_config?.annotation
    const enabled = ann === true || (ann && ann.enabled)
    if (enabled) {
      router.push({
        path: '/post-annotation',
        query: { session_id: session.session_id || sessionIdentifier, participant_id: pid }
      })
    }
  } catch (e) {
    console.error('[Participant] Error checking post-annotation:', e)
  }
}

const getFirstPanel = (ui, groupName) => {
  const group = ui?.[groupName]
  if (Array.isArray(group) && group.length > 0) return group[0]
  return null
}

// Dynamic configs populated from backend on login (stored in sessionStorage)
// IMPORTANT: default visible_if should be false so panels don't "stick" visible when backend removes/disables them.
const DEFAULT_MY_STATUS = { id: 'my_status', label: 'My Status', description: 'Your current role and status in the experiment.', visible_if: false, bindings: [] }
const DEFAULT_MY_ACTIONS = { id: 'my_actions', label: 'My Actions', description: 'Actions you can take during the experiment.', visible_if: false, bindings: [] }
const DEFAULT_MY_TASKS = { id: 'my_tasks', label: 'My Tasks', description: 'Your assigned tasks and goals for this session.', visible_if: false, bindings: [] }
const DEFAULT_SOCIAL_PANEL = { id: 'social_panel', label: 'Social Panel', description: 'Communicate and trade with other participants.', visible_if: false, bindings: [], tabs: ['trade', 'messages'] }
const DEFAULT_INFO_DASHBOARD = { id: 'info_dashboard', label: 'Info Dashboard', description: 'View information about other participants in the session.', visible_if: false, bindings: [] }

const myStatusConfig = ref({ ...DEFAULT_MY_STATUS })
const myActionsConfig = ref({ ...DEFAULT_MY_ACTIONS })
const myTasksConfig = ref({ ...DEFAULT_MY_TASKS })
const socialPanelConfig = ref({ ...DEFAULT_SOCIAL_PANEL })
const infoDashboardConfig = ref({ ...DEFAULT_INFO_DASHBOARD })

// Popup UI elements for hidden profile
const readingWindowConfig = ref(null)
const initialVoteConfig = ref(null)
const finalVoteConfig = ref(null)

// Popup state management
const showReadingWindow = ref(false)
const showInitialVote = ref(false)
const showFinalVote = ref(false)
const initialVoteSubmitted = ref(false)
const finalVoteSubmitted = ref(false)
const readingTimeRemaining = ref(0) // in seconds
const readingTimerInterval = ref(null)
const hasEnteredInterface = ref(false)
const readingWindowEnded = ref(false)
const sessionEnded = ref(false)
const candidateDocument = ref(null)
const candidateNames = ref([])
const selectedCandidate = ref('')
const isSubmittingVote = ref(false)

// Auto start popup state
const showAutoStartPopup = ref(false)
const autoStartCountdown = ref(5)
const autoStartMessage = ref('Session starts in 5 seconds.')
const autoStartProgress = ref(0)
const autoStartInterval = ref(null)
const autoStartChecked = ref(false) // Track if we've already checked for auto start
const waitingForPopups = ref(false) // Track if we're waiting for popup windows to complete before starting timer
const checkingPopups = ref(false) // Flag to prevent infinite loops when checking popups
const checkingTimer = ref(false) // Flag to prevent infinite loops when checking timer
const pendingPopupTimers = ref([]) // Track all popup timers that should start after auto start countdown

const applyInterface = (ui) => {
  // Reset first so if a panel is removed/disabled in the latest interface, it disappears immediately.
  myStatusConfig.value = { ...DEFAULT_MY_STATUS }
  myActionsConfig.value = { ...DEFAULT_MY_ACTIONS }
  myTasksConfig.value = { ...DEFAULT_MY_TASKS }
  socialPanelConfig.value = { ...DEFAULT_SOCIAL_PANEL }
  infoDashboardConfig.value = { ...DEFAULT_INFO_DASHBOARD }

  const myStatus = getFirstPanel(ui, 'My Status')
  const myActions = getFirstPanel(ui, 'My Actions')
  const myTasks = getFirstPanel(ui, 'My Tasks')
  const social = getFirstPanel(ui, 'Social Panel')
  const info = getFirstPanel(ui, 'Info Dashboard')

  if (myStatus) myStatusConfig.value = { ...DEFAULT_MY_STATUS, ...myStatus }
  if (myActions) myActionsConfig.value = { ...DEFAULT_MY_ACTIONS, ...myActions }
  if (myTasks) myTasksConfig.value = { ...DEFAULT_MY_TASKS, ...myTasks }
  if (social) socialPanelConfig.value = { ...DEFAULT_SOCIAL_PANEL, ...social }
  if (info) infoDashboardConfig.value = { ...DEFAULT_INFO_DASHBOARD, ...info }

  // Handle popup UI elements
  const readingWindow = getFirstPanel(ui, 'Reading Window')
  const initialVote = getFirstPanel(ui, 'Initial Vote')
  const finalVote = getFirstPanel(ui, 'Final Vote')

  console.log('[Participant] applyInterface - readingWindow:', readingWindow, 'hasEnteredInterface:', hasEnteredInterface.value)

  if (readingWindow) {
    readingWindowConfig.value = readingWindow
    console.log('[Participant] Reading window config found, visible_if:', readingWindow.visible_if, 'type:', typeof readingWindow.visible_if)
    
    // Check if visible_if indicates we should show on enter/start
    // Handle both string values ('on_enter', 'on_start') and boolean true
    // Note: Backend may convert 'on_enter' to boolean true, so we check for both
    const visibleIfValue = readingWindow.visible_if
    const isOnEnter = (
      visibleIfValue === 'on_enter' || 
      visibleIfValue === 'on_start' ||
      (visibleIfValue === true && readingWindow.type === 'popup') // If it's a popup with true, treat as on_enter
    )
    console.log('[Participant] Should show reading window (on_enter):', isOnEnter, 'hasEnteredInterface:', hasEnteredInterface.value)
    
    // Only show reading window if it hasn't ended yet
    if (isOnEnter && !hasEnteredInterface.value && !readingWindowEnded.value) {
      console.log('[Participant] Showing reading window for the first time')
      hasEnteredInterface.value = true
      // Show window immediately, then load document
      showReadingWindow.value = true
      console.log('[Participant] showReadingWindow set to:', showReadingWindow.value)
      // Load candidate document first (async)
      loadCandidateDocument()
      
      // Check if this popup has a timer (check for readingTime or duration in config)
      const hasTimer = checkPopupHasTimer(readingWindow)
      
      if (hasTimer) {
        // Check if auto start is enabled - if so, wait for auto start countdown to finish
        schedulePopupTimerStart(() => startReadingTimer(), 'Reading Window')
      } else {
        // No timer, start immediately (though reading window should always have timer)
        setTimeout(() => {
          startReadingTimer()
        }, 100)
      }
    } else if (readingWindowEnded.value) {
      console.log('[Participant] Reading window already ended, not showing again')
    }
  } else {
    console.log('[Participant] No reading window config found in interface')
  }

  if (initialVote) {
    initialVoteConfig.value = initialVote
    console.log('[Participant] Initial vote config found, visible_if:', initialVote.visible_if, 'readingWindowEnded:', readingWindowEnded.value, 'initialVoteSubmitted:', initialVoteSubmitted.value)
    // Check if visible_if is "reading_window.on_end" and reading window has ended
    // Only show if not already submitted
    // Handle both string and boolean values
    const initialVoteVisibleIf = initialVote.visible_if
    const shouldShowInitial = (
      (initialVoteVisibleIf === 'reading_window.on_end' || 
       (initialVoteVisibleIf === true && initialVote.type === 'popup')) &&
      readingWindowEnded.value && 
      !showInitialVote.value &&
      !initialVoteSubmitted.value
    )
    console.log('[Participant] Should show initial vote from applyInterface:', shouldShowInitial)
    if (shouldShowInitial) {
      console.log('[Participant] Showing initial vote popup from applyInterface')
      showInitialVote.value = true
      loadCandidateNames()
      // Notify backend that vote popup is shown (for agent voting)
      notifyVotePopupShown('initial')
    }
  }

  if (finalVote) {
    finalVoteConfig.value = finalVote
    console.log('[Participant] Final vote config found, visible_if:', finalVote.visible_if, 'sessionEnded:', sessionEnded.value, 'finalVoteSubmitted:', finalVoteSubmitted.value)
    // Check if visible_if is "on_end" and session has ended
    // Only show if not already submitted
    // Handle both string and boolean values
    const finalVoteVisibleIf = finalVote.visible_if
    const shouldShowFinal = (
      (finalVoteVisibleIf === 'on_end' || 
       (finalVoteVisibleIf === true && finalVote.type === 'popup')) &&
      sessionEnded.value && 
      !showFinalVote.value &&
      !finalVoteSubmitted.value
    )
    console.log('[Participant] Should show final vote from applyInterface:', shouldShowFinal)
    if (shouldShowFinal) {
      console.log('[Participant] Showing final vote popup from applyInterface')
      showFinalVote.value = true
      loadCandidateNames()
      // Notify backend that vote popup is shown (for agent voting)
      notifyVotePopupShown('final')
    }
  }
}

// Store all participants for Info Dashboard
const allParticipants = ref([])

/** Synced from session / sessionStorage; used for Map Task header role badge */
const experimentType = ref(sessionStorage.getItem('experiment_type') || '')

const mapTaskRoleForHeader = computed(() => {
  if (experimentType.value !== 'maptask') return ''
  const myId = sessionStorage.getItem('participant_id')
  const me = allParticipants.value.find((p) => p?.id === myId || p?.participant_id === myId)
  const fromApi = me?.role != null ? String(me.role).trim() : ''
  const fromStore = (sessionStorage.getItem('participant_role') || '').trim()
  return fromApi || fromStore
})

const headerRoleBadgeClass = computed(() => {
  const r = String(mapTaskRoleForHeader.value || '').toLowerCase()
  if (r === 'guider') return 'guider'
  if (r === 'follower') return 'follower'
  return 'role-other'
})

/** Role text only (inside the colored tag); prefix "You are:" is outside the tag */
const mapTaskRoleHeaderPretty = computed(() => {
  const raw = mapTaskRoleForHeader.value
  if (!raw) return ''
  const role = String(raw).trim()
  return role.charAt(0).toUpperCase() + role.slice(1).toLowerCase()
})

// Store conversations and messages for Social Panel
const conversations = ref({}) // Format: { "from_to": [messages] }
const messages = ref([]) // Flat array of all messages

// Store trade data for Social Panel
const pendingOffers = ref([])
const completedTrades = ref([])
const participantsMap = computed(() => {
  const map = {}
  allParticipants.value.forEach(p => {
    const id = p?.id || p?.participant_id
    if (id) {
      map[id] = p
    }
  })
  return map
})

// Store interaction config for communication level
const interactionConfig = ref({})
const commLevel = computed(() => {
  // Get communication level from interaction config
  // Backend stores it as interaction.communicationLevel
  // The value could be: "Private Messaging", "Group Chat", "No Chat"
  // Or normalized: "chat", "groupChat", "no_chat"
  let level = interactionConfig.value?.communicationLevel
  
  // If not found, try alternative paths
  if (!level) {
    level = interactionConfig.value?.['Communication Level'] ||
            interactionConfig.value?.['communicationLevel']
  }
  
  // Normalize the value
  if (!level) return 'chat'
  
  if (typeof level === 'string') {
    const levelLower = level.toLowerCase()
    // Map backend values to frontend values
    if (levelLower.includes('private') || levelLower === 'chat') return 'chat'
    if (levelLower.includes('group')) return 'groupChat'
    if (levelLower.includes('no chat') || levelLower === 'no_chat') return 'no_chat'
    // If already normalized, return as is
    return level
  }
  
  return 'chat'
})

const normalizeTimestamp = (ts) => {
  if (ts == null) return 0
  if (typeof ts === 'number') {
    // seconds vs ms (rough cutoff: 2000-01-01 in ms)
    return ts < 946684800000 ? ts * 1000 : ts
  }
  if (typeof ts === 'string') {
    const trimmed = ts.trim()
    if (trimmed) {
      const num = Number(trimmed)
      if (Number.isFinite(num)) {
        return num < 946684800000 ? num * 1000 : num
      }
    }
    const parsed = new Date(ts).getTime()
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

// Message length limit (word count) when enabled in interaction config
const messageLengthLimit = computed(() => {
  const ml = interactionConfig.value?.messageLength
  if (ml && typeof ml === 'object' && ml.enabled && typeof ml.value === 'number' && ml.value > 0) {
    return ml.value
  }
  return null
})

// Communication media: array of 'text' | 'audio' | 'meeting_room' from interaction config
const communicationMedia = computed(() => {
  const media = interactionConfig.value?.communicationMedia
  if (Array.isArray(media) && media.length > 0) {
    return media
  }
  return ['text']
})

const typeIndicatorEnabled = computed(() => interactionConfig.value?.typeIndicator === 'enabled')

// In-session annotation popup state
const showAnnotationPopup = ref(false)
const annotationCheckpoint = ref(0)
/** True after this participant submitted but other human(s) have not yet */
const annotationWaitingForPartners = ref(false)

// Store cleanup function reference
let cleanupParticipantsListener = null
let cleanupMessageListener = null
let cleanupTimerListener = null
let cleanupAnnotationListener = null

// Handle incoming messages from WebSocket
const handleMessageReceived = (message) => {
  console.log('[Participant] Received message:', message)
  
  const sender = message.sender
  const receiver = message.receiver // null for group chat
  
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
    timestamp: normalizeTimestamp(message.timestamp) || Date.now()
  }
  
  // Add to flat messages array
  const existsInFlat = messages.value.some(m => m.id === msg.id || (m.timestamp === msg.timestamp && m.content === msg.content))
  if (!existsInFlat) {
    messages.value.push(msg)
    // Keep sorted by timestamp
    messages.value.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0))
  }
  
  // Add to conversations object
  if (receiver === null) {
    // Group chat: use special key
    const key = 'group'
    const existing = conversations.value[key] || []
    const exists = existing.some(m => m.id === msg.id || (m.timestamp === msg.timestamp && m.content === msg.content))
    if (!exists) {
      conversations.value = {
        ...conversations.value,
        [key]: [...existing, msg]
      }
    }
  } else {
    // Private chat: determine conversation key (sender_receiver or receiver_sender)
    const key1 = `${sender}_${receiver}`
    const key2 = `${receiver}_${sender}`
    const key = conversations.value[key1] ? key1 : (conversations.value[key2] ? key2 : key1)
    
    const existing = conversations.value[key] || []
    const exists = existing.some(m => m.id === msg.id || (m.timestamp === msg.timestamp && m.content === msg.content))
    if (!exists) {
      conversations.value = {
        ...conversations.value,
        [key]: [...existing, msg]
      }
    }
  }
}

const participantsUpdateHandler = (data) => {
  console.log('[Participant] participantsUpdateHandler called with:', data)

  // (kept for future extensibility) ignore noop updates if needed
  
  // Check if this update is for our session
  const currentSessionId = sessionId.value
  if (data?.session_id && data.session_id !== currentSessionId) {
    console.log('[Participant] Ignoring update for different session:', {
      receivedSessionId: data.session_id,
      currentSessionId: currentSessionId
    })
    return
  }
  
  const myParticipantId = sessionStorage.getItem('participant_id')
  const list = data?.participants
  if (!myParticipantId || !Array.isArray(list)) {
    console.log('[Participant] No participant ID or participants list:', { 
      hasMyId: !!myParticipantId, 
      hasList: !!list,
      listType: Array.isArray(list) ? 'array' : typeof list,
      listLength: Array.isArray(list) ? list.length : 'N/A'
    })
    return
  }

  console.log('[Participant] Received websocket update:', {
    updateType: data?.update_type,
    participantsCount: list.length,
    participantIds: list.map(p => p?.id || p?.participant_id)
  })

  // Store all participants for Info Dashboard
  allParticipants.value = list

  const me = list.find((p) => p?.id === myParticipantId || p?.participant_id === myParticipantId)
  if (
    experimentType.value === 'maptask' &&
    me?.role != null &&
    String(me.role).trim() !== ''
  ) {
    sessionStorage.setItem('participant_role', String(me.role).trim())
  }
  if (!me) {
    console.log('[Participant] My participant not found in list:', { 
      myId: myParticipantId,
      availableIds: list.map(p => p?.id || p?.participant_id)
    })
    // Fallback: re-fetch via REST (handles mismatched payload shapes / stale ids)
    fetchParticipants()
    return
  }
  
  if (!me.interface) {
    console.log('[Participant] My participant has no interface')
    // Fallback: re-fetch via REST to get computed interface
    fetchParticipants()
    return
  }

  console.log('[Participant] Applying interface update:', {
    updateType: data?.update_type,
    infoDashboardBindings: me.interface['Info Dashboard']?.[0]?.bindings?.length || 0,
    bindings: me.interface['Info Dashboard']?.[0]?.bindings,
    totalParticipants: list.length,
    otherParticipantsCount: list.filter(p => (p?.id || p?.participant_id) !== myParticipantId).length
  })

  // Persist latest UI config so refresh keeps in sync
  sessionStorage.setItem('participant_interface', JSON.stringify(me.interface))
  console.log('[Participant] Applying interface from participantsUpdateHandler:', me.interface)
  applyInterface(me.interface)
  
  // If this is a trade update, refresh trade data
  if (data?.update_type === 'trade_update') {
    console.log('[Participant] Trade update detected, refreshing trade data')
    fetchTradeData()
  }
  
  // If this is an investment update, the participant data is already updated via WebSocket
  // but we can log it for debugging
  if (data?.update_type === 'investment_update') {
    console.log('[Participant] Investment update detected, participant data updated via WebSocket')
  }
  
  // Also fetch latest session config to update interaction config (for communication level)
  if (sessionId.value || sessionName.value) {
    fetchSessionConfig()
  }
  
  // Check for auto start after participants are loaded
  if (!autoStartChecked.value && list.length > 0) {
    checkAutoStart(list)
  }
  
  // Update session status if provided
  if (data.session_info) {
    const sessionInfo = data.session_info
    if (sessionInfo.status) {
      sessionStatus.value = sessionInfo.status
      // Update status message
      if (sessionInfo.status === 'running') {
        sessionStatusMessage.value = 'Running'
        // Close auto start popup if session is already running
        if (showAutoStartPopup.value) {
          closeAutoStartPopup()
        }
        // Check if we need to wait for popups (for manual start by researcher)
        checkIfShouldWaitForPopups(sessionInfo)
      } else if (sessionInfo.status === 'paused') {
        sessionStatusMessage.value = 'Paused'
      } else if (sessionInfo.status === 'waiting') {
        sessionStatusMessage.value = 'Waiting'
      } else {
        sessionStatusMessage.value = sessionInfo.status.charAt(0).toUpperCase() + sessionInfo.status.slice(1)
      }
      console.log('[Participant] Session status updated via WebSocket:', sessionInfo.status)
    }
  }
  
  // Also handle status_changed update type
  // Note: We only handle this if session_info.status wasn't already processed above
  // to avoid duplicate calls
  if (data.update_type === 'status_changed' && data.session_info) {
    const sessionInfo = data.session_info
    if (sessionInfo.status && sessionStatus.value !== sessionInfo.status) {
      sessionStatus.value = sessionInfo.status
      // Update status message
      if (sessionInfo.status === 'running') {
        // Check if we need to wait for popups before starting timer
        // This handles the case when researcher manually starts the session
        checkIfShouldWaitForPopups(sessionInfo)
        sessionStatusMessage.value = 'Running'
      } else if (sessionInfo.status === 'paused') {
        sessionStatusMessage.value = 'Paused'
      } else if (sessionInfo.status === 'waiting') {
        sessionStatusMessage.value = 'Waiting'
      } else {
        sessionStatusMessage.value = sessionInfo.status.charAt(0).toUpperCase() + sessionInfo.status.slice(1)
      }
      console.log('[Participant] Session status changed via WebSocket:', sessionInfo.status)
    }
  }

  // When timer expires: session is paused with remaining_seconds=0 - navigate to post-annotation
  // (fallback if timer_update with 0 was missed)
  if (data.update_type === 'timer_expired' && data.session_info && !sessionEnded.value) {
    const sessionInfo = data.session_info
    const remaining = sessionInfo.remaining_seconds
    if ((remaining === 0 || remaining === '0') && sessionInfo.status === 'paused') {
      sessionEnded.value = true
      timerDisplay.value = '00:00'
      sessionStatus.value = 'paused'
      sessionStatusMessage.value = 'Paused'
      console.log('[Participant] Session ended (timer_expired), checking for final vote / post-annotation')
      const finalVoteVisibleIf = finalVoteConfig.value?.visible_if
      const shouldShowFinalVote = (
        finalVoteConfig.value &&
        (finalVoteVisibleIf === 'on_end' ||
         (finalVoteVisibleIf === true && finalVoteConfig.value.type === 'popup'))
      )
      if (shouldShowFinalVote && !finalVoteSubmitted.value) {
        showFinalVote.value = true
        loadCandidateNames()
        notifyVotePopupShown('final')
      } else {
        navigateToPostAnnotationIfNeeded()
      }
    }
  }
}

// Fetch session config to get interaction config (for communication level)
const fetchSessionConfig = async () => {
  if (!sessionId.value && !sessionName.value) return
  
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    const response = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    if (response.ok) {
      const session = await response.json()
      const et = session.experiment_type || session.experiment_config?.id
      if (et) {
        experimentType.value = et
        sessionStorage.setItem('experiment_type', et)
        if (et !== 'maptask') {
          sessionStorage.removeItem('participant_role')
        }
      }
      if (session.interaction) {
        interactionConfig.value = session.interaction
        console.log('[Participant] Updated interaction config from session:', interactionConfig.value)
      } else if (session.experiment_config?.interaction) {
        interactionConfig.value = session.experiment_config.interaction
        console.log('[Participant] Updated interaction config from experiment_config:', interactionConfig.value)
      }
    }
  } catch (error) {
    console.error('[Participant] Error fetching session config:', error)
  }
}

// Fetch participants on mount
const fetchParticipants = async () => {
  if (!sessionId.value && !sessionName.value) return
  
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    const response = await fetch(`/api/sessions/${encodedSessionName}/participants`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (response.ok) {
      const data = await response.json()
      if (data.participants && Array.isArray(data.participants)) {
        allParticipants.value = data.participants
        console.log('[Participant] Fetched participants on mount:', data.participants.length)
        
        // Also apply interface if available
        const myParticipantId = sessionStorage.getItem('participant_id')
        const me = data.participants.find((p) => p?.id === myParticipantId || p?.participant_id === myParticipantId)
        if (
          experimentType.value === 'maptask' &&
          me?.role != null &&
          String(me.role).trim() !== ''
        ) {
          sessionStorage.setItem('participant_role', String(me.role).trim())
        }
        if (me && me.interface) {
          console.log('[Participant] Applying interface from fetchParticipants:', me.interface)
          applyInterface(me.interface)
        }
        
        // Check for auto start after participants are loaded
        if (!autoStartChecked.value && data.participants.length > 0) {
          await checkAutoStart(data.participants)
        }
      }
    }
  } catch (error) {
    console.error('[Participant] Error fetching participants:', error)
  }
}

// Fetch trade data (pending offers and completed trades)
const fetchTradeData = async () => {
  if (!sessionId.value && !sessionName.value) return
  
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    
    // Fetch pending offers
    const offersResponse = await fetch(`/api/sessions/${encodedSessionName}/pending_offers`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    if (offersResponse.ok) {
      const offersData = await offersResponse.json()
      if (Array.isArray(offersData.offers || offersData)) {
        pendingOffers.value = offersData.offers || offersData
      }
    }
    
    // Fetch completed trades
    const tradesResponse = await fetch(`/api/sessions/${encodedSessionName}/completed_trades`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    if (tradesResponse.ok) {
      const tradesData = await tradesResponse.json()
      if (Array.isArray(tradesData.trades || tradesData)) {
        completedTrades.value = tradesData.trades || tradesData
      }
    }
  } catch (error) {
    console.error('[Participant] Error fetching trade data:', error)
  }
}

// Handle trade submission
const handleTradeSubmit = async (data) => {
  console.log('[Participant] Trade submitted:', data)
  // The actual submission is handled in social_panel, but we can refresh trade data here
  await fetchTradeData()
}

// Notify backend when vote popup is shown (for agent voting)
const notifyVotePopupShown = (voteType) => {
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    const participantId = sessionStorage.getItem('participant_id')
    
    if (!sessionIdentifier || !participantId) {
      console.warn('[Participant] Cannot notify vote popup: missing session or participant ID')
      return
    }
    
    const ws = getSocket()
    if (ws && ws.connected) {
      ws.emit('vote_popup_shown', {
        session_id: sessionIdentifier,
        participant_id: participantId,
        vote_type: voteType
      })
      console.log(`[Participant] Notified backend: ${voteType} vote popup shown`)
    } else {
      console.warn('[Participant] WebSocket not connected, cannot notify vote popup')
    }
  } catch (error) {
    console.error('[Participant] Error notifying vote popup:', error)
  }
}

// Reading window timer management
const startReadingTimer = async () => {
  // Fetch reading time from session params
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    const response = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    if (response.ok) {
      const session = await response.json()
      const readingTimeMinutes = session.params?.readingTime || session.experiment_config?.params?.readingTime || 1
      readingTimeRemaining.value = readingTimeMinutes * 60 // convert to seconds
      
      // Start countdown timer
      readingTimerInterval.value = setInterval(() => {
        readingTimeRemaining.value--
        if (readingTimeRemaining.value <= 0) {
          clearInterval(readingTimerInterval.value)
          readingTimerInterval.value = null
          // Reading window ended
          showReadingWindow.value = false
          readingWindowEnded.value = true
          console.log('[Participant] Reading window ended, checking for initial vote')
          // Show initial vote if configured
          // Handle both string and boolean values for visible_if
          const initialVoteVisibleIf = initialVoteConfig.value?.visible_if
          const shouldShowInitialVote = (
            initialVoteConfig.value && 
            (initialVoteVisibleIf === 'reading_window.on_end' || 
             (initialVoteVisibleIf === true && initialVoteConfig.value.type === 'popup'))
          )
          console.log('[Participant] Should show initial vote:', shouldShowInitialVote, 'visible_if:', initialVoteVisibleIf)
          if (shouldShowInitialVote) {
            console.log('[Participant] Showing initial vote popup')
            showInitialVote.value = true
            loadCandidateNames()
            // Notify backend that vote popup is shown (for agent voting)
            notifyVotePopupShown('initial')
          }
          
          // Check if we should start auto start countdown now
          checkPendingAutoStart()
        }
      }, 1000)
    }
  } catch (error) {
    console.error('[Participant] Error fetching reading time:', error)
  }
}

// Load candidate document
const loadCandidateDocument = async () => {
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    const participantId = sessionStorage.getItem('participant_id')
    if (!sessionIdentifier || !participantId) {
      console.warn('[Participant] Missing session identifier or participant ID')
      return
    }
    
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    
    // Fetch participant data to get assigned document
    const response = await fetch(`/api/sessions/${encodedSessionName}/participants`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    if (response.ok) {
      const data = await response.json()
      const me = data.participants?.find((p) => p?.id === participantId || p?.participant_id === participantId)
      if (me && me.experiment_params?.candidate_document) {
        const doc = me.experiment_params.candidate_document
        console.log('[Participant] Raw candidate_document from backend:', doc, 'type:', typeof doc)
        
        // Handle both file object and file path string
        if (typeof doc === 'string') {
          // If it's a string, it could be a filename or a path
          // Use the standard essays API endpoint
          candidateDocument.value = { 
            filename: doc,
            file_path: `/api/essays/${encodeURIComponent(doc)}`
          }
        } else if (doc && typeof doc === 'object') {
          // If it's an object, use it as-is but ensure file_path is set
          candidateDocument.value = {
            ...doc,
            file_path: doc.file_path || doc.download_url || (doc.filename ? `/api/essays/${encodeURIComponent(doc.filename)}` : null)
          }
        }
        console.log('[Participant] Loaded candidate document:', candidateDocument.value)
      } else {
        console.warn('[Participant] No candidate document assigned to participant:', { me, participantId, experiment_params: me?.experiment_params })
      }
    } else {
      console.error('[Participant] Failed to fetch participants:', response.statusText)
    }
  } catch (error) {
    console.error('[Participant] Error loading candidate document:', error)
  }
}

// Load candidate names from session params
const loadCandidateNames = async () => {
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    const response = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    if (response.ok) {
      const session = await response.json()
      const names = session.params?.candidateNames || session.experiment_config?.params?.candidateNames || []
      candidateNames.value = Array.isArray(names) ? names : (names ? [names] : [])
    }
  } catch (error) {
    console.error('[Participant] Error loading candidate names:', error)
  }
}

// Submit initial vote
const submitInitialVote = async () => {
  if (!selectedCandidate.value) {
    return
  }
  
  isSubmittingVote.value = true
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    const participantId = sessionStorage.getItem('participant_id')
    const encodedSessionId = encodeURIComponent(sessionIdentifier)
    
    // Fetch current participant data
    const getResponse = await fetch(`/api/sessions/${encodedSessionId}/participants`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (!getResponse.ok) {
      throw new Error('Failed to fetch participant data')
    }
    
    const participantsData = await getResponse.json()
    const currentParticipant = participantsData.participants?.find(
      (p) => p?.id === participantId || p?.participant_id === participantId
    )
    
    if (!currentParticipant) {
      throw new Error('Participant not found')
    }
    
    // Update participant with initial vote
    const updatedParticipant = {
      ...currentParticipant,
      experiment_params: {
        ...currentParticipant.experiment_params,
        initial_vote: selectedCandidate.value
      }
    }
    const ctx = await captureActionContext()
    Object.assign(updatedParticipant, ctx)
    
    // Use PUT method to update participant
    const response = await fetch(`/api/sessions/${encodedSessionId}/participants/${participantId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(updatedParticipant)
    })
    
    if (response.ok) {
      showInitialVote.value = false
      initialVoteSubmitted.value = true // Mark as submitted
      selectedCandidate.value = ''
      // Reload participants to update UI
      await fetchParticipants()
      console.log('[Participant] Initial vote submitted successfully')
      
      // After initial vote, ensure session timer can start for HiddenProfile
      try {
        const sessionIdentifier = sessionName.value || sessionId.value
        if (sessionIdentifier) {
          const encodedSessionName = encodeURIComponent(sessionIdentifier)
          const sessionResp = await fetch(`/api/sessions/${encodedSessionName}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
          })
          if (sessionResp.ok) {
            const session = await sessionResp.json()
            const experimentType = session.experiment_type || session.experiment_config?.id
            // If this is a HiddenProfile session and it's still waiting,
            // start the session (and timer) immediately after initial vote
            if (experimentType === 'hiddenprofile' && session.status === 'waiting') {
              console.log('[Participant] HiddenProfile: starting session after initial vote')
              const startResp = await fetch(`/api/sessions/${encodedSessionName}/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ delay_timer: false })
              })
              if (!startResp.ok) {
                console.error('[Participant] Failed to start HiddenProfile session after initial vote')
              } else {
                // Mark auto start as handled so we don't double-start
                autoStartChecked.value = true
              }
            } else {
              // For other experiments, fall back to existing auto start logic
              if (Array.isArray(allParticipants.value) && allParticipants.value.length > 0) {
                await checkAutoStart(allParticipants.value)
              }
            }
          }
        }
      } catch (e) {
        console.error('[Participant] Error starting session / auto start after initial vote:', e)
      }
      
      // For sessions that were manually started with delayed timer,
      // this will allow the timer to actually begin once popups complete
      checkPendingAutoStart()
    } else {
      const errorText = await response.text()
      let error
      try {
        error = JSON.parse(errorText)
      } catch {
        error = { error: errorText || 'Failed to submit initial vote' }
      }
      console.error('[Participant] Failed to submit initial vote:', error)
      alert(error.error || 'Failed to submit initial vote')
    }
  } catch (error) {
    console.error('[Participant] Error submitting initial vote:', error)
    alert('Error submitting vote. Please try again.')
  } finally {
    isSubmittingVote.value = false
  }
}

// Submit final vote
const submitFinalVote = async () => {
  if (!selectedCandidate.value) {
    return
  }
  
  isSubmittingVote.value = true
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    const participantId = sessionStorage.getItem('participant_id')
    const encodedSessionId = encodeURIComponent(sessionIdentifier)
    
    // Fetch current participant data
    const getResponse = await fetch(`/api/sessions/${encodedSessionId}/participants`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (!getResponse.ok) {
      throw new Error('Failed to fetch participant data')
    }
    
    const participantsData = await getResponse.json()
    const currentParticipant = participantsData.participants?.find(
      (p) => p?.id === participantId || p?.participant_id === participantId
    )
    
    if (!currentParticipant) {
      throw new Error('Participant not found')
    }
    
    // Update participant with final vote
    const updatedParticipant = {
      ...currentParticipant,
      experiment_params: {
        ...currentParticipant.experiment_params,
        final_vote: selectedCandidate.value
      }
    }
    const ctx = await captureActionContext()
    Object.assign(updatedParticipant, ctx)
    
    // Use PUT method to update participant
    const response = await fetch(`/api/sessions/${encodedSessionId}/participants/${participantId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(updatedParticipant)
    })
    
    if (response.ok) {
      showFinalVote.value = false
      finalVoteSubmitted.value = true // Mark as submitted
      selectedCandidate.value = ''
      // Reload participants to update UI
      await fetchParticipants()
      console.log('[Participant] Final vote submitted successfully')
      // Navigate to post-annotation if enabled
      await navigateToPostAnnotationIfNeeded()
    } else {
      const errorText = await response.text()
      let error
      try {
        error = JSON.parse(errorText)
      } catch {
        error = { error: errorText || 'Failed to submit final vote' }
      }
      console.error('[Participant] Failed to submit final vote:', error)
      alert(error.error || 'Failed to submit final vote')
    }
  } catch (error) {
    console.error('[Participant] Error submitting final vote:', error)
    alert('Error submitting vote. Please try again.')
  } finally {
    isSubmittingVote.value = false
  }
}

// Check if auto start should be triggered
const checkAutoStart = async (participantsList) => {
  // Only check once
  if (autoStartChecked.value) {
    return
  }
  
  // Don't check if session is already running
  if (sessionStatus.value === 'running') {
    autoStartChecked.value = true
    return
  }
  
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    if (!sessionIdentifier) return
    
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    const response = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (!response.ok) return
    
    const session = await response.json()
    
    const experimentType = session.experiment_type || session.experiment_config?.id
    
    // Don't check if session is already running
    if (session.status === 'running') {
      autoStartChecked.value = true
      return
    }
    
    // Check if auto_start is enabled
    const autoStart = session.experiment_config?.participant_settings?.auto_start
    if (!autoStart) {
      autoStartChecked.value = true
      return
    }
    
    // For hiddenprofile, we must wait until initial vote is submitted
    // before we allow auto start countdown (session timer + agents)
    if (experimentType === 'hiddenprofile') {
      // If required popups (reading window + initial vote) are not complete yet,
      // do NOT start auto start countdown now. We'll re-check after initial vote submit.
      if (!arePopupsComplete()) {
        console.log('[Participant] HiddenProfile: popups not complete (waiting for initial vote), skipping auto start for now')
        // IMPORTANT: do NOT set autoStartChecked here so we can check again later
        return
      }
    }
    
    // Check if there are popup windows that need to complete first
    const hasOnEnterPopups = checkForOnEnterPopups(session)
    
    // Get all human participants
    const humanParticipants = participantsList.filter(p => {
      const type = (p.type || '').toLowerCase()
      return type === 'human'
    })
    
    const myParticipantId = sessionStorage.getItem('participant_id')
    
    
    // If no human participants, don't start
    if (humanParticipants.length === 0) {
      console.log('[Participant] No human participants found, skipping auto start')
      autoStartChecked.value = true
      return
    }
    
    // If only one human participant, start countdown immediately
    if (humanParticipants.length === 1) {
      console.log('[Participant] Single human participant, starting auto start countdown')
      startAutoStartCountdown()
      autoStartChecked.value = true
      return
    }
    
    // If multiple human participants, check if all are online
    const onlineHumanParticipants = humanParticipants.filter(p => {
      const participantId = p.id || p.participant_id
      const status = p.status || ''
      const loginTime = p.login_time
      // Consider online if:
      // 1. It's the current user (they're logged in)
      // 2. Status is 'online'
      // 3. Has login_time
      const isOnline = participantId === myParticipantId || 
             status === 'online' || 
             (loginTime && loginTime !== null && loginTime !== '')
      console.log(`[Participant] Participant ${participantId} online check:`, {
        participantId,
        isCurrentUser: participantId === myParticipantId,
        status,
        loginTime,
        isOnline
      })
      return isOnline
    })
    
    console.log('[Participant] Online human participants:', {
      online: onlineHumanParticipants.length,
      total: humanParticipants.length,
      onlineIds: onlineHumanParticipants.map(p => p.id || p.participant_id),
      allHumanIds: humanParticipants.map(p => p.id || p.participant_id)
    })
    
    // If all human participants are online, start countdown
    if (onlineHumanParticipants.length === humanParticipants.length && humanParticipants.length > 0) {
      console.log('[Participant] All human participants online, starting auto start countdown')
      startAutoStartCountdown()
      autoStartChecked.value = true
    } else {
      console.log('[Participant] Not all human participants online yet, waiting...', {
        online: onlineHumanParticipants.length,
        total: humanParticipants.length
      })
      // Don't set autoStartChecked to true yet, so we can check again when more participants come online
      
      // If auto start is enabled but won't start (not all online), start any pending popup timers
      // This handles the case where popup timers are waiting but auto start won't trigger
      if (autoStart && pendingPopupTimers.value.length > 0) {
        console.log('[Participant] Auto start enabled but not all participants online, starting pending popup timers')
        pendingPopupTimers.value.forEach(({ timer, name }) => {
          console.log(`[Participant] Starting ${name} timer (auto start won't trigger)`)
          timer()
        })
        pendingPopupTimers.value = []
      }
    }
  } catch (error) {
    console.error('[Participant] Error checking auto start:', error)
  }
}

// Check if a popup has a timer (countdown functionality)
const checkPopupHasTimer = (popupConfig) => {
  if (!popupConfig) return false
  
  // Check for common timer-related properties
  // Reading window has readingTime in session params
  // Other popups might have duration, timeLimit, etc.
  // For now, we check if it's a reading window type or has duration-related config
  const popupId = popupConfig.id || popupConfig.label || ''
  const isReadingWindow = popupId.toLowerCase().includes('reading') || 
                          popupId.toLowerCase().includes('read')
  
  // If it's a reading window, it likely has a timer
  // For other popups, we could check for duration properties
  // For now, assume reading window has timer, others might not
  return isReadingWindow || popupConfig.duration || popupConfig.timeLimit || popupConfig.timer
}

// Schedule a popup timer to start (either immediately or after auto start)
const schedulePopupTimerStart = async (timerFunction, popupName) => {
  const sessionIdentifier = sessionName.value || sessionId.value
  if (!sessionIdentifier) {
    // No session, start timer immediately
    timerFunction()
    return
  }
  
  try {
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    const response = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    if (response.ok) {
      const session = await response.json()
      const autoStart = session.experiment_config?.participant_settings?.auto_start
      const experimentType = session.experiment_type || session.experiment_config?.id
      
      // Check if auto start is enabled (either showing or about to show)
      // We need to delay if:
      // 1. Auto start is enabled AND (showing OR not checked yet)
      // 2. This ensures we wait even if auto start check hasn't completed yet
      let shouldDelay = autoStart && (showAutoStartPopup.value || !autoStartChecked.value)
      
      // For HiddenProfile, reading window and related popups should NOT wait for auto start.
      // Participants must be able to read and vote before the session timer starts.
      if (experimentType === 'hiddenprofile') {
        shouldDelay = false
      }
      
      if (shouldDelay) {
        // Auto start is enabled - wait for it to finish
        console.log(`[Participant] Auto start enabled, delaying ${popupName} timer start (auto start showing: ${showAutoStartPopup.value}, checked: ${autoStartChecked.value})`)
        pendingPopupTimers.value.push({ timer: timerFunction, name: popupName })
      } else {
        // No auto start or already finished - start timer immediately
        console.log(`[Participant] Starting ${popupName} timer immediately (auto start: ${autoStart}, showing: ${showAutoStartPopup.value})`)
        timerFunction()
      }
    } else {
      // If we can't check, start timer anyway
      timerFunction()
    }
  } catch (error) {
    console.error(`[Participant] Error checking auto start for ${popupName} timer:`, error)
    // If error, start timer anyway
    timerFunction()
  }
}

// Check if there are popup windows with on_enter that need to complete first
const checkForOnEnterPopups = (session) => {
  // Check interface config for popups with visible_if === 'on_enter' or 'on_start'
  const interfaceConfig = session.experiment_config?.interface || {}
  
  // Check all interface sections for popups
  for (const sectionName in interfaceConfig) {
    const section = interfaceConfig[sectionName]
    if (Array.isArray(section)) {
      for (const item of section) {
        if (item.type === 'popup') {
          const visibleIf = item.visible_if
          if (visibleIf === 'on_enter' || visibleIf === 'on_start' || 
              (visibleIf === true && item.type === 'popup')) {
            console.log('[Participant] Found on_enter popup:', item.id || item.label)
            return true
          }
        }
      }
    }
  }
  
  return false
}

// Check if all required popups have completed
const arePopupsComplete = () => {
  // Check if reading window has ended (if it exists)
  if (readingWindowConfig.value) {
    const visibleIf = readingWindowConfig.value.visible_if
    const isOnEnter = (
      visibleIf === 'on_enter' || 
      visibleIf === 'on_start' ||
      (visibleIf === true && readingWindowConfig.value.type === 'popup')
    )
    
    if (isOnEnter && !readingWindowEnded.value) {
      console.log('[Participant] Reading window still active, waiting...')
      return false
    }
  }
  
  // Check if initial vote needs to be completed (if it depends on reading window)
  if (initialVoteConfig.value) {
    const visibleIf = initialVoteConfig.value.visible_if
    const dependsOnReadingWindow = visibleIf === 'reading_window.on_end'
    
    if (dependsOnReadingWindow && !initialVoteSubmitted.value) {
      console.log('[Participant] Initial vote not submitted yet, waiting...')
      return false
    }
  }
  
  return true
}

// Check if we should wait for popups when session starts (for manual start by researcher)
const checkIfShouldWaitForPopups = async (sessionInfo) => {
  // Prevent infinite loops
  if (checkingPopups.value) {
    return
  }
  
  checkingPopups.value = true
  try {
    // Check if there are popups that need to complete
    const hasOnEnterPopups = readingWindowConfig.value && (
      readingWindowConfig.value.visible_if === 'on_enter' || 
      readingWindowConfig.value.visible_if === 'on_start' ||
      (readingWindowConfig.value.visible_if === true && readingWindowConfig.value.type === 'popup')
    )
    
    // Check if there are dependent actions (like initial vote)
    const hasDependentActions = initialVoteConfig.value && 
      initialVoteConfig.value.visible_if === 'reading_window.on_end'
    
    // If there are popups or dependent actions, and they're not complete, set waitingForPopups
    if ((hasOnEnterPopups || hasDependentActions) && !arePopupsComplete()) {
      console.log('[Participant] Session started manually, but popups not complete, waiting for them...')
      waitingForPopups.value = true
    } else if (arePopupsComplete()) {
      // Popups are complete, check if timer needs to be started
      if (waitingForPopups.value) {
        console.log('[Participant] Popups complete after manual start, starting timer')
        waitingForPopups.value = false
        // Use checkPendingAutoStart to start timer (it has its own loop prevention)
        checkPendingAutoStart()
      }
    }
  } catch (error) {
    console.error('[Participant] Error checking if should wait for popups:', error)
  } finally {
    checkingPopups.value = false
  }
}

// Check if we should start session timer after popups complete
const checkPendingAutoStart = () => {
  // Prevent infinite loops
  if (checkingTimer.value) {
    return
  }
  
  // If session is running but timer was delayed, start it now
  // Also check if session is running and popups are complete, even if waitingForPopups wasn't set
  // (this handles the case when researcher manually starts the session)
  if (sessionStatus.value === 'running') {
    if (arePopupsComplete()) {
      // Popups are complete, check if timer needs to be started
      if (waitingForPopups.value) {
        console.log('[Participant] Popups completed, starting session timer')
        waitingForPopups.value = false
        checkingTimer.value = true
        startSessionTimer().finally(() => {
          checkingTimer.value = false
        })
      }
    } else {
      // Popups not complete yet, set waitingForPopups if not already set
      if (!waitingForPopups.value) {
        console.log('[Participant] Session running but popups not complete, waiting...')
        waitingForPopups.value = true
      }
    }
  }
}

// Start auto start countdown
const startAutoStartCountdown = () => {
  if (showAutoStartPopup.value) {
    return // Already showing
  }
  
  showAutoStartPopup.value = true
  autoStartCountdown.value = 5
  autoStartProgress.value = 0
  autoStartMessage.value = 'Session starts in 5 seconds.'
  
  // Update progress and countdown every second
  autoStartInterval.value = setInterval(() => {
    autoStartCountdown.value--
    autoStartProgress.value = ((5 - autoStartCountdown.value) / 5) * 100
    autoStartMessage.value = `Session starts in ${autoStartCountdown.value} second${autoStartCountdown.value !== 1 ? 's' : ''}.`
    
    if (autoStartCountdown.value <= 0) {
      clearInterval(autoStartInterval.value)
      autoStartInterval.value = null
      startSessionFromParticipant()
    }
  }, 1000)
}

// Close auto start popup
const closeAutoStartPopup = () => {
  if (autoStartInterval.value) {
    clearInterval(autoStartInterval.value)
    autoStartInterval.value = null
  }
  showAutoStartPopup.value = false
  autoStartCountdown.value = 5
  autoStartProgress.value = 0
}

// Start session from participant interface
const startSessionFromParticipant = async () => {
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    if (!sessionIdentifier) {
      console.error('[Participant] No session identifier available')
      closeAutoStartPopup()
      return
    }
    
    // Check if we need to delay timer start (waiting for popups and dependent actions)
    // We need to delay if:
    // 1. There are on_enter popups (like reading window) that haven't completed
    // 2. OR there are actions that depend on those popups (like initial vote depending on reading window)
    const hasOnEnterPopups = readingWindowConfig.value && (
      readingWindowConfig.value.visible_if === 'on_enter' || 
      readingWindowConfig.value.visible_if === 'on_start' ||
      (readingWindowConfig.value.visible_if === true && readingWindowConfig.value.type === 'popup')
    )
    
    // Check if there are any dependent actions (like initial vote depending on reading window)
    const hasDependentActions = initialVoteConfig.value && 
      initialVoteConfig.value.visible_if === 'reading_window.on_end' &&
      !initialVoteSubmitted.value
    
    // Delay timer if popups are not complete OR if dependent actions are not complete
    const shouldDelayTimer = (hasOnEnterPopups || hasDependentActions) && !arePopupsComplete()
    
    console.log('[Participant] Timer delay check:', {
      hasOnEnterPopups,
      hasDependentActions,
      readingWindowEnded: readingWindowEnded.value,
      initialVoteSubmitted: initialVoteSubmitted.value,
      arePopupsComplete: arePopupsComplete(),
      shouldDelayTimer
    })
    
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    const response = await fetch(`/api/sessions/${encodedSessionName}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ delay_timer: shouldDelayTimer })
    })
    
    if (response.ok) {
      console.log('[Participant] Session started successfully', shouldDelayTimer ? '(timer delayed until popups complete)' : '')
      closeAutoStartPopup()
      
      // If timer was delayed, we'll start it after popups complete
      if (shouldDelayTimer) {
        waitingForPopups.value = true
        console.log('[Participant] Timer start delayed, waiting for popups to complete')
      }
      
      // Start all pending popup timers (auto start countdown has finished)
      if (pendingPopupTimers.value.length > 0) {
        console.log('[Participant] Auto start countdown finished, starting pending popup timers:', pendingPopupTimers.value.map(p => p.name))
        pendingPopupTimers.value.forEach(({ timer, name }) => {
          console.log(`[Participant] Starting ${name} timer`)
          timer()
        })
        pendingPopupTimers.value = []
      }
    } else {
      const error = await response.json().catch(() => ({ error: 'Failed to start session' }))
      console.error('[Participant] Failed to start session:', error)
      alert(error.error || 'Failed to start session. Please contact the researcher.')
      closeAutoStartPopup()
      
      // Even if session start failed, start all pending popup timers
      if (pendingPopupTimers.value.length > 0) {
        console.log('[Participant] Session start failed but starting pending popup timers anyway')
        pendingPopupTimers.value.forEach(({ timer, name }) => {
          console.log(`[Participant] Starting ${name} timer`)
          timer()
        })
        pendingPopupTimers.value = []
      }
    }
  } catch (error) {
    console.error('[Participant] Error starting session:', error)
    alert('Error starting session. Please contact the researcher.')
    closeAutoStartPopup()
    
    // Even if error, start all pending popup timers
    if (pendingPopupTimers.value.length > 0) {
      console.log('[Participant] Error occurred but starting pending popup timers anyway')
      pendingPopupTimers.value.forEach(({ timer, name }) => {
        console.log(`[Participant] Starting ${name} timer`)
        timer()
      })
      pendingPopupTimers.value = []
    }
  }
}

// Start timer after popups complete
const startSessionTimer = async () => {
  try {
    const sessionIdentifier = sessionName.value || sessionId.value
    if (!sessionIdentifier) return
    
    const encodedSessionName = encodeURIComponent(sessionIdentifier)
    
    // Get session to get timer info
    const getResponse = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (!getResponse.ok) return
    
    const session = await getResponse.json()
    
    // Start timer via resume endpoint (which will start if not running)
    const response = await fetch(`/api/sessions/${encodedSessionName}/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (response.ok) {
      console.log('[Participant] Session timer started after popups completed')
    } else {
      console.error('[Participant] Failed to start timer:', response.statusText)
    }
  } catch (error) {
    console.error('[Participant] Error starting timer:', error)
  }
}

// Submit annotation for in-session checkpoint
const submitAnnotation = async (payload) => {
  const transcription =
    typeof payload === 'string' ? payload.trim() : String(payload?.transcription || '').trim()
  const submittedAt =
    typeof payload === 'object' && payload?.submitted_at
      ? payload.submitted_at
      : new Date().toISOString()
  const sessionIdentifier = sessionName.value || sessionId.value
  const participantId = sessionStorage.getItem('participant_id')
  if (!sessionIdentifier || !participantId) {
    alert('Session or participant information not found.')
    return
  }
  try {
    const encodedSessionId = encodeURIComponent(sessionIdentifier)
    const response = await fetch(`/api/sessions/${encodedSessionId}/participants/${participantId}/submit_annotation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcription, submitted_at: submittedAt })
    })
    const data = await response.json()
    if (data.success) {
      if (data.resumed) {
        annotationWaitingForPartners.value = false
        showAnnotationPopup.value = false
        sessionStatus.value = 'running'
        sessionStatusMessage.value = 'Running'
      } else {
        annotationWaitingForPartners.value = true
        sessionStatus.value = 'paused'
        sessionStatusMessage.value = 'Paused'
      }
    } else {
      alert(data.error || 'Failed to submit annotation')
    }
  } catch (err) {
    console.error('[Participant] Error submitting annotation:', err)
    alert('Error submitting annotation. Please try again.')
  }
}

// Handle investment submission
const handleInvestmentSubmit = async (data) => {
  console.log('[Participant] Investment submitted:', data)
  
  if (data.action === 'submit_investment') {
    const sessionId = sessionStorage.getItem('session_id') || sessionStorage.getItem('session_code') || sessionStorage.getItem('session_name')
    const participantId = sessionStorage.getItem('participant_id')
    
    if (!sessionId || !participantId) {
      alert('Session or participant information not found. Please login again.')
      return
    }
    
    try {
      const encodedSessionId = encodeURIComponent(sessionId)
      const url = `/api/sessions/${encodedSessionId}/participants/${participantId}/submit_investment`
      
      const investmentRequest = {
        investment_amount: parseFloat(data.values.investment_amount) || 0,
        investment_type: data.values.investment_type || 'individual'
      }
      const ctx = await captureActionContext()
      Object.assign(investmentRequest, ctx)
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(investmentRequest)
      })
      
      const result = await response.json()
      
      if (result.success) {
        console.log('[Participant] Investment submitted successfully:', result)
        console.log('[Participant] Investment record:', result.investment)
        console.log('[Participant] Remaining money:', result.remaining_money)
        // The WebSocket broadcast will update the UI automatically
        // But we also refresh to ensure consistency
        await fetchParticipants()
        // Show success message after a brief delay to allow UI to update
        setTimeout(() => {
          alert(`Investment submitted successfully! Remaining money: $${result.remaining_money}`)
        }, 100)
      } else {
        console.error('[Participant] Investment submission failed:', result.error)
        alert(result.error || 'Failed to submit investment')
      }
    } catch (error) {
      console.error('[Participant] Error submitting investment:', error)
      alert('Error submitting investment. Please try again.')
    }
  }
}

onMounted(async () => {
  // 1) Session first so experiment type is correct (Map Task header role / participant_role persistence)
  await fetchSessionConfig()
  // 2) Fetch participants (applies interface)
  await fetchParticipants()

  // 4) Also try to apply config from sessionStorage if fetchParticipants didn't work
  const raw = sessionStorage.getItem('participant_interface')
  if (raw) {
    try {
      const savedInterface = JSON.parse(raw)
      console.log('[Participant] Applying interface from sessionStorage:', savedInterface)
      applyInterface(savedInterface)
    } catch (e) {
      console.error('Failed to parse participant_interface from sessionStorage', e)
    }
  }
  
  // 5) Fetch trade data initially
  await fetchTradeData()
  
  // Note: Trade data updates are now handled via WebSocket broadcasts (participants_updated with update_type='trade_update')
  // No need for polling interval anymore

  // 3) Ensure websocket is initialized and connected (single socket instance)
  const ws = initWebSocket()

  // Wait for websocket connection (clean timeout that doesn't fire after connect)
  if (!ws.connected) {
    await new Promise((resolve) => {
      const timeoutId = setTimeout(() => {
        console.warn('[Participant] WebSocket connection timeout')
        ws.off('connect', onConnect)
        resolve()
      }, 5000)

      const onConnect = () => {
        clearTimeout(timeoutId)
        console.log('[Participant] WebSocket connected')
        resolve()
      }

      ws.once('connect', onConnect)
    })
  }
  
  // 4) Register listener FIRST (so we don't miss early events), then join
  // Use session_id (UUID) for websocket room, not session_name
  let sessionIdForWebSocket = sessionId.value
  if (!sessionIdForWebSocket && sessionName.value) {
    // Try to fetch session_id from session_name if available
    try {
      const encodedSessionName = encodeURIComponent(sessionName.value)
      const response = await fetch(`/api/sessions/${encodedSessionName}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })
      if (response.ok) {
        const sessionData = await response.json()
        sessionIdForWebSocket = sessionData.session_id || sessionData.id
        if (sessionIdForWebSocket) {
          sessionId.value = sessionIdForWebSocket
          sessionStorage.setItem('session_id', sessionIdForWebSocket)
        }
      }
    } catch (error) {
      console.error('[Participant] Error fetching session_id:', error)
    }
  }
  
  if (sessionIdForWebSocket) {
    try {
      // Register listener before joining to avoid missing early events
      if (!cleanupParticipantsListener) {
        cleanupParticipantsListener = onParticipantsUpdate(participantsUpdateHandler)
        console.log('[Participant] WebSocket listener registered for participants_updated')
      }

      // Wait for join confirmation
      await joinSession(sessionIdForWebSocket, 'participant')
      console.log('[Participant] Successfully joined session:', sessionIdForWebSocket)
      
      // Register message listener
      if (!cleanupMessageListener) {
        cleanupMessageListener = onMessageReceived(handleMessageReceived)
        console.log('[Participant] Registered message_received listener')
      }
      
      // Register timer update listener
      if (!cleanupTimerListener) {
        const ws = getSocket()
        const timerUpdateHandler = (data) => {
          // Check if this update is for the current session
          if (data.session_id && data.session_id !== sessionIdForWebSocket) {
            return
          }
          
            // Update timer display
          if (data.remaining_seconds !== undefined && data.remaining_seconds !== null) {
            const totalSeconds = data.remaining_seconds
            const minutes = Math.floor(totalSeconds / 60)
            const seconds = totalSeconds % 60
            timerDisplay.value = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
            
            // Check if session has ended (timer reached 0)
            if (totalSeconds === 0 && !sessionEnded.value) {
              sessionEnded.value = true
              console.log('[Participant] Session ended, checking for final vote')
              // Show final vote popup if configured
              // Handle both string and boolean values for visible_if
              const finalVoteVisibleIf = finalVoteConfig.value?.visible_if
              const shouldShowFinalVote = (
                finalVoteConfig.value && 
                (finalVoteVisibleIf === 'on_end' || 
                 (finalVoteVisibleIf === true && finalVoteConfig.value.type === 'popup'))
              )
              console.log('[Participant] Should show final vote:', shouldShowFinalVote, 'visible_if:', finalVoteVisibleIf, 'finalVoteSubmitted:', finalVoteSubmitted.value)
              if (shouldShowFinalVote && !finalVoteSubmitted.value) {
                console.log('[Participant] Showing final vote popup')
                showFinalVote.value = true
                loadCandidateNames()
                // Notify backend that vote popup is shown (for agent voting)
                notifyVotePopupShown('final')
              } else {
                // No final vote to show - navigate to post-annotation if enabled
                navigateToPostAnnotationIfNeeded()
              }
            }
            
            // Update session status if timer is paused
            if (data.is_paused && sessionStatus.value === 'running') {
              sessionStatus.value = 'paused'
              sessionStatusMessage.value = 'Paused'
            } else if (data.is_running && !data.is_paused && sessionStatus.value === 'paused') {
              sessionStatus.value = 'running'
              sessionStatusMessage.value = 'Running'
            }
          }
        }
        ws.on('timer_update', timerUpdateHandler)
        cleanupTimerListener = () => {
          ws.off('timer_update', timerUpdateHandler)
        }
        console.log('[Participant] Registered timer_update listener')
      }

      // Register annotation popup listener
      if (!cleanupAnnotationListener) {
        const annotationPopupHandler = (data) => {
          if (data.session_id && data.session_id !== sessionIdForWebSocket) return
          const myId = sessionStorage.getItem('participant_id')
          if (data.human_participant_ids && !data.human_participant_ids.includes(myId)) return
          annotationWaitingForPartners.value = false
          showAnnotationPopup.value = true
          annotationCheckpoint.value = data.checkpoint_index ?? 0
          sessionStatus.value = 'paused'
          sessionStatusMessage.value = 'Paused'
        }
        const annotationResumeHandler = (data) => {
          if (data.session_id && data.session_id !== sessionIdForWebSocket) return
          annotationWaitingForPartners.value = false
          showAnnotationPopup.value = false
          sessionStatus.value = 'running'
          sessionStatusMessage.value = 'Running'
        }
        ws.on('annotation_popup', annotationPopupHandler)
        ws.on('annotation_resume', annotationResumeHandler)
        cleanupAnnotationListener = () => {
          ws.off('annotation_popup', annotationPopupHandler)
          ws.off('annotation_resume', annotationResumeHandler)
        }
        console.log('[Participant] Registered annotation_popup and annotation_resume listeners')
      }
      
      // Load existing messages from session
      try {
        const sessionIdentifier = sessionName.value || sessionIdForWebSocket
        const encodedSessionName = encodeURIComponent(sessionIdentifier)
        const response = await fetch(`/api/sessions/${encodedSessionName}`, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' }
        })
        if (response.ok) {
          const session = await response.json()
          // Update interaction config from session
          if (session.interaction) {
            interactionConfig.value = session.interaction
            console.log('[Participant] Updated interaction config:', interactionConfig.value)
          } else if (session.experiment_config?.interaction) {
            interactionConfig.value = session.experiment_config.interaction
            console.log('[Participant] Updated interaction config from experiment_config:', interactionConfig.value)
          }
          
          // Load existing messages from session
          if (session.messages && Array.isArray(session.messages)) {
            console.log(`[Participant] Loading ${session.messages.length} existing messages from session`)
            // Process each message
            session.messages.forEach(message => {
              handleMessageReceived(message)
            })
          }
        }
      } catch (error) {
        console.error('[Participant] Error fetching session messages:', error)
      }
      
      // Debug: Check socket state
      const activeWs = getSocket()
      console.log('[Participant] Socket state:', {
        connected: activeWs.connected,
        socketId: activeWs.id,
        hasRooms: typeof activeWs.rooms === 'function' ? activeWs.rooms() : 'N/A'
      })
    } catch (error) {
      console.error('[Participant] Error joining session:', error)
    }
  } else {
    console.warn('[Participant] No sessionId available, cannot join session')
  }
})

// Cleanup on component unmount
onUnmounted(() => {
  // Clean up reading timer
  if (readingTimerInterval.value) {
    clearInterval(readingTimerInterval.value)
    readingTimerInterval.value = null
  }
  
  // Clean up auto start interval
  if (autoStartInterval.value) {
    clearInterval(autoStartInterval.value)
    autoStartInterval.value = null
  }
  
  // Clean up WebSocket listeners
  // Note: tradeDataInterval is no longer used (replaced by WebSocket broadcasts)
  if (cleanupParticipantsListener) {
    cleanupParticipantsListener()
    cleanupParticipantsListener = null
    console.log('[Participant] Cleaned up WebSocket listener')
  }
  if (cleanupMessageListener) {
    cleanupMessageListener()
    cleanupMessageListener = null
    console.log('[Participant] Cleaned up message listener')
  }
  if (cleanupTimerListener) {
    cleanupTimerListener()
    cleanupTimerListener = null
    console.log('[Participant] Cleaned up timer listener')
  }
  if (cleanupAnnotationListener) {
    cleanupAnnotationListener()
    cleanupAnnotationListener = null
    console.log('[Participant] Cleaned up annotation listener')
  }
})
</script>

<template>
  <!-- Header -->
  <header class="header-row">
    <div class="header-left">
        <div class="current-session-display">
          <div class="session-label">Session: {{ sessionName || sessionId }}</div>
        </div>
        <span class="tooltip-wrapper">
          <button @click="showRulesPopup" class="rules-btn">Rules</button>
          <span class="tooltip-icon" @mouseenter="showTooltip('rules', $event)" @mousemove="updateTooltipPosition" @mouseleave="hideTooltip">ⓘ</span>
        </span>
        <span v-if="mapTaskRoleForHeader" class="header-role-wrap">
          <span class="header-role-prefix">You are:</span>
          <span
            class="header-role-tag"
            :class="headerRoleBadgeClass"
            @mouseenter="showTooltip('role', $event)"
            @mousemove="updateTooltipPosition"
            @mouseleave="hideTooltip"
          >{{ mapTaskRoleHeaderPretty }}</span>
        </span>
      </div>
      <div class="header-center">
        <div class="timer-display">
          <div class="timer-value">{{ timerDisplay }}</div>
        </div>
        <span class="tooltip-wrapper">
          <div class="session-status-indicator" :class="sessionStatus">
            <span class="status-text">{{ sessionStatusMessage }}</span>
          </div>
          <span class="tooltip-icon" @mouseenter="showTooltip('sessionStatus', $event)" @mousemove="updateTooltipPosition" @mouseleave="hideTooltip">ⓘ</span>
        </span>
      </div>
      <div class="header-right">

        <button @click="logout" class="login-toggle-btn">Logout</button>
      </div>
  </header>

  <!-- Tooltip -->
  <div v-if="activeTooltip" class="custom-tooltip" :style="{ left: tooltipPosition.x + 'px', top: tooltipPosition.y + 'px' }">
    {{ tooltipContent[activeTooltip] }}
  </div>

  <!-- Main -->
  <main>
    <!-- Three Column Layout -->
    <div class="main-container">
      <div class="participant-column">
        <myStatus :config="myStatusConfig" />
        <myActions :config="myActionsConfig" @submit="handleInvestmentSubmit" />
        <myTasks
          :key="`my-tasks-${myTasksConfig?.id || 'default'}-${(myTasksConfig?.bindings?.length ?? 0)}`"
          :config="myTasksConfig"
        />
      </div>
      <div class="social_panel">
        <SocialPanel 
          :config="socialPanelConfig" 
          :participants-list="allParticipants"
          :participants="participantsMap"
          :conversations="conversations"
          :comm-level="commLevel"
          :message-length-limit="messageLengthLimit"
          :communication-media="communicationMedia"
          :type-indicator-enabled="typeIndicatorEnabled"
          :pending-offers="pendingOffers"
          :completed-trades="completedTrades"
          @submit-trade="handleTradeSubmit"
          @offer-updated="fetchTradeData"
        />
      </div>
      <div
        v-if="infoDashboardConfig.visible_if === true || infoDashboardConfig.visible_if === 'true'"
        class="info_panel"
      >
        <InfoDashboard :config="infoDashboardConfig" :participants="allParticipants" />
      </div>
    </div>
  </main>

  <!-- Reading Window Popup -->
  <DocPreview 
    v-if="showReadingWindow && readingWindowConfig"
    :show="showReadingWindow"
    :essay="candidateDocument"
    mode="reading_window"
    :label="readingWindowConfig.label || 'Reading Window'"
    :reading-time-remaining="readingTimeRemaining"
    :allow-close="false"
    @close="() => {}"
  />

  <!-- Initial Vote Popup -->
  <ActionDialog
    v-if="showInitialVote && initialVoteConfig"
    :show="showInitialVote"
    dialog-type="vote"
    :label="initialVoteConfig.label || 'Initial Vote'"
    :vote-label="initialVoteConfig.bindings?.[0]?.label || 'Please select your preferred candidate'"
    :vote-options="candidateNames"
    v-model:selectedValue="selectedCandidate"
    :is-submitting="isSubmittingVote"
    @close="() => { if (!isSubmittingVote) showInitialVote = false }"
    @submit="submitInitialVote"
  />

  <!-- Final Vote Popup -->
  <ActionDialog
    v-if="showFinalVote && finalVoteConfig"
    :show="showFinalVote"
    dialog-type="vote"
    :label="finalVoteConfig.label || 'Final Vote'"
    :vote-label="finalVoteConfig.bindings?.[0]?.label || 'Please select your preferred candidate'"
    :vote-options="candidateNames"
    v-model:selectedValue="selectedCandidate"
    :is-submitting="isSubmittingVote"
    @close="() => { if (!isSubmittingVote) showFinalVote = false }"
    @submit="submitFinalVote"
  />

  <!-- In-session Annotation Popup -->
  <AnnotationPopup
    v-if="showAnnotationPopup"
    :show="showAnnotationPopup"
    :checkpoint-index="annotationCheckpoint"
    :waiting-for-partners="annotationWaitingForPartners"
    @submit="submitAnnotation"
  />

  <!-- Auto Start Popup -->
  <div v-if="showAutoStartPopup" class="modal-overlay auto-start-overlay" @click="closeAutoStartPopup">
    <div class="modal-content auto-start-modal" @click.stop>
      <div class="modal-header">
        <h3>Session Starting</h3>
      </div>
      <div class="modal-body">
        <div class="auto-start-content">
          <div class="countdown-display">
            <div class="countdown-number">{{ autoStartCountdown }}</div>
            <div class="countdown-label">seconds</div>
          </div>
          <p class="auto-start-message">{{ autoStartMessage }}</p>
          <div class="auto-start-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${autoStartProgress}%` }"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.main-container {
  display: flex;
  flex-direction: row;
  gap: 10px;
  width: 100%;
  height: 100%;
  flex: 1;
  overflow: hidden;
}

.participant-column {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  height: calc(100vh - 90px);
  flex: 2;
  overflow: auto;
}

.social_panel {
  flex: 3;
  display: flex;
  flex-direction: row;
  height: calc(100vh - 90px);
  min-height: 0;
  overflow: hidden;
  padding-bottom: 12px;
  box-sizing: border-box;
}

.info_panel {
  flex: 2;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: calc(100vh - 90px);
}

.header-left, .header-center{
  display: flex;
  flex-direction: row;
  gap: 8px;
  align-items: center;
}

/* Map Task: "You are:" plain + role pill */
.header-role-wrap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.header-role-prefix {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  white-space: nowrap;
}

/* Map Task: role pill next to Rules (matches social_panel / awareness role badges) */
.header-role-tag {
  flex-shrink: 0;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  cursor: default;
}

.header-role-tag.guider {
  background: #dbeafe;
  color: #1d4ed8;
}

.header-role-tag.follower {
  background: #d1fae5;
  color: #047857;
}

.header-role-tag.role-other {
  background: #f3f4f6;
  color: #374151;
}

/* Session Status Indicator */
.session-status-indicator {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.session-status-indicator.idle {
  background-color: #f8f9fa;
  color: #6c757d;
  border: 1px solid #dee2e6;
}

.session-status-indicator.running {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.session-status-indicator.paused {
  background-color: #fff3cd;
  color: #856404;
  border: 1px solid #ffeaa7;
}

.session-status-indicator.completed {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.session-status-indicator.stopped {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.session-status-indicator.ended {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.status-text {
  font-size: 11px;
}

/* Popup Styles */
.popup-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 20px;
}

.popup-container {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
  border-radius: 8px 8px 0 0;
}

.popup-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.popup-timer {
  font-size: 14px;
  font-weight: 600;
  color: #3b82f6;
}

.popup-content {
  flex: 1;
  padding: 20px;
  overflow: auto;
}

.popup-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #6b7280;
}

.vote-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vote-form label {
  font-size: 16px;
  font-weight: 500;
  color: #111827;
}

.vote-select {
  padding: 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  width: 100%;
}

.popup-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

.btn-primary {
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-primary:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

/* Auto Start Popup Styles */
.auto-start-overlay {
  z-index: 10001;
}

.auto-start-modal {
  max-width: 400px;
  text-align: center;
}

.auto-start-content {
  padding: 20px;
}

.countdown-display {
  margin-bottom: 24px;
}

.countdown-number {
  font-size: 64px;
  font-weight: 700;
  color: #3b82f6;
  line-height: 1;
  margin-bottom: 8px;
}

.countdown-label {
  font-size: 14px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.auto-start-message {
  font-size: 16px;
  color: #111827;
  margin-bottom: 24px;
}

.auto-start-progress {
  width: 100%;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background-color: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
  border-radius: 4px;
  transition: width 0.3s ease;
}

/* Tooltip styles */
.tooltip-wrapper {
  display: inline-flex;
  align-items: center;
  position: relative;
}

.tooltip-icon {
  margin-left: 4px;
  cursor: help;
  color: #6b7280;
  font-size: 12px;
}

.tooltip-icon:hover {
  color: #374151;
}

.custom-tooltip {
  position: fixed;
  background: #374151;
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  max-width: 250px;
  z-index: 1000;
  pointer-events: none;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  line-height: 1.4;
}

</style>
