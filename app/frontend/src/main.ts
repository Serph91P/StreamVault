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
