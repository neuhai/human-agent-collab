<script setup>
import { computed, ref } from 'vue'
import MapWithDrawing from './MapWithDrawing.vue'
import { normalizeMapIdentity } from '../utils/mapIdentity.js'

const props = defineProps({
  bindings: {
    type: Array,
    default: () => []
  }
})

const mapBinding = computed(() =>
  props.bindings.find(b =>
    b.path === 'Participant.map' || b.control === 'map'
  )
)

const mapToolboxBinding = computed(() =>
  props.bindings.find(b => b.control === 'map_toolbox')
)

const map = computed(() => mapBinding.value?.value ?? null)

const showToolbox = computed(() => !!mapToolboxBinding.value)

/** Match MapWithDrawing: stable across filename vs file_path / late id (see mapIdentity.js). */
const mapStableKey = computed(() => {
  const id = normalizeMapIdentity(map.value)
  return id != null ? id : 'no-map'
})

// Tooltip state
const showTooltip = ref(false)
const tooltipPosition = ref({ x: 0, y: 0 })

const getDescription = () => {
  const path = mapBinding.value?.path || ''
  
  // Role-specific descriptions for the map
  const role = mapBinding.value?.value?.role || mapBinding.value?.role || ''
  const roleLower = role.toLowerCase()
  
  if (roleLower === 'follower') {
    return 'Your blank map where you draw the route based on the guide\'s description.'
  }
  if (roleLower === 'guide') {
    return 'The reference map showing the correct route. Describe this route to the follower.'
  }
  
  // Fallback to binding description
  if (mapBinding.value?.description) {
    return mapBinding.value.description
  }
  
  return 'The map showing landmarks and route.'
}

const description = computed(() => getDescription())

const onMouseEnter = (event) => {
  if (description.value) {
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
  <div class="map-task-panel">
    <div class="map-task-content">
      <span 
        v-if="mapBinding?.label" 
        class="map-task-label"
        @mouseenter="onMouseEnter"
        @mousemove="onMouseMove"
        @mouseleave="onMouseLeave"
      >
        {{ mapBinding.label }}:<span v-if="description" class="tooltip-icon">ⓘ</span>
      </span>
      <MapWithDrawing :key="mapStableKey" :map="map" :show-toolbox="showToolbox" />
    </div>
    <!-- Tooltip popup -->
    <div
      v-if="showTooltip && description"
      class="map-tooltip-popup"
      :style="{ left: tooltipPosition.x + 'px', top: tooltipPosition.y + 'px' }"
    >
      {{ description }}
    </div>
  </div>
</template>

<style scoped>
.map-task-panel {
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.map-task-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.map-task-label {
  font-weight: 500;
  color: #374151;
  font-size: 13px;
  cursor: help;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.tooltip-icon {
  font-size: 12px;
  color: #6b7280;
  margin-left: 2px;
}

.map-tooltip-popup {
  position: fixed;
  z-index: 9999;
  background: #1f2937;
  color: #ffffff;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  max-width: 280px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  pointer-events: none;
  line-height: 1.4;
}
</style>
