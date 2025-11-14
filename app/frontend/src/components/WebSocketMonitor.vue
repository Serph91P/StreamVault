<template>
  <div class="websocket-monitor">
    <div class="monitor-header">
      <h3>WebSocket Connection Monitor</h3>
      <button @click="refresh" :disabled="loading" class="refresh-btn">
        <span v-if="loading">Loading...</span>
        <span v-else>Refresh</span>
      </button>
    </div>
    
    <div v-if="error" class="error">
      Error loading connection data: {{ error }}
    </div>
    
    <div v-else-if="connectionData" class="connection-stats">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-number">{{ connectionData.total_connections }}</div>
          <div class="stat-label">Total Connections</div>
        </div>
        <div class="stat-card">
          <div class="stat-number">{{ connectionData.unique_clients }}</div>
          <div class="stat-label">Unique Clients</div>
        </div>
      </div>
      
      <div class="clients-section">
        <h4>Clients by IP</h4>
        <div v-for="client in connectionData.clients" :key="client.ip" class="client-card">
          <div class="client-header">
            <span class="client-ip">{{ client.ip }}</span>
            <span class="connection-count" :class="{ 'multiple': client.count > 1 }">
              {{ client.count }} connection{{ client.count === 1 ? '' : 's' }}
            </span>
          </div>
          <div class="connections-list">
            <div v-for="conn in client.connections" :key="conn.connection_id" class="connection-item">
              <span class="connection-id">ID: {{ conn.connection_id }}</span>
              <span class="connection-state" :class="conn.state?.toLowerCase() || 'unknown'">{{ conn.state || 'Unknown' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface Connection {
  connection_id: number
  real_ip: string
  client_identifier: string
  state: string
}

interface Client {
  ip: string
  connections: Connection[]
  count: number
}

interface ConnectionData {
  total_connections: number
  unique_clients: number
  clients: Client[]
  connections: Connection[]
}

const connectionData = ref<ConnectionData | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function refresh() {
  loading.value = true
  error.value = null
  
  try {
    const response = await fetch('/admin/websocket-connections')
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    connectionData.value = await response.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refresh()
})
</script>

<style scoped lang="scss">
.websocket-monitor {
  padding: var(--spacing-6);
  max-width: 800px;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-6);
}

.monitor-header h3 {
  margin: 0;
  color: var(--text-primary);
}

.refresh-btn {
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--success-color);
  color: var(--text-on-primary);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background-color 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: var(--success-color-dark);
}

.refresh-btn:disabled {
  background: var(--text-muted);
  cursor: not-allowed;
}

.error {
  padding: var(--spacing-3);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--danger-color);
  border-radius: var(--radius-sm);
  color: var(--danger-color);
  margin-bottom: var(--spacing-6);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-4);
  margin-bottom: var(--spacing-7);
}

.stat-card {
  background: var(--background-card);
  padding: var(--spacing-6);
  border-radius: var(--radius-md);
  text-align: center;
  border: 1px solid var(--border-color);
}

.stat-number {
  font-size: 2em;
  font-weight: bold;
  color: var(--info-color);
  margin-bottom: var(--spacing-2);
}

.stat-label {
  color: var(--text-secondary);
  font-size: 0.9em;
}

.clients-section h4 {
  margin-bottom: var(--spacing-4);
  color: var(--text-primary);
}

.client-card {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-3);
  overflow: hidden;
}

.client-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--background-darker);
  border-bottom: 1px solid var(--border-color);
}

.client-ip {
  font-weight: bold;
  color: var(--text-primary);
}

.connection-count {
  padding: var(--spacing-1) var(--spacing-2);
  border-radius: var(--radius-full);
  font-size: 0.85em;
  background: var(--background-darker);
  color: var(--text-secondary);
}

.connection-count.multiple {
  background: rgba(245, 158, 11, 0.15);
  color: var(--warning-color);
  border: 1px solid var(--warning-color);
}

.connections-list {
  padding: var(--spacing-3) var(--spacing-4);
}

.connection-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-2) 0;
  border-bottom: 1px solid var(--border-color);
}

.connection-item:last-child {
  border-bottom: none;
}

.connection-id {
  font-family: monospace;
  font-size: 0.85em;
  color: var(--text-secondary);
}

.connection-state {
  padding: var(--spacing-1) var(--spacing-2);
  border-radius: var(--radius-sm);
  font-size: 0.8em;
  text-transform: uppercase;
  font-weight: bold;
}

.connection-state.connected {
  background: rgba(34, 197, 94, 0.15);
  color: var(--success-color);
}

.connection-state.disconnected {
  background: rgba(239, 68, 68, 0.15);
  color: var(--danger-color);
}

.connection-state.connecting {
  background: rgba(245, 158, 11, 0.15);
  color: var(--warning-color);
}
</style>
