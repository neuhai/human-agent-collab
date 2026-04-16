import { io } from 'socket.io-client'

// WebSocket connection instance
let socket = null

// Initialize WebSocket connection
export function initWebSocket() {
  if (socket && socket.connected) {
    return socket
  }

  // Socket.IO target:
  // - explicit VITE_BACKEND_URL if provided
  // - Vite dev server -> Flask :5000
  // - production build -> same origin via nginx proxy (/socket.io)
  const envUrl = import.meta.env.VITE_BACKEND_URL
  const trimmedEnvUrl = typeof envUrl === 'string' ? envUrl.trim() : ''
  const backendUrl =
    trimmedEnvUrl !== ''
      ? trimmedEnvUrl
      : import.meta.env.DEV
        ? 'http://localhost:5000'
        : null
  
  // Backend uses Flask-SocketIO with `async_mode='threading'` (see backend/app.py).
  // In that mode, WebSocket transport is not reliably supported and can trigger
  // 500s on `/socket.io/?transport=websocket`, causing clients to disconnect and
  // miss critical emits (e.g. `annotation_popup`). Force long-polling for stability.
  const socketOptions = {
    path: '/socket.io',
    transports: ['polling'],
    upgrade: false,
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 10
  }

  socket = backendUrl ? io(backendUrl, socketOptions) : io(socketOptions)

  // Connection event handlers
  socket.on('connect', () => {
    console.log('WebSocket connected:', socket.id)
  })

  socket.on('disconnect', () => {
    console.log('WebSocket disconnected')
  })

  socket.on('connect_error', (error) => {
    console.error('WebSocket connection error:', error)
    if (typeof window !== 'undefined' && window.location.protocol === 'https:' && backendUrl?.startsWith('http://')) {
      console.warn(
        '[WebSocket] HTTPS page is trying to reach an explicit HTTP backend URL:',
        backendUrl,
        'This often breaks polling with SSL/protocol errors. Prefer same-origin proxying or an HTTPS backend URL.',
      )
    }
    if (typeof window !== 'undefined' && String(error?.message || '').includes('xhr poll')) {
      console.warn(
        '[WebSocket] Polling failed — nothing is accepting connections at',
        backendUrl || `${window.location.origin}/socket.io`,
        '(e.g. Docker frontend/backend stopped, or `vite preview` without proxy). Map chat uses HTTP log_action; real-time events need a running Socket.IO server.',
      )
    }
  })
  
  // Debug: Log all received events (enable only when needed)
  // if (socket.onAny) {
  //   socket.onAny((eventName, ...args) => {
  //     console.log('[WebSocket DEBUG] Received event:', eventName, args)
  //   })
  // }

  return socket
}

// Get current socket instance
export function getSocket() {
  if (!socket || !socket.connected) {
    return initWebSocket()
  }
  return socket
}

// Join a session room (returns a Promise that resolves when join is confirmed)
export function joinSession(sessionId, role = 'researcher') {
  return new Promise((resolve, reject) => {
  const ws = getSocket()
    
    // Set up one-time listener for join confirmation
    const onJoined = (data) => {
      // Server always replies with the actual session_id (UUID) used as room id.
      // The caller might provide a session_name; don't treat that as a failure.
      ws.off('joined_session', onJoined)
      ws.off('error', onError)
      const actualSessionId = data?.session_id || sessionId
      console.log(`[WebSocket] Successfully joined session: ${actualSessionId} as ${role} (requested: ${sessionId})`)
      resolve({ ...data, session_id: actualSessionId, requested_session_id: sessionId })
    }
    
    const onError = (error) => {
      ws.off('joined_session', onJoined)
      ws.off('error', onError)
      console.error(`[WebSocket] Error joining session ${sessionId}:`, error)
      reject(error)
    }
    
    ws.once('joined_session', onJoined)
    ws.once('error', onError)
    
    // Emit join request
  ws.emit('join_session', {
    session_id: sessionId,
    role: role
  })
    console.log(`[WebSocket] Joining session: ${sessionId} as ${role}`)
    
    // Timeout after 5 seconds
    setTimeout(() => {
      ws.off('joined_session', onJoined)
      ws.off('error', onError)
      reject(new Error('Join session timeout'))
    }, 5000)
  })
}

