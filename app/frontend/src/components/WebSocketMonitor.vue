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
              <span class="connection-state" :class="conn.state.toLowerCase()">{{ conn.state }}</span>
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

<style scoped>
.websocket-monitor {
  padding: 20px;
  max-width: 800px;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.monitor-header h3 {
  margin: 0;
  color: #333;
}

.refresh-btn {
  padding: 8px 16px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: #45a049;
}

.refresh-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.error {
  padding: 12px;
  background: #ffebee;
  border: 1px solid #f44336;
  border-radius: 4px;
  color: #c62828;
  margin-bottom: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: #f5f5f5;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  border: 1px solid #ddd;
}

.stat-number {
  font-size: 2em;
  font-weight: bold;
  color: #2196F3;
  margin-bottom: 8px;
}

.stat-label {
  color: #666;
  font-size: 0.9em;
}

.clients-section h4 {
  margin-bottom: 16px;
  color: #333;
}

.client-card {
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
}

.client-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8f9fa;
  border-bottom: 1px solid #dee2e6;
}

.client-ip {
  font-weight: bold;
  color: #495057;
}

.connection-count {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.85em;
  background: #e9ecef;
  color: #6c757d;
}

.connection-count.multiple {
  background: #fff3cd;
  color: #856404;
  border: 1px solid #ffeaa7;
}

.connections-list {
  padding: 12px 16px;
}

.connection-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #f1f3f4;
}

.connection-item:last-child {
  border-bottom: none;
}

.connection-id {
  font-family: monospace;
  font-size: 0.85em;
  color: #666;
}

.connection-state {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8em;
  text-transform: uppercase;
  font-weight: bold;
}

.connection-state.connected {
  background: #d4edda;
  color: #155724;
}

.connection-state.disconnected {
  background: #f8d7da;
  color: #721c24;
}

.connection-state.connecting {
  background: #fff3cd;
  color: #856404;
}
</style>
