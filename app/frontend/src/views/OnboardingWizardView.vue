<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GlassCard from '@/components/cards/GlassCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'

/**
 * Unified onboarding wizard. Both `/auth/setup` and `/welcome` route
 * here. The wizard skips Step 1 (Admin) when the admin already exists,
 * which is what `/welcome` callers want, and resumes at the right step
 * after the Twitch OAuth round-trip via `?step=...`.
 */

type StepId = 'admin' | 'twitch' | 'recording' | 'streamers' | 'done'

interface StepDef {
  id: StepId
  title: string
  subtitle: string
  icon: string
}

const STEPS: StepDef[] = [
  { id: 'admin', title: 'Admin Account', subtitle: 'Create your administrator credentials', icon: 'icon-user' },
  { id: 'twitch', title: 'Connect Twitch', subtitle: 'Optional: link Twitch for HEVC + ad-free recordings', icon: 'icon-link' },
  { id: 'recording', title: 'Recording Defaults', subtitle: 'Where and how recordings are stored', icon: 'icon-video' },
  { id: 'streamers', title: 'Add Streamers', subtitle: 'Optional: add your first streamer to track', icon: 'icon-users' },
  { id: 'done', title: 'All Set', subtitle: 'You are ready to go', icon: 'icon-check-circle' },
]

const router = useRouter()
const route = useRoute()

// ---- wizard state ----
const stepIndex = ref(0)
const setupRequired = ref(true)
const welcomeCompleted = ref(false)
const initializing = ref(true)

const currentStep = computed(() => STEPS[stepIndex.value])
const visibleSteps = computed(() =>
  // Hide the admin step from the indicator once the admin account exists.
  setupRequired.value ? STEPS : STEPS.slice(1),
)
const visibleIndex = computed(() => {
  const idx = visibleSteps.value.findIndex((s) => s.id === currentStep.value.id)
  return idx === -1 ? 0 : idx
})

// ---- step 1: admin ----
const adminUsername = ref('')
const adminPassword = ref('')
const adminConfirm = ref('')
const adminSubmitting = ref(false)
const adminError = ref('')
const adminPasswordValid = computed(() => adminPassword.value.length >= 6)
const adminUsernameValid = computed(() => adminUsername.value.trim().length >= 3)
const adminMatch = computed(() => adminPassword.value === adminConfirm.value && adminPasswordValid.value)
const adminFormValid = computed(() => adminUsernameValid.value && adminMatch.value)

async function submitAdmin(): Promise<void> {
  if (!adminFormValid.value || adminSubmitting.value) return
  adminSubmitting.value = true
  adminError.value = ''
  try {
    const response = await fetch('/auth/setup', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({ username: adminUsername.value.trim(), password: adminPassword.value }),
    })
    if (response.ok) {
      setupRequired.value = false
      goToStep('twitch')
    } else {
      const detail = await response.json().catch(() => ({}))
      adminError.value = detail?.detail || 'Setup failed. Please try again.'
    }
  } catch (err) {
    adminError.value = 'Connection failed. Please check your network.'
    console.error('Admin setup failed:', err)
  } finally {
    adminSubmitting.value = false
  }
}

// ---- step 2: twitch ----
const twitchConnected = ref(false)
const twitchChecking = ref(false)
const twitchStarting = ref(false)

async function refreshTwitchStatus(): Promise<void> {
  twitchChecking.value = true
  try {
    const res = await fetch('/api/twitch/connection-status', { credentials: 'include' })
    if (res.ok) {
      const data = await res.json()
      twitchConnected.value = Boolean(data.connected)
    }
  } catch (err) {
    console.error('Twitch status check failed:', err)
  } finally {
    twitchChecking.value = false
  }
}

async function startTwitchOAuth(): Promise<void> {
  twitchStarting.value = true
  try {
    const res = await fetch('/api/twitch/auth-url', { credentials: 'include' })
    const data = await res.json()
    if (data.auth_url) {
      // After callback we want to land back on the wizard at the next step.
      sessionStorage.setItem('oauth_return_url', '/onboarding?step=recording')
      window.location.href = data.auth_url
      return
    }
  } catch (err) {
    console.error('Twitch OAuth start failed:', err)
  } finally {
    twitchStarting.value = false
  }
}

