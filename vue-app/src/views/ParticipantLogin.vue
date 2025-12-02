<template>
  <div class="login-container">
    <div class="login-card">
      <div class="header">
        <h1>Participant Login</h1>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <div class="input-group">
          <label for="participantCode">Participant ID</label>
          <input
            id="participantCode"
            v-model="participantCode"
            type="text"
            required
            placeholder="Enter your Participant ID (e.g., Jack)"
            :disabled="isLoading"
          />
        </div>

        <div class="input-group">
          <label for="sessionCode">Session ID</label>
          <input
            id="sessionCode"
            v-model="sessionCode"
            type="text"
            required
            placeholder="Enter Session ID"
            :disabled="isLoading"
          />
        </div>

        <button type="submit" class="login-btn" :disabled="isLoading">
          {{ isLoading ? 'Logging in...' : 'Login' }}
        </button>
      </form>

      <div v-if="errorMessage" class="error-message">
        {{ errorMessage }}
      </div>

      <div class="info-section">
        <h3>Instructions</h3>
        <ul>
          <li>Enter your assigned Participant ID</li>
          <li>Use Session ID provided by researcher</li>
          <li>Once logged in, you can start trading and producing shapes</li>
          <li>Contact the researcher if you have login issues</li>
        </ul>
      </div>

      <!-- <div class="experiment-info">
        <h4>About Shape Factory</h4>
        <p>You'll be participating in an economic simulation where you trade geometric shapes with other participants to complete orders and earn money.</p>
      </div> -->
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

// Reactive state
const participantCode = ref('')
const sessionCode = ref('')  // Empty by default - require user input
const isLoading = ref(false)
const errorMessage = ref('')

// check if the page is loaded by a mTurk worker or Prolific participant
onMounted(async () => {
  const workerId = route.query.workerId as string
  const assignmentId = route.query.assignmentId as string
  const hitId = route.query.hitId as string
  
  const prolificPid = route.query.PROLIFIC_PID as string
  const studyId = route.query.STUDY_ID as string
  const prolificSessionId = route.query.SESSION_ID as string
  
  // if the page is loaded by a mTurk worker, auto assign and login
  if (workerId && assignmentId) {
    await handleMTurkAutoFlow(workerId, assignmentId, hitId)
  }
  // if the page is loaded by a Prolific participant, auto assign and login
  else if (prolificPid && studyId && prolificSessionId) {
    await handleProlificAutoFlow(prolificPid, studyId, prolificSessionId)
  }
})

// mTurk auto assign and login flow
const handleMTurkAutoFlow = async (workerId: string, assignmentId: string, hitId?: string) => {
  isLoading.value = true
  errorMessage.value = ''
  
  try {
    // step 1: assign an existing participant
    const assignResponse = await fetch('/api/mturk/assign-hiddenprofile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workerId, assignmentId, hitId })
    })
    
    const assignData = await assignResponse.json()
    
    if (!assignResponse.ok || !assignData.success) {
      errorMessage.value = assignData.error || 'Failed to assign session'
      isLoading.value = false
      return
    }
    
    // assignment successful, save information
    participantCode.value = assignData.participant_code
    sessionCode.value = assignData.session_code
    
    // step 2: auto login
    const loginResponse = await fetch('/api/mturk/auto-login-hiddenprofile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workerId, assignmentId })
    })
    
    const loginData = await loginResponse.json()
    
    if (!loginResponse.ok || !loginData.success) {
      errorMessage.value = loginData.error || 'Failed to login'
      isLoading.value = false
      return
    }
    
    // login successful, save authentication information and redirect
    sessionStorage.setItem('auth_token', loginData.token)
    sessionStorage.setItem('participant_code', loginData.participant.participant_code)
    sessionStorage.setItem('participant_id', loginData.participant.participant_id)
    sessionStorage.setItem('session_code', loginData.session.session_code)
    
    // redirect to the participant interface
    router.push('/participant')
    
  } catch (error) {
    console.error('MTurk auto flow error:', error)
    errorMessage.value = 'Network error during auto assignment/login'
    isLoading.value = false
  }
}

