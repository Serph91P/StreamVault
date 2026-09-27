// import './assets/main.css'
import './styles/main.scss'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

// Initialize theme before app mounts
import { useTheme } from './composables/useTheme'
const { initializeTheme } = useTheme()
initializeTheme()

if (import.meta.env.DEV) {
  import('./utils/pwaDebug')
}

// Import directives
import rippleDirective from './directives/ripple'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// Register directives
app.directive('ripple', rippleDirective)

app.mount('#app')

// VitePWA owns SW registration via virtual:pwa-register
import { registerSW } from 'virtual:pwa-register'

const updateSW = registerSW({
  onNeedRefresh() {
    window.dispatchEvent(new CustomEvent('pwa-needs-refresh', {
      detail: { update: () => updateSW(true) }
    }))
  },
  onRegisterError(error) {
    console.error('Service Worker registration failed:', error)
  },
})


// Lightweight session keepalive: ping backend periodically to refresh cookie session
// Runs only when page is visible to reduce battery impact
const KEEPALIVE_INTERVAL_MS = 5 * 60 * 1000 // 5 minutes

async function keepaliveOnce() {
  try {
    await fetch('/auth/keepalive', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    })
  } catch (e) {
    // silent
  }
}

let keepaliveTimer: number | null = null
function startKeepalive() {
  if (keepaliveTimer !== null) return
  keepaliveTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') {
      keepaliveOnce()
    }
  }, KEEPALIVE_INTERVAL_MS)
}

function stopKeepalive() {
  if (keepaliveTimer !== null) {
    window.clearInterval(keepaliveTimer)
    keepaliveTimer = null
  }
}

// Start on load and toggle with visibility
startKeepalive()
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    keepaliveOnce()
  }
})

// Optional: stop on unload
window.addEventListener('beforeunload', () => {
  stopKeepalive()
})