// Leave a session room
export function leaveSession(sessionId) {
  if (socket && socket.connected) {
    socket.emit('leave_session', {
      session_id: sessionId
    })
    console.log(`Left session: ${sessionId}`)
  }
}

// Disconnect WebSocket
export function disconnectWebSocket() {
  if (socket) {
    socket.disconnect()
    socket = null
    console.log('WebSocket disconnected')
  }
}

// Store callbacks for cleanup
const participantsUpdateCallbacks = new Map()

// Listen for participant updates in a session
export function onParticipantsUpdate(callback) {
  const ws = getSocket()
  
  // Create a unique wrapper to track this callback
  const wrappedCallback = (data) => {
    console.log('[WebSocket] Received participants_updated event:', {
      hasData: !!data,
      hasParticipants: !!data?.participants,
      participantsCount: data?.participants?.length || 0,
      updateType: data?.update_type,
      sessionId: data?.session_id,
      fullData: data
    })
    try {
      callback(data)
    } catch (error) {
      console.error('[WebSocket] Error in participants_updated callback:', error)
    }
  }
  
  // Store the mapping for cleanup
  participantsUpdateCallbacks.set(callback, wrappedCallback)
  
  // Register the listener
  ws.on('participants_updated', wrappedCallback)
  console.log('[WebSocket] Registered participants_updated listener, total listeners:', ws.listeners('participants_updated').length)
  
  return () => {
    // Return cleanup function
    if (ws) {
      const storedWrapper = participantsUpdateCallbacks.get(callback)
      if (storedWrapper) {
        ws.off('participants_updated', storedWrapper)
        participantsUpdateCallbacks.delete(callback)
        console.log('[WebSocket] Removed participants_updated listener')
      }
    }
  }
}

// Remove participant update listener
export function offParticipantsUpdate(callback) {
  if (socket && socket.connected) {
    const storedWrapper = participantsUpdateCallbacks.get(callback)
    if (storedWrapper) {
      socket.off('participants_updated', storedWrapper)
      participantsUpdateCallbacks.delete(callback)
      console.log('[WebSocket] Removed participants_updated listener via offParticipantsUpdate')
    }
  }
}

// Send a message via WebSocket
// options: { messageType?: 'text'|'audio', audioUrl?: string, duration?: number, screenshot?: string, html_snapshot?: string }
export function sendMessage(sessionId, sender, receiver, content, options = {}) {
  const ws = getSocket()
  if (!ws || !ws.connected) {
    console.error('[WebSocket] Cannot send message: not connected')
    return Promise.reject(new Error('WebSocket not connected'))
  }
  
  return new Promise((resolve, reject) => {
    let resolved = false
    let timeoutId = null
    
    const cleanup = () => {
      if (timeoutId) {
        clearTimeout(timeoutId)
        timeoutId = null
      }
      ws.off('message_sent', onSent)
      ws.off('error', onError)
    }
    
    const onSent = (data) => {
      if (resolved) return
      resolved = true
      cleanup()
      console.log('[WebSocket] Message sent successfully:', data)
      resolve(data)
    }
    
    const onError = (error) => {
      if (resolved) return
      resolved = true
      cleanup()
      console.error('[WebSocket] Error sending message:', error)
      reject(error)
    }
    
    // Register listeners BEFORE emitting
    ws.once('message_sent', onSent)
    ws.once('error', onError)
    
    // Emit the message
    const messageData = {
      session_id: sessionId,
      sender: sender,
      receiver: receiver,  // null for group chat
      content: content
    }
    if (options.messageType === 'audio') {
      messageData.message_type = 'audio'
      messageData.audio_url = options.audioUrl || ''
      messageData.duration = options.duration || 0
    }
    if (options.screenshot) messageData.screenshot = options.screenshot
    if (options.html_snapshot) messageData.html_snapshot = options.html_snapshot
    if (options.clientTimestamp) messageData.client_timestamp = options.clientTimestamp
    
    console.log('[WebSocket] Emitting send_message event:', messageData)
    console.log('[WebSocket] Socket connected:', ws.connected)
    console.log('[WebSocket] Socket ID:', ws.id)
    console.log('[WebSocket] Socket transport:', ws.io?.engine?.transport?.name)
    
    // Test: Try emitting a ping first to verify connection
    ws.emit('ping', {}, (response) => {
      console.log('[WebSocket] Ping response:', response)
    })
    
    // Emit the message (without callback, wait for message_sent event instead)
    console.log('[WebSocket] About to emit send_message...')
    ws.emit('send_message', messageData)
    console.log('[WebSocket] send_message event emitted, waiting for message_sent event')
    
    // Timeout after 10 seconds (increased from 5)
    timeoutId = setTimeout(() => {
      if (resolved) return
      resolved = true
      cleanup()
      console.error('[WebSocket] Send message timeout after 10s')
      reject(new Error('Send message timeout'))
    }, 10000)
  })
}

