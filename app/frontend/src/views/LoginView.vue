<template>
  <div class="login-view">
    <div class="login-container">
      <!-- Logo & Branding -->
      <div class="login-header">
        <div class="logo-wrapper">
          <svg class="logo-icon">
            <use href="#icon-video" />
          </svg>
        </div>
        <h1 class="app-title">StreamVault</h1>
        <p class="app-subtitle">Automated Stream Recording</p>
      </div>

      <!-- Login Card -->
      <GlassCard class="login-card">
        <form @submit.prevent="handleLogin" class="login-form">
          <h2 class="form-title">Welcome Back</h2>
          <p class="form-subtitle">Sign in to continue to your dashboard</p>

          <!-- Error Message -->
          <div v-if="error" class="error-banner" role="alert">
            <svg class="error-icon">
              <use href="#icon-alert-circle" />
            </svg>
            <span>{{ error }}</span>
          </div>

          <!-- Username Input -->
          <div class="form-group">
            <label for="username" class="form-label">Username</label>
            <div class="input-wrapper">
              <svg class="input-icon">
                <use href="#icon-user" />
              </svg>
              <input
                id="username"
                class="form-input"
                type="text"
                v-model="username"
                placeholder="Enter your username"
                autocomplete="username"
                required
                :disabled="isLoading"
              />
            </div>
          </div>

          <!-- Password Input -->
          <div class="form-group">
            <label for="password" class="form-label">Password</label>
            <div class="input-wrapper">
              <svg class="input-icon">
                <use href="#icon-lock" />
              </svg>
              <input
                id="password"
                class="form-input"
                type="password"
                v-model="password"
                placeholder="Enter your password"
                autocomplete="current-password"
                required
                :disabled="isLoading"
              />
            </div>
          </div>

          <!-- Submit Button -->
          <button
            type="submit"
            class="btn-submit"
            :disabled="isLoading"
            v-ripple
          >
            <span v-if="isLoading" class="spinner"></span>
            <svg v-else class="btn-icon">
              <use href="#icon-log-in" />
            </svg>
            <span>{{ isLoading ? 'Signing in...' : 'Sign In' }}</span>
          </button>
        </form>
      </GlassCard>

      <!-- Footer -->
      <div class="login-footer">
        <p>First time here? The default credentials are in the setup guide.</p>
      </div>
    </div>

    <!-- Background Decoration -->
    <div class="background-decoration">
      <div class="decoration-circle decoration-1"></div>
      <div class="decoration-circle decoration-2"></div>
      <div class="decoration-circle decoration-3"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import GlassCard from '@/components/cards/GlassCard.vue'

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
      credentials: 'include', // CRITICAL: Required to set/send session cookie
      body: JSON.stringify({
        username: username.value,
        password: password.value
      })
    })

    if (response.ok) {
      // Force a full page reload to ensure all composables reinitialize with auth
      window.location.href = '/'
    } else {
      const data = await response.json()
      error.value = data.detail || 'Invalid username or password'
    }
  } catch (e) {
    error.value = 'Connection failed. Please check your network and try again.'
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-4);
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, var(--background-primary) 0%, var(--background-secondary) 100%);
}

.login-container {
  width: 100%;
  max-width: 440px;
  position: relative;
  z-index: 2;
  animation: fadeInUp 0.6s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

// Header
.login-header {
  text-align: center;
  margin-bottom: var(--spacing-8);
}

.logo-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  background: var(--gradient-primary);
  border-radius: var(--radius-2xl);
  margin-bottom: var(--spacing-4);
  box-shadow: var(--shadow-lg);
  animation: logoFloat 3s ease-in-out infinite;
}

@keyframes logoFloat {
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-10px);
  }
}

.logo-icon {
  width: 40px;
  height: 40px;
  fill: white;
}

.app-title {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-2);
  letter-spacing: -0.02em;
}

.app-subtitle {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
}

// Login Card
.login-card {
  padding: var(--spacing-8);
  animation: scaleIn 0.6s ease-out 0.2s both;
}

@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
}

.form-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin: 0;
  text-align: center;
}

.form-subtitle {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  text-align: center;
  margin-top: calc(var(--spacing-2) * -1);
}

// Error Banner
.error-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-4);
  background: rgba(var(--color-error-rgb), 0.1);
  border: 1px solid var(--color-error);
  border-radius: var(--radius-lg);
  color: var(--color-error);
  font-size: var(--font-size-sm);
  animation: shake 0.5s ease-out;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-10px); }
  75% { transform: translateX(10px); }
}

.error-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  fill: currentColor;
}

// Form Groups
.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.form-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: var(--spacing-4);
  width: 20px;
  height: 20px;
  fill: var(--text-tertiary);
  pointer-events: none;
  transition: fill 0.2s ease;
}

.form-input {
  width: 100%;
  padding: var(--spacing-4) var(--spacing-4) var(--spacing-4) var(--spacing-12);
  background: var(--background-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-base);
  color: var(--text-primary);
  transition: all 0.2s ease;

  &::placeholder {
    color: var(--text-tertiary);
  }

  &:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), 0.1);

    + .input-icon {
      fill: var(--color-primary);
    }
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

// Submit Button
.btn-submit {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  width: 100%;
  padding: var(--spacing-4);
  background: var(--gradient-primary);
  color: white;
  border: none;
  border-radius: var(--radius-lg);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
  }

  &:active:not(:disabled) {
    transform: translateY(0);
  }

  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
}

.btn-icon {
  width: 20px;
  height: 20px;
  fill: currentColor;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

// Footer
.login-footer {
  text-align: center;
  margin-top: var(--spacing-6);
  animation: fadeIn 0.6s ease-out 0.4s both;

  p {
    font-size: var(--font-size-sm);
    color: var(--text-tertiary);
    margin: 0;
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

// Background Decoration
.background-decoration {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  overflow: hidden;
}

.decoration-circle {
  position: absolute;
  border-radius: 50%;
  background: var(--gradient-primary);
  opacity: 0.05;
  animation: float 20s ease-in-out infinite;
}

.decoration-1 {
  width: 400px;
  height: 400px;
  top: -200px;
  right: -100px;
  animation-delay: 0s;
}

.decoration-2 {
  width: 300px;
  height: 300px;
  bottom: -150px;
  left: -100px;
  animation-delay: -7s;
}

.decoration-3 {
  width: 200px;
  height: 200px;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation-delay: -14s;
}

@keyframes float {
  0%, 100% {
    transform: translate(0, 0) scale(1);
  }
  33% {
    transform: translate(30px, -30px) scale(1.1);
  }
  66% {
    transform: translate(-20px, 20px) scale(0.9);
  }
}

// Responsive
@media (max-width: 640px) {
  .login-view {
    padding: var(--spacing-4);
  }

  .login-card {
    padding: var(--spacing-6);
  }

  .app-title {
    font-size: var(--font-size-2xl);
  }

  .form-title {
    font-size: var(--font-size-xl);
  }

  .logo-wrapper {
    width: 64px;
    height: 64px;
  }

  .logo-icon {
    width: 32px;
    height: 32px;
  }
}
</style>
