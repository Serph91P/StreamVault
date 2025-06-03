<template>
  <div class="welcome-page">
    <h2>Welcome to StreamVault!</h2>
    <p>How to get started:</p>
    <ol>
      <li>
        <router-link to="/settings">Set up recording settings</router-link>
      </li>
      <li>
        <router-link to="/settings">Configure notifications</router-link>
      </li>
      <li>
        <router-link to="/streamers">Add & manage streamers</router-link>
      </li>
    </ol>
    <p>You can change these settings at any time from the menu.</p>
    <button class="btn btn-primary" @click="continueToHome">Continue</button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()

function continueToHome() {
  localStorage.setItem('welcome_seen', '1')
  router.replace('/home')
}
</script>

<style scoped>
.welcome-page {
  max-width: 600px;
  margin: 2rem auto;
  padding: 2rem;
  background: var(--background-secondary);
  border-radius: var(--radius-lg);
  box-shadow: 0 2px 12px rgba(0,0,0,0.07);
  text-align: center;
}
.welcome-page h2 {
  margin-bottom: 1rem;
}
.welcome-page ol {
  text-align: left;
  margin: 2rem auto;
  max-width: 400px;
}
.welcome-page li {
  margin-bottom: 1rem;
  font-size: 1.1rem;
}
.btn {
  margin-top: 2rem;
}
</style>
