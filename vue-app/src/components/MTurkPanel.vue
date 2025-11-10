<template>
  <div class="mturk-panel">
    <div class="association-section">
      <h3>Associate mTurk HIT</h3>
      <div class="form-group">
        <label for="hit-id">HIT ID</label>
        <input type="text" id="hit-id" v-model="hitId" placeholder="Enter HIT ID from mTurk" />
      </div>
      <div class="form-group">
        <label>Environment</label>
        <div class="radio-group">
          <label><input type="radio" v-model="environment" value="sandbox" /> Sandbox</label>
          <label><input type="radio" v-model="environment" value="production" /> Production</label>
        </div>
      </div>
      <button @click="associateHit" :disabled="!hitId || !environment">Associate HIT</button>
    </div>

    <div class="review-section">
      <h3>Review Assignments</h3>
      <button @click="fetchAssignments">Refresh Assignments</button>
      <div v-if="isLoading">Loading...</div>
      <div v-else-if="assignments.length === 0">No assignments to review.</div>
      <table v-else>
        <thead>
          <tr>
            <th>Worker ID</th>
            <th>Assignment ID</th>
            <th>Status</th>
            <th>Platform Data</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="assignment in assignments" :key="assignment.AssignmentId">
            <td>{{ assignment.WorkerId }}</td>
            <td>{{ assignment.AssignmentId }}</td>
            <td>{{ assignment.AssignmentStatus }}</td>
            <td><!-- Placeholder for platform data --></td>
            <td>
              <button @click="approve(assignment.AssignmentId)" :disabled="assignment.AssignmentStatus !== 'Submitted'">Approve</button>
              <button @click="reject(assignment.AssignmentId)" :disabled="assignment.AssignmentStatus !== 'Submitted'">Reject</button>
            </td>
          </tr>
        </tbody>
      </table>
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
  gap: 2rem;
}
.form-group {
  margin-bottom: 1rem;
}
.radio-group {
  display: flex;
  gap: 1rem;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}
th, td {
  border: 1px solid #ddd;
  padding: 8px;
  text-align: left;
}
th {
  background-color: #f2f2f2;
}
</style>
