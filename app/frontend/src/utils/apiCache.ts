/**
 * PERFORMANCE OPTIMIZATION: API Request Deduplication & Caching
 * Prevents duplicate requests and caches responses
 */

interface CacheEntry {
  data: any
  timestamp: number
  promise?: Promise<any>
}

class APICache {
  private cache = new Map<string, CacheEntry>()
  private readonly TTL = 30000 // 30 seconds default TTL
  
  private generateKey(url: string, options: RequestInit = {}): string {
    const method = options.method || 'GET'
    const body = options.body ? JSON.stringify(options.body) : ''
    return `${method}:${url}:${body}`
  }
  
  private isExpired(entry: CacheEntry): boolean {
    return Date.now() - entry.timestamp > this.TTL
  }
  
  async get(url: string, options: RequestInit = {}, ttl = this.TTL): Promise<any> {
    const key = this.generateKey(url, options)
    const cached = this.cache.get(key)
    
    // Return cached data if valid
    if (cached && !this.isExpired(cached) && !cached.promise) {
      console.log(`📋 Cache HIT for ${url}`)
      return cached.data
    }
    
    // Return pending promise if request is in flight
    if (cached?.promise) {
      console.log(`⏳ Request DEDUPLICATION for ${url}`)
      return cached.promise
    }
    
    // Make new request
    console.log(`🌐 Cache MISS for ${url}, making request`)
    const promise = this.makeRequest(url, options)
    
    // Store pending promise to deduplicate requests
    this.cache.set(key, {
      data: null,
      timestamp: Date.now(),
      promise
    })
    
    try {
      const data = await promise
      
      // Store successful result
      this.cache.set(key, {
        data,
        timestamp: Date.now()
      })
      
      return data
    } catch (error) {
      // Remove failed request from cache
      this.cache.delete(key)
      throw error
    }
  }
  
  private async makeRequest(url: string, options: RequestInit): Promise<any> {
    const response = await fetch(url, {
      credentials: 'include',
      ...options
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    return response.json()
  }
  
  invalidate(pattern?: string): void {
    if (pattern) {
      for (const [key] of this.cache.entries()) {
        if (key.includes(pattern)) {
          this.cache.delete(key)
        }
      }
    } else {
      this.cache.clear()
    }
  }
  
  // Force refresh specific URL
  async refresh(url: string, options: RequestInit = {}): Promise<any> {
    const key = this.generateKey(url, options)
    this.cache.delete(key)
    return this.get(url, options)
  }
}

// Global instance
export const apiCache = new APICache()

// Helper function for common GET requests
export async function cachedFetch(url: string, ttl?: number): Promise<any> {
  return apiCache.get(url, { method: 'GET' }, ttl)
}

// Helper function for POST requests (usually not cached)
export async function postRequest(url: string, data: any): Promise<any> {
  return apiCache.makeRequest(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })
}
