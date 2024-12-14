<template>
  <div class="subscription-manager">
    <div class="controls">
      <button @click="loadSubscriptions" class="btn primary">
        Check Subscriptions
      </button>
      <button @click="deleteAllSubscriptions" class="btn danger">
        Delete All Subscriptions
      </button>
    </div>

    <div v-if="subscriptions.length" class="subscription-list">
      <div v-for="sub in subscriptions" :key="sub.id" class="subscription-item">
        <div class="subscription-info">
          <span>Type: {{ sub.type }}</span>
          <span>Status: {{ sub.status }}</span>
          <span>Created: {{ new Date(sub.created_at).toLocaleString() }}</span>
        </div>
        <button @click="deleteSubscription(sub.id)" class="btn danger small">
          Delete
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const subscriptions = ref([])

async function loadSubscriptions() {
  const response = await fetch('/api/streamers/subscriptions')
  const data = await response.json()
  subscriptions.value = data.subscriptions
}

async function deleteSubscription(id) {
  await fetch(`/api/streamers/subscriptions/${id}`, {
    method: 'DELETE'
  })
  await loadSubscriptions()
}

async function deleteAllSubscriptions() {
  await fetch('/api/streamers/subscriptions', {
    method: 'DELETE'
  })
  subscriptions.value = []
}
</script>

<style scoped>
.subscription-manager {
  padding: 1rem;
}

.controls {
  margin-bottom: 1rem;
  display: flex;
  gap: 1rem;
}

.subscription-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.subscription-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.subscription-info {
  display: flex;
  gap: 1rem;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  border: none;
  cursor: pointer;
}

.btn.primary {
  background: #4CAF50;
  color: white;
}

.btn.danger {
  background: #f44336;
  color: white;
}

.btn.small {
  padding: 0.25rem 0.5rem;
}
</style>
