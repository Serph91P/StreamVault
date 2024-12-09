<template>
  <div class="app">
    <header>
      <h1>StreamVault</h1>
      <AddStreamerForm @streamer-added="refreshData" />
    </header>
    
    <div class="main-content">
      <StreamerList />
      <ViewerStats />
      <NotificationFeed />
    </div>
  </div>
</template>

<script setup>
import StreamerList from '@/components/StreamerList.vue'
import NotificationFeed from '@/components/NotificationFeed.vue'
import ViewerStats from '@/components/ViewerStats.vue'
import AddStreamerForm from '@/components/AddStreamerForm.vue'
</script>
