<template>
  <div class="viewer-stats">
    <LineChart :data="viewerData" :options="chartOptions" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Line as LineChart } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js'

// Register Chart.js components
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const viewerData = ref({
  labels: [],
  datasets: [{
    label: 'Viewers',
    data: [],
    borderColor: '#6441a5'
  }]
})

const chartOptions = {
  responsive: true,
  scales: {
    x: {
      type: 'category'
    },
    y: {
      beginAtZero: true
    }
  }
}

onMounted(async () => {
  await fetchViewerStats()
})

async function fetchViewerStats() {
  try {
    const response = await fetch('/api/viewer-stats')
    const data = await response.json()
    viewerData.value.labels = data.labels
    viewerData.value.datasets[0].data = data.data
  } catch (error) {
    console.error('Error fetching viewer stats:', error)
  }
}
</script>
