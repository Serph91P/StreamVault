<template>
  <div class="app">
    <!-- Desktop and tablet header -->
    <header class="app-header">
      <div class="header-content">
        <h1 class="app-logo">StreamVault</h1>
        <nav class="main-nav">
          <router-link to="/" class="nav-link">Home</router-link>
          <router-link to="/add-streamer" class="nav-link">Add Streamer</router-link>
          <router-link to="/subscriptions" class="nav-link">Subscriptions</router-link>
          <router-link to="/settings" class="nav-link">Settings</router-link>
        </nav>
      </div>
    </header>
    
    <div class="main-content">
      <NotificationFeed />
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>
    
    <!-- Mobile navigation for better mobile experience -->
    <div class="mobile-nav-bottom">
      <router-link to="/" class="mobile-nav-item">
        <i class="mobile-nav-icon">🏠</i>
        <span>Home</span>
      </router-link>
      <router-link to="/add-streamer" class="mobile-nav-item">
        <i class="mobile-nav-icon">➕</i>
        <span>Add</span>
      </router-link>
      <router-link to="/subscriptions" class="mobile-nav-item">
        <i class="mobile-nav-icon">🔔</i>
        <span>Subs</span>
      </router-link>
      <router-link to="/settings" class="mobile-nav-item">
        <i class="mobile-nav-icon">⚙️</i>
        <span>Settings</span>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import NotificationFeed from '@/components/NotificationFeed.vue'
import '@/styles/main.scss'
</script>