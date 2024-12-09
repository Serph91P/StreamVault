import { ref, onMounted, onUnmounted } from 'vue'

export function useWebSocket() {
  const messages = ref([])
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws`)

  ws.onmessage = (event) => {
    messages.value.push(event.data)
  }

  onUnmounted(() => {
    ws.close()
  })

  return {
    messages
  }
}
