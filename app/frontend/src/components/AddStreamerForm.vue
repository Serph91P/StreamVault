<template>
  <form @submit.prevent="validateAndSubmit" class="streamer-form">
    <div class="input-group">
      <input 
        type="text" 
        v-model="username" 
        :disabled="isLoading || isValidating"
        placeholder="Enter Twitch username" 
        required
        class="input-field interactive-element"
        @blur="validateUsername"
      >
      <button 
        type="button" 
        @click="validateUsername" 
        :disabled="isLoading || isValidating || !username.trim()"
        class="validate-button interactive-element"
      >
        <span v-if="isValidating" class="loader"></span>
        {{ isValidating ? 'Checking...' : 'Check' }}
      </button>
    </div>

    <div v-if="validationMessage" class="validation-message" :class="{ error: !isValid, success: isValid }">
      {{ validationMessage }}
    </div>

    <!-- Erweiterte Einstellungen (nur anzeigen, wenn der Benutzername gültig ist) -->
    <div v-if="isValid && streamerInfo" class="settings-panel">
      <h3>Streamer Settings for {{ streamerInfo.display_name }}</h3>
      
      <div class="streamer-preview">
        <img v-if="streamerInfo.profile_image_url" :src="streamerInfo.profile_image_url" alt="Profile" class="profile-image">
        <div class="streamer-info">
          <div class="streamer-name">{{ streamerInfo.display_name }}</div>
          <div class="streamer-details" v-if="streamerInfo.description">{{ streamerInfo.description }}</div>
        </div>
      </div>

      <!-- Qualitätseinstellungen -->
      <div class="settings-section">
        <h4>Stream Quality</h4>
        <div class="form-group">
          <label for="quality-select">Quality:</label>
          <select 
            id="quality-select"
            v-model="quality" 
            :disabled="isLoading"
            class="quality-select interactive-element"
          >
            <option value="best">Best</option>
            <option value="1080p60">1080p60</option>
            <option value="1080p">1080p</option>
            <option value="720p60">720p60</option>
            <option value="720p">720p</option>
            <option value="480p">480p</option>
            <option value="360p">360p</option>
            <option value="160p">160p</option>
            <option value="audio_only">Audio Only</option>
          </select>
        </div>
      </div>

      <!-- Benachrichtigungseinstellungen -->
      <div class="settings-section">
        <h4>Notification Settings</h4>
        <div class="notification-options">
          <div class="option-item">
            <label class="checkbox-container">
              <input type="checkbox" v-model="notifications.notify_online">
              <span class="checkmark"></span>
              <div class="option-text">
                <span class="option-title">Online</span>
                <span class="option-description">Notify when stream starts</span>
              </div>
            </label>
          </div>
          
          <div class="option-item">
            <label class="checkbox-container">
              <input type="checkbox" v-model="notifications.notify_offline">
              <span class="checkmark"></span>
              <div class="option-text">
                <span class="option-title">Offline</span>
                <span class="option-description">Notify when stream ends</span>
              </div>
            </label>
          </div>
          
          <div class="option-item">
            <label class="checkbox-container">
              <input type="checkbox" v-model="notifications.notify_update">
              <span class="checkmark"></span>
              <div class="option-text">
                <span class="option-title">Updates</span>
                <span class="option-description">Notify on title/category changes</span>
              </div>
            </label>
          </div>
          
          <div class="option-item">
            <label class="checkbox-container">
              <input type="checkbox" v-model="notifications.notify_favorite_category">
              <span class="checkmark"></span>
              <div class="option-text">
                <span class="option-title">Favorites</span>
                <span class="option-description">Notify when streaming favorite games</span>
              </div>
            </label>
          </div>
        </div>
      </div>

      <!-- Aufnahmeeinstellungen -->
      <div class="settings-section">
        <h4>Recording Settings</h4>
        <div class="recording-options">
          <div class="option-item">
            <label class="checkbox-container">
              <input type="checkbox" v-model="recording.enabled">
              <span class="checkmark"></span>
              <div class="option-text">
                <span class="option-title">Enable Recording</span>
                <span class="option-description">Automatically record streams</span>
              </div>
            </label>
          </div>
          
          <div class="form-group" v-if="recording.enabled">
            <label for="recording-quality">Recording Quality:</label>
            <select 
              id="recording-quality"
              v-model="recording.quality" 
              class="form-control"
            >
              <option value="">Use global default</option>
              <option value="best">Best</option>
              <option value="1080p60">1080p60</option>
              <option value="1080p">1080p</option>
              <option value="720p60">720p60</option>
              <option value="720p">720p</option>
              <option value="480p">480p</option>
              <option value="360p">360p</option>
              <option value="160p">160p</option>
            </select>
          </div>
          
          <div class="form-group" v-if="recording.enabled">
            <label for="custom-filename">Custom Filename Template:</label>
            <input 
              id="custom-filename"
              type="text" 
              v-model="recording.custom_filename"
              placeholder="Use global template" 
              class="form-control"
            >
            <div class="help-text">
              Leave empty to use global template
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="form-actions">
      <button 
        type="submit" 
        :disabled="isLoading || isValidating || !isValid" 
        class="submit-button interactive-element"
      >
        <span v-if="isLoading" class="loader"></span>
        {{ isLoading ? 'Adding...' : 'Add Streamer' }}
      </button>
    </div>

    <div v-if="statusMessage" class="status-message" :class="{ error: hasError }">
      {{ statusMessage }}
    </div>
  </form>
