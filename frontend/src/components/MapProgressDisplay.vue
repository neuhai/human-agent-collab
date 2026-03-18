<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  mapProgress: {
    type: Object,
    default: null
  }
})

const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']
const TXT_EXTENSIONS = ['txt']

const map = computed(() => props.mapProgress?.map ?? null)
const filledCellsSet = computed(() => {
  const arr = props.mapProgress?.filledCells
  return new Set(Array.isArray(arr) ? arr : [])
})
const canvasDataUrl = computed(() => props.mapProgress?.canvasDataUrl ?? null)

const mapType = computed(() => {
  if (!map.value?.filename) return null
  const ext = map.value.filename.split('.').pop()?.toLowerCase() || ''
  if (IMAGE_EXTENSIONS.includes(ext)) return 'image'
  if (TXT_EXTENSIONS.includes(ext)) return 'txt'
  return null
})

const mapUrl = computed(() => {
  if (!map.value) return ''
  const path = map.value.file_path || `/api/maps/${map.value.filename}`
  return path.startsWith('/') ? path : `/${path}`
})

const txtContent = ref('')
const txtLoading = ref(false)

const loadTxtContent = async () => {
  if (mapType.value !== 'txt' || !mapUrl.value) return
  txtLoading.value = true
  try {
    const url = mapUrl.value.startsWith('http') ? mapUrl.value : `${window.location.origin}${mapUrl.value}`
    const res = await fetch(url)
    if (!res.ok) throw new Error('Failed to load')
    txtContent.value = await res.text()
  } catch {
    txtContent.value = ''
  } finally {
    txtLoading.value = false
  }
}

const txtLines = computed(() => {
  if (!txtContent.value) return []
  const normalized = txtContent.value.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const lines = normalized.split('\n')
  if (lines.length === 0) return []
  const maxLen = Math.max(...lines.map(l => l.length), 1)
  return lines.map(line => line.padEnd(maxLen, ' '))
})

const getCellKey = (row, col) => `${row},${col}`
const isCellFilled = (row, col) => filledCellsSet.value.has(getCellKey(row, col))

watch(() => props.mapProgress?.map, () => {
  txtContent.value = ''
  if (mapType.value === 'txt') loadTxtContent()
}, { immediate: true })
</script>

<template>
  <div v-if="!mapProgress" class="map-progress-empty">No map progress yet</div>
  <div v-else class="map-progress-display">
    <!-- Image: show map with canvas overlay -->
    <div v-if="mapType === 'image'" class="map-progress-image">
      <div class="image-wrapper">
        <img :src="mapUrl" :alt="map?.original_filename || 'Map'" class="map-image" />
        <img
          v-if="canvasDataUrl"
          :src="canvasDataUrl"
          class="drawing-overlay"
          alt="Route"
        />
      </div>
    </div>
    <!-- TXT: show grid with filled cells -->
    <div v-else-if="mapType === 'txt'" class="map-progress-txt">
      <div v-if="txtLoading" class="map-loading">Loading...</div>
      <div v-else class="txt-grid">
        <div v-for="(line, row) in txtLines" :key="row" class="txt-row">
          <span
            v-for="(char, col) in line"
            :key="col"
            class="txt-cell"
            :class="{ filled: isCellFilled(row, col) }"
          >{{ char || '\u00A0' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-progress-empty {
  padding: 12px;
  color: #6b7280;
  font-size: 13px;
  font-style: italic;
}

.map-progress-display {
  width: 100%;
  max-width: 200px;
}

.map-progress-image {
  position: relative;
}

.image-wrapper {
  position: relative;
  width: 100%;
}

.map-image {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}

.drawing-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.map-progress-txt {
  font-family: monospace;
  font-size: 8px;
  line-height: 1;
}

.txt-grid {
  display: flex;
  flex-direction: column;
  width: fit-content;
}

.txt-row {
  display: flex;
}

.txt-cell {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 10px;
  min-width: 10px;
  height: 10px;
}

.txt-cell.filled {
  background-color: #000;
  color: #fff;
}

.map-loading {
  padding: 12px;
  text-align: center;
  color: #6b7280;
  font-size: 12px;
}
</style>