// ---- step 3: recording defaults ----
interface RecordingSettings {
  enabled: boolean
  output_directory: string
  filename_template: string
  filename_preset: string
  default_quality: string
  use_chapters: boolean
  use_category_as_chapter_title: boolean
  max_streams_per_streamer: number
  cleanup_policy: unknown
}

const recording = ref<RecordingSettings | null>(null)
const recordingLoading = ref(false)
const recordingSaving = ref(false)
const recordingError = ref('')

const QUALITY_OPTIONS = ['best', '1080p60', '1080p', '720p60', '720p', '480p', 'audio_only']

async function loadRecordingSettings(): Promise<void> {
  recordingLoading.value = true
  recordingError.value = ''
  try {
    const res = await fetch('/api/recording/settings', { credentials: 'include' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    recording.value = await res.json()
  } catch (err) {
    console.error('Loading recording settings failed:', err)
    recordingError.value = 'Could not load defaults. Using server defaults.'
    recording.value = {
      enabled: true,
      output_directory: '/recordings',
      filename_template:
        '{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}',
      filename_preset: 'default',
      default_quality: 'best',
      use_chapters: true,
      use_category_as_chapter_title: false,
      max_streams_per_streamer: 0,
      cleanup_policy: null,
    }
  } finally {
    recordingLoading.value = false
  }
}

async function saveRecordingSettings(): Promise<void> {
  if (!recording.value || recordingSaving.value) return
  recordingSaving.value = true
  recordingError.value = ''
  try {
    const res = await fetch('/api/recording/settings', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(recording.value),
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      recordingError.value = detail?.detail || 'Saving failed. Please try again.'
      return
    }
    goToStep('streamers')
  } catch (err) {
    console.error('Saving recording settings failed:', err)
    recordingError.value = 'Connection failed.'
  } finally {
    recordingSaving.value = false
  }
}

// ---- step 4: streamers ----
const streamerInput = ref('')
const streamerAdding = ref(false)
const streamerError = ref('')
const addedStreamers = ref<string[]>([])

async function addStreamer(): Promise<void> {
  const username = streamerInput.value.trim().replace(/^@/, '')
  if (!username || streamerAdding.value) return
  streamerAdding.value = true
  streamerError.value = ''
  try {
    const res = await fetch(`/api/streamers/${encodeURIComponent(username)}`, {
      method: 'POST',
      credentials: 'include',
    })
    if (res.ok) {
      addedStreamers.value.push(username)
      streamerInput.value = ''
    } else {
      const detail = await res.json().catch(() => ({}))
      streamerError.value = detail?.detail || `Could not add ${username}.`
    }
  } catch (err) {
    console.error('Add streamer failed:', err)
    streamerError.value = 'Connection failed.'
  } finally {
    streamerAdding.value = false
  }
}

// ---- step 5: done ----
const finishing = ref(false)
const finishError = ref('')

async function finishOnboarding(): Promise<void> {
  if (finishing.value) return
  finishing.value = true
  finishError.value = ''
  try {
    const res = await fetch('/auth/onboarding/complete', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
    if (!res.ok) {
      finishError.value = 'Could not save onboarding state. Continuing anyway.'
    }
  } catch (err) {
    console.error('Finishing onboarding failed:', err)
    finishError.value = 'Could not save onboarding state. Continuing anyway.'
  } finally {
    finishing.value = false
  }
  router.replace('/')
}

// ---- step navigation ----
function indexOfStep(id: StepId): number {
  return STEPS.findIndex((s) => s.id === id)
}

async function goToStep(id: StepId): Promise<void> {
  const target = indexOfStep(id)
  if (target === -1) return
  stepIndex.value = target
  router.replace({ path: route.path, query: { step: id } })
  await onEnterStep(id)
}

async function onEnterStep(id: StepId): Promise<void> {
  if (id === 'twitch' && !twitchChecking.value) {
    await refreshTwitchStatus()
  } else if (id === 'recording' && !recording.value) {
    await loadRecordingSettings()
  }
}

function nextStep(): void {
  const remaining = STEPS.slice(stepIndex.value + 1)
  const next = remaining.find((s) => !(s.id === 'admin' && !setupRequired.value))
  if (next) void goToStep(next.id)
}

function prevStep(): void {
  for (let i = stepIndex.value - 1; i >= 0; i -= 1) {
    if (STEPS[i].id === 'admin' && !setupRequired.value) continue
    void goToStep(STEPS[i].id)
    return
  }
}

const canGoBack = computed(() => {
  if (currentStep.value.id === 'admin') return false
  if (currentStep.value.id === 'twitch' && !setupRequired.value) return false
  if (currentStep.value.id === 'done') return false
  return stepIndex.value > 0
})

// ---- bootstrap ----
async function bootstrap(): Promise<void> {
  initializing.value = true
  try {
    const res = await fetch('/auth/setup', {
      credentials: 'include',
      headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    })
    if (res.ok) {
      const data = await res.json()
      setupRequired.value = Boolean(data.setup_required)
      welcomeCompleted.value = Boolean(data.welcome_completed)
    }
  } catch (err) {
    console.error('Onboarding bootstrap failed:', err)
  }

  // Decide where to start.
  const requested = String(route.query.step || '')
  let target: StepId
  if (setupRequired.value) {
    target = 'admin'
  } else if (requested && STEPS.some((s) => s.id === requested)) {
    target = requested as StepId
  } else if (route.path === '/auth/setup') {
    target = 'twitch'
  } else {
    target = 'twitch'
  }
  initializing.value = false
  await goToStep(target)
}

onMounted(() => {
  void bootstrap()
})
</script>

<template>
  <div class="onboarding-view">
    <div class="onboarding-container">
      <header class="onboarding-header">
        <div class="logo-wrapper">
          <svg class="logo-icon"><use href="#icon-video" /></svg>
        </div>
        <h1 class="app-title">StreamVault</h1>
        <p class="app-subtitle">Setup Wizard</p>
      </header>

      <ol v-if="!initializing" class="step-indicator" :aria-label="`Step ${visibleIndex + 1} of ${visibleSteps.length}`">
        <li
          v-for="(step, idx) in visibleSteps"
          :key="step.id"
          class="step-pill"
          :class="{
            'is-active': step.id === currentStep.id,
            'is-done': idx < visibleIndex,
          }"
        >
          <span class="step-pill-dot">{{ idx + 1 }}</span>
          <span class="step-pill-label">{{ step.title }}</span>
        </li>
      </ol>

      <GlassCard class="wizard-card">
        <div v-if="initializing" class="wizard-loading">
          <span class="spinner" />
          <span>Loading...</span>
        </div>

        <template v-else>
          <div class="wizard-step-header">
            <h2 class="wizard-step-title">{{ currentStep.title }}</h2>
            <p class="wizard-step-subtitle">{{ currentStep.subtitle }}</p>
          </div>

          <!-- ============ Step 1: Admin ============ -->
          <form
            v-if="currentStep.id === 'admin'"
            class="wizard-form"
            @submit.prevent="submitAdmin"
          >
            <label class="form-label" for="wiz-username">Username</label>
            <input
              id="wiz-username"
              v-model="adminUsername"
              type="text"
              class="form-input"
              placeholder="admin"
              :disabled="adminSubmitting"
              autocomplete="username"
              required
            />

            <label class="form-label" for="wiz-password">Password</label>
            <input
              id="wiz-password"
              v-model="adminPassword"
              type="password"
              class="form-input"
              placeholder="At least 6 characters"
              :disabled="adminSubmitting"
              autocomplete="new-password"
              required
            />

            <label class="form-label" for="wiz-confirm">Confirm Password</label>
            <input
              id="wiz-confirm"
              v-model="adminConfirm"
              type="password"
              class="form-input"
              placeholder="Repeat password"
              :disabled="adminSubmitting"
              autocomplete="new-password"
              required
            />

            <div v-if="adminError" class="error-banner">{{ adminError }}</div>

            <div class="wizard-footer">
              <span />
              <BaseButton
                type="submit"
                variant="primary"
                :loading="adminSubmitting"
                :disabled="!adminFormValid"
              >
                Create Admin & Continue
              </BaseButton>
            </div>
          </form>

          <!-- ============ Step 2: Twitch ============ -->
          <div v-else-if="currentStep.id === 'twitch'" class="wizard-step-body">
            <p class="wizard-text">
              Linking your Twitch account is optional but unlocks H.265/1440p
              and ad-free recordings (with Twitch Turbo). You can do this later
              under Settings.
            </p>

            <div class="status-row">
              <svg class="status-icon" :class="{ 'is-good': twitchConnected }">
                <use :href="twitchConnected ? '#icon-check-circle' : '#icon-link'" />
              </svg>
              <span v-if="twitchChecking">Checking status...</span>
              <span v-else-if="twitchConnected">Twitch account connected.</span>
              <span v-else>No Twitch account linked yet.</span>
            </div>

            <div class="wizard-footer">
              <BaseButton variant="outline" :disabled="!canGoBack" @click="prevStep">
                Back
              </BaseButton>
              <div class="wizard-footer-actions">
                <BaseButton
                  v-if="!twitchConnected"
                  variant="outline-primary"
                  :loading="twitchStarting"
                  @click="startTwitchOAuth"
                >
                  Connect Twitch
                </BaseButton>
                <BaseButton variant="primary" @click="nextStep">
                  {{ twitchConnected ? 'Continue' : 'Skip & Continue' }}
                </BaseButton>
              </div>
            </div>
          </div>

          <!-- ============ Step 3: Recording defaults ============ -->
          <div v-else-if="currentStep.id === 'recording'" class="wizard-step-body">
            <div v-if="recordingLoading" class="wizard-loading">
              <span class="spinner" />
              <span>Loading defaults...</span>
            </div>

            <template v-else-if="recording">
              <label class="form-label" for="wiz-output-dir">Output Directory</label>
              <input
                id="wiz-output-dir"
                v-model="recording.output_directory"
                type="text"
                class="form-input"
                placeholder="/recordings"
              />
              <p class="form-hint">
                Absolute path inside the StreamVault container. Make sure it is
                writable and mounted from your host.
              </p>

              <label class="form-label" for="wiz-quality">Default Quality</label>
              <select
                id="wiz-quality"
                v-model="recording.default_quality"
                class="form-input"
              >
                <option v-for="q in QUALITY_OPTIONS" :key="q" :value="q">{{ q }}</option>
              </select>

              <label class="form-checkbox">
                <input v-model="recording.use_chapters" type="checkbox" />
                <span>Write chapter markers (category changes during stream)</span>
              </label>

              <label class="form-checkbox">
                <input v-model="recording.enabled" type="checkbox" />
                <span>Enable recording globally</span>
              </label>

              <div v-if="recordingError" class="error-banner">{{ recordingError }}</div>
            </template>

            <div class="wizard-footer">
              <BaseButton variant="outline" :disabled="!canGoBack" @click="prevStep">
                Back
              </BaseButton>
              <BaseButton
                variant="primary"
                :loading="recordingSaving"
                :disabled="recordingLoading || !recording"
                @click="saveRecordingSettings"
              >
                Save & Continue
              </BaseButton>
            </div>
          </div>

          <!-- ============ Step 4: Streamers ============ -->
          <div v-else-if="currentStep.id === 'streamers'" class="wizard-step-body">
            <p class="wizard-text">
              Add Twitch usernames to start tracking. You can also import your
              entire follow list later from the Streamers page.
            </p>

            <form class="inline-form" @submit.prevent="addStreamer">
              <input
                v-model="streamerInput"
                type="text"
                class="form-input"
                placeholder="Twitch username"
                :disabled="streamerAdding"
              />
              <BaseButton
                type="submit"
                variant="primary"
                :loading="streamerAdding"
                :disabled="!streamerInput.trim()"
              >
                Add
              </BaseButton>
            </form>

            <div v-if="streamerError" class="error-banner">{{ streamerError }}</div>

            <ul v-if="addedStreamers.length" class="added-streamers">
              <li v-for="name in addedStreamers" :key="name">
                <svg class="status-icon is-good"><use href="#icon-check-circle" /></svg>
                <span>{{ name }}</span>
              </li>
            </ul>

            <div class="wizard-footer">
              <BaseButton variant="outline" :disabled="!canGoBack" @click="prevStep">
                Back
              </BaseButton>
              <BaseButton variant="primary" @click="nextStep">
                {{ addedStreamers.length ? 'Continue' : 'Skip & Continue' }}
              </BaseButton>
            </div>
          </div>

          <!-- ============ Step 5: Done ============ -->
          <div v-else-if="currentStep.id === 'done'" class="wizard-step-body wizard-done">
            <svg class="done-icon"><use href="#icon-check-circle" /></svg>
            <h3 class="done-title">Welcome aboard!</h3>
            <p class="wizard-text">
              StreamVault is ready. You can change every setting later from the
              Settings page and add more streamers anytime.
            </p>
            <div v-if="finishError" class="error-banner">{{ finishError }}</div>
            <div class="wizard-footer">
              <BaseButton variant="outline" :disabled="!canGoBack" @click="prevStep">
                Back
              </BaseButton>
              <BaseButton
                variant="primary"
                :loading="finishing"
                @click="finishOnboarding"
              >
                Go to Dashboard
              </BaseButton>
            </div>
          </div>
        </template>
      </GlassCard>
    </div>
  </div>
</template>

<style scoped>
.onboarding-view {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 2rem 1rem;
  background: var(--bg-primary);
}

.onboarding-container {
  width: 100%;
  max-width: 720px;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.onboarding-header {
  text-align: center;
}

.logo-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  margin-bottom: 0.75rem;
}

.logo-icon {
  width: 32px;
  height: 32px;
  color: white;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
}

.app-title {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary);
}

.app-subtitle {
  margin: 0.25rem 0 0;
  color: var(--text-secondary);
  font-size: 0.95rem;
}

.step-indicator {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
}

.step-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--text-secondary);
  font-size: 0.85rem;
  transition: all var(--transition-base);
}

