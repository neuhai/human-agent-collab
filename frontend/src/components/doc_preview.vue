<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  essay: {
    type: Object,
    default: null
  },
  // For reading window mode
  mode: {
    type: String,
    default: 'preview', // 'preview' or 'reading_window'
    validator: (value) => ['preview', 'reading_window'].includes(value)
  },
  label: {
    type: String,
    default: 'Document Preview'
  },
  readingTimeRemaining: {
    type: Number,
    default: 0 // in seconds
  },
  allowClose: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['close'])

const pdfUrl = ref('')
const loading = ref(false)
const error = ref(null)

const loadPdf = () => {
  if (!props.essay || !props.show) {
    return
  }
  
  loading.value = true
  error.value = null
  
  // Get PDF URL from essay object
  // Try multiple possible paths for the file
  let filePath = null
  
  if (props.essay.file_path) {
    filePath = props.essay.file_path
  } else if (props.essay.filename) {
    // Check if it's already a full URL or just a filename
    if (props.essay.filename.startsWith('http') || props.essay.filename.startsWith('/')) {
      filePath = props.essay.filename
    } else {
      filePath = `/api/essays/${props.essay.filename}`
    }
  } else if (props.essay.id) {
    filePath = `/api/essays/${props.essay.id}`
  } else if (typeof props.essay === 'string') {
    // If essay is just a string (filename), use it directly
    if (props.essay.startsWith('http') || props.essay.startsWith('/')) {
      filePath = props.essay
    } else {
      filePath = `/api/essays/${props.essay}`
    }
  }
  
  if (!filePath) {
    console.error('[DocPreview] Could not determine file path from essay object:', props.essay)
    error.value = 'Could not determine document path'
    loading.value = false
    return
  }
  
  // Ensure the URL is absolute if it's a relative path
  if (filePath && !filePath.startsWith('http') && filePath.startsWith('/')) {
    // It's already an absolute path, use as-is
    pdfUrl.value = filePath
  } else if (filePath && !filePath.startsWith('http')) {
    // Make it absolute
    pdfUrl.value = filePath.startsWith('/') ? filePath : `/${filePath}`
  } else {
    pdfUrl.value = filePath
  }
  
  loading.value = false
}

const close = () => {
  if (props.allowClose) {
    emit('close')
    pdfUrl.value = ''
    error.value = null
  }
}

// Format timer display
const formatTimer = (seconds) => {
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    loadPdf()
  }
})

watch(() => props.essay, () => {
  if (props.show) {
    loadPdf()
  }
})

onMounted(() => {
  if (props.show) {
    loadPdf()
  }
})
</script>

<template>
  <div v-if="show" class="doc-preview-overlay" :class="{ 'reading-window-mode': mode === 'reading_window' }" @click.self="close">
    <!-- Reading Window Timer Header -->
    <div v-if="mode === 'reading_window'" class="reading-window-timer-header">
      <div class="reading-timer">
        Remaining Time: {{ formatTimer(readingTimeRemaining) }}
      </div>
    </div>
    
    <div class="doc-preview-container">
      <div class="doc-preview-header">
        <h3 class="doc-preview-title">{{ mode === 'reading_window' ? label : (essay?.title || 'Document Preview') }}</h3>
        <button v-if="allowClose" class="doc-preview-close" @click="close">
          <i class="fa-solid fa-times"></i>
        </button>
      </div>
      <div class="doc-preview-content">
        <div v-if="loading" class="doc-preview-loading">
          <i class="fa-solid fa-spinner fa-spin"></i>
          <span>Loading PDF...</span>
        </div>
        <div v-else-if="error" class="doc-preview-error">
          <i class="fa-solid fa-exclamation-triangle"></i>
          <span>{{ error }}</span>
        </div>
        <iframe
          v-else
          :src="pdfUrl"
          class="doc-preview-iframe"
          frameborder="0"
        ></iframe>
      </div>
    </div>
  </div>
</template>

<style scoped>
.doc-preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 20px;
}

.doc-preview-overlay.reading-window-mode {
  pointer-events: none;
}

.doc-preview-overlay.reading-window-mode .doc-preview-container {
  pointer-events: auto;
}

.reading-window-timer-header {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: white;
  padding: 12px 24px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  z-index: 10001;
  display: flex;
  align-items: center;
  gap: 20px;
}

.reading-window-timer-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}

.reading-timer {
  font-size: 14px;
  font-weight: 500;
  color: #3b82f6;
}

.doc-preview-container {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 1200px;
  height: 90%;
  max-height: 900px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.doc-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
  border-radius: 8px 8px 0 0;
}

.doc-preview-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  flex: 1;
}

.doc-preview-close {
  background: none;
  border: none;
  font-size: 20px;
  color: #6b7280;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.2s;
}

.doc-preview-close:hover {
  background: #e5e7eb;
  color: #111827;
}

.doc-preview-content {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.doc-preview-loading,
.doc-preview-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #6b7280;
  font-size: 16px;
}

.doc-preview-loading i {
  font-size: 32px;
  color: #3b82f6;
}

.doc-preview-error i {
  font-size: 32px;
  color: #ef4444;
}

.doc-preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
}
</style>
