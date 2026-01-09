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
import { ref, reactive, watch } from 'vue'
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
  const displayName = formData.display_name || formData.username
  
  // First confirmation: Delete streamer?
  if (!confirm(`Delete streamer "${displayName}"?\n\nThis will remove the streamer from your database and unsubscribe from EventSub notifications.`)) {
    return
  }

  // Second confirmation: Delete recordings too?
  const deleteRecordings = confirm(
    `Do you want to delete ALL recordings for "${displayName}" as well?\n\n` +
    `⚠️ WARNING: This cannot be undone!\n\n` +
    `• Click OK to DELETE all recording files\n` +
    `• Click Cancel to KEEP recording files (only remove streamer from database)`
  )
  
  emit('delete', formData.username, deleteRecordings)
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.streamer-form {
  background-color: var(--background-darker);
  padding: var(--spacing-md);
  border-radius: var(--border-radius);
  margin-bottom: var(--spacing-md);
  box-shadow: var(--shadow-sm);
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
  cursor: pointer;
}

.form-control {
  width: 100%;
  padding: 0.5rem 0.75rem;
  font-size: 1rem;
  line-height: 1.5;
  color: var(--text-primary);
  background-color: var(--input-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  transition: all 0.2s var(--vue-ease);
}

.form-control:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(66, 184, 131, 0.25);
  outline: none;
}

.form-control::placeholder {
  color: var(--text-secondary);
  opacity: 0.7;
}

.form-control:disabled {
  background-color: var(--background-darker);
  cursor: not-allowed;
  opacity: 0.7;
}

.is-invalid {
  border-color: var(--danger-color);
}

.is-invalid:focus {
  box-shadow: 0 0 0 2px rgba(220, 53, 69, 0.25);
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
  transition: all 0.2s var(--vue-ease);
  cursor: pointer;
  border: none;
  position: relative;
  overflow: hidden;
}

.btn::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 5px;
  height: 5px;
  background: rgba(255, 255, 255, 0.5);
  opacity: 0;
  border-radius: 100%;
  transform: scale(1, 1) translate(-50%);
  transform-origin: 50% 50%;
}

.btn:focus:not(:active)::after {
  animation: ripple 0.5s ease-out;
}

@keyframes ripple {
  0% {
    transform: scale(0, 0);
    opacity: 0.5;
  }
  100% {
    transform: scale(100, 100);
    opacity: 0;
  }
}

.btn-primary {
  background-color: var(--primary-color);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: var(--primary-color-hover);
  transform: translateY(-1px);
}

.btn-primary:active {
  transform: translateY(0px);
}

.btn-secondary {
  background-color: var(--background-dark);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
}

.btn-secondary:hover:not(:disabled) {
  background-color: var(--background-darker);
  transform: translateY(-1px);
}

.btn-danger {
  background-color: var(--danger-color);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background-color: var(--danger-color-hover);
  transform: translateY(-1px);
}

.btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

/* Checkbox styling */
input[type="checkbox"] {
  appearance: none;
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  background-color: var(--background-darker);
  border: 2px solid var(--border-color);
  border-radius: 4px;
  cursor: pointer;
  margin-right: 8px;
  position: relative;
  vertical-align: middle;
  transition: all 0.2s var(--vue-ease);
}

input[type="checkbox"]:checked {
  background-color: var(--primary-color);
  border-color: var(--primary-color);
}

input[type="checkbox"]:checked::after {
  content: "";
  position: absolute;
  left: 5px;
  top: 2px;
  width: 5px;
  height: 10px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

/* Responsive adjustments for mobile */
@include m.respond-below('md') {  // < 768px
  .form-actions {
    flex-direction: column;
  }
  
  .form-actions .btn {
    width: 100%;
  }
  
  .form-group label:has(input[type="checkbox"]) {
    padding: 8px 0;
  }
}
</style>
