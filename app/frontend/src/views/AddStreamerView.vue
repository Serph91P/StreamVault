<template>
  <div class="page-view add-streamer-view">
    <!-- Header -->
    <div class="view-header">
      <button @click="goBack" class="btn-back" v-ripple>
        <svg class="icon">
          <use href="#icon-arrow-left" />
        </svg>
        <span>Back</span>
      </button>

      <div class="header-content">
        <h1 class="page-title">
          <svg class="icon-title">
            <use href="#icon-user-plus" />
          </svg>
          Add New Streamer
        </h1>
        <p class="page-subtitle">
          Track your favorite Twitch streamers and get notified when they go live
        </p>
      </div>
    </div>

    <!-- Two big choice cards, no divider -->
    <div class="choice-grid">
      <button
        type="button"
        class="choice-card"
        @click="openManual"
        v-ripple
      >
        <div class="choice-icon-wrapper">
          <svg class="choice-icon"><use href="#icon-user-plus" /></svg>
        </div>
        <h2 class="choice-title">Add by Username</h2>
        <p class="choice-description">
          Enter a Twitch username to add a streamer manually.
        </p>
      </button>

      <button
        type="button"
        class="choice-card"
        @click="openImport"
        v-ripple
      >
        <div class="choice-icon-wrapper accent">
          <svg class="choice-icon"><use href="#icon-download" /></svg>
        </div>
        <h2 class="choice-title">Import from Twitch</h2>
        <p class="choice-description">
          Import streamers you already follow on your Twitch account.
        </p>
      </button>
    </div>

    <!-- Info banner -->
    <div class="info-banner">
      <svg class="info-icon"><use href="#icon-info" /></svg>
      <div class="info-content">
        <p>
          StreamVault will automatically check if these streamers are live
          and start recording based on your settings.
        </p>
      </div>
    </div>

    <!-- Modals routed via /add-streamer/manual and /add-streamer/import.
         Closing returns to /add-streamer (this view). -->
    <BaseModal
      :model-value="manualOpen"
      title="Add by Username"
      size="lg"
      @update:model-value="(v: boolean) => !v && closeModal()"
    >
      <AddStreamerForm @streamer-added="closeAndGoToList" />
    </BaseModal>

    <BaseModal
      :model-value="importOpen"
      title="Import from Twitch"
      size="lg"
      @update:model-value="(v: boolean) => !v && closeModal()"
    >
      <TwitchImportForm @streamers-imported="closeAndGoToList" />
    </BaseModal>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AddStreamerForm from '@/components/AddStreamerForm.vue'
import TwitchImportForm from '@/components/TwitchImportForm.vue'
import BaseModal from '@/components/base/BaseModal.vue'

const router = useRouter()
const route = useRoute()

const manualOpen = computed(() => route.name === 'add-streamer-manual')
const importOpen = computed(() => route.name === 'add-streamer-import')

const goBack = () => router.back()
const openManual = () => router.push({ name: 'add-streamer-manual' })
const openImport = () => router.push({ name: 'add-streamer-import' })
const closeModal = () => router.push({ name: 'add-streamer' })

const closeAndGoToList = () => {
  // Backend WS event "streamer.added" / import-done fills the list, toast
  // shows feedback. Just navigate.
  router.push('/streamers')
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.add-streamer-view {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}

// Header
.view-header {
  margin-bottom: var(--spacing-8);
  max-width: 1200px;
  margin-left: auto;
  margin-right: auto;
}

.btn-back {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--background-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: var(--transition-base);
  margin-bottom: var(--spacing-6);

  .icon {
    width: 16px;
    height: 16px;
    fill: currentColor;
  }

  &:hover {
    background: var(--background-tertiary);
    color: var(--text-primary);
    border-color: var(--color-primary);
  }
}

.header-content {
  text-align: center;
}

.page-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-3);
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-3);
}

.icon-title {
  width: 32px;
  height: 32px;
  fill: var(--color-primary);
}

.page-subtitle {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  max-width: 600px;
  margin: 0 auto;
  line-height: 1.6;
}

// Choice grid
.choice-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--spacing-6);
  max-width: 1100px;
  margin: 0 auto;
}

.choice-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  text-align: left;
  gap: var(--spacing-3);
  padding: var(--spacing-8);
  background: var(--background-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  cursor: pointer;
  transition: var(--transition-base);
  font: inherit;
  color: inherit;
  position: relative;
  overflow: hidden;

  &:hover {
    border-color: var(--color-primary);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  }

  &:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }
}

.choice-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg,
    rgba(var(--color-primary-rgb), 0.15) 0%,
    rgba(var(--color-accent-rgb), 0.15) 100%);
  border-radius: var(--radius-xl);

  &.accent {
    background: linear-gradient(135deg,
      rgba(var(--color-accent-rgb), 0.15) 0%,
      rgba(var(--color-primary-rgb), 0.15) 100%);
  }
}

.choice-icon {
  width: 28px;
  height: 28px;
  fill: var(--color-primary);
}

.choice-title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.choice-description {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}

// Info banner
.info-banner {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-3);
  padding: var(--spacing-5);
  background: rgba(var(--color-primary-rgb), 0.05);
  border: 1px solid rgba(var(--color-primary-rgb), 0.2);
  border-radius: var(--radius-xl);
  margin-top: var(--spacing-8);
  max-width: 1100px;
  margin-left: auto;
  margin-right: auto;
}

.info-icon {
  width: 20px;
  height: 20px;
  fill: var(--color-primary);
  flex-shrink: 0;
  margin-top: 2px;
}

.info-content p {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}

@include m.respond-below('md') {
  .add-streamer-view { padding: var(--spacing-4); }
  .page-title        { font-size: var(--font-size-2xl); }
  .icon-title        { width: 24px; height: 24px; }
  .choice-card       { padding: var(--spacing-6); }
}
</style>
