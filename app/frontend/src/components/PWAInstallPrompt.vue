<template>
  <div v-if="showInstallPrompt" class="install-prompt">
    <div class="install-prompt__content">
      <div class="install-prompt__icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" fill="currentColor"/>
        </svg>
      </div>
      <div class="install-prompt__text">
        <h3>{{ installText }}</h3>
        <p>{{ installDescription }}</p>
      </div>
      <div class="install-prompt__actions">
        <button @click="installApp" class="install-btn">Install</button>
        <button @click="dismissPrompt" class="dismiss-btn">Not now</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { usePWA } from '@/composables/usePWA'

const { isInstallable, isInstalled, installPWA, getPlatformInfo } = usePWA()
const showInstallPrompt = ref(false)
const hasBeenDismissed = ref(false)
const platformInfo = ref(null)

// Computed properties for platform-specific content
const installText = computed(() => {
  if (!platformInfo.value) return 'Install StreamVault'
  
  const { platform, browser } = platformInfo.value
  
  if (platform === 'iOS' && browser === 'Safari') {
    return 'Add StreamVault to Home Screen'
  }
  if (platform === 'Android') {
    return 'Install StreamVault App'
  }
  if (platform === 'Windows') {
    return 'Install StreamVault'
  }
  if (platform === 'macOS') {
    return 'Add StreamVault to Dock'
  }
  if (platform === 'Linux') {
    return 'Install StreamVault'
  }
  
  return 'Install StreamVault'
})

const installDescription = computed(() => {
  if (!platformInfo.value) return 'Install this app on your device for a better experience'
  
  const { platform, browser } = platformInfo.value
  
  if (platform === 'iOS' && browser === 'Safari') {
    return 'Tap the Share button, then "Add to Home Screen" for quick access'
  }
  if (platform === 'Android') {
    return 'Install for faster loading and offline access'
  }
  if (platform === 'Windows') {
    return 'Install to your Start Menu and taskbar'
  }
  if (platform === 'macOS') {
    return 'Add to your Dock for quick access'
  }
  if (platform === 'Linux') {
    return 'Install for better performance and offline use'
  }
  
  return 'Install this app on your device for a better experience'
})

onMounted(() => {
  // Show install prompt if app is installable and hasn't been dismissed
  const dismissed = localStorage.getItem('pwa-install-dismissed')
  hasBeenDismissed.value = dismissed === 'true'
  
  // Show prompt after 3 seconds if installable and not dismissed
  setTimeout(() => {
    if (isInstallable.value && !isInstalled.value && !hasBeenDismissed.value) {
      showInstallPrompt.value = true
    }
  }, 3000)
  
  // Also check periodically for installability changes (mobile browsers)
  setInterval(() => {
    if (isInstallable.value && !isInstalled.value && !hasBeenDismissed.value && !showInstallPrompt.value) {
      showInstallPrompt.value = true
    }
  }, 10000)
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

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.install-prompt {
  position: fixed;
  bottom: var(--spacing-6);
  left: var(--spacing-6);
  right: var(--spacing-6);
  background: var(--background-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
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
  padding: var(--spacing-4);
  gap: var(--spacing-3);
}

.install-prompt__icon {
  color: var(--accent-color);
  flex-shrink: 0;
}

.install-prompt__text {
  flex: 1;
}

.install-prompt__text h3 {
  margin: 0 0 var(--spacing-1) 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.install-prompt__text p {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
}

.install-prompt__actions {
  display: flex;
  gap: var(--spacing-2);
  flex-shrink: 0;
}

.install-btn, .dismiss-btn {
  padding: var(--spacing-2) var(--spacing-4);
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.install-btn {
  background: var(--accent-color);
  color: white;
}

.install-btn:hover {
  background: var(--accent-color-hover);
}

.dismiss-btn {
  background: var(--background-darker);
  color: var(--text-secondary);
}

.dismiss-btn:hover {
  background: var(--background-dark);
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

/* Mobile specific styles */
@include m.respond-below('md') {  // < 768px
  .install-prompt {
    margin: var(--spacing-2);
    border-radius: var(--radius-lg);
  }
  
  .install-prompt__content {
    padding: var(--spacing-4);
    flex-direction: column;
    text-align: center;
  }
  
  .install-prompt__icon {
    margin: 0 0 var(--spacing-3) 0;
  }
  
  .install-prompt__actions {
    margin-top: var(--spacing-4);
    justify-content: center;
    flex-direction: column;
    width: 100%;
  }
  
  .install-btn, .dismiss-btn {
    width: 100%;
    padding: var(--spacing-3) var(--spacing-4);
    font-size: 16px;
  }
}
</style>
