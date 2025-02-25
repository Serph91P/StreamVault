<template>
  <div class="streamer-detail">
    <div class="streamer-header" v-if="streamerName">
      <h1>Streams von {{ streamerName }}</h1>
    </div>
    <StreamList />
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import StreamList from '@/components/StreamList.vue'

const route = useRoute()
const streamerName = computed(() => route.query.name as string)
</script>