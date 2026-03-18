<script setup>
import { computed } from 'vue'
import Panel from '../components/Panel.vue'
import BaseComponent from '../components/BaseComponent.vue'

const props = defineProps({
  config: {
    type: Object,
    default: () => ({
      id: '',
      label: 'My Status',
      description: '',
      visible_if: 'true',
      bindings: []
    })
  }
})

const isVisible = computed(() => {
  return props.config.visible_if === 'true' || props.config.visible_if === true
})
</script>

<template>
  <Panel v-if="isVisible" :header="config.label || 'My Status'" :description="config.description || ''" :fitContent="true" flex="none">
    <BaseComponent 
      v-for="(binding, index) in config.bindings" 
      :key="index"
      :title="binding.label"
      :binding="binding"
    />
  </Panel>
</template>

<style scoped>
</style>