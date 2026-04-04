<script setup>
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import AnnotationPopup from '../components/AnnotationPopup.vue'

const showPopup = ref(false)
const lastSubmit = ref('')

const onSubmit = (payload) => {
  const text = typeof payload === 'string' ? payload : (payload?.transcription || '')
  lastSubmit.value = text
  showPopup.value = false
  console.log('[AnnotationTest] Submitted:', text, typeof payload === 'object' ? payload?.submitted_at : '')
}
</script>

<template>
  <div class="test-page">
    <h1>Annotation Popup Test</h1>
    <p class="test-desc">Click the button below to open the annotation popup for testing.</p>
    <button class="open-btn" @click="showPopup = true">Open Annotation Popup</button>

    <p class="test-desc" style="margin-top: 24px;">Post-session annotation (uses sample data with guider participant):</p>
    <RouterLink to="/post-annotation?session_id=9b472636-6687-4130-8bae-0556525250ff&participant_id=3998d45e-20c4-4d6b-bc65-373fbb76b6b2" class="open-btn" style="display: inline-block; text-decoration: none;">Open Post-Session Annotation</RouterLink>

    <div v-if="lastSubmit" class="last-submit">
      <h3>Last submitted transcription:</h3>
      <pre>{{ lastSubmit }}</pre>
    </div>

    <AnnotationPopup
      :show="showPopup"
      :checkpoint-index="0"
      :allow-close="true"
      @submit="onSubmit"
      @close="showPopup = false"
    />
  </div>
</template>

<style scoped>
.test-page {
  padding: 40px;
  max-width: 600px;
  margin: 0 auto;
}

.test-page h1 {
  font-size: 24px;
  margin-bottom: 12px;
}

.test-desc {
  color: #6b7280;
  margin-bottom: 24px;
}

.open-btn {
  padding: 12px 24px;
  font-size: 16px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.open-btn:hover {
  background: #2563eb;
}

.last-submit {
  margin-top: 32px;
  padding: 16px;
  background: #f3f4f6;
  border-radius: 8px;
}

.last-submit h3 {
  font-size: 14px;
  margin-bottom: 8px;
  color: #374151;
}

.last-submit pre {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  margin: 0;
}
</style>
