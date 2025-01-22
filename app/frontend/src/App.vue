<template>
  <div class="app">
    <header class="app-header">
      <div class="header-content">
        <h1>StreamVault</h1>
        <nav>
          <router-link to="/">Home</router-link>
          <router-link to="/add-streamer">Add Streamer</router-link>
          <router-link to="/subscriptions">Subscriptions</router-link>
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
</script>
  <style scoped>
  .app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .app-header {
    background: #18181b;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 100;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .header-content {
    width: 100%;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }

  h1 {
    color: #efeff1;
    margin: 0;
    font-size: 1.5rem;
  }

  nav {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.5rem;
    width: 100%;
  }

  nav a {
    color: #adadb8;
    text-decoration: none;
    font-weight: 500;
    padding: 0.5rem;
    border-radius: 4px;
    transition: all 0.2s ease;
    font-size: 0.9rem;
  }

  nav a:hover {
    color: #efeff1;
    background: rgba(255, 255, 255, 0.1);
  }

  nav a.router-link-active {
    color: #9147ff;
    background: rgba(145, 71, 255, 0.1);
  }

  .main-content {
    margin-top: 120px;
    padding: 1rem;
    flex: 1;
    width: 100%;
  }

  /* Tablet and up */
  @media (min-width: 768px) {
    .header-content {
      flex-direction: row;
      justify-content: space-between;
      max-width: 1200px;
      margin: 0 auto;
      padding: 1rem 2rem;
    }

    nav {
      width: auto;
      gap: 1.5rem;
    }

    nav a {
      padding: 0.5rem 1rem;
      font-size: 1rem;
    }

    .main-content {
      margin-top: 80px;
      padding: 2rem;
      max-width: 1200px;
      margin-left: auto;
      margin-right: auto;
    }
  }
  </style>
