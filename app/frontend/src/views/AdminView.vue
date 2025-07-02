<template>
  <div class="admin-view">
    <AdminPanel />
  </div>
</template>

<script setup lang="ts">
import AdminPanel from '../components/admin/AdminPanel.vue'
</script>

<style scoped>
.admin-view {
  min-height: 100vh;
  background: #f8f9fa;
  padding-top: 20px;
}
</style>
