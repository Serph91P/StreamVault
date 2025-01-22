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
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const username = ref('');
const password = ref('');
const confirmPassword = ref('');
const isLoading = ref(false);
const error = ref('');

const isValid = computed(() => {
  return (
    username.value.length >= 3 &&
    password.value.length >= 6 &&
    password.value === confirmPassword.value
  );
});

const handleSetup = async () => {
  if (!isValid.value) return;

  isLoading.value = true;
  error.value = '';

  try {
    const response = await fetch('/auth/setup', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({
        username: username.value,
        password: password.value,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      alert(data.message || 'Setup completed successfully.');
      router.push('/');
    } else {
      const errorResponse = await response.json().catch(() => ({ detail: 'Unknown error' }));
      error.value = errorResponse.detail || 'Setup failed.';
    }
  } catch (e) {
    error.value = 'An error occurred while submitting the setup.';
    console.error('Setup submission error:', e);
  } finally {
    isLoading.value = false;
  }
};
</script>