<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// Session/participant from route or sessionStorage
const sessionId = ref(route.query.session_id || sessionStorage.getItem('session_id') || '')
const participantId = ref(route.query.participant_id || sessionStorage.getItem('participant_id') || '')
const sessionName = ref('')

// Data from API
const mergedLogs = ref([])
const annotationMoments = ref([])
const participantNames = ref({})
const filesBase = ref('')
const loading = ref(true)
const error = ref('')

// Session start time (first log timestamp) for relative time calculation
const sessionStartTime = ref(null)

// Current annotation index
const currentMomentIndex = ref(0)
const currentMoment = computed(() => annotationMoments.value[currentMomentIndex.value] || null)

// Format timestamp to MM:SS (relative to session start)
function formatTime(ts) {
  if (!ts) return '00:00'
  try {
    const d = new Date(ts)
    if (sessionStartTime.value) {
      // Calculate relative time from session start
      const diff = d.getTime() - sessionStartTime.value.getTime()
      if (diff < 0) return '00:00'
      const totalSeconds = Math.floor(diff / 1000)
      const m = Math.floor(totalSeconds / 60)
      const s = totalSeconds % 60
      return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    }
    // Fallback: use actual time
    const m = d.getMinutes()
    const s = d.getSeconds()
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  } catch {
    return '00:00'
  }
}

// Display name for participant - use participant_name from log entry if available
function getDisplayName(entry, isYou = false) {
  const pid = entry.participant_id
  const name = entry.participant_name || participantNames.value[pid] || pid?.slice(0, 8) || 'Unknown'
  return isYou ? `${name} (you)` : name
}

// Action type display: show actual action_type, format snake_case to readable
function getActionTypeDisplay(actionType) {
  if (!actionType) return 'Action'
  return actionType
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ')
}

// Screenshot URL for current moment
const screenshotUrl = computed(() => {
  const m = currentMoment.value
  if (!m?.screenshot || !filesBase.value) return null
  const filename = m.screenshot.startsWith('files/') ? m.screenshot.slice(6) : m.screenshot
  return `${filesBase.value}/${filename}`
})

// Annotation answers (persisted per moment)
const annotations = ref({}) // action_id -> { q1, q2, q3, q4, q4Reasons }
const previousAnswers = ref({ q1: '', q2: '', q3: '' }) // For "previous answer" display

// Text inputs for Q1-Q3
const q1Text = ref('')
const q2Text = ref('')
const q3Text = ref('')
const q4Value = ref(null) // 'yes' | 'no'
const q4Reasons = ref([])

const Q4_REASONS = [
  'Goal misunderstanding',
  'Unclear communication',
  'Poor coordination / roles',
  'Unexpected actions / errors',
  'Low trust in partner/agent',
  'Interface / context issues',
]

// Confirmed state per question
const confirmed = ref({ q1: false, q2: false, q3: false })

// In-game thoughts (placeholder - not in log data yet)
const inGameThoughts = ref('')

// Voice recording
const isRecording = ref(false)
const mediaRecorder = ref(null)
const isTranscribing = ref(false)
const recordingTarget = ref(null) // 'q1' | 'q2' | 'q3'

