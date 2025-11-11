<template>
  <div class="setup-view">
    <div class="setup-container">
      <!-- Header -->
      <div class="setup-header">
        <div class="logo-wrapper">
          <svg class="logo-icon">
            <use href="#icon-video" />
          </svg>
        </div>
        <h1 class="app-title">StreamVault</h1>
        <p class="app-subtitle">Initial Setup</p>
      </div>

      <!-- Setup Card -->
      <GlassCard class="setup-card">
        <div class="card-header">
          <h2 class="form-title">Create Admin Account</h2>
          <p class="form-subtitle">Set up your administrator credentials to get started</p>
        </div>

        <form @submit.prevent="handleSetup" class="setup-form">
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
                :class="{ 'has-error': username && username.length < 3 }"
                type="text"
                v-model="username"
                placeholder="Enter admin username"
                required
                :disabled="isLoading"
              />
              <svg v-if="username && username.length >= 3" class="validation-icon success">
                <use href="#icon-check-circle" />
              </svg>
            </div>
            <div v-if="username && username.length < 3" class="error-message">
              <svg class="error-icon">
                <use href="#icon-alert-circle" />
              </svg>
              <span>Username must be at least 3 characters</span>
            </div>
            <div v-else-if="username && username.length >= 3" class="success-message">
              <svg class="success-icon">
                <use href="#icon-check-circle" />
              </svg>
              <span>Username looks good!</span>
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
                :class="{ 'has-error': password && password.length < 6 }"
                type="password"
                v-model="password"
                placeholder="Enter password (min. 6 characters)"
                required
                :disabled="isLoading"
              />
              <svg v-if="password && password.length >= 6" class="validation-icon success">
                <use href="#icon-check-circle" />
              </svg>
            </div>
            <!-- Password Strength Indicator -->
            <div v-if="password" class="password-strength">
              <div class="strength-bar">
                <div class="strength-fill" :class="passwordStrengthClass" :style="{ width: passwordStrengthWidth }"></div>
              </div>
              <span class="strength-label" :class="passwordStrengthClass">{{ passwordStrengthLabel }}</span>
            </div>
            <div v-if="password && password.length < 6" class="error-message">
              <svg class="error-icon">
                <use href="#icon-alert-circle" />
              </svg>
              <span>Password must be at least 6 characters</span>
            </div>
          </div>

          <!-- Confirm Password Input -->
          <div class="form-group">
            <label for="confirmPassword" class="form-label">Confirm Password</label>
            <div class="input-wrapper">
              <svg class="input-icon">
                <use href="#icon-lock" />
              </svg>
              <input
                id="confirmPassword"
                class="form-input"
                :class="{ 'has-error': confirmPassword && password !== confirmPassword }"
                type="password"
                v-model="confirmPassword"
                placeholder="Re-enter password"
                required
                :disabled="isLoading"
              />
              <svg v-if="confirmPassword && password === confirmPassword && password.length >= 6" class="validation-icon success">
                <use href="#icon-check-circle" />
              </svg>
            </div>
            <div v-if="confirmPassword && password !== confirmPassword" class="error-message">
              <svg class="error-icon">
                <use href="#icon-alert-circle" />
              </svg>
              <span>Passwords do not match</span>
            </div>
            <div v-else-if="confirmPassword && password === confirmPassword && password.length >= 6" class="success-message">
              <svg class="success-icon">
                <use href="#icon-check-circle" />
              </svg>
              <span>Passwords match!</span>
            </div>
          </div>

          <!-- Global Error Message -->
          <div v-if="error" class="error-banner">
            <svg class="error-banner-icon">
              <use href="#icon-alert-circle" />
            </svg>
            <span>{{ error }}</span>
          </div>

          <!-- Submit Button -->
          <button
            type="submit"
            class="btn-submit"
            :disabled="isLoading || !isValid"
            v-ripple
          >
            <span v-if="isLoading" class="spinner"></span>
            <svg v-else class="btn-icon">
              <use href="#icon-check" />
            </svg>
            <span>{{ isLoading ? 'Creating Account...' : 'Create Admin Account' }}</span>
          </button>
        </form>
      </GlassCard>

      <!-- Security Info -->
      <GlassCard class="security-info">
        <svg class="security-icon">
          <use href="#icon-shield" />
        </svg>
        <div class="security-content">
          <h3 class="security-title">Secure Setup</h3>
          <p class="security-description">
            Your credentials are stored securely and encrypted. Make sure to remember your password as it cannot be recovered.
          </p>
        </div>
      </GlassCard>
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
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import GlassCard from '@/components/cards/GlassCard.vue'

const router = useRouter()
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const isLoading = ref(false)
const error = ref('')

