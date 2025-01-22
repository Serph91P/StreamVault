<template>
  <div class="login-page">
    <form @submit.prevent="handleLogin" class="login-form">
      <h2>Login</h2>
      <div class="form-group">
        <input 
          type="text" 
          v-model="username" 
          placeholder="Username" 
          required
        >
      </div>
      <div class="form-group">
        <input 
          type="password" 
          v-model="password" 
          placeholder="Password" 
          required
        >
      </div>
      <button type="submit" :disabled="isLoading">
        {{ isLoading ? 'Logging in...' : 'Login' }}
      </button>
      <div v-if="error" class="error">{{ error }}</div>
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