function loadData() {
  if (!sessionId.value || !participantId.value) {
    error.value = 'Missing session_id or participant_id'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  fetch(`/api/sessions/${encodeURIComponent(sessionId.value)}/post_annotation_data?participant_id=${encodeURIComponent(participantId.value)}`)
    .then((r) => r.json())
    .then((data) => {
      if (data.error) {
        error.value = data.error
        return
      }
      mergedLogs.value = data.merged_logs || []
      annotationMoments.value = data.annotation_moments || []
      participantNames.value = data.participant_names || {}
      filesBase.value = data.files_base || ''
      sessionName.value = data.session_name || data.session_id || ''
      // Load saved annotations from file
      if (data.saved_annotations && typeof data.saved_annotations === 'object') {
        annotations.value = { ...data.saved_annotations }
      }
      // Set session start time from first log entry
      if (mergedLogs.value.length > 0 && mergedLogs.value[0].timestamp) {
        sessionStartTime.value = new Date(mergedLogs.value[0].timestamp)
      }
      currentMomentIndex.value = 0
      loadCurrentMomentState()
    })
    .catch((err) => {
      error.value = err.message || 'Failed to load annotation data'
    })
    .finally(() => {
      loading.value = false
    })
}

function loadCurrentMomentState() {
  const m = currentMoment.value
  if (!m) return
  const aid = m.action_id
  const idx = currentMomentIndex.value
  const moments = annotationMoments.value
  const saved = annotations.value[aid]
  if (saved) {
    q1Text.value = saved.q1 ?? ''
    q2Text.value = saved.q2 ?? ''
    q3Text.value = saved.q3 ?? ''
    q4Value.value = saved.q4 ?? null
    q4Reasons.value = saved.q4Reasons ?? []
    confirmed.value = { q1: !!saved.q1, q2: !!saved.q2, q3: !!saved.q3 }
  } else {
    // For first action: empty. For others: show previous action's answers
    if (idx > 0 && moments[idx - 1]) {
      const prevSaved = annotations.value[moments[idx - 1].action_id]
      q1Text.value = prevSaved?.q1 ?? ''
      q2Text.value = prevSaved?.q2 ?? ''
      q3Text.value = prevSaved?.q3 ?? ''
    } else {
      q1Text.value = ''
      q2Text.value = ''
      q3Text.value = ''
    }
    q4Value.value = null
    q4Reasons.value = []
    confirmed.value = { q1: false, q2: false, q3: false }
  }
  // Placeholder for in-game thoughts
  inGameThoughts.value = 'I think my partner is guiding me to draw the route near the starting point.'
}

watch(currentMoment, () => loadCurrentMomentState(), { immediate: true })

function confirmQuestion(q) {
  const val = q === 'q1' ? q1Text.value : q === 'q2' ? q2Text.value : q3Text.value
  if (val.trim()) {
    confirmed.value[q] = true
    previousAnswers.value[q] = val.trim()
    saveCurrentAnnotations()
    saveAnnotationsToFile()
  }
}

function saveCurrentAnnotations() {
  const m = currentMoment.value
  if (!m) return
  annotations.value[m.action_id] = {
    q1: q1Text.value.trim(),
    q2: q2Text.value.trim(),
    q3: q3Text.value.trim(),
    q4: q4Value.value,
    q4Reasons: [...q4Reasons.value],
  }
}

function onQ4Change() {
  saveCurrentAnnotations()
  saveAnnotationsToFile()
}

function toggleQ4Reason(reason) {
  const idx = q4Reasons.value.indexOf(reason)
  if (idx >= 0) {
    q4Reasons.value.splice(idx, 1)
  } else {
    q4Reasons.value.push(reason)
  }
  saveCurrentAnnotations()
  saveAnnotationsToFile()
}

async function saveAnnotationsToFile() {
  if (!sessionId.value || !participantId.value) return
  try {
    await fetch(
      `/api/sessions/${encodeURIComponent(sessionId.value)}/participants/${encodeURIComponent(participantId.value)}/post_annotations`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ annotations: annotations.value }),
      }
    )
  } catch (err) {
    console.error('[PostAnnotation] Failed to save annotations:', err)
  }
}

function prevMoment() {
  saveCurrentAnnotations()
  saveAnnotationsToFile()
  if (currentMomentIndex.value > 0) {
    currentMomentIndex.value--
  }
}

function validateAllAnswered() {
  const q1 = q1Text.value.trim()
  const q2 = q2Text.value.trim()
  const q3 = q3Text.value.trim()
  if (!q1) {
    alert('Please answer: At this moment, what did you think the group was trying to do?')
    return false
  }
  if (!q2) {
    alert('Please answer: What was your intention of this action?')
    return false
  }
  if (!q3) {
    alert('Please answer: At that moment, what did you think your partner(s) were trying to do?')
    return false
  }
  if (!q4Value.value) {
    alert('Please answer: Do you think you and your partner are on the same page? (Yes or No)')
    return false
  }
  return true
}

