<template>
  <p v-if="realtime.snapshotRevision !== loadedRevision" role="status">
    Last-known status: realtime history was interrupted. Displayed status may be outdated.
    Reopen this view to load current server data. Notification history may be incomplete.
  </p>
</template>

<script setup lang="ts">
import { useRealtimeStore } from '@/stores/realtime'

const realtime = useRealtimeStore()
const loadedRevision = realtime.snapshotRevision
</script>
