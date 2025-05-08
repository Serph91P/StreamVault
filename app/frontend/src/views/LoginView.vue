<template>
  <div class="auth-view login-page">
    <form @submit.prevent="handleLogin" class="auth-form login-form" aria-labelledby="login-heading">
      <h2 id="login-heading">Login</h2>
      
      <div class="form-group">
        <label for="username" class="sr-only">Username</label>
        <input 
          id="username"
          class="auth-input"
          type="text" 
          v-model="username" 
          placeholder="Username" 
          autocomplete="username"
          required
        >
      </div>
      
      <div class="form-group">
        <label for="password" class="sr-only">Password</label>
        <input 
          id="password"
          class="auth-input"
          type="password" 
          v-model="password" 
          placeholder="Password"
          autocomplete="current-password"
          required
        >
      </div>
      
      <button 
        type="submit" 
        class="auth-submit-btn" 
        :disabled="isLoading"
        aria-live="polite"
      >
        <span v-if="isLoading" class="loader" aria-hidden="true"></span>
        <span>{{ isLoading ? 'Logging in...' : 'Login' }}</span>
      </button>
      
      <div v-if="error" class="error-msg" role="alert">{{ error }}</div>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const username = ref('')
const password = ref('')
const isLoading = ref(false)
const error = ref('')

const handleLogin = async () => {
  isLoading.value = true
  error.value = ''

  try {
    const response = await fetch('/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        username: username.value,
        password: password.value
      })
    })
  
    if (response.ok) {
      router.push('/')
    } else {
      const data = await response.json()
      error.value = data.detail || 'Login failed'
    }
  } catch (e) {
    error.value = 'An error occurred'
  } finally {
    isLoading.value = false
  }
}
</script>
