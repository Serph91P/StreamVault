<template>
  <div class="subscription-manager">
    <div class="controls">
      <button @click="loadSubscriptions" class="btn primary interactive-element">
        Check Subscriptions
      </button>
      <button @click="deleteAllSubscriptions" class="btn danger interactive-element">
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
        <button @click="deleteSubscription(sub.id)" class="delete-btn interactive-element">
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