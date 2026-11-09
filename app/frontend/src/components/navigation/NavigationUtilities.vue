<script setup lang="ts">
import { utilityTabs, useNavigation } from '@/composables/useNavigation'
import { useAuth } from '@/composables/useAuth'
import ThemeToggle from '@/components/ThemeToggle.vue'


const emit = defineEmits<{ navigate: [] }>()
const { isActiveRoute } = useNavigation()
const { logout } = useAuth()
async function confirmLogout() {
  if (confirm('Are you sure you want to logout?')) await logout()
}
</script>

<template>
  <nav class="navigation-utilities" aria-label="Werkzeuge und Sitzung">
    <router-link v-for="tab in utilityTabs" :key="tab.route" :to="tab.route"
      :aria-current="isActiveRoute(tab.route) ? 'page' : undefined" @click="emit('navigate')">
      {{ tab.label }}
    </router-link>
    <div class="utility-session">
      <ThemeToggle />
      <button type="button" aria-label="Logout" @click="confirmLogout">Logout</button>
    </div>
  </nav>
</template>

<style scoped lang="scss">
.navigation-utilities {
  display: grid;
  gap: var(--spacing-2);
  padding: var(--spacing-2);
  border-top: 1px solid var(--sv-sem-border-default);
  a, button { min-height: 44px; color: var(--sv-sem-text-primary); border-radius: var(--radius-md); }
  a { display: flex; gap: var(--spacing-2); text-decoration: none; overflow-wrap: anywhere; }

  button { background: var(--sv-sem-surface-panel); border: 1px solid var(--sv-sem-border-default); padding: var(--spacing-2); cursor: pointer; }
}
.utility-session { display: flex; flex-wrap: wrap; gap: var(--spacing-2); }
</style>
