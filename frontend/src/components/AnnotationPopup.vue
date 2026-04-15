<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  checkpointIndex: {
    type: Number,
    default: 0
  },
  /** After this user submitted; session stays paused until all humans submit */
  waitingForPartners: {
    type: Boolean,
    default: false
  },
  /** When true, show a close button (for test page) */
  allowClose: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'submit'])

const participantRole = computed(() => (sessionStorage.getItem('participant_role') || '').trim().toLowerCase())

const sincePhrase = computed(() =>
  props.checkpointIndex === 0 ? 'since the session starts' : 'since the last checkpoint'
)

const roleSpecificQuestion = computed(() => {
  const s = sincePhrase.value
  if (participantRole.value === 'follower') return `What has the guide been trying to do ${s}?`
  if (participantRole.value === 'guide') return `What has the follower been trying to do ${s}?`
  return 'What have you and your partner been trying to do ${s}?'
})

const QUESTIONS = computed(() => [
  `What have you and your partner been trying to do ${sincePhrase.value}?`,
  'How do you think you and your partner did?',
  roleSpecificQuestion.value,
  'What do you plan to do next?'
])

const INSTRUCTION = 'Please briefly answer the four questions.\nClick on the button to start recording.'

const isRecording = ref(false)
const mediaRecorder = ref(null)
const audioChunks = ref([])
const transcription = ref('')
const isTranscribing = ref(false)
const isSubmitting = ref(false)
const hasRecorded = ref(false)


const canSubmit = computed(() => transcription.value.trim().length > 0 && !isSubmitting.value)

const toggleRecording = async () => {
  if (isTranscribing.value || isSubmitting.value) return

  if (hasRecorded.value && !isRecording.value) {
    transcription.value = ''
    hasRecorded.value = false
  }

  if (isRecording.value) {
    if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
      mediaRecorder.value.stop()
    }
    return
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    audioChunks.value = []

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
        const form = new FormData()
        form.append('audio', blob, 'recording.webm')
        const res = await fetch('/api/transcribe', { method: 'POST', body: form })
        const data = await res.json().catch(() => ({}))
        transcription.value = (data.text || '').trim()
        hasRecorded.value = true
      } catch (err) {
        console.error('[AnnotationPopup] Transcribe error:', err)
        transcription.value = '[Transcription failed. Please try again.]'
      } finally {
        isTranscribing.value = false
      }
    }
    recorder.start()
    mediaRecorder.value = recorder
    isRecording.value = true
  } catch (err) {
    console.error('[AnnotationPopup] Microphone error:', err)
    alert('Microphone access denied. Please allow microphone access.')
  }
}

const handleSubmit = async () => {
  if (!canSubmit.value) return
  isSubmitting.value = true
  try {
    emit('submit', {
      transcription: transcription.value.trim(),
      submitted_at: new Date().toISOString()
    })
  } finally {
    isSubmitting.value = false
  }
}

const handleClose = () => {
  if (!isSubmitting.value) {
    emit('close')
  }
}
</script>

<template>
  <div v-if="show" class="annotation-overlay" @click.self="allowClose && !waitingForPartners ? handleClose() : null">
    <div class="annotation-modal">
      <div class="annotation-header">
        <h3>{{ waitingForPartners ? 'Please wait' : 'Quick Checking' }}</h3>
        <button v-if="allowClose && !waitingForPartners" type="button" class="close-btn" @click="handleClose" :disabled="isSubmitting">×</button>
      </div>
      <div v-if="waitingForPartners" class="annotation-body annotation-waiting-body">
        <p class="annotation-waiting-message">Waiting for your partner(s) to finish</p>
      </div>
      <div v-else class="annotation-body">
        <div class="annotation-questions">
          <ol>
            <li v-for="(q, i) in QUESTIONS" :key="i" class="question-item">{{ q }}</li>
          </ol>
        </div>
        <p class="annotation-instruction">{{ INSTRUCTION }}</p>

        <div class="annotation-recording">
          <button
            type="button"
            class="record-btn-circle"
            :class="{ recording: isRecording, 'has-recorded': hasRecorded }"
            @click="toggleRecording"
            :disabled="isTranscribing || isSubmitting"
            :title="hasRecorded ? 'Re-record' : (isRecording ? 'Stop' : 'Record')"
          >
            <i v-if="isRecording" class="fa-solid fa-microphone record-circle-icon"></i>
            <i v-else-if="hasRecorded" class="fa-solid fa-arrow-rotate-left record-circle-icon"></i>
            <i v-else class="fa-solid fa-microphone record-circle-icon"></i>
          </button>

          <div v-if="isRecording" class="sound-wave">
            <span v-for="i in 12" :key="i" class="wave-bar"></span>
          </div>

          <div v-if="isTranscribing" class="transcribing-status">Transcribing...</div>

          <div v-if="hasRecorded && !isTranscribing" class="transcription-area">
            <label>Your response:</label>
            <textarea
              v-model="transcription"
              class="transcription-textarea"
              placeholder="Edit your response..."
              rows="3"
            />
            <div class="annotation-actions">
              <button type="button" class="btn btn-primary" @click="handleSubmit" :disabled="!canSubmit">
                {{ isSubmitting ? 'Submitting...' : 'Submit' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.annotation-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10002;
  padding: 20px;
}

.annotation-modal {
  color-scheme: light;
  background: white;
  border-radius: 12px;
  max-width: 580px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.annotation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
  border-radius: 12px 12px 0 0;
}

.annotation-header h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #111827;
}

