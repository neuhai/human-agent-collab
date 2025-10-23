<template>
  <div class="ecl-interface">
    <!-- ECL Header -->
    <header class="ecl-header">
      <div class="ecl-header-left">
        <span class="session-label">Session ID: <span>{{ sessionId }}</span></span>
        <button @click="showRulesPopup" class="rules-btn">Rules</button>
      </div>
      <div class="ecl-header-center">
        <span class="timer-display">{{ timerDisplay }}</span>
        <div class="session-status-indicator" :class="sessionStatus">
          <span class="status-text">{{ sessionStatusMessage }}</span>
        </div>
      </div>
      <div class="ecl-header-right">
        <button @click="logout" class="login-toggle-btn">Logout</button>
      </div>
    </header>

    <!-- ECL Rules Popup -->
    <div v-show="showRules" class="rules-popup" @click="hideRulesIfClickedOutside">
      <div class="rules-popup-content">
        <div class="rules-popup-header">
          <h3>{{ eclConfig.experiment?.title || 'Experiment Rules' }}</h3>
          <button @click="hideRulesPopup" class="close-rules-btn">×</button>
        </div>
        <div class="rules-popup-body">
          <p><strong>Description:</strong> {{ eclConfig.experiment?.description || 'No description available.' }}</p>
          <div v-if="eclConfig.experiment?.timing">
            <p><strong>Duration:</strong> {{ eclConfig.experiment.timing.session_duration_minutes }} minutes</p>
          </div>
          <div v-if="eclConfig.actions">
            <p><strong>Available Actions:</strong></p>
            <ul>
              <li v-for="(action, name) in eclConfig.actions" :key="name">
                <strong>{{ name }}:</strong> {{ action.description || 'No description available' }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- Session Status Overlay -->
    <Transition name="session-overlay" mode="out-in">
      <div v-if="!isSessionActive" class="session-overlay" key="session-overlay">
        <div class="session-overlay-content">
          <div class="session-overlay-icon">⏸️</div>
          <h3>{{ sessionStatusMessage }}</h3>
          <p v-if="stableSessionStatus === 'completed' || stableSessionStatus === 'stopped' || stableSessionStatus === 'ended'">
            The session has ended. Thank you for participating!
          </p>
          <p v-else>
            Please wait for the researcher to start the session.
          </p>
          
          <div v-if="stableSessionStatus === 'completed' || stableSessionStatus === 'ended'" class="session-overlay-actions">
            <button @click="returnToLogin" class="return-to-login-btn">
              Return to Login
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ECL Main Content -->
    <Transition name="content-disabled" mode="out-in">
      <div class="ecl-main-content" :class="{ 'disabled-content': !isSessionActive }" key="main-content">
        <!-- Dynamic ECL Modules -->
        <div class="main-content">
          <div class="column column-left">
            <div class="left-sub-column">
              <div 
                v-for="(module, moduleName) in visibleModules" 
                :key="moduleName"
                v-show="evaluateVisibility(module.visible_if)"
                class="panel"
                :class="`${moduleName}-panel`"
              >
                <h3 class="panel-header">{{ module.label }}</h3>
                <div class="panel-body">
              <!-- Dynamic Components -->
              <div 
                v-for="(component, index) in module.components" 
                :key="index"
                class="ecl-component"
                :class="`component-${component.type}`"
              >
                <!-- Text Display Component -->
                <div v-if="component.type === 'text-display'" class="wealth-display">
                  <div class="component-module">
                    <span class="component-text">{{ component.props.label }}:</span>
                    <span class="component-num">{{ evaluatePath(component.props.path) }}</span>
                  </div>
                </div>

                <!-- Number Input Component -->
                <div v-else-if="component.type === 'number-input'" class="factory-info">
                  <label class="component-text">{{ component.props.label }}</label>
                  <input 
                    type="number" 
                    v-model="localState[component.props.bind_to]"
                    :min="component.props.min"
                    :max="component.props.max"
                    :step="component.props.step"
                    class="production-dropdown"
                    :disabled="!isSessionActive"
                  />
                </div>

                <!-- Select Input Component -->
                <div v-else-if="component.type === 'select-input'" class="factory-info">
                  <label class="component-text">{{ component.props.label }}</label>
                  <select 
                    v-model="localState[component.props.bind_to]" 
                    class="production-dropdown"
                    :disabled="!isSessionActive"
                  >
                    <option v-for="option in component.props.options" :key="option" :value="option">
                      {{ option }}
                    </option>
                  </select>
                </div>

                <!-- Segmented Control Component -->
                <div v-else-if="component.type === 'segmented-control'" class="factory-info">
                  <label class="component-text">{{ component.props.label }}</label>
                  <div class="production-controls">
                    <button 
                      v-for="option in component.props.options" 
                      :key="option"
                      type="button" 
                      :class="{ active: localState[component.props.bind_to] === option }" 
                      @click="localState[component.props.bind_to] = option"
                      :disabled="!isSessionActive"
                      class="btn secondary"
                    >
                      {{ option }}
                    </button>
                  </div>
                </div>

                <!-- Action Button Component -->
                <div v-else-if="component.type === 'action-button'" class="factory-info">
                  <button 
                    type="button" 
                    @click="executeAction(component.props.action, component.props.inputs)"
                    class="btn primary"
                    :disabled="!isSessionActive"
                  >
                    {{ component.props.label }}
                  </button>
                </div>

                <!-- Data List Component -->
                <div v-else-if="component.type === 'data-list'" class="inventory-section">
                  <h4 class="component-text">{{ component.props.label }}</h4>
                  <div class="component-list">
                    <div 
                      v-for="(item, index) in evaluatePath(component.props.path)" 
                      :key="index"
                      class="component-list-item"
                    >
                      <div class="component-text">{{ item }}</div>
                    </div>
                  </div>
                </div>

                <!-- Communication Module -->
                <div v-else-if="module.communication_level" class="factory-info">
                  <div v-if="module.communication_level === 'group_chat'" class="social-panel">
                    <h4 class="component-text">Group Chat</h4>
                    <div class="chat-messages">
                      <div 
                        v-for="message in messages" 
                        :key="message.id"
                        class="chat-message"
                        :class="{ 'own-message': message.sender === participantCode }"
                      >
                        <strong>{{ message.sender }}:</strong> {{ message.content }}
                      </div>
                    </div>
                    <div class="chat-input">
                      <input 
                        v-model="newMessage" 
                        @keyup.enter="sendMessage"
                        placeholder="Type your message..."
                        class="message-input"
                        :disabled="!isSessionActive"
                      />
                      <button @click="sendMessage" class="btn primary" :disabled="!isSessionActive">
                        Send
                      </button>
                    </div>
                  </div>
                </div>
              </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import io from 'socket.io-client'
import { BACKEND_URL } from '../config.js'

export default {
  name: 'ECLInterface',
  props: {
    sessionId: {
      type: String,
      required: true
    },
    participantCode: {
      type: String,
      required: true
    }
  },
  setup(props) {
    const router = useRouter()
    
    // Reactive state
    const showRules = ref(false)
    const isSessionActive = ref(false)
    const sessionStatus = ref('idle')
    const sessionStatusMessage = ref('Session not started')
    const timerDisplay = ref('00:00')
    const stableSessionStatus = ref('idle')
    
    // ECL-specific state
    const eclConfig = ref({})
    const eclState = ref({})
    const localState = ref({})
    const messages = ref([])
    const newMessage = ref('')
    
    // Socket connection
    let socket = null
    
    // Computed properties
    const visibleModules = computed(() => {
      console.log('🔧 visibleModules computed - eclConfig.value.views:', eclConfig.value.views)
      if (!eclConfig.value.views) {
        console.log('🔧 No views found in eclConfig')
        return {}
      }
      
      const visible = {}
      for (const [moduleName, views] of Object.entries(eclConfig.value.views)) {
        console.log(`🔧 Processing module ${moduleName}:`, views)
        if (views && views.length > 0) {
          const view = views[0]
          visible[moduleName] = {
            label: view.label,
            visible_if: view.visible_if,
            components: view.bindings || [],
            communication_level: view.communication_level
          }
        }
      }
      console.log('🔧 Final visible modules:', visible)
      return visible
    })
    
    // Methods
    const showRulesPopup = () => {
      showRules.value = true
    }
    
    const hideRulesPopup = () => {
      showRules.value = false
    }
    
    const hideRulesIfClickedOutside = (event) => {
      if (event.target.classList.contains('rules-popup')) {
        hideRulesPopup()
      }
    }
    
    const logout = () => {
      if (socket) {
        socket.disconnect()
      }
      router.push('/participant-login')
    }
    
    const returnToLogin = () => {
      router.push('/participant-login')
    }
    
    const evaluateVisibility = (condition) => {
      if (!condition || condition === 'true') return true
      
      try {
        // Simple condition evaluation
        // Replace ECL expressions with JavaScript equivalents
        let jsCondition = condition
          .replace(/Session\.settled\('S'\)/g, 'eclState.value.session?.settled || false')
          .replace(/==/g, '===')
          .replace(/!=/g, '!==')
        
        return eval(jsCondition)
      } catch (error) {
        console.warn('Failed to evaluate visibility condition:', condition, error)
        return true
      }
    }
    
    const evaluatePath = (path) => {
      if (!path) return null
      
      try {
        // Simple path evaluation
        // This is a basic implementation - in production, you'd want a more robust evaluator
        if (path.startsWith('Participant.')) {
          const attr = path.split('.')[1]
          return eclState.value.participant?.[attr] || null
        } else if (path.startsWith('Session.')) {
          const attr = path.split('.')[1]
          return eclState.value.session?.[attr] || null
        } else if (path.startsWith('variables.')) {
          const varName = path.split('.')[1]
          return eclState.value.variables?.[varName] || null
        }
        
        return null
      } catch (error) {
        console.warn('Failed to evaluate path:', path, error)
        return null
      }
    }
    
    const executeAction = async (actionName, inputs) => {
      if (!isSessionActive.value) return
      
      try {
        // Prepare input values from local state
        const actionInputs = {}
        for (const input of inputs) {
          const value = localState.value[input.from.replace('$local.', '')]
          actionInputs[input.name] = value
        }
        
        const authToken = sessionStorage.getItem('auth_token')
        const response = await fetch(`${BACKEND_URL}/api/experiment/ecl/action`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
          body: JSON.stringify({
            session_code: props.sessionId,
            participant_code: props.participantCode,
            action: actionName,
            inputs: actionInputs
          })
        })
        
        const result = await response.json()
        
        if (result.success) {
          console.log('Action executed successfully:', result)
          // Refresh ECL state
          await loadECLState()
        } else {
          console.error('Action failed:', result.error)
          alert('Action failed: ' + result.error)
        }
      } catch (error) {
        console.error('Action execution error:', error)
        alert('Action error: ' + error.message)
      }
    }
    
    const sendMessage = async () => {
      if (!newMessage.value.trim() || !isSessionActive.value) return
      
      try {
        const authToken = sessionStorage.getItem('auth_token')
        const response = await fetch(`${BACKEND_URL}/api/send-message`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
          body: JSON.stringify({
            session_code: props.sessionId,
            participant_code: props.participantCode,
            recipient: 'all',
            content: newMessage.value.trim()
          })
        })
        
        const result = await response.json()
        
        if (result.success) {
          newMessage.value = ''
        } else {
          console.error('Failed to send message:', result.error)
        }
      } catch (error) {
        console.error('Message sending error:', error)
      }
    }
    
    const loadECLState = async () => {
      try {
        const authToken = sessionStorage.getItem('auth_token')
        const response = await fetch(`${BACKEND_URL}/api/experiment/ecl/state?session_code=${props.sessionId}&participant_code=${props.participantCode}`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        })
        const result = await response.json()
        
        if (result.success) {
          eclState.value = result.state
          // Extract participant and session data
          if (result.participant_state) {
            eclState.value.participant = result.participant_state
          }
        }
      } catch (error) {
        console.error('Failed to load ECL state:', error)
      }
    }
    
    const loadECLConfig = async () => {
      try {
        const authToken = sessionStorage.getItem('auth_token')
        const response = await fetch(`${BACKEND_URL}/api/experiment/config?session_code=${props.sessionId}`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        })
        const result = await response.json()
        
        if (result.success && result.config.experiment_type === 'custom_ecl') {
          // Load the full ECL configuration from the top level of the config
          eclConfig.value = {
            // Include metadata from ecl_config section
            ...(result.config.ecl_config || {}),
            // Include the actual ECL configuration data
            views: result.config.views || {},
            types: result.config.types || {},
            objects: result.config.objects || {},
            variables: result.config.variables || {},
            actions: result.config.actions || {},
            constraints: result.config.constraints || [],
            policies: result.config.policies || []
          }
          console.log('🔧 ECL Config loaded:', eclConfig.value)
          console.log('🔧 Views loaded:', eclConfig.value.views)
        }
      } catch (error) {
        console.error('Failed to load ECL config:', error)
      }
    }
    
    const loadTimerState = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/api/experiment/timer-state?session_code=${props.sessionId}`)
        const result = await response.json()
        
        if (result.experiment_status) {
          sessionStatus.value = result.experiment_status
          isSessionActive.value = result.experiment_status === 'running'
          stableSessionStatus.value = result.experiment_status
          
          if (result.experiment_status === 'running') {
            sessionStatusMessage.value = 'Session is active'
          } else if (result.experiment_status === 'paused') {
            sessionStatusMessage.value = 'Session is paused'
          } else if (result.experiment_status === 'completed' || result.experiment_status === 'stopped' || result.experiment_status === 'ended') {
            sessionStatusMessage.value = 'Session has ended'
          } else {
            sessionStatusMessage.value = 'Session not started'
          }
        }
        
        if (result.time_remaining) {
          const minutes = Math.floor(result.time_remaining / 60)
          const seconds = result.time_remaining % 60
          timerDisplay.value = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
        }
      } catch (error) {
        console.error('Failed to load timer state:', error)
      }
    }
    
    const initializeSocket = () => {
      socket = io()
      
      socket.on('connect', () => {
        console.log('Connected to server')
        socket.emit('register_participant', {
          session_code: props.sessionId,
          participant_code: props.participantCode
        })
      })
      
      socket.on('session_status_update', (data) => {
        if (data.session_code === props.sessionId) {
          sessionStatus.value = data.status
          sessionStatusMessage.value = data.message
          isSessionActive.value = data.status === 'running'
          stableSessionStatus.value = data.status
        }
      })
      
      socket.on('timer_update', (data) => {
        if (data.session_code === props.sessionId) {
          // Update timer display
          if (data.time_remaining !== undefined) {
            const minutes = Math.floor(data.time_remaining / 60)
            const seconds = data.time_remaining % 60
            timerDisplay.value = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
          }
          
          // Update session status based on experiment status
          if (data.experiment_status) {
            sessionStatus.value = data.experiment_status
            isSessionActive.value = data.experiment_status === 'running'
            stableSessionStatus.value = data.experiment_status
            
            if (data.experiment_status === 'running') {
              sessionStatusMessage.value = 'Session is active'
            } else if (data.experiment_status === 'paused') {
              sessionStatusMessage.value = 'Session is paused'
            } else if (data.experiment_status === 'completed' || data.experiment_status === 'stopped' || data.experiment_status === 'ended') {
              sessionStatusMessage.value = 'Session has ended'
            } else {
              sessionStatusMessage.value = 'Session not started'
            }
          }
        }
      })
      
      socket.on('ecl_state_updated', (data) => {
        if (data.session_code === props.sessionId) {
          loadECLState()
        }
      })
      
      socket.on('new_message', (data) => {
        if (data.session_code === props.sessionId) {
          messages.value.push(data)
        }
      })
    }
    
    // Lifecycle
    onMounted(async () => {
      await loadECLConfig()
      await loadECLState()
      await loadTimerState()
      initializeSocket()
    })
    
    onUnmounted(() => {
      if (socket) {
        socket.disconnect()
      }
    })
    
    return {
      showRules,
      isSessionActive,
      sessionStatus,
      sessionStatusMessage,
      timerDisplay,
      stableSessionStatus,
      eclConfig,
      eclState,
      localState,
      messages,
      newMessage,
      visibleModules,
      showRulesPopup,
      hideRulesPopup,
      hideRulesIfClickedOutside,
      logout,
      returnToLogin,
      evaluateVisibility,
      evaluatePath,
      executeAction,
      sendMessage
    }
  }
}
</script>

<style scoped>
/* Use existing unified styles - only add ECL-specific overrides */
.ecl-interface {
  min-height: 100vh;
  background: #f8f9fa;
}

.ecl-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background: white;
  border-bottom: 2px solid #007bff;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.ecl-header-left, .ecl-header-right {
  display: flex;
  align-items: center;
  gap: 15px;
}

.ecl-header-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
}

.session-label {
  font-weight: bold;
  color: #333;
}

.rules-btn, .login-toggle-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.rules-btn {
  background: #28a745;
  color: white;
}

.rules-btn:hover {
  background: #218838;
}

.login-toggle-btn {
  background: #dc3545;
  color: white;
}

.login-toggle-btn:hover {
  background: #c82333;
}

.timer-display {
  font-size: 24px;
  font-weight: bold;
  color: #007bff;
  font-family: monospace;
}

.session-status-indicator {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: bold;
  text-transform: uppercase;
}

.session-status-indicator.running {
  background: #d4edda;
  color: #155724;
}

.session-status-indicator.idle {
  background: #fff3cd;
  color: #856404;
}

.session-status-indicator.completed {
  background: #d1ecf1;
  color: #0c5460;
}

.ecl-main-content {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.ecl-main-content.disabled-content {
  opacity: 0.5;
  pointer-events: none;
}

/* ECL-specific component styles that extend existing styles */
.ecl-component {
  margin-bottom: 12px;
}

/* Chat styles for communication modules */
.chat-messages {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 10px;
  background: #f8f9fa;
}

.chat-message {
  margin-bottom: 8px;
  padding: 5px;
  border-radius: 4px;
}

.chat-message.own-message {
  background: #e3f2fd;
  text-align: right;
}

.chat-input {
  display: flex;
  gap: 10px;
}

.chat-input input {
  flex: 1;
}

/* Session overlay styles */
.session-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.session-overlay-content {
  background: white;
  padding: 40px;
  border-radius: 8px;
  text-align: center;
  max-width: 400px;
}

.session-overlay-icon {
  font-size: 48px;
  margin-bottom: 20px;
}

.session-overlay-actions {
  margin-top: 20px;
}

.return-to-login-btn {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

.return-to-login-btn:hover {
  background: #0056b3;
}

/* Rules popup styles */
.rules-popup {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.rules-popup-content {
  background: white;
  border-radius: 8px;
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
  margin: 20px;
}

.rules-popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #dee2e6;
}

.rules-popup-header h3 {
  margin: 0;
  color: #333;
}

.close-rules-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
}

.close-rules-btn:hover {
  color: #333;
}

.rules-popup-body {
  padding: 20px;
}

.rules-popup-body p {
  margin-bottom: 15px;
  line-height: 1.6;
}

.rules-popup-body ul {
  margin-left: 20px;
}

.rules-popup-body li {
  margin-bottom: 8px;
}

/* Transitions */
.session-overlay-enter-active, .session-overlay-leave-active {
  transition: opacity 0.3s ease;
}

.session-overlay-enter-from, .session-overlay-leave-to {
  opacity: 0;
}

.content-disabled-enter-active, .content-disabled-leave-active {
  transition: opacity 0.3s ease;
}

.content-disabled-enter-from, .content-disabled-leave-to {
  opacity: 0;
}
</style>
