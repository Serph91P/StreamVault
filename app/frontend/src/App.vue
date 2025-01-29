<template>
  <div class="app">
    <header class="app-header">
      <div class="header-content">
        <h1>StreamVault</h1>
        <nav>
          <router-link to="/">Home</router-link>
          <router-link to="/add-streamer">Add Streamer</router-link>
          <router-link to="/subscriptions">Subscriptions</router-link>
          <router-link to="/settings">Settings</router-link>
        </nav>
      </div>
    </header>
    
    <div class="main-content">
      <NotificationFeed />
      <router-view />
    </div>
  </div>
</template>

<script setup>
import NotificationFeed from '@/components/NotificationFeed.vue'
import '@/styles/main.scss'
</script>