</template>

<script setup>
import { ref, reactive } from 'vue'

const username = ref('')
const quality = ref('best') // Default quality
const isLoading = ref(false)
const isValidating = ref(false)
const statusMessage = ref('')
const hasError = ref(false)
const isValid = ref(false)
const validationMessage = ref('')
const streamerInfo = ref(null)

// Benachrichtigungseinstellungen
const notifications = reactive({
  notify_online: true,
  notify_offline: true,
  notify_update: true,
  notify_favorite_category: true
})

// Aufnahmeeinstellungen
const recording = reactive({
  enabled: true,
  quality: '',
  custom_filename: ''
})

// Überprüfe den Benutzernamen über die Twitch API
const validateUsername = async () => {
  if (!username.value.trim()) return

  isValidating.value = true
  validationMessage.value = 'Checking username...'
  isValid.value = false
  streamerInfo.value = null

  try {
    const response = await fetch(`/api/streamers/validate/${username.value.trim().toLowerCase()}`)
    const data = await response.json()
    
    if (response.ok && data.valid) {
      isValid.value = true
      validationMessage.value = 'Valid Twitch username!'
      streamerInfo.value = data.streamer_info
    } else {
      isValid.value = false
      validationMessage.value = data.message || 'Invalid Twitch username'
    }
  } catch (error) {
    isValid.value = false
    validationMessage.value = 'Error checking username'
    console.error('Error:', error)
  } finally {
    isValidating.value = false
  }
}

const validateAndSubmit = () => {
  if (!isValid.value) {
    validateUsername()
    return
  }
  
  addStreamer()
}

