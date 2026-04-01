<script setup>
import { ref } from 'vue'

const props = defineProps({
  tool: {
    type: String,
    default: 'brush'
  },
  eraserRadius: {
    type: Number,
    default: 16
  },
  eraserMin: {
    type: Number,
    default: 4
  },
  eraserMax: {
    type: Number,
    default: 72
  },
  canUndo: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:tool', 'update:eraserRadius', 'reset', 'undo'])

const setTool = (t) => {
  emit('update:tool', t)
}

const onReset = () => {
  emit('reset')
}

const onUndo = () => {
  emit('undo')
}

const onEraserRadiusInput = (e) => {
  emit('update:eraserRadius', Number(e.target.value))
}

const TOOLTIPS = {
  brush: 'Brush — draw on the map',
  eraser: 'Eraser — remove ink',
  undo: 'Undo last stroke',
  reset: 'Reset — clear all drawing'
}

const activeTooltip = ref(null)
const tooltipPosition = ref({ x: 0, y: 0 })

const showTooltip = (key, event) => {
  activeTooltip.value = key
  tooltipPosition.value = { x: event.clientX + 12, y: event.clientY + 12 }
}

const moveTooltip = (event) => {
  if (!activeTooltip.value) return
  tooltipPosition.value = { x: event.clientX + 12, y: event.clientY + 12 }
}

const hideTooltip = () => {
  activeTooltip.value = null
}
</script>

<template>
  <div class="map-toolbox">
    <button
      class="tool-btn"
      :class="{ active: tool === 'brush' }"
      type="button"
      aria-label="Brush"
      @mouseenter="showTooltip('brush', $event)"
      @mousemove="moveTooltip"
      @mouseleave="hideTooltip"
      @click="setTool('brush')"
    >
      <i class="fa-solid fa-paintbrush" aria-hidden="true"></i>
    </button>
    <div class="tool-with-flyout">
      <button
        class="tool-btn"
        :class="{ active: tool === 'eraser' }"
        type="button"
        aria-label="Eraser"
        @mouseenter="showTooltip('eraser', $event)"
        @mousemove="moveTooltip"
        @mouseleave="hideTooltip"
        @click="setTool('eraser')"
      >
        <i class="fa-solid fa-eraser" aria-hidden="true"></i>
      </button>
      <div
        v-if="tool === 'eraser'"
        class="eraser-size-flyout"
        title="Eraser size"
        @mousedown.stop
        @click.stop
      >
        <span class="eraser-size-label">Large</span>
        <input
          type="range"
          class="eraser-slider-vertical"
          :min="eraserMin"
          :max="eraserMax"
          :value="eraserRadius"
          @input="onEraserRadiusInput"
        />
        <span class="eraser-size-label">Small</span>
      </div>
    </div>
    <span
      class="tool-tooltip-anchor"
      @mouseenter="showTooltip('undo', $event)"
      @mousemove="moveTooltip"
      @mouseleave="hideTooltip"
    >
      <button
        class="tool-btn"
        type="button"
        :disabled="!canUndo"
        aria-label="Undo last stroke"
        @click="onUndo"
      >
        <i class="fa-solid fa-clock-rotate-left" aria-hidden="true"></i>
      </button>
    </span>
    <button
      class="tool-btn reset-btn"
      type="button"
      aria-label="Reset"
      @mouseenter="showTooltip('reset', $event)"
      @mousemove="moveTooltip"
      @mouseleave="hideTooltip"
      @click="onReset"
    >
      <i class="fa-solid fa-rotate-left" aria-hidden="true"></i>
    </button>
    <Teleport to="body">
      <div
        v-if="activeTooltip"
        class="map-toolbox-tooltip"
        :style="{ left: tooltipPosition.x + 'px', top: tooltipPosition.y + 'px' }"
      >
        {{ TOOLTIPS[activeTooltip] }}
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.map-toolbox {
  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
  align-items: center;
  gap: 6px;
  padding: 6px;
  width: fit-content;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}

.tool-with-flyout {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.eraser-size-flyout {
  position: absolute;
  right: calc(100% + 8px);
  left: auto;
  top: 50%;
  bottom: auto;
  transform: translateY(-50%);
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px 6px;
  min-height: 112px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.12);
}

.tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  transition: all 0.2s;
}

.tool-btn:hover:not(:disabled) {
  background: #f3f4f6;
  border-color: #9ca3af;
}

.tool-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.tool-btn.active {
  background: #2563eb;
  border-color: #2563eb;
  color: white;
}

.reset-btn {
  margin-top: 2px;
  padding-top: 8px;
  border-top: 1px solid #e5e7eb;
}

.eraser-size-label {
  font-size: 10px;
  color: #6b7280;
  line-height: 1;
  user-select: none;
}

/* Vertical range: writing-mode works in Chromium & Safari */
.eraser-slider-vertical {
  width: 28px;
  height: 88px;
  padding: 0;
  margin: 0;
  writing-mode: vertical-lr;
  direction: rtl;
  accent-color: #2563eb;
  cursor: pointer;
}

.tool-tooltip-anchor {
  display: flex;
  flex-direction: column;
  align-items: center;
}
</style>

<style>
/* Teleport to body — unscoped so tooltip is not clipped by overflow */
.map-toolbox-tooltip {
  position: fixed;
  z-index: 10050;
  background: #1f2937;
  color: #ffffff;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  max-width: 260px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  pointer-events: none;
  line-height: 1.4;
}
</style>
