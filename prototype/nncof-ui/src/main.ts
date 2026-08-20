import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import { initializeTheme } from './composables/useTheme'

initializeTheme()

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.mount('#app')
