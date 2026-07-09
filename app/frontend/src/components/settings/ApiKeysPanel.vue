<template>
  <div class="api-keys-panel">
    <div class="panel-intro">
      <p>
        API keys provide programmatic access to StreamVault without an
        interactive login. Send them as
        <code>X-API-Key: sv_…</code> or
        <code>Authorization: ApiKey sv_…</code>.
      </p>
      <p class="hint">
        Public Twitch endpoints (<code>/eventsub</code>,
        <code>/api/twitch/callback</code>) and the auth flow do not need a key.
        Everything else can be reached either with a session cookie or with an
        API key, e.g. <code>/api/status/recordings-active</code>.
      </p>
    </div>

    <!-- Create form -->
    <div class="create-row">
      <input
        v-model="newKeyName"
        type="text"
        placeholder="Key name (e.g. 'monitoring')"
        class="key-name-input"
        @keyup.enter="createKey"
      />
      <button
        class="btn btn-primary"
        :disabled="!newKeyName.trim() || creating"
        @click="createKey"
      >
        {{ creating ? 'Creating…' : 'Create API Key' }}
      </button>
    </div>

    <!-- Freshly created key (only shown once) -->
    <div v-if="freshKey" class="fresh-key">
      <div class="fresh-key-header">
        <strong>New API key created - copy it now.</strong>
        <button class="btn btn-sm" @click="freshKey = null">Dismiss</button>
      </div>
      <p class="fresh-key-warning">
        This is the only time the full key is shown. If you lose it, revoke it
        and create a new one.
      </p>
      <div class="fresh-key-row">
        <code class="fresh-key-value">{{ freshKey.key }}</code>
        <button class="btn btn-sm" @click="copyFresh">Copy</button>
      </div>
    </div>

    <!-- Existing keys -->
    <section class="danger-zone" aria-labelledby="api-key-danger-title">
      <div class="danger-zone-header">
        <h2 id="api-key-danger-title">API key access</h2>
        <span class="danger-badge">Danger zone</span>
      </div>
      <p class="danger-copy">
        Revoking a key immediately stops existing scripts and dashboards that use it.
      </p>

      <div v-if="loading" class="loading">Loading…</div>
      <div v-else-if="keys.length === 0" class="empty">
        No API keys yet.
      </div>
      <div v-else class="keys-table-wrap">
        <table class="keys-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Prefix</th>
              <th>Created</th>
              <th>Last used</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="k in keys" :key="k.id">
              <td data-label="Name">{{ k.name }}</td>
              <td data-label="Prefix"><code>{{ k.prefix }}…</code></td>
              <td data-label="Created">{{ formatDate(k.created_at) }}</td>
              <td data-label="Last used">{{ k.last_used_at ? formatDate(k.last_used_at) : 'never' }}</td>
              <td data-label="Action">
                <button class="btn btn-sm btn-danger" @click="revokeKey(k)">
                  Revoke
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface ApiKey {
  id: number
  name: string
  prefix: string
  created_at: string
  last_used_at: string | null
}

interface ApiKeyCreated extends ApiKey {
  key: string
}

const keys = ref<ApiKey[]>([])
const loading = ref(false)
const creating = ref(false)
const newKeyName = ref('')
const freshKey = ref<ApiKeyCreated | null>(null)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch('/api/api-keys', { credentials: 'include' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    keys.value = await res.json()
  } catch (e: any) {
    error.value = `Failed to load API keys: ${e.message}`
  } finally {
    loading.value = false
  }
}

async function createKey() {
  const name = newKeyName.value.trim()
  if (!name) return
  creating.value = true
  error.value = null
  try {
    const res = await fetch('/api/api-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ name })
    })
    if (!res.ok) {
      const txt = await res.text()
      throw new Error(`HTTP ${res.status}: ${txt}`)
    }
    freshKey.value = await res.json()
    newKeyName.value = ''
    await load()
  } catch (e: any) {
    error.value = `Failed to create API key: ${e.message}`
  } finally {
    creating.value = false
  }
}

async function revokeKey(k: ApiKey) {
  if (!confirm(`Revoke API key "${k.name}"? Existing clients using it will stop working.`)) return
  error.value = null
  try {
    const res = await fetch(`/api/api-keys/${k.id}`, {
      method: 'DELETE',
      credentials: 'include'
    })
    if (!res.ok && res.status !== 204) {
      throw new Error(`HTTP ${res.status}`)
    }
    await load()
  } catch (e: any) {
    error.value = `Failed to revoke key: ${e.message}`
  }
}

function copyFresh() {
  if (!freshKey.value) return
  navigator.clipboard.writeText(freshKey.value.key).catch(() => {})
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

onMounted(load)
</script>

<style scoped>
.api-keys-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.panel-intro p {
  margin: 0 0 0.5rem 0;
  font-size: 0.9rem;
  opacity: 0.85;
}
.panel-intro .hint {
  opacity: 0.7;
}
.panel-intro code {
  background: rgba(255, 255, 255, 0.08);
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-size: 0.85em;
}
.create-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.key-name-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(0, 0, 0, 0.3);
  color: inherit;
}
.fresh-key {
  border: 1px solid rgba(255, 200, 0, 0.4);
  background: rgba(255, 200, 0, 0.08);
  border-radius: 8px;
  padding: 0.75rem 1rem;
}
.fresh-key-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}
.fresh-key-warning {
  font-size: 0.85rem;
  opacity: 0.8;
  margin: 0 0 0.5rem 0;
}
.fresh-key-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.danger-zone {
  border: 1px solid rgba(255, 80, 80, 0.35);
  border-radius: 12px;
  padding: 1rem;
  background: rgba(255, 80, 80, 0.06);
}
.danger-zone-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.35rem;
}
.danger-zone h2 {
  margin: 0;
  font-size: 1rem;
}
.danger-badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 80, 80, 0.45);
  color: var(--danger-text-color);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.danger-copy {
  margin: 0 0 0.75rem;
  color: var(--text-secondary);
  font-size: 0.9rem;
}
.fresh-key-value {
  flex: 1;
  font-family: monospace;
  background: rgba(0, 0, 0, 0.4);
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  word-break: break-all;
}
.keys-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.keys-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.keys-table th,
.keys-table td {
  padding: 0.5rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.keys-table th {
  font-weight: 600;
  opacity: 0.8;
}
.empty,
.loading {
  opacity: 0.6;
  font-style: italic;
}
.error {
  color: var(--danger-color);
  font-size: 0.9rem;
}
.btn {
  padding: 0.4rem 0.8rem;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: inherit;
  cursor: pointer;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-primary {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: var(--text-on-primary);
}
.btn-danger {
  background: rgba(255, 80, 80, 0.15);
  border-color: rgba(255, 80, 80, 0.4);
  color: var(--danger-text-color);
}
.btn-sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.8rem;
}
@media (max-width: 640px) {
  .create-row,
  .fresh-key-header,
  .fresh-key-row,
  .danger-zone-header {
    align-items: stretch;
    flex-direction: column;
  }

  .keys-table,
  .keys-table thead,
  .keys-table tbody,
  .keys-table tr,
  .keys-table th,
  .keys-table td {
    display: block;
  }

  .keys-table thead {
    display: none;
  }

  .keys-table tr {
    padding: 0.75rem 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .keys-table td {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.35rem 0;
    border-bottom: 0;
    text-align: right;
  }

  .keys-table td::before {
    content: attr(data-label);
    color: var(--text-secondary);
    font-weight: 600;
    text-align: left;
  }
}
</style>
