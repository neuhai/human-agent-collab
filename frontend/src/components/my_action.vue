<script setup>
import { computed } from 'vue'
import Panel from '../components/Panel.vue'
import BaseComponent from '../components/BaseComponent.vue'

const props = defineProps({
  config: {
    type: Object,
    default: () => ({
      id: '',
      label: 'My Action',
      description: '',
      visible_if: 'true',
      bindings: []
    })
  }
})

const emit = defineEmits(['submit'])

const isVisible = computed(() => {
  return props.config.visible_if === 'true' || props.config.visible_if === true
})

const handleSubmit = (data) => {
  emit('submit', data)
}
</script>

<template>
  <Panel v-if="isVisible" :header="config.label || 'My Action'" :description="config.description || ''" :fitContent="true" flex="none">
    <BaseComponent 
      v-for="(binding, index) in config.bindings" 
      :key="index"
      :title="binding.label"
      :binding="binding"
      @submit="handleSubmit"
    />
  </Panel>
</template>

<style scoped>
</style>