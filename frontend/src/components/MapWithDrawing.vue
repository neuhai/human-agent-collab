<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import MapDisplay from './MapDisplay.vue'
import MapToolbox from './MapToolbox.vue'
import { logActionToBackend } from '../composables/useActionLog.js'

const props = defineProps({
  map: {
    type: Object,
    default: null
  },
  showToolbox: {
    type: Boolean,
    default: false
  }
})

const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']
const TXT_EXTENSIONS = ['txt']
const PDF_EXTENSIONS = ['pdf']

const canDraw = computed(() => {
  if (!props.map || !props.map.filename) return false
  const ext = props.map.filename.split('.').pop()?.toLowerCase() || ''
  return IMAGE_EXTENSIONS.includes(ext) || TXT_EXTENSIONS.includes(ext)
})

const mapType = computed(() => {
  if (!props.map || !props.map.filename) return null
  const ext = props.map.filename.split('.').pop()?.toLowerCase() || ''
  if (IMAGE_EXTENSIONS.includes(ext)) return 'image'
  if (PDF_EXTENSIONS.includes(ext)) return 'pdf'
  if (TXT_EXTENSIONS.includes(ext)) return 'txt'
  return null
})

const tool = ref('brush')
const filledCells = ref(new Set())
const canvasRef = ref(null)
const containerRef = ref(null)
const isDrawing = ref(false)
const lastCell = ref(null)

/** Get current map image as base64 (follower, image map only). Exports at 2x resolution for clarity. */
const getMapImage = () => {
  if (!props.showToolbox || mapType.value !== 'image' || !canvasRef.value) return null
  try {
    const canvas = canvasRef.value
    const scale = Math.max(2, window.devicePixelRatio || 1)
    const w = canvas.width
    const h = canvas.height
    const off = document.createElement('canvas')
    off.width = w * scale
    off.height = h * scale
    const ctx = off.getContext('2d')
    ctx.scale(scale, scale)
    ctx.drawImage(canvas, 0, 0)
    return off.toDataURL('image/png')
  } catch {
    return null
  }
}

/** Log map action (tool click or draw stop). For follower, includes map_image (image) or filledCells (txt). */
const logMapAction = async (actionType, actionContent) => {
  let mapImage = null
  let metadata = {}
  if (props.showToolbox) {
    mapImage = getMapImage()
    if (mapType.value === 'txt' && filledCells.value.size > 0) {
      metadata = { filledCells: [...filledCells.value] }
    }
  }
  await logActionToBackend({ actionType, actionContent, mapImage, metadata })
}

const onToolChange = async (newTool) => {
  await logMapAction('map_tool_click', newTool)
  tool.value = newTool
}

const onTxtMouseUp = async () => {
  if (isDrawing.value && props.showToolbox) await logMapAction('map_draw_stop', 'brush_release')
  isDrawing.value = false
}

const onTxtMouseLeave = async () => {
  if (isDrawing.value && props.showToolbox) await logMapAction('map_draw_stop', 'mouse_leave')
  isDrawing.value = false
}

const mapUrl = computed(() => {
  if (!props.map) return ''
  const path = props.map.file_path || `/api/maps/${props.map.filename}`
  return path.startsWith('/') ? path : `/${path}`
})

const txtContent = ref('')
const txtLoading = ref(false)
const txtError = ref(null)

const resetDrawing = async () => {
  await logMapAction('map_tool_click', 'reset')
  filledCells.value = new Set()
  if (mapType.value === 'image' && canvasCtx.value && canvasImage.value) {
    canvasCtx.value.clearRect(0, 0, canvasRef.value?.width || 0, canvasRef.value?.height || 0)
  }
  scheduleSyncMapProgress()
}

const getCellKey = (row, col) => `${row},${col}`

const handleTxtCellClick = (row, col) => {
  if (!canDraw.value || !props.showToolbox) return
  const key = getCellKey(row, col)
  if (tool.value === 'brush') {
    filledCells.value = new Set([...filledCells.value, key])
  } else if (tool.value === 'eraser') {
    const next = new Set(filledCells.value)
    next.delete(key)
    filledCells.value = next
  }
  scheduleSyncMapProgress()
}

const handleTxtCellEnter = (row, col) => {
  if (!canDraw.value || !props.showToolbox || !isDrawing.value) return
  const key = getCellKey(row, col)
  if (lastCell.value === key) return
  lastCell.value = key
  if (tool.value === 'brush') {
    filledCells.value = new Set([...filledCells.value, key])
  } else if (tool.value === 'eraser') {
    const next = new Set(filledCells.value)
    next.delete(key)
    filledCells.value = next
  }
  scheduleSyncMapProgress()
}

