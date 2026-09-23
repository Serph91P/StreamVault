/**
 * Proxy System Types
 *
 * Types for Multi-Proxy System with Health Checks
 */

export interface ProxySettings {
  id: number
  proxy_url: string  // Masked URL from backend
  masked_url: string // Masked URL for display (user:***@host:port)
  priority: number
  enabled: boolean
  health_status: 'unknown' | 'healthy' | 'degraded' | 'failed'
  last_check: string | null  // ISO datetime
  response_time_ms: number | null
  consecutive_failures: number
  last_error: string | null
  total_requests: number
  successful_requests: number
  failed_requests: number
  created_at: string | null  // ISO datetime
}

export interface ProxyAddRequest {
  proxy_url: string
  priority?: number
}

export interface ProxyUpdatePriorityRequest {
  priority: number
}

export interface ProxyListResponse {
  proxies: ProxySettings[]
  system_config: ProxyConfigSettings
}

export interface ProxyConfigSettings {
  enable_proxy: boolean
  proxy_health_check_enabled: boolean
  proxy_health_check_interval_seconds: number
  proxy_max_consecutive_failures: number
  fallback_to_direct_connection: boolean
}

export interface ProxyHealthCheckResult {
  proxy_id: number
  health_status: 'healthy' | 'degraded' | 'failed'
  response_time_ms: number | null
  consecutive_failures: number
  enabled: boolean
  error: string | null
}

export interface ProxySuccessResponse {
  success: boolean
  message: string
}

export interface ProxyAddResponse extends ProxySuccessResponse {
  proxy_id: number
}

export interface ProxyToggleResponse extends ProxySuccessResponse {
  enabled: boolean
}

export interface ProxyHealthCheckResponse {
  success: boolean
  result: ProxyHealthCheckResult
}

export interface ProxyConfigUpdateResponse extends ProxySuccessResponse {
  config: ProxyConfigSettings
}

export interface BestProxyResponse {
  proxy: ProxySettings | null
  message: string
}

// WebSocket event payload for real-time updates
export interface ProxyHealthUpdateEvent {
  type: 'proxy_health_update'
  data: {
    proxy_id: number
    health_status: 'healthy' | 'degraded' | 'failed'
    response_time_ms: number | null
    last_error: string | null
    consecutive_failures: number
    checked_at: string
  }
}