function nextMoment() {
  // Auto-confirm: save current inputs as annotations
  saveCurrentAnnotations()
  // All four questions required
  if (!validateAllAnswered()) return
  saveAnnotationsToFile()
  if (currentMomentIndex.value < annotationMoments.value.length - 1) {
    currentMomentIndex.value++
  } else {
    router.push('/login')
  }
}

// Voice recording
async function toggleRecording(target) {
  if (isTranscribing.value) return
  if (isRecording.value) {
    if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
      mediaRecorder.value.stop()
    }
    return
  }
  recordingTarget.value = target
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    const chunks = []
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data) }
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      if (chunks.length === 0) return
      isTranscribing.value = true
      try {
        const blob = new Blob(chunks, { type: 'audio/webm' })
        const form = new FormData()
        form.append('audio', blob, 'recording.webm')
        const res = await fetch('/api/transcribe', { method: 'POST', body: form })
        const data = await res.json().catch(() => ({}))
        const text = (data.text || '').trim()
        if (target === 'q1') q1Text.value = text
        else if (target === 'q2') q2Text.value = text
        else if (target === 'q3') q3Text.value = text
      } catch (err) {
        console.error('[PostAnnotation] Transcribe error:', err)
      } finally {
        isTranscribing.value = false
      }
    }
    recorder.start()
    mediaRecorder.value = recorder
    isRecording.value = true
  } catch (err) {
    console.error('[PostAnnotation] Microphone error:', err)
    alert('Microphone access denied.')
  }
}

function handleUpdate(target) {
  if (isRecording.value && recordingTarget.value === target) {
    if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
      mediaRecorder.value.stop()
    }
    isRecording.value = false
  } else {
    toggleRecording(target)
  }
}

onMounted(() => {
  // Allow override from route for testing with sample data
  if (route.query.session_id) sessionId.value = route.query.session_id
  if (route.query.participant_id) participantId.value = route.query.participant_id
  loadData()
})
</script>