const isCellFilled = (row, col) => filledCells.value.has(getCellKey(row, col))

const canvasCtx = ref(null)
const canvasImage = ref(null)
const drawStart = ref(null)

const mounted = ref(true)

const initCanvas = () => {
  if (!mounted.value || !containerRef.value || !canvasRef.value || mapType.value !== 'image') return
  const img = containerRef.value.querySelector('.map-image')
  if (!img) return
  const onLoad = () => {
    if (!mounted.value || !canvasRef.value) return
    const canvas = canvasRef.value
    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    canvas.style.width = img.offsetWidth + 'px'
    canvas.style.height = img.offsetHeight + 'px'
    canvasCtx.value = canvas.getContext('2d')
    canvasImage.value = img
  }
  if (img.complete) onLoad()
  else img.addEventListener('load', onLoad)
}

const getCanvasCoords = (e) => {
  const canvas = canvasRef.value
  if (!canvas) return null
  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height
  return {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top) * scaleY
  }
}

const handleCanvasMouseDown = (e) => {
  if (!canDraw.value || !props.showToolbox || mapType.value !== 'image') return
  isDrawing.value = true
  const coords = getCanvasCoords(e)
  if (coords && canvasCtx.value) {
    drawStart.value = coords
    if (tool.value === 'brush') {
      canvasCtx.value.beginPath()
      canvasCtx.value.arc(coords.x, coords.y, 4, 0, Math.PI * 2)
      canvasCtx.value.fillStyle = '#000'
      canvasCtx.value.fill()
    } else if (tool.value === 'eraser') {
      canvasCtx.value.clearRect(coords.x - 16, coords.y - 16, 32, 32)
    }
  }
}

const handleCanvasMouseMove = (e) => {
  if (!isDrawing.value || !canvasCtx.value) return
  const coords = getCanvasCoords(e)
  if (!coords) return
  if (tool.value === 'brush' && drawStart.value) {
    canvasCtx.value.beginPath()
    canvasCtx.value.moveTo(drawStart.value.x, drawStart.value.y)
    canvasCtx.value.lineTo(coords.x, coords.y)
    canvasCtx.value.strokeStyle = '#000'
    canvasCtx.value.lineWidth = 8
    canvasCtx.value.lineCap = 'round'
    canvasCtx.value.stroke()
    drawStart.value = coords
  } else if (tool.value === 'eraser') {
    canvasCtx.value.clearRect(coords.x - 16, coords.y - 16, 32, 32)
  }
}

const handleCanvasMouseUp = async () => {
  if (isDrawing.value && props.showToolbox) {
    await logMapAction('map_draw_stop', 'brush_release')
  }
  isDrawing.value = false
  if (props.showToolbox && mapType.value === 'image') scheduleSyncMapProgress()
}

const handleCanvasMouseLeave = async () => {
  if (isDrawing.value && props.showToolbox) {
    await logMapAction('map_draw_stop', 'mouse_leave')
  }
  isDrawing.value = false
  if (props.showToolbox && mapType.value === 'image') scheduleSyncMapProgress()
}

// Sync map_progress to backend for guider's Info Dashboard (follower only)
let syncTimeout = null
const scheduleSyncMapProgress = () => {
  if (!props.showToolbox || !canDraw.value || !props.map) return
  if (syncTimeout) clearTimeout(syncTimeout)
  syncTimeout = setTimeout(syncMapProgress, 300)
}

const syncMapProgress = async () => {
  if (!props.showToolbox || !canDraw.value || !props.map) return
  const sessionId = sessionStorage.getItem('session_id') || sessionStorage.getItem('session_code')
  const participantId = sessionStorage.getItem('participant_id')
  if (!sessionId || !participantId) return

  let mapProgress = { map: props.map }
  if (mapType.value === 'txt') {
    mapProgress.filledCells = [...filledCells.value]
  } else if (mapType.value === 'image' && canvasRef.value) {
    try {
      mapProgress.canvasDataUrl = canvasRef.value.toDataURL('image/png')
    } catch {
      return
    }
  }

  try {
    const enc = encodeURIComponent(sessionId)
    await fetch(`/api/sessions/${enc}/participants/${participantId}/map_progress`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ map_progress: mapProgress })
    })
  } catch (e) {
    console.warn('[MapWithDrawing] Failed to sync map_progress:', e)
  }
}

