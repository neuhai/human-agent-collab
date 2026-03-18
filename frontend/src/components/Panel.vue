<script setup>
import { ref } from 'vue'

const props = defineProps({
  header: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  },
  fitContent: {
    type: Boolean,
    default: false
  },
  flex: {
    type: String,
    default: '1'
  }
})

const showTooltip = ref(false)
const tooltipPosition = ref({ x: 0, y: 0 })

const onMouseEnter = (event) => {
  if (props.description) {
    showTooltip.value = true
    tooltipPosition.value = { x: event.clientX + 10, y: event.clientY + 10 }
  }
}

const onMouseMove = (event) => {
  if (showTooltip.value) {
    tooltipPosition.value = { x: event.clientX + 10, y: event.clientY + 10 }
  }
}

const onMouseLeave = () => {
  showTooltip.value = false
}
</script>

<template>
  <div class="panel-container" :class="{ 'fit-content': fitContent }" :style="{ flex: flex }">
    <h3 class="panel-header" @mouseenter="onMouseEnter" @mousemove="onMouseMove" @mouseleave="onMouseLeave">
      {{ header }}
      <span v-if="description" class="tooltip-icon">ⓘ</span>
    </h3>
    <div class="panel-body" :class="{ 'fit-content': fitContent }">
      <slot></slot>
    </div>
    <div v-if="showTooltip && description" class="panel-tooltip" :style="{ left: tooltipPosition.x + 'px', top: tooltipPosition.y + 'px' }">
      {{ description }}
    </div>
  </div>
</template>

<style scoped>
.panel-container {
  background: #ffffff;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  margin-bottom: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: relative;
}

.panel-container.fit-content {
  height: fit-content;
}

.panel-body.fit-content {
  flex: 0 0 auto;
}

.panel-header {
  background: #e9ecef;
  padding: 8px 12px;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #495057;
  border-bottom: 1px solid #dee2e6;
  border-radius: 6px 6px 0 0;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: help;
}

.panel-body {
  padding: 12px;
  flex: 1;
  overflow: auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tooltip-icon {
  font-size: 12px;
  color: #6b7280;
}

.panel-tooltip {
  position: fixed;
  background: #374151;
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  max-width: 250px;
  z-index: 1000;
  pointer-events: none;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  line-height: 1.4;
}
</style>

