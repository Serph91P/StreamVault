<template>
  <div class="page-view channel-management-view">
    <PageHeader title="Kanalverwaltung" icon="users" back-to="/streamers" back-label="Zurück zu Kanälen" />
    <BasePanel padding="lg">
      <template #title>Mehrere Kanäle verwalten</template>
      <template #description>Aufnahmen und Benachrichtigungen für alle Kanäle schalten. Einzelne Einstellungen bleiben im Kanaldetail.</template>
      <ChannelSettingsPanel />
    </BasePanel>
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/base/PageHeader.vue'
import BasePanel from '@/components/base/BasePanel.vue'
import ChannelSettingsPanel from '@/components/settings/ChannelSettingsPanel.vue'
</script>
