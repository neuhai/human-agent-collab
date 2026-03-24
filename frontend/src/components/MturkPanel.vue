<template>
  <div class="mturk-panel">
    <div class="manage-forms">
      <div class="form-card">
        <div class="card-title">Associate MTurk HIT</div>
        <div class="form-grid">
          <div class="form-row">
            <input
              v-model="hitId"
              class="input"
              type="text"
              placeholder="Enter HIT ID from MTurk"
              :disabled="!isSessionReady || isLoading"
            />
          </div>
          <div class="form-row">
            <select v-model="environment" class="select" :disabled="!isSessionReady || isLoading">
              <option value="sandbox">Sandbox</option>
              <option value="production">Production</option>
            </select>
          </div>
          <div class="form-row">
            <button class="btn primary" :disabled="!canAssociate" @click="associateHit">
              Associate HIT
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="table-section">
      <div class="section-title">
        Review Assignments
        <button class="btn secondary" @click="fetchAssignments" :disabled="!isSessionReady || isLoading">
          {{ isLoading ? 'Loading...' : 'Refresh Assignments' }}
        </button>
      </div>

      <div class="helper-box">
        <div><strong>External URL template</strong></div>
        <code class="url">{{ externalUrlTemplate }}</code>
      </div>

      <div v-if="errorMessage" class="error-message">{{ errorMessage }}</div>
      <div v-if="successMessage" class="success-message">{{ successMessage }}</div>

      <div v-if="isLoading" class="loading-message">Loading assignments...</div>
      <div v-else-if="assignments.length === 0" class="empty-message">No assignments to review.</div>
      <div v-else class="manage-table">
        <div class="table-head">
          <div class="th">Worker ID</div>
          <div class="th">Assignment ID</div>
          <div class="th">Status</div>
          <div class="th">Submitted</div>
          <div class="th actions">Actions</div>
        </div>
        <div class="table-body">
          <div class="tr" v-for="assignment in assignments" :key="assignment.assignment_id">
            <div class="td">{{ assignment.worker_id }}</div>
            <div class="td">{{ assignment.assignment_id }}</div>
            <div class="td">{{ assignment.status }}</div>
            <div class="td">{{ assignment.submit_time || '-' }}</div>
            <div class="td actions">
              <button
                class="btn primary"
                :disabled="assignment.status !== 'Submitted' || isLoading"
                @click="approve(assignment.assignment_id)"
              >
                Approve
              </button>
              <button
                class="btn danger"
                :disabled="assignment.status !== 'Submitted' || isLoading"
                @click="reject(assignment.assignment_id)"
              >
                Reject
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'

const props = defineProps({
  sessionName: { type: String, default: '' },
  sessionId: { type: String, default: '' },
  isSessionCreated: { type: Boolean, default: false },
})

const hitId = ref('')
const environment = ref('sandbox')
const assignments = ref([])
const isLoading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

const sessionIdentifier = computed(() => props.sessionName || props.sessionId || '')
const isSessionReady = computed(() => props.isSessionCreated && !!sessionIdentifier.value)
const canAssociate = computed(() => isSessionReady.value && !!hitId.value.trim() && !!environment.value && !isLoading.value)

const externalUrlTemplate = computed(() => {
  if (typeof window === 'undefined') return '/login?workerId=${workerId}&assignmentId=${assignmentId}&hitId=${hitId}'
  const base = `${window.location.origin}/login`
  return `${base}?workerId=\${workerId}&assignmentId=\${assignmentId}&hitId=\${hitId}`
})

const clearMessages = () => {
  errorMessage.value = ''
  successMessage.value = ''
}

const fetchConfig = async () => {
  if (!isSessionReady.value) return
  clearMessages()
  try {
    const encoded = encodeURIComponent(sessionIdentifier.value)
    const response = await fetch(`/api/mturk/sessions/${encoded}/config`)
    const result = await response.json()
    if (response.ok && result.success && result.mturk) {
      hitId.value = result.mturk.hit_id || ''
      environment.value = result.mturk.environment || 'sandbox'
    }
  } catch (error) {
    errorMessage.value = `Failed to load MTurk config: ${error.message}`
  }
}

