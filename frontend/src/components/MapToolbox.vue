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

/** Inline SVGs so html2canvas (post-annotation screenshots) captures icons; FA webfonts often drop in foreignObject. */
const svgAttrs = {
  class: 'tool-icon',
  xmlns: 'http://www.w3.org/2000/svg',
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': 'true',
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
      <svg v-bind="svgAttrs">
        <path
          d="M9.53 16.12a3 3 0 0 0-5.78 1.13 2.25 2.25 0 0 1-2.4 2.24 4.5 4.5 0 0 0 8.4-2.25c0-.42-.14-.82-.39-1.12Zm.08-4.38L15 2.25A2.25 2.25 0 0 1 17.25 0h.01c.66 0 1.3.26 1.77.73l2.25 2.25a2.25 2.25 0 0 1 0 3.18l-5.38 5.38a2.25 2.25 0 0 1-3.18 0l-2.5-2.5Z"
        />
      </svg>
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
        <svg v-bind="svgAttrs">
          <path d="M7 21h10" />
          <path d="M7 3h2l10 10-5 5L4 8V6a2 2 0 0 1 2-2Z" />
          <path d="m13 13 6 6" />
        </svg>
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
        <svg v-bind="svgAttrs">
          <path d="M3 7v6h6" />
          <path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13" />
        </svg>
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
      <svg v-bind="svgAttrs">
        <polyline points="23 4 23 10 17 10" />
        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
      </svg>
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
  color: #374151;
  transition: all 0.2s;
}

.tool-icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  display: block;
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
