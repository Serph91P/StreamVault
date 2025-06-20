<template>
  <div v-if="showInstallPrompt" class="install-prompt">
    <div class="install-prompt__content">
      <div class="install-prompt__icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" fill="currentColor"/>
        </svg>
      </div>
      <div class="install-prompt__text">
        <h3>Install StreamVault</h3>
        <p>Install this app on your device for a better experience</p>
      </div>
      <div class="install-prompt__actions">
        <button @click="installApp" class="install-btn">Install</button>
        <button @click="dismissPrompt" class="dismiss-btn">Not now</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePWA } from '@/composables/usePWA'

const { isInstallable, isInstalled, installPWA } = usePWA()
const showInstallPrompt = ref(false)
const hasBeenDismissed = ref(false)

onMounted(() => {
  // Show install prompt if app is installable and hasn't been dismissed
  const dismissed = localStorage.getItem('pwa-install-dismissed')
  hasBeenDismissed.value = dismissed === 'true'
  
  // Show prompt after 5 seconds if installable and not dismissed
  setTimeout(() => {
    if (isInstallable.value && !isInstalled.value && !hasBeenDismissed.value) {
      showInstallPrompt.value = true
    }
  }, 5000)
})

const installApp = async () => {
  try {
    await installPWA()
    showInstallPrompt.value = false
  } catch (error) {
    console.error('Installation failed:', error)
  }
}

const dismissPrompt = () => {
  showInstallPrompt.value = false
  hasBeenDismissed.value = true
  localStorage.setItem('pwa-install-dismissed', 'true')
  
  // Show again after 7 days
  setTimeout(() => {
    localStorage.removeItem('pwa-install-dismissed')
  }, 7 * 24 * 60 * 60 * 1000)
}
</script>

<style scoped>
.install-prompt {
  position: fixed;
  bottom: 20px;
  left: 20px;
  right: 20px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  animation: slideUp 0.3s ease-out;
}

@media (min-width: 768px) {
  .install-prompt {
    left: auto;
    max-width: 400px;
  }
}

.install-prompt__content {
  display: flex;
  align-items: center;
  padding: 16px;
  gap: 12px;
}

.install-prompt__icon {
  color: #6f42c1;
  flex-shrink: 0;
}

.install-prompt__text {
  flex: 1;
}

.install-prompt__text h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
}

.install-prompt__text p {
  margin: 0;
  font-size: 14px;
  color: #666;
}

.install-prompt__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.install-btn, .dismiss-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.install-btn {
  background: #6f42c1;
  color: white;
}

.install-btn:hover {
  background: #5a359a;
}

.dismiss-btn {
  background: #f8f9fa;
  color: #666;
}

.dismiss-btn:hover {
  background: #e9ecef;
}

@keyframes slideUp {
  from {
    transform: translateY(100%);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

/* Dark mode styles */
@media (prefers-color-scheme: dark) {
  .install-prompt {
    background: #2a2c33;
    color: white;
  }
  
  .install-prompt__text h3 {
    color: white;
  }
  
  .install-prompt__text p {
    color: #a8b2c7;
  }
  
  .dismiss-btn {
    background: #3a3d45;
    color: #a8b2c7;
  }
  
  .dismiss-btn:hover {
    background: #4a4d55;
  }
}
</style>