<template>
  <div class="post-annotation-page">
    <div class="page-header">
      <h1>Post-Session Annotation <span class="session-name">- Session: {{ sessionName || sessionId }}</span></h1>
    </div>
    <div v-if="loading" class="loading-state">
      <p>Loading annotation data...</p>
    </div>
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <p class="hint">For testing with sample data, use: ?session_id=016c8aca-bac7-4f60-ae36-0ccc5504a1fb&participant_id=a59bed79-e55a-417e-92cc-e0ff70fc8cf9</p>
    </div>
    <div v-else-if="annotationMoments.length === 0" class="empty-state">
      <p>No annotation moments found for this session.</p>
    </div>
    <div v-else class="annotation-layout">
      <!-- Left panel: Action revisiting -->
      <div class="left-panel">
        <h2 class="panel-title">
          You are revisiting your action at
          <span class="time-highlight">{{ currentMoment ? formatTime(currentMoment.timestamp) : '00:00' }}</span>
        </h2>
        <div class="session-replay-preview">
          <img
            v-if="screenshotUrl"
            :src="screenshotUrl"
            alt="Session replay at action time"
            class="replay-screenshot"
          />
          <div v-else class="replay-placeholder">No screenshot</div>
        </div>
        <div class="log-list-header">Interaction Log</div>
        <div class="log-list">
          <div
            v-for="entry in mergedLogs"
            :key="entry.action_id"
            class="log-item"
            :class="{ highlighted: currentMoment && entry.action_id === currentMoment.action_id }"
          >
            <span class="log-time">{{ formatTime(entry.timestamp) }}</span>
            <span class="log-participant">{{ getDisplayName(entry, entry.participant_id === participantId) }}</span>
            <span class="log-type">{{ getActionTypeDisplay(entry.action_type) }}</span>
            <span class="log-content">{{ entry.action_content || '—' }}</span>
          </div>
        </div>
      </div>

      <!-- Right panel: Annotation form -->
      <div class="right-panel">
        <h2 class="panel-title">
          You are annotating your action at
          <span class="time-highlight">{{ currentMoment ? formatTime(currentMoment.timestamp) : '00:00' }}</span>
        </h2>
        <div class="thoughts-box">
          <label>Your in-game thoughts:</label>
          <p>{{ inGameThoughts || '(No thoughts recorded)' }}</p>
        </div>

        <!-- Q1 -->
        <div class="question-block">
          <label>1. At this moment, what do you think the group (you and your partner) was trying to do? *</label>
          <div class="input-row">
            <input v-model="q1Text" type="text" placeholder="previous answer" class="text-input" />
            <button type="button" class="btn-update" @click="handleUpdate('q1')" :disabled="isTranscribing">
              <span v-if="isRecording && recordingTarget === 'q1'" class="recording-indicator">...</span>
              <i v-else class="fa-solid fa-microphone"></i>
              {{ isRecording && recordingTarget === 'q1' ? ' Listening' : ' Update' }}
            </button>
            <button type="button" class="btn-confirm" @click="confirmQuestion('q1')">
              Confirm <i v-if="confirmed.q1" class="fa-solid fa-check"></i>
            </button>
          </div>
        </div>


        <!-- Q3 -->
        <div class="question-block">
          <label>2. At that moment, what did you think your partner(s) were trying to do? *</label>
          <p class="question-note">This is about your impression, not what they were actually trying to do.</p>
          <div class="input-row">
            <input v-model="q3Text" type="text" placeholder="previous answer" class="text-input" />
            <button type="button" class="btn-update" @click="handleUpdate('q3')" :disabled="isTranscribing">
              <span v-if="isRecording && recordingTarget === 'q3'" class="recording-indicator">...</span>
              <i v-else class="fa-solid fa-microphone"></i>
              {{ isRecording && recordingTarget === 'q3' ? ' Listening' : ' Update' }}
            </button>
            <button type="button" class="btn-confirm" @click="confirmQuestion('q3')">
              Confirm <i v-if="confirmed.q3" class="fa-solid fa-check"></i>
            </button>
          </div>
        </div>

        <!-- Q2 -->
        <div class="question-block">
          <label>3. What was your intention of this action? *</label>
           <div class="input-row">
            <input v-model="q2Text" type="text" placeholder="previous answer" class="text-input" />
            <button type="button" class="btn-update" @click="handleUpdate('q2')" :disabled="isTranscribing">
              <span v-if="isRecording && recordingTarget === 'q2'" class="recording-indicator">...</span>
              <i v-else class="fa-solid fa-microphone"></i>
              {{ isRecording && recordingTarget === 'q2' ? ' Listening' : ' Update' }}
            </button>
            <button type="button" class="btn-confirm" @click="confirmQuestion('q2')">
              Confirm <i v-if="confirmed.q2" class="fa-solid fa-check"></i>
            </button>
          </div>
        </div>

        <!-- Q4 -->
        <div class="question-block">
          <label>Do you think you and your partner are on the same page?</label>
          <div class="q4-options">
            <label class="radio-option">
              <input v-model="q4Value" type="radio" value="yes" @change="onQ4Change" />
              Yes
            </label>
            <label class="radio-option">
              <input v-model="q4Value" type="radio" value="no" @change="onQ4Change" />
              No
            </label>
          </div>
          <div v-if="q4Value === 'no'" class="q4-reasons">
            <label v-for="r in Q4_REASONS" :key="r" class="checkbox-option">
              <input type="checkbox" :checked="q4Reasons.includes(r)" @change="toggleQ4Reason(r)" />
              {{ r }}
            </label>
          </div>
        </div>

        <div class="nav-footer">
          <button
            type="button"
            class="btn-prev"
            :disabled="currentMomentIndex <= 0"
            @click="prevMoment"
          >
            Prev
          </button>
          <button
            type="button"
            class="btn-next"
            @click="nextMoment"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  text-align: center;
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #111;
  margin: 0;
}