.close-btn {
  width: 32px;
  height: 32px;
  font-size: 24px;
  line-height: 1;
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  border-radius: 4px;
}

.close-btn:hover:not(:disabled) {
  background: #e5e7eb;
  color: #111827;
}

.close-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.annotation-body {
  padding: 24px;
}

.annotation-waiting-body {
  text-align: center;
  padding: 40px 24px;
}

.annotation-waiting-message {
  margin: 0;
  font-size: 17px;
  color: #374151;
  line-height: 1.5;
}

.annotation-questions {
  margin-bottom: 16px;
  text-align: left;
}

.annotation-questions ol {
  margin: 0;
  padding-left: 20px;
  text-align: left;
}

.question-item {
  margin-bottom: 8px;
  font-size: 18px;
  color: #374151;
  line-height: 1.5;
  text-align: left;
}

.annotation-instruction {
  margin: 0 0 24px 0;
  font-size: 14px;
  color: #6b7280;
  font-style: italic;
  text-align: center;
  white-space: pre-line;
}

.annotation-recording {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.record-btn-circle {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  border: none;
  background: #3b82f6;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.record-btn-circle:hover:not(:disabled) {
  background: #2563eb;
}

.record-btn-circle.recording {
  background: #ef4444;
  animation: pulse 1s infinite;
}

.record-btn-circle.has-recorded:hover:not(:disabled) {
  background: #2563eb;
}

.record-btn-circle:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.record-circle-icon {
  font-size: 28px;
  color: white;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.85; transform: scale(1.05); }
}

.sound-wave {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 40px;
}

.wave-bar {
  width: 4px;
  height: 20px;
  background: #3b82f6;
  border-radius: 2px;
  animation: wave 0.8s ease-in-out infinite;
}

.wave-bar:nth-child(1) { animation-delay: 0s; }
.wave-bar:nth-child(2) { animation-delay: 0.1s; }
.wave-bar:nth-child(3) { animation-delay: 0.2s; }
.wave-bar:nth-child(4) { animation-delay: 0.3s; }
.wave-bar:nth-child(5) { animation-delay: 0.4s; }
.wave-bar:nth-child(6) { animation-delay: 0.5s; }
.wave-bar:nth-child(7) { animation-delay: 0.4s; }
.wave-bar:nth-child(8) { animation-delay: 0.3s; }
.wave-bar:nth-child(9) { animation-delay: 0.2s; }
.wave-bar:nth-child(10) { animation-delay: 0.1s; }
.wave-bar:nth-child(11) { animation-delay: 0s; }
.wave-bar:nth-child(12) { animation-delay: 0.1s; }

@keyframes wave {
  0%, 100% { height: 8px; }
  50% { height: 24px; }
}

.transcribing-status {
  font-size: 14px;
  color: #6b7280;
}

.transcription-area {
  width: 100%;
  padding: 16px;
  background: #f9fafb;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  box-sizing: border-box;
}

.transcription-area label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 8px;
}

.transcription-textarea {
  width: 100%;
  font-size: 15px;
  color: #111827;
  background-color: #fff;
  margin-bottom: 16px;
  padding: 12px;
  line-height: 1.5;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  resize: vertical;
  box-sizing: border-box;
}

.transcription-textarea:focus {
  outline: none;
  border-color: #3b82f6;
}

.annotation-actions {
  display: flex;
  justify-content: flex-end;
}

.btn {
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 6px;
  cursor: pointer;
  border: none;
  transition: background 0.2s;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