const isValid = computed(() => {
  return (
    username.value.length >= 3 &&
    password.value.length >= 6 &&
    password.value === confirmPassword.value
  )
})

// Password Strength Calculation
const passwordStrength = computed(() => {
  const pwd = password.value
  if (pwd.length < 6) return 0

  let strength = 0

  // Length check
  if (pwd.length >= 8) strength += 25
  if (pwd.length >= 12) strength += 25

  // Character variety checks
  if (/[a-z]/.test(pwd)) strength += 15
  if (/[A-Z]/.test(pwd)) strength += 15
  if (/[0-9]/.test(pwd)) strength += 10
  if (/[^A-Za-z0-9]/.test(pwd)) strength += 10

  return Math.min(strength, 100)
})

const passwordStrengthClass = computed(() => {
  const strength = passwordStrength.value
  if (strength < 40) return 'weak'
  if (strength < 70) return 'medium'
  return 'strong'
})

const passwordStrengthLabel = computed(() => {
  const strength = passwordStrength.value
  if (strength < 40) return 'Weak'
  if (strength < 70) return 'Medium'
  return 'Strong'
})

const passwordStrengthWidth = computed(() => {
  return `${passwordStrength.value}%`
})

const handleSetup = async () => {
  if (!isValid.value) return

  isLoading.value = true
  error.value = ''

  try {
    const response = await fetch('/auth/setup', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify({
        username: username.value,
        password: password.value
      })
    })

    if (response.ok) {
      const data = await response.json()
      // Success - redirect to login
      router.push('/login')
    } else {
      const errorResponse = await response.json().catch(() => ({ detail: 'Unknown error' }))
      error.value = errorResponse.detail || 'Setup failed. Please try again.'
    }
  } catch (e) {
    error.value = 'Connection failed. Please check your network and try again.'
    console.error('Setup submission error:', e)
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.setup-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-4);
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, var(--background-primary) 0%, var(--background-secondary) 100%);
}

.setup-container {
  width: 100%;
  max-width: 500px;
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
.setup-header {
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

// Setup Card
.setup-card {
  padding: var(--spacing-8);
  margin-bottom: var(--spacing-6);
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

.card-header {
  text-align: center;
  margin-bottom: var(--spacing-8);
}

.form-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-2);
}

.form-subtitle {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}

// Form
.setup-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.form-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
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
  z-index: 2;
}

.validation-icon {
  position: absolute;
  right: var(--spacing-4);
  width: 20px;
  height: 20px;
  pointer-events: none;
  z-index: 2;

  &.success {
    fill: var(--color-success);
  }
}

.form-input {
  width: 100%;
  padding: var(--spacing-4) var(--spacing-12);
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

    ~ .input-icon {
      fill: var(--color-primary);
    }
  }

  &.has-error {
    border-color: var(--color-error);

    &:focus {
      box-shadow: 0 0 0 3px rgba(var(--color-error-rgb), 0.1);
    }
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

// Password Strength Indicator
.password-strength {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
}

.strength-bar {
  flex: 1;
  height: 4px;
  background: var(--background-tertiary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.strength-fill {
  height: 100%;
  transition: all 0.3s ease;
  border-radius: var(--radius-full);

  &.weak {
    background: var(--color-error);
  }

  &.medium {
    background: var(--color-warning);
  }

  &.strong {
    background: var(--color-success);
  }
}

.strength-label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  min-width: 60px;
  text-align: right;

  &.weak {
    color: var(--color-error);
  }

  &.medium {
    color: var(--color-warning);
  }

  &.strong {
    color: var(--color-success);
  }
}

// Validation Messages
.error-message,
.success-message {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--font-size-xs);
  animation: slideDown 0.2s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.error-message {
  color: var(--color-error);
}

.success-message {
  color: var(--color-success);
}

.error-icon,
.success-icon {
  width: 14px;
  height: 14px;
  fill: currentColor;
  flex-shrink: 0;
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

.error-banner-icon {
  width: 20px;
  height: 20px;
  fill: currentColor;
  flex-shrink: 0;
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
    opacity: 0.5;
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

// Security Info
.security-info {
  display: flex;
  gap: var(--spacing-4);
  padding: var(--spacing-5);
  animation: fadeIn 0.6s ease-out 0.4s both;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.security-icon {
  width: 24px;
  height: 24px;
  fill: var(--color-success);
  flex-shrink: 0;
  margin-top: 2px;
}

.security-content {
  flex: 1;
}

.security-title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-1);
}

.security-description {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
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
@include m.respond-below('sm') {  // < 640px
  .setup-view {
    padding: var(--spacing-4);
  }

  .setup-card {
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
