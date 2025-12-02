<template>
  <div v-if="visible && fileUrl" class="file-preview-container">
    <!-- PDF preview -->
    <PdfPreview
      v-if="isPdf"
      :file-url="fileUrl"
      :visible="visible"
      @error="forwardError"
    />

    <!-- Word document preview (open in new tab / download) -->
    <div v-else-if="isWord" class="word-preview">
      <div class="word-header">
        <span class="word-icon">W</span>
        <div class="word-meta">
          <p class="word-filename"><strong>{{ filename || 'Word document' }}</strong></p>
          <p class="word-hint">This is a Word document. Click the button below to open it in a new tab.</p>
        </div>
      </div>
      <div class="word-actions">
        <a
          :href="fileUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="btn secondary"
        >
          Open document
        </a>
      </div>
    </div>

    <!-- Fallback for other file types -->
    <div v-else class="generic-preview">
      <p><strong>{{ filename || 'Document' }}</strong></p>
      <p class="generic-hint">
        In-browser preview is not available for this file type. You can download or open it using the button below.
      </p>
      <a
        :href="fileUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="btn secondary"
      >
        Open / Download
      </a>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import PdfPreview from './PdfPreview.vue'

const props = defineProps<{
  fileUrl?: string
  filename?: string
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'error', message: string): void
}>()

const extension = computed(() => {
  if (!props.filename) return ''
  const parts = props.filename.toLowerCase().split('.')
  return parts.length > 1 ? parts[parts.length - 1] : ''
})

const isPdf = computed(() => {
  return extension.value === 'pdf'
})

const isWord = computed(() => {
  return extension.value === 'doc' || extension.value === 'docx'
})

const forwardError = (message: string) => {
  emit('error', message)
}
</script>

<style scoped>
.file-preview-container {
  margin-top: 20px;
}

.word-preview {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px 16px;
  background: #f9fafb;
}

.word-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.word-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: #2563eb;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 18px;
}

.word-meta {
  display: flex;
  flex-direction: column;
}

.word-filename {
  margin: 0;
}

.word-hint {
  margin: 4px 0 0;
  font-size: 13px;
  color: #4b5563;
}

.word-actions {
  margin-top: 10px;
}

.generic-preview {
  border: 1px dashed #e5e7eb;
  border-radius: 6px;
  padding: 12px 16px;
  background: #f9fafb;
}

.generic-hint {
  margin-top: 4px;
  font-size: 13px;
  color: #4b5563;
}
</style>


