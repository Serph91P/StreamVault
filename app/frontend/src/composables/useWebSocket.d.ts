interface WebSocketMessage {
  type: string
  data?: any
  message?: string
}

export function useWebSocket(): {
  messages: Ref<WebSocketMessage[]>
  connectionStatus: Ref<string>
}
