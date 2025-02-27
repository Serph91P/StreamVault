// import './assets/main.css'
import './styles/main.scss'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

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
