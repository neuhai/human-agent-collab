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

/** Inline SVG paths so html2canvas captures icons; avoid FA webfont glyph loss in foreignObject mode. */
const faIconAttrs = {
  class: 'tool-icon',
  xmlns: 'http://www.w3.org/2000/svg',
  viewBox: '0 0 640 640',
  fill: 'currentColor',
  'aria-hidden': 'true',
}

const FA_PATHS = {
  brush:
    'M512.5 74.3L291.1 222C262 241.4 243.5 272.9 240.5 307.3C302.8 320.1 351.9 369.2 364.8 431.6C399.3 428.6 430.7 410.1 450.1 381L597.7 159.5C604.4 149.4 608 137.6 608 125.4C608 91.5 580.5 64 546.6 64C534.5 64 522.6 67.6 512.5 74.3zM320 464C320 402.1 269.9 352 208 352C146.1 352 96 402.1 96 464C96 467.9 96.2 471.8 96.6 475.6C98.4 493.1 86.4 512 68.8 512L64 512C46.3 512 32 526.3 32 544C32 561.7 46.3 576 64 576L208 576C269.9 576 320 525.9 320 464z',
  eraser:
    'M210.5 480L333.5 480L398.8 414.7L225.3 241.2L98.6 367.9L210.6 479.9zM256 544L210.5 544C193.5 544 177.2 537.3 165.2 525.3L49 409C38.1 398.1 32 383.4 32 368C32 352.6 38.1 337.9 49 327L295 81C305.9 70.1 320.6 64 336 64C351.4 64 366.1 70.1 377 81L559 263C569.9 273.9 576 288.6 576 304C576 319.4 569.9 334.1 559 345L424 480L544 480C561.7 480 576 494.3 576 512C576 529.7 561.7 544 544 544L256 544z',
  undo:
    'M320 128C426 128 512 214 512 320C512 426 426 512 320 512C254.8 512 197.1 479.5 162.4 429.7C152.3 415.2 132.3 411.7 117.8 421.8C103.3 431.9 99.8 451.9 109.9 466.4C156.1 532.6 233 576 320 576C461.4 576 576 461.4 576 320C576 178.6 461.4 64 320 64C234.3 64 158.5 106.1 112 170.7L112 144C112 126.3 97.7 112 80 112C62.3 112 48 126.3 48 144L48 256C48 273.7 62.3 288 80 288L104.6 288C105.1 288 105.6 288 106.1 288L192.1 288C209.8 288 224.1 273.7 224.1 256C224.1 238.3 209.8 224 192.1 224L153.8 224C186.9 166.6 249 128 320 128zM344 216C344 202.7 333.3 192 320 192C306.7 192 296 202.7 296 216L296 320C296 326.4 298.5 332.5 303 337L375 409C384.4 418.4 399.6 418.4 408.9 409C418.2 399.6 418.3 384.4 408.9 375.1L343.9 310.1L343.9 216z',
  reset:
    'M129.9 292.5C143.2 199.5 223.3 128 320 128C373 128 421 149.5 455.8 184.2C456 184.4 456.2 184.6 456.4 184.8L464 192L416.1 192C398.4 192 384.1 206.3 384.1 224C384.1 241.7 398.4 256 416.1 256L544.1 256C561.8 256 576.1 241.7 576.1 224L576.1 96C576.1 78.3 561.8 64 544.1 64C526.4 64 512.1 78.3 512.1 96L512.1 149.4L500.8 138.7C454.5 92.6 390.5 64 320 64C191 64 84.3 159.4 66.6 283.5C64.1 301 76.2 317.2 93.7 319.7C111.2 322.2 127.4 310 129.9 292.6zM573.4 356.5C575.9 339 563.7 322.8 546.3 320.3C528.9 317.8 512.6 330 510.1 347.4C496.8 440.4 416.7 511.9 320 511.9C267 511.9 219 490.4 184.2 455.7C184 455.5 183.8 455.3 183.6 455.1L176 447.9L223.9 447.9C241.6 447.9 255.9 433.6 255.9 415.9C255.9 398.2 241.6 383.9 223.9 383.9L96 384C87.5 384 79.3 387.4 73.3 393.5C67.3 399.6 63.9 407.7 64 416.3L65 543.3C65.1 561 79.6 575.2 97.3 575C115 574.8 129.2 560.4 129 542.7L128.6 491.2L139.3 501.3C185.6 547.4 249.5 576 320 576C449 576 555.7 480.6 573.4 356.5z',
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
      <svg v-bind="faIconAttrs">
        <path :d="FA_PATHS.brush" />
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
        <svg v-bind="faIconAttrs">
          <path :d="FA_PATHS.eraser" />
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
        <svg v-bind="faIconAttrs">
          <path :d="FA_PATHS.undo" />
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
      <svg v-bind="faIconAttrs">
        <path :d="FA_PATHS.reset" />
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
  width: 18px;
  height: 18px;
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
