/**
 * PERFORMANCE OPTIMIZATION: API Request Deduplication & Caching
 * Prevents duplicate requests and caches responses
 */
class APICache {
    cache = new Map();
    TTL = 30000; // 30 seconds default TTL
    generateKey(url, options = {}) {
        const method = options.method || 'GET';
        const body = options.body ? JSON.stringify(options.body) : '';
        return `${method}:${url}:${body}`;
    }
    isExpired(entry) {
        return Date.now() - entry.timestamp > this.TTL;
    }
    async get(url, options = {}, ttl = this.TTL) {
        const key = this.generateKey(url, options);
        const cached = this.cache.get(key);
        // Return cached data if valid
        if (cached && !this.isExpired(cached) && !cached.promise) {
            console.log(`📋 Cache HIT for ${url}`);
            return cached.data;
        }
        // Return pending promise if request is in flight
        if (cached?.promise) {
            console.log(`⏳ Request DEDUPLICATION for ${url}`);
            return cached.promise;
        }
        // Make new request
        console.log(`🌐 Cache MISS for ${url}, making request`);
        const promise = this.makeRequest(url, options);
        // Store pending promise to deduplicate requests
        this.cache.set(key, {
            data: null,
            timestamp: Date.now(),
            promise
        });
        try {
            const data = await promise;
            // Store successful result
            this.cache.set(key, {
                data,
                timestamp: Date.now()
            });
            return data;
        }
        catch (error) {
            // Remove failed request from cache
            this.cache.delete(key);
            throw error;
        }
    }
    async makeRequest(url, options) {
        const response = await fetch(url, {
            credentials: 'include',
            ...options
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    }
    invalidate(pattern) {
        if (pattern) {
            for (const [key] of this.cache.entries()) {
                if (key.includes(pattern)) {
                    this.cache.delete(key);
                }
            }
        }
        else {
            this.cache.clear();
        }
    }
    // Force refresh specific URL
    async refresh(url, options = {}) {
        const key = this.generateKey(url, options);
        this.cache.delete(key);
        return this.get(url, options);
    }
}
// Global instance
export const apiCache = new APICache();
// Helper function for common GET requests
export async function cachedFetch(url, ttl) {
    return apiCache.get(url, { method: 'GET' }, ttl);
}
// Helper function for POST requests (usually not cached)
export async function postRequest(url, data) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data),
        credentials: 'include'
    });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
}
