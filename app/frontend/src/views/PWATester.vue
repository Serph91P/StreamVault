<template>
  <div class="pwa-tester">
    <div class="header">
      <h1>📱 PWA Mobile Tester</h1>
      <p>Debug-Informationen für mobile PWA-Installation</p>
    </div>

    <div class="info-cards">
      <div class="info-card">
        <h3>🔧 Browser Info</h3>
        <div class="info-item">
          <span>User Agent:</span>
          <code>{{ browserInfo.userAgent }}</code>
        </div>
        <div class="info-item">
          <span>Platform:</span>
          <code>{{ browserInfo.platform }}</code>
        </div>
        <div class="info-item">
          <span>Is Mobile:</span>
          <span :class="browserInfo.isMobile ? 'success' : 'error'">
            {{ browserInfo.isMobile ? '✅' : '❌' }}
          </span>
        </div>
      </div>

      <div class="info-card">
        <h3>🚀 PWA Status</h3>
        <div class="info-item">
          <span>Is Installable:</span>
          <span :class="pwaStatus.isInstallable ? 'success' : 'error'">
            {{ pwaStatus.isInstallable ? '✅ Installierbar' : '❌ Nicht installierbar' }}
          </span>
        </div>
        <div class="info-item">
          <span>Is Installed:</span>
          <span :class="pwaStatus.isInstalled ? 'success' : 'error'">
            {{ pwaStatus.isInstalled ? '✅ Installiert' : '❌ Nicht installiert' }}
          </span>
        </div>
        <div class="info-item">
          <span>Display Mode:</span>
          <code>{{ pwaStatus.displayMode }}</code>
        </div>
      </div>

      <div class="info-card">
        <h3>⚙️ Service Worker</h3>
        <div class="info-item">
          <span>Supported:</span>
          <span :class="serviceWorker.supported ? 'success' : 'error'">
            {{ serviceWorker.supported ? '✅' : '❌' }}
          </span>
        </div>
        <div class="info-item">
          <span>Registered:</span>
          <span :class="serviceWorker.registered ? 'success' : 'error'">
            {{ serviceWorker.registered ? '✅' : '❌' }}
          </span>
        </div>
        <div class="info-item">
          <span>Controller:</span>
          <span :class="serviceWorker.hasController ? 'success' : 'error'">
            {{ serviceWorker.hasController ? '✅' : '❌' }}
          </span>
        </div>
      </div>

      <div class="info-card">
        <h3>📄 Manifest</h3>
        <div class="info-item">
          <span>Loaded:</span>
          <span :class="manifest.loaded ? 'success' : 'error'">
            {{ manifest.loaded ? '✅' : '❌' }}
          </span>
        </div>
        <div class="info-item" v-if="manifest.data">
          <span>Name:</span>
          <code>{{ manifest.data.name }}</code>
        </div>
        <div class="info-item" v-if="manifest.data">
          <span>Icons:</span>
          <code>{{ manifest.data.icons?.length || 0 }} gefunden</code>
        </div>
      </div>
    </div>

    <div class="actions">
      <button @click="testInstall" :disabled="!pwaStatus.isInstallable" class="install-btn">
        🚀 Installation testen
      </button>
      <button @click="refreshData" class="refresh-btn">
        🔄 Daten aktualisieren
      </button>
      <button @click="showDebugConsole" class="debug-btn">
        🐛 Debug Console
      </button>
    </div>

    <div class="tips" v-if="browserInfo.isMobile && !pwaStatus.isInstallable">
      <h3>💡 Tipps für mobile Installation:</h3>
      <ul>
        <li>Stellen Sie sicher, dass Sie HTTPS verwenden</li>
        <li>Laden Sie die Seite komplett neu (Hard Refresh)</li>
        <li>Warten Sie 30 Sekunden auf der Seite</li>
        <li>Interagieren Sie mit der Seite (scrollen, klicken)</li>
        <li>Chrome: Menü → "Zum Startbildschirm hinzufügen"</li>
        <li>Safari: Teilen → "Zum Home-Bildschirm"</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { usePWA } from '@/composables/usePWA'

const { isInstallable, isInstalled, installPWA } = usePWA()

const browserInfo = ref({
  userAgent: '',
  platform: '',
  isMobile: false
})

const pwaStatus = ref({
  isInstallable: false,
  isInstalled: false,
  displayMode: 'browser'
})

const serviceWorker = ref({
  supported: false,
  registered: false,
  hasController: false
})

const manifest = ref({
  loaded: false,
  data: null as any
})

const detectDisplayMode = () => {
  const modes = ['standalone', 'minimal-ui', 'fullscreen', 'browser']
  for (const mode of modes) {
    if (window.matchMedia(`(display-mode: ${mode})`).matches) {
      return mode
    }
  }
  return 'browser'
}

const loadManifest = async () => {
  try {
    const response = await fetch('/manifest.json')
    const data = await response.json()
    manifest.value.data = data
    manifest.value.loaded = true
  } catch (error) {
    console.error('Failed to load manifest:', error)
    manifest.value.loaded = false
  }
}

