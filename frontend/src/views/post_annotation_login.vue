<template>
  <div class="login-container">
    <div class="login-card">
      <div class="header">
        <h1>Post-Session Annotation</h1>
        <p class="subtitle">Sign in with the same participant and session names you used in the study</p>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <div class="input-group">
          <label for="paParticipantName">Participant name</label>
          <input
            id="paParticipantName"
            v-model="participantName"
            type="text"
            required
            autocomplete="username"
            placeholder="e.g. Jack"
            :disabled="isLoading"
          />
        </div>

        <div class="input-group">
          <label for="paSessionName">Session name</label>
          <input
            id="paSessionName"
            v-model="sessionName"
            type="text"
            required
            autocomplete="off"
            placeholder="Session name from the researcher"
            :disabled="isLoading"
          />
        </div>

        <button type="submit" class="login-btn" :disabled="isLoading">
          {{ isLoading ? 'Signing in…' : 'Continue to annotation' }}
        </button>
      </form>

      <div v-if="errorMessage" class="error-message">
        {{ errorMessage }}
      </div>

      <div class="info-section">
        <h3>Instructions</h3>
        <ul>
          <li>Use the participant name assigned for this session</li>
          <li>Use the session name your researcher gave you</li>
          <li>This page only opens the post-session annotation task (not the live session)</li>
          <li>For the live experiment, use the main participant login instead</li>
        </ul>
      </div>

      <div class="footer-link">
        <RouterLink to="/login">Go to participant session login</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

const router = useRouter()

const participantName = ref('')
const sessionName = ref('')
const isLoading = ref(false)
const errorMessage = ref('')

const handleLogin = async () => {
  if (!participantName.value.trim() || !sessionName.value.trim()) {
    errorMessage.value = 'Please enter both participant name and session name'
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        participant_name: participantName.value.trim(),
        session_name: sessionName.value.trim(),
      }),
    })

    const data = await response.json()

    if (response.ok && data.success) {
      const sid = data.session?.session_id
      const pid = data.participant?.participant_id || data.participant?.id
      if (!sid || !pid) {
        errorMessage.value = 'Login succeeded but session or participant id is missing. Please contact the researcher.'
        return
      }

      sessionStorage.setItem('session_id', sid)
      sessionStorage.setItem('participant_id', pid)
      if (data.session?.session_name || data.session?.session_code) {
        sessionStorage.setItem(
          'session_code',
          data.session.session_code || data.session.session_name,
        )
      }
      if (data.session?.experiment_type) {
        sessionStorage.setItem('experiment_type', data.session.experiment_type)
      }

      await router.push({ path: '/post-annotation' })
    } else {
      errorMessage.value = data.message || 'Sign-in failed. Check names and try again.'
    }
  } catch (e) {
    console.error('[PostAnnotationLogin]', e)
    errorMessage.value = 'Network error. Please check your connection and try again.'
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
  box-sizing: border-box;
  min-height: calc(100vh - 2vh);
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #2d6a4f 0%, #1b4332 100%);
  padding: 16px;
}

.login-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
  padding: 28px;
  max-width: 500px;
  width: 100%;
}

.header {
  text-align: center;
  margin-bottom: 20px;
}

.header h1 {
  color: #333;
  margin-bottom: 8px;
  font-size: 26px;
}

.subtitle {
  color: #666;
  font-size: 15px;
  line-height: 1.45;
  margin: 0;
}

.login-form {
  margin-bottom: 20px;
}

.input-group {
  margin-bottom: 16px;
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
  box-sizing: border-box;
}

.input-group input:focus {
  outline: none;
  border-color: #2d6a4f;
}

.input-group input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-btn {
  width: 100%;
  background: #2d6a4f;
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
  background: #1b4332;
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
  padding-top: 16px;
  margin-bottom: 16px;
}

.info-section h3 {
  color: #333;
  margin-bottom: 10px;
  font-size: 18px;
}

.info-section ul {
  list-style: none;
  padding: 0;
  text-align: left;
}

.info-section li {
  margin-bottom: 6px;
  padding-left: 20px;
  position: relative;
}

.info-section li:last-child {
  margin-bottom: 0;
}

.info-section li:before {
  content: '•';
  color: #2d6a4f;
  font-weight: bold;
  position: absolute;
  left: 0;
}

.footer-link {
  text-align: center;
  padding-top: 4px;
}

.footer-link a {
  color: #2d6a4f;
  font-weight: 600;
  text-decoration: none;
}

.footer-link a:hover {
  text-decoration: underline;
}
</style>
