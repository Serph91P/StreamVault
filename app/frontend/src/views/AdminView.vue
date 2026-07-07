<template>
  <div class="page-view admin-view">
    <PageHeader
      title="Admin"
      icon="settings"
      subtitle="Monitor system health, services, connections, and background jobs."
    >
      <template #status>
        <span class="diag-status" :class="diagStatusClass">
          <span class="diag-dot"></span>
          {{ diagStatusLabel }}
        </span>
      </template>
    </PageHeader>
    <AdminPanel />
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/base/PageHeader.vue'
import AdminPanel from '../components/admin/AdminPanel.vue'

const diagStatusClass = 'status-idle'
const diagStatusLabel = 'Admin tools'
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.admin-view {
  min-height: 100vh;
  background: var(--color-background);
  color: var(--color-text);
}

.diag-status {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--text-sm);
  font-weight: 600;
  padding: var(--spacing-1) var(--spacing-3);
  border-radius: var(--radius-pill);
  border: 1px solid var(--border-color);
}

.diag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-tertiary);
}

.status-idle {
  color: var(--text-primary);
  border-color: var(--border-color);
}

.status-healthy {
  color: var(--success-color);
  border-color: var(--success-color);

  .diag-dot {
    background: var(--success-color);
  }
}

.status-warning {
  color: var(--warning-color);
  border-color: var(--warning-color);

  .diag-dot {
    background: var(--warning-color);
  }
}
</style>