.step-pill.is-active {
  background: rgba(108, 92, 231, 0.15);
  border-color: var(--color-primary);
  color: var(--text-primary);
}

.step-pill.is-done {
  color: var(--color-success);
  border-color: rgba(16, 185, 129, 0.4);
}

.step-pill-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  font-weight: 600;
  font-size: 0.8rem;
}

.step-pill.is-active .step-pill-dot {
  background: var(--color-primary);
  color: white;
}

.step-pill.is-done .step-pill-dot {
  background: var(--color-success);
  color: white;
}

.wizard-card {
  padding: 1.75rem;
}

.wizard-step-header {
  margin-bottom: 1.25rem;
}

.wizard-step-title {
  margin: 0 0 0.25rem;
  font-size: 1.35rem;
  color: var(--text-primary);
}

.wizard-step-subtitle {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.95rem;
}

.wizard-form,
.wizard-step-body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.wizard-text {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.form-label {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.form-hint {
  margin: -0.25rem 0 0;
  color: var(--text-tertiary);
  font-size: 0.8rem;
}

.form-input {
  width: 100%;
  padding: 0.65rem 0.85rem;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
  font-size: 0.95rem;
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(108, 92, 231, 0.2);
}

.form-checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-primary);
  font-size: 0.95rem;
  cursor: pointer;
}

