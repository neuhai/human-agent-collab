<script setup>
const props = defineProps({
  tool: {
    type: String,
    default: 'brush'
  }
})

const emit = defineEmits(['update:tool', 'reset'])

const setTool = (t) => {
  emit('update:tool', t)
}

const onReset = () => {
  emit('reset')
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
    <button
      class="tool-btn"
      :class="{ active: tool === 'eraser' }"
      @click="setTool('eraser')"
      title="Eraser"
    >
      <i class="fa-solid fa-eraser"></i>
      <span>Eraser</span>
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
  gap: 8px;
  padding: 8px;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
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

.tool-btn:hover {
  background: #f3f4f6;
  border-color: #9ca3af;
}

.tool-btn.active {
  background: #2563eb;
  border-color: #2563eb;
  color: white;
}

.reset-btn {
  margin-left: auto;
}
</style>
