<template>
  <div class="viewer-stats">
    <LineChart :data="viewerData" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Line as LineChart } from 'vue-chartjs'

const viewerData = ref({
  labels: [],
  datasets: [{
    label: 'Viewers',
    data: [],
    borderColor: '#6441a5'
  }]
})

onMounted(async () => {
  await fetchViewerStats()
})

async function fetchViewerStats() {
  const response = await fetch('/api/viewer-stats')
  const data = await response.json()
  viewerData.value = formatChartData(data)
}
</script>