.page-header .session-name {
  font-size: 20px;
  font-weight: 500;
  color: #6b7280;
}

.post-annotation-page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 24px;
  box-sizing: border-box;
}

.loading-state,
.error-state,
.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: #666;
}

.error-state .hint {
  font-size: 12px;
  color: #999;
  margin-top: 12px;
}

.annotation-layout {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;
  max-width: 1400px;
  margin: 0 auto;
  height: calc(100vh - 120px);
  min-height: 600px;
}

@media (max-width: 900px) {
  .annotation-layout {
    grid-template-columns: 1fr;
    height: auto;
  }
}

.left-panel,
.right-panel {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.left-panel {
  max-height: calc(100vh - 120px);
}

.right-panel {
  max-height: calc(100vh - 120px);
  overflow-y: auto;
}

.panel-title {
  font-size: 18px;
  font-weight: 600;
  color: #111;
  margin: 0 0 16px 0;
  flex-shrink: 0;
}

.time-highlight {
  color: #dc2626;
  font-weight: 700;
}

.session-replay-preview {
  width: 100%;
  max-height: 400px;
  aspect-ratio: 16/10;
  background: #eee;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.replay-screenshot {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.replay-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
}

.log-list-header {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.log-list {
  flex: 1;
  min-height: 200px;
  overflow-y: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.log-item {
  display: grid;
  grid-template-columns: 48px 110px 120px 1fr;
  gap: 8px;
  padding: 10px 12px;
  font-size: 13px;
  border-bottom: 1px solid #f3f4f6;
  align-items: start;
}

.log-item:last-child {
  border-bottom: none;
}

.log-item.highlighted {
  background: #dbeafe;
}

.log-time {
  font-weight: 500;
  color: #374151;
}

.log-participant {
  color: #6b7280;
}

.log-type {
  color: #9ca3af;
  font-size: 12px;
}

.log-content {
  color: #4b5563;
  word-break: break-word;
  white-space: pre-wrap;
}

.thoughts-box {
  background: #e5e7eb;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.thoughts-box label {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  display: block;
  margin-bottom: 4px;
}

.thoughts-box p {
  margin: 0;
  font-size: 14px;
  color: #374151;
}

.question-block {
  margin-bottom: 20px;
}

.question-block > label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #111;
  margin-bottom: 8px;
  text-align: left;
}

.question-note {
  font-size: 12px;
  color: #6b7280;
  margin: -4px 0 8px 0;
  text-align: left;
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.text-input {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.text-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.btn-update,
.btn-confirm {
  padding: 8px 12px;
  font-size: 13px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  background: #f9fafb;
  cursor: pointer;
  white-space: nowrap;
}

.btn-update:hover:not(:disabled),
.btn-confirm:hover {
  background: #f3f4f6;
}

.btn-update:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-confirm {
  color: #059669;
}

.btn-confirm i {
  margin-left: 4px;
}

.recording-indicator {
  color: #dc2626;
  font-weight: bold;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.q4-options {
  display: flex;
  gap: 16px;
  margin-top: 8px;
}

.radio-option {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  cursor: pointer;
}

.q4-reasons {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.checkbox-option {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #4b5563;
  cursor: pointer;
}

.nav-footer {
  margin-top: 24px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.btn-prev,
.btn-next {
  padding: 12px 24px;
  font-size: 14px;
  font-weight: 500;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.btn-prev {
  background: #e5e7eb;
  color: #374151;
}

.btn-prev:hover:not(:disabled) {
  background: #d1d5db;
}

.btn-prev:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-next {
  background: #6b7280;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.btn-next:hover {
  background: #4b5563;
}
</style>
