<template>
  <div class="app">
    <header>
      <h1>StreamVault</h1>
      <nav>
        <router-link to="/">Home</router-link>
        <router-link to="/subscriptions">Subscriptions</router-link>
      </nav>
      <AddStreamerForm @streamer-added="refreshData" />
    </header>
    
    <div class="main-content">
      <StreamerList />
      <NotificationFeed />
      <router-view />
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
