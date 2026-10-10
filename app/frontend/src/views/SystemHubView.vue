<template>
  <main class="page-view system-hub">
    <PageHeader
      title="System"
      icon="settings"
      subtitle="Open settings, administration, or subscription management."
    />

    <section class="system-hub-grid" aria-label="System tools">
      <router-link to="/settings" class="system-hub-card" aria-label="Settings">
        <span class="system-hub-icon" aria-hidden="true">
          <svg><use href="#icon-settings" /></svg>
        </span>
        <span class="system-hub-copy">
          <strong>Settings</strong>
          <small>Preferences and application configuration</small>
        </span>
      </router-link>
      <router-link to="/admin" class="system-hub-card" aria-label="Admin tools">
        <span class="system-hub-icon" aria-hidden="true">
          <svg><use href="#icon-sliders" /></svg>
        </span>
        <span class="system-hub-copy">
          <strong>Admin tools</strong>
          <small>System health, services, and background jobs</small>
        </span>
      </router-link>
      <router-link to="/subscriptions" class="system-hub-card" aria-label="Subscriptions">
        <span class="system-hub-icon" aria-hidden="true">
          <svg><use href="#icon-rss" /></svg>
        </span>
        <span class="system-hub-copy">
          <strong>Subscriptions</strong>
          <small>Manage subscribed streams and updates</small>
        </span>
      </router-link>
    </section>
  </main>
</template>

<script setup lang="ts">
import PageHeader from '@/components/base/PageHeader.vue'
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
@use '@/styles/variables' as v;

.system-hub-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--spacing-4);
}

.system-hub-card {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-4);
  min-width: 0;
  min-height: 44px;
  padding: var(--spacing-5);
  color: var(--text-primary);
  text-decoration: none;
  background: var(--sv-cmp-panel-background);
  border: 1px solid var(--sv-cmp-panel-border);
  border-radius: var(--radius-xl);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  transition: border-color v.$duration-200 v.$ease-out;

  &:hover {
    border-color: var(--sv-sem-border-strong);
  }
}

.system-hub-card:focus-visible {
  outline: 2px solid var(--sv-cmp-button-focus);
  outline-offset: 3px;
}

.system-hub-icon {
  display: grid;
  flex: 0 0 44px;
  width: 44px;
  height: 44px;
  place-items: center;
  color: var(--primary-color);
  background: var(--sv-sem-surface-raised);
  border-radius: var(--radius-lg);
}

.system-hub-icon svg {
  width: 24px;
  height: 24px;
}

.system-hub-copy {
  display: grid;
  min-width: 0;
  gap: var(--spacing-1);
}

.system-hub-copy strong {
  font-size: v.$text-lg;
  line-height: v.$leading-tight;
}

.system-hub-copy small {
  color: var(--text-secondary);
  font-size: v.$text-sm;
  line-height: v.$leading-relaxed;
}

@include m.respond-below('md') {
  .system-hub-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@include m.respond-below('sm') {
  .system-hub {
    // NavigationWrapper reserves this space for ordinary page content. Keep
    // the final system card independently reachable when the hub itself
    // becomes taller than the mobile viewport.
    padding-bottom: calc(128px + env(safe-area-inset-bottom, 0px));
  }

  .system-hub-grid {
    grid-template-columns: 1fr;
  }

  .system-hub-card {
    scroll-margin-bottom: calc(128px + env(safe-area-inset-bottom, 0px));
  }
}

@media (prefers-reduced-motion: reduce) {
  .system-hub-card {
    transition: none;
  }
}
</style>
