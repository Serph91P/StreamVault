/**
 * Logger utility for development and production environments
 * Provides configurable logging levels and development-only debug output
 */

export enum LogLevel {
  ERROR = 0,
  WARN = 1,
  INFO = 2,
  DEBUG = 3
}

class Logger {
  private level: LogLevel
  private isDevelopment: boolean

  constructor() {
    // Check if we're in development mode
    this.isDevelopment = import.meta.env?.DEV || process.env.NODE_ENV === 'development'
    
    // Set default log level based on environment
    this.level = this.isDevelopment ? LogLevel.DEBUG : LogLevel.ERROR
  }

  setLevel(level: LogLevel) {
    this.level = level
  }

  private shouldLog(level: LogLevel): boolean {
    return level <= this.level
  }

  private formatMessage(level: string, component: string, message: string, data?: any): string {
    const timestamp = new Date().toISOString()
    let formatted = `[${timestamp}] ${level} [${component}] ${message}`
    
    if (data !== undefined) {
      formatted += ` ${typeof data === 'object' ? JSON.stringify(data) : data}`
    }
    
    return formatted
  }

  error(component: string, message: string, data?: any) {
    if (this.shouldLog(LogLevel.ERROR)) {
      console.error(this.formatMessage('ERROR', component, message, data))
    }
  }

  warn(component: string, message: string, data?: any) {
    if (this.shouldLog(LogLevel.WARN)) {
      console.warn(this.formatMessage('WARN', component, message, data))
    }
  }

  info(component: string, message: string, data?: any) {
    if (this.shouldLog(LogLevel.INFO)) {
      console.info(this.formatMessage('INFO', component, message, data))
    }
  }

  debug(component: string, message: string, data?: any) {
    if (this.shouldLog(LogLevel.DEBUG) && this.isDevelopment) {
      console.log(this.formatMessage('DEBUG', component, message, data))
    }
  }

  // WebSocket-specific debug methods for easier debugging
  websocket(component: string, type: 'sent' | 'received' | 'error' | 'connected' | 'disconnected', message: string, data?: any) {
    if (this.isDevelopment) {
      const emoji = {
        sent: '📤',
        received: '📥',
        error: '❌',
        connected: '🔗',
        disconnected: '🔌'
      }[type]
      
      this.debug(component, `${emoji} WebSocket ${type}: ${message}`, data)
    }
  }
}

// Create singleton instance
export const logger = new Logger()

// Export convenience methods for common use cases
export const logError = (component: string, message: string, data?: any) => logger.error(component, message, data)
export const logWarn = (component: string, message: string, data?: any) => logger.warn(component, message, data)
export const logInfo = (component: string, message: string, data?: any) => logger.info(component, message, data)
export const logDebug = (component: string, message: string, data?: any) => logger.debug(component, message, data)
export const logWebSocket = (component: string, type: 'sent' | 'received' | 'error' | 'connected' | 'disconnected', message: string, data?: any) => 
  logger.websocket(component, type, message, data)
