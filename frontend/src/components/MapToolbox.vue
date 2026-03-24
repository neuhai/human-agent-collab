<script setup>
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
</script>

<template>
  <div class="map-toolbox">
    <button
      class="tool-btn"
      :class="{ active: tool === 'brush' }"
      @click="setTool('brush')"
      title="Brush"
    >
      <i class="fa-solid fa-paintbrush"></i>
      <span>Brush</span>
    </button>
    <div class="tool-with-flyout">
      <button
        class="tool-btn"
        :class="{ active: tool === 'eraser' }"
        @click="setTool('eraser')"
        title="Eraser"
      >
        <i class="fa-solid fa-eraser"></i>
        <span>Eraser</span>
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
    <button
      class="tool-btn"
      :disabled="!canUndo"
      title="Undo last stroke"
      @click="onUndo"
    >
      <i class="fa-solid fa-clock-rotate-left"></i>
      <span>Undo</span>
    </button>
    <button class="tool-btn reset-btn" @click="onReset" title="Reset">
      <i class="fa-solid fa-rotate-left"></i>
      <span>Reset</span>
    </button>
  </div>
</template>

<style scoped>
.map-toolbox {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}

.tool-with-flyout {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.eraser-size-flyout {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
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
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 13px;
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
  margin-left: auto;
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
</style>
