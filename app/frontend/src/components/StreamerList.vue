<template>
  <div class="container">
    <div class="streamer-table-container">
      <table class="streamer-table">
        <thead>
          <tr>
            <th @click="sortBy('username')" style="width: 15%">
              Streamer
              <span class="sort-icon">{{ sortKey === 'username' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
            </th>
            <th @click="sortBy('status')" style="width: 10%">
              Status
              <span class="sort-icon">{{ sortKey === 'status' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
            </th>
            <th style="width: 30%">Title</th>
            <th style="width: 15%">Category</th>
            <th style="width: 10%">Language</th>
            <th @click="sortBy('lastUpdate')" style="width: 15%">
              Last Update
              <span class="sort-icon">{{ sortKey === 'lastUpdate' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
            </th>
            <th style="width: 5%">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="streamer in sortedStreamers" 
              :key="streamer.id"
              :class="{ 'live': streamer.is_live }">
            <td>
              <div class="streamer-info">
                <span class="status-dot" :class="{ 'live': streamer.is_live }"></span>
                {{ streamer.username }}
              </div>
            </td>
            <td>
              <span class="status-badge" :class="{ 'live': streamer.is_live }">
                {{ streamer.is_live ? 'LIVE' : 'OFFLINE' }}
              </span>
            </td>
            <td class="title-cell">{{ streamer.title || '-' }}</td>
            <td>{{ streamer.category || '-' }}</td>
            <td>{{ streamer.language || '-' }}</td>
            <td>{{ formatDate(streamer.last_updated) }}</td>
            <td>
              <button 
                @click="deleteStreamer(streamer.id)" 
                class="delete-btn"
                :disabled="isDeleting"
              >
                {{ isDeleting ? 'Deleting...' : 'Delete' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 2rem;
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
  font-size: 1.1em;
}

th {
  background: #2f2f2f;
  padding: 16px;
  cursor: pointer;
  border-bottom: 1px solid #383838;
  user-select: none;
  font-weight: 600;
}

td {
  padding: 16px;
  border-bottom: 1px solid #383838;
}

.title-cell {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sort-icon {
  font-size: 0.8em;
  margin-left: 4px;
  opacity: 0.7;
}

.streamer-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ff4444;
  transition: background-color 0.3s;
}

.status-dot.live {
  background: #44ff44;
}

.status-badge {
  padding: 6px 12px;
  border-radius: 12px;
  font-size: 0.9em;
  font-weight: bold;
  background: #dc3545;
  color: #fff;
  display: inline-block;
  min-width: 80px;
  text-align: center;
}

.status-badge.live {
  background: #28a745;
}

tr {
  transition: background-color 0.2s;
}

tr:hover {
  background: #2f2f2f;
}

.delete-btn {
  background: #dc3545;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
  font-size: 0.9em;
}

.delete-btn:hover:not(:disabled) {
  background: #c82333;
}

.delete-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.6; }
  100% { opacity: 1; }
}

tr.live {
  animation: pulse 2s infinite;
}
</style>
