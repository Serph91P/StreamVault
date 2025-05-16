<template>
  <div class="welcome-page">
    <h2>Willkommen bei StreamVault!</h2>
    <p>So startest du am besten:</p>
    <ol>
      <li>
        <router-link to="/settings">Aufnahme-Einstellungen festlegen</router-link>
      </li>
      <li>
        <router-link to="/settings">Benachrichtigungen konfigurieren</router-link>
      </li>
      <li>
        <router-link to="/streamers">Streamer hinzufügen & verwalten</router-link>
      </li>
    </ol>
    <p>Du kannst diese Einstellungen jederzeit im Menü anpassen.</p>
  </div>
</template>

<script setup lang="ts">
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
</style>
