<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import PageHeader from '@/components/base/PageHeader.vue'
import NotificationFeed from '@/components/NotificationFeed.vue'
import BackgroundQueueMonitor from '@/components/BackgroundQueueMonitor.vue'
import HomeView from './HomeView.vue'

const route = useRoute()
const showHistory = computed(() => route.query.tab === 'history')
</script>

<template>
  <div class="page-view activity-view" :class="{ 'activity-history': showHistory }">
    <PageHeader
      title="Aktivität"
      icon="activity"
      subtitle="Laufende Aufnahmen und Ereignisse. Neue Meldungen erscheinen automatisch."
    >
      <template #actions>
        <router-link class="btn btn-secondary btn-sm" to="/overview">Gesamtübersicht</router-link>
      </template>
    </PageHeader>
    <nav class="activity-tabs" aria-label="Aktivitätsansicht">
      <router-link to="/activity" :aria-current="!showHistory ? 'page' : undefined">Aktuell</router-link>
      <router-link to="/activity?tab=history" :aria-current="showHistory ? 'page' : undefined">Benachrichtigungsverlauf</router-link>

    </nav>
    <NotificationFeed v-if="showHistory" />
    <template v-else>
      <BackgroundQueueMonitor inline />
      <HomeView embedded />
    </template>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.activity-history :deep(.notification-feed) {
  height: calc(100dvh - var(--app-header-height, 56px) - var(--spacing-2) - env(safe-area-inset-top, 0px));
  overflow: hidden;
}
.activity-history :deep(.feed-header) { display: block; padding: var(--spacing-3); }
.activity-history :deep(.header-actions) { margin-top: var(--spacing-2); flex-direction: row; flex-wrap: wrap; }
.activity-history :deep(.notification-groups) { max-height: none; overscroll-behavior-y: contain; }
@include m.respond-below('lg') {
  .activity-history :deep(.notification-feed) { height: calc(100dvh - var(--app-header-height, 56px) - var(--spacing-2) - 68px - env(safe-area-inset-top, 0px) - env(safe-area-inset-bottom, 0px)); }
}
.activity-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
  margin-bottom: var(--spacing-6);
  border-bottom: 1px solid var(--border-color);

  a {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    padding: var(--spacing-3);
    color: var(--text-secondary);
    text-decoration: none;
    border-bottom: 2px solid transparent;

    &[aria-current] {
      color: var(--sv-sem-action-foreground);
      border-bottom-color: currentColor;
    }
  }
}

:deep(.home-view) {
  padding: 0;
}
</style>
