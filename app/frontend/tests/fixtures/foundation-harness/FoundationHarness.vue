<script setup lang="ts">
import { computed, ref } from 'vue'
import BaseButton from '../../../src/components/base/BaseButton.vue'
import BaseDropdown from '../../../src/components/base/BaseDropdown.vue'
import BaseIconButton from '../../../src/components/base/BaseIconButton.vue'
import BaseInput from '../../../src/components/base/BaseInput.vue'
import BaseModal from '../../../src/components/base/BaseModal.vue'
import BasePanel from '../../../src/components/base/BasePanel.vue'
import BaseSheet from '../../../src/components/base/BaseSheet.vue'
import StatusBadge from '../../../src/components/base/StatusBadge.vue'

const query = new URLSearchParams(location.search)
const broken = query.get('broken')
const theme = ref<'dark' | 'light'>('dark')
const name = ref('Night archive')
const quality = ref<string | number>('source')
const modalOpen = ref(false)
const sheetOpen = ref(false)
const state = ref<'loaded' | 'empty' | 'loading' | 'error' | 'disabled'>('loaded')
const themeLabel = computed(() => theme.value === 'dark' ? 'Use light theme' : 'Use dark theme')
function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  document.documentElement.dataset.theme = theme.value
}
</script>

<template>
  <main class="foundation-harness" :class="broken && `broken-${broken}`" :data-state="state">
    <header class="harness-header">
      <div>
        <p class="eyebrow">StreamVault foundation</p>
        <h1>Recording controls</h1>
      </div>
      <BaseIconButton :label="themeLabel" @click="toggleTheme">◐</BaseIconButton>
    </header>

    <BasePanel tone="strong">
      <template #title>Primitive states</template>
      <template #description>Canonical roles across real Vue controls.</template>
      <div class="state-row" aria-label="Preview state">
        <BaseButton v-for="value in ['loaded', 'empty', 'loading', 'error', 'disabled']" :key="value" variant="secondary" size="sm" :aria-pressed="state === value" @click="state = value as typeof state">
          {{ value }}
        </BaseButton>
      </div>

      <div class="status-row" aria-live="polite">
        <StatusBadge tone="success" dot>Ready</StatusBadge>
        <StatusBadge tone="warning" dot>Waiting</StatusBadge>
        <StatusBadge tone="danger" dot :pulse="state === 'loading'">Recording</StatusBadge>
        <StatusBadge tone="info">Info</StatusBadge>
      </div>

      <p v-if="state === 'empty'" class="message">No recordings yet. Add a streamer to begin.</p>
      <p v-else-if="state === 'error'" class="message error-message" role="alert">The archive could not be loaded. Try again.</p>
      <p v-else-if="state === 'loading'" class="message" role="status">Loading recording controls…</p>

      <div class="form-grid">
        <BaseInput v-model="name" label="Archive name" hint="Visible in your library" :disabled="state === 'disabled'" :error="state === 'error' ? 'Choose another archive name' : undefined" />
        <BaseDropdown v-model="quality" label="Recording quality" :disabled="state === 'disabled'" :options="[{ label: 'Source', value: 'source' }, { label: '720p', value: 720 }]" />
      </div>

      <div class="action-row">
        <BaseButton :loading="state === 'loading'" loading-label="Saving recording" :disabled="state === 'disabled'">Save recording</BaseButton>
        <BaseButton variant="secondary" @click="modalOpen = true">Open dialog</BaseButton>
        <BaseButton variant="outline" @click="sheetOpen = true">Open sheet</BaseButton>
      </div>
    </BasePanel>

    <button v-if="broken === 'touch'" class="broken-target" aria-label="Broken target">!</button>
    <div v-if="broken === 'overflow'" class="broken-overflow">overflow fixture</div>
    <p v-if="broken === 'contrast'" class="broken-contrast">contrast fixture</p>

    <BaseModal v-model="modalOpen" title="Confirm recording">
      <p>Save these recording defaults?</p>
      <template #footer><BaseButton @click="modalOpen = false">Confirm</BaseButton></template>
    </BaseModal>
    <BaseSheet v-model="sheetOpen" title="Recording filters">
      <BaseButton variant="secondary" @click="sheetOpen = false">Apply filters</BaseButton>
    </BaseSheet>
  </main>
</template>

<style scoped>
.foundation-harness { min-height: 100dvh; max-width: 64rem; margin: 0 auto; padding: var(--sv-fdn-space-4); padding-bottom: calc(var(--sv-fdn-space-8) + env(safe-area-inset-bottom, 0px)); background: var(--sv-sem-surface-canvas); color: var(--sv-sem-text-primary); }
.harness-header, .state-row, .status-row, .action-row { display: flex; align-items: center; gap: var(--sv-fdn-space-3); flex-wrap: wrap; }
.harness-header { justify-content: space-between; margin-bottom: var(--sv-fdn-space-5); }
.harness-header > div { min-width: 0; flex: 1 1 auto; }
.harness-header h1, .eyebrow { overflow-wrap: anywhere; }
.eyebrow { color: var(--sv-sem-text-secondary); }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr)); gap: var(--sv-fdn-space-4); margin-block: var(--sv-fdn-space-5); }
.message { margin-block: var(--sv-fdn-space-4); color: var(--sv-sem-text-secondary); }
.error-message { color: var(--sv-sem-status-danger); }
.broken-target { width: 20px; height: 20px; min-width: 0; min-height: 0; }
.broken-overflow { width: 500px; }
.broken-contrast { color: #777777; background: #777777; }
@media (prefers-reduced-motion: reduce) { .foundation-harness, .foundation-harness * { scroll-behavior: auto; } }
</style>
