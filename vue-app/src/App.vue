<script setup>
import { ref, onMounted } from 'vue'
import ApiKeyModal from './components/ApiKeyModal.vue'

const showApiKeyModal = ref(false)

const checkApiKeys = async () => {
  try {
    const response = await fetch('/api/check-api-keys')
    const data = await response.json()
    showApiKeyModal.value = !data.keys_present
  } catch (error) {
    console.error('Error checking API keys:', error)
    // Assume keys are missing if the check fails
    showApiKeyModal.value = true
  }
}

onMounted(() => {
  checkApiKeys()
})
</script>

<template>
  <div id="app">
    <router-view />
    <ApiKeyModal :visible="showApiKeyModal" @recheck="checkApiKeys" />
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
}

#app {
  width: 100vw;
  height: 100vh;
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
</style>