const addStreamer = async () => {
  if (!username.value.trim() || !isValid.value) return

  isLoading.value = true
  statusMessage.value = 'Adding streamer...'
  hasError.value = false

  try {
    const cleanUsername = username.value.trim().toLowerCase()
    
    const response = await fetch(`/api/streamers/${cleanUsername}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        quality: quality.value,
        notifications: {
          notify_online: notifications.notify_online,
          notify_offline: notifications.notify_offline,
          notify_update: notifications.notify_update,
          notify_favorite_category: notifications.notify_favorite_category
        },
        recording: {
          enabled: recording.enabled,
          quality: recording.quality,
          custom_filename: recording.custom_filename
        }
      })
    })
    
    const data = await response.json()
    
    if (response.ok) {
      statusMessage.value = 'Streamer added successfully!'
      username.value = ''
      isValid.value = false
      streamerInfo.value = null
      emit('streamer-added')
    } else {
      hasError.value = true
      statusMessage.value = data.message || 'Failed to add streamer'
    }
  } catch (error) {
    hasError.value = true
    statusMessage.value = 'Error connecting to server'
    console.error('Error:', error)
  } finally {
    isLoading.value = false
  }
}

const emit = defineEmits(['streamer-added'])
</script>

<style scoped>
.streamer-form {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  background-color: var(--background-dark, #18181b);
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.input-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.input-field {
  flex: 1;
  min-width: 200px;
  padding: 10px 12px;
  border: 2px solid var(--border-color, #303034);
  border-radius: 6px;
  background-color: var(--background-darker, #0e0e10);
  color: var(--text-primary, #efeff1);
  font-size: 16px;
}

.validate-button {
  padding: 10px 16px;
  background-color: var(--secondary-color, #6441a5);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
}

.validate-button:hover:not(:disabled) {
  background-color: var(--secondary-color-hover, #7d5bbe);
}

.validate-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.quality-select, .form-control {
  background: var(--background-dark, #18181b);
  color: var(--text-primary, #efeff1);
  border: 2px solid var(--border-color, #303034);
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 16px;
  min-width: 120px;
  width: 100%;
  transition: all 0.2s ease;
}

.quality-select:focus, .form-control:focus {
  outline: none;
  border-color: var(--primary-color, #42b883);
  box-shadow: 0 0 0 2px rgba(66, 184, 131, 0.2);
}

.validation-message {
  margin-bottom: 1rem;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 14px;
}

.validation-message.error {
  background-color: rgba(220, 53, 69, 0.1);
  color: #dc3545;
  border: 1px solid rgba(220, 53, 69, 0.2);
}

.validation-message.success {
  background-color: rgba(40, 167, 69, 0.1);
  color: #28a745;
  border: 1px solid rgba(40, 167, 69, 0.2);
}

.settings-panel {
  margin-top: 1.5rem;
  padding: 1rem;
  background-color: var(--background-darker, #0e0e10);
  border-radius: 6px;
  border: 1px solid var(--border-color, #303034);
}

.settings-section {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color, #303034);
}

.settings-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.settings-section h4 {
  margin-top: 0;
  margin-bottom: 1rem;
  color: var(--text-primary, #efeff1);
  font-size: 1.1rem;
  font-weight: 600;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  font-size: 16px;
}

.help-text {
  margin-top: 0.25rem;
  font-size: 14px;
  color: var(--text-secondary, #adadb8);
}

.notification-options,
.recording-options {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
}

.option-item {
  margin-bottom: 1rem;
}

.checkbox-container {
  display: flex;
  align-items: flex-start;
  position: relative;
  padding-left: 35px;
  cursor: pointer;
  font-size: 16px;
  user-select: none;
}

.checkbox-container input {
  position: absolute;
  opacity: 0;
  cursor: pointer;
  height: 0;
  width: 0;
}

.checkmark {
  position: absolute;
  top: 0;
  left: 0;
  height: 24px;
  width: 24px;
  background-color: var(--background-darker, #0e0e10);
  border: 2px solid var(--border-color, #303034);
  border-radius: 4px;
}

.checkbox-container:hover input ~ .checkmark {
  border-color: var(--primary-color, #42b883);
}

.checkbox-container input:checked ~ .checkmark {
  background-color: var(--primary-color, #42b883);
  border-color: var(--primary-color, #42b883);
}

.checkmark:after {
  content: "";
  position: absolute;
  display: none;
}

.checkbox-container input:checked ~ .checkmark:after {
  display: block;
}

.checkbox-container .checkmark:after {
  left: 8px;
  top: 4px;
  width: 5px;
  height: 10px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.option-text {
  display: flex;
  flex-direction: column;
  margin-left: 10px;
}

.option-title {
  font-weight: 500;
  font-size: 16px;
  margin-bottom: 2px;
  color: var(--text-primary, #efeff1);
}

.option-description {
  font-size: 14px;
  color: var(--text-secondary, #adadb8);
  line-height: 1.3;
}

.streamer-preview {
  display: flex;
  align-items: center;
  margin-bottom: 1.5rem;
  padding: 1rem;
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
}

.profile-image {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  margin-right: 1rem;
  object-fit: cover;
}

.streamer-info {
  flex: 1;
}

.streamer-name {
  font-size: 1.2rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.streamer-details {
  font-size: 0.9rem;
  color: var(--text-secondary, #adadb8);
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.form-actions {
  margin-top: 1.5rem;
  display: flex;
  justify-content: flex-end;
}

.submit-button {
  padding: 12px 24px;
  background-color: var(--primary-color, #42b883);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  font-size: 16px;
  transition: background-color 0.2s;
}

.submit-button:hover:not(:disabled) {
  background-color: var(--primary-color-hover, #3ca576);
}

.submit-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.status-message {
  margin-top: 1rem;
  padding: 10px;
  border-radius: 4px;
  text-align: center;
  background-color: rgba(40, 167, 69, 0.1);
  color: #28a745;
  border: 1px solid rgba(40, 167, 69, 0.2);
}

.status-message.error {
  background-color: rgba(220, 53, 69, 0.1);
  color: #dc3545;
  border: 1px solid rgba(220, 53, 69, 0.2);
}

.loader {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: #fff;
  animation: spin 1s ease-in-out infinite;
  margin-right: 8px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.interactive-element {
  transition: all 0.2s ease;
}

.interactive-element:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(66, 184, 131, 0.4);
}

/* Responsive Anpassungen */
@media (max-width: 768px) {
  .notification-options,
  .recording-options {
    grid-template-columns: 1fr;
  }
  
  .input-group {
    flex-direction: column;
  }
  
  .validate-button {
    width: 100%;
    margin-top: 0.5rem;
  }
  
  .form-actions {
    justify-content: center;
  }
  
  .submit-button {
    width: 100%;
  }
  
  .streamer-preview {
    flex-direction: column;
    text-align: center;
  }
  
  .profile-image {
    margin-right: 0;
    margin-bottom: 1rem;
  }
  
  .checkbox-container {
    padding-left: 30px;
  }
  
  .checkmark {
    height: 20px;
    width: 20px;
  }
  
  .checkbox-container .checkmark:after {
    left: 6px;
    top: 3px;
    width: 4px;
    height: 8px;
  }
}

@media (max-width: 480px) {
  .streamer-form {
    padding: 15px;
  }
  
  .settings-panel {
    padding: 0.75rem;
  }
  
  .option-title {
    font-size: 15px;
  }
  
  .option-description {
    font-size: 13px;
  }
}
</style>