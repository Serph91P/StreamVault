<template>
  <div class="app">
    <header>
      <h1>StreamVault</h1>
      <AddStreamerForm @streamer-added="refreshData" />
    </header>
    
    <div class="main-content">
      <StreamerList />
      <NotificationFeed />
    </div>
  </div>
</template>

<script setup>
import StreamerList from '@/components/StreamerList.vue'
import NotificationFeed from '@/components/NotificationFeed.vue'
import AddStreamerForm from '@/components/AddStreamerForm.vue'

const refreshData = () => {
  // Implement if needed
}
</script>