const checkServiceWorker = async () => {
  serviceWorker.value.supported = 'serviceWorker' in navigator
  
  if (serviceWorker.value.supported) {
    try {
      const registrations = await navigator.serviceWorker.getRegistrations()
      serviceWorker.value.registered = registrations.length > 0
      serviceWorker.value.hasController = !!navigator.serviceWorker.controller
    } catch (error) {
      console.error('Service Worker check failed:', error)
    }
  }
}

const refreshData = () => {
  // Browser Info
  browserInfo.value.userAgent = navigator.userAgent
  browserInfo.value.platform = navigator.platform
  browserInfo.value.isMobile = /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
  
  // PWA Status
  pwaStatus.value.isInstallable = isInstallable.value
  pwaStatus.value.isInstalled = isInstalled.value
  pwaStatus.value.displayMode = detectDisplayMode()
  
  // Service Worker
  checkServiceWorker()
  
  // Manifest
  loadManifest()
}

const testInstall = async () => {
  try {
    await installPWA()
    alert('Installation erfolgreich!')
  } catch (error) {
    alert('Installation fehlgeschlagen: ' + error)
  }
}

const showDebugConsole = () => {
  import('@/utils/pwaDebug').then(module => {
    if (module.debugPWA) {
      module.debugPWA()
    }
  })
}

onMounted(() => {
  refreshData()
  
  // Auto-refresh every 5 seconds - PERFORMANCE FIX: Clear interval on unmount
  // Real-time updates via WebSocket - no polling needed
  
  // WebSocket integration for real-time updates
  const { messages } = useWebSocket()
  
  watch(messages, (newMessages) => {
    if (newMessages.length === 0) return
    
    const latestMessage = newMessages[newMessages.length - 1]
    
    // Refresh data when relevant WebSocket events occur
    if (latestMessage.type === 'active_recordings_update' ||
        latestMessage.type === 'recording_started' ||
        latestMessage.type === 'recording_stopped' ||
        latestMessage.type === 'queue_stats_update') {
      refreshData()
    }
  })
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.pwa-tester {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: system-ui, -apple-system, sans-serif;
}

.header {
  text-align: center;
  margin-bottom: var(--spacing-8);  // 32px
}

.header h1 {
  margin: 0 0 var(--spacing-3) 0;
  color: var(--text-primary);
}

.header p {
  margin: 0;
  color: var(--text-secondary);
}

.info-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--spacing-5);  // 20px
  margin-bottom: var(--spacing-8);  // 32px
}

.info-card {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);  // 12px
  padding: var(--spacing-5);  // 20px
  box-shadow: var(--shadow-sm);
  transition: var(--transition-all);

  &:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
  }
}

.info-card h3 {
  margin: 0 0 var(--spacing-4) 0;
  color: var(--text-primary);
  font-weight: 600;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-3);  // 12px
  font-size: v.$text-sm;
}

.info-item span:first-child {
  font-weight: 500;
  color: var(--text-secondary);
}

.info-item code {
  background: var(--background-darker);
  color: var(--text-primary);
  padding: var(--spacing-1) var(--spacing-2);  // 4px 8px
  border-radius: var(--radius-sm);  // 4px
  font-size: v.$text-xs;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border: 1px solid var(--border-color);
}

.success {
  color: var(--success-color);
  font-weight: 500;
}

.error {
  color: var(--danger-color);
  font-weight: 500;
}

.actions {
  display: flex;
  gap: var(--spacing-3);  // 12px
  justify-content: center;
  margin-bottom: var(--spacing-8);  // 32px
  flex-wrap: wrap;
}

.actions button {
  padding: var(--spacing-3) var(--spacing-5);  // 12px 20px
  border: none;
  border-radius: var(--radius);  // 8px
  font-weight: 500;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  min-height: 44px;  // Touch target

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }

  &:active:not(:disabled) {
    transform: translateY(0);
  }
}

.install-btn {
  background: var(--info-color);
  color: white;

  &:hover:not(:disabled) {
    background: #2563eb;  // info-600
  }

  &:disabled {
    background: var(--text-secondary);
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.refresh-btn {
  background: var(--success-color);
  color: white;

  &:hover {
    background: #059669;  // success-600
  }
}

.debug-btn {
  background: var(--warning-color);
  color: #212529;

  &:hover {
    background: #d97706;  // warning-600
    color: white;
  }
}

.tips {
  background: rgba(245, 158, 11, 0.1);  // warning-500 mit 10% opacity
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: var(--radius-lg);  // 12px
  padding: var(--spacing-5);  // 20px
}

.tips h3 {
  margin: 0 0 var(--spacing-4) 0;
  color: var(--warning-color);
  font-weight: 600;
}

.tips ul {
  margin: 0;
  padding-left: var(--spacing-5);  // 20px
}

.tips li {
  margin-bottom: var(--spacing-2);  // 8px
  color: var(--text-primary);
}

@include m.respond-below('md') {  // < 768px
  .pwa-tester {
    padding: 10px;
  }
  
  .info-cards {
    grid-template-columns: 1fr;
  }
  
  .actions {
    flex-direction: column;
  }
  
  .actions button {
    width: 100%;
  }
}
</style>
