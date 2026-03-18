<script setup>
import { computed } from 'vue'
import Panel from '../components/Panel.vue'
import BaseComponent from '../components/BaseComponent.vue'
import MapTaskPanel from '../components/MapTaskPanel.vue'

const props = defineProps({
  config: {
    type: Object,
    default: () => ({
      id: '',
      label: 'My Tasks',
      description: '',
      visible_if: 'true',
      bindings: []
    })
  }
})

const isVisible = computed(() => {
  return props.config.visible_if === 'true' || props.config.visible_if === true
})

const hasMapTask = computed(() => {
  const bindings = props.config.bindings || []
  return bindings.some(b => b.path === 'Participant.map' || b.control === 'map')
})
</script>

<template>
  <Panel v-if="isVisible" :header="config.label || 'My Tasks'" :description="config.description || ''" :fitContent="!hasMapTask" :flex="hasMapTask ? '1' : 'none'">
    <MapTaskPanel v-if="hasMapTask" :bindings="config.bindings || []" />
    <template v-else>
      <BaseComponent
        v-for="(binding, index) in config.bindings"
        :key="index"
        :title="binding.label"
        :binding="binding"
      />
    </template>
  </Panel>
</template>

<style scoped>
</style>