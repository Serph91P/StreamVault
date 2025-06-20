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
import { ref, onMounted } from 'vue'
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
  
  // Auto-refresh every 5 seconds
  setInterval(refreshData, 5000)
})
</script>

<style scoped>
.pwa-tester {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: system-ui, -apple-system, sans-serif;
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.header h1 {
  margin: 0 0 10px 0;
  color: #333;
}

.header p {
  margin: 0;
  color: #666;
}

.info-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.info-card {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
}

.info-card h3 {
  margin: 0 0 15px 0;
  color: #495057;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 14px;
}

.info-item span:first-child {
  font-weight: 500;
  color: #495057;
}

.info-item code {
  background: #e9ecef;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.success {
  color: #28a745;
  font-weight: 500;
}

.error {
  color: #dc3545;
  font-weight: 500;
}

.actions {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-bottom: 30px;
  flex-wrap: wrap;
}

.actions button {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.install-btn {
  background: #007bff;
  color: white;
}

.install-btn:hover:not(:disabled) {
  background: #0056b3;
}

.install-btn:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.refresh-btn {
  background: #28a745;
  color: white;
}

.refresh-btn:hover {
  background: #1e7e34;
}

.debug-btn {
  background: #ffc107;
  color: #212529;
}

.debug-btn:hover {
  background: #e0a800;
}

.tips {
  background: #fff3cd;
  border: 1px solid #ffeaa7;
  border-radius: 8px;
  padding: 20px;
}

.tips h3 {
  margin: 0 0 15px 0;
  color: #856404;
}

.tips ul {
  margin: 0;
  padding-left: 20px;
}

.tips li {
  margin-bottom: 5px;
  color: #856404;
}

@media (max-width: 768px) {
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