const associateHit = async () => {
  if (!isSessionReady.value) {
    errorMessage.value = 'Please create or load a session first.'
    return
  }
  clearMessages()
  isLoading.value = true
  try {
    const encoded = encodeURIComponent(sessionIdentifier.value)
    const response = await fetch(`/api/mturk/sessions/${encoded}/associate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hit_id: hitId.value.trim(), environment: environment.value }),
    })
    const result = await response.json()
    if (response.ok && result.success) {
      successMessage.value = 'HIT associated successfully.'
      await fetchAssignments()
    } else {
      errorMessage.value = result.error || 'Failed to associate HIT.'
    }
  } catch (error) {
    errorMessage.value = `Failed to associate HIT: ${error.message}`
  } finally {
    isLoading.value = false
  }
}

const fetchAssignments = async () => {
  if (!isSessionReady.value) return
  clearMessages()
  isLoading.value = true
  try {
    const encoded = encodeURIComponent(sessionIdentifier.value)
    const response = await fetch(`/api/mturk/sessions/${encoded}/assignments`)
    const result = await response.json()
    if (response.ok && result.success) {
      assignments.value = result.assignments || []
    } else {
      assignments.value = []
      errorMessage.value = result.error || 'Failed to fetch assignments.'
    }
  } catch (error) {
    assignments.value = []
    errorMessage.value = `Failed to fetch assignments: ${error.message}`
  } finally {
    isLoading.value = false
  }
}

const approve = async (assignmentId) => {
  clearMessages()
  isLoading.value = true
  try {
    const response = await fetch(`/api/mturk/assignments/${assignmentId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ environment: environment.value }),
    })
    const result = await response.json()
    if (response.ok && result.success) {
      successMessage.value = `Approved assignment ${assignmentId}.`
      await fetchAssignments()
    } else {
      errorMessage.value = result.error || 'Failed to approve assignment.'
    }
  } catch (error) {
    errorMessage.value = `Failed to approve assignment: ${error.message}`
  } finally {
    isLoading.value = false
  }
}

const reject = async (assignmentId) => {
  const reason = window.prompt('Please provide a reason for rejection:')
  if (!reason || !reason.trim()) return
  clearMessages()
  isLoading.value = true
  try {
    const response = await fetch(`/api/mturk/assignments/${assignmentId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason.trim(), environment: environment.value }),
    })
    const result = await response.json()
    if (response.ok && result.success) {
      successMessage.value = `Rejected assignment ${assignmentId}.`
      await fetchAssignments()
    } else {
      errorMessage.value = result.error || 'Failed to reject assignment.'
    }
  } catch (error) {
    errorMessage.value = `Failed to reject assignment: ${error.message}`
  } finally {
    isLoading.value = false
  }
}

watch(
  () => sessionIdentifier.value,
  async () => {
    assignments.value = []
    await fetchConfig()
    await fetchAssignments()
  },
  { immediate: true }
)

onMounted(async () => {
  await fetchConfig()
})
</script>

<style scoped>
.mturk-panel { display: flex; flex-direction: column; gap: 1rem; }
.form-card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px; }
.card-title { font-weight: 600; margin-bottom: 6px; font-size: 13px; color: #374151; }
.form-grid { display: grid; grid-template-columns: 1fr; gap: 6px; }
.form-row { width: 100%; min-width: 0; }
.input, .select { width: 100%; max-width: 100%; box-sizing: border-box; padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 12px; min-width: 0; }
.btn { padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600; }
.btn.primary { background: #2563eb; color: #fff; }
.btn.secondary { background: #f3f4f6; color: #374151; }
.btn.danger { background: #dc2626; color: #fff; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.section-title { display: flex; justify-content: space-between; align-items: center; font-weight: 600; font-size: 14px; color: #374151; }
.helper-box { background: #f8fafc; border: 1px solid #e2e8f0; padding: 8px; border-radius: 6px; font-size: 12px; color: #334155; }
.url { display: block; margin-top: 6px; white-space: pre-wrap; word-break: break-all; }
.loading-message, .empty-message { padding: 12px; text-align: center; color: #6b7280; font-size: 13px; }
.error-message { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; padding: 8px; border-radius: 6px; font-size: 12px; }
.success-message { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; padding: 8px; border-radius: 6px; font-size: 12px; }
.manage-table { border: 1px solid #e5e7eb; border-radius: 6px; background: #fff; display: flex; flex-direction: column; overflow-x: auto; }
.table-head, .tr { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 2fr; gap: 8px; padding: 8px; }
.table-head { background: #f9fafb; border-bottom: 1px solid #e5e7eb; font-weight: 600; font-size: 12px; color: #374151; }
.tr { border-bottom: 1px solid #f3f4f6; }
.td, .th { font-size: 12px; color: #374151; display: flex; align-items: center; }
.td.actions { gap: 6px; }
</style>