// Prolific auto assign and login flow
const handleProlificAutoFlow = async (prolificPid: string, studyId: string, prolificSessionId: string) => {
  isLoading.value = true
  errorMessage.value = ''
  
  try {
    // step 1: assign an existing participant
    const assignResponse = await fetch('/api/prolific/assign-hiddenprofile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prolificPid, studyId, prolificSessionId })
    })
    
    const assignData = await assignResponse.json()
    
    if (!assignResponse.ok || !assignData.success) {
      errorMessage.value = assignData.error || 'Failed to assign session'
      isLoading.value = false
      return
    }
    
    // assignment successful, save information
    participantCode.value = assignData.participant_code
    sessionCode.value = assignData.session_code
    
    // step 2: auto login
    const loginResponse = await fetch('/api/prolific/auto-login-hiddenprofile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prolificPid, studyId, prolificSessionId })
    })
    
    const loginData = await loginResponse.json()
    
    if (!loginResponse.ok || !loginData.success) {
      errorMessage.value = loginData.error || 'Failed to login'
      isLoading.value = false
      return
    }
    
    // login successful, save authentication information and redirect
    sessionStorage.setItem('auth_token', loginData.token)
    sessionStorage.setItem('participant_code', loginData.participant.participant_code)
    sessionStorage.setItem('participant_id', loginData.participant.participant_id)
    sessionStorage.setItem('session_code', loginData.session.session_code)
    
    // redirect to the participant interface
    router.push('/participant')
    
  } catch (error) {
    console.error('Prolific auto flow error:', error)
    errorMessage.value = 'Network error during auto assignment/login'
    isLoading.value = false
  }
}

// Handle form submission
const handleLogin = async () => {
  if (!participantCode.value.trim() || !sessionCode.value.trim()) {
    errorMessage.value = 'Please enter both participant code and session code'
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  try {
    // Using sessionStorage for tab-specific authentication
    // This allows multiple participants to login simultaneously in different tabs
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        participant_code: participantCode.value.trim(),
        session_code: sessionCode.value.trim()
      })
    })

    const data = await response.json()

    if (response.ok && data.success) {
      // Store authentication data in sessionStorage (tab-specific)
      sessionStorage.setItem('auth_token', data.token)
      sessionStorage.setItem('participant_code', data.participant.participant_code)
      sessionStorage.setItem('participant_id', data.participant.participant_id)
      sessionStorage.setItem('session_code', data.session.session_code)

      // Redirect to participant interface (now adaptive)
      router.push('/participant')
    } else {
      errorMessage.value = data.message || 'Login failed. Please check your credentials.'
    }
  } catch (error) {
    console.error('Login error:', error)
    errorMessage.value = 'Network error. Please check your connection and try again.'
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.2);
  padding: 40px;
  max-width: 500px;
  width: 100%;
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.header h1 {
  color: #333;
  margin-bottom: 8px;
  font-size: 28px;
}

.subtitle {
  color: #666;
  font-size: 16px;
}

.login-form {
  margin-bottom: 30px;
}

.input-group {
  margin-bottom: 20px;
}

.input-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: #333;
}

.input-group input {
  width: 100%;
  padding: 12px;
  border: 2px solid #e1e5e9;
  border-radius: 6px;
  font-size: 16px;
  transition: border-color 0.3s;
}

.input-group input:focus {
  outline: none;
  border-color: #667eea;
}

.input-group input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-btn {
  width: 100%;
  background: #667eea;
  color: white;
  border: none;
  padding: 14px;
  border-radius: 6px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.3s;
}

.login-btn:hover:not(:disabled) {
  background: #5a6fd8;
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-message {
  background: #f8d7da;
  color: #721c24;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 20px;
  border: 1px solid #f5c6cb;
}

.info-section {
  border-top: 1px solid #e1e5e9;
  padding-top: 25px;
  margin-bottom: 20px;
}

.info-section h3 {
  color: #333;
  margin-bottom: 15px;
  font-size: 18px;
}

.info-section ul {
  list-style: none;
  padding: 0;
}

.info-section li {
  margin-bottom: 8px;
  padding-left: 20px;
  position: relative;
}

.info-section li:before {
  content: "•";
  color: #667eea;
  font-weight: bold;
  position: absolute;
  left: 0;
}

.experiment-info {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 6px;
}

.experiment-info h4 {
  color: #333;
  margin-bottom: 10px;
  font-size: 16px;
}

.experiment-info p {
  color: #666;
  line-height: 1.5;
  margin: 0;
}
</style> 