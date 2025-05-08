<template>
  <div class="add-streamer-view">
    <div class="add-streamer-container">
      <div class="page-header">
        <h2>Add New Streamer</h2>
        <p class="description">Add your favorite Twitch streamers to get notifications when they go live.</p>
      </div>
      
      <div class="content-section">
        <AddStreamerForm @streamer-added="handleStreamerAdded" />
      </div>
      
      <div class="content-section import-section">
        <h3>Import from Twitch</h3>
        <p class="import-description">Or import streamers you already follow on Twitch</p>
        <TwitchImportForm @streamers-imported="handleStreamersImported" />
      </div>
    </div>
  </div>
</template>

<script setup>
import AddStreamerForm from '@/components/AddStreamerForm.vue'
import TwitchImportForm from '@/components/TwitchImportForm.vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const handleStreamerAdded = () => {
  router.push('/')
}

const handleStreamersImported = () => {
  router.push('/')
}
</script>
