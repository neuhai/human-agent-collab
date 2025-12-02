<template>
  <div class="mturk-panel">
    <div class="manage-forms">
      <div class="form-card">
        <div class="card-title">Associate mTurk HIT</div>
        <div class="form-grid">
          <div class="form-row">
            <input 
              class="input" 
              type="text" 
              id="hit-id" 
              v-model="hitId" 
              placeholder="Enter HIT ID from mTurk" 
            />
          </div>
          <div class="form-row">
            <select class="select" v-model="environment">
              <option value="">Select Environment</option>
              <option value="sandbox">Sandbox</option>
              <option value="production">Production</option>
            </select>
          </div>
          <div class="form-row">
            <button class="btn primary" @click="associateHit" :disabled="!hitId || !environment">
              Associate HIT
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="table-section">
      <div class="section-title">
        Review Assignments
        <button class="btn secondary" @click="fetchAssignments" :disabled="isLoading">
          {{ isLoading ? 'Loading...' : 'Refresh Assignments' }}
        </button>
      </div>
      <div v-if="isLoading" class="loading-message">Loading assignments...</div>
      <div v-else-if="assignments.length === 0" class="empty-message">No assignments to review.</div>
      <div v-else class="manage-table">
        <div class="table-head">
          <div class="th">Worker ID</div>
          <div class="th">Assignment ID</div>
          <div class="th">Status</div>
          <div class="th">Platform Data</div>
          <div class="th actions">Actions</div>
        </div>
        <div class="table-body">
          <div class="tr" v-for="assignment in assignments" :key="assignment.AssignmentId">
            <div class="td">{{ assignment.WorkerId }}</div>
            <div class="td">{{ assignment.AssignmentId }}</div>
            <div class="td">{{ assignment.AssignmentStatus }}</div>
            <div class="td"><!-- Placeholder for platform data --></div>
            <div class="td actions">
              <button 
                class="btn primary" 
                @click="approve(assignment.AssignmentId)" 
                :disabled="assignment.AssignmentStatus !== 'Submitted'"
              >
                Approve
              </button>
              <button 
                class="btn danger" 
                @click="reject(assignment.AssignmentId)" 
                :disabled="assignment.AssignmentStatus !== 'Submitted'"
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
import { ref, onMounted } from 'vue';
import { BACKEND_URL } from '@/config.js';

const props = defineProps({
  sessionCode: {
    type: String,
    required: true,
  },
});

const hitId = ref('');
const environment = ref('sandbox');
const assignments = ref([]);
const isLoading = ref(false);

const associateHit = async () => {
  if (!props.sessionCode) {
    alert('Please create or load a session first.');
    return;
  }
  try {
    const response = await fetch(`${BACKEND_URL}/api/mturk/sessions/${props.sessionCode}/associate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hit_id: hitId.value, environment: environment.value }),
    });
    const result = await response.json();
    if (response.ok && result.success) {
      alert('HIT associated successfully.');
      fetchAssignments();
    } else {
      alert(`Error associating HIT: ${result.error}`);
    }
  } catch (error) {
    alert(`Error associating HIT: ${error.message}`);
  }
};

const fetchAssignments = async () => {
  if (!props.sessionCode) return;
  isLoading.value = true;
  try {
    const response = await fetch(`${BACKEND_URL}/api/mturk/sessions/${props.sessionCode}/assignments`);
    const result = await response.json();
    if (response.ok && result.success) {
      assignments.value = result.assignments;
    } else {
      console.error('Failed to fetch assignments:', result.error);
      assignments.value = [];
    }
  } catch (error) {
    console.error('Error fetching assignments:', error.message);
    assignments.value = [];
  } finally {
    isLoading.value = false;
  }
};

const approve = async (assignmentId) => {
  try {
    const response = await fetch(`${BACKEND_URL}/api/mturk/assignments/${assignmentId}/approve`, {
      method: 'POST',
    });
    const result = await response.json();
    if (response.ok && result.success) {
      alert('Assignment approved.');
      fetchAssignments();
    } else {
      alert(`Error approving assignment: ${result.error}`);
    }
  } catch (error) {
    alert(`Error approving assignment: ${error.message}`);
  }
};

const reject = async (assignmentId) => {
  const reason = prompt('Please provide a reason for rejection:');
  if (reason) {
    try {
      const response = await fetch(`${BACKEND_URL}/api/mturk/assignments/${assignmentId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
      });
      const result = await response.json();
      if (response.ok && result.success) {
        alert('Assignment rejected.');
        fetchAssignments();
      } else {
        alert(`Error rejecting assignment: ${result.error}`);
      }
    } catch (error) {
      alert(`Error rejecting assignment: ${error.message}`);
    }
  }
};

onMounted(() => {
  if (props.sessionCode) {
    fetchAssignments();
  }
});
</script>

<style scoped>
.mturk-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.manage-forms {
  margin-bottom: 1rem;
}

.form-card {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 10px;
}

.card-title {
  font-weight: 600;
  margin-bottom: 6px;
  font-size: 13px;
  color: #374151;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
}

.form-row {
  margin-bottom: 6px;
}

.input, .select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 12px;
}

.select:disabled {
  background-color: #f9fafb;
  color: #9ca3af;
  cursor: not-allowed;
  opacity: 0.7;
}

.btn {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.15s ease;
}

.btn.primary {
  background: #2563eb;
  color: #fff;
}

.btn.primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn.secondary {
  background-color: #f3f4f6;
  color: #374151;
}

.btn.secondary:hover:not(:disabled) {
  background-color: #e5e7eb;
}

.btn.danger {
  background: #dc2626;
  color: #fff;
}

.btn.danger:hover:not(:disabled) {
  background: #b91c1c;
}

.table-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
  color: #374151;
}

.loading-message,
.empty-message {
  padding: 12px;
  text-align: center;
  color: #6b7280;
  font-size: 13px;
}

.manage-table {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  overflow-x: auto;
}

.table-head {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr 2fr;
  gap: 8px;
  padding: 8px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 600;
  font-size: 12px;
  color: #374151;
}

.table-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f1f5f9;
}

.table-body::-webkit-scrollbar {
  width: 6px;
}

.table-body::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.table-body::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.table-body::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.tr {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr 2fr;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid #f3f4f6;
}

.tr:hover {
  background: #f9fafb;
}

.td {
  font-size: 12px;
  color: #374151;
  display: flex;
  align-items: center;
}

.td.actions {
  display: flex;
  gap: 6px;
  justify-content: flex-start;
}

.th {
  font-size: 12px;
  color: #374151;
}

.th.actions {
  text-align: left;
}
</style>
