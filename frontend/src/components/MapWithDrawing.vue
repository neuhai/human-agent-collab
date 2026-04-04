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

/** Eraser radius in canvas pixel space (image resolution). */
const eraserRadius = ref(16)
const eraserPreview = ref({ visible: false, left: 0, top: 0, size: 0 })

/** Image map: stack of full-canvas ImageData after each completed stroke (for undo). */
const canvasUndoStack = ref([])
const txtUndoStack = ref([])

const pushCanvasUndoState = () => {
  if (!canvasRef.value || !canvasCtx.value || mapType.value !== 'image') return
  const c = canvasRef.value
  try {
    const data = canvasCtx.value.getImageData(0, 0, c.width, c.height)
    canvasUndoStack.value.push(data)
  } catch {
    /* ignore */
  }
}

const setsEqual = (a, b) => {
  if (!a || !b || a.size !== b.size) return false
  for (const x of a) if (!b.has(x)) return false
  return true
}

const pushTxtUndoStateIfChanged = () => {
  const last = txtUndoStack.value[txtUndoStack.value.length - 1]
  if (setsEqual(last, filledCells.value)) return
  txtUndoStack.value.push(new Set(filledCells.value))
}

const canUndo = computed(() => {
  if (mapType.value === 'image') return canvasUndoStack.value.length > 1
  if (mapType.value === 'txt') return txtUndoStack.value.length > 1
  return false
})

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

/** Log map action (tool click or draw stop). One rAF so canvas/tool UI updates before enqueue; useActionLog adds another rAF + captureActionContextSafe (2 rAF) for styled screenshots. */
const logMapAction = (actionType, actionContent, extraMetadata = {}) => {
  requestAnimationFrame(() => {
    let mapImage = null
    let metadata = { ...extraMetadata }
    if (props.showToolbox) {
      mapImage = getMapImage()
      if (mapType.value === 'txt' && filledCells.value.size > 0) {
        metadata = { ...metadata, filledCells: [...filledCells.value] }
      }
    }
    logActionToBackend({ actionType, actionContent, mapImage, metadata })
  })
}

const onToolChange = (newTool) => {
  tool.value = newTool
  logMapAction('map_tool_click', newTool)
}

const onTxtMouseUp = () => {
  const wasDrawing = isDrawing.value
  const strokeTool = tool.value
  isDrawing.value = false
  lastCell.value = null
  if (wasDrawing && props.showToolbox) {
    pushTxtUndoStateIfChanged()
    const drawStop =
      strokeTool === 'eraser' ? 'eraser_release' : 'brush_release'
    void logMapAction('map_draw_stop', drawStop, { stroke_tool: strokeTool })
  }
}

/** Only reset segment tracking; stroke ends on window pointerup/mouseup (avoids mouseleave-before-mouseup losing the log). */
const onTxtMouseLeave = () => {
  lastCell.value = null
}

const mapUrl = computed(() => {
  if (!props.map) return ''
  const path = props.map.file_path || `/api/maps/${props.map.filename}`
  return path.startsWith('/') ? path : `/${path}`
})

const txtContent = ref('')
const txtLoading = ref(false)
const txtError = ref(null)

