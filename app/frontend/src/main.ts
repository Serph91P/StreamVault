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

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js', {
    scope: '/'
  }).then(registration => {
    console.log('ServiceWorker registration successful');
  }).catch(err => {
    console.log('ServiceWorker registration failed: ', err);
  });
}

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
