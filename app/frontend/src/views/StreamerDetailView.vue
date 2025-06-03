<template>
  <div class="streamer-detail-view">
    <div class="streamer-detail-container">      <div class="back-btn-container">
        <router-link to="/streamers" class="back-btn">Back to streamers</router-link>
      </div>
      
      <div class="streamer-header" v-if="streamerName">
        <h1>{{ streamerName }}</h1>
      </div>
      
      <div class="streamer-content">
        <div class="streamer-section">
          <h2>Recent Streams</h2>
          <StreamList />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import StreamList from '@/components/StreamList.vue'

const route = useRoute()
const streamerName = computed(() => route.query.name as string)
</script>