const resetDrawing = () => {
  filledCells.value = new Set()
  txtUndoStack.value = [new Set()]
  if (mapType.value === 'image' && canvasCtx.value && canvasRef.value) {
    canvasCtx.value.clearRect(0, 0, canvasRef.value.width || 0, canvasRef.value.height || 0)
    canvasUndoStack.value = []
    pushCanvasUndoState()
  }
  scheduleSyncMapProgress()
  logMapAction('map_tool_click', 'reset')
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

const ERASER_RADIUS_MIN = 4
const ERASER_RADIUS_MAX = 72

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
    canvasUndoStack.value = []
    pushCanvasUndoState()
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

/** Circular erase (transparent hole) using current radius in canvas pixels. */
const eraseCircleAt = (ctx, x, y, r) => {
  ctx.save()
  ctx.globalCompositeOperation = 'destination-out'
  ctx.beginPath()
  ctx.arc(x, y, r, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

const updateEraserPreview = (e) => {
  if (tool.value !== 'eraser' || mapType.value !== 'image' || !canvasRef.value) return
  const canvas = canvasRef.value
  const scale = canvas.clientWidth / canvas.width
  const rCss = eraserRadius.value * scale
  eraserPreview.value = {
    visible: true,
    left: e.offsetX - rCss,
    top: e.offsetY - rCss,
    size: rCss * 2
  }
}

const canvasPointerDown = ref(false)
/** Pointer id when setPointerCapture is active (primary button drawing). */
const canvasCapturedPointerId = ref(null)

const releaseCanvasPointerCaptureIfAny = () => {
  const id = canvasCapturedPointerId.value
  const el = canvasRef.value
  if (id != null && el?.releasePointerCapture) {
    try {
      el.releasePointerCapture(id)
    } catch {
      /* ignore */
    }
  }
  canvasCapturedPointerId.value = null
}

const finishCanvasStroke = () => {
  const wasDrawing = isDrawing.value
  const strokeTool = tool.value
  isDrawing.value = false
  drawStart.value = null
  canvasPointerDown.value = false
  releaseCanvasPointerCaptureIfAny()
  if (!wasDrawing || !props.showToolbox) {
    if (props.showToolbox && mapType.value === 'image') scheduleSyncMapProgress()
    return
  }
  if (mapType.value === 'image') pushCanvasUndoState()
  const drawStop =
    strokeTool === 'eraser' ? 'eraser_release' : 'brush_release'
  void logMapAction('map_draw_stop', drawStop, { stroke_tool: strokeTool })
  if (props.showToolbox && mapType.value === 'image') scheduleSyncMapProgress()
}

/** End image-canvas or txt-grid stroke when button is released anywhere (canvas mouseup misses releases outside the element). */
const onWindowStrokeEnd = () => {
  if (canvasPointerDown.value) {
    finishCanvasStroke()
    return
  }
  if (mapType.value === 'txt' && props.showToolbox && canDraw.value && isDrawing.value) {
    onTxtMouseUp()
  }
}

const handleCanvasPointerDown = (e) => {
  if (!e.isPrimary) return
  if (e.pointerType === 'mouse' && e.button !== 0) return
  if (!canDraw.value || !props.showToolbox || mapType.value !== 'image') return
  canvasPointerDown.value = true
  isDrawing.value = true
  const coords = getCanvasCoords(e)
  const r = eraserRadius.value
  if (coords && canvasCtx.value) {
    drawStart.value = coords
    if (tool.value === 'brush') {
      canvasCtx.value.beginPath()
      canvasCtx.value.arc(coords.x, coords.y, 4, 0, Math.PI * 2)
      canvasCtx.value.fillStyle = '#000'
      canvasCtx.value.fill()
    } else if (tool.value === 'eraser') {
      eraseCircleAt(canvasCtx.value, coords.x, coords.y, r)
    }
  }
  try {
    if (canvasRef.value?.setPointerCapture) {
      canvasRef.value.setPointerCapture(e.pointerId)
      canvasCapturedPointerId.value = e.pointerId
    }
  } catch {
    /* ignore */
  }
}

const handleCanvasPointerMove = (e) => {
  if (!canvasCtx.value) return
  if (tool.value === 'eraser') updateEraserPreview(e)
  else if (eraserPreview.value.visible) {
    eraserPreview.value = { visible: false, left: 0, top: 0, size: 0 }
  }

  if (!isDrawing.value) return
  const coords = getCanvasCoords(e)
  if (!coords) return
  const r = eraserRadius.value
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
    eraseCircleAt(canvasCtx.value, coords.x, coords.y, r)
  }
}

const handleCanvasPointerUp = (e) => {
  if (!e.isPrimary) return
  if (e.type === 'pointerup' && e.pointerType === 'mouse' && e.button !== 0) return
  finishCanvasStroke()
}

/** Hide eraser ring only; do not end stroke here — mouseleave often fires before mouseup and would swallow the log. */
const handleCanvasPointerLeave = () => {
  eraserPreview.value = { visible: false, left: 0, top: 0, size: 0 }
}

const undoLast = () => {
  if (mapType.value === 'image') {
    if (canvasUndoStack.value.length <= 1) return
    canvasUndoStack.value.pop()
    const prev = canvasUndoStack.value[canvasUndoStack.value.length - 1]
    if (canvasCtx.value && canvasRef.value && prev) {
      canvasCtx.value.putImageData(prev, 0, 0)
    }
  } else if (mapType.value === 'txt') {
    if (txtUndoStack.value.length <= 1) return
    txtUndoStack.value.pop()
    const prev = txtUndoStack.value[txtUndoStack.value.length - 1]
    filledCells.value = new Set(prev)
  } else {
    return
  }
  scheduleSyncMapProgress()
  logMapAction('map_tool_click', 'undo')
}

// Sync map_progress to backend for guide's Info Dashboard (follower only)
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
    txtUndoStack.value = [new Set()]
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

watch(tool, () => {
  eraserPreview.value = { visible: false, left: 0, top: 0, size: 0 }
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
  window.addEventListener('pointerup', onWindowStrokeEnd)
  window.addEventListener('mouseup', onWindowStrokeEnd)
  if (mapType.value === 'txt') loadTxtContent()
  else if (mapType.value === 'image' && props.showToolbox) setTimeout(initCanvas, 150)
})

onBeforeUnmount(() => {
  mounted.value = false
  window.removeEventListener('pointerup', onWindowStrokeEnd)
  window.removeEventListener('mouseup', onWindowStrokeEnd)
  releaseCanvasPointerCaptureIfAny()
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
          :class="{ 'drawing-canvas--eraser': tool === 'eraser' }"
          @pointerdown="handleCanvasPointerDown"
          @pointermove="handleCanvasPointerMove"
          @pointerup="handleCanvasPointerUp"
          @pointercancel="handleCanvasPointerUp"
          @pointerleave="handleCanvasPointerLeave"
        />
        <div
          v-if="mapType === 'image' && showToolbox && canDraw && tool === 'eraser' && eraserPreview.visible"
          class="eraser-cursor-ring"
          :style="{
            left: eraserPreview.left + 'px',
            top: eraserPreview.top + 'px',
            width: eraserPreview.size + 'px',
            height: eraserPreview.size + 'px'
          }"
          aria-hidden="true"
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
    <aside v-if="showToolbox && canDraw" class="map-toolbox-rail">
      <MapToolbox
        v-model:eraser-radius="eraserRadius"
        :eraser-min="ERASER_RADIUS_MIN"
        :eraser-max="ERASER_RADIUS_MAX"
        :can-undo="canUndo"
        :tool="tool"
        @update:tool="onToolChange"
        @reset="resetDrawing"
        @undo="undoLast"
      />
    </aside>
  </div>
</template>

<style scoped>
.map-with-drawing {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 12px;
  flex: 1;
  min-height: 0;
  min-width: 0;
}

.map-toolbox-rail {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: flex-end;
  align-self: stretch;
}

.map-container {
  position: relative;
  flex: 1;
  min-width: 0;
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
  z-index: 1;
  pointer-events: auto;
  touch-action: none;
  cursor: crosshair;
}

.drawing-canvas--eraser {
  cursor: none;
}

.eraser-cursor-ring {
  position: absolute;
  z-index: 2;
  pointer-events: none;
  border: 2px solid rgba(37, 99, 235, 0.85);
  border-radius: 50%;
  box-sizing: border-box;
  background: rgba(37, 99, 235, 0.08);
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