.error-banner {
  padding: 0.65rem 0.85rem;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.4);
  color: var(--color-error);
  font-size: 0.9rem;
}

.wizard-footer {
  margin-top: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.wizard-footer-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.wizard-loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--text-secondary);
  padding: 1rem 0;
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.status-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.65rem 0.85rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

.status-icon {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  color: var(--text-secondary);
}

.status-icon.is-good {
  color: var(--color-success);
}

.inline-form {
  display: flex;
  gap: 0.5rem;
}

.inline-form .form-input {
  flex: 1;
}

.added-streamers {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.added-streamers li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.25);
  color: var(--text-primary);
}

.wizard-done {
  text-align: center;
  align-items: center;
}

.done-icon {
  width: 64px;
  height: 64px;
  color: var(--color-success);
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  margin: 0 auto;
}

.done-title {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.25rem;
}

.wizard-done .wizard-footer {
  width: 100%;
}

@media (max-width: 540px) {
  .step-pill-label {
    display: none;
  }
  .wizard-card {
    padding: 1.25rem;
  }
  .wizard-footer {
    flex-direction: column-reverse;
    align-items: stretch;
  }
  .wizard-footer-actions {
    width: 100%;
  }
  .wizard-footer-actions :deep(button),
  .wizard-footer :deep(button) {
    width: 100%;
  }
}
</style>
