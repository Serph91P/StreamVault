/**
 * PWA-compatible authentication composable
 * Handles persistent sessions for standalone apps
 */
import { ref, computed } from 'vue'

const isAuthenticated = ref(false)
const sessionToken = ref<string | null>(null)
const user = ref<any>(null)

export function useAuth() {
  
  // Check if we have a stored session (for PWA)
  const checkStoredAuth = async () => {
    const storedToken = localStorage.getItem('streamvault_session')
    if (storedToken) {
      sessionToken.value = storedToken
      
      try {
        const response = await fetch('/auth/check', {
          method: 'GET',
          credentials: 'include',
          headers: {
            'Authorization': `Bearer ${storedToken}`
          }
        })
        
        if (response.ok) {
          const data = await response.json()
          isAuthenticated.value = data.authenticated || false
          if (data.user) {
            user.value = data.user
          }
        } else {
          // Invalid stored token, clear it
          clearAuth()
        }
      } catch (error) {
        console.error('Auth check failed:', error)
        clearAuth()
      }
    }
  }
  
  const login = async (username: string, password: string) => {
    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({ username, password })
      })
      
      if (response.ok) {
        const data = await response.json()
        isAuthenticated.value = true
        
        // For PWA: Store token in localStorage as backup
        const cookies = document.cookie.split(';')
        const sessionCookie = cookies.find(c => c.trim().startsWith('session='))
        if (sessionCookie) {
          const token = sessionCookie.split('=')[1]
          sessionToken.value = token
          localStorage.setItem('streamvault_session', token)
        }
        
        return { success: true, data }
      } else {
        const error = await response.json()
        return { success: false, error: error.detail || 'Login failed' }
      }
    } catch (error) {
      return { success: false, error: 'Network error during login' }
    }
  }
  
  const logout = async () => {
    try {
      await fetch('/auth/logout', {
        method: 'POST',
        credentials: 'include'
      })
    } catch (error) {
      console.error('Logout request failed:', error)
    }
    
    clearAuth()
    
    // Force redirect to login for ALL scenarios
    window.location.href = '/auth/login'
  }
  
  const clearAuth = () => {
    isAuthenticated.value = false
    sessionToken.value = null
    user.value = null
    localStorage.removeItem('streamvault_session')
    sessionStorage.clear()
  }
  
  return {
    isAuthenticated: computed(() => isAuthenticated.value),
    user: computed(() => user.value),
    sessionToken: computed(() => sessionToken.value),
    checkStoredAuth,
    login,
    logout,
    clearAuth
  }
}