const loadTxtContent = async () => {
  if (mapType.value !== 'txt' || !mapUrl.value) return
  txtLoading.value = true
  txtError.value = null
  try {
    const url = mapUrl.value.startsWith('http') ? mapUrl.value : `${window.location.origin}${mapUrl.value}`
    const res = await fetch(url)
    if (!res.ok) throw new Error(`Failed to load map (${res.status})`)
    txtContent.value = await res.text()
  } catch (e) {
    txtError.value = e?.message || 'Failed to load map'
    txtContent.value = ''
  } finally {
    txtLoading.value = false
  }
}

watch(() => props.map?.id ?? null, (newId, oldId) => {
  // Only reset when map actually changes (different id), not when object reference changes
  // (e.g. from participants_updated broadcast after syncMapProgress)
  if (oldId !== undefined && newId === oldId) return
  resetDrawing()
  lastCell.value = null
  txtContent.value = ''
  txtError.value = null
  if (mapType.value === 'txt') loadTxtContent()
  else setTimeout(initCanvas, 150)
}, { immediate: true })

watch(() => props.showToolbox, () => {
  if (props.showToolbox && mapType.value === 'image') setTimeout(initCanvas, 150)
})

const TXT_CELL_SIZE = 14
const TXT_MAX_HEIGHT = 600
const TXT_MAX_WIDTH = 400

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
  const naturalH = rows * TXT_CELL_SIZE
  const naturalW = cols * TXT_CELL_SIZE
  const scaleH = TXT_MAX_HEIGHT / naturalH
  const scaleW = TXT_MAX_WIDTH / naturalW
  return Math.min(1, scaleH, scaleW)
})

onMounted(() => {
  if (mapType.value === 'txt') loadTxtContent()
  else if (mapType.value === 'image' && props.showToolbox) setTimeout(initCanvas, 150)
})

onBeforeUnmount(() => {
  mounted.value = false
})
</script>

<template>
  <div class="map-with-drawing">
    <div ref="containerRef" class="map-container">
      <!-- Image or PDF: use MapDisplay (no drawing for PDF) -->
      <div v-if="mapType === 'image' || mapType === 'pdf' || !mapType" class="map-inner">
        <MapDisplay :map="map" />
        <canvas
          v-if="mapType === 'image' && showToolbox && canDraw"
          ref="canvasRef"
          class="drawing-canvas"
          @mousedown="handleCanvasMouseDown"
          @mousemove="handleCanvasMouseMove"
          @mouseup="handleCanvasMouseUp"
          @mouseleave="handleCanvasMouseLeave"
        />
      </div>
      <!-- TXT: render here for drawing support -->
      <div v-else-if="mapType === 'txt'" class="map-txt-drawable">
        <div v-if="txtLoading" class="map-loading">Loading map...</div>
        <div v-else-if="txtError" class="map-error">{{ txtError }}</div>
        <div
          v-else
          class="txt-grid"
          :style="{ transform: `scale(${txtScale})` }"
          @mousedown="isDrawing = true"
          @mouseup="onTxtMouseUp"
          @mouseleave="onTxtMouseLeave"
        >
          <template v-for="(line, row) in txtLines" :key="row">
          <div class="txt-row">
            <span
              v-for="(char, col) in line"
              :key="col"
              class="txt-cell"
              :class="{ filled: showToolbox && isCellFilled(row, col) }"
              @mousedown="handleTxtCellClick(row, col)"
              @mouseenter="handleTxtCellEnter(row, col)"
            >{{ char || '\u00A0' }}</span>
          </div>
          </template>
        </div>
      </div>
    </div>
    <MapToolbox
      v-if="showToolbox && canDraw"
      :tool="tool"
      @update:tool="onToolChange"
      @reset="resetDrawing"
    />
  </div>
</template>

<style scoped>
.map-with-drawing {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.map-container {
  position: relative;
  width: 100%;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.map-inner {
  position: relative;
  height: 100%;
  max-height: 100%;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.drawing-canvas {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: auto;
  cursor: crosshair;
}

.map-txt-drawable {
  width: 100%;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  justify-content: center;
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
  min-width: 14px;
  width: 14px;
  height: 14px;
  font-family: monospace;
  font-size: 10px;
  line-height: 1;
  user-select: none;
}

.txt-cell.filled {
  background-color: #000;
  color: #fff;
}

.map-loading,
.map-error {
  padding: 24px;
  text-align: center;
  color: #6b7280;
}

.map-error {
  color: #dc2626;
}
</style>
