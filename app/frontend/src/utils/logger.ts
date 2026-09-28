function formatMessage(level: string, component: string, message: string, data?: any): string {
  const suffix = data === undefined ? '' : ` ${typeof data === 'object' ? JSON.stringify(data) : data}`
  return `[${new Date().toISOString()}] ${level} [${component}] ${message}${suffix}`
}

export function logError(component: string, message: string, data?: any): void {
  console.error(formatMessage('ERROR', component, message, data))
}

export function logDebug(component: string, message: string, data?: any): void {
  if (import.meta.env.DEV) console.log(formatMessage('DEBUG', component, message, data))
}

export function logWebSocket(
  component: string,
  type: 'sent' | 'received' | 'error' | 'connected' | 'disconnected',
  message: string,
  data?: any
): void {
  if (!import.meta.env.DEV) return
  const emoji = {
    sent: '📤',
    received: '📥',
    error: '❌',
    connected: '🔗',
    disconnected: '🔌'
  }[type]
  logDebug(component, `${emoji} WebSocket ${type}: ${message}`, data)
}
