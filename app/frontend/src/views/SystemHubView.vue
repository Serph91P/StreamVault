<template>
  <main class="page-view system-hub">
    <PageHeader
      title="System"
      icon="settings"
      subtitle="Open settings, administration, or subscription management."
    />

    <section aria-label="System tools">
      <router-link to="/settings" aria-label="Settings">
        <span aria-hidden="true">
          <svg><use href="#icon-settings" /></svg>
        </span>
        <span>
          <strong>Settings</strong>
          <small>Preferences and application configuration</small>
        </span>
      </router-link>
      <router-link to="/admin" aria-label="Admin tools">
        <span aria-hidden="true">
          <svg><use href="#icon-sliders" /></svg>
        </span>
        <span>
          <strong>Admin tools</strong>
          <small>System health, services, and background jobs</small>
        </span>
      </router-link>
      <router-link to="/subscriptions" aria-label="Subscriptions">
        <span aria-hidden="true">
          <svg><use href="#icon-rss" /></svg>
        </span>
        <span>
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
