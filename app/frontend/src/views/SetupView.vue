<template>
  <div class="setup-page">
    <form @submit.prevent="handleSetup" class="setup-form">
      <h2>Initial Setup</h2>
      <p class="setup-info">Create your admin account</p>
      
      <div class="form-group">
        <input 
          type="text" 
          v-model="username" 
          placeholder="Admin Username" 
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
      <div class="form-group">
        <input 
          type="password" 
          v-model="confirmPassword" 
          placeholder="Confirm Password" 
          required
        >
      </div>
      
      <button type="submit" :disabled="isLoading || !isValid">
        {{ isLoading ? 'Creating Account...' : 'Create Admin Account' }}
      </button>
      
      <div v-if="error" class="error">{{ error }}</div>
    </form>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const isLoading = ref(false)
const error = ref('')

const isValid = computed(() => {
  return username.value.length >= 3 && 
         password.value.length >= 6 && 
         password.value === confirmPassword.value
})

const handleSetup = async () => {
  if (!isValid.value) return
  
  isLoading.value = true
  error.value = ''
  
  try {
    const response = await fetch('/setup', {
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
      error.value = data.detail || 'Setup failed'
    }
  } catch (e) {
    error.value = 'An error occurred'
  } finally {
    isLoading.value = false
  }
}</script>

<style scoped>
.setup-page {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #18181b;
  z-index: 100;
}

.setup-form {
  background: #1f1f23;
  padding: 2rem;
  border-radius: 8px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.setup-info {
  color: #adadb8;
  text-align: center;
  margin-bottom: 1.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #303034;
  border-radius: 4px;
  background: #18181b;
  color: #efeff1;
}

button {
  width: 100%;
  padding: 0.75rem;
  background: #9147ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

button:disabled {
  background: #392e5c;
  cursor: not-allowed;
}

.error {
  color: #ff4444;
  margin-top: 1rem;
  text-align: center;
}
</style>
