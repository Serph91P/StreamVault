// import './assets/main.css'
import './styles/main.scss'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

// PWA Debug helper (nur in development) 
import('./utils/pwaDebug')

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')

// Service Worker wird automatisch von VitePWA registriert
import { registerSW } from 'virtual:pwa-register'

const updateSW = registerSW({
  onNeedRefresh() {
    // Zeige eine Benachrichtigung für Updates
    console.log('PWA needs refresh')
  },
  onOfflineReady() {
    console.log('PWA is ready for offline use')
  },
  onRegistered(registration) {
    console.log('Service Worker registered successfully', registration)
  },
  onRegisterError(error) {
    console.error('Service Worker registration failed:', error)
  },
})

// PWA Install Event
let deferredPrompt: any = null

window.addEventListener('beforeinstallprompt', (e) => {
  // Prevent the mini-infobar from appearing on mobile
  e.preventDefault()
  // Stash the event so it can be triggered later.
  deferredPrompt = e
  console.log('PWA install prompt available')
  
  // Make the install prompt available
  window.dispatchEvent(new CustomEvent('pwa-installable', { detail: e }))
})

window.addEventListener('appinstalled', () => {
  console.log('PWA was installed')
  deferredPrompt = null
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
