<template>
  <div class="add-streamer-page">
    <h2>Add New Streamer</h2>
    <AddStreamerForm @streamer-added="handleStreamerAdded" />
  </div>
</template>

<script setup>
import AddStreamerForm from '@/components/AddStreamerForm.vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const handleStreamerAdded = () => {
  router.push('/')
}
</script>

<style scoped>
.add-streamer-page {
  padding: 2rem;
  max-width: 800px;
  margin: 0 auto;
}
</style>
