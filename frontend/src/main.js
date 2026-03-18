import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import { initWebSocket } from './services/websocket.js'

// Initialize WebSocket connection when app starts
initWebSocket()

createApp(App).use(router).mount('#app')