// Store callbacks for message received listeners
const messageReceivedCallbacks = new Map()

// Listen for incoming messages
export function onMessageReceived(callback) {
  const ws = getSocket()
  
  // Create a unique wrapper to track this callback
  const wrappedCallback = (message) => {
    console.log('[WebSocket] Received message_received event:', message)
    try {
      callback(message)
    } catch (error) {
      console.error('[WebSocket] Error in message_received callback:', error)
    }
  }
  
  // Store the mapping for cleanup
  messageReceivedCallbacks.set(callback, wrappedCallback)
  
  // Register the listener
  ws.on('message_received', wrappedCallback)
  console.log('[WebSocket] Registered message_received listener')
  
  return () => {
    // Return cleanup function
    if (ws) {
      const storedWrapper = messageReceivedCallbacks.get(callback)
      if (storedWrapper) {
        ws.off('message_received', storedWrapper)
        messageReceivedCallbacks.delete(callback)
        console.log('[WebSocket] Removed message_received listener')
      }
    }
  }
}

// Remove message received listener
export function offMessageReceived(callback) {
  if (socket && socket.connected) {
    const storedWrapper = messageReceivedCallbacks.get(callback)
    if (storedWrapper) {
      socket.off('message_received', storedWrapper)
      messageReceivedCallbacks.delete(callback)
      console.log('[WebSocket] Removed message_received listener via offMessageReceived')
    }
  }
}

/** Fire-and-forget typing indicator (participants must only emit when experiment enables it). */
export function emitTypingIndicator(sessionId, sender, receiver, isTyping) {
  const ws = getSocket()
  if (!ws?.connected) return
  ws.emit('typing_indicator', {
    session_id: sessionId,
    sender,
    receiver: receiver ?? null,
    is_typing: !!isTyping,
  })
}

const typingIndicatorCallbacks = new Map()

export function onTypingIndicator(callback) {
  const ws = getSocket()
  const wrapped = (payload) => {
    try {
      callback(payload)
    } catch (error) {
      console.error('[WebSocket] Error in typing_indicator callback:', error)
    }
  }
  typingIndicatorCallbacks.set(callback, wrapped)
  ws.on('typing_indicator', wrapped)
  return () => {
    const w = typingIndicatorCallbacks.get(callback)
    if (w && ws) {
      ws.off('typing_indicator', w)
      typingIndicatorCallbacks.delete(callback)
    }
  }
}

export function offTypingIndicator(callback) {
  if (!socket?.connected) return
  const w = typingIndicatorCallbacks.get(callback)
  if (w) {
    socket.off('typing_indicator', w)
    typingIndicatorCallbacks.delete(callback)
  }
}

// Export socket for direct access if needed
export { socket }

