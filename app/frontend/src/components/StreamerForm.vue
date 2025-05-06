<template>
  <div class="streamer-form">
    <h3 v-if="!editMode">Add New Streamer</h3>
    <h3 v-else>Edit Streamer</h3>
    
    <form @submit.prevent="submitForm" class="form">
      <div class="form-group">
        <label for="username">Username:</label>
        <input 
          id="username"
          v-model="formData.username" 
          type="text" 
          class="form-control"
          :class="{ 'is-invalid': errors.username }"
          :disabled="editMode"
          placeholder="Twitch username"
          required
        />
        <div v-if="errors.username" class="invalid-feedback">
          {{ errors.username }}
        </div>
      </div>
      
      <div class="form-group" v-if="editMode">
        <label for="displayName">Display Name:</label>
        <input 
          id="displayName"
          v-model="formData.display_name" 
          type="text" 
          class="form-control"
          placeholder="Display name"
        />
      </div>

      <div class="form-group">
        <label>
          <input 
            type="checkbox" 
            v-model="formData.auto_record"
          />
          Automatically record streams
        </label>
      </div>
      
      <div class="form-group">
        <label>
          <input 
            type="checkbox" 
            v-model="formData.record_public"
          />
          Record VODs/Public Streams
        </label>
      </div>
      
      <div class="form-group">
        <label>
          <input 
            type="checkbox" 
            v-model="formData.record_subscribers"
          />
          Record Subscriber-Only Streams
        </label>
      </div>
      
      <div class="form-group">
        <label for="quality">Record Quality:</label>
        <select 
          id="quality"
          v-model="formData.quality" 
          class="form-control"
        >
          <option value="best">Best (Source)</option>
          <option value="1080p">1080p</option>
          <option value="720p">720p</option>
          <option value="480p">480p</option>
          <option value="worst">Lowest quality</option>
        </select>
      </div>
      
      <div class="form-actions">
        <button 
          type="submit" 
          class="btn btn-primary"
          :disabled="isSubmitting"
        >
          {{ isSubmitting ? 'Saving...' : (editMode ? 'Save Changes' : 'Add Streamer') }}
        </button>
        <button 
          type="button" 
          class="btn btn-secondary"
          @click="$emit('cancel')"
        >
          Cancel
        </button>
        <button 
          v-if="editMode" 
          type="button" 
          class="btn btn-danger"
          @click="confirmDelete"
        >
          Delete Streamer
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import type { Streamer } from '@/types/streamer'

const props = defineProps({
  streamer: {
    type: Object as () => Streamer,
    required: false
  },
  editMode: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['submit', 'cancel', 'delete'])

const isSubmitting = ref(false)
const errors = reactive({
  username: ''
})

// Form data with default values
const formData = reactive({
  username: '',
  display_name: '',
  twitch_id: '',
  auto_record: true,
  record_public: true,
  record_subscribers: false,
  quality: 'best'
})

// If editing, populate form with existing streamer data
watch(() => props.streamer, (streamer) => {
  if (streamer) {
    formData.username = streamer.username || ''
    formData.display_name = streamer.display_name || streamer.username || ''
    formData.twitch_id = streamer.twitch_id || ''
    formData.auto_record = streamer.auto_record !== false
    formData.record_public = streamer.record_public !== false
    formData.record_subscribers = streamer.record_subscribers === true
    formData.quality = streamer.quality || 'best'
  }
}, { immediate: true })

// Form validation
const validateForm = () => {
  let isValid = true
  errors.username = ''

  if (!formData.username.trim()) {
    errors.username = 'Username is required'
    isValid = false
  }

  return isValid
}

// Submit form
const submitForm = async () => {
  if (!validateForm()) return

  try {
    isSubmitting.value = true
    
    const streamerData = {
      username: formData.username.trim(),
      display_name: formData.display_name.trim() || formData.username.trim(),
      twitch_id: formData.twitch_id,
      auto_record: formData.auto_record,
      record_public: formData.record_public,
      record_subscribers: formData.record_subscribers,
      quality: formData.quality
    }
    
    emit('submit', streamerData)
  } catch (error) {
    console.error('Form submission error:', error)
  } finally {
    isSubmitting.value = false
  }
}

const confirmDelete = () => {
  if (confirm(`Are you sure you want to delete ${formData.display_name || formData.username}? This will also remove all recording settings and stream history for this streamer.`)) {
    emit('delete', formData.username)
  }
}
</script>

<style scoped>
.streamer-form {
  background-color: var(--background-darker);
  padding: var(--spacing-md);
  border-radius: var(--border-radius);
  margin-bottom: var(--spacing-md);
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.form-group {
  margin-bottom: var(--spacing-sm);
}

.form-group label {
  display: block;
  margin-bottom: var(--spacing-xs);
  font-weight: 500;
  color: var(--text-primary);
}

.form-group label:has(input[type="checkbox"]) {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-weight: normal;
}

.form-control {
  width: 100%;
  padding: 0.5rem 0.75rem;
  font-size: 1rem;
  line-height: 1.5;
  color: var(--text-primary);
  background-color: var(--background-dark);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  transition: border-color 0.15s ease-in-out;
}

.form-control:focus {
  border-color: var(--primary-color);
  outline: none;
}

.form-control::placeholder {
  color: var(--text-secondary);
}

.is-invalid {
  border-color: var(--danger-color);
}

.invalid-feedback {
  color: var(--danger-color);
  font-size: 0.875em;
  margin-top: 0.25rem;
}

.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-md);
}

.btn {
  display: inline-block;
  font-weight: 500;
  text-align: center;
  vertical-align: middle;
  user-select: none;
  padding: 0.5rem 1rem;
  font-size: 1rem;
  line-height: 1.5;
  border-radius: var(--border-radius);
  transition: all 0.2s ease-in-out;
  cursor: pointer;
  border: none;
}

.btn-primary {
  background-color: var(--primary-color);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: darken(var(--primary-color), 10%);
  transform: translateY(-1px);
}

.btn-secondary {
  background-color: var(--background-dark);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
}

.btn-secondary:hover:not(:disabled) {
  background-color: lighten(var(--background-dark), 5%);
  transform: translateY(-1px);
}

.btn-danger {
  background-color: var(--danger-color);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background-color: darken(var(--danger-color), 10%);
  transform: translateY(-1px);
}

.btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

/* Responsive adjustments for mobile */
@media (max-width: 768px) {
  .form-actions {
    flex-direction: column;
  }
  
  .form-actions .btn {
    width: 100%;
  }
}
</style>
