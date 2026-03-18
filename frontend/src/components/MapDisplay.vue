<script setup>
import { ref, computed, watch, onMounted } from 'vue'

const props = defineProps({
  map: {
    type: Object,
    default: null
  }
})

const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']
const PDF_EXTENSIONS = ['pdf']
const TXT_EXTENSIONS = ['txt']

const mapType = computed(() => {
  if (!props.map || !props.map.filename) return null
  const ext = props.map.filename.split('.').pop()?.toLowerCase() || ''
  if (IMAGE_EXTENSIONS.includes(ext)) return 'image'
  if (PDF_EXTENSIONS.includes(ext)) return 'pdf'
  if (TXT_EXTENSIONS.includes(ext)) return 'txt'
  return 'image'
})

const mapUrl = computed(() => {
  if (!props.map) return ''
  const path = props.map.file_path || `/api/maps/${props.map.filename}`
  return path.startsWith('/') ? path : `/${path}`
})

const CELL_SIZE = 14
const MAX_HEIGHT = 600
const MAX_WIDTH = 400

const txtContent = ref('')
const txtLines = computed(() => {
  if (!txtContent.value) return []
  const normalized = txtContent.value.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const lines = normalized.split('\n')
  if (lines.length === 0) return []
  const maxLen = Math.max(...lines.map(l => l.length), 1)
  return lines.map(line => line.padEnd(maxLen, ' '))
})

const txtScale = computed(() => {
  const lines = txtLines.value
  if (lines.length === 0) return 1
  const rows = lines.length
  const cols = lines[0]?.length || 1
  const naturalH = rows * CELL_SIZE
  const naturalW = cols * CELL_SIZE
  const scaleH = MAX_HEIGHT / naturalH
  const scaleW = MAX_WIDTH / naturalW
  return Math.min(1, scaleH, scaleW)
})

const loading = ref(false)
const error = ref(null)

const loadTxtContent = async () => {
  if (mapType.value !== 'txt' || !mapUrl.value) return
  loading.value = true
  error.value = null
  try {
    const url = mapUrl.value.startsWith('http') ? mapUrl.value : `${window.location.origin}${mapUrl.value}`
    const res = await fetch(url)
    if (!res.ok) throw new Error(`Failed to load map (${res.status})`)
    txtContent.value = await res.text()
  } catch (e) {
    error.value = e?.message || 'Failed to load map'
    txtContent.value = ''
  } finally {
    loading.value = false
  }
}

watch(() => props.map, () => {
  txtContent.value = ''
  if (mapType.value === 'txt') loadTxtContent()
}, { immediate: true })

onMounted(() => {
  if (mapType.value === 'txt') loadTxtContent()
})
</script>

<template>
  <div v-if="!map" class="map-display-empty">No map assigned</div>
  <div v-else class="map-display" :class="mapType">
    <!-- Image -->
    <img v-if="mapType === 'image'" :src="mapUrl" :alt="map.original_filename || 'Map'" class="map-image" />
    
    <!-- PDF -->
    <iframe v-else-if="mapType === 'pdf'" :src="mapUrl" class="map-pdf" frameborder="0" title="Map PDF"></iframe>
    
    <!-- TXT -->
    <div v-else-if="mapType === 'txt'" class="map-txt">
      <div v-if="loading" class="map-loading">Loading...</div>
      <div v-else-if="error" class="map-error">{{ error }}</div>
      <div v-else class="txt-grid" :style="{ transform: `scale(${txtScale})` }">
        <div v-for="(line, row) in txtLines" :key="row" class="txt-row">
          <span v-for="(char, col) in line" :key="col" class="txt-cell">{{ char || '\u00A0' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-display {
  width: 100%;
  height: 100%;
  min-height: 120px;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  overflow: hidden;
}

.map-display-empty {
  padding: 24px;
  color: #6b7280;
  text-align: center;
}

.map-image {
  max-height: 100%;
  width: auto;
  max-width: 100%;
  object-fit: contain;
  display: block;
}

.map-pdf {
  width: 100%;
  height: 100%;
  min-height: 200px;
  object-fit: contain;
}

.map-txt {
  width: 100%;
  height: 100%;
  overflow: hidden;
  display: flex;
  justify-content: center;
}

.map-loading,
.map-error {
  padding: 16px;
  text-align: center;
  color: #6b7280;
}

.map-error {
  color: #dc2626;
}

.txt-grid {
  display: flex;
  flex-direction: column;
  width: fit-content;
  transform-origin: top center;
}

.txt-row {
  display: flex;
}

.txt-cell {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  min-width: 14px;
  height: 14px;
  font-family: monospace;
  font-size: 10px;
  line-height: 1;
}
</style>
