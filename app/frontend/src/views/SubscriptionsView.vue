<template>
  <div class="subscriptions-page">
    <h2>Subscription Management</h2>
    
    <div class="controls">
      <button @click="loadSubscriptions" :disabled="loading" class="btn primary">
        {{ loading ? 'Loading...' : 'Refresh Subscriptions' }}
      </button>
      <button @click="deleteAllSubscriptions" :disabled="loading || !subscriptions.length" class="btn danger">
        Delete All Subscriptions
      </button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading subscriptions...</p>
    </div>

    <div v-else-if="subscriptions.length" class="streamer-table-container">
      <table class="streamer-table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Status</th>
            <th>Created At</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="sub in subscriptions" :key="sub.id">
            <td>{{ sub.type }}</td>
            <td>
              <span class="status-badge" :class="sub.status">
                {{ sub.status }}
              </span>
            </td>
            <td>{{ new Date(sub.created_at).toLocaleString() }}</td>
            <td>
              <button @click="deleteSubscription(sub.id)" class="delete-btn" :disabled="loading">
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="empty-state">
      <p>No subscriptions found</p>
    </div>
  </div>
</template>

<style scoped>
.subscriptions-page {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.controls {
  margin-bottom: 2rem;
  display: flex;
  gap: 1rem;
}

.streamer-table-container {
  overflow-x: auto;
  background: #242424;
  border-radius: 8px;
  border: 1px solid #383838;
  margin: 20px 0;
}

.streamer-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  color: #fff;
}

th {
  background: #2f2f2f;
  padding: 12px;
  border-bottom: 1px solid #383838;
}

td {
  padding: 12px;
  border-bottom: 1px solid #383838;
}

tr:hover {
  background: #2f2f2f;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: bold;
}

.status-badge.enabled {
  background: #28a745;
}

.status-badge.disabled {
  background: #dc3545;
}

.delete-btn {
  background: #dc3545;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.delete-btn:hover:not(:disabled) {
  background: #c82333;
}

.delete-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.loading-state {
  text-align: center;
  padding: 2rem;
  color: #fff;
}

.spinner {
  border: 4px solid #383838;
  border-top: 4px solid #3498db;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-weight: 500;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn.primary {
  background: #3498db;
  color: white;
}

.btn.danger {
  background: #dc3545;
  color: white;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #666;
}
</style